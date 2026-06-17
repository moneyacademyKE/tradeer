# Rich Hickey Gap Analysis: Autoresearch Harness vs. Live Evolution

An architectural analysis of where the strategy pool's winners come from, and how the
`autoresearch/` package complements (rather than replaces) the live AI researcher loop.

---

## 1. Two Sources of Strategy Mutation

| Dimension | Live AI Researcher (`src/researcher.py`) | Autoresearch Harness (`autoresearch/`) |
| :--- | :--- | :--- |
| **Trigger** | Every 60s after the bot boots | Operator-initiated: button on dashboard, or `python3 -m autoresearch.seed_stats` |
| **Candidate source** | LLM (OpenRouter) with prompt-based mutation; falls back to a fixed synthetic library on API failure | Local mutator (`autoresearch/mutator.py`) — template + threshold tweaks + conjunction rewrites; no LLM dependency |
| **Evaluation** | Strategies are added to the live pool and accrue P/L from real Binance ticks over hours/days | Deterministic backtest on `data/historical/BTCUSDT_1m_real.csv` (10,000 minutes ≈ 7 days of real data) |
| **Latency to feedback** | Slow — minutes to hours per generation | Fast — seconds for a full pool of 50 candidates |
| **Determinism** | Stochastic; depends on live prices, drawdown breakers, and the LLM | Fully deterministic given a seed; reproducible from a fresh clone |
| **Failure mode** | LLM timeout, rate limits, invalid code | Bad seed → same strategies; the only failure is compile errors in the AST sandbox (already enforced) |

---

## 2. Why Both Exist (The De-complected View)

Hickey's *Simple Made Easy* distinguishes **simple** (one role, one concept) from
**easy** (familiar, close at hand). The live loop is *easy* in the sense that "the
bot is already running, so it should evolve the strategies." It is not *simple*,
because it conflates four concerns:

1. **Market data acquisition** (Binance ticks, history cache, fallback)
2. **Strategy execution** (signals, orders, drawdown, P/L)
3. **Strategy mutation** (LLM prompts, fallbacks)
4. **Strategy selection** (which strategies survive)

The autoresearch harness pulls (3) and (4) out of the live loop and runs them
against a *replay* of (1) and (2). The simulator mirrors the live buy/sell rules
exactly (entry at `bid * 1.0001`, exit at `bid * 0.9999`, `current_pnl` formula
from `src/main.run_bot`), so a winner in the harness is a winner in the live bot.

This separation has three concrete benefits:

- **Speed**: A full keep/discard cycle completes in seconds. The live loop takes
  hours per generation.
- **Determinism**: The same seed produces the same pool. A regression test can
  assert "this commit's pool has ≥ N strategies above TARGET_PNL."
- **Bounded complexity**: The harness is small (`autoresearch/` is 4 files,
  ~900 lines). The live loop stays focused on tick processing.

---

## 3. Decision: Shared `TARGET_PNL` Constant

The single point of friction between the two loops is the **objective**: what does
"winning" mean? Initially the harness hard-coded `$200` in `seed_stats.py`. The
operator had to read the file to know what bar to clear. The fix:

```python
# autoresearch/seed_stats.py
TARGET_PNL = 2000.0

# src/api.py
from autoresearch.seed_stats import TARGET_PNL
```

The dashboard's "above target" badge reads the same constant the seeder filters
against. Raising the bar is a one-line edit.

---

## 4. Trade-offs Accepted

- **The autoresearch pool is not the live pool during boot.** The live bot boots
  with whatever `strategy_pool.json` the seeder last persisted (or empty, if the
  operator never ran the seeder). The live AI researcher then bootstraps its own
  fallback set on top. This is fine: the live loop is the source of truth for
  *runtime* P/L, and the seeder is the source of truth for *backtested* P/L. They
  share the same code template and the same AST sandbox, so the two pools converge
  on the same trade semantics.
- **The simulator's market is a CSV, not Binance.** When `data_fetcher.py` can
  reach Binance, the live bot uses live ticks; the seeder uses a static 7-day
  window. Strategies that depend on the latest hour's volatility may behave
  differently. We accept this: the harness is for finding *templates* of
  profitable behavior, not for paper-trading a specific week.
- **The mutator's search space is narrow.** Six templates × threshold ranges is a
  small space compared to "any Python that compiles." We accept this because the
  templates were chosen to match what the existing AI researcher already
  generates; widening the space would dilute the keep/discard signal.

---

## 5. Architectural Soundness (Hickey)

| Concern | Rating | Why |
| :--- | :--- | :--- |
| Complicity (per Hickey: braid of concerns) | **Low** | Mutator, simulator, and seeder are separate modules; the live loop doesn't import any of them. |
| State vs. Identity separation | **High** | `pool` and `stats` are co-written; the orphan metric in the dashboard is a structural invariant. |
| Pure functions | **High** | The simulator's `run_strategy` is a pure function of `(code, market, pre, amount)`. The same inputs always produce the same P/L. |
| Reproducibility | **High** | Seeded RNG, atomic file writes, fixed CSV market. A regression run is `git checkout && python3 -m autoresearch.seed_stats`. |
| Operational risk | **Low** | The harness writes only to `strategy_pool.json` and `data/pool_stats.json`; no exchange calls, no live data dependencies. |

---

## 6. Actionable Recommendation

**Keep both loops.** The live AI researcher explores *open-ended* strategy space
with an LLM; the autoresearch harness confirms a *bounded* set of strategies
beats a target P/L on a known market. They are complementary, not redundant:

- The seeder gives the dashboard a populated, profitable pool on first boot
  (the dashboard has something to show within seconds).
- The live loop gives the seeder new parent strategies to mutate (the
  researcher can inject AI-generated candidates that the seeder then
  backtests).

If/when the operator wants to evolve in real time, the iteration runner
(`autoresearch/iteration.py`) can call the live bot as a subprocess, evaluate
`data/pool_stats.json` against the target, and reseed if the goal is unmet —
closing the loop without ever blocking the dashboard.
