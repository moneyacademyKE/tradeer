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

