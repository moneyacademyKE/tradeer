## Identity vs. State (Hickey Principle)
- **Problem**: Conflating identity with state can lead to inconsistent transformations and race conditions.
- **Solution**: Decouple the **Identity** of the Lab (A container/Atom) from the **State** (The immutable value/snapshot).
- **Hardening**: Refactored `StateAtom` to use a functional `swap(f, *args)` that transforms the current immutable value into a new one atomically.
- **Bug Fix**: Discovered that passing a raw state value directly to `swap(state)` raises a `TypeError` (since `swap` expects a transformation function). Replaced with `reset(state)` for explicit value updates.

## The Pure State-Transition Function
- **Knowledge**: Every change in the system is a function of (State, Event) -> (NextState, Commands).
- **Benefit**: This allows for complete determinism, easy backtesting, and de-complected logic (e.g. signal calculation is a pure derivation of the state).
- **Bug Fix**: Fixed `calculate_signals` to handle cases where it receives a single `Ticker` rather than a list of tickers, avoiding `TypeError: object of type 'Ticker' has no len()` when called from the pure `next_state` transitions.

## Value-at-Rest Optimization
- **Optimization**: Switched from rebuilding entire DataFrames to passing immutable snapshots of history to signal logic.
- **Result**: Drastic reduction in CPU overhead and memory churn during high-frequency trading loops.

## Silent Loop Failures & API Boundaries
- **Problem**: Swallowing generic exceptions in the background execution loop (`try/except Exception: pass`) masked critical initialization and type errors.
- **Solution**: Always log loop exceptions to standard error/output to prevent silent failures.
- **Problem**: API calls like `ccxt` fetching ticker can return `None` due to rate limits or connection drops.
- **Solution**: Sanitize boundary values immediately before appending to persistent state/history to prevent downstream `AttributeError` and data corruption.

## JSON Serialization Compliance
- **Problem**: Mathematical calculations (such as rolling RSI or standard deviation) can generate `NaN`, `Infinity`, or `-Infinity` values (e.g. when division by zero or empty subsets occur). Storing these native Python float values in state will crash JSON serialization (e.g. `GET /api/state`) with `ValueError: Out of range float values are not JSON compliant`.
- **Solution**: Explicitly check and sanitize all calculated float signals using `pd.isna(v)` and `np.isinf(v)` to replace any out-of-range floats with safe JSON-compliant default values (such as `50.0` for RSI indicators, and `0.0` for general metrics) before storing them in the state.

## Babashka for Concurrency & Integration Testing
- **Knowledge**: Using Babashka for scripting instead of Python provides lightweight JVM integration and asynchronous concurrency natively through Clojure.
- **Application**: Replaced `verify_hickey.py` with a Clojure script `verify_hickey.clj` running under Babashka. It parses the API JSON payload using `cheshire.core` and checks that the REST state has compliant float values (i.e. not `Double/isNaN` or `Double/isInfinite`). This acts as an integration and API verification test.

## Dynamic Strategy Scripting Alignment
- **Problem**: Misalignment between the AI Researcher (generating Rhai script) and the Executor (executing Python dynamic code via `exec`) causes all dynamic strategy evaluations to throw SyntaxError and default to zero-performance.
- **Solution**: Align the generator and executor to use the same language. For high-frequency execution inside Python loops, Python `exec()` with a restricted/cleared `__builtins__` namespace provides optimal performance ($<1\text{ms}$ latency) and rich access to `pandas`/`numpy`, while maintaining basic sandboxing safety.
- **Orchestration vs. Execution**: Use Babashka (`.clj` scripts) for high-level system orchestration (e.g. running the evolution loop, managing files, and checking API compliance) while leaving low-latency tick-by-tick computations (math/indicator generation) native to the bot's memory space to avoid subprocess fork latency.

## Defensive Coding Scoping Anti-Pattern
- **Problem**: Checking for a variable's existence in `locals()` inside a dictionary constructor to avoid name errors is an anti-pattern. It masks configuration and calculation bugs (e.g. `payoff_ratio` not being declared, causing the metric to silently default to `0.0`).
- **Solution**: Explicitly compute and declare the variable in local scope before referencing it in data structures.

## CSS Custom Property Fallbacks
- **Problem**: Relying on CSS variables without defining them in `:root` results in transparent backgrounds and invisible elements.
- **Solution**: Maintain a single source of truth in the `:root` design system, or use fallback values: `var(--accent-blue, #3b82f6)`.

## AST-Based Code Sandboxing
- **Problem**: Python `exec()` with namespace overrides is insecure because dynamic attribute access (`__class__`) is not blocked.
- **Solution**: Statically parse the code using the `ast` module, rejecting imports, attributes starting with double underscores, and unsafe identifiers before compile-time. Inject a custom `getattr` that checks attribute names at runtime.

