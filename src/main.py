import os
import json
import asyncio
import pandas as pd
import numpy as np
import warnings
import ast
import logging

warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tradeer")

POOL_STATS_FILE = "data/pool_stats.json"

def load_pool_stats() -> dict:
    if os.path.exists(POOL_STATS_FILE):
        try:
            with open(POOL_STATS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pool stats from {POOL_STATS_FILE}: {e}")
    return {}

def save_pool_stats(stats: dict):
    os.makedirs(os.path.dirname(POOL_STATS_FILE), exist_ok=True)
    serializable = {}
    for sid, s in stats.items():
        serializable[sid] = {k: v for k, v in s.items() if k not in ("returns", "equity_curve")}
    try:
        with open(POOL_STATS_FILE, "w") as f:
            json.dump(serializable, f)
    except Exception as e:
        logger.error(f"Failed to save pool stats to {POOL_STATS_FILE}: {e}")

from concurrent.futures import ThreadPoolExecutor
from src.core import WorldState, next_state, CreateOrderCommand, StrategyStats, Ticker
from src.exchange import ExchangeAdapter
from src.signals import calculate_signals
from src.data_fetcher import DataFetcher
from src.state_manager import SHARED_STATE
from src.performance import log_performance
from src.strategy_pool import POOL
from src.analytics import calculate_advanced_metrics
from typing import Dict, List

# Optimized for executing hundreds of pure functions
EXECUTOR = ThreadPoolExecutor(max_workers=10)
FETCH = DataFetcher()

def validate_strategy_code(code_str: str) -> bool:
    """
    Statically analyzes strategy code using AST to block unsafe imports,
    dunder names, and dangerous built-ins.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        logger.warning(f"Strategy code validation failed with syntax error: {e}")
        return False

    dangerous_names = {
        "eval", "exec", "open", "compile", "globals", "locals", "__import__",
        "setattr", "delattr", "system", "subprocess", "os", "sys", "shutil"
    }

    for node in ast.walk(tree):
        # 1. Reject imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            logger.warning("Strategy code validation failed: imports are forbidden.")
            return False

        # 2. Reject attribute access starting with dunder (__)
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                logger.warning(f"Strategy code validation failed: unsafe attribute access to '{node.attr}'.")
                return False

        # 3. Reject dunder names and dangerous functions
        if isinstance(node, ast.Name):
            if node.id.startswith("__") or node.id in dangerous_names:
                logger.warning(f"Strategy code validation failed: unsafe identifier '{node.id}' detected.")
                return False

    return True

def safe_getattr(obj, name: str, default=None):
    """
    Custom wrapper for getattr to block dunder attribute access at runtime.
    """
    if not isinstance(name, str) or name.startswith("__"):
        raise AttributeError(f"Unsafe attribute access blocked: '{name}'")
    return getattr(obj, name, default)

def execute_strategy_code(code_str: str, state: WorldState, history: Dict[str, List[Ticker]]) -> Dict[str, float]:
    """
    Safely execute dynamic strategy code in a restricted namespace.
    Restricts __builtins__ to prevent malicious/unexpected file, system, or import operations.
    """
    if not validate_strategy_code(code_str):
        return {}

    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "pow": pow,
        "range": range,
        "round": round,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "getattr": safe_getattr,
    }
    
    namespace = {
        "__builtins__": safe_builtins,
        "state": state,
        "history": history
    }
    
    try:
        exec(code_str, namespace)
        if "calculate_dynamic_signals" in namespace:
            return namespace["calculate_dynamic_signals"](state, history)
    except Exception as e:
        logger.error(f"Strategy runtime execution error: {e}")
        
    return {}

async def run_bot(symbol: str):
    # --- Initialization ---
    adapter = ExchangeAdapter('binance')
    state = WorldState(timestamp=0)
    history = {symbol: []}
    
    # Persistent stats for the whole pool
    # Key: Strategy ID, Value: Internal tracking dict
    pool_stats = load_pool_stats()
    
    print(f"Starting Multi-Strategy Bot Pool for {symbol}...")
    
    # Fetch historical returns for startup simulations
    print(f"Pre-loading historical returns for {symbol}...")
    try:
        df = FETCH.fetch_ohlcv_de_complected(symbol, limit=1000)
        prices = df['close'].values
        returns_array = np.diff(prices) / prices[:-1] if len(prices) > 1 else np.array([0.0])
    except Exception as e:
        print(f"Failed to fetch historical returns: {e}")
        returns_array = np.random.normal(0.0001, 0.01, 1000)

    # Helper function to simulate/reconstruct history
    def simulate_history(s_id: str) -> tuple:
        equity = [1000.0]
        rets = []
        was_in = False
        for r in returns_array:
            is_in = hash(s_id) % 100 > 40
            periodic_ret = r if is_in else 0.0
            if is_in != was_in:
                periodic_ret -= 0.001
            was_in = is_in
            rets.append(float(periodic_ret))
            equity.append(float(equity[-1] * (1 + periodic_ret)))
        return rets, equity

    # Ensure "base" is initialized
    if "base" not in pool_stats:
        pool_stats["base"] = {
            "pos": 0.0, "entry": 0.0, "pnl": 0.0, "action": "HOLD", "name": "Base HF Scalper",
            "wins": 0, "trades": 0, "drawdown": 0.0, "peak": 0.0, "metrics": {}
        }

    # Pre-populate returns and equity_curve arrays for all existing/loaded strategies
    for sid in list(pool_stats.keys()):
        if "returns" not in pool_stats[sid] or "equity_curve" not in pool_stats[sid]:
            rets, eq = simulate_history(sid)
            pool_stats[sid]["returns"] = rets
            pool_stats[sid]["equity_curve"] = eq
            metrics = calculate_advanced_metrics(rets, eq)
            metrics["hist_equity"] = eq[-100:]
            metrics["hist_returns"] = rets[-100:]
            pool_stats[sid]["metrics"] = metrics

    while True:
        try:
            ticker = await adapter.fetch_ticker(symbol)
            if not ticker:
                print("Ticker is None (fetching failed or rate limited)")
                await asyncio.sleep(2)
                continue
            history[symbol].append(ticker)
            if len(history[symbol]) > 100: history[symbol].pop(0)
            
            price = ticker.bid
            
            # --- 1. Base Strategy Logic (High-Frequency RSI Scalper) ---
            signals = calculate_signals(state, history)
            # Using period 2 for extreme sensitivity
            rsi_2 = signals.get(f"{symbol}_rsi_2")
            
            current_b = pool_stats["base"]
            if rsi_2:
                # Extreme Aggression: Flip positions at 20/80
                if rsi_2 < 20: 
                    if current_b["pos"] <= 0: # Buy if flat or short
                        if current_b["pos"] < 0: # Close short first
                            trade_pnl = (current_b["entry"] - (price * 1.001))
                            current_b["pnl"] += trade_pnl
                            current_b["trades"] += 1
                            if trade_pnl > 0: current_b["wins"] += 1
                        current_b["pos"] = 1.0; current_b["entry"] = price * 1.001; current_b["action"] = "BUY"
                elif rsi_2 > 80:
                    if current_b["pos"] >= 0: # Sell if flat or long
                        if current_b["pos"] > 0: # Close long first
                            trade_pnl = ((price * 0.999) - current_b["entry"])
                            current_b["pnl"] += trade_pnl
                            current_b["trades"] += 1
                            if trade_pnl > 0: current_b["wins"] += 1
                        current_b["pos"] = 0; current_b["action"] = "SELL"
                else:
                    current_b["action"] = "SCALP"
            
            # Unrealized P/L and Peak for Drawdown
            current_total_pnl_b = current_b["pnl"] + ((price * 0.999) - current_b["entry"] if current_b["pos"] > 0 else 0)
            current_b["current_pnl"] = current_total_pnl_b
            if current_total_pnl_b > current_b["peak"]:
                current_b["peak"] = current_total_pnl_b
            dd_b = current_b["peak"] - current_total_pnl_b
            if dd_b > current_b["drawdown"]:
                current_b["drawdown"] = dd_b

            # Append to history arrays for base strategy
            last_eq_b = current_b["equity_curve"][-1] if current_b["equity_curve"] else 1000.0
            new_eq_b = 1000.0 + current_total_pnl_b
            periodic_ret_b = (new_eq_b - last_eq_b) / last_eq_b if last_eq_b > 0 else 0.0
            current_b["returns"].append(periodic_ret_b)
            current_b["equity_curve"].append(new_eq_b)
            if len(current_b["returns"]) > 1000: current_b["returns"].pop(0)
            if len(current_b["equity_curve"]) > 1000: current_b["equity_curve"].pop(0)

            # --- 2. Dynamic Pool Logic (Parallel Execution for 200 strategies) ---
            active_strategies = POOL.get_all()
            
            def run_strategy(strategy):
                s_signals = execute_strategy_code(strategy.code, state, history)
                return strategy.id, strategy.name, s_signals

            # Run in parallel
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(EXECUTOR, run_strategy, s) for s in active_strategies]
            results = await asyncio.gather(*tasks)

            for s_id, s_name, s_signals in results:
                if s_id not in pool_stats:
                    rets, eq = simulate_history(s_id)
                    metrics = calculate_advanced_metrics(rets, eq)
                    metrics["hist_equity"] = eq[-100:]
                    metrics["hist_returns"] = rets[-100:]
                    pool_stats[s_id] = {
                        "pos": 0.0, "entry": 0.0, "pnl": 0.0, "action": "HOLD", "name": s_name,
                        "wins": 0, "trades": 0, "drawdown": 0.0, "peak": 0.0,
                        "returns": rets, "equity_curve": eq, "metrics": metrics
                    }
                
                s_stats = pool_stats[s_id]
                if s_signals.get("gemini_buy") and s_stats["pos"] == 0:
                    s_stats["pos"] = 1.0; s_stats["entry"] = price * 1.001; s_stats["action"] = "BUY"
                elif s_signals.get("gemini_sell") and s_stats["pos"] > 0:
                    trade_pnl = ((price * 0.999) - s_stats["entry"])
                    s_stats["pnl"] += trade_pnl
                    s_stats["trades"] += 1
                    if trade_pnl > 0: s_stats["wins"] += 1
                    s_stats["pos"] = 0; s_stats["action"] = "SELL"
                else:
                    s_stats["action"] = "HOLD"
                
                current_total_pnl = s_stats["pnl"] + ((price * 0.999) - s_stats["entry"] if s_stats["pos"] > 0 else 0)
                s_stats["current_pnl"] = current_total_pnl
                
                # Drawdown calculation
                if current_total_pnl > s_stats["peak"]:
                    s_stats["peak"] = current_total_pnl
                dd = (s_stats["peak"] - current_total_pnl)
                if dd > s_stats["drawdown"]:
                    s_stats["drawdown"] = dd

                # Append to history arrays for dynamic strategy
                last_eq = s_stats["equity_curve"][-1] if s_stats["equity_curve"] else 1000.0
                new_eq = 1000.0 + current_total_pnl
                periodic_ret = (new_eq - last_eq) / last_eq if last_eq > 0 else 0.0
                s_stats["returns"].append(periodic_ret)
                s_stats["equity_curve"].append(new_eq)
                if len(s_stats["returns"]) > 1000: s_stats["returns"].pop(0)
                if len(s_stats["equity_curve"]) > 1000: s_stats["equity_curve"].pop(0)

                signals.update({f"{s_id}_{k}": v for k, v in s_signals.items()})

            # Prune obsolete strategies from stats if they were removed from POOL
            pool_ids = {s.id for s in active_strategies} | {"base"}
            pool_stats = {sid: s for sid, s in pool_stats.items() if sid in pool_ids}

            # --- 2.5 Concurrently recalculate advanced metrics for active strategies ---
            async def calc_metrics_for_strat(sid, s):
                rets_copy = list(s["returns"])
                eq_copy = list(s["equity_curve"])
                metrics = await loop.run_in_executor(
                    EXECUTOR, calculate_advanced_metrics, rets_copy, eq_copy
                )
                metrics["hist_equity"] = eq_copy[-100:]
                metrics["hist_returns"] = rets_copy[-100:]
                return sid, metrics

            metric_tasks = [
                calc_metrics_for_strat(sid, s) for sid, s in pool_stats.items()
            ]
            metric_results = await asyncio.gather(*metric_tasks)
            for sid, metrics in metric_results:
                pool_stats[sid]["metrics"] = metrics

            # --- 3. Update WorldState for Dashboard ---
            strategy_telemetry = {
                sid: StrategyStats(
                    pnl=s["current_pnl"], 
                    position_size=s["pos"], 
                    entry_price=s["entry"], 
                    action=s["action"],
                    metrics=s.get("metrics", {}),
                    name=s["name"],
                    explanation=POOL.strategies[sid].explanation if sid in POOL.strategies else ""
                ) for sid, s in pool_stats.items()
            }

            state, _ = next_state(state, ticker)
            state = state.model_copy(update={
                'signals': signals, 
                'strategy_stats': strategy_telemetry,
                'balance': {'USDT': 1000.0}
            })
            
            SHARED_STATE.reset(state)
            
            # Print overview
            top_performer = max(strategy_telemetry.items(), key=lambda x: x[1].pnl) if strategy_telemetry else ("None", None)
            print(f"[{ticker.datetime}] Strategies: {len(pool_stats)} | Top: {top_performer[0]} ({top_performer[1].pnl:.2f})")
            
            # Persist the paper-trading state across restarts
            save_pool_stats(pool_stats)
            
            await asyncio.sleep(2)
            
        except Exception as e:
            # Silence loop errors for cleaner terminal, but print for debugging
            print(f"Loop error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_bot('BTC/USDT'))
