import os
import json
import time
import warnings
import logging
import requests
import random
import re
from dotenv import load_dotenv
from src.strategy_pool import POOL
from src.state_manager import SHARED_STATE

warnings.filterwarnings("ignore")
logger = logging.getLogger("tradeer")

# Load API Key
load_dotenv()

MAX_POOL_SIZE = 200
SIGNALS_PATH = "src/signals.py"

PYTHON_BASE_STRATEGY = """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 30:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 70:
        signals["gemini_sell"] = 1.0
    return signals
"""

MUTATION_PROMPT = """Mutate the parent trading strategy. Keep the TEMPLATE structure identical, only change threshold numbers or combine signals.

TEMPLATE:
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    # MUTATE: change thresholds, combine rsi_2/rsi_14/ema_20
    if rsi_2 < 20:
        signals["gemini_buy"] = 1.0
    elif rsi_2 > 80:
        signals["gemini_sell"] = 1.0
    return signals

RULES:
- state is NOT a dict. Use state.signals.get
- No imports

Parent:
```
PARENT_CODE_GOES_HERE
```

Return ONLY JSON: {"name":"...","explanation":"...","code":"def calculate_dynamic_signals(state, history):\n    symbol = ...\n    rsi_2 = ...\n    signals = {}\n    ...\n    return signals"}"""

def repair_strategy_code(code: str) -> str:
    """
    Strips any import/from lines from AI-generated code as a defense-in-depth
    measure in case the model ignores the prompt constraints.
    """
    lines = code.split('\n')
    cleaned = [l for l in lines if not re.match(r'^\s*(import |from )', l)]
    return '\n'.join(cleaned)


SYNTHETIC_FALLBACKS = [
    # All strategies use RSI-14 (the only indicator that profits on oscillating data)
    # 1
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 30:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 70:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 2
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 25:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 75:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 3
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 35:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 65:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 4
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_14 < 28 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 72:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 5
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_14 < 32 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    if rsi_14 > 68:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 6
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 20:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 80:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 7
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 40:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 60:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 8
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_14 < 35 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 65 and ema_20 > 0:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # 9
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 < 45:
        signals["gemini_buy"] = 0.5
    elif rsi_14 > 55:
        signals["gemini_sell"] = 0.5
    return signals
""",
    # 10
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_14 < 30:
        signals["gemini_buy"] = 1.5
    elif rsi_14 > 70:
        signals["gemini_sell"] = 1.5
    return signals
""",
]

def get_openrouter_json(prompt: str):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OpenRouter Error: OPENROUTER_API_KEY is not set.")
        return None
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "nex-agi/nex-n2-pro:free",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    max_retries = 1
    delay = 1.0
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45.0)
            if response.status_code != 200:
                raise IOError(f"Status {response.status_code} - {response.text}")
                
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Try to find JSON in the response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]
            
            return json.loads(content)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"OpenRouter JSON Error after {max_retries} attempts: {e}")
                return None
            logger.warning(f"OpenRouter JSON Error: {e}. Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
            delay *= 2.0

def try_add_from_ai(prompt: str, name_prefix: str, parent_id: str = None) -> bool:
    """Try to get a strategy from the AI, falling back to a synthetic if it fails."""
    data = get_openrouter_json(prompt)
    if data and "code" in data:
        repaired = repair_strategy_code(data["code"])
        # Try the AI version first
        new_id = POOL.add_strategy(repaired, data.get("name", name_prefix), data.get("explanation", ""), parent_id)
        if new_id:
            logger.info(f"AI Researcher: Added AI strategy {new_id} ({data.get('name')})")
            return True
    
    # AI failed or code invalid — fall back to synthetic
    if SYNTHETIC_FALLBACKS:
        fallback_code = random.choice(SYNTHETIC_FALLBACKS)
        new_id = POOL.add_strategy(fallback_code, f"Fallback_{name_prefix}", f"Pre-built synthetic: {name_prefix}", parent_id)
        if new_id:
            logger.info(f"AI Researcher: Added fallback synthetic {new_id} (AI failed)")
            return True
    return False

def run_evolution():
    logger.info("AI Researcher: Evolution cycle started...")
    
    # 1. Evaluate Current Pool
    state = SHARED_STATE.deref()
    if not state or not state.strategy_stats:
        logger.info("AI Researcher: No stats yet. Bootstrapping...")
        # Bootstrap with 5 initial strategies — skip AI, use synthetic fallbacks directly
        if len(POOL.get_all()) < 5:
            for i in range(len(POOL.get_all()), 5):
                fallback_code = random.choice(SYNTHETIC_FALLBACKS)
                new_id = POOL.add_strategy(fallback_code, f"Fallback_Bootstrap_{i}", "Pre-built synthetic strategy")
                if new_id:
                    logger.info(f"AI Researcher: Bootstrapped fallback {new_id} ({i+1}/5)")
        return

    # 2. Prune Underperformers
    stats = state.strategy_stats
    sorted_ids = sorted([sid for sid in stats.keys() if sid != "base"], 
                        key=lambda sid: stats[sid].pnl, reverse=True)
    
    current_size = len(sorted_ids)
    if current_size > 50:
        to_kill = sorted_ids[int(current_size * 0.8):]
        for sid in to_kill:
            logger.info(f"AI Researcher: Killing underperformer {sid}")
            POOL.remove_strategy(sid)
            sorted_ids.remove(sid)

    # 3. Spawn Children (Mutate)
    if len(POOL.get_all()) < MAX_POOL_SIZE:
        num_to_spawn = min(10, MAX_POOL_SIZE - len(POOL.get_all()))
        logger.info(f"AI Researcher: Spawning {num_to_spawn} new candidates (Current: {len(POOL.get_all())})")
        
        top_performers = sorted_ids[:5] if sorted_ids else []
        for i in range(num_to_spawn):
            if not top_performers:
                parent_code = PYTHON_BASE_STRATEGY
                parent_id = "base"
            else:
                parent_id = random.choice(top_performers)
                strat = POOL.strategies.get(parent_id)
                parent_code = strat.code if strat else ""
            
            # Inject parent code into prompt (simple replace, no .format())
            safe_code = parent_code.replace("```", "'''")
            prompt = MUTATION_PROMPT.replace("PARENT_CODE_GOES_HERE", safe_code)
            try_add_from_ai(prompt, f"Mutant_of_{parent_id}", parent_id)
            time.sleep(1)

def run_forever():
    while True:
        try:
            run_evolution()
        except Exception as e:
            logger.error(f"AI Researcher Error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    run_forever()
