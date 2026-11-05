/* ============================================
   OSI LAYERS AI AGENT - DASHBOARD JS
   ============================================ */

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ── State ──
let currentTab = 'dashboard';
let socket = null;
let analyticsChart = null;

// ── Initialize ──
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initSocket();
    fetchData();
    initAnalyticsChart();
    
    // Refresh data every 10 seconds
    setInterval(fetchData, 10000);
});

// ── Clock ──
function initClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('sys-clock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
    }, 1000);
}

// ── Tabs Switching ──
window.switchTab = function(tabName, element) {
    currentTab = tabName;
    
    // Toggle active class on tab buttons
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    if (element) {
        element.classList.add('active');
    } else {
        // Fallback find active tab button
        document.querySelectorAll('.tab').forEach(t => {
            if (t.textContent.toLowerCase().includes(tabName.toLowerCase().replace('_', ' '))) {
                t.classList.add('active');
            }
        });
    }
    
    // Toggle active class on views
    document.querySelectorAll('.view-section').forEach(view => {
        view.classList.remove('active');
    });
    const targetView = document.getElementById(`view-${tabName}`);
    if (targetView) {
        targetView.classList.add('active');
    }
};

// ── Socket.IO Connection ──
function initSocket() {
    try {
        socket = io();
        
        socket.on('connect', () => {
            logToConsole("[SYSTEM] Connected to real-time event bridge.", "info");
        });
        
        socket.on('system_log', (data) => {
            const message = data.message || "";
            const type = data.type || "info";
            const timeStr = data.timestamp || new Date().toLocaleTimeString();
            logToConsole(`[${timeStr}] ${message}`, type);
        });

        socket.on('incident_event', (data) => {
            logToConsole(`[ALERT] ${data.message}`, "critical");
            showToast("critical", data.message);
            // Refresh data on incident
            fetchData();
        });
    } catch (e) {
        console.error("SocketIO connection failed:", e);
    }
}

// ── Fetch & Bind Data ──
function fetchData() {
    fetchKPIs();
    fetchDevices();
    fetchPrinters();
    fetchIncidents();
    fetchKBStats();
}

function fetchKPIs() {
    fetch('/api/kpi_metrics')
        .then(res => res.json())
        .then(data => {
            const glob = data.global || {};
            document.getElementById('stat-fcr-rate').textContent = `${glob.fcr_rate}%`;
            document.getElementById('stat-confidence').textContent = `${glob.avg_confidence * 100}%`;
            document.getElementById('stat-csat').textContent = `${glob.csat_rating}/5.0`;
        })
        .catch(err => console.error("Error fetching KPIs:", err));
}

