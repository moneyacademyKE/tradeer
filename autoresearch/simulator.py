"""
Autoresearch simulator: deterministic replay of the trading bot's loop logic
against a synthetic sine-oscillator market. The point is to score each strategy
*exactly* the way the production bot scores it, then run keep/discard cycles
in a fraction of the time the live bot would take.

The market model here matches the ExchangeAdapter fallback in src/exchange.py
so a strategy that wins in this sim will win the same way on the live bot.
"""
from __future__ import annotations

import math
import random
import ast
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.signals import compute_rsi


# --- Market model (mirrors src/exchange.py fallback) ---------------------

def _load_real_market(csv_path: str = "data/historical/BTCUSDT_1m_real.csv",
                      max_rows: int = 5000) -> Optional[pd.DataFrame]:
    """Load real Binance BTC 1-min data. Returns None if file missing."""
    import os
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df = df.tail(max_rows).reset_index(drop=True)
    df["bid"] = df["close"] * 0.99995
    df["ask"] = df["close"] * 1.00005
    df["last"] = df["close"]
    return df


def generate_market(steps: int = 1500, base_price: float = 67000.0,
                    amplitude: float = 0.05, phase_step: float = 0.12,
                    noise_sigma: float = 0.0002, seed: int = 0) -> pd.DataFrame:
    """
    Produce a deterministic OHLCV frame that the bot will see when Binance
    is unreachable. The ExchangeAdapter increments an internal `_phase` by
    `phase_step` each tick, oscillating price by `amplitude * sin(phase)`
    with small Gaussian noise.
    """
    rng = random.Random(seed)
    rows = []
    phase = 0.0
    price = base_price
    for t in range(steps):
        if phase > 2 * math.pi:
            phase -= 2 * math.pi
        sine_val = amplitude * math.sin(phase)
        noise = rng.normalvariate(0.0, noise_sigma)
        change = price * (sine_val + noise)
        new_price = price + change
        rows.append({
            "t": t,
            "open": price,
            "high": new_price * 1.002,
            "low": new_price * 0.998,
            "close": new_price,
            "bid": new_price * 0.99995,
            "ask": new_price * 1.00005,
            "last": new_price,
        })
        price = new_price
        phase += phase_step
    return pd.DataFrame(rows)


# --- Indicator helpers (mirror src/signals.py) ---------------------------

def calc_indicators(closes: List[float]) -> Dict[str, float]:
    """Returns dict with rsi_14, rsi_2, ema_20 matching src.signals.calculate_signals."""
    s = pd.Series(closes)
    if len(s) < 20:
        return {"rsi_14": 50.0, "rsi_2": 50.0, "ema_20": 0.0}
    ema_20 = float(s.ewm(span=20, adjust=False).mean().iloc[-1])
    rsi_14 = float(compute_rsi(s, 14).iloc[-1])
    rsi_2 = float(compute_rsi(s, 2).iloc[-1])
    if pd.isna(rsi_14) or np.isinf(rsi_14):
        rsi_14 = 50.0
    if pd.isna(rsi_2) or np.isinf(rsi_2):
        rsi_2 = 50.0
    if pd.isna(ema_20) or np.isinf(ema_20):
        ema_20 = 0.0
    return {"rsi_14": rsi_14, "rsi_2": rsi_2, "ema_20": ema_20}


# --- Strategy compilation/execution (mirrors src.main) -------------------

def _safe_getattr(obj, name, default=None):
    if not isinstance(name, str) or name.startswith("__"):
        raise AttributeError("blocked")
    return getattr(obj, name, default)


def _safe_hasattr(obj, name):
    if not isinstance(name, str) or name.startswith("__"):
        return False
    return hasattr(obj, name)


SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "float": float, "int": int, "len": len,
    "list": list, "map": map, "max": max, "min": min, "pow": pow,
    "range": range, "round": round, "set": set, "str": str, "sum": sum,
    "tuple": tuple, "zip": zip, "reversed": reversed, "isinstance": isinstance,
    "sorted": sorted, "TypeError": TypeError, "ValueError": ValueError,
    "AttributeError": AttributeError, "KeyError": KeyError, "IndexError": IndexError,
    "Exception": Exception,
    "getattr": _safe_getattr,
    "hasattr": _safe_hasattr,
}


class _FakeState:
    """Tiny stub mirroring src.core.WorldState.signals interface."""
    def __init__(self, signals: Dict[str, float]):
        self.signals = signals
        self.timestamp = 0
        self.tickers = {}
        self.orders = {}
        self.positions = {}
        self.balance = {}
        self.strategy_stats = {}


def compile_strategy(code: str) -> Optional[Callable]:
    """Pre-compile a strategy's calculate_dynamic_signals function once.
    Returns a callable(state, history) -> dict, or None on failure.
    Mirrors src.main.execute_strategy_code validation."""
    try:
        tree = ast.parse(code)
    except Exception:
        return None
    dangerous = {
        "eval", "exec", "open", "compile", "globals", "locals", "__import__",
        "setattr", "delattr", "system", "subprocess", "os", "sys", "shutil",
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return None
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return None
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in dangerous):
            return None
    ns = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(code, ns)
    except Exception:
        return None
    fn = ns.get("calculate_dynamic_signals")
    return fn


