import os
import json
import time
import warnings
warnings.filterwarnings("ignore")
import random
import google.generativeai as genai
from dotenv import load_dotenv
from src.strategy_pool import POOL
from src.state_manager import SHARED_STATE

# Load API Key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MAX_POOL_SIZE = 200
SIGNALS_PATH = "src/signals.py"

RHAI_BASE_STRATEGY = """
// Rhai Base Scalper Strategy
// The Rust DO injects: 'price', 'rsi_2', 'roc', 'momentum' into scope.

if rsi_2 < 20.0 {
    return 1; // BUY
} else if rsi_2 > 80.0 {
    return -1; // SELL
} else {
    return 0; // HOLD
}
"""

MUTATION_PROMPT = """
As an expert quantitative trader, you are part of an evolutionary research loop.
You are given the code for a successful "Parent" strategy written in Rhai. 
Your task is to create a "Child" strategy by applying a mutation (parameter tweak or logic variation).

### Strategy Generation Guidelines:
1. You are an Extreme Aggression Quantitative Researcher. 
2. Your goal is to generate HYPER-ACTIVE scalping strategies for BTC/USDT.
3. Every strategy MUST output a BUY (1) or SELL (-1) frequently. Long-term HOLD (0) is unauthorized.
4. Strategies exploit micro-volatility, order flow imbalances, and high-frequency oscillators.

### Variables injected by the Rust Core:
- `price` (f64): Current asset price
- `rsi_2` (f64): 2-period RSI
- `roc` (f64): Rate of change over 3 periods
- `momentum` (f64): Short term momentum delta

### Parent Rhai Script:
```rhai
{parent_code}
```

### Output Requirements:
You MUST return a JSON object with the following keys:
1. "name": A short semantic name for the strategy (e.g. "Rhai-RSI-Reversal").
2. "explanation": A 1-2 sentence explanation of what this specific mutation does and why it might work.
3. "code": The full Rhai script replacing the parent logic. The script MUST end with a `return 1;` (BUY), `return -1;` (SELL), or `return 0;` (HOLD).

### Code Constraints:
1. The code must be valid Rhai script format (like Rust/JS).
2. Return ONLY the JSON object. Do not include markdown blocks around the JSON itself.
"""

def get_gemini_json(prompt: str):
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    try:
        response = model.generate_content(prompt)
        content = response.text
        # Try to find JSON in the response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content:
            content = content[content.find("{"):content.rfind("}")+1]
        
        return json.loads(content)
    except Exception as e:
        print(f"Gemini JSON Error: {e}")
        return None

def run_evolution():
    print("AI Researcher: Evolution cycle started...")
    
    # 1. Evaluate Current Pool
    state = SHARED_STATE.deref()
    if not state or not state.strategy_stats:
        print("AI Researcher: No stats yet. Bootstrapping...")
        # Bootstrap with 5 initial strategies from base logic if pool is empty
        if len(POOL.get_all()) < 5:
            prompt = MUTATION_PROMPT.format(parent_code=RHAI_BASE_STRATEGY)
            for i in range(5):
                data = get_gemini_json(prompt)
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
                parent_code = RHAI_BASE_STRATEGY
                parent_id = "base"
            else:
                parent_id = random.choice(top_performers)
                strat = POOL.strategies.get(parent_id)
                parent_code = strat.code if strat else ""
                
            prompt = MUTATION_PROMPT.format(parent_code=parent_code)
            data = get_gemini_json(prompt)
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
