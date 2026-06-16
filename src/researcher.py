import os
import json
import time
import warnings
import logging
import requests
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
    # Python Base Scalper Strategy
    # Injected variables: 'state' (WorldState), 'history' (Dict[str, List[Ticker]])
    symbol = "BTC/USDT"
    
    # Safely get signals computed by the core
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    
    signals = {}
    if rsi_2 < 20.0:
        signals["gemini_buy"] = 1.0
    elif rsi_2 > 80.0:
        signals["gemini_sell"] = 1.0
    return signals
"""

MUTATION_PROMPT = """
As an expert quantitative trader, you are part of an evolutionary research loop.
You are given the code for a successful "Parent" strategy written in Python. 
Your task is to create a "Child" strategy by applying a mutation (parameter tweak or logic variation).

### Strategy Generation Guidelines:
1. You are an Extreme Aggression Quantitative Researcher. 
2. Your goal is to generate HYPER-ACTIVE scalping strategies for BTC/USDT.
3. Every strategy MUST output signals frequently. Long-term HOLD is unauthorized.
4. Strategies exploit micro-volatility, order flow imbalances, and high-frequency oscillators.

### Input Variables:
- `state`: The WorldState object. You can read signals using `state.signals.get("BTC/USDT_rsi_2", 50.0)` or `state.signals.get("BTC/USDT_rsi_14", 50.0)` or `state.signals.get("BTC/USDT_ema_20", 0.0)`.
- `history`: A dictionary mapping symbols to a list of historical Ticker objects (e.g. `history["BTC/USDT"]`).

### Parent Python Code:
```python
{parent_code}
```

### Output Requirements:
You MUST return a JSON object with the following keys:
1. "name": A short semantic name for the strategy (e.g. "RSI-Reversal-v2").
2. "explanation": A 1-2 sentence explanation of what this specific mutation does and why it might work.
3. "code": The full Python function `calculate_dynamic_signals(state, history)`. The function MUST return a dictionary, e.g. `{{"gemini_buy": 1.0}}` to buy, `{{"gemini_sell": 1.0}}` to sell, or `{{}}` to hold.

### Code Constraints:
1. The code must be a valid Python function definition. Do not include markdown blocks around the python code itself inside the JSON value.
2. Return ONLY the JSON object.
"""

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
    
    max_retries = 3
    delay = 1.0
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30.0)
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

def run_evolution():
    print("AI Researcher: Evolution cycle started...")
    
    # 1. Evaluate Current Pool
    state = SHARED_STATE.deref()
    if not state or not state.strategy_stats:
        print("AI Researcher: No stats yet. Bootstrapping...")
        # Bootstrap with 5 initial strategies from base logic if pool is empty
        if len(POOL.get_all()) < 5:
            prompt = MUTATION_PROMPT.format(parent_code=PYTHON_BASE_STRATEGY)
            for i in range(5):
                data = get_openrouter_json(prompt)
                if data and "code" in data:
                    POOL.add_strategy(data["code"], data.get("name", f"Bootstrap_{i}"), data.get("explanation", ""))
        return

    # 2. Prune Underperformers
    stats = state.strategy_stats
    sorted_ids = sorted([sid for sid in stats.keys() if sid != "base"], 
                        key=lambda sid: stats[sid].pnl, reverse=True)
    
    current_size = len(sorted_ids)
    if current_size > 50:
        to_kill = sorted_ids[int(current_size * 0.8):]
        for sid in to_kill:
            print(f"AI Researcher: Killing underperformer {sid}")
            POOL.remove_strategy(sid)
            sorted_ids.remove(sid)

    # 3. Spawn Children (Mutate)
    if len(POOL.get_all()) < MAX_POOL_SIZE:
        num_to_spawn = min(10, MAX_POOL_SIZE - len(POOL.get_all()))
        print(f"AI Researcher: Spawning {num_to_spawn} new candidates (Current: {len(POOL.get_all())})")
        
        top_performers = sorted_ids[:5] if sorted_ids else []
        for i in range(num_to_spawn):
            if not top_performers:
                parent_code = PYTHON_BASE_STRATEGY
                parent_id = "base"
            else:
                parent_id = random.choice(top_performers)
                strat = POOL.strategies.get(parent_id)
                parent_code = strat.code if strat else ""
                
            prompt = MUTATION_PROMPT.format(parent_code=parent_code)
            data = get_openrouter_json(prompt)
            if data and "code" in data:
                new_id = POOL.add_strategy(
                    data["code"], 
                    data.get("name", f"Mutant_of_{parent_id}"), 
                    data.get("explanation", ""), 
                    parent_id
                )
                print(f"AI Researcher: Added Mutant {new_id} ({data.get('name')})")
            time.sleep(1)

def run_forever():
    while True:
        try:
            run_evolution()
        except Exception as e:
            print(f"AI Researcher Error: {e}")
        time.sleep(60) # Try to add 1 mutant every minute

if __name__ == "__main__":
    run_forever()
