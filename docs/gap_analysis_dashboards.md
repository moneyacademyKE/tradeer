# Gap Analysis: Both Dashboards
> Rich Hickey Gap Analysis · Tradeer · Updated June 2026 (post-fix)

---

## Changelog

| Date | Event |
|---|---|
| 2026-06-17 (initial) | Gap analysis written: 4 bugs, 13 recommendations |
| 2026-06-17 (this update) | All Priority 1 bugs fixed; 7 of 8 Priority 2 items fixed; 1 of 5 Priority 3 items fixed |

---

## 1. Dashboard Inventory (Current State)

### Trading Lab — `index.html` + `app.js`
| Feature | Status | Notes |
|---|---|---|
| Strategy grid (cards) | ✅ | Sorted by PnL, hover lift, shimmer skeleton |
| Per-card equity curve | ✅ | SVG polyline, green/red by direction |
| Per-card PnL + win rate + trades | ✅ | **3 metrics now** (PnL · Trades · Win Rate) |
| Pulse indicator (BUY/SELL/HOLD) | ✅ | Animated glow dot |
| **BREACHED state card** | ✅ **Fixed** | `.breached` CSS: dimmed, desaturated, red border, BREACHED pill |
| Strategy detail modal | ✅ | Native `<dialog>`, code + all 20+ metrics |
| Transaction log | ✅ | Last 100 orders, newest-first |
| Live signal pulse panel | ✅ | RSI gauge bars + EMA as currency |
| Signal code viewer (tabbed) | ✅ | `signals.py` + `dynamic_signals.py` tabs |
| Header: price, equity, % change | ✅ | Updates every 2s |
| **Orphan badge in header** | ✅ **Fixed** | Amber pulsing badge, visible when pool desyncs |
| Link to autoresearch | ✅ | Nav pill in header |
| Auth (Basic, localStorage) | ✅ | Prompt on 401, cached |
| Connection error banner | ✅ | Fixed toast, clears on recover |
| Keyboard accessibility | ✅ | Arrow key tab nav, focus-visible |
| Reduced motion | ✅ | `@media prefers-reduced-motion` |
| Responsive layout | ✅ | 3→2→1 col breakpoints |
| **Auto-pause when tab hidden** | ✅ **Fixed** | `visibilitychange` pauses 2s poll; resumes on focus |
| **Strategy filter / sort UI** | ❌ Remaining | Always PnL-sorted, no filter chips |
| **Chart hover tooltip** | ❌ Remaining | SVG polyline has no labels or hover value |

---

### Autoresearch Lab — `autoresearch.html` + `autoresearch.js`
| Feature | Status | Notes |
|---|---|---|
| Headline metrics row | ✅ | Above target, pool size, losers, orphans |
| Goal progress bar | ✅ | Animated fill, % of pool label |
| Winners list with drawdown | ✅ **Fixed** | ID, name, trades, wins, **drawdown**, PnL |
| Losers list with drawdown | ✅ **Fixed** | Same columns |
| Orphan health warning | ✅ | Banner when orphan_count > 0 |
| Iteration log | ✅ | Last 20 entries, newest-first |
| **target_pnl from API (not hardcoded)** | ✅ **Fixed** | Reads `target_pnl` from state; `n_above_target` field |
| **Old log entry fallback** | ✅ **Fixed** | `n_above_target ?? n_above_2000 ?? 0` — backward-compatible |
| "Run Evolution Cycle" button | ✅ | POST /api/autoresearch/run, spinner |
| **"Reseed From Top Winners" — distinct action** | ✅ **Fixed** | POST /api/autoresearch/reseed; keeps top 25 by P/L, mutates rest |
| **Visible error toast on failure** | ✅ **Fixed** | Red fixed toast, auto-dismisses after 6s |
| **Script extracted to `autoresearch.js`** | ✅ **Fixed** | 190-line inline script removed; external module |
| Auth (shared localStorage) | ✅ | Same key as trading lab |
| **Auto-pause when tab hidden** | ✅ **Fixed** | `visibilitychange` pauses 15s poll; resumes on focus |
| Nav pills | ✅ | Active state on current page |
| **Winner click → strategy detail** | ❌ Remaining | No way to inspect code from AR page |
| **Configurable params UI** | ❌ Remaining | pool_size/seed hardcoded in JS |
| **Real-time run progress** | ❌ Remaining | Spinner only, no step log |
| **Winners-over-time chart** | ❌ Remaining | Log is text only, no trend visualization |

