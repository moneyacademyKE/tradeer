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