function fetchDevices() {
    fetch('/api/fleet/admin/devices')
        .then(res => res.json())
        .then(data => {
            // API now returns an array directly (not {devices: [...]})
            const devices = Array.isArray(data) ? data : (data.devices || []);
            document.getElementById('stat-fleet-size').textContent = devices.length;
            
            const tbody = document.querySelector('#table-dashboard-fleet tbody');
            tbody.innerHTML = '';
            
            const onlineCount = devices.filter(d => d.status === 'ONLINE').length;
            const statOnline = document.getElementById('stat-fleet-online');
            if (statOnline) statOnline.textContent = onlineCount;
            
            devices.forEach(dev => {
                const tr = document.createElement('tr');
                const isOnline = dev.online || dev.status === 'ONLINE';
                const badgeClass = isOnline ? 'badge-success' : 'badge-error';
                const osIcon = dev.os_type === 'linux' ? '🐧' : '🪟';
                
                const tdName = document.createElement('td');
                tdName.innerHTML = `<strong>${osIcon} </strong>`;
                tdName.querySelector('strong').appendChild(document.createTextNode(dev.name || ''));

                const tdIp = document.createElement('td');
                const spanIp = document.createElement('span');
                spanIp.style.fontFamily = 'var(--font-mono)';
                spanIp.textContent = dev.ip || '—';
                tdIp.appendChild(spanIp);

                const tdLayer = document.createElement('td');
                tdLayer.textContent = `Layer ${dev.layer || 1}`;

                const tdLoc = document.createElement('td');
                tdLoc.textContent = dev.location || 'Jakarta_Head_Office';

                const tdStatus = document.createElement('td');
                const spanStatus = document.createElement('span');
                spanStatus.className = `badge ${badgeClass}`;
                spanStatus.textContent = dev.status || '';
                tdStatus.appendChild(spanStatus);

                const tdLastSeen = document.createElement('td');
                tdLastSeen.style.fontFamily = 'var(--font-mono)';
                tdLastSeen.style.fontSize = '11px';
                tdLastSeen.style.color = 'var(--text-muted)';
                tdLastSeen.textContent = dev.last_seen || '—';

                const tdAction = document.createElement('td');
                const btn = document.createElement('button');
                btn.textContent = 'Detail';
                btn.style.cssText = 'background:var(--purple); border:none; border-radius:4px; padding:4px 10px; color:white; cursor:pointer; font-size:11px;';
                btn.addEventListener('click', () => showAgentDeepDetail(dev.name));
                tdAction.appendChild(btn);

                tr.append(tdName, tdIp, tdLayer, tdLoc, tdStatus, tdLastSeen, tdAction);
                tbody.appendChild(tr);
            });
            
            // Populate PC Health tab with real metrics from ALL agents
            const pcTbody = document.querySelector('#table-pc-health tbody');
            if (pcTbody) {
                pcTbody.innerHTML = '';
                devices.forEach(dev => {
                    const tr = document.createElement('tr');
                    const isOnline = dev.online || dev.status === 'ONLINE';
                    const badgeClass = isOnline ? 'badge-success' : 'badge-error';
                    const osIcon = dev.os_type === 'linux' ? '🐧' : '🪟';
                    
                    const cpu  = dev.cpu  > 0 ? `${dev.cpu.toFixed(0)}%`  : '—';
                    const ram  = dev.ram  > 0 ? `${dev.ram.toFixed(0)}%`  : '—';
                    const disk = dev.disk > 0 ? `${dev.disk.toFixed(0)}%` : '—';
                    
                    // Color-code high usage
                    const cpuColor  = dev.cpu  > 85 ? 'var(--red)' : dev.cpu  > 60 ? 'var(--orange)' : 'var(--green)';
                    const ramColor  = dev.ram  > 90 ? 'var(--red)' : dev.ram  > 70 ? 'var(--orange)' : 'var(--green)';
                    const diskColor = dev.disk > 90 ? 'var(--red)' : dev.disk > 75 ? 'var(--orange)' : 'var(--cyan)';
                    
                    const tdName = document.createElement('td');
                    const strongName = document.createElement('strong');
                    strongName.textContent = `${osIcon} ${dev.name || ''}`;
                    tdName.appendChild(strongName);

                    const tdIp = document.createElement('td');
                    const spanIp = document.createElement('span');
                    spanIp.style.cssText = 'font-family:var(--font-mono); font-size:11px;';
                    spanIp.textContent = dev.ip || '—';
                    tdIp.appendChild(spanIp);

                    const tdStatus = document.createElement('td');
                    const spanStatus = document.createElement('span');
                    spanStatus.className = `badge ${badgeClass}`;
                    spanStatus.textContent = dev.status || 'OFFLINE';
                    tdStatus.appendChild(spanStatus);

                    const tdCpu = document.createElement('td');
                    tdCpu.style.cssText = `font-family:var(--font-mono); color:${cpuColor};`;
                    tdCpu.textContent = cpu;

                    const tdRam = document.createElement('td');
                    tdRam.style.cssText = `font-family:var(--font-mono); color:${ramColor};`;
                    tdRam.textContent = ram;

                    const tdDisk = document.createElement('td');
                    tdDisk.style.cssText = `font-family:var(--font-mono); color:${diskColor};`;
                    tdDisk.textContent = disk;

                    const tdLastSeen = document.createElement('td');
                    tdLastSeen.style.cssText = 'font-size:11px; color:var(--text-muted);';
                    tdLastSeen.textContent = dev.last_seen || '—';

                    tr.append(tdName, tdIp, tdStatus, tdCpu, tdRam, tdDisk, tdLastSeen);
                    pcTbody.appendChild(tr);
                });
            }
        })
        .catch(err => console.error("Error fetching devices:", err));
}


