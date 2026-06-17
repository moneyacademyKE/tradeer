## The Identity Atom (Managed Continuity)
- **Pattern**: Wrap the current state value in an `Atom` (StateAtom). Only allow identity updates via a functional `swap` when modifying state concurrently, or `reset` when applying an externally fully-computed immutable state.
- **Hickey Principle**: Preserves the identity of the Lab across time while ensuring every state is an immutable, consistent value.

## Pure Functional Transitions (World Evolution)
- **Pattern**: Define a single `next_state` function that takes (State, Event) and returns (NextState, Commands).
- **Benefit**: Decouples the evolution logic from the orchestration mechanics, making the entire Quant Lab testable in a pure repl.

## Value-at-Rest (Immutable History)
- **Pattern**: Treat history as a persistent, immutable list of facts. Pass snapshots of this history to signals rather than mutable objects.
- **Benefit**: Simplifies the logic and ensures that signals are always derived from a consistent, un-complected data source.

## Dynamic Input-Type Normalization
- **Pattern**: When calculations can be invoked under different scopes (e.g., from a pure state transition with single values, or from a historical loop with lists of values), normalize the input type to the richest expected format at the beginning of the calculation (e.g., wrapping single elements in lists).
- **Benefit**: Retains purity of the core transitions while ensuring calculations are robust to varying input sources.

## Babashka Integration & REST Verification
- **Pattern**: Write system integration, boundary checks, and API validation scripts as Babashka scripts (`.clj`). Utilize standard HTTP clients and JSON parsers (`cheshire.core`) to pull and inspect state representations from external endpoints.
- **Benefit**: Decouples verification logic from the language of implementation (Python/FastAPI) and enforces strict JSON/structure guarantees from a clean, external JVM runtime perspective.

## Orchestration vs. Execution Separation
- **Pattern**: For multi-paradigm systems (e.g. AI-driven trading systems), orchestrate slow-moving control loops (evolution, API verification, cleanup, and background tasks) via Babashka/Clojure scripts. Meanwhile, keep high-frequency loops (price ticks, indicators, and state transitions) inside the native runtime (Python) to leverage in-memory state, numpy/pandas speed, and avoid process-spawning bottlenecks.
- **Benefit**: Leverages the best tools for the job: Clojure/Babashka's robust concurrent orchestration, and Python's native library access and dynamic in-memory execution.

## Red/Green Test-Driven Development (TDD)
- **Pattern**: When fixing bugs or implementing new features, write a regression/unit test first that asserts the desired outcome and fails on the current codebase. Fix the code to make the test pass, confirming correctness and guarding against regression.

## Design System Variable Completeness
- **Pattern**: Every CSS layout/component variable must map back to a defined `:root` property. If a component introduces specific styling colors (e.g. up/down signals, accents), declare them in the centralized design tokens blocks first to keep styling de-complected.

## AST-Validated Execution Sandbox
- **Pattern**: Statically analyze untrusted Python code segments using the `ast` compiler module. Walk the nodes to confirm structural rules (no import nodes, no names or attributes prefixed with `__`, and no dangerous builtins) before calling `exec()`.

## Container Event Delegation
- **Pattern**: When dynamically rendering lists of interactive HTML components (such as strategy details), omit inline Javascript attributes. Render elements with simple `data-*` attributes and bind a single click handler to the parent wrapper using `e.target.closest("[data-*]")` to read the key values safely.

## Raw/Adapter Separation
- **Pattern**: When applying retry or failure policies to external API clients, decouple the network fetch from the data formatting and fallback rules. Create a private decorated raw fetch method (`_fetch_ticker_raw`) and a public wrapper adapter method (`fetch_ticker`) that coordinates raw calls and fallback policies.

## Evolution Circuit Breaker
- **Pattern**: Run periodic drawdown checks against in-memory strategy statistics. If a strategy's drawdown exceeds predefined limits, automatically generate close orders, set its state to `BREACHED`, and prune it from the active strategies pool.

## Accessible Native Modal
- **Pattern**: Avoid custom layout overlay structures. Leverage `<dialog>` HTML5 blocks, show them programmatically via `.showModal()`, close them using `.close()`, and attach a click event listener on the element to close when clicked targets match the dialog backdrop container natively.

## Shimmer Skeleton Loaders
- **Pattern**: When rendering dynamic collections over async APIs, load a placeholder template using basic CSS-shimmer keyframe animations. It improves perceived load speed, visually scales elements, and prevents sudden page layout shifts.

## Network-Layer Access Isolation
- **Pattern**: Avoid coding credentials or auth middleware checks directly inside application routes for local-first utility tools. Instead, de-complect the application from access policies by binding API sockets strictly to local loopback addresses (`127.0.0.1`) and leaving the route logic simple. If external access is required, deploy a reverse proxy gateway to terminate authentication.

## Atomic I/O Write-Replace
- **Pattern**: When persisting state snapshots concurrently, perform file write operations inside a temporary file within the target folder, close the file descriptor, and swap the file using an atomic replace (`os.replace` or similar system-level operation). This isolates write-in-progress modifications from external readers.

## Dynamic Credentials integration (Test Auth Injection)
- **Pattern**: In scripts that interact with security-gated APIs, read and parse the project's local configurations (`.env`) using regular expression or string-split mapping. Base64-encode the credentials and attach them as a headers mapping to REST request functions, restoring automated testing continuity.

