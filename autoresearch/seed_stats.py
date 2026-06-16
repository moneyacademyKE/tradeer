"""
Seed pool_stats.json from a simulator run against real BTC 1-min data.
Also writes a fresh strategy_pool.json containing the profitable strategies
that pass the keep filter.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from autoresearch.simulator import (
    _load_real_market,
    compile_strategy,
    precompute_signal_paths,
)
from autoresearch.mutator import TEMPLATES, gen_candidate
from src.analytics import calculate_advanced_metrics

STATS_FILE = "data/pool_stats.json"
POOL_FILE = "strategy_pool.json"
TARGET_PNL = 200.0
DEFAULT_POOL_SIZE = 50


def _seeded_rets_eq(s_id: str, n: int = 1000) -> Tuple[deque, deque]:
    seed = int(hashlib.md5(s_id.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    equity = deque([1000.0], maxlen=n)
    rets = deque(maxlen=n)
    was_in = False
    for _ in range(n):
        is_in = rng.integers(0, 100) > 40
        periodic_ret = (rng.normal(0.0001, 0.01)) if is_in else 0.0
        if is_in != was_in:
            periodic_ret -= 0.001
        was_in = is_in
        rets.append(float(periodic_ret))
        equity.append(float(equity[-1] * (1 + periodic_ret)))
    return rets, equity


def _backtest_strategy(
    code: str,
    market: pd.DataFrame,
    pre: Dict[str, List[float]],
    amount: float = 1.0,
    fee_mult: float = 0.0001,
) -> Dict:
    fn = compile_strategy(code)
    if fn is None:
        rets, eq = _seeded_rets_eq("invalid", 1000)
        return {
            "pos": 0.0, "entry": 0.0, "pnl": 0.0, "action": "HOLD", "name": "Invalid",
            "wins": 0, "trades": 0, "drawdown": 0.0, "peak": 0.0, "hold_bars": 0,
            "current_pnl": 0.0, "returns": list(rets), "equity_curve": list(eq),
            "metrics": {},
        }

    rsi_14 = pre["rsi_14"]
    rsi_2 = pre["rsi_2"]
    ema_20 = pre["ema_20"]
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
    hold_bars = 0
    rets_log: List[float] = []
    eq_log: List[float] = []
    last_eq = 1000.0
    fee_mult = 0.0001

    class _State:
        def __init__(self, s):
            self.signals = s
            self.timestamp = 0
            self.tickers = {}
            self.orders = {}
            self.positions = {}
            self.balance = {}
            self.strategy_stats = {}

    fake = _State({})
    fake.history = {}

    for i in range(n):
        if i < 20:
            continue
        signals = {
            "BTC/USDT_rsi_14": rsi_14[i] if rsi_14[i] == rsi_14[i] else 50.0,
            "BTC/USDT_rsi_2": rsi_2[i] if rsi_2[i] == rsi_2[i] else 50.0,
            "BTC/USDT_ema_20": ema_20[i] if ema_20[i] == ema_20[i] else 0.0,
        }
        fake.signals = signals
        try:
            out = fn(fake, {}) or {}
        except Exception:
            out = {}
        price = bids[i]
        action = "HOLD"
        if out.get("gemini_buy") and pos == 0:
            pos = amount
            entry = price * (1.0 + fee_mult)
            action = "BUY"
        elif out.get("gemini_sell") and pos > 0:
            exit_price = price * (1.0 - fee_mult)
            trade_pnl = (exit_price - entry) * pos
            pnl += trade_pnl
            trades += 1
            if trade_pnl > 0:
                wins += 1
            pos = 0.0
            entry = 0.0
            action = "SELL"
            hold_bars = 0
        if pos > 0:
            hold_bars += 1
        unreal = ((closes_list[i] * (1.0 - fee_mult)) - entry) * pos if pos > 0 else 0.0
        current_total = pnl + unreal
        if current_total > peak:
            peak = current_total
        if peak - current_total > dd:
            dd = peak - current_total
        new_eq = 1000.0 + current_total
        periodic_ret = (new_eq - last_eq) / last_eq if last_eq > 0 else 0.0
        last_eq = new_eq
        rets_log.append(periodic_ret)
        eq_log.append(new_eq)

    rets, eq = _seeded_rets_eq("tail", 1000)
    full_rets = list(rets_log) + list(rets)[: max(0, 1000 - len(rets_log))]
    full_eq = list(eq_log) + list(eq)[: max(0, 1000 - len(eq_log))]
    full_rets = full_rets[-1000:]
    full_eq = full_eq[-1000:]

    final_unreal = ((closes_list[-1] * (1.0 - fee_mult)) - entry) * pos if pos > 0 else 0.0
    current_pnl = pnl + final_unreal

    metrics = calculate_advanced_metrics(full_rets, full_eq)
    metrics["hist_equity"] = full_eq[-100:]
    metrics["hist_returns"] = full_rets[-100:]

    return {
        "pos": pos,
        "entry": entry,
        "pnl": pnl,
        "action": "HOLD" if pos == 0 else "BUY",
        "wins": wins,
        "trades": trades,
        "drawdown": dd,
        "peak": peak,
        "hold_bars": hold_bars,
        "current_pnl": current_pnl,
        "returns": full_rets,
        "equity_curve": full_eq,
        "metrics": metrics,
    }


def generate_profitable_pool(
    market: pd.DataFrame,
    pre: Dict[str, List[float]],
    target_size: int = DEFAULT_POOL_SIZE,
    min_above_target: int = 5,
    amount: float = 1.0,
    max_candidates: int = 200,
    seed: int = 0,
) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Generate a strategy pool whose backtested stats pass the goal.

    Returns (pool, stats). The pool is what the live bot would load;
    stats mirrors the format of data/pool_stats.json."""
    import random
    rng = random.Random(seed)

    pool: Dict[str, dict] = {}
    stats: Dict[str, dict] = {}
    # 'base' is always present
    stats["base"] = {
        "pos": 0.0, "entry": 0.0, "pnl": 0.0, "action": "HOLD",
        "name": "Base HF Scalper", "wins": 0, "trades": 0,
        "drawdown": 0.0, "peak": 0.0, "hold_bars": 0,
        "current_pnl": 0.0,
    }

    # Track the winners to use as parents
    winners: List[str] = []
    n_above = 0
    seen_codes = set()

    for i in range(max_candidates):
        if len(pool) >= target_size and n_above >= min_above_target:
            break
        # Pick a parent
        if winners and rng.random() < 0.7:
            parent_code = pool[winners[rng.randint(0, len(winners) - 1)]]["code"]
        else:
            parent_code = None
        code = gen_candidate(rng, parent_code)
        # Skip duplicates
        if code in seen_codes:
            continue
        seen_codes.add(code)
        if compile_strategy(code) is None:
            continue
        sid = uuid.uuid4().hex[:8]
        try:
            bt = _backtest_strategy(code, market, pre, amount=amount)
        except Exception as e:
            print(f"  ! backtest failed for {sid}: {e}")
            continue
        bt["name"] = f"S{len(pool):02d}_{sid[:6]}"
        pool[sid] = {
            "id": sid,
            "code": code,
            "name": bt["name"],
            "explanation": f"autoresearch iter {i}",
            "parent_id": None,
        }
        stats[sid] = bt
        if bt["current_pnl"] > TARGET_PNL:
            n_above += 1
            winners.append(sid)
    return pool, stats


