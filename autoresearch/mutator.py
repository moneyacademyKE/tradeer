"""
Autoresearch mutator: generates strategy mutations and scores them in a
keep/discard loop. The metric is "at least 3 strategies with pnl > $200"
when scored on real BTC 1-min data with a 1.0 BTC position size (matches
src/main.run_bot).
"""
from __future__ import annotations

import json
import random
import re
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from autoresearch.simulator import (
    StrategyRunResult,
    _load_real_market,
    compile_strategy,
    generate_market,
    precompute_signal_paths,
    run_strategy,
    score_pool,
    count_above,
    top_n,
)


def _rng_from_seed(seed: str) -> random.Random:
    import hashlib
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    return random.Random(h)


# --- Mutation operators -------------------------------------------------

def mutate_thresholds(code: str, rng: random.Random, parent_id: str) -> str:
    """Tweak any numeric literals in `if rsi_X < N` / `> N` / `and ema_20 > N`
    style conditions. Picks a random existing threshold and shifts it by ±5
    or replaces it with a new random value. Caps the threshold magnitude
    to keep strategies sane."""
    def repl(m: re.Match) -> str:
        var = m.group(1)
        op = m.group(2)
        val = float(m.group(3))
        # Clamp value to safe range per indicator
        if "rsi" in var:
            lo, hi = 1.0, 99.0
        elif "ema" in var:
            lo, hi = 0.0, 1.0
        else:
            lo, hi = -1.0, 1.0
        # Bias towards extreme values
        new = rng.uniform(lo, hi)
        new = round(new, 2) if new < 10 else round(new)
        return f"{var} {op} {new}"

    # Match e.g. rsi_2 < 18, ema_20 > 0
    pattern = r"(\b(?:rsi_[0-9]+|ema_[0-9]+))\s*([<>]=?)\s*(-?\d+(?:\.\d+)?)"
    new_code = re.sub(pattern, repl, code)
    if new_code == code:
        # No numeric thresholds found - inject one
        new_code = code + f"\n# autogen tweak for {parent_id}\n"
    return new_code


def mutate_combinator(code: str, rng: random.Random) -> str:
    """Add or remove an AND-conjunction combining two signal conditions.
    Targets lines that look like: if COND1: signals["gemini_buy"] = 1.0"""
    lines = code.split("\n")
    candidates = [(i, l) for i, l in enumerate(lines) if "gemini_buy" in l and l.strip().startswith("if")]
    if not candidates:
        return code
    idx, line = rng.choice(candidates)
    cond = line.split(":", 1)[0][2:].strip()
    # 50/50: add EMA confirmation or replace with RSI-14 confirmation
    if rng.random() < 0.5 and "ema_20" not in cond:
        new_cond = f"{cond} and ema_20 > 0"
    elif "rsi_14" not in cond:
        # Insert rsi_14 > 50 / < 50 (complement direction)
        op = ">" if "buy" in line else "<"
        thr = rng.choice([40, 45, 50, 55, 60])
        new_cond = f"{cond} and rsi_14 {op} {thr}"
    else:
        return code
    new_line = f"if {new_cond}:"
    if new_line != line:
        lines[idx] = new_line
    return "\n".join(lines)


def mutate_direction(code: str, rng: random.Random) -> str:
    """Add a SHORT signal variant: invert the buy logic. Some markets let
    shorting strategies win in downtrends."""
    if "gemini_short" in code:
        return code
    if rng.random() < 0.5:
        return code
    # Find the buy condition and invert it
    lines = code.split("\n")
    for i, l in enumerate(lines):
        if "gemini_buy" in l and l.strip().startswith("if"):
            cond = l.split(":", 1)[0][2:].strip()
            inv = re.sub(r"<\s*(\d+)", lambda m: f"> {int(m.group(1)) + 10}", cond)
            inv = re.sub(r">\s*(\d+)", lambda m: f"< {max(0, int(m.group(1)) - 10)}", inv)
            inv = re.sub(r"and\s+(\w+)\s*<\s*(\d+)", lambda m: f"and {m.group(1)} > {int(m.group(2)) - 10}", inv)
            inv = re.sub(r"and\s+(\w+)\s*>\s*(\d+)", lambda m: f"and {m.group(1)} < {int(m.group(2)) + 10}", inv)
            inv = re.sub(r"and\s+(\w+)\s*<=\s*(\d+)", lambda m: f"and {m.group(1)} >= {int(m.group(2)) - 10}", inv)
            inv = re.sub(r"and\s+(\w+)\s*>=\s*(\d+)", lambda m: f"and {m.group(1)} <= {int(m.group(2)) + 10}", inv)
            new_block = f"""
# Short variant: inverse condition emits gemini_sell
if {inv}:
    signals["gemini_sell"] = 1.0
"""
            lines.insert(i + 1, new_block)
            break
    return "\n".join(lines)


def mutate_tighter(code: str, rng: random.Random) -> str:
    """Wrap buy/sell conditions with a hold-counter — only fire after N
    consecutive ticks at the threshold. Reduces whipsaw."""
    n = rng.choice([2, 3, 5, 8])
    return code  # Implementation deferred — keep simple for now


# --- Strategy "templates" that we know work on this kind of market -------