function fetchPrinters() {
    fetch('/api/fleet/admin/printers')
        .then(res => res.json())
        .then(data => {
            const printers = Array.isArray(data) ? data : (data.printers || []);
            const tbody = document.querySelector('#table-printers tbody');
            tbody.innerHTML = '';
            
            printers.forEach(printer => {
                const tr = document.createElement('tr');
                
                let badgeClass = 'badge-success';
                const pStatus = String(printer.status || '');
                if (pStatus.toLowerCase().includes('jam')) {
                    badgeClass = 'badge-warning';
                } else if (pStatus.toLowerCase().includes('offline')) {
                    badgeClass = 'badge-error';
                }

                const tdName = document.createElement('td');
                const strongName = document.createElement('strong');
                strongName.textContent = String(printer.name || '').replace(/_/g, ' ');
                tdName.appendChild(strongName);

                const tdHost = document.createElement('td');
                tdHost.textContent = printer.host || '—';

                const tdType = document.createElement('td');
                const spanType = document.createElement('span');
                spanType.style.cssText = 'font-family:var(--font-mono); font-size:11px;';
                spanType.textContent = printer.type || '—';
                tdType.appendChild(spanType);

                const tdToners = document.createElement('td');
                const tonerGrid = document.createElement('div');
                tonerGrid.className = 'toner-grid';
                tonerGrid.innerHTML = `
                    <div style="font-size:10px;">K: ${Number(printer.toner_black || 0)}%</div>
                    <div style="font-size:10px;">C: ${Number(printer.toner_cyan || 0)}%</div>
                    <div style="font-size:10px;">M: ${Number(printer.toner_magenta || 0)}%</div>
                    <div style="font-size:10px;">Y: ${Number(printer.toner_yellow || 0)}%</div>
                `;
                const barGrid = document.createElement('div');
                barGrid.style.cssText = 'display:flex; gap:2px; height:4px; margin-top:2px; background:rgba(255,255,255,0.05); border-radius:2px; overflow:hidden;';
                barGrid.innerHTML = `
                    <div style="width:${Number(printer.toner_black || 0)}%; background:#000; height:100%;"></div>
                    <div style="width:${Number(printer.toner_cyan || 0)}%; background:#00ffff; height:100%;"></div>
                    <div style="width:${Number(printer.toner_magenta || 0)}%; background:#ff00ff; height:100%;"></div>
                    <div style="width:${Number(printer.toner_yellow || 0)}%; background:#ffff00; height:100%;"></div>
                `;
                tdToners.append(tonerGrid, barGrid);

                const tdStatus = document.createElement('td');
                const spanStatus = document.createElement('span');
                spanStatus.className = `badge ${badgeClass}`;
                spanStatus.textContent = pStatus;
                tdStatus.appendChild(spanStatus);

                const tdAction = document.createElement('td');
                const btnDetail = document.createElement('button');
                btnDetail.textContent = 'Detail';
                btnDetail.style.cssText = 'background:var(--bg-panel-hover); border:1px solid var(--border); border-radius:4px; padding:4px 8px; color:var(--text-bright); cursor:pointer; font-size:12px;';
                btnDetail.addEventListener('click', () => showPrinterDetail(printer.host, printer.name));
                tdAction.appendChild(btnDetail);

                tr.append(tdName, tdHost, tdType, tdToners, tdStatus, tdAction);
                tbody.appendChild(tr);
            });
        })
        .catch(err => console.error("Error fetching printers:", err));
}