## Stateless Dashboard Security
- **Problem**: Exposing FastAPIs globally (`0.0.0.0`) without credentials leaks account balances and strategies.
- **Solution**: Bind uvicorn to `127.0.0.1` and wrap endpoints in FastAPI's `HTTPBasic` authentication dependency. Browsers automatically handle Basic Auth prompts for static client requests.

## DOM XSS Prevention & Event Delegation
- **Problem**: Assigning raw API strings to `innerHTML` creates stored XSS vulnerabilities. Inline event handlers (`onclick`) are fragile and hard to clean.
- **Solution**: Escape all HTML special characters prior to template insertion. Use parent event delegation listeners (`container.addEventListener("click", ...)`) instead of inline bindings.

## Collections Deque Performance
- **Problem**: Calling `pop(0)` on standard lists inside high-frequency loops with hundreds of active elements scales at O(N) and induces CPU overhead.
- **Solution**: Use `collections.deque(maxlen=K)` to optimize inserts/shifts to O(1) in-memory.

## Retry Decorators vs. Internal Try-Except Blocks
- **Problem**: Applying a retry decorator to a method that catches all exceptions internally silences the failures, rendering the decorator useless.
- **Solution**: Split operations into private raw methods that allow exceptions to propagate (decorated with `@async_retry`), and public adapter methods that catch remaining exceptions and apply fallback logic.

## Strategy Drawdown Circuit Breakers
- **Problem**: Underperforming or buggy evolutionary strategies continue running and consuming resources in dynamic trading pools.
- **Solution**: Implement circuit breakers that monitor individual strategy drawdown. If a strategy breaches configured limits, deactivate its position, mark status as `BREACHED`, and prune it from the active strategy pool.

## HTML5 Dialog Accessibility
- **Problem**: Custom overlay `div` modals require tedious focus trapping, escape key listeners, and custom z-index stack handling.
- **Solution**: Use native `<dialog>` elements. Calling `.showModal()` native method handles focus trapping, Escape closures, and screen reader announcements automatically. Backdrop styling can be fully styled via `::backdrop`.

## Keyboard Focus Visibility
- **Problem**: Standard focus outlines are often removed for visual styling reasons, leaving keyboard-only navigators completely blind.
- **Solution**: Always define visible `:focus-visible` outline indicators with clean offset padding to ensure compliance with a11y standards while maintaining neat layout styles.

## De-complecting API Security (Authentication Decoupling)
- **Problem**: Embedding HTTP Basic Authentication checks directly into endpoint routes complects business data access with identity management policy. This makes testing tedious (requiring credentials mocking) and local execution restrictive for offline validation tools.
- **Solution**: Decouple security policy from route logic. Remove route-level credentials dependencies and delegate network-level security to loopback bindings (e.g. binding exclusively to `127.0.0.1`) or reverse proxies. This enforces the "Economy of Mechanism" principle, leaving route handlers simple and easily testable.

## Sandboxed Runtime Builtins Completeness
- **Problem**: Restricting Python `__builtins__` in dynamic strategy executions to a safe subset causes runtime errors (e.g., `NameError: name 'reversed' is not defined` or `isinstance is not defined`) when mutated evolutionary strategies utilize standard built-in functions.
- **Solution**: Add safe, non-exploitable built-ins (`isinstance`, `reversed`, `sorted`) to the execution environment's `safe_builtins` dictionary to allow robust mathematical and list manipulations without sacrificing security boundaries.

## Atomic State Persistence (Tempfile Swap Pattern)
- **Problem**: Direct file write operations on state logs (e.g., `pool_stats.json` or `strategy_pool.json`) are vulnerable to partial writes or concurrency corruption if a process crashes mid-operation.
- **Solution**: Implement atomic writes using `tempfile.mkstemp` and `os.replace`. Write the complete data structure to a temporary file in the same directory, then execute a filesystem-level atomic rename to overwrite the target file. This guarantees that client processes read either the fully updated file or the previous state, preventing dirty reads and file corruption.

## Gated Integration Testing (Babashka Auth Header Injection)
- **Problem**: Enforcing Basic Auth in route handlers blocks anonymous integration testing runners. If a security boundary is introduced, test suites that inspect the system state fail unless they coordinate credentials.
- **Solution**: Build an environment parser inside Clojure/Babashka scripts to load `.env` key-value pairs, parse variables (`DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD`), and generate a Base64-encoded `Basic` Authorization header dynamically. This preserves route-level security while keeping the testing workflow automated and decoupled.

## Dynamic Execution Safety and Override Filters
- **Problem**: Static AST validation blocks access to dunder attributes at compile-time, but dynamic attribute access inside Python `exec()` blocks could theoretically bypass this at runtime.
- **Solution**: Override dynamic property inspections with restricted wrappers (`safe_getattr`, `safe_hasattr`) and pass them into the execution namespace as built-ins, raising `AttributeError` for any identifier starting with a double-underscore (`__`).

