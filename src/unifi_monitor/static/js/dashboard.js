// dashboard.js -- Fetches API data and renders the dashboard
// WebSocket for live updates with REST polling fallback.

const REFRESH_MS = 15000;
const STALE_THRESHOLD_MS = 60000;
const WS_MAX_BACKOFF_MS = 30000;
let bandwidthChart = null;
let latencyChart = null;
let lastSuccessfulFetch = 0;
let refreshTimer = null;
let currentClients = [];
let sortColumn = 'rx_bytes';
let sortDirection = 'desc';
let expandedClientMac = null;
let clientDetailCharts = {};

// -- WebSocket connection --

var wsConn = null;
var wsBackoff = 1000;
var wsFailCount = 0;
var wsMode = 'connecting'; // 'live', 'polling', 'connecting', 'disconnected'
var _wsToken = '';

async function fetchWsToken() {
    try {
        var resp = await fetch('/api/auth/token');
        if (resp.ok) {
            var data = await resp.json();
            _wsToken = data.token || '';
        }
    } catch (e) {
        // Auth may not be enabled -- proceed without token
        _wsToken = '';
    }
}

function wsConnect() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + '/api/ws';
    if (_wsToken) url += '?token=' + encodeURIComponent(_wsToken);
    wsConn = new WebSocket(url);

    wsConn.onopen = function() {
        wsBackoff = 1000;
        wsFailCount = 0;
        wsMode = 'live';
        updateConnectionBadge();
        // Stop REST polling -- WS takes over
        stopRefresh();
    };

    wsConn.onmessage = function(event) {
        try {
            var msg = JSON.parse(event.data);
            if (msg.type === 'update') {
                lastSuccessfulFetch = Date.now();
                renderOverview(msg.overview);
                renderClients(msg.clients);
                renderDevices(msg.devices);
                renderAlarms(msg.alarms);
                updateStatusBanner();
            }
        } catch (e) {
            console.error('WS message parse error:', e);
        }
    };

    wsConn.onclose = function() {
        wsConn = null;
        wsFailCount++;
        wsMode = 'disconnected';
        updateConnectionBadge();

        if (wsFailCount >= 3) {
            // Fall back to REST polling
            wsMode = 'polling';
            updateConnectionBadge();
            startRefresh();
        }

        // Reconnect with exponential backoff
        var delay = Math.min(wsBackoff, WS_MAX_BACKOFF_MS);
        wsBackoff = Math.min(wsBackoff * 2, WS_MAX_BACKOFF_MS);
        setTimeout(function() {
            if (!document.hidden) {
                wsConnect();
            }
        }, delay);
    };

    wsConn.onerror = function() {
        // onclose will fire after this
    };
}

function updateConnectionBadge() {
    var badge = document.getElementById('conn-badge');
    if (!badge) return;
    badge.className = 'conn-badge conn-' + wsMode;
    var labels = {live: 'Live', polling: 'Polling', connecting: 'Connecting', disconnected: 'Disconnected'};
    badge.textContent = labels[wsMode] || wsMode;
}

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

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function deviceStateBadge(state) {
    if (state === 1) return '<span class="badge badge-online">Online</span>';
    if (state === 5) return '<span class="badge badge-adopting">Adopting</span>';
    return '<span class="badge badge-offline">Offline</span>';
}

// -- Toast notifications --

function showToast(msg, durationMs) {
    durationMs = durationMs || 4000;
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(function() { toast.classList.add('hidden'); }, durationMs);
}

// -- Status banner --

function updateStatusBanner() {
    const banner = document.getElementById('status-banner');
    const elapsed = Date.now() - lastSuccessfulFetch;

    if (lastSuccessfulFetch === 0) {
        banner.classList.add('hidden');
        return;
    }

    if (elapsed > STALE_THRESHOLD_MS * 3) {
        banner.className = 'status-banner error';
        banner.textContent = 'Connection lost -- data may be outdated';
    } else if (elapsed > STALE_THRESHOLD_MS) {
        banner.className = 'status-banner warn';
        banner.textContent = 'Data may be stale -- last updated ' + Math.round(elapsed / 1000) + 's ago';
    } else {
        banner.classList.add('hidden');
    }
}

// -- API calls --