## Runtime Attribute Access Interceptor
- **Pattern**: Couple compile-time safety (AST validations) with runtime guards. Inject safe custom wrappers (`getattr` / `hasattr`) into the restricted globals of a sandbox compiler environment to catch and raise `AttributeError` for private properties or dunder attributes at run-time.

## Transient Recovery on Startup (Deterministic Simulation)
- **Pattern**: When restoring states from persistent files where large dynamic arrays are pruned, do not attempt to write complex database migrations or save heavy time-series logs. Instead, use a deterministic seed (derived from the persistent entity ID) and a pure simulation function of historical returns to dynamically reconstruct the curves on startup, keeping files lightweight and recovery instant.

## Autoresearch Keep/Discard Loop
- **Pattern**: Treat strategy evolution as an *outer* optimization over the *inner* trading simulation. Define a measurable objective (e.g. "at least N strategies with P/L > T dollars"), backtest every candidate against the same deterministic market, sort by objective value, prune the bottom half, spawn mutations of the top performers, and repeat. The objective is the same number the dashboard surfaces, so the harness and the UI share one source of truth.
- **Benefit**: The optimizer is decoupled from the live bot. The harness can iterate in seconds against historical data without waiting for the slow real-time loop to discover winners, while the live bot continues to use whichever pool the harness last persisted.
- **Application**: The Karpathy autoresearch pattern applied to trading — mutate a parent's numeric thresholds, compile under the same AST sandbox the live bot uses, score on a fixed Binance 1-min CSV, keep/discard based on the persisted `current_pnl`.

## Backtest Mirrors Live Buy/Sell Semantics
- **Pattern**: When scoring candidate code, replay the *exact* buy/sell rules from the live runtime (entry at `bid * 1.0001`, exit at `bid * 0.9999`, position size 1.0, mark-to-market on `close`, drawdown breach at the env-configured limit) rather than a parallel, simpler model. A strategy that wins the backtest must make the same trade on the live bot or the loop is misleading.
- **Benefit**: A passing backtest is a sufficient (not just necessary) condition for a strategy to be a winner. The optimizer and the runtime are de-complected but refer to the same equation.

## Shared `TARGET_PNL` Constant for Optimizer and UI
- **Pattern**: The autoresearch target threshold lives in one module (`autoresearch/seed_stats.TARGET_PNL`). The API endpoint that powers the dashboard imports the same constant, so the "above target" badge on the page is byte-for-byte the same filter the seeder applies.
- **Benefit**: Raising the bar is a one-line edit; the UI updates without redeploy, and the operator can never get a "12 strategies above target" page that disagrees with the next seeder run.

## Atomic Pool + Stats Co-Write
- **Pattern**: When persisting the optimized pool and its corresponding `pool_stats.json`, write both files inside the same Python function using `tempfile.mkstemp` + `os.replace` per file. A reader can still see a brief window where the new pool is on disk but the old stats are, but the inverse (new stats, old pool) is impossible because the stats file is only meaningful when its strategy IDs are present in the pool.
- **Benefit**: Avoids the orphan-state failure mode where `pool_stats.json` references strategy IDs that no longer exist in `strategy_pool.json`. The dashboard can detect orphans and surface a warning, but a single seeder call never produces them.

## Event-Loop Unblocking
- **Pattern**: When introducing long-running or CPU-intensive operations inside FastAPI async routes, always execute them inside a worker thread via `asyncio.to_thread` or declare the router path using a standard synchronous `def` handler (which FastAPI executes inside its external thread pool). This preserves the single-threaded event loop's responsiveness for concurrent network I/O.

## Babashka Orchestration Pipeline
- **Pattern**: For multi-paradigm applications requiring OS process management, REST verification, and data assertions, write orchestration workflows as Babashka scripts (`.clj`). Utilize Clojure's native thread-safe concurrency models, HTTP client packages, and clean process control wrappers to coordinate external actions and verify system health without adding overhead or signal handling complications to the main runtime application.

## Shared Constant Single Source of Truth
- **Pattern**: Any threshold or goal metric referenced by both the optimizer/seeder and the dashboard/UI must live in *one* module and be imported everywhere else. Never copy-paste numeric literals across files.
- **Anti-pattern**: `TARGET_PNL = 200.0` in `iteration.py` while `TARGET_PNL = 2000.0` in `seed_stats.py` — the operator can never trust the iteration runner's "goal reached" output.
- **Benefit**: A one-line edit to the constant is automatically reflected in every metric, badge, and log line that references it.

## Thread-Safe Singleton with I/O Outside Lock
- **Pattern**: When a singleton holds mutable state (e.g. `StrategyPool.strategies` dict) and is accessed from multiple threads, wrap all dict mutations in a `threading.Lock`. Crucially, **release the lock before** performing file I/O (the atomic write). Holding a lock across a syscall serializes all readers for the duration of disk writes, causing unnecessary contention.
- **Implementation**: `with self._lock: data = {copy dict}` then `os.replace(tmp, path)` outside the lock.

## Top-of-File Import Invariant
- **Pattern**: All `import` statements belong at the top of the module, regardless of where the using function is defined. Python resolves names at *call time*, so a function defined before an import statement will work if the import runs first — but a reader cannot tell without careful inspection, and removing or re-ordering the import produces a hard-to-diagnose `NameError`.
- **Anti-pattern**: `import tempfile` on line 97 while `tempfile.mkstemp(...)` is called in a function body on line 86.