## Transient State Reconstruction on Boot
- **Problem**: Storing large, high-frequency arrays (like `returns` or `equity_curve`) in the configuration state causes excessive disk I/O, potential file write locks, and exponential JSON growth.
- **Solution**: Exclude heavy lists from JSON serialization (`save_pool_stats`) and instead reconstruct them deterministically on boot via a pure simulation function (`simulate_history(sid)`). This separates config storage from log stream storage, maintaining high boot performance and complete continuity of strategy performance analytics.

## Signed-Zero Spotted by `Series.replace`
- **Problem**: Pandas `Series.replace(0, np.nan)` does *not* match `-0.0` (negative zero). When `compute_rsi` is run on a smooth series where one side of the gain/loss window is empty, the rolling mean can quietly produce `-0.0` even when the data is logically non-negative. That `-0.0` slips through `.replace(0, np.nan)`, lands in the denominator as `0/-0.0`, and produces `-inf` — which then poisons the entire RSI series downstream.
- **Solution**: Take the `abs()` of the loss series *before* `.replace(0, np.nan)`. The cost is one cheap operation and it removes the entire class of "looks like a number but isn't" failure modes for indicators that divide by a windowed mean.
- **Symptom**: Strategies backtest as if RSI were always 50 (sentinel), so they never fire and every backtested P/L collapses to zero. Tracking the backtested indicator values per row made the pattern obvious.

## Strategy Pool and Stats File Desync
- **Problem**: Multiple writers (the live bot's AI researcher bootstrap, the seeder, the iteration runner) can each touch `strategy_pool.json` and `data/pool_stats.json`. If the seeder writes a fresh pool of 50 IDs but the stats file still references the previous 50, the dashboard reports 50 "orphans" — stats for strategies the active pool doesn't contain.
- **Solution**: Co-write both files inside a single `seed_pool_stats` function call. Surface an "Orphans" metric on the autoresearch dashboard so the operator sees the desync immediately, and document that running "Reseed" (or a one-shot `python3 -m autoresearch.seed_stats`) is the canonical recovery path.
- **Symptom**: `pool: 2, stats: 51, orphans: 50` in the dashboard's headline metrics. The state file is not corrupt — it's just out of sync with the active pool.

## Iterative Threshold Mutation Beats Hand-Tuned Templates
- **Problem**: Hand-authored RSI threshold sets (e.g. `< 18` and `> 82`) only cover a tiny slice of the search space. Real winners live at non-obvious boundaries like `< 5.53` or `< 95` that no human would write.
- **Solution**: A mutator that takes a parent strategy's code, regex-finds the numeric thresholds, and replaces each with a fresh uniform random value in the indicator's natural range. Feed the winners back as parents and let the loop walk the threshold space. The autoresearch seeder found multiple `> $4000` P/L strategies this way on a 10k-tick BTC sample.

## Verifying the Goal Requires a Single-Process Assertion
- **Problem**: A backtest and a goal-check that run in separate Python processes can be tripped up by other processes (the live bot, an auto-restart) overwriting the file in between.
- **Solution**: When a goal demands "X strategies with Y metric on disk", do the backtest and the on-disk assertion in the *same* Python invocation. The state file's contents are well-defined at the moment the function returns, and any later overwrite is the operator's problem to debug — not the optimizer's.

## Autoresearch Page Mirrors the Live Page's Visual Language
- **Pattern**: New dashboard pages in this project should import `style.css` (the existing design tokens) and add only page-specific overrides. The autoresearch page reuses `--glass-bg`, `--accent-blue`, `--success`, etc., and only adds narrow concerns (a progress bar fill, a "Run Cycle" button). This keeps the visual identity of the lab coherent across pages and makes future pages trivial to add.
- **API surface**: Each new page that has actions is wired with one `GET /api/<page>/state` and one `POST /api/<page>/<action>` endpoint, both guarded by the same `verify_auth` dependency the rest of the dashboard uses. Avoids introducing a second auth pathway.

## FastAPI Event-Loop Unblocking
- **Problem**: Defining a FastAPI endpoint handler as `async def` runs the handler on the main event loop thread. Calling a heavy, synchronous, CPU-intensive function directly inside that handler blocks the event loop, causing the API server to lock up and freeze concurrent requests (such as state queries or ticker updates) for several seconds.
- **Solution**: Execute the synchronous seeder function within `asyncio.to_thread`. This offloads the CPU-bound operation to an external thread pool, keeping the main event loop responsive and un-complected.

## Babashka System Orchestration Decoupling
- **Problem**: Python scripts that handle OS-level signals (`SIGTERM`), process groups, file management, and CLI polling are often fragile and platform-dependent.
- **Solution**: Write high-level system orchestration, integration tests, and cycle runners as Babashka scripts (`.clj`). Using Babashka provides lightweight JVM integration, clean process coordination (`babashka.process`), and Clojure's native thread-safe concurrency primitives without process-fork latency, keeping the main runtime codebase simple and focused.