async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            showToast('API error: ' + resp.status + ' on ' + url);
            return null;
        }
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
    const factors = data.health_factors || [];
    const factorText = factors.length > 0 ? factors.join(', ') : 'All systems normal';

    el.innerHTML =
        '<div class="card ' + hc + '">' +
            '<div class="label">Health Score</div>' +
            '<div class="value">' + data.health_score + '</div>' +
            '<div class="detail">' + escapeHtml(factorText) + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="label">WAN Status</div>' +
            '<div class="value">' +
                '<span class="status-dot ' + (wan.status === 'ok' ? 'ok' : 'down') + '"></span>' +
                escapeHtml(wan.status || 'N/A') +
            '</div>' +
            '<div class="detail">' + escapeHtml(wan.wan_ip || '') + (wan.latency_ms ? ' / ' + wan.latency_ms + ' ms' : '') + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="label">Gateway</div>' +
            '<div class="value">' + (wan.cpu_pct != null ? wan.cpu_pct + '%' : 'N/A') + '</div>' +
            '<div class="detail">CPU' + (wan.mem_pct != null ? ' / Memory ' + wan.mem_pct + '%' : '') + '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="label">Clients</div>' +
            '<div class="value">' + ((data.clients && data.clients.total) || 0) + '</div>' +
            '<div class="detail">' + ((data.clients && data.clients.wireless) || 0) + ' wireless, ' + ((data.clients && data.clients.wired) || 0) + ' wired</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="label">Devices</div>' +
            '<div class="value">' + ((data.devices && data.devices.online) || 0) + '/' + ((data.devices && data.devices.total) || 0) + '</div>' +
            '<div class="detail">online</div>' +
        '</div>';

    document.getElementById('last-updated').textContent = 'Updated ' + timeAgo(data.timestamp);
}

function renderDevices(devices) {
    if (!devices || !devices.length) return;
    var container = document.getElementById('device-cards');
    container.innerHTML = devices.map(function(d) {
        return '<div class="device-card">' +
            '<div class="device-name">' + escapeHtml(d.name || d.mac) + '</div>' +
            '<div class="device-model">' + escapeHtml(d.model || 'Unknown') + ' ' + deviceStateBadge(d.state) + '</div>' +
            '<div class="device-stats">' +
                (d.cpu_pct != null ? 'CPU ' + d.cpu_pct + '%' : '') +
                (d.mem_pct != null ? ' / Mem ' + d.mem_pct + '%' : '') +
                (d.num_clients != null ? ' / ' + d.num_clients + ' clients' : '') +
            '</div>' +
        '</div>';
    }).join('');
}

