# Quant Lab Patterns

## The "Fast-Forward" Warmup
- **Pattern**: Initialize a large population by playing back 1000 candles in a vectorized loop (or parallel bash) before entering the live `while True` loop.
- **Benefit**: Ensures all 50+ metrics (Sharpe, Kelly, etc.) are available the moment the dashboard opens.

## Silent-Catch Network IO
- **Pattern**: Wrap all unauthenticated exchange calls (tickers, balances) in a silent `try/except` that returns the last known value.
- **Benefit**: Keeps the high-frequency terminal "pristine" and focused on alpha logs rather than infrastructure noise.

## Pure Logic Mutation
- **Pattern**: Mutate only the `calculate_dynamic_signals` function string via LLM, then `exec` in a sandbox-like dictionary.
- **Hickey Principle**: Treating code as data allows for extreme extensibility without complecting the core execution engine.

## The WebAssembly Edge Sandbox
- **Pattern**: Instead of heavy Python containers, compile the core execution loop (Durable Object) to WebAssembly (WASM). Embed `Rhai` to execute dynamic AI scripts.
- **Benefit**: Achieves zero-latency WebSocket processing at the Cloudflare Edge while maintaining the flexibility of dynamic LLM-generated logic.
