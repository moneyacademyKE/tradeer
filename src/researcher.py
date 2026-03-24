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

MUTATION_PROMPT = """
As an expert quantitative trader, you are part of an evolutionary research loop.
You are given the code for a successful "Parent" strategy. 
Your task is to create a "Child" strategy by applying a mutation (parameter tweak or logic variation).

### Strategy Generation Guidelines:
You are an Extreme Aggression Quantitative Researcher. 
Your goal is to generate HYPER-ACTIVE scalping strategies for BTC/USDT.
CRITICAL: Every strategy MUST output a BUY or SELL signal every 60 seconds. Long-term 'HOLD' is unauthorized.
Strategies should exploit micro-volatility, order flow imbalances, and high-frequency oscillators.

### Parent Strategy Code:
```python
{parent_code}
```

### Output Requirements:
You MUST return a JSON object with the following keys:
1. "name": A short semantic name for the strategy (e.g. "RSI-Trend-Reversal").
2. "explanation": A 1-2 sentence explanation of what this specific mutation does and why it might work.
3. "code": The full python code for the `calculate_dynamic_signals(state: WorldState, history: Dict[str, List[Ticker]]) -> Dict[str, float]` function.
The function must return a dictionary with `gemini_buy` and `gemini_sell` (boolean values).

### Code Constraints:
1. The code must be a pure function.
2. Return ONLY the JSON object. Do not include markdown blocks around the JSON itself, just the raw string or a json code block.
3. The function must return a dictionary with `gemini_buy` and `gemini_sell`.
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
            with open(SIGNALS_PATH, "r") as f:
                base_code = f.read()
            prompt = MUTATION_PROMPT.format(parent_code=base_code)
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
                with open(SIGNALS_PATH, "r") as f:
                    parent_code = f.read()
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
