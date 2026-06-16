/**
 * Institutional Quant Lab Dashboard Logic
 * Powered by Rich Hickey Principles
 */
(() => {
    'use strict';

    const AUTH_KEY = 'dashboard_auth';
    let authHeader = localStorage.getItem(AUTH_KEY);
    let authPromptShown = false;

    function encodeCredentials(username, password) {
        return 'Basic ' + btoa(username + ':' + password);
    }

    function getAuthHeaders() {
        return authHeader ? { 'Authorization': authHeader } : {};
    }

    async function authFetch(url, options = {}) {
        const res = await fetch(url, { ...options, headers: { ...getAuthHeaders(), ...options.headers } });
        if (res.status === 401 && !authPromptShown) {
            authPromptShown = true;
            const username = prompt('Dashboard username:');
            const password = prompt('Dashboard password:');
            if (username && password) {
                authHeader = encodeCredentials(username, password);
                localStorage.setItem(AUTH_KEY, authHeader);
                return authFetch(url, options);
            }
            authPromptShown = false;
        }
        if (res.status === 401) {
            throw new Error('Authentication failed. Check DASHBOARD_USERNAME / DASHBOARD_PASSWORD in .env');
        }
        return res;
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return str.toString()
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    const elements = {
        lastPrice: document.getElementById('last-price'),
        balance: document.getElementById('balance-display'),
        priceChange: document.getElementById('price-change'),
        strategyCode: document.getElementById('strategy-code'),
        experimentList: document.getElementById('experiment-list'),
        experimentBadge: document.getElementById('experiment-badge'),
        transactionLog: document.getElementById('transaction-log')
    };

    let stateSnapshot = null;
    let lastPriceValue = null;
    let currentSignalsData = { static: '', dynamic: '' };
    let activeTab = 'static';
    let errorBanner = null;

    function renderSkeletons() {
        if (!elements.experimentList) return;
        elements.experimentList.innerHTML = Array(6).fill(0).map(() => `
            <div class="skeleton-card">
                <div class="skeleton-line title"></div>
                <div class="skeleton-line chart"></div>
                <div class="skeleton-line metric"></div>
            </div>
        `).join('');
    }

    function showConnectionError(message) {
        if (errorBanner) return;
        errorBanner = document.createElement('div');
        errorBanner.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #ef4444;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            transition: transform 0.3s ease;
        `;
        errorBanner.textContent = message;
        document.body.appendChild(errorBanner);
    }

    function clearConnectionError() {
        if (errorBanner) {
            errorBanner.remove();
            errorBanner = null;
        }
    }

    async function fetchSignalsCode() {
        try {
            const response = await authFetch('/api/signals');
            if (!response.ok) return;
            currentSignalsData = await response.json();
            if (elements.strategyCode) {
                elements.strategyCode.textContent = currentSignalsData[activeTab] || "// No code available";
            }
        } catch (e) { /* silent */ }
    }

    function renderEquityCurve(containerId, equity) {
        if (!equity || equity.length < 2) return;
        const container = document.getElementById(containerId);
        if (!container) return;

        const width = container.clientWidth || 280;
        const height = 40;
        const min = Math.min(...equity);
        const max = Math.max(...equity);
        const range = max - min || 1;

        const points = equity.map((val, i) => {
            const x = (i / (equity.length - 1)) * width;
            const y = height - ((val - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');

        const color = equity[equity.length - 1] >= equity[0] ? '#22c55e' : '#ef4444';
        
        container.innerHTML = `
            <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
                <polyline fill="none" stroke="${color}" stroke-width="2" points="${points}" stroke-linejoin="round" />
            </svg>
        `;
    }

    function renderExperiments(state) {
        const list = elements.experimentList;
        if (!list || !state || !state.strategy_stats) return;

        const sortedStats = Object.entries(state.strategy_stats)
            .sort((a, b) => b[1].pnl - a[1].pnl);

        if (elements.experimentBadge) {
            elements.experimentBadge.textContent = `${sortedStats.length} EXPERIMENTS`;
        }
        
        list.innerHTML = sortedStats.map(([id, stats]) => {
            const pnlClass = (stats.pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg';
            const chartId = `chart-${id.replace(/[^a-zA-Z0-9]/g, '')}`;
            const escapedId = escapeHtml(id);
            const escapedName = escapeHtml(stats.name || id);
            const actionClass = escapeHtml((stats.action || 'hold').toLowerCase());
            return `
                <div class="strategy-card" data-id="${escapedId}">
                    <div class="card-header">
                        <h3>${escapedName}</h3>
                        <div class="pulse ${actionClass}"></div>
                    </div>
                    <div class="chart-mini" id="${chartId}"></div>
                    <div class="metrics">
                        <div class="metric">
                            <span class="label">PnL</span>
                            <span class="value ${pnlClass}">${(stats.pnl || 0).toFixed(2)}</span>
                        </div>
                        <div class="metric">
                            <span class="label">Win Rate</span>
                            <span class="value">${(((stats.wins || 0) / (stats.trades || 1)) * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        sortedStats.forEach(([id, stats]) => {
            if (stats && stats.metrics && stats.metrics.hist_equity) {
                renderEquityCurve(
                    `chart-${id.replace(/[^a-zA-Z0-9]/g, '')}`,
                    stats.metrics.hist_equity
                );
            }
        });
    }

    async function showStrategyDetail(id) {
        const modal = document.getElementById('strategy-modal');
        const statsContainer = document.getElementById('modal-stats');
        const codeContainer = document.getElementById('modal-code');
        const title = document.getElementById('modal-title');

        try {
            const response = await authFetch(`/api/strategy/${encodeURIComponent(id)}`);
            if (!response.ok) {
                throw new Error(`Strategy API returned ${response.status}`);
            }
            const data = await response.json();
            const stats = stateSnapshot ? stateSnapshot.strategy_stats[id] : null;

            if (title) title.textContent = data.name || id;
            if (codeContainer) codeContainer.textContent = data.code || "// Pure logic hidden";
            
            if (statsContainer) {
                let html = `
                    <div class="explanation-box glass">
                        <p>${escapeHtml(data.explanation || "De-complected mutation.")}</p>
                    </div>
                    <div class="stats-grid">
                `;

                if (stats && stats.metrics) {
                    for (const [key, val] of Object.entries(stats.metrics)) {
                        if (key === 'hist_equity' || key === 'hist_returns') continue;
                        const escapedKey = escapeHtml(key);
                        const formattedVal = typeof val === 'number' ? val.toFixed(4) : escapeHtml(val);
                        html += `
                            <div class="stat-card mini glass">
                                <span class="label">${escapedKey}</span>
                                <span class="value">${formattedVal}</span>
                            </div>
                        `;
                    }
                }
                html += `</div>`;
                statsContainer.innerHTML = html;
            }
            
            if (modal) modal.showModal();
        } catch (e) {
            showConnectionError("Failed to load strategy details.");
        }
    }

    function renderTransactions(state) {
        const container = elements.transactionLog;
        if (!container || !state || !state.orders) return;

        const orders = Object.values(state.orders);
        if (orders.length === 0) {
            container.innerHTML = '<div class="no-transactions">No transactions logged yet.</div>';
            return;
        }

        // Sort by timestamp descending (newest first)
        orders.sort((a, b) => b.timestamp - a.timestamp);

        // Helper to resolve strategy name
        function getStrategyName(sid) {
            if (sid === 'base') return 'Base HF Scalper';
            const stats = state.strategy_stats && state.strategy_stats[sid];
            return stats && stats.name ? stats.name : sid;
        }

        container.innerHTML = orders.map(order => {
            const sideClass = (order.side || '').toLowerCase() === 'buy' ? 'buy' : 'sell';
            const escapedSide = escapeHtml(order.side);
            const escapedSymbol = escapeHtml(order.symbol);
            const escapedName = escapeHtml(getStrategyName(order.strategy_id));
            const formattedPrice = (order.price || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const formattedAmount = (order.amount || 0).toFixed(4);
            const dateStr = new Date(order.timestamp).toLocaleTimeString();

            return `
                <div class="transaction-row">
                    <div class="transaction-details">
                        <span class="transaction-strategy">${escapedName}</span>
                        <span class="transaction-meta">${escapedSymbol} &bull; ${dateStr}</span>
                    </div>
                    <div class="transaction-price-info">
                        <span class="transaction-side ${sideClass}">${escapedSide} ${formattedAmount}</span>
                        <span class="transaction-price">$${formattedPrice}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    async function updateDashboard() {
        try {
            const response = await authFetch('/api/state');
            if (!response.ok) {
                throw new Error(`State API returned ${response.status}`);
            }
            const state = await response.json();
            clearConnectionError();
            stateSnapshot = state;

            const ticker = state.tickers && state.tickers["BTC/USDT"];
            if (ticker && elements.lastPrice) {
                elements.lastPrice.textContent = `$${ticker.last.toLocaleString()}`;
                if (lastPriceValue != null) {
                    const diff = ticker.last - lastPriceValue;
                    const pct = (diff / lastPriceValue) * 100;
                    if (elements.priceChange) {
                        elements.priceChange.textContent = `${diff >= 0 ? '+' : ''}${pct.toFixed(4)}%`;
                        elements.priceChange.className = diff >= 0 ? 'pnl-pos' : 'pnl-neg';
                    }
                }
                lastPriceValue = ticker.last;
            }

            if (elements.balance) {
                elements.balance.textContent = `$${((state.balance && state.balance['USDT']) || 0).toLocaleString()}`;
            }
            renderExperiments(state);
            renderTransactions(state);
        } catch (e) {
            showConnectionError("API connection offline. Retrying...");
            if (!stateSnapshot) {
                renderSkeletons();
            }
        }
    }

    // --- Init ---
    document.addEventListener('DOMContentLoaded', () => {
        const closeBtn = document.getElementById('close-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                const modal = document.getElementById('strategy-modal');
                if (modal) modal.close();
            });
        }
    });

    const strategyModal = document.getElementById('strategy-modal');
    if (strategyModal) {
        strategyModal.addEventListener('click', (e) => {
            if (e.target === strategyModal) strategyModal.close();
        });

        // Keyboard: Escape closes modal (native <dialog> behavior, but add Arrow key nav)
        strategyModal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') strategyModal.close();
        });
    }

    // Event delegation for strategy card clicks
    if (elements.experimentList) {
        elements.experimentList.addEventListener('click', (e) => {
            const card = e.target.closest('.strategy-card');
            if (card && card.dataset.id) {
                showStrategyDetail(card.dataset.id);
            }
        });
    }

    // Tabs with keyboard navigation
    const tabList = document.querySelector('[role="tablist"]');
    const tabs = tabList ? Array.from(tabList.querySelectorAll('[role="tab"]')) : [];
    
    function activateTab(tab) {
        tabs.forEach(t => {
            t.classList.remove('active');
            t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        activeTab = tab.dataset.tab;
        fetchSignalsCode();
    }
    
    tabs.forEach((btn, i) => {
        btn.addEventListener('click', () => activateTab(btn));
        btn.addEventListener('keydown', (e) => {
            let targetIdx = -1;
            if (e.key === 'ArrowRight') targetIdx = (i + 1) % tabs.length;
            else if (e.key === 'ArrowLeft') targetIdx = (i - 1 + tabs.length) % tabs.length;
            if (targetIdx >= 0) {
                e.preventDefault();
                tabs[targetIdx].focus();
                activateTab(tabs[targetIdx]);
            }
        });
    });

    setInterval(updateDashboard, 2000);
    renderSkeletons();
    updateDashboard();
    fetchSignalsCode();
})();