function fetchIncidents() {
    fetch('/api/incidents')
        .then(res => res.json())
        .then(data => {
            const tbody = document.querySelector('#table-incidents tbody');
            tbody.innerHTML = '';
            
            data.forEach(inc => {
                const tr = document.createElement('tr');
                const confPercent = Math.round((inc.confidence || 0) * 100);

                const tdTime = document.createElement('td');
                tdTime.style.cssText = 'font-family:var(--font-mono); font-size:12px;';
                tdTime.textContent = inc.timestamp || '—';

                const tdAgent = document.createElement('td');
                const strongAgent = document.createElement('strong');
                strongAgent.textContent = inc.agent || '—';
                tdAgent.appendChild(strongAgent);

                const tdLayer = document.createElement('td');
                tdLayer.textContent = `Layer ${inc.layer || '—'}`;

                const tdFlag = document.createElement('td');
                const spanFlag = document.createElement('span');
                spanFlag.className = 'badge badge-error';
                spanFlag.textContent = inc.flag || '—';
                tdFlag.appendChild(spanFlag);

                const tdAnalysis = document.createElement('td');
                tdAnalysis.textContent = inc.analysis || '—';

                const tdConf = document.createElement('td');
                tdConf.style.cssText = 'font-family:var(--font-mono); font-weight:600; color:var(--purple);';
                tdConf.textContent = `${confPercent}%`;

                const tdActions = document.createElement('td');
                const btnSOP = document.createElement('button');
                btnSOP.textContent = 'View SOP';
                btnSOP.style.cssText = 'background:var(--purple); border:none; border-radius:4px; padding:4px 8px; color:white; cursor:pointer; font-size:12px;';
                btnSOP.addEventListener('click', () => showIncidentDetail(inc.layer, inc.analysis, inc.steps));

                const btnDAG = document.createElement('button');
                btnDAG.textContent = 'Causal DAG';
                btnDAG.style.cssText = 'background:var(--cyan); border:none; border-radius:4px; padding:4px 8px; color:black; cursor:pointer; font-size:12px; margin-left:4px; font-weight:bold;';
                btnDAG.addEventListener('click', () => viewCausalDAG(inc.incident_id || 'latest', inc.agent));

                tdActions.append(btnSOP, btnDAG);
                tr.append(tdTime, tdAgent, tdLayer, tdFlag, tdAnalysis, tdConf, tdActions);
                tbody.appendChild(tr);
            });
        })
        .catch(err => console.error("Error fetching incidents:", err));
}

function fetchKBStats() {
    fetch('/api/kb_stats')
        .then(res => res.json())
        .then(data => {
            const tbody = document.querySelector('#table-kb-stats tbody');
            tbody.innerHTML = '';
            
            data.forEach(stat => {
                const tr = document.createElement('tr');
                const confPercent = Math.round((stat.confidence || 0) * 100);
                const cov = Number(stat.coverage) || 0;
                
                const tdLayer = document.createElement('td');
                const strongLayer = document.createElement('strong');
                strongLayer.textContent = stat.layer || '—';
                tdLayer.appendChild(strongLayer);

                const tdCov = document.createElement('td');
                const wrapCov = document.createElement('div');
                wrapCov.style.cssText = 'display:flex; align-items:center; gap:8px;';
                const barOuter = document.createElement('div');
                barOuter.style.cssText = 'flex:1; height:6px; background:rgba(255,255,255,0.05); border-radius:3px; overflow:hidden;';
                const barInner = document.createElement('div');
                barInner.style.cssText = `width:${cov}%; background:var(--purple); height:100%;`;
                barOuter.appendChild(barInner);
                const spanCov = document.createElement('span');
                spanCov.textContent = `${cov}%`;
                wrapCov.append(barOuter, spanCov);
                tdCov.appendChild(wrapCov);

                const tdConf = document.createElement('td');
                tdConf.style.cssText = 'font-family:var(--font-mono); color:var(--purple); font-weight:600;';
                tdConf.textContent = `${confPercent}%`;

                const tdLastUpdate = document.createElement('td');
                tdLastUpdate.style.cssText = 'color:var(--text-muted); font-size:12px;';
                tdLastUpdate.textContent = stat.last_update || '—';

                tr.append(tdLayer, tdCov, tdConf, tdLastUpdate);
                tbody.appendChild(tr);
            });
        })
        .catch(err => console.error("Error fetching KB stats:", err));
}

