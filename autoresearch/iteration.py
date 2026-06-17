"""
Autoresearch iteration: a single "train, evaluate, keep/discard" cycle.

Run the live bot for a fixed duration, read pool_stats.json, then:
- If the goal is met (>=3 strategies with current_pnl > TARGET_PNL), exit success
- Otherwise, replace the worst strategies with mutations of the best, and
  signal the caller to run another cycle.

This is the Karpathy autoresearch pattern applied to the trading bot:
modify -> evaluate -> keep/discard -> repeat.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Dict, List, Optional, Tuple

POOL_FILE = "strategy_pool.json"
STATS_FILE = "data/pool_stats.json"
# Single source of truth: import from seed_stats to keep optimizer and UI aligned
try:
    from autoresearch.seed_stats import TARGET_PNL
except ImportError:
    TARGET_PNL = 2000.0
MIN_ABOVE = 3


def count_strategies_above(stats: dict, threshold: float = TARGET_PNL) -> int:
    """Count strategies in pool_stats.json whose current_pnl > threshold.
    Excludes the 'base' strategy because it's hardcoded, not evolvable."""
    n = 0
    for sid, s in stats.items():
        if sid == "base":
            continue
        if s.get("current_pnl", 0.0) > threshold:
            n += 1
    return n


def top_n_stats(stats: dict, n: int = 10) -> List[Tuple[str, float, str]]:
    items = []
    for sid, s in stats.items():
        if sid == "base":
            continue
        items.append((sid, s.get("current_pnl", 0.0), s.get("name", "")))
    items.sort(key=lambda x: -x[1])
    return items[:n]


def run_bot_subprocess(duration_sec: int, log_path: str = "data/iter.log") -> subprocess.Popen:
    """Spawn the bot in a subprocess and return the handle. Caller must
    terminate and wait."""
    with open(log_path, "w") as f:
        proc = subprocess.Popen(
            [sys.executable, "run_dashboard.py"],
            stdout=f, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
    return proc


def stop_bot(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """Send SIGTERM to the whole process group, wait, then SIGKILL."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=timeout)


def load_pool() -> Dict[str, dict]:
    if not os.path.exists(POOL_FILE):
        return {}
    with open(POOL_FILE) as f:
        return json.load(f)


def save_pool(pool: Dict[str, dict]) -> None:
    fd, tmp = tempfile.mkstemp(dir=".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(pool, f, indent=2)
        os.replace(tmp, POOL_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise




def reseed_strategies(pool: Dict[str, dict], stats: dict, n_keep: int = 25) -> None:
    """Keep the best n_keep strategies by current_pnl, replace the rest with
    mutated templates. Uses the autoresearch mutator."""
    from autoresearch.mutator import gen_candidate
    import random
    # Rank strategies by current_pnl from stats
    ranked = []
    for sid, m in pool.items():
        s = stats.get(sid, {})
        ranked.append((sid, m, s.get("current_pnl", 0.0)))
    ranked.sort(key=lambda x: -x[2])
    keep = ranked[:n_keep]
    new_pool = {sid: m for sid, m, _ in keep}
    # Spawn n_keep new mutated strategies from top performers
    rng = random.Random(int(time.time()))
    parents = [m["code"] for _, m, _ in keep if m.get("code")]
    for i in range(n_keep):
        parent = rng.choice(parents) if parents and rng.random() < 0.7 else None
        code = gen_candidate(rng, parent)
        # Validate
        from autoresearch.simulator import compile_strategy
        if compile_strategy(code) is None:
            continue
        sid = uuid.uuid4().hex[:8]
        new_pool[sid] = {
            "id": sid,
            "code": code,
            "name": f"R{i}_{sid[:6]}",
            "explanation": f"reseeded iter",
            "parent_id": None,
        }
    save_pool(new_pool)


def iteration(duration_sec: int = 90, n_keep: int = 25) -> dict:
    """Run one cycle: bot for N seconds, then evaluate."""
    proc = run_bot_subprocess(duration_sec)
    try:
        proc.wait(timeout=duration_sec + 5)
    except subprocess.TimeoutExpired:
        stop_bot(proc)
    # Bot saves on shutdown, but also saves on each tick. Give it a moment.
    time.sleep(1)
    stats = {}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            stats = json.load(f)
    n_above = count_strategies_above(stats, TARGET_PNL)
    return {
        "n_above": n_above,
        "stats": stats,
        "log": "data/iter.log",
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=90, help="seconds to run bot per cycle")
    p.add_argument("--cycles", type=int, default=10, help="max iterations")
    p.add_argument("--n-keep", type=int, default=25, help="strategies kept per reseed")
    p.add_argument("--seed-from-sim", action="store_true",
                   help="Before first cycle, seed pool_stats from a 5000-tick simulation")
    args = p.parse_args()

    if args.seed_from_sim:
        print("Seeding pool_stats from simulation...")
        from autoresearch.seed_stats import seed_pool_stats
        seed_pool_stats(amount=1.0, market_path="data/historical/BTCUSDT_1m_real.csv")

    for cycle in range(args.cycles):
        print(f"\n=== Cycle {cycle}: running bot for {args.duration}s ===")
        res = iteration(args.duration, args.n_keep)
        n = res["n_above"]
        print(f"After cycle {cycle}: {n} strategies with current_pnl > ${TARGET_PNL}")
        for sid, pnl, name in top_n_stats(res["stats"], 5):
            print(f"  {sid[:8]} {name:35s} pnl=${pnl:8.2f}")
        if n >= MIN_ABOVE:
            print(f"\nGOAL REACHED: {n} strategies > ${TARGET_PNL}")
            sys.exit(0)
        # Reseed
        print(f"Reseeding pool, keeping top {args.n_keep}...")
        pool = load_pool()
        reseed_strategies(pool, res["stats"], args.n_keep)
        print(f"Pool now has {len(load_pool())} strategies")

    print(f"\nMax cycles reached without hitting goal")
    sys.exit(1)
