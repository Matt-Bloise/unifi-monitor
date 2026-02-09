// dashboard.js -- Fetches API data and renders the dashboard
// Auto-refreshes every 15 seconds.

const REFRESH_MS = 15000;
let bandwidthChart = null;
let latencyChart = null;

// -- Helpers --

function fmtBytes(b) {
    if (!b) return '0 B';
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB';
    if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB';
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB';
    return b.toFixed(0) + ' B';
}

function fmtBps(bytesPerSec) {
    if (!bytesPerSec) return '0 bps';
    const bits = bytesPerSec * 8;
    if (bits >= 1e9) return (bits / 1e9).toFixed(1) + ' Gbps';
    if (bits >= 1e6) return (bits / 1e6).toFixed(1) + ' Mbps';
    if (bits >= 1e3) return (bits / 1e3).toFixed(1) + ' Kbps';
    return bits.toFixed(0) + ' bps';
}

function signalClass(dbm) {
    if (dbm === null || dbm === undefined) return '';
    if (dbm >= -65) return 'signal-good';
    if (dbm >= -75) return 'signal-warn';
    return 'signal-bad';
}

function healthClass(score) {
    if (score >= 80) return 'health-good';
    if (score >= 50) return 'health-warn';
    return 'health-bad';
}

function timeAgo(ts) {
    const diff = Date.now() / 1000 - ts;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

// -- API calls --

async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        return await resp.json();
    } catch (e) {
        console.error('Fetch error:', url, e);
        return null;
    }
}

// -- Render functions --

function renderOverview(data) {
    if (!data) return;

    const el = document.getElementById('overview-cards');
    const wan = data.wan || {};
    const hc = healthClass(data.health_score);

    el.innerHTML = `
        <div class="card ${hc}">
            <div class="label">Health Score</div>
            <div class="value">${data.health_score}</div>
            <div class="detail">${data.alarms || 0} active alarm${data.alarms !== 1 ? 's' : ''}</div>
        </div>
        <div class="card">
            <div class="label">WAN Status</div>
            <div class="value">
                <span class="status-dot ${wan.status === 'ok' ? 'ok' : 'down'}"></span>
                ${wan.status || 'N/A'}
            </div>
            <div class="detail">${wan.wan_ip || ''} ${wan.latency_ms ? '/ ' + wan.latency_ms + ' ms' : ''}</div>
        </div>
        <div class="card">
            <div class="label">Gateway</div>
            <div class="value">${wan.cpu_pct != null ? wan.cpu_pct + '%' : 'N/A'}</div>
            <div class="detail">CPU${wan.mem_pct != null ? ' / Memory ' + wan.mem_pct + '%' : ''}</div>
        </div>
        <div class="card">
            <div class="label">Clients</div>
            <div class="value">${data.clients?.total || 0}</div>
            <div class="detail">${data.clients?.wireless || 0} wireless, ${data.clients?.wired || 0} wired</div>
        </div>
        <div class="card">
            <div class="label">Devices</div>
            <div class="value">${data.devices?.online || 0}/${data.devices?.total || 0}</div>
            <div class="detail">online</div>
        </div>
    `;

    document.getElementById('last-updated').textContent = 'Updated ' + timeAgo(data.timestamp);
}

function renderClients(clients) {
    if (!clients) return;
    const tbody = document.getElementById('clients-body');

    tbody.innerHTML = clients.map(c => `
        <tr>
            <td>${c.hostname || c.mac}</td>
            <td>${c.ip || '-'}</td>
            <td>${c.ssid || (c.is_wired ? 'Wired' : '-')}</td>
            <td class="${signalClass(c.signal_dbm)}">${c.signal_dbm != null ? c.signal_dbm + ' dBm' : '-'}</td>
            <td>${c.satisfaction != null ? c.satisfaction + '%' : '-'}</td>
            <td>${c.channel || '-'}</td>
            <td>${fmtBytes(c.rx_bytes)}</td>
            <td>${fmtBytes(c.tx_bytes)}</td>
        </tr>
    `).join('');
}

function renderTopTalkers(talkers) {
    if (!talkers) return;
    const tbody = document.getElementById('talkers-body');

    tbody.innerHTML = talkers.slice(0, 10).map(t => `
        <tr>
            <td>${t.src_ip}</td>
            <td>${t.total_bytes_fmt || fmtBytes(t.total_bytes)}</td>
            <td>${t.flow_count || 0}</td>
        </tr>
    `).join('');
}

function renderTopPorts(ports) {
    if (!ports) return;
    const tbody = document.getElementById('ports-body');

    tbody.innerHTML = ports.slice(0, 10).map(p => `
        <tr>
            <td>${p.dst_port}</td>
            <td>${p.protocol_name || p.protocol}</td>
            <td>${p.total_bytes_fmt || fmtBytes(p.total_bytes)}</td>
            <td>${p.flow_count || 0}</td>
        </tr>
    `).join('');
}

function renderBandwidthChart(data) {
    if (!data || !data.length) return;

    const ctx = document.getElementById('bandwidth-chart');
    const labels = data.map(d => new Date(d.bucket * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
    const mbps = data.map(d => d.mbps || 0);

    if (bandwidthChart) {
        bandwidthChart.data.labels = labels;
        bandwidthChart.data.datasets[0].data = mbps;
        bandwidthChart.update('none');
    } else {
        bandwidthChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Bandwidth (Mbps)',
                    data: mbps,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#8b8fa3', maxTicksLimit: 12 }, grid: { color: '#2a2d3a' } },
                    y: { ticks: { color: '#8b8fa3' }, grid: { color: '#2a2d3a' }, beginAtZero: true },
                },
            },
        });
    }
}

function renderLatencyChart(data) {
    if (!data || !data.length) return;

    const ctx = document.getElementById('latency-chart');
    const labels = data.map(d => new Date(d.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
    const latency = data.map(d => d.latency_ms || 0);

    if (latencyChart) {
        latencyChart.data.labels = labels;
        latencyChart.data.datasets[0].data = latency;
        latencyChart.update('none');
    } else {
        latencyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Latency (ms)',
                    data: latency,
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#8b8fa3', maxTicksLimit: 12 }, grid: { color: '#2a2d3a' } },
                    y: { ticks: { color: '#8b8fa3' }, grid: { color: '#2a2d3a' }, beginAtZero: true },
                },
            },
        });
    }
}

// -- Main loop --

async function refresh() {
    const [overview, clients, talkers, ports, bandwidth, wanHistory] = await Promise.all([
        fetchJSON('/api/overview'),
        fetchJSON('/api/clients'),
        fetchJSON('/api/traffic/top-talkers?hours=1&limit=10'),
        fetchJSON('/api/traffic/top-ports?hours=1&limit=10'),
        fetchJSON('/api/traffic/bandwidth?hours=24&bucket_minutes=5'),
        fetchJSON('/api/wan/history?hours=24'),
    ]);

    renderOverview(overview);
    renderClients(clients);
    renderTopTalkers(talkers);
    renderTopPorts(ports);
    renderBandwidthChart(bandwidth);
    renderLatencyChart(wanHistory);
}

// Initial load + auto-refresh
refresh();
setInterval(refresh, REFRESH_MS);
