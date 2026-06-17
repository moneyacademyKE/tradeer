# Gap Analysis: Both Dashboards
> Rich Hickey Gap Analysis · Tradeer · June 2026

---

## 1. Dashboard Inventory (What Exists Today)

### Trading Lab — `index.html` + `app.js`
| Feature | Status | Notes |
|---|---|---|
| Strategy grid (cards) | ✅ | Sorted by PnL, hover lift, shimmer skeleton |
| Per-card equity curve | ✅ | SVG polyline, green/red by direction |
| Per-card PnL + win rate | ✅ | 2 metrics shown |
| Pulse indicator (BUY/SELL/HOLD) | ✅ | Animated glow dot |
| Strategy detail modal | ✅ | Native `<dialog>`, code + all 20+ metrics |
| Transaction log | ✅ | Last 100 orders, newest-first |
| Live signal pulse panel | ✅ | RSI gauge bars + EMA as currency |
| Signal code viewer (tabbed) | ✅ | `signals.py` + `dynamic_signals.py` tabs |
| Header: price, equity, % change | ✅ | Updates every 2s |
| Link to autoresearch | ✅ | Nav pill in header |
| Auth (Basic, localStorage) | ✅ | Prompt on 401, cached |
| Connection error banner | ✅ | Fixed toast, clears on recover |
| Keyboard accessibility | ✅ | Arrow key tab nav, focus-visible |
| Reduced motion | ✅ | `@media prefers-reduced-motion` |
| Responsive layout | ✅ | 3→2→1 col breakpoints |
| **Drawdown display on card** | ❌ | Cards show PnL only |
| **Trades count on card** | ❌ | Only visible in modal |
| **Pool health / orphan warning** | ❌ | No desync indicator |
| **Strategy filter / sort UI** | ❌ | Always PnL-sorted, no control |
| **BREACHED state styling** | ❌ | Risk module fires, UI silent |
| **Auto-pause when tab hidden** | ❌ | 2s polling burns CPU in background |
| **Chart hover tooltip** | ❌ | SVG polyline has no labels |

---

### Autoresearch Lab — `autoresearch.html`
| Feature | Status | Notes |
|---|---|---|
| Headline metrics row | ✅ | Above target, pool size, losers, orphans |
| Goal progress bar | ✅ | Animated fill, % of pool label |
| Winners list (top 10) | ✅ | ID, name, trades, wins, PnL |
| Losers list (top 5) | ✅ | Same columns |
| Orphan health warning | ✅ | Banner when orphan_count > 0 |
| Iteration log | ✅ | Last 20 entries, newest-first |
| "Run Evolution Cycle" button | ✅ | POST /api/autoresearch/run, spinner |
| "Refresh" button | ✅ | Manual |
| "Reseed From Top Winners" button | ⚠️ | **BUG: wired to same action as Run Cycle** |
| Auth (shared localStorage) | ✅ | Same key as trading lab |
| Auto-refresh every 15s | ✅ | Background interval |
| Nav pills | ✅ | Active state on current page |
| **Winner click → strategy detail** | ❌ | No way to inspect strategy code from AR page |
| **Configurable params UI** | ❌ | pool_size/seed hardcoded in JS |
| **Real-time run progress** | ❌ | Spinner only, no step log |
| **Winners-over-time chart** | ❌ | Log is text only, no trend |
| **Drawdown column in lists** | ❌ | Missing from winners/losers rows |
| **Distinct Reseed action** | ❌ | Same as Run Cycle |
| **Auto-pause when tab hidden** | ❌ | Same as trading lab |
| **Visible auth error** | ❌ | Error only in small grey status bar |

---

## 2. Feature Difference Table

| Capability | Trading Lab | Autoresearch Lab | Verdict |
|---|---|---|---|
| Live data cadence | 2s | 15s | ✅ By design |
| Strategy detail modal | ✅ | ❌ | AR gap |
| Drawdown displayed | ❌ | ❌ | Both missing |
| Orphan / health warning | ❌ | ✅ | Trading lab gap |
| Action buttons | ❌ read-only | ✅ 3 buttons | ✅ By design |
| RSI/EMA signal gauge | ✅ | ❌ | Different scopes |
| Equity curve chart | ✅ per-strategy | ❌ | AR needs winners trend |
| Filter / sort control | ❌ | ❌ | Both missing |
| BREACHED state | ❌ visual | ❌ visual | Both missing |
| Auto-pause on bg tab | ❌ | ❌ | Both missing |
| Configurable params | N/A | ❌ hardcoded | AR gap |

---

## 3. Bugs Found in Dashboard Code

