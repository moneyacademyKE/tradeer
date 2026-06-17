/**
 * Autoresearch Lab Dashboard Logic
 * Fixes applied vs inline script:
 *   - "Reseed" wired to POST /api/autoresearch/reseed (distinct from Run Cycle)
 *   - $2000 / n_above_2000 replaced with target_pnl from API (single source of truth)
 *   - Visible error toast on fetch failure (matches app.js behaviour)
 *   - Drawdown column added to winners/losers rows
 *   - Auto-pause polling when browser tab is hidden
 *   - Strategy detail modal display on row click
 *   - Configurable parameters read from expandable DOM form
 *   - SVG Sparkline of winners-over-time trend
 */
(() => {
    'use strict';

    const AUTH_KEY = 'dashboard_auth';
    let authHeader = localStorage.getItem(AUTH_KEY);
    let authPromptShown = false;
    let errorBanner = null;
    let refreshTimer = null;
    let targetPnl = 2000; // overwritten by first API response
    let stateSnapshot = null; // keeps track of the latest metrics state for modals

    // ── Auth ────────────────────────────────────────────────────────────────
    function encodeCredentials(u, p) { return 'Basic ' + btoa(u + ':' + p); }
    function getAuthHeaders() { return authHeader ? { Authorization: authHeader } : {}; }

    async function authFetch(url, options = {}) {
        const res = await fetch(url, {
            ...options,
            headers: { ...getAuthHeaders(), ...options.headers },
        });
        if (res.status === 401 && !authPromptShown) {
            authPromptShown = true;
            const u = prompt('Dashboard username:');
            const p = prompt('Dashboard password:');
            if (u && p) {
                authHeader = encodeCredentials(u, p);
                localStorage.setItem(AUTH_KEY, authHeader);
                return authFetch(url, options);
            }
            authPromptShown = false;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res;
    }

    // ── Error toast (same pattern as app.js) ────────────────────────────────
    function showError(message) {
        if (errorBanner) errorBanner.remove();
        errorBanner = document.createElement('div');
        errorBanner.style.cssText = [
            'position:fixed', 'bottom:20px', 'right:20px',
            'background:#ef4444', 'color:white',
            'padding:1rem 1.5rem', 'border-radius:12px',
            'box-shadow:0 4px 12px rgba(0,0,0,0.3)',
            'z-index:10000', "font-family:'Inter',sans-serif",
            'font-weight:600', 'transition:transform 0.3s ease',
        ].join(';');
        errorBanner.textContent = message;
        document.body.appendChild(errorBanner);
        setTimeout(() => { errorBanner?.remove(); errorBanner = null; }, 6000);
    }

    // ── Formatting helpers ───────────────────────────────────────────────────
    function fmt(n, d = 2) {
        if (n === null || n === undefined || Number.isNaN(n)) return '—';
        const abs = Math.abs(n);
        if (abs >= 1e6) return (n / 1e6).toFixed(d) + 'M';
        if (abs >= 1e3) return (n / 1e3).toFixed(d) + 'k';
        return Number(n).toFixed(d);
    }
    function fmtPnl(n) {
        if (n === null || n === undefined) return '—';
        return (n >= 0 ? '+$' : '-$') + fmt(Math.abs(n));
    }
    function fmtTs(epoch) {
        if (!epoch) return '—';
        return new Date(epoch * 1000).toLocaleTimeString();
    }
    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    const $ = (id) => document.getElementById(id);

    // ── Strategy row renderer (winners + losers) ─────────────────────────────
    function stratRow(w, pnlClass) {
        return `
            <div class="strat-row clickable-row" data-id="${escapeHtml(w.id)}">
                <span class="id">${escapeHtml(w.id.slice(0, 8))}</span>
                <span class="name" title="${escapeHtml(w.name)}">${escapeHtml(w.name)}</span>
                <span class="trades">t=${w.trades} w=${w.wins}</span>
                <span class="trades" style="color:var(--accent-red)">dd=$${fmt(Math.abs(w.drawdown ?? 0))}</span>
                <span class="pnl ${pnlClass}">${fmtPnl(w.current_pnl)}</span>
            </div>`;
    }

    // ── SVG Sparkline Renderer for Iteration Log ────────────────────────────
    function renderSparkline(iterations) {
        const container = $('sparkline-container');
        if (!container) return;

        if (!iterations || iterations.length < 2) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';

        const data = iterations.map(it => it.n_above_target ?? it.n_above_2000 ?? 0);
        const maxVal = Math.max(...data, 3);
        const minVal = Math.min(...data, 0);

        const width = container.clientWidth || 600;
        const height = 50;
        const padding = 6;

        const points = data.map((val, idx) => {
            const x = padding + (idx / (data.length - 1)) * (width - padding * 2);
            const y = height - padding - ((val - minVal) / (maxVal - minVal)) * (height - padding * 2);
            return { x, y, val };
        });

        const polylinePoints = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

        let svgHtml = `
            <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow: visible;">
                <defs>
                    <linearGradient id="sparkline-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="var(--accent-blue)" stop-opacity="0.25"></stop>
                        <stop offset="100%" stop-color="var(--accent-blue)" stop-opacity="0"></stop>
                    </linearGradient>
                </defs>
                <!-- Shaded Area Under Curve -->
                <path d="M ${points[0].x.toFixed(1)},${height} ${points.map(p => `L ${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')} L ${points[points.length - 1].x.toFixed(1)},${height} Z" fill="url(#sparkline-gradient)"></path>
                <!-- Line path -->
                <polyline points="${polylinePoints}" fill="none" stroke="var(--accent-blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></polyline>
                <!-- Pulse points -->
                ${points.map((p, idx) => `
                    <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="var(--text-primary)" stroke="var(--accent-blue)" stroke-width="1.5" style="cursor: pointer;">
                        <title>Run ${idx + 1}: ${p.val} above target</title>
                    </circle>
                `).join('')}
            </svg>
        `;
        container.innerHTML = svgHtml;
    }

    // ── Strategy Detail Modal Renderer ──────────────────────────────────────
    async function showStrategyDetail(id) {
        const modal = $('strategy-modal');
        const statsContainer = $('modal-stats');
        const codeContainer = $('modal-code');
        const title = $('modal-title');

        try {
            const response = await authFetch(`/api/strategy/${encodeURIComponent(id)}`);
            if (!response.ok) {
                throw new Error(`Strategy API returned ${response.status}`);
            }
            const data = await response.json();

            // Resolve statistics from snapshot
            let stats = null;
            if (stateSnapshot) {
                stats = stateSnapshot.top_winners.find(w => w.id === id) ||
                        stateSnapshot.top_losers.find(w => w.id === id) ||
                        (stateSnapshot.orphans && stateSnapshot.orphans.find(w => w.id === id));
            }

            if (title) title.textContent = data.name || id;
            if (codeContainer) codeContainer.textContent = data.code || "// Pure logic hidden";

            if (statsContainer) {
                let html = `
                    <div class="explanation-box glass">
                        <p>${escapeHtml(data.explanation || "De-complected mutation.")}</p>
                    </div>
                    <div class="stats-grid">
                `;

                if (stats) {
                    const metrics = {
                        "PnL": fmtPnl(stats.current_pnl),
                        "Trades": stats.trades,
                        "Wins": stats.wins,
                        "Win Rate": stats.trades > 0 ? ((stats.wins / stats.trades) * 100).toFixed(1) + '%' : '0%',
                        "Drawdown": '$' + fmt(stats.drawdown),
                        "Peak": '$' + fmt(stats.peak),
                        "Action": stats.action
                    };
                    for (const [key, val] of Object.entries(metrics)) {
                        html += `
                            <div class="stat-card mini glass">
                                <span class="label">${escapeHtml(key)}</span>
                                <span class="value">${escapeHtml(String(val))}</span>
                            </div>
                        `;
                    }
                }
                html += `</div>`;
                statsContainer.innerHTML = html;
            }

            if (modal) modal.showModal();
        } catch (e) {
            showError("Failed to load strategy details.");
        }
    }

    // ── Render ───────────────────────────────────────────────────────────────
    function render(d) {
        $('target-pnl').textContent = '$' + fmt(d.target_pnl, 0);
        $('pool-size').textContent = `${d.pool_size} / ${d.pool_cap}`;

        // Health warning
        const warn = $('health-warning');
        if (d.orphan_count > 0) {
            warn.style.display = 'block';
            warn.textContent = `⚠ ${d.orphan_count} strategy stats reference IDs not in the active pool. Run "Reseed From Top Winners" to align them.`;
        } else {
            warn.style.display = 'none';
        }

        // Headline metrics
        $('headline').innerHTML = `
            <div class="ar-metric">
                <div class="label">Above Target</div>
                <div class="value pnl-pos">${d.above_target}</div>
                <div class="sub">Strategies past $${fmt(d.target_pnl, 0)} P/L</div>
            </div>
            <div class="ar-metric">
                <div class="label">Goal Progress</div>
                <div class="value">${Math.min(d.above_target, 3)} / 3</div>
                <div class="sub">${d.above_target >= 3 ? '✓ Goal met' : 'Keep evolving'}</div>
            </div>
            <div class="ar-metric">
                <div class="label">Pool Size</div>
                <div class="value">${d.pool_size}</div>
                <div class="sub">Cap: ${d.pool_cap}</div>
            </div>
            <div class="ar-metric">
                <div class="label">Losers</div>
                <div class="value pnl-neg">${d.loser_count}</div>
                <div class="sub">Strategies below 0 P/L</div>
            </div>
            <div class="ar-metric">
                <div class="label">Orphans</div>
                <div class="value ${d.orphan_count > 0 ? 'pnl-neg' : ''}">${d.orphan_count}</div>
                <div class="sub">${d.orphan_count > 0 ? 'In stats, not in pool' : 'Pool is consistent'}</div>
            </div>`;

        // Goal progress bar
        const pct = Math.min(100, (d.above_target / 3) * 100);
        $('goal-bar-fill').style.width = pct + '%';
        $('goal-progress-text').textContent = `${Math.min(d.above_target, 3)} / 3`;
        $('goal-bar-left').textContent = `${d.above_target} strategies above target`;
        const poolPct = d.pool_size > 0 ? ((d.above_target / d.pool_size) * 100).toFixed(1) : '0';
        $('goal-bar-right').textContent = `${poolPct}% of pool`;

        // Winners
        $('winner-count').textContent = d.above_target;
        $('winners-list').innerHTML = d.top_winners.length === 0
            ? '<div class="empty">No winners yet. Run an evolution cycle to seed profitable strategies.</div>'
            : d.top_winners.map(w => stratRow(w, 'pnl-pos')).join('');

        // Losers
        $('loser-count').textContent = d.loser_count;
        $('losers-list').innerHTML = d.top_losers.length === 0
            ? '<div class="empty">No losers — every strategy is profitable.</div>'
            : d.top_losers.map(w => stratRow(w, 'pnl-neg')).join('');

        // Iteration log — use n_above_target (fallback to n_above_2000 for old log entries)
        $('iter-count').textContent = d.iterations.length;
        const iterEl = $('iter-log');
        if (d.iterations.length === 0) {
            iterEl.innerHTML = '<div class="empty">No iterations yet. Press "Run Evolution Cycle" to seed a new pool.</div>';
        } else {
            const tLabel = '$' + fmt(d.target_pnl, 0);
            iterEl.innerHTML = d.iterations.slice().reverse().map(it => {
                const nAbove = it.n_above_target ?? it.n_above_2000 ?? 0;
                return `<div class="line">
                    <span class="ts">${fmtTs(it.ts)}</span> ·
                    seed=<span class="n">${it.seed}</span> ·
                    pool=<span class="n">${it.pool_size}</span> ·
                    above ${escapeHtml(tLabel)}=<span class="${nAbove >= 3 ? 'ok' : 'err'}">${nAbove}</span>
                </div>`;
            }).join('');
        }

        // Render sparkline trend visualization
        renderSparkline(d.iterations);
    }

    // ── Data fetch ───────────────────────────────────────────────────────────
    async function refresh() {
        try {
            $('status-text').innerHTML = '<span class="spinner"></span>Loading state…';
            const res = await authFetch('/api/autoresearch/state');
            const data = await res.json();
            stateSnapshot = data;
            targetPnl = data.target_pnl || 2000;
            render(data);
            $('status-text').textContent = `Last refresh: ${new Date().toLocaleTimeString()}`;
        } catch (e) {
            showError(`API error: ${e.message}`);
            $('status-text').textContent = `Error: ${e.message}`;
        }
    }

    // ── Actions ──────────────────────────────────────────────────────────────
    function setAllBtns(disabled) {
        ['run-btn', 'reseed-btn', 'refresh-btn'].forEach(id => {
            const el = $(id);
            if (el) el.disabled = disabled;
        });
    }

    async function runCycle() {
        setAllBtns(true);
        $('status-text').innerHTML = '<span class="spinner"></span>Running evolution cycle… (this can take a minute)';
        
        // Read parameters form inputs
        const poolSizeInput = $('param-pool-size');
        const minAboveInput = $('param-min-above');
        const marketStepsInput = $('param-market-steps');
        const seedInput = $('param-seed');

        const poolSizeVal = poolSizeInput ? parseInt(poolSizeInput.value, 10) || 50 : 50;
        const minAboveVal = minAboveInput ? parseInt(minAboveInput.value, 10) || 5 : 5;
        const marketStepsVal = marketStepsInput ? parseInt(marketStepsInput.value, 10) || 10000 : 10000;
        
        let seedVal = seedInput ? seedInput.value.trim() : "";
        if (!seedVal) {
            seedVal = Math.floor(Math.random() * 1e6);
        } else {
            seedVal = parseInt(seedVal, 10) || Math.floor(Math.random() * 1e6);
        }

        try {
            const res = await authFetch('/api/autoresearch/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    seed: seedVal,
                    pool_size: poolSizeVal,
                    min_above_target: minAboveVal,
                    market_steps: marketStepsVal,
                }),
            });
            const data = await res.json();
            const nAbove = data.n_above_target ?? data.n_above_2000 ?? 0;
            $('status-text').textContent = `Cycle complete: ${nAbove} strategies above $${fmt(targetPnl, 0)}, pool of ${data.pool_size}`;
            await refresh();
        } catch (e) {
            showError(`Cycle failed: ${e.message}`);
            $('status-text').textContent = `Cycle failed: ${e.message}`;
        } finally {
            setAllBtns(false);
        }
    }

    async function reseedPool() {
        setAllBtns(true);
        $('status-text').innerHTML = '<span class="spinner"></span>Reseeding from top winners…';
        try {
            const res = await authFetch('/api/autoresearch/reseed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ n_keep: 25 }),
            });
            const data = await res.json();
            $('status-text').textContent = `Reseeded: pool now has ${data.pool_size} strategies`;
            await refresh();
        } catch (e) {
            showError(`Reseed failed: ${e.message}`);
            $('status-text').textContent = `Reseed failed: ${e.message}`;
        } finally {
            setAllBtns(false);
        }
    }

    // ── Event bindings ───────────────────────────────────────────────────────
    $('run-btn').addEventListener('click', runCycle);
    $('refresh-btn').addEventListener('click', refresh);
    $('reseed-btn').addEventListener('click', reseedPool);

    // Event delegation for row clicks
    function bindRowClicks(listId) {
        const list = $(listId);
        if (list) {
            list.addEventListener('click', (e) => {
                const row = e.target.closest('.strat-row');
                if (row) {
                    const id = row.getAttribute('data-id');
                    if (id) showStrategyDetail(id);
                }
            });
        }
    }
    bindRowClicks('winners-list');
    bindRowClicks('losers-list');

    // Dialog close hooks
    const strategyModal = $('strategy-modal');
    if (strategyModal) {
        const closeBtn = $('close-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => strategyModal.close());
        }
        strategyModal.addEventListener('click', (e) => {
            if (e.target === strategyModal) strategyModal.close();
        });
        strategyModal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') strategyModal.close();
        });
    }

    // ── Auto-pause polling when tab is hidden ────────────────────────────────
    function startPolling() {
        if (refreshTimer) return;
        refreshTimer = setInterval(refresh, 15000);
    }
    function stopPolling() {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopPolling();
        else { refresh(); startPolling(); }
    });

    // ── Init ─────────────────────────────────────────────────────────────────
    refresh();
    startPolling();
})();