---

## 2. Feature Difference Table (Updated)

| Capability | Trading Lab | Autoresearch Lab | Verdict |
|---|---|---|---|
| Live data cadence | 2s (pauses when hidden) | 15s (pauses when hidden) | ✅ Both fixed |
| Strategy detail modal | ✅ | ❌ | AR gap — remaining |
| Drawdown displayed | ❌ on card | ✅ in lists | AR fixed; TL card still missing |
| Orphan / health warning | ✅ amber badge | ✅ banner | ✅ Both covered |
| Action buttons | ❌ read-only | ✅ 3 distinct buttons | ✅ Correct by design |
| RSI/EMA signal gauge | ✅ | ❌ | Different scopes — by design |
| Equity curve chart | ✅ per-strategy | ❌ | AR needs winners trend — remaining |
| Filter / sort control | ❌ | ❌ | Both remaining |
| BREACHED state | ✅ card + pill | ❌ in AR lists | TL fixed; AR losers list not tagged |
| Auto-pause on bg tab | ✅ | ✅ | Both fixed |
| Configurable params | N/A | ❌ hardcoded | AR remaining |
| Single source of truth for TARGET_PNL | ✅ | ✅ | Both fixed |

---

## 3. Bug Tracker

| ID | Bug | Status | Fix Applied |
|---|---|---|---|
| BUG-D001 | "Reseed From Top Winners" called same fn as "Run Cycle" | ✅ **Fixed** | New `POST /api/autoresearch/reseed` endpoint + distinct `reseedPool()` fn |
| BUG-D002 | Iteration log hardcodes `$2000` / `n_above_2000` | ✅ **Fixed** | API returns `n_above_target`; JS reads `target_pnl` from state; backward-compatible fallback |
| BUG-D003 | No prominent error on auth/fetch failure (autoresearch) | ✅ **Fixed** | Red fixed toast, same pattern as `app.js` |
| BUG-D004 | Signal pulse strips all dynamic strategy signals | ⚠️ Accepted | Filter kept intentional — pulse panel shows core indicators only; cluttering with per-strategy signals would obscure the RSI/EMA signal |

---

## 4. Recommendations Tracker

### Priority 1 — Bugs (all resolved ✅)

| # | Action | Status |
|---|---|---|
| 1 | Fix "Reseed" button — wire distinct endpoint | ✅ Done |
| 2 | Replace `n_above_2000`/`$2000` with `target_pnl` | ✅ Done |
| 3 | Add visible error toast to autoresearch page | ✅ Done |

### Priority 2 — High-utility additions

| # | Feature | Status |
|---|---|---|
| 4 | BREACHED card state (grey, pill badge) | ✅ Done |
| 5 | Auto-pause polling on `visibilitychange` | ✅ Done — both dashboards |
| 6 | Drawdown column in winners/losers rows | ✅ Done |
| 7 | Trades count on strategy card | ✅ Done |
| 8 | Orphan warning badge in Trading Lab header | ✅ Done |

### Priority 3 — Quality / capability improvements (remaining backlog)

