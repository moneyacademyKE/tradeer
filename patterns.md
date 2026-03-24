# Patterns: Rich Hickey Trading Bot Implementation

- **State Transition Pattern**: `next_state(state, event) -> (new_state, commands)`.
- **Data Normalization Pattern**: Immediate conversion of external (CCXT) JSON into internal frozen Pydantic types.
- **Signal-as-Data Pattern**: Signals are pure projections of the world state, not stateful indicators in a class.
- **Risk-as-Filter Pattern**: Risk management acts as a final pure filter on proposed commands before they hit the imperative shell.
- **State Atom Pattern**: A simple container that supports an atomic `swap` of the entire state value, ensuring that readers always see a consistent, point-in-time snapshot.
