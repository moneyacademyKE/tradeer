/**
 * Autoresearch Lab Dashboard Logic
 * Fixes applied vs inline script:
 *   - "Reseed" wired to POST /api/autoresearch/reseed (distinct from Run Cycle)
 *   - $2000 / n_above_2000 replaced with target_pnl from API (single source of truth)
 *   - Visible error toast on fetch failure (matches app.js behaviour)
 *   - Drawdown column added to winners/losers rows
 *   - Auto-pause polling when browser tab is hidden
 */
(() => {
    'use strict';

    const AUTH_KEY = 'dashboard_auth';
    let authHeader = localStorage.getItem(AUTH_KEY);
    let authPromptShown = false;
    let errorBanner = null;
    let refreshTimer = null;
    let targetPnl = 2000; // overwritten by first API response

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
            <div class="strat-row">
                <span class="id">${escapeHtml(w.id.slice(0, 8))}</span>
                <span class="name" title="${escapeHtml(w.name)}">${escapeHtml(w.name)}</span>
                <span class="trades">t=${w.trades} w=${w.wins}</span>
                <span class="trades" style="color:var(--accent-red)">dd=$${fmt(Math.abs(w.drawdown ?? 0))}</span>
                <span class="pnl ${pnlClass}">${fmtPnl(w.current_pnl)}</span>
            </div>`;
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
    }

    // ── Data fetch ───────────────────────────────────────────────────────────
    async function refresh() {
        try {
            $('status-text').innerHTML = '<span class="spinner"></span>Loading state…';
            const res = await authFetch('/api/autoresearch/state');
            const data = await res.json();
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
        try {
            const res = await authFetch('/api/autoresearch/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    seed: Math.floor(Math.random() * 1e6),
                    pool_size: 50,
                    min_above_target: 5,
                    market_steps: 10000,
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
    $('reseed-btn').addEventListener('click', reseedPool);  // ← now calls distinct reseedPool()

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