| # | Feature | Dashboard | Effort | Status |
|---|---|---|---|---|
| 9 | Click winner → strategy detail modal | Autoresearch | Medium | ❌ Open |
| 10 | Extract inline script to `autoresearch.js` | Autoresearch | Low | ✅ Done |
| 11 | Winners-over-iterations sparkline | Autoresearch | Medium | ❌ Open |
| 12 | Configurable params form (pool_size, market_steps, seed) | Autoresearch | Medium | ❌ Open |
| 13 | Filter chips on strategy grid (All / Winners / Losers / Breached) | Trading Lab | Medium | ❌ Open |

---

## 5. Complexity vs. Utility (Updated)

| Component | Complexity | Utility | Verdict |
|---|---|---|---|
| Strategy card grid | Medium | High | ✅ |
| SVG equity curve | Low | High | ✅ |
| `<dialog>` modal | Medium | High | ✅ |
| Transaction log | Low | High | ✅ |
| Signal pulse panel (core indicators only) | Low | Medium | ✅ Intentional scope |
| Skeleton loaders | Low | Medium | ✅ |
| Auto-pause on hidden tab | Low | High | ✅ Fixed |
| BREACHED card state | Low | High | ✅ Fixed |
| "Reseed" → distinct endpoint | Low | High | ✅ Fixed |
| `autoresearch.js` module | Low | Medium | ✅ Fixed |
| Winners trend chart (missing) | Medium | High | ❌ Open |
| Configurable params form (missing) | Medium | Medium | ❌ Open |
| AR winner → detail modal (missing) | Medium | High | ❌ Open |

---

## 6. Rich Hickey Certification (Updated)

| Principle | Trading Lab | Autoresearch Lab |
|---|---|---|
| **Simple** | ✅ Vanilla JS, external module | ✅ External `autoresearch.js` module |
| **Values not mutation** | ✅ API JSON → render | ✅ Same |
| **Complecting avoided** | ✅ Render separate from fetch | ✅ `runCycle` / `reseedPool` are distinct functions |
| **One source of truth** | ✅ `target_pnl` from API | ✅ `target_pnl` from API; fallback for old logs |
| **Names say what they mean** | ✅ | ✅ "Reseed From Top Winners" now reseeds from top winners |
| **Auto-pause (liveness)** | ✅ | ✅ |

**Certification**:
- **Trading Lab**: ✅ **Passing** — all core Hickey principles met. Remaining gaps (filter chips, chart tooltip) are UX enhancements, not correctness issues.
- **Autoresearch Lab**: ✅ **Passing** — naming, single-source-of-truth, and script modularity are all resolved. Remaining gaps (winner detail, sparkline, params form) are capability expansions.

---

## 7. Remaining Backlog (Open Items)

These are the 4 items left in Priority 3 that were not addressed in this session:

### OPEN-01 · Click winner row → strategy detail modal
**Dashboard**: Autoresearch Lab  
**Impact**: Currently the only way to read a winner's code is to switch to the Trading Lab and find it there. Would require either sharing `showStrategyDetail` via a lib module or duplicating the fetch+modal logic.  
**Prerequisite**: Extract shared auth + modal logic to `static/lib.js`.

### OPEN-02 · Winners-over-iterations sparkline
**Dashboard**: Autoresearch Lab  
**Impact**: The iteration log shows text; a small SVG sparkline of `n_above_target` per iteration would immediately show whether the optimizer is converging or plateauing.  
**Prerequisite**: `n_above_target` is now correctly stored per log entry — the data is ready.

### OPEN-03 · Configurable params form
**Dashboard**: Autoresearch Lab  
**Impact**: `pool_size=50`, `market_steps=10000`, `seed` are hardcoded in `runCycle()`. An expandable `<details>` form would let the operator tune without editing JS.  
**Prerequisite**: None.

### OPEN-04 · Filter chips on strategy grid
**Dashboard**: Trading Lab  
**Impact**: With 20+ strategies, there's no way to view only BREACHED cards or only winners above TARGET_PNL.  
**Prerequisite**: None — `strategy_stats` already has `action` and `pnl` fields.
