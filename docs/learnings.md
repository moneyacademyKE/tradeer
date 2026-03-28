## Identity vs. State (Hickey Principle)
- **Problem**: Conflating identity with state can lead to inconsistent transformations and race conditions.
- **Solution**: Decouple the **Identity** of the Lab (A container/Atom) from the **State** (The immutable value/snapshot).
- **Hardening**: Refactored `StateAtom` to use a functional `swap(f, *args)` that transforms the current immutable value into a new one atomically.

## The Pure State-Transition Function
- **Knowledge**: Every change in the system is a function of (State, Event) -> (NextState, Commands).
- **Benefit**: This allows for complete determinism, easy backtesting, and de-complected logic (e.g. signal calculation is a pure derivation of the state).

## Value-at-Rest Optimization
- **Optimization**: Switched from rebuilding entire DataFrames to passing immutable snapshots of history to signal logic.
- **Result**: Drastic reduction in CPU overhead and memory churn during high-frequency trading loops.
