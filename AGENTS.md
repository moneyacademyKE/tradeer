# Memory

## Project Overview
See @README.md for project overview and @package.json for available npm/pnpm commands for this project.

The `autoresearch/` package implements a Karpathy-pattern keep/discard loop that
backtests strategy candidates against real Binance 1-min data and persists a
profitable pool. The live `TARGET_PNL` is read by the dashboard so the same
metric the page shows is the same metric the seeder optimizes. Run it with:
```bash
python3 -m autoresearch.seed_stats
```
See `docs/patterns.md`, `docs/learnings.md`, and `docs/gap_analysis_autoresearch.md`
for design notes.

## Code Style Guidelines
- Use descriptive variable names
- Follow existing patterns in the codebase
- Extract complex conditions into meaningful boolean variables

## Architecture Notes
- The autoresearch harness writes `strategy_pool.json` and `data/pool_stats.json`
  atomically inside `seed_pool_stats`. Treat them as a co-write pair; the
  dashboard surfaces an "Orphans" count to detect desync.
- `TARGET_PNL` lives in `autoresearch/seed_stats.py`. The API endpoint
  `/api/autoresearch/state` imports it so the dashboard badge and the seeder
  filter never disagree.
- The simulator (`autoresearch/simulator.py`) mirrors the live buy/sell rules
  exactly — entry at `bid * 1.0001`, exit at `bid * 0.9999`, mark-to-market
  on `close`, drawdown breach at `MAX_STRATEGY_DRAWDOWN`. A backtest winner is
  a live winner.

## Common Workflows
- Start the bot + dashboard: `python3 run_dashboard.py`
- Run a single autoresearch cycle (re-seeds pool and stats): `python3 -m autoresearch.seed_stats`
- Replay the harness from the command line: `python3 -m autoresearch.mutator`
- Run the iteration runner (live bot + autoresearch loop): `python3 -m autoresearch.iteration --duration 90 --cycles 5`
- Open the trading lab: http://127.0.0.1:8001/static/index.html
- Open the autoresearch dashboard: http://127.0.0.1:8001/static/autoresearch.html