function renderAlarms(alarms) {
    var panel = document.getElementById('alarms-panel');
    if (!alarms || alarms.length === 0) {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = '';
    var tbody = document.getElementById('alarms-body');
    tbody.innerHTML = alarms.map(function(a) {
        return '<tr class="alarm-row">' +
            '<td>' + escapeHtml(a.type) + '</td>' +
            '<td>' + escapeHtml(a.message) + '</td>' +
            '<td>' + escapeHtml(a.device_name || '-') + '</td>' +
        '</tr>';
    }).join('');
}

function renderClients(clientsResponse) {
    if (!clientsResponse) return;
    // Handle paginated {data:[]}, raw array, or WS update formats
    var clients = Array.isArray(clientsResponse) ? clientsResponse : (clientsResponse.data || []);
    currentClients = clients;
    renderClientTable(clients);
}

function renderClientTable(clients) {
    var tbody = document.getElementById('clients-body');

    // Sort
    var sorted = clients.slice().sort(function(a, b) {
        var aVal = a[sortColumn];
        var bVal = b[sortColumn];
        if (aVal == null) aVal = sortDirection === 'desc' ? -Infinity : Infinity;
        if (bVal == null) bVal = sortDirection === 'desc' ? -Infinity : Infinity;
        if (typeof aVal === 'string') aVal = aVal.toLowerCase();
        if (typeof bVal === 'string') bVal = bVal.toLowerCase();
        if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    var html = '';
    sorted.forEach(function(c) {
        var mac = c.mac || '';
        var isExpanded = (mac === expandedClientMac);
        html += '<tr class="client-row' + (isExpanded ? ' client-row-selected' : '') + '" data-mac="' + escapeHtml(mac) + '">' +
            '<td>' + escapeHtml(c.hostname || c.mac) + '</td>' +
            '<td>' + escapeHtml(c.ip || '-') + '</td>' +
            '<td>' + escapeHtml(c.ssid || (c.is_wired ? 'Wired' : '-')) + '</td>' +
            '<td class="' + signalClass(c.signal_dbm) + '">' + (c.signal_dbm != null ? c.signal_dbm + ' dBm' : '-') + '</td>' +
            '<td>' + (c.satisfaction != null ? c.satisfaction + '%' : '-') + '</td>' +
            '<td>' + (c.channel || '-') + '</td>' +
            '<td>' + fmtBytes(c.rx_bytes) + '</td>' +
            '<td>' + fmtBytes(c.tx_bytes) + '</td>' +
        '</tr>';
        if (isExpanded) {
            html += '<tr class="client-detail-row"><td colspan="8">' +
                '<div class="client-detail" id="client-detail-' + escapeHtml(mac) + '">' +
                    '<div class="client-detail-meta">' +
                        '<span>MAC: ' + escapeHtml(mac) + '</span>' +
                        '<span>Radio: ' + escapeHtml(c.radio || '-') + '</span>' +
                        '<span>Channel: ' + (c.channel || '-') + '</span>' +
                        '<span>SSID: ' + escapeHtml(c.ssid || '-') + '</span>' +
                    '</div>' +
                    '<div class="client-detail-charts">' +
                        '<div class="chart-container chart-container-sm"><canvas id="signal-chart-' + escapeHtml(mac) + '"></canvas></div>' +
                        '<div class="chart-container chart-container-sm"><canvas id="satisfaction-chart-' + escapeHtml(mac) + '"></canvas></div>' +
                    '</div>' +
                '</div>' +
            '</td></tr>';
        }
    });
    tbody.innerHTML = html;

    // Render charts for expanded client
    if (expandedClientMac) {
        loadClientCharts(expandedClientMac);
    }

    // Update sort indicators
    document.querySelectorAll('th.sortable').forEach(function(th) {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.dataset.sort === sortColumn) {
            th.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
        }
    });
}

// -- Client detail charts --

async function loadClientCharts(mac) {
    var data = await fetchJSON('/api/clients/' + encodeURIComponent(mac) + '/history?hours=24');
    if (!data || !data.length) return;

    var labels = data.map(function(d) {
        return new Date(d.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    });
    var signals = data.map(function(d) { return d.signal_dbm; });
    var satisfactions = data.map(function(d) { return d.satisfaction; });

    var chartOpts = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: '#8b8fa3', maxTicksLimit: 8 }, grid: { color: '#2a2d3a' } },
            y: { ticks: { color: '#8b8fa3' }, grid: { color: '#2a2d3a' } },
        },
    };

    // Destroy old charts if any
    if (clientDetailCharts.signal) { clientDetailCharts.signal.destroy(); clientDetailCharts.signal = null; }
    if (clientDetailCharts.satisfaction) { clientDetailCharts.satisfaction.destroy(); clientDetailCharts.satisfaction = null; }

    var sigEl = document.getElementById('signal-chart-' + mac);
    if (sigEl) {
        clientDetailCharts.signal = new Chart(sigEl, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Signal (dBm)',
                    data: signals,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true, tension: 0.3, pointRadius: 0,
                }],
            },
            options: Object.assign({}, chartOpts, {
                plugins: { legend: { display: true, labels: { color: '#8b8fa3' } } },
            }),
        });
    }

    var satEl = document.getElementById('satisfaction-chart-' + mac);
    if (satEl) {
        clientDetailCharts.satisfaction = new Chart(satEl, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Satisfaction (%)',
                    data: satisfactions,
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: true, tension: 0.3, pointRadius: 0,
                }],
            },
            options: Object.assign({}, chartOpts, {
                plugins: { legend: { display: true, labels: { color: '#8b8fa3' } } },
                scales: Object.assign({}, chartOpts.scales, { y: { ticks: { color: '#8b8fa3' }, grid: { color: '#2a2d3a' }, min: 0, max: 100 } }),
            }),
        });
    }
}

function renderTopTalkers(talkers) {
    if (!talkers) return;
    var tbody = document.getElementById('talkers-body');

    tbody.innerHTML = talkers.slice(0, 10).map(function(t) {
        return '<tr>' +
            '<td>' + escapeHtml(t.src_ip) + '</td>' +
            '<td>' + (t.total_bytes_fmt || fmtBytes(t.total_bytes)) + '</td>' +
            '<td>' + (t.flow_count || 0) + '</td>' +
        '</tr>';
    }).join('');
}

