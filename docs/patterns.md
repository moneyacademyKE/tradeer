## The Identity Atom (Managed Continuity)
- **Pattern**: Wrap the current state value in an `Atom` (StateAtom). Only allow identity updates via a functional `swap`.
- **Hickey Principle**: Preserves the identity of the Lab across time while ensuring every state is an immutable, consistent value.

## Pure Functional Transitions (World Evolution)
- **Pattern**: Define a single `next_state` function that takes (State, Event) and returns (NextState, Commands).
- **Benefit**: Decouples the evolution logic from the orchestration mechanics, making the entire Quant Lab testable in a pure repl.

## Value-at-Rest (Immutable History)
- **Pattern**: Treat history as a persistent, immutable list of facts. Pass snapshots of this history to signals rather than mutable objects.
- **Benefit**: Simplifies the logic and ensures that signals are always derived from a consistent, un-complected data source.