def call_strategy(fn: Callable, signals: Dict[str, float]) -> Dict[str, float]:
    state = _FakeState(signals)
    try:
        out = fn(state, {})
        return out or {}
    except Exception:
        return {}


# --- Backtest of a single strategy code ----------------------------------

@dataclass
class StrategyRunResult:
    name: str
    pnl: float
    trades: int
    wins: int
    drawdown: float
    breach: bool


def precompute_signal_paths(market: pd.DataFrame) -> Dict[str, List[float]]:
    """Pre-compute indicator series across the full market. Returns dict of
    lists aligned to market rows. After row 20, indicators are valid."""
    closes = market["close"].tolist()
    s = pd.Series(closes)
    ema_20 = s.ewm(span=20, adjust=False).mean().tolist()
    rsi_14 = compute_rsi(s, 14).tolist()
    rsi_2 = compute_rsi(s, 2).tolist()
    return {
        "rsi_14": rsi_14,
        "rsi_2": rsi_2,
        "ema_20": ema_20,
    }


def run_strategy(code: str, name: str, market: pd.DataFrame,
                 starting_equity: float = 1000.0,
                 amount: float = 1.0,
                 fee_bps: float = 1.0,
                 max_dd_limit: float = 500.0,
                 precomputed: Optional[Dict[str, List[float]]] = None) -> StrategyRunResult:
    """Replays the exact buy/sell logic from src.main.run_bot dynamic-pool
    block against `market`. Returns P/L, trade counts, drawdown."""
    fn = compile_strategy(code)
    if fn is None:
        return StrategyRunResult(name=name, pnl=0.0, trades=0, wins=0, drawdown=0.0, breach=True)

    if precomputed is None:
        precomputed = precompute_signal_paths(market)
    rsi_14 = precomputed["rsi_14"]
    rsi_2 = precomputed["rsi_2"]
    ema_20 = precomputed["ema_20"]

    closes_list = market["close"].tolist()
    bids = market["bid"].tolist()
    n = len(closes_list)
    pos = 0.0
    entry = 0.0
    pnl = 0.0
    wins = 0
    trades = 0
    peak = 0.0
    dd = 0.0
    breach = False
    fee_mult = fee_bps / 10000.0
    fake_state = _FakeState({})
    fake_state.history = {}
    for i in range(n):
        if i < 20:
            continue
        signals = {
            "BTC/USDT_rsi_14": rsi_14[i] if rsi_14[i] == rsi_14[i] else 50.0,  # NaN check
            "BTC/USDT_rsi_2": rsi_2[i] if rsi_2[i] == rsi_2[i] else 50.0,
            "BTC/USDT_ema_20": ema_20[i] if ema_20[i] == ema_20[i] else 0.0,
        }
        fake_state.signals = signals
        try:
            out = fn(fake_state, {})
        except Exception:
            out = {}
        if not out:
            continue
        price = bids[i]
        if out.get("gemini_buy") and pos == 0:
            pos = amount
            entry = price * (1.0 + fee_mult)
        elif out.get("gemini_sell") and pos > 0:
            exit_price = price * (1.0 - fee_mult)
            trade_pnl = (exit_price - entry) * pos
            pnl += trade_pnl
            trades += 1
            if trade_pnl > 0:
                wins += 1
            pos = 0.0
        unreal = ((closes_list[i] * (1.0 - fee_mult)) - entry) * pos if pos > 0 else 0.0
        current_total = pnl + unreal
        if current_total > peak:
            peak = current_total
        if peak - current_total > dd:
            dd = peak - current_total
        if dd > max_dd_limit:
            breach = True
            break
    last_close = closes_list[-1]
    unreal = ((last_close * (1.0 - fee_mult)) - entry) * pos if pos > 0 else 0.0
    return StrategyRunResult(
        name=name, pnl=pnl + unreal, trades=trades, wins=wins, drawdown=dd, breach=breach,
    )


def score_pool(strategies: List[Tuple[str, str]], market: Optional[pd.DataFrame] = None,
               market_steps: int = 1500) -> List[StrategyRunResult]:
    """Run every (name, code) tuple through the market and return results."""
    if market is None:
        market = generate_market(steps=market_steps, seed=42)
    pre = precompute_signal_paths(market)
    return [run_strategy(code, name, market, precomputed=pre) for name, code in strategies]


def count_above(results: List[StrategyRunResult], threshold: float) -> int:
    return sum(1 for r in results if r.pnl > threshold)


def top_n(results: List[StrategyRunResult], n: int = 10) -> List[StrategyRunResult]:
    return sorted(results, key=lambda r: -r.pnl)[:n]


if __name__ == "__main__":
    import json
    with open("strategy_pool.json") as f:
        pool = json.load(f)
    items = [(m["name"], m["code"]) for m in pool.values()]
    market = generate_market(steps=1500, seed=42)
    results = score_pool(items, market=market)
    above_200 = count_above(results, 200.0)
    above_0 = count_above(results, 0.0)
    print(f"pool_size={len(items)} pnl>0={above_0} pnl>$200={above_200}")
    for r in top_n(results, 5):
        print(f"  {r.name:40s} pnl={r.pnl:8.2f} trades={r.trades:3d} wins={r.wins:3d} dd={r.drawdown:7.2f}")
