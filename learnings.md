# Quant Lab Learnings

## De-complecting Data
- **Problem**: CCXT API rate limits hit during 200-strategy warmup.
- **Solution**: Implement a `DataFetcher` that treats history as a **static resource** (CSV).
- **Hickey Principle**: Decoupling the "Stateful Service" (API) from the "Immutable Fact" (History).

## High-Frequency Scalping
- **Problem**: 14-period RSI is too sluggish for 1-minute flips.
- **Solution**: 2-period RSI with extreme thresholds (20/80) provides the necessary velocity.
- **DNA Evolution**: Aggressive mutations survive longer in high-volatility environments.

## UI Performance
- **Problem**: Rendering 200 cards with logic traces lags the browser.
- **Solution**: Use Masonry grid and deferred SVG rendering for sparklines.
- **Aesthetics**: OKLCH color palettes provide superior perceptual uniformity for "Flash-at-a-glance" PnL monitoring.

## State Continuity
- **Problem**: Restarting the Python loop erases all running balances and trade counts, breaking the leaderboard.
- **Solution**: Serialize the `pool_stats` dict to a local JSON file on every tick, seamlessly reconstructing the live PnL across hard reboots.

## Edge Computing Limitation (Dynamic Code)
- **Problem**: WASM on Cloudflare Edge cannot compile raw Rust dynamically on the fly (no `exec()` equivalent).
- **Solution**: Embed the `Rhai` scripting engine inside the Worker. Prompt Gemini to output Rhai scripts (instead of Python).
- **Insight**: De-complecting the *execution binary* (Rust) from the *trading logic* (Rhai) provides ultimate scale without sacrificing AI mutability.