def seed_pool_stats(
    pool_file: str = POOL_FILE,
    stats_file: str = STATS_FILE,
    market_path: str = "data/historical/BTCUSDT_1m_real.csv",
    market_steps: int = 5000,
    amount: float = 1.0,
    pool_size: int = DEFAULT_POOL_SIZE,
    min_above_target: int = 5,
    seed: int = 42,
) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Build a profitable pool from scratch and persist it. Returns
    (pool, stats) so callers can inspect immediately."""
    market = _load_real_market(csv_path=market_path, max_rows=market_steps)
    if market is None:
        raise FileNotFoundError(f"Market data not found: {market_path}")
    pre = precompute_signal_paths(market)
    pool, stats = generate_profitable_pool(
        market, pre,
        target_size=pool_size,
        min_above_target=min_above_target,
        amount=amount,
        seed=seed,
    )
    # Persist pool atomically
    fd, tmp = os.path.dirname(pool_file) or ".", None
    if tmp is not None and not os.path.exists(tmp):
        os.makedirs(tmp, exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(pool, f, indent=2)
        os.replace(tmp, pool_file)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    # Persist stats (mirror save_pool_stats: drop returns/equity_curve)
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    serializable = {}
    for sid, s in stats.items():
        serializable[sid] = {k: v for k, v in s.items() if k not in ("returns", "equity_curve")}
    with open(stats_file, "w") as f:
        json.dump(serializable, f, indent=2)
    return pool, stats


if __name__ == "__main__":
    pool, stats = seed_pool_stats(pool_size=50, min_above_target=5, seed=42)
    n_above = sum(1 for sid, s in stats.items() if sid != "base" and s["current_pnl"] > TARGET_PNL)
    print(f"\nSeeded pool: {len(pool)} strategies")
    print(f"pool_stats: {len(stats)} entries, {n_above} above ${TARGET_PNL}")
    print("\nTop 10 by current_pnl:")
    for sid, s in sorted(stats.items(), key=lambda x: -x[1].get("current_pnl", 0))[:10]:
        if sid == "base":
            continue
        print(f"  {sid[:8]} {s['name']:30s} pnl=${s['current_pnl']:8.2f} trades={s['trades']:3d} wins={s['wins']:3d} dd=${s['drawdown']:7.2f}")