// ── Modals & Actions ──
window.showPrinterDetail = function(host, printerName) {
    fetch('/api/fleet/admin/printers')
        .then(res => res.json())
        .then(data => {
            const printers = Array.isArray(data) ? data : (data.printers || []);
            const printer = printers.find(p => p.host === host && p.name === printerName);
            if (!printer) return;
            
            document.getElementById('modal-printer-title').textContent = printer.name.replace(/_/g, ' ');
            document.getElementById('modal-printer-host').textContent = printer.host;
            document.getElementById('modal-printer-interface').textContent = printer.type;
            
            const statusEl = document.getElementById('modal-printer-status');
            statusEl.textContent = printer.status;
            statusEl.className = 'badge ' + (printer.status === 'Online' ? 'badge-success' : printer.status === 'Offline' ? 'badge-error' : 'badge-warning');
            
            document.getElementById('modal-printer-jobs').textContent = printer.jobs_pending;
            
            // Set levels
            document.getElementById('modal-toner-black-val').textContent = `${printer.toner_black}%`;
            document.getElementById('modal-toner-black-bar').style.width = `${printer.toner_black}%`;
            document.getElementById('modal-toner-cyan-val').textContent = `${printer.toner_cyan}%`;
            document.getElementById('modal-toner-cyan-bar').style.width = `${printer.toner_cyan}%`;
            document.getElementById('modal-toner-magenta-val').textContent = `${printer.toner_magenta}%`;
            document.getElementById('modal-toner-magenta-bar').style.width = `${printer.toner_magenta}%`;
            document.getElementById('modal-toner-yellow-val').textContent = `${printer.toner_yellow}%`;
            document.getElementById('modal-toner-yellow-bar').style.width = `${printer.toner_yellow}%`;
            
            // Wire action
            document.getElementById('btn-modal-clear').onclick = () => {
                clearQueue(host, printerName);
            };
            
            document.getElementById('modal-printer-detail').classList.add('active');
        });
};

function clearQueue(host, printerName) {
    fetch('/api/printers/clear_queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host: host, printer: printerName })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('success', 'Queue clear command successfully sent!');
            closeModal();
            fetchPrinters();
        } else {
            showToast('error', 'Failed to clear queue: ' + data.error);
        }
    });
}

window.showIncidentDetail = function(layer, analysis, steps) {
    document.getElementById('modal-inc-layer').textContent = `OSI Layer ${layer}`;
    document.getElementById('modal-inc-analysis').textContent = analysis;
    
    const stepsContainer = document.getElementById('modal-inc-steps');
    stepsContainer.innerHTML = '';
    
    if (steps && steps.length > 0) {
        steps.forEach((step, idx) => {
            const stepDiv = document.createElement('div');
            stepDiv.style.background = 'rgba(255,255,255,0.02)';
            stepDiv.style.border = '1px solid var(--border)';
            stepDiv.style.padding = '8px 12px';
            stepDiv.style.borderRadius = '6px';
            
            const numSpan = document.createElement('span');
            numSpan.style.color = 'var(--purple)';
            numSpan.style.fontWeight = '600';
            numSpan.textContent = `${idx+1}. `;
            
            const textSpan = document.createElement('span');
            textSpan.textContent = typeof step === 'string' ? step : JSON.stringify(step);
            
            stepDiv.append(numSpan, textSpan);
            stepsContainer.appendChild(stepDiv);
        });
    } else {
        const emptySpan = document.createElement('span');
        emptySpan.style.color = 'var(--text-muted)';
        emptySpan.textContent = 'No immediate steps required. Follow standard procedures.';
        stepsContainer.appendChild(emptySpan);
    }
    
    document.getElementById('modal-incident-detail').classList.add('active');
};

window.closeModal = function() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
};

