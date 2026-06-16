# Rich Hickey Gap Analysis: Strategy State Persistence & Session Restart

An architectural analysis of strategy state persistence across application restarts following Rich Hickey's design philosophies (specifically *Simple Made Easy* and the separation of Value, State, and Identity).

---

## 1. Feature Set Differences

| Feature Dimension | Option A: Reinitialize Empty (Current) | Option B: Reconstruct via Pure History Simulation (Recommended) | Option C: Persist Heavy Lists in JSON | Option D: Reconstruct from Order Logs |
| :--- | :--- | :--- | :--- | :--- |
| **Code Complection** | Low, but incorrect. Discards state completely, avoiding persistence complection but failing user requirements. | Low. Persists only the core values (scalar counts, configuration) and uses a pure simulation function to reconstruct the heavy arrays. | High. Braids disk-bound configuration files with highly dynamic, memory-intensive telemetry logs. | Extremely High. Braids order history (execution domain) with performance statistics calculation (analytics domain). |
| **I/O Overhead** | None. | Low. Core stats are tiny JSON payloads ($<10\text{KB}$) written atomically. | Extremely High. Fast-growing array values (`returns` and `equity_curve`) write to disk on every single ticker tick, causing disk thrashing. | Medium. Requires parsing the complete order log database on boot. |
| **State Continuity** | Fails. All strategy statistics are reset to empty lists and baseline stats on reboot. | High. Loaded strategy IDs retain their historical stats (wins, trades, entry, current pnl), and their arrays are deterministically rebuilt. | High. Full state is loaded exactly as it was. | Partial. Can reconstruct equity from order logs, but cannot reconstruct returns for steps where no trades occurred. |
| **Testability / Simplicity** | High (but useless). | Excellent. The simulation function `simulate_history` is a pure function of strategy ID and historical returns. | Poor. File writes depend heavily on array size, creating test flakiness under high ticker counts. | Very Complex. Requires seeding and mock-building hundreds of orders to test statistical recovery. |

---

## 2. Feature Differences & Architectural Explanations

### Value vs. State vs. Identity (The Hickey Model)
- **Identity**: The strategy pool item (e.g. `base` or a generated uuid strategy ID) is an identity that persists over time.
- **State**: The snapshot of its performance metrics (pnl, trades, wins, position size, etc.) at any given epoch.
- **Value**: The immutable numbers/strings representation of that state.
- **The Gap**: Currently, the application conflates the *Identity* of a strategy with its *Transient Telemetry* (`returns`, `equity_curve`). When persisting, we do not want to persist the entire execution history (the heavy transient telemetry arrays) to a single monolithic configuration file on every tick.
- **The Solution**: Persist only the core state *Value* (e.g. `pnl`, `pos`, `entry`, `wins`, `trades`). When restarting, load these core values, and use a pure, deterministic function (`simulate_history(sid)`) to reconstruct the transient arrays. This de-complects serialization of configurations from serialization of dynamic streams.

### Complection of Analytics & Persistence
- Directly saving the entire list of `returns` and `equity_curve` (which grow by 1 element every 2 seconds for each of the 200 strategies) into `pool_stats.json` represents a classic complection. It braids **durable storage** with **in-memory caching of high-frequency data**. Option B decouples them by using deterministic simulation to reconstruct history.

---

## 3. Benefits and Trade-Offs

### Option A: Reinitialize Empty (Current)
- **Benefits**: Zero persistence logic; no file corruptions from schema mismatch.
- **Trade-offs**: Terrible user experience; every restart resets performance histories and dashboard metrics, preventing the AI Researcher from building on top of older generations' success.

### Option B: Reconstruct via Pure History Simulation (Recommended)
- **Benefits**: Perfect state continuity; negligible I/O footprint; robust, deterministic recovery; completely de-complected design.
- **Trade-offs**: Reconstructed `returns` and `equity_curve` are statistically equivalent and deterministic simulations, rather than identical tick-by-tick records (but since paper trades are simulated based on historical price movement anyway, this is a completely acceptable and elegant trade-off).

### Option C: Persist Heavy Lists in JSON
- **Benefits**: Exact data replication across boots.
- **Trade-offs**: JSON file size grows exponentially; risk of file lock contention and disk write blockages in high-frequency loop; complects config storage with logs.

### Option D: Reconstruct from Order Logs
- **Benefits**: Reconstructs real trade history.
- **Trade-offs**: Complex code; fails if order logs are pruned or deleted; cannot represent periods of inactive holding accurately.

---

## 4. Complexity vs. Utility Matrix

| Approach | Code Complexity | Storage / I/O Cost | Recovery Quality | Architectural Soundness (Hickey) |
| :--- | :--- | :--- | :--- | :--- |
| **Option A (Reinitialize Empty)** | Low | Zero | Zero (Resets) | Low |
| **Option B (Simulation Recovery)** | **Medium** | **Low** | **High** | **High (De-complected)** |
| **Option C (Full Persistence)** | Low | Extremely High | High | Low (Complected) |
| **Option D (Order Reconstruction)**| High | Medium | Medium | Medium (Complected Domains) |

---

## 5. Actionable Recommendation

**Weighted Analysis**:
- **Simplicity/Speed**: Option B provides the best balance. Reconstructing the deques via `simulate_history` takes less than 1ms per strategy on boot and uses existing pure logic.
- **Power**: Reclaims complete state representation for the AI Researcher, allowing evolutionary runs to resume seamlessly.
- **Complexity**: Low implementation risk. Requires changing the initialization of `pool_stats` to call `load_pool_stats()` and verifying the recovery loop.

**Decision**:
Implement **Option B (Reconstruct via Pure History Simulation)**. Update the bot runner startup to:
1. Load `pool_stats` from disk on boot.
2. If `pool_stats` is loaded, inspect and reconstruct the missing transient lists (`returns`, `equity_curve`) via `simulate_history(sid)`.
3. Retain the loaded scalar values (`pnl`, `wins`, `trades`, `pos`, `entry`, etc.) rather than resetting them, ensuring complete session continuity.
4. Keep the atomic replace pattern for safe state persistence.