### BUG-D001 · "Reseed From Top Winners" is identical to "Run Cycle"
**File**: [`autoresearch.html:521`](file:///Users/moe/Desktop/gh/tradeer/static/autoresearch.html#L521)

```js
$('reseed-btn').addEventListener('click', runCycle);  // same as run-btn
```

Both fire `runCycle()` → `POST /api/autoresearch/run`. The label implies selecting existing top performers as parents, but it seeds from scratch. **Actively misleading.**

**Fix**: Either wire to a distinct `/api/autoresearch/reseed` endpoint, or rename to "Re-run Seeder".

---

### BUG-D002 · Iteration log hardcodes `$2000` / `n_above_2000`
**Files**: [`autoresearch.html:493`](file:///Users/moe/Desktop/gh/tradeer/static/autoresearch.html#L493), [`autoresearch.html:510`](file:///Users/moe/Desktop/gh/tradeer/static/autoresearch.html#L510)

```js
above \$2000=<span ...>${it.n_above_2000}</span>   // line 493
`Cycle complete: ${data.n_above_2000} strategies above $2000 ...`  // line 510
```

`TARGET_PNL` is already exposed by `GET /api/autoresearch/state` as `target_pnl`. If the threshold changes in the backend, both display strings will be wrong forever. The field name `n_above_2000` in the log entry also needs to become `n_above_target`.

**Fix**: Backend returns `n_above_target` in log entries. Frontend uses `target_pnl` from state to render the label.

---

### BUG-D003 · Autoresearch page shows no prominent error on auth/fetch failure
**File**: [`autoresearch.html:393-395`](file:///Users/moe/Desktop/gh/tradeer/static/autoresearch.html#L393-L395)

```js
} catch (e) {
    $('status-text').textContent = `Error: ${e.message}`;
}
```

`app.js` shows a fixed red toast on failure; `autoresearch.html` silently sets a small grey status-bar string. On page load with bad credentials, all panels are empty and the only indicator is 0.85rem grey text.

---

### BUG-D004 · Signal pulse filters out all dynamic strategy signals
**File**: [`app.js:286`](file:///Users/moe/Desktop/gh/tradeer/static/app.js#L286)

```js
.filter(([k, _]) => k.startsWith('BTC/USDT_'));
```

`gemini_buy`, `gemini_sell`, and `{sid}_gemini_buy` signals are all stripped. Zero visibility into whether dynamic strategies are actually firing signals.

---

## 4. Complexity vs. Utility

| Component | Complexity | Utility | Verdict |
|---|---|---|---|
| Strategy card grid | Medium | High | ✅ |
| SVG equity curve | Low | High | ✅ |
| `<dialog>` modal | Medium | High | ✅ |
| Transaction log | Low | High | ✅ |
| Signal pulse panel | Low | Medium | ✅ |
| Skeleton loaders | Low | Medium | ✅ |
| Always-on 2s poll | Low | Zero when hidden | ⚠️ Add pause |
| "Reseed" button (duplicate) | Low | Zero | ❌ Fix |
| Inline `<script>` in autoresearch.html | Low | Negative (harder to test) | ⚠️ Extract |
| BREACHED state (missing) | Low | High | ❌ Add |
| Winners trend chart (missing) | Medium | High | ❌ Add |
| Configurable params form (missing) | Medium | Medium | ❌ Add |

---

## 5. Actionable Recommendations (Prioritized)

### Priority 1 — Fix bugs (correctness, zero cost)

| # | Action | File | Effort |
|---|---|---|---|
| 1 | Fix "Reseed" button label or wire distinct endpoint | autoresearch.html | Low |
| 2 | Replace `n_above_2000`/`$2000` with `target_pnl` from API | autoresearch.html + api.py | Low |
| 3 | Add visible error toast to autoresearch page | autoresearch.html | Low |

### Priority 2 — High-utility additions (small effort)

| # | Feature | Dashboard | Effort |
|---|---|---|---|
| 4 | BREACHED card state (grey, pill badge, no animation) | Trading Lab | Low |
| 5 | Auto-pause polling on `document.visibilitychange` | Both | Low |
| 6 | Drawdown column in winners/losers rows | Autoresearch | Low |
| 7 | Trades count on strategy card | Trading Lab | Low |
| 8 | Orphan warning badge in Trading Lab header | Trading Lab | Low |

### Priority 3 — Quality / capability improvements (medium effort)

| # | Feature | Dashboard | Effort |
|---|---|---|---|
| 9 | Click winner → strategy detail (shared `showStrategyDetail`) | Autoresearch | Medium |
| 10 | Extract inline script to `autoresearch.js` | Autoresearch | Low |
| 11 | Winners-over-iterations sparkline (SVG, same pattern as equity curve) | Autoresearch | Medium |
| 12 | Configurable params form (pool_size, market_steps, seed) | Autoresearch | Medium |
| 13 | Filter chips on strategy grid (All / Winners / Losers / Breached) | Trading Lab | Medium |

---

## 6. Rich Hickey Certification

| Principle | Trading Lab | Autoresearch Lab |
|---|---|---|
| **Simple** | ✅ Vanilla JS, no framework | ⚠️ Inline script harder to reason about |
| **Values not mutation** | ✅ API JSON → render | ✅ Same |
| **Complecting avoided** | ✅ Render separate from fetch | ⚠️ `runCycle` does fetch + render + log |
| **One source of truth** | ⚠️ `$2000` hardcoded once | ❌ `$2000` in 3 places |
| **Names say what they mean** | ✅ | ❌ "Reseed" does not reseed |

**Certification**: Trading Lab — **Near-passing** (fix BREACHED state + auto-pause).  
Autoresearch Lab — **Failing** on naming and single-source-of-truth. Fixable in one session.
