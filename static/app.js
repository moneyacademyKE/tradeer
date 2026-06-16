/**
 * Institutional Quant Lab Dashboard Logic
 * Powered by Rich Hickey Principles
 */

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
    experimentBadge: document.getElementById('experiment-badge')
};

let stateSnapshot = null;
let lastPriceValue = null;
let currentSignalsData = { static: '', dynamic: '' };
let activeTab = 'static';
let errorBanner = null;

function renderSkeletons() {
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
        const response = await fetch('/api/signals');
        currentSignalsData = await response.json();
        elements.strategyCode.textContent = currentSignalsData[activeTab] || "// No code available";
    } catch (e) { console.error(e); }
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
        <svg width="100%" height="${height}" viewbox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <polyline fill="none" stroke="${color}" stroke-width="2" points="${points}" stroke-linejoin="round" />
        </svg>
    `;
}

function renderExperiments(state) {
    const list = elements.experimentList;
    if (!state.strategy_stats) return;

    const sortedStats = Object.entries(state.strategy_stats)
        .sort((a, b) => b[1].pnl - a[1].pnl);

    elements.experimentBadge.textContent = `${sortedStats.length} EXPERIMENTS`;
    
    list.innerHTML = sortedStats.map(([id, stats]) => {
        const pnlClass = stats.pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
        const chartId = `chart-${id.replace(/[^a-zA-Z0-9]/g, '')}`;
        const escapedId = escapeHtml(id);
        const escapedName = escapeHtml(stats.name || id);
        const actionClass = escapeHtml(stats.action.toLowerCase());
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
                        <span class="value ${pnlClass}">${stats.pnl.toFixed(2)}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Win Rate</span>
                        <span class="value">${((stats.wins / (stats.trades || 1)) * 100).toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // After HTML is set, render SVG curves
    sortedStats.forEach(([id, stats]) => {
        if (stats.metrics && stats.metrics.hist_equity) {
            renderEquityCurve(`chart-${id.replace(/[^a-zA-Z0-9]/g, '')}`, stats.metrics.hist_equity);
        }
    });
}

async function showStrategyDetail(id) {
    const modal = document.getElementById('strategy-modal');
    const statsContainer = document.getElementById('modal-stats');
    const codeContainer = document.getElementById('modal-code');
    const title = document.getElementById('modal-title');

    try {
        const response = await fetch(`/api/strategy/${id}`);
        if (!response.ok) {
            throw new Error(`Strategy API returned ${response.status}`);
        }
        const data = await response.json();
        const stats = stateSnapshot ? stateSnapshot.strategy_stats[id] : null;

        title.textContent = data.name || id;
        codeContainer.textContent = data.code || "// Pure logic hidden";
        
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
        
        const modal = document.getElementById('strategy-modal');
        modal.showModal();
    } catch (e) {
        console.error(e);
        showConnectionError("Failed to load strategy details.");
    }
}

async function updateDashboard() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) {
            throw new Error(`State API returned ${response.status}`);
        }
        const state = await response.json();
        clearConnectionError();
        stateSnapshot = state;

        const ticker = state.tickers["BTC/USDT"];
        if (ticker) {
            elements.lastPrice.textContent = `$${ticker.last.toLocaleString()}`;
            if (lastPriceValue) {
                const diff = ticker.last - lastPriceValue;
                const pct = (diff / lastPriceValue) * 100;
                elements.priceChange.textContent = `${diff >= 0 ? '+' : ''}${pct.toFixed(4)}%`;
                elements.priceChange.className = diff >= 0 ? 'pnl-pos' : 'pnl-neg';
            }
            lastPriceValue = ticker.last;
        }

        elements.balance.textContent = `$${(state.balance['USDT'] || 0).toLocaleString()}`;
        renderExperiments(state);
    } catch (e) {
        console.error(e);
        showConnectionError("API connection offline. Retrying...");
        if (!stateSnapshot) {
            renderSkeletons();
        }
    }
}

document.getElementById('close-modal').onclick = () => {
    document.getElementById('strategy-modal').close();
};

const strategyModal = document.getElementById('strategy-modal');
strategyModal.addEventListener('click', (e) => {
    if (e.target === strategyModal) {
        strategyModal.close();
    }
});

// Event delegation for strategy card clicks
elements.experimentList.addEventListener('click', (e) => {
    const card = e.target.closest('.strategy-card');
    if (card) {
        const id = card.dataset.id;
        showStrategyDetail(id);
    }
});

// Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => {
        document.querySelector('.tab-btn.active').classList.remove('active');
        btn.classList.add('active');
        activeTab = btn.dataset.tab;
        fetchSignalsCode();
    };
});

setInterval(updateDashboard, 2000);
renderSkeletons();
updateDashboard();
fetchSignalsCode();