// ── Logs Helper ──
function logToConsole(message, type = "info") {
    const logsContainer = document.getElementById('dashboard-logs');
    if (!logsContainer) return;
    
    const div = document.createElement('div');
    let color = 'var(--text-main)';
    if (type === 'critical' || type === 'error') color = 'var(--red)';
    else if (type === 'warning') color = 'var(--orange)';
    else if (type === 'success') color = 'var(--green)';
    
    div.style.color = color;
    div.textContent = message;
    
    logsContainer.appendChild(div);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// ── Production-Ready Alert Storm Debouncer & Categorized Notification Manager ──
let alertQueue = [];
let alertDebounceTimer = null;

function playAlertChime() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
        // AudioContext disabled or unsupported
    }
}

function showToast(type, msg) {
    // Push alert to sliding window queue for 3-second debouncing
    alertQueue.push({ type, msg, timestamp: Date.now() });

    if (alertDebounceTimer) {
        clearTimeout(alertDebounceTimer);
    }

    alertDebounceTimer = setTimeout(() => {
        flushAlertQueue();
    }, 1500);
}

function flushAlertQueue() {
    if (alertQueue.length === 0) return;

    const container = document.getElementById('toast-container');
    if (!container) {
        alertQueue = [];
        return;
    }

    // Cluster alerts if > 3 arrive in same debouncing window
    if (alertQueue.length >= 4) {
        const criticalCount = alertQueue.filter(a => a.type === 'critical' || a.type === 'error').length;
        const summaryMsg = `[ALERT CLUSTER] ${alertQueue.length} Telemetry Alerts Received (${criticalCount} Critical)`;
        renderToastCard(container, 'critical', summaryMsg, true);
        playAlertChime();
    } else {
        alertQueue.forEach(item => {
            const isCritical = item.type === 'critical' || item.type === 'error';
            renderToastCard(container, item.type, item.msg, isCritical);
            if (isCritical) {
                playAlertChime();
            }
        });
    }

    alertQueue = [];
}

function renderToastCard(container, type, msg, isPersistent) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.background = (type === 'critical' || type === 'error') ? 'var(--red)' : type === 'warning' ? 'var(--orange)' : 'var(--purple)';
    toast.style.color = 'white';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.fontSize = '13px';
    toast.style.fontWeight = '600';
    toast.style.boxShadow = '0 4px 15px rgba(0,0,0,0.3)';
    toast.style.transition = 'all 0.3s ease';
    toast.style.marginBottom = '8px';

    if (isPersistent) {
        const span = document.createElement('span');
        span.textContent = `🚨 ${msg}`;
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '✕';
        closeBtn.style.cssText = 'background:transparent; border:none; color:white; font-weight:bold; cursor:pointer; margin-left:10px;';
        closeBtn.addEventListener('click', () => toast.remove());
        toast.append(span, closeBtn);
    } else {
        toast.textContent = msg;
    }

    container.appendChild(toast);

    if (!isPersistent) {
        const ttl = type === 'warning' ? 5000 : 3000;
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, ttl);
    }
}

// ── Chart.js Analytics ──
function initAnalyticsChart() {
    const ctx = document.getElementById('chart-analytics').getContext('2d');
    analyticsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['10m ago', '9m ago', '8m ago', '7m ago', '6m ago', '5m ago', '4m ago', '3m ago', '2m ago', '1m ago', 'Now'],
            datasets: [
                {
                    label: 'PC CPU Utilization (%)',
                    data: [15, 12, 18, 20, 22, 14, 16, 25, 30, 22, 14],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.05)',
                    tension: 0.3,
                    borderWidth: 2
                },
                {
                    label: 'Printer Spooler Queue Length',
                    data: [0, 0, 1, 1, 2, 2, 2, 3, 5, 2, 2],
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.05)',
                    tension: 0.1,
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#b4bcc9', font: { family: 'Outfit' } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#626d7f' }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#626d7f' }
                }
            }
        }
    });
}