function renderTopPorts(ports) {
    if (!ports) return;
    var tbody = document.getElementById('ports-body');

    tbody.innerHTML = ports.slice(0, 10).map(function(p) {
        return '<tr>' +
            '<td>' + p.dst_port + '</td>' +
            '<td>' + escapeHtml(p.protocol_name || String(p.protocol)) + '</td>' +
            '<td>' + (p.total_bytes_fmt || fmtBytes(p.total_bytes)) + '</td>' +
            '<td>' + (p.flow_count || 0) + '</td>' +
        '</tr>';
    }).join('');
}

function renderBandwidthChart(data) {
    if (!data || !data.length) return;

    var ctx = document.getElementById('bandwidth-chart');
    var labels = data.map(function(d) {
        return new Date(d.bucket * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    });
    var mbps = data.map(function(d) { return d.mbps || 0; });

    if (bandwidthChart) {
        bandwidthChart.data.labels = labels;
        bandwidthChart.data.datasets[0].data = mbps;
        bandwidthChart.update('none');
    } else {
        bandwidthChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
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

    var ctx = document.getElementById('latency-chart');
    var labels = data.map(function(d) {
        return new Date(d.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    });
    var latency = data.map(function(d) { return d.latency_ms || 0; });

    if (latencyChart) {
        latencyChart.data.labels = labels;
        latencyChart.data.datasets[0].data = latency;
        latencyChart.update('none');
    } else {
        latencyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
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

// -- Column sorting + client detail click --

document.addEventListener('click', function(e) {
    // Column sorting
    if (e.target.classList.contains('sortable')) {
        var col = e.target.dataset.sort;
        if (sortColumn === col) {
            sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            sortColumn = col;
            sortDirection = col === 'hostname' ? 'asc' : 'desc';
        }
        if (currentClients.length > 0) {
            renderClientTable(currentClients);
        }
        return;
    }

    // Client row click -> expand detail
    var row = e.target.closest('.client-row');
    if (row) {
        var mac = row.dataset.mac;
        if (!mac) return;
        if (expandedClientMac === mac) {
            expandedClientMac = null;
        } else {
            expandedClientMac = mac;
        }
        renderClientTable(currentClients);
    }
});

// -- Main loop (REST fallback) --

async function refresh() {
    var results = await Promise.all([
        fetchJSON('/api/overview'),
        fetchJSON('/api/clients?limit=200'),
        fetchJSON('/api/traffic/top-talkers?hours=1&limit=10'),
        fetchJSON('/api/traffic/top-ports?hours=1&limit=10'),
        fetchJSON('/api/traffic/bandwidth?hours=24&bucket_minutes=5'),
        fetchJSON('/api/wan/history?hours=24'),
        fetchJSON('/api/devices'),
        fetchJSON('/api/alarms'),
    ]);

    var anySuccess = results.some(function(r) { return r !== null; });
    if (anySuccess) {
        lastSuccessfulFetch = Date.now();
    }

    renderOverview(results[0]);
    renderClients(results[1]);
    renderTopTalkers(results[2]);
    renderTopPorts(results[3]);
    renderBandwidthChart(results[4]);
    renderLatencyChart(results[5]);
    renderDevices(results[6]);
    renderAlarms(results[7]);

    updateStatusBanner();
}

// -- Visibility-based auto-pause --

function startRefresh() {
    if (refreshTimer) return;
    refresh();
    refreshTimer = setInterval(refresh, REFRESH_MS);
}

function stopRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        stopRefresh();
        if (wsConn) {
            wsConn.close();
            wsConn = null;
        }
    } else {
        // Re-fetch token (may have rotated) then reconnect
        fetchWsToken().then(function() {
            if (wsMode === 'polling' || !wsConn) {
                wsConnect();
            }
        });
        // Also do an immediate REST fetch for charts (WS doesn't carry chart data)
        refresh();
    }
});

// Manual refresh button
document.getElementById('refresh-btn').addEventListener('click', function() {
    refresh();
});

// Periodic stale check (even when paused, update the banner)
setInterval(updateStatusBanner, 10000);

// Initial load: fetch WS token, then start WS + REST fetch for chart data
fetchWsToken().then(function() {
    wsConnect();
    refresh();
});
