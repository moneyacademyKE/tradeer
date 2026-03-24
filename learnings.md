# Learnings: Rich Hickey Trading Bot Implementation

- **De-complecting**: Existing bots (Freqtrade, Hummingbot) often complect data and behavior using heavy class hierarchies.
- **Values as Identity**: By treating the "World View" as a single immutable map, we gain deterministic backtesting and easy debugging.
- **Functional Core, Imperative Shell**: Maintain a pure logic core and keep side-effects (API calls) at the edge.
- **Data-First Signals**: Signals should be pure projections of historical values, not stateful entities.
- **The State Atom**: Using a thread-safe "Atom" to store the current world state allows disparate parts of the system (Bot loop vs. API) to access the same truth without complecting their lifecycles.