window.showAgentDeepDetail = function(agentName) {
    document.getElementById('modal-agent-name').textContent = agentName;
    document.getElementById('modal-agent-ip').textContent = 'Fetching IP...';
    document.getElementById('agentDetailModal').style.display = 'block';
    
    const body = document.getElementById('modal-agent-body');
    body.innerHTML = `
      <div style="text-align:center; padding:40px; color:var(--cyan);">
        <div style="font-size:36px; margin-bottom:15px;" class="fa-spin">⚙️</div>
        <div style="font-family:var(--font-mono);">Establishing Secure TCP Connection to Agent...</div>
      </div>
    `;

    fetch('/api/agent_deep_diagnostics/' + encodeURIComponent(agentName))
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                body.innerHTML = `<div style="color:var(--red); padding:20px;">Error: ${escapeHtml(data.error)}</div>`;
                return;
            }
            document.getElementById('modal-agent-ip').textContent = data.ip || 'Unknown IP';
            
            let tabsHtml = `
              <div style="display:flex; border-bottom:1px solid var(--border); margin-bottom:15px; gap:10px;">
                <button onclick="switchAgentTab('network')" class="agent-tab active" id="tab-btn-network" style="background:none; color:var(--cyan); border:none; border-bottom:2px solid var(--cyan); padding:8px 12px; cursor:pointer;">Network</button>
                <button onclick="switchAgentTab('apps')" class="agent-tab" id="tab-btn-apps" style="background:none; color:var(--text-muted); border:none; border-bottom:2px solid transparent; padding:8px 12px; cursor:pointer;">Apps & Web</button>
                <button onclick="switchAgentTab('printers')" class="agent-tab" id="tab-btn-printers" style="background:none; color:var(--text-muted); border:none; border-bottom:2px solid transparent; padding:8px 12px; cursor:pointer;">Printers</button>
                <button onclick="switchAgentTab('issues')" class="agent-tab" id="tab-btn-issues" style="background:none; color:var(--text-muted); border:none; border-bottom:2px solid transparent; padding:8px 12px; cursor:pointer;">AI Issues</button>
              </div>
            `;
            
            // Network
            let networkStr = (data.agent_data && data.agent_data.network) ? data.agent_data.network : 'No data';
            let networkHtml = `<div id="tab-content-network" class="agent-tab-content active" style="display:block;">
              <pre style="background:rgba(0,0,0,0.3); padding:10px; border-radius:4px; border:1px solid var(--border); font-family:var(--font-mono); font-size:11px; color:var(--green); max-height:400px; overflow-y:auto; white-space:pre-wrap;">${escapeHtml(networkStr)}</pre>
            </div>`;
            
            // Apps
            let appsHtml = '<div id="tab-content-apps" class="agent-tab-content" style="display:none;">';
            if (data.agent_data && data.agent_data.apps && data.agent_data.apps.length > 0) {
                appsHtml += `<div style="font-size:12px; color:var(--text-muted); margin-bottom:5px;">${data.agent_data.apps.length} Active UI Applications</div>
                <table class="gov-table" style="width:100%; font-size:12px;">
                  <thead><tr><th>PID</th><th>Process Name</th><th>Window Title</th></tr></thead><tbody>`;
                data.agent_data.apps.forEach(app => {
                    appsHtml += `<tr>
                      <td style="color:var(--purple);">${escapeHtml(app.Id)}</td>
                      <td>${escapeHtml(app.Name)}</td>
                      <td style="color:var(--cyan);">${escapeHtml(app.MainWindowTitle)}</td>
                    </tr>`;
                });
                appsHtml += `</tbody></table>`;
            } else {
                appsHtml += `<div style="color:var(--text-muted);">No active apps detected or command failed.</div>`;
            }
            
            // Web Connections
            appsHtml += `<div style="font-size:12px; color:var(--text-muted); margin-top:20px; margin-bottom:5px;">Active TCP Web Connections (80/443)</div>`;
            if (data.agent_data && data.agent_data.webs && data.agent_data.webs.length > 0) {
                 appsHtml += `<table class="gov-table" style="width:100%; font-size:12px;">
                  <thead><tr><th>PID</th><th>Local Address</th><th>Remote Web Address</th></tr></thead><tbody>`;
                data.agent_data.webs.forEach(w => {
                    appsHtml += `<tr>
                      <td style="color:var(--purple);">${escapeHtml(w.pid)}</td>
                      <td>${escapeHtml(w.local)}</td>
                      <td style="color:var(--green);">${escapeHtml(w.remote)}</td>
                    </tr>`;
                });
                appsHtml += `</tbody></table>`;
            } else {
                 appsHtml += `<div style="color:var(--text-muted);">No active web TCP connections found.</div>`;
            }
            appsHtml += `</div>`;
            
            // Printers
            let prHtml = '<div id="tab-content-printers" class="agent-tab-content" style="display:none;">';
            if (data.agent_data && data.agent_data.printers && data.agent_data.printers.installed_list) {
                let prList = data.agent_data.printers.installed_list;
                prList.forEach(pr => {
                    let stColor = pr.status_code === 0 ? "var(--green)" : "var(--red)";
                    prHtml += `<div style="background:rgba(255,255,255,0.05); border:1px solid var(--border); padding:10px; margin-bottom:10px; border-radius:4px;">
                      <div style="font-weight:bold; color:var(--text-bright); margin-bottom:5px;">🖨️ ${escapeHtml(pr.name)}</div>
                      <div style="display:grid; grid-template-columns:1fr 1fr; gap:5px; font-size:12px; color:var(--text-muted);">
                        <div>Port/IP: <span style="color:var(--cyan);">${escapeHtml(pr.port)}</span></div>
                        <div>Status: <span style="color:${stColor};">${pr.status_code === 0 ? 'Ready' : 'Error/Offline'} (Code ${escapeHtml(pr.status_code)})</span></div>
                        <div>Queue Size: <span style="color:var(--purple);">${escapeHtml(pr.queue_size)}</span> jobs</div>
                      </div>
                    </div>`;
                });
            } else {
                prHtml += `<div style="color:var(--text-muted);">No detailed printer info available.</div>`;
            }
            prHtml += `</div>`;
            
            // Issues
            let isHtml = '<div id="tab-content-issues" class="agent-tab-content" style="display:none;">';
            if (data.incidents && data.incidents.length > 0) {
                 data.incidents.forEach(inc => {
                     isHtml += `<div style="background:rgba(0,0,0,0.2); border-left:3px solid var(--red); padding:10px; margin-bottom:10px;">
                       <div style="font-size:11px; color:var(--text-muted);">${escapeHtml(inc.timestamp)} - OSI Layer ${escapeHtml(inc.layer)}</div>
                       <div style="font-weight:bold; color:var(--amber); margin:5px 0;">${escapeHtml(inc.flag || inc.issue)}</div>
                       <div style="font-size:12px; color:var(--text-primary);">${escapeHtml(inc.analysis || inc.alert_info)}</div>
                     </div>`;
                 });
            } else {
                 isHtml += `<div style="color:var(--green);"><i class="fas fa-check-circle"></i> No recent incidents recorded in AI database.</div>`;
            }
            isHtml += `</div>`;
            
            body.innerHTML = tabsHtml + networkHtml + appsHtml + prHtml + isHtml;
        })
        .catch(err => {
            body.innerHTML = `<div style="color:var(--red); padding:20px;">Fetch failed: ${escapeHtml(err)}</div>`;
        });
};

window.switchAgentTab = function(tabName) {
    document.querySelectorAll('.agent-tab').forEach(b => {
        b.style.color = 'var(--text-muted)';
        b.style.borderColor = 'transparent';
    });
    document.querySelectorAll('.agent-tab-content').forEach(c => c.style.display = 'none');
    
    document.getElementById('tab-btn-' + tabName).style.color = 'var(--cyan)';
    document.getElementById('tab-btn-' + tabName).style.borderColor = 'var(--cyan)';
    document.getElementById('tab-content-' + tabName).style.display = 'block';
};

window.closeAgentModal = function() {
    document.getElementById('agentDetailModal').style.display = 'none';
};