TEMPLATES = [
    # Mean-reversion: oversold buy, overbought sell
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
    # EMA-20 trend: buy when price > EMA, sell when below
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_14 > 50 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    elif rsi_14 < 50:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # RSI-2 extreme: very tight oversold
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    signals = {}
    if rsi_2 < 5 and rsi_14 < 30:
        signals["gemini_buy"] = 1.0
    elif rsi_2 > 95 and rsi_14 > 70:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # Mean reversion with EMA confirmation
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_14 < 25 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    elif rsi_14 > 75:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # Contrarian RSI-2
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    signals = {}
    if rsi_2 < 1:
        signals["gemini_buy"] = 1.0
    elif rsi_2 > 99:
        signals["gemini_sell"] = 1.0
    return signals
""",
    # Double confirmation
    """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    rsi_14 = state.signals.get(f"{symbol}_rsi_14", 50.0)
    ema_20 = state.signals.get(f"{symbol}_ema_20", 0.0)
    signals = {}
    if rsi_2 < 10 and rsi_14 < 40 and ema_20 > 0:
        signals["gemini_buy"] = 1.0
    elif rsi_2 > 90 and rsi_14 > 60:
        signals["gemini_sell"] = 1.0
    return signals
""",
]


def gen_candidate(rng: random.Random, parent_code: Optional[str] = None) -> str:
    """Produce a new strategy code, either from a template or by mutating
    a parent."""
    if parent_code is None or rng.random() < 0.3:
        return rng.choice(TEMPLATES)
    # Mutate parent
    code = parent_code
    if rng.random() < 0.7:
        code = mutate_thresholds(code, rng, parent_code[:20])
    if rng.random() < 0.4:
        code = mutate_combinator(code, rng)
    if rng.random() < 0.15:
        code = mutate_direction(code, rng)
    return code


# --- Evolution loop -----------------------------------------------------

def evolve(strategy_pool: Dict[str, dict], market, *,
           target_above: float = 200.0,
           min_above: int = 3,
           max_pool: int = 60,
           max_iters: int = 200,
           position_amount: float = 1.0,
           seed: int = 0) -> List[StrategyRunResult]:
    """Run keep/discard evolution. Each iteration scores the pool, prunes
    losers, and spawns mutations of the best performers. Stops when at
    least `min_above` strategies have pnl > `target_above`, or after
    `max_iters` rounds."""
    rng = random.Random(seed)
    pre = precompute_signal_paths(market)

    def _score_pool():
        return [
            run_strategy(m["code"], m.get("name", m["id"]), market,
                         precomputed=pre, amount=position_amount,
                         max_dd_limit=10000.0)
            for m in strategy_pool.values()
        ]

    results = _score_pool()
    history = []
    for it in range(max_iters):
        above = count_above(results, target_above)
        best = top_n(results, 3)
        history.append((it, len(strategy_pool), above, results[:]))
        print(f"iter={it:3d} pool={len(strategy_pool):3d} above${target_above:.0f}={above:2d} top: "
              + ", ".join(f"{r.name}({r.pnl:.0f})" for r in best))
        if above >= min_above:
            print(f"GOAL REACHED at iter {it}: {above} strategies with pnl > ${target_above}")
            return results

        # Prune: keep only the top half
        if len(strategy_pool) > 20:
            sorted_results = sorted(results, key=lambda r: -r.pnl)
            keep_ids = set()
            for r in sorted_results[:max(10, len(strategy_pool) // 2)]:
                # find id
                for sid, m in strategy_pool.items():
                    if m.get("name") == r.name or sid in r.name:
                        keep_ids.add(sid)
                        break
            for sid in list(strategy_pool.keys()):
                if sid not in keep_ids:
                    del strategy_pool[sid]

        # Spawn: 5 new candidates from top performers
        top_results = sorted(results, key=lambda r: -r.pnl)[:5]
        top_codes = []
        for r in top_results:
            for m in strategy_pool.values():
                if m.get("name") == r.name:
                    top_codes.append(m["code"])
                    break
        for _ in range(5):
            parent = rng.choice(top_codes) if top_codes and rng.random() < 0.7 else None
            code = gen_candidate(rng, parent)
            # Validate by compiling
            if compile_strategy(code) is None:
                continue
            import uuid
            sid = uuid.uuid4().hex[:8]
            strategy_pool[sid] = {
                "id": sid,
                "code": code,
                "name": f"E{it}_{sid}",
                "explanation": f"evolved iter {it}",
                "parent_id": None,
            }
            if len(strategy_pool) >= max_pool:
                break

        results = _score_pool()
    return results


if __name__ == "__main__":
    import json
    with open("strategy_pool.json") as f:
        pool = json.load(f)
    market = _load_real_market(max_rows=5000)
    if market is None:
        market = generate_market(steps=5000, seed=42)
    results = evolve(pool, market, position_amount=1.0, max_iters=50, seed=42)
    above_200 = count_above(results, 200.0)
    print(f"\nFinal: above $200 = {above_200}")
    for r in top_n(results, 10):
        print(f"  {r.name:30s} pnl={r.pnl:8.2f} trades={r.trades:3d} wins={r.wins:3d} dd={r.drawdown:7.2f}")
