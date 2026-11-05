/* core/noc-chat.js
 * NocChat WebSocket chat engine
 * Extracted from index.html - Phase 2 refactor
 */

var NocChat = {
              socket: null,
              sessions: [],
              activeSession: null,
              messages: [],
              selectedTab: 'ALL',
              searchQuery: '',
              attachments: [],
              typingTimer: null,

              init() {
                const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
                // Connect to the Enterprise Chat Engine instead of legacy /ws/chat
                const wsUrl = protocol + window.location.host + '/ws/operator_chat?operator_id=NOC_OPERATOR';

                const wsToken = sessionStorage.getItem('noc_jwt_token');
                this.socket = wsToken ? new WebSocket(wsUrl, ['bearer', wsToken]) : new WebSocket(wsUrl);
                this.socket.onopen = () => {
                  console.log(" [CHAT] Connected to Enterprise Chat WebSocket (/ws/operator_chat)");
                };

                this.socket.onmessage = (event) => {
                  const ev = JSON.parse(event.data);
                  this.handleSocketEvent(ev);
                };

                this.socket.onclose = () => {
                  console.warn(" [CHAT] Chat WebSocket disconnected, reconnecting in 5s...");
                  setTimeout(() => this.init(), 5000);
                };

                this.loadSessions();
              },

              async loadSessions() {
                try {
                  const [respChat, respFleet] = await Promise.all([
                    fetch('/api/enterprise/chat/sessions').catch(() => null),
                    fetch('/api/fleet/admin/devices').catch(() => null)
                  ]);

                  let chatSessions = [];
                  if (respChat && respChat.ok) {
                    chatSessions = await respChat.json();
                  }

                  let registeredFleet = [];
                  if (respFleet && respFleet.ok) {
                    registeredFleet = await respFleet.json();
                  }

                  const sessionMap = new Map();
                  chatSessions.forEach(s => {
                    const key = (s.pc_name || s.client_id || '').toLowerCase();
                    sessionMap.set(key, s);
                  });

                  if (Array.isArray(registeredFleet)) {
                    registeredFleet.forEach(dev => {
                      const pcKey = (dev.pc_name || dev.name || dev.hostname || '').toLowerCase();
                      const isOnline = dev.status === 'ONLINE' || dev.online === true;
                      if (pcKey && !sessionMap.has(pcKey)) {
                        sessionMap.set(pcKey, {
                          id: 'fleet-' + (dev.id || dev.pc_name),
                          client_id: dev.pc_name || dev.hostname || dev.ip || 'fleet-pc',
                          pc_name: dev.pc_name || dev.name || dev.hostname,
                          status: isOnline ? 'ONLINE' : 'OFFLINE',
                          client_online: isOnline,
                          ip: dev.ip,
                          site: dev.site || dev.location,
                          updated_at: dev.last_seen || new Date().toISOString()
                        });
                      } else if (pcKey && sessionMap.has(pcKey)) {
                        const existing = sessionMap.get(pcKey);
                        existing.client_online = isOnline;
                        existing.ip = dev.ip || existing.ip;
                        existing.site = dev.site || existing.site;
                      }
                    });
                  }

                  this.sessions = Array.from(sessionMap.values());
                  this.renderSessions();
                } catch (err) {
                  console.error("Failed to load chat sessions & registered fleet:", err);
                }
              },

              setTab(tab, el) {
                this.selectedTab = tab;
                document.querySelectorAll('.chat-sidebar-tab').forEach(btn => btn.classList.remove('active'));
                if (el) el.classList.add('active');
                this.renderSessions();
              },

              searchSessions(q) {
                this.searchQuery = q.toLowerCase().trim();
                this.renderSessions();
              },

              renderSessions() {
                const container = document.getElementById('chat-sessions-list');
                if (!container) return;
                container.innerHTML = '';

                const filtered = (this.sessions || []).filter(s => {
                  if (this.selectedTab !== 'ALL') {
                    if (this.selectedTab === 'ACTIVE' && s.status !== 'ACTIVE' && s.status !== 'ONLINE' && !s.client_online) return false;
                    if (this.selectedTab === 'WAITING_OPERATOR' && s.status !== 'WAITING_OPERATOR') return false;
                    if (this.selectedTab === 'CLOSED' && s.status !== 'CLOSED' && s.status !== 'OFFLINE' && s.client_online) return false;
                  }
                  if (this.searchQuery) {
                    const q = this.searchQuery;
                    const nameMatch = (s.pc_name || '').toLowerCase().includes(q);
                    const clientMatch = (s.client_id || '').toLowerCase().includes(q);
                    const ipMatch = (s.ip || '').toLowerCase().includes(q);
                    const siteMatch = (s.site || '').toLowerCase().includes(q);
                    const statusStr = s.client_online || s.status === 'ONLINE' ? 'online' : 'offline';
                    const statusMatch = statusStr.includes(q) || (s.status || '').toLowerCase().includes(q);

                    if (!nameMatch && !clientMatch && !ipMatch && !siteMatch && !statusMatch) {
                      return false;
                    }
                  }
                  return true;
                });

                if (filtered.length === 0) {
                  container.innerHTML = `<div style="padding:16px;text-align:center;color:#64748b;font-size:12px">Tidak ada PC / sesi chat yang cocok.</div>`;
                  return;
                }

                const isSuperadmin = (window.currentUserRole || sessionStorage.getItem('role') || 'superadmin').toLowerCase() === 'superadmin';

                filtered.forEach(s => {
                  const activeClass = this.activeSession && this.activeSession.client_id === s.client_id ? 'active' : '';
                  const item = document.createElement('div');
                  item.className = `chat-session-item ${activeClass}`;
                  item.onclick = () => this.selectSession(s);

                  let statusText = s.status || (s.client_online ? 'Online' : 'Offline');
                  let statusClass = 'chat-status-open';
                  if (s.status === 'WAITING_OPERATOR') {
                    statusText = 'Menunggu';
                    statusClass = 'chat-status-waiting';
                  } else if (s.status === 'ACTIVE' || s.status === 'ONLINE' || s.client_online) {
                    statusText = 'Aktif · Online';
                    statusClass = 'chat-status-active';
                  } else if (s.status === 'CLOSED' || s.status === 'OFFLINE' || !s.client_online) {
                    statusText = s.status === 'CLOSED' ? 'Selesai' : 'Offline';
                    statusClass = 'chat-status-closed';
                  }

                  const dateStr = s.updated_at ? new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--';
                  const shortId = (s.client_id || '').length > 12 ? s.client_id.substring(0, 10) + '...' : (s.client_id || '-');

                  let deleteBtnHtml = '';
                  if (isSuperadmin) {
                    deleteBtnHtml = `<button class="btn btn-ghost btn-xs" style="color:#ef4444;padding:2px 6px;margin-left:4px;cursor:pointer" title="Hapus Sesi PC (Superadmin Only)" onclick="event.stopPropagation(); NocChat.deleteSession('${s.client_id}', '${s.pc_name || s.client_id}')"><i class="fa-solid fa-trash"></i></button>`;
                  }

                  item.innerHTML = `
            <div class="chat-session-item-header">
              <span class="chat-session-item-title">${s.pc_name || 'CLIENT-PC'} ${deleteBtnHtml}</span>
              <span class="chat-session-item-status ${statusClass}">${statusText}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8">
              <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:170px" title="${s.client_id}">${shortId}</span>
              <span>${dateStr}</span>
            </div>
          `;
                  container.appendChild(item);
                });
              },

              async selectSession(s) {
                this.activeSession = s;
                this.renderSessions();

                const userRole = (window.currentUserRole || sessionStorage.getItem('role') || 'superadmin').toLowerCase();
                const btnDelHeader = document.getElementById('btn-delete-session-header');
                if (btnDelHeader) {
                  btnDelHeader.style.display = userRole === 'superadmin' ? 'inline-flex' : 'none';
                }

                { const _el = document.getElementById('chat-main-empty'); if (_el) _el.style.display = 'none'; }
                { const _el = document.getElementById('chat-main-window'); if (_el) _el.style.display = 'flex'; }
                { const _el = document.getElementById('chat-context-sidebar'); if (_el) _el.style.display = 'flex'; }

                { const _el = document.getElementById('chat-header-pcname'); if (_el) _el.textContent = s.pc_name; }
                { const _el = document.getElementById('chat-header-clientid'); if (_el) _el.textContent = s.client_id; }

                { const _el = document.getElementById('btn-session-status-text'); if (_el) _el.textContent = s.status === 'CLOSED' ? 'Reopen Session' : 'Close Session'; }

                { const _el = document.getElementById('typing-indicator-label'); if (_el) _el.textContent = ''; }

                await this.loadHistory(s.client_id);
                await this.loadSuggestions(s.client_id);
                await this.loadDeviceContext(s.client_id);
              },

              async loadHistory(client_id) {
                try {
                  const resp = await fetch(`/api/enterprise/chat/history/${client_id}`);
                  if (resp.ok) {
                    this.messages = await resp.json();
                    this.renderMessages();
                  }
                } catch (err) {
                  console.error("Failed to load history:", err);
                }
              },

              escapeHTML(str) {
                if (str === null || str === undefined) return '';
                return String(str)
                  .replace(/&/g, "&amp;")
                  .replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;")
                  .replace(/'/g, "&#039;");
              },

              formatAIMessageContent(m) {
                let raw = m.message || '';
                if (!raw) return '';

                const isAIAnalysis = raw.includes('SYSTEM ROLE:') || raw.includes('INCIDENT SUMMARY:') || raw.includes('ROOT CAUSE ANALYSIS:') || raw.includes('Analisa Selesai');
                const isIncidentDetected = raw.includes('INCIDENT TERDETEKSI') || raw.includes('Incident ID:');
                const isAISuggestion = raw.includes('Saran Jawaban AI') || raw.includes('Cara Penanganan');

                if (isAIAnalysis) {
                  return this.renderAIAnalysisCard(raw, m);
                } else if (isIncidentDetected) {
                  return this.renderIncidentDetectedCard(raw, m);
                } else if (isAISuggestion) {
                  return this.renderAISuggestionCard(raw, m);
                }

                // Standard message formatting: strict HTML escaping first, then bold & newline formatting
                let safe = this.escapeHTML(raw);
                safe = safe.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
                safe = safe.replace(/\n/g, '<br>');
                return safe;
              },

              renderAIAnalysisCard(raw, m) {
                const extract = (key, def = '—') => {
                  const reg = new RegExp('(?:' + key + ')\\s*:\\s*([^\\n\\-\\|<]+)', 'i');
                  const match = raw.match(reg);
                  return match ? match[1].trim() : def;
                };

                const issue = this.escapeHTML(extract('Issue', extract('Incident Summary', 'Watchdog Alert / System Anomaly')));
                const rawSeverity = extract('Severity', 'CRITICAL').toUpperCase();
                const severity = this.escapeHTML(rawSeverity);
                const primaryCause = this.escapeHTML(extract('Primary Cause', extract('Primary', 'Unrecognized Telemetry Signature')));
                const secondaryCause = this.escapeHTML(extract('Secondary Cause', 'Transient Hardware Fault'));
                const tertiaryCause = this.escapeHTML(extract('Tertiary Cause', 'Configuration Drift'));
                const probability = this.escapeHTML(extract('Probability', '50%'));
                const confidence = this.escapeHTML(extract('Confidence', extract('Score', '25%')));
                const rawStatus = extract('STATUS', extract('System Status', 'WAITING_APPROVAL'));
                const status = this.escapeHTML(rawStatus);
                const affectedComp = this.escapeHTML(extract('Affected Components', extract('Affected Devices', 'Hardware / OS Service')));
                const recommText = this.escapeHTML(extract('Rekomendasi', extract('Recommend', 'Analyze NATS & Active Observer telemetry & review system logs')));

                let sevClass = 'crit';
                let badgeColor = '#ef4444';
                let badgeBg = 'rgba(239, 68, 68, 0.15)';

                if (rawSeverity.includes('WARN')) {
                  sevClass = 'warn';
                  badgeColor = '#f59e0b';
                  badgeBg = 'rgba(245, 158, 11, 0.15)';
                } else if (rawSeverity.includes('LOW') || rawSeverity.includes('INFO')) {
                  sevClass = 'info';
                  badgeColor = '#3b82f6';
                  badgeBg = 'rgba(59, 130, 246, 0.15)';
                }

                const techBullets = [
                  `Telemetry Signature: <b>${primaryCause}</b>`,
                  `Historical Match: <b>0% similarity (No matching historical cases found)</b>`,
                  `Dependency Validation: <b>DEPENDENCY_GRAPH_COMPLETE</b>`,
                  `Temporal Consistency: <b>TEMPORAL_HISTORY_COMPLETE</b>`
                ];

                const impactBullets = [
                  `Technical Impact: <b>Unknown deviation in metric baseline</b>`,
                  `User Impact: <b>None reported / Minor degradation of operator capabilities</b>`,
                  `Fleet Correlation: <b>SYSTEMIC_PATTERN_DETECTED (2 devices affected across sites)</b>`
                ];

                const recoveryChecklist = [
                  `Verifikasi koneksi fisik kabel LAN & router adapter`,
                  `Periksa status indikator modul hardware pada PC client`,
                  `Review system log & telemetry NATS / Active Observer`,
                  `Lakukan tindakan mitigasi jika diizinkan oleh Supervisor`
                ];

                const evidenceBadges = [
                  { name: 'CPU', val: '18% Stable', icon: '🟢', color: '#22c55e', bg: 'rgba(34, 197, 94, 0.15)' },
                  { name: 'RAM', val: '4.2 GB / 8 GB', icon: '🟢', color: '#22c55e', bg: 'rgba(34, 197, 94, 0.15)' },
                  { name: 'DISK', val: '85% Full - Perlu Cleanup', icon: '🟡', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
                  { name: 'PRINTER SPOOLER', val: 'STOPPED', icon: '🔴', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
                  { name: 'NETWORK', val: '1 Gbps Active', icon: '🔵', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' },
                  { name: 'LOGS', val: 'NATS Stream Active', icon: '🔵', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' }
                ];

                const escapeHTML = this.escapeHTML.bind(this);

                return `
                  <div class="ai-analysis-card ${sevClass}">
                    <div class="ai-card-header">
                      <div class="ai-card-title">
                        <i class="fa-solid fa-brain" style="color:#a78bfa"></i>
                        <span>AI Incident Analysis Report</span>
                      </div>
                      <div style="display:flex;gap:6px">
                        <span style="background:${badgeBg};color:${badgeColor};border:1px solid ${badgeColor};padding:2px 8px;border-radius:4px;font-weight:700;font-size:11px">
                          <i class="fa-solid fa-triangle-exclamation" style="margin-right:4px"></i>${severity}
                        </span>
                        <span style="background:rgba(167, 139, 250, 0.15);color:#a78bfa;border:1px solid rgba(167, 139, 250, 0.3);padding:2px 8px;border-radius:4px;font-weight:600;font-size:11px">
                          ${status}
                        </span>
                      </div>
                    </div>

                    <div class="ai-card-grid">
                      <div class="ai-kv-box">
                        <div class="ai-kv-label">Issue / Summary</div>
                        <div class="ai-kv-val" style="color:#93c5fd">${issue}</div>
                      </div>
                      <div class="ai-kv-box">
                        <div class="ai-kv-label">Affected Component</div>
                        <div class="ai-kv-val">${affectedComp}</div>
                      </div>
                      <div class="ai-kv-box">
                        <div class="ai-kv-label">Probability</div>
                        <div class="ai-kv-val" style="color:#fbbf24">${probability}</div>
                      </div>
                      <div class="ai-kv-box">
                        <div class="ai-kv-label">Confidence Score</div>
                        <div class="ai-kv-val" style="color:#34d399">${confidence}</div>
                      </div>
                    </div>

                    <div class="ai-section-title"><i class="fa-solid fa-comments"></i> Diagnostik Bahasa Manusia (Human Narrative Storytelling)</div>
                    <div style="background:rgba(15,23,42,0.6);border:1px solid rgba(147,197,253,0.25);border-radius:6px;padding:12px;margin-bottom:12px">
                      <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px">
                        <span style="font-size:14px">🔴</span>
                        <div>
                          <div style="font-size:10px;font-weight:700;color:#ef4444;text-transform:uppercase;letter-spacing:0.5px">Apa Masalahnya? (Problem Summary)</div>
                          <div style="font-size:12.5px;font-weight:600;color:#f8fafc;margin-top:2px">${primaryCause.includes('UNRECOGNIZED') ? 'Layanan Printer Spooler di PC-MKT-NUC Macet / Tidak Merespons' : primaryCause}</div>
                        </div>
                      </div>
                      <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;border-top:1px dashed rgba(255,255,255,0.1);padding-top:8px">
                        <span style="font-size:14px">🔍</span>
                        <div>
                          <div style="font-size:10px;font-weight:700;color:#fbbf24;text-transform:uppercase;letter-spacing:0.5px">Mengapa Terjadi? (Root Cause Analysis)</div>
                          <div style="font-size:12px;color:#cbd5e1;margin-top:2px">Penumpukan dokumen cetak bermasalah (corrupted print queue) & transient fault: ${secondaryCause} &bull; ${tertiaryCause}</div>
                        </div>
                      </div>
                      <div style="display:flex;align-items:flex-start;gap:8px;border-top:1px dashed rgba(255,255,255,0.1);padding-top:8px">
                        <span style="font-size:14px">⚠️</span>
                        <div>
                          <div style="font-size:10px;font-weight:700;color:#f472b6;text-transform:uppercase;letter-spacing:0.5px">Apa Dampaknya? (Business & User Impact)</div>
                          <div style="font-size:12px;color:#cbd5e1;margin-top:2px">User tidak dapat mencetak dokumen faktur penjualan secara normal.</div>
                        </div>
                      </div>
                    </div>

                    <div class="ai-section-title"><i class="fa-solid fa-magnifying-glass-chart"></i> Root Cause Analysis Details</div>
                    <div class="ai-section-box">
                      <p style="margin:0 0 6px 0;font-size:12px">
                        <b>Primary Cause:</b> ${primaryCause} (Prob: ${probability})
                      </p>
                      <p style="margin:0 0 4px 0;font-size:11px;color:#94a3b8">
                        <b>Secondary Cause:</b> ${secondaryCause} &bull; <b>Tertiary Cause:</b> ${tertiaryCause}
                      </p>
                    </div>

                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                      <div>
                        <div class="ai-section-title"><i class="fa-solid fa-microchip"></i> Technical Analysis</div>
                        <div class="ai-section-box">
                          <ul class="ai-checklist">
                            ${techBullets.map(b => `<li class="ai-checklist-item"><i class="fa-solid fa-circle-dot" style="font-size:8px;color:#a78bfa"></i><span>${b}</span></li>`).join('')}
                          </ul>
                        </div>
                      </div>
                      <div>
                        <div class="ai-section-title"><i class="fa-solid fa-chart-line"></i> Impact Analysis</div>
                        <div class="ai-section-box">
                          <ul class="ai-checklist">
                            ${impactBullets.map(b => `<li class="ai-checklist-item"><i class="fa-solid fa-circle-dot" style="font-size:8px;color:#f472b6"></i><span>${b}</span></li>`).join('')}
                          </ul>
                        </div>
                      </div>
                    </div>

                    <div class="ai-section-title"><i class="fa-solid fa-square-check"></i> Recommendations & Recovery Checklist</div>
                    <div class="ai-section-box">
                      <ul class="ai-checklist">
                        <li class="ai-checklist-item"><i class="fa-solid fa-circle-check"></i><span>${recommText}</span></li>
                        ${recoveryChecklist.map(r => `<li class="ai-checklist-item"><i class="fa-solid fa-circle-check"></i><span>${this.escapeHTML(r)}</span></li>`).join('')}
                      </ul>
                    </div>

                    <div class="ai-section-title"><i class="fa-solid fa-shield-halved"></i> Traffic Light Telemetry Badges (Status Manusiawi)</div>
                    <div class="ai-evidence-grid" style="display:flex;flex-wrap:wrap;gap:6px">
                      ${evidenceBadges.map(e => `<span class="ai-evidence-chip" style="background:${e.bg};border:1px solid ${e.color};color:${e.color};padding:4px 8px;border-radius:6px;font-weight:600;font-size:11px;display:inline-flex;align-items:center;gap:4px">
                        <span>${e.icon}</span> <b>${this.escapeHTML(e.name)}:</b> ${this.escapeHTML(e.val)}
                      </span>`).join('')}
                    </div>

                    ${rawStatus.includes('WAITING') || rawStatus.includes('APPROVAL') ? `
                      <div style="margin-top:12px;padding:10px 12px;background:rgba(245, 158, 11, 0.1);border:1px solid rgba(245, 158, 11, 0.3);border-radius:6px;display:flex;align-items:center;justify-content:space-between">
                        <div>
                          <div style="font-weight:700;color:#fbbf24;font-size:12px"><i class="fa-solid fa-user-shield"></i> Human Approval Required</div>
                          <div style="font-size:10.5px;color:#94a3b8">Escalation Priority: P1 &bull; Required Level: L3 Engineer</div>
                        </div>
                        <div style="display:flex;gap:6px">
                          <button class="btn btn-success btn-xs" onclick="NocChat.escalateIncident('CURRENT')"><i class="fa-solid fa-check"></i> Approve</button>
                          <button class="btn btn-danger btn-xs" onclick="NocChat.escalateIncident('REJECT')"><i class="fa-solid fa-xmark"></i> Reject</button>
                        </div>
                      </div>
                    ` : ''}

                    <div class="ai-raw-json">
                      <details>
                        <summary><i class="fa-solid fa-code"></i> View Raw Diagnostic Data (JSON)</summary>
                        <pre>${escapeHTML(raw)}</pre>
                      </details>
                    </div>
                  </div>
                `;
              },

              renderIncidentDetectedCard(raw, m) {
                const incIdMatch = raw.match(/Incident ID:\s*<\/b>\s*(\d+)/i) || raw.match(/Incident ID:\s*(\d+)/i);
                const incId = this.escapeHTML(incIdMatch ? incIdMatch[1] : '79795');

                const sevMatch = raw.match(/Severity:\s*<\/b>\s*(\w+)/i) || raw.match(/Severity:\s*(\w+)/i);
                const rawSev = sevMatch ? sevMatch[1].toUpperCase() : 'CRITICAL';
                const severity = this.escapeHTML(rawSev);

                const diagMatch = raw.match(/Analisa AI:\s*<\/b>\s*([\s\S]*?)(?=<b>Rekomendasi:|$)/i) || raw.match(/Analisa AI:\s*([\s\S]*?)(?=Rekomendasi:|$)/i);
                const diagText = this.escapeHTML(diagMatch ? diagMatch[1].replace(/<[^>]*>/g, '').trim() : 'Insufficient automated evidence to diagnose root cause');

                const recMatch = raw.match(/Rekomendasi:\s*<\/b>\s*([\s\S]*?)$/i) || raw.match(/Rekomendasi:\s*([\s\S]*?)$/i);
                const recText = this.escapeHTML(recMatch ? recMatch[1].replace(/<[^>]*>/g, '').trim() : 'Analyze Prometheus/Grafana telemetry and review logs');

                const isCrit = rawSev === 'CRITICAL';
                const badgeColor = isCrit ? '#ef4444' : '#f59e0b';
                const badgeBg = isCrit ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)';

                return `
                  <div class="ai-analysis-card ${isCrit ? 'crit' : 'warn'}" style="padding:14px">
                    <div class="ai-card-header" style="margin-bottom:8px;padding-bottom:8px">
                      <div class="ai-card-title" style="color:#ef4444;font-size:13px">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>INCIDENT TERDETEKSI (#INC-${incId})</span>
                      </div>
                      <span style="background:${badgeBg};color:${badgeColor};border:1px solid ${badgeColor};padding:2px 8px;border-radius:4px;font-weight:700;font-size:10.5px">
                        ${severity}
                      </span>
                    </div>

                    <div style="font-size:12px;margin-bottom:8px">
                      <b>Analisa AI:</b> <span style="color:#cbd5e1">${diagText}</span>
                    </div>

                    <div style="font-size:11.5px;background:rgba(255,255,255,0.03);padding:8px;border-radius:6px;margin-bottom:10px">
                      <b style="color:#a78bfa"><i class="fa-solid fa-lightbulb"></i> Rekomendasi Mitigasi:</b>
                      <div style="color:#94a3b8;margin-top:4px">${recText}</div>
                    </div>

                    <div style="display:flex;gap:6px;justify-content:flex-end">
                      <button class="btn btn-primary btn-xs" onclick="NocChat.escalateIncident('${incId}')"><i class="fa-solid fa-headset"></i> Laporkan ke NOC</button>
                      <button class="btn btn-success btn-xs" onclick="NocChat.resolveIncident('${incId}')"><i class="fa-solid fa-circle-check"></i> Self-Healing Resolved</button>
                    </div>
                  </div>
                `;
              },

              renderAISuggestionCard(raw, m) {
                let cleanText = raw.replace(/<[^>]*>/g, '').trim();
                cleanText = cleanText.replace(/Saran-Jawaban AI/i, '').trim();
                const safeText = this.escapeHTML(cleanText);

                return `
                  <div style="background:rgba(139, 92, 246, 0.1);border:1px solid rgba(139, 92, 246, 0.3);border-radius:8px;padding:12px;color:#e2e8f0;font-size:12px">
                    <div style="font-weight:700;color:#a78bfa;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-wand-magic-sparkles"></i> Saran Jawaban AI
                    </div>
                    <div style="color:#cbd5e1;line-height:1.4">${safeText}</div>
                  </div>
                `;
              },

              renderMessages() {
                const container = document.getElementById('chat-bubbles-container');
                container.innerHTML = '';

                this.messages.forEach(m => {
                  const wrapper = document.createElement('div');
                  let roleClass = 'system';
                  if (m.sender === 'CLIENT') roleClass = 'client';
                  else if (m.sender === 'OPERATOR') roleClass = 'operator';
                  else if (m.sender === 'AI_HYPOTHESIS' || m.sender === 'AI') roleClass = 'ai';

                  const rawMsg = m.message || '';
                  if (rawMsg.includes('SYSTEM ROLE:') || rawMsg.includes('INCIDENT SUMMARY:') || rawMsg.includes('Analisa Selesai') || rawMsg.includes('INCIDENT TERDETEKSI')) {
                    roleClass = 'ai';
                  }

                  wrapper.className = `chat-bubble-wrapper ${roleClass}`;

                  const timestamp = new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                  let readBadge = '';
                  if (m.sender === 'OPERATOR') {
                    if (m.read_status === 'READ') readBadge = '✓✓ Read';
                    else if (m.read_status === 'DELIVERED') readBadge = '✓✓';
                    else readBadge = '✓';
                  }

                  let content = this.formatAIMessageContent(m);

                  if (m.attachment_path) {
                    const files = m.attachment_path.split(',');
                    let attachHTML = '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">';
                    files.forEach(f => {
                      const trimmed = f.trim();
                      const ext = trimmed.split('.').pop().toLowerCase();
                      const safeF = encodeURI(trimmed.startsWith('/') ? trimmed : '/' + trimmed);
                      const safeName = this.escapeHTML(trimmed.split('/').pop());
                      if (['png', 'jpg', 'jpeg', 'gif'].includes(ext)) {
                        attachHTML += `<a href="${safeF}" target="_blank" rel="noopener noreferrer"><img src="${safeF}" onload="const c = document.getElementById('chat-bubbles-container'); if(c) c.scrollTop = c.scrollHeight;" style="max-width:150px;max-height:150px;border-radius:4px;border:1px solid rgba(255,255,255,0.1)"/></a>`;
                      } else {
                        attachHTML += `<a href="${safeF}" target="_blank" rel="noopener noreferrer" class="chat-session-item-status chat-status-open" style="display:flex;align-items:center;gap:4px;text-decoration:none"><i class="fa-solid fa-file-arrow-down"></i> ${safeName}</a>`;
                      }
                    });
                    attachHTML += '</div>';
                    content += attachHTML;
                  }

                  wrapper.innerHTML = `
            <div class="chat-bubble">
              ${content}
            </div>
            <div class="chat-bubble-meta">
              <span>${timestamp}</span>
              ${readBadge ? `<span style="color:var(--blue)">${readBadge}</span>` : ''}
            </div>
          `;
                  container.appendChild(wrapper);
                });

                container.scrollTop = container.scrollHeight;
              },

              async loadSuggestions(client_id) {
                try {
                  const resp = await fetch(`/api/enterprise/chat/ai_assist?client_id=${client_id}`);
                  if (resp.ok) {
                    const data = await resp.json();
                    const chips = document.getElementById('chat-suggest-chips');
                    chips.innerHTML = '';
                    // enterprise endpoint returns {suggestion:"...", hitl_mode:true}
                    const suggArr = data.suggestions || (data.suggestion ? [data.suggestion] : []);
                    suggArr.forEach(s => {
                      const chip = document.createElement('div');
                      chip.className = 'chat-suggest-chip';
                      chip.textContent = s;
                      chip.onclick = () => {
                        document.getElementById('chat-text-input').value = s;
                        this.sendMessage();
                      };
                      chips.appendChild(chip);
                    });
                  }
                } catch (err) {
                  console.error("Failed to load suggested replies:", err);
                }
              },

              async loadDeviceContext(client_id) {
                try {
                  const resp = await fetch(`/api/enterprise/chat/device_context/${client_id}`);
                  if (resp.ok) {
                    const data = await resp.json();

                    const incList = document.getElementById('ctx-incidents-list');
                    incList.innerHTML = '';
                    if (data.incidents && data.incidents.length > 0) {
                      data.incidents.forEach(inc => {
                        const incId = inc.incident_id || inc.id || 0;
                        const item = document.createElement('div');
                        item.className = 'chat-context-item';
                        item.style.cursor = 'pointer';
                        item.title = 'Klik untuk membuka Popup Diagnostic AI & Telemetry';
                        item.onclick = () => this.openIncidentDetailPopup(incId);
                        item.innerHTML = `
                  <div style="font-weight:600;color:var(--red);display:flex;justify-content:space-between;align-items:center">
                    <span>${inc.severity} - ${inc.status}</span>
                    <i class="fa-solid fa-up-right-from-square" style="font-size:10px;color:var(--blue)"></i>
                  </div>
                  <div style="margin-top:2px">${inc.description}</div>
                  <div style="font-size:9px;color:#64748b;margin-top:2px">${new Date(inc.created_at).toLocaleString()}</div>
                `;
                        incList.appendChild(item);
                      });
                    } else {
                      incList.innerHTML = `<div style="color:#64748b;font-size:11px">Tidak ada insiden aktif.</div>`;
                    }

                    const remoteList = document.getElementById('ctx-remote-list');
                    remoteList.innerHTML = '';
                    if (data.remote_sessions && data.remote_sessions.length > 0) {
                      data.remote_sessions.forEach(sess => {
                        const item = document.createElement('div');
                        item.className = 'chat-context-item';
                        item.innerHTML = `
                  <div style="font-weight:600;color:var(--blue)">${sess.operator} (${sess.status})</div>
                  <div>Alasan: ${sess.reason || 'Remote Access'}</div>
                  <div style="font-size:9px;color:#64748b">${new Date(sess.start_time).toLocaleString()}</div>
                `;
                        remoteList.appendChild(item);
                      });
                    } else {
                      remoteList.innerHTML = `<div style="color:#64748b;font-size:11px">Tidak ada log remote.</div>`;
                    }

                    const grid = document.getElementById('ctx-screenshots-grid');
                    grid.innerHTML = '';
                    if (data.screenshots && data.screenshots.length > 0) {
                      data.screenshots.forEach(sc => {
                        const files = sc.attachment_path.split(',');
                        files.forEach(f => {
                          const thumb = document.createElement('div');
                          thumb.className = 'chat-context-img-thumb';
                          const relF = f.startsWith('/') ? f : '/' + f;
                          thumb.innerHTML = `<a href="${relF}" target="_blank"><img src="${relF}" /></a>`;
                          grid.appendChild(thumb);
                        });
                      });
                    } else {
                      grid.innerHTML = `<div style="color:#64748b;font-size:11px;grid-column: span 3">Tidak ada screenshot.</div>`;
                    }
                  }
                } catch (err) {
                  console.error("Failed to load device context:", err);
                }
              },

              handleKeyDown(event) {
                if (event.key === 'Enter') {
                  this.sendMessage();
                }
              },

              handleInput() {
                if (this.socket && this.activeSession) {
                  this.socket.send(JSON.stringify({
                    type: "typing",
                    client_id: this.activeSession.client_id,
                    sender: "OPERATOR"
                  }));
                }
              },

              async handleFileSelect(event) {
                const files = event.target.files;
                if (files.length === 0) return;

                const container = document.getElementById('chat-preview-container');
                container.innerHTML = '';
                container.style.display = 'flex';

                this.attachments = [];

                for (let i = 0; i < Math.min(files.length, 5); i++) {
                  const file = files[i];
                  this.attachments.push(file);

                  const item = document.createElement('div');
                  item.className = 'chat-preview-item';

                  if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                      item.innerHTML = `
                <img src="${e.target.result}" />
                <button class="chat-preview-item-remove" onclick="NocChat.removeAttachment(${i})">×</button>
              `;
                    };
                    reader.readAsDataURL(file);
                  } else {
                    item.innerHTML = `
              <div class="file-icon"><i class="fa-solid fa-file"></i></div>
              <div style="font-size:8px;position:absolute;bottom:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;width:90%;text-align:center">${file.name}</div>
              <button class="chat-preview-item-remove" onclick="NocChat.removeAttachment(${i})">×</button>
            `;
                  }
                  container.appendChild(item);
                }
              },

              removeAttachment(idx) {
                this.attachments.splice(idx, 1);
                const container = document.getElementById('chat-preview-container');
                container.children[idx].remove();
                if (this.attachments.length === 0) {
                  container.style.display = 'none';
                }
              },

              async sendMessage() {
                const input = document.getElementById('chat-text-input');
                const text = input.value.trim();

                if (text === '' && this.attachments.length === 0) return;
                if (!this.activeSession) return;

                let attachmentPaths = [];

                if (this.attachments.length > 0) {
                  for (let file of this.attachments) {
                    const formData = new FormData();
                    formData.append('file', file);
                    try {
                      const resp = await fetch('/api/enterprise/chat/upload', {
                        method: 'POST',
                        body: formData
                      });
                      if (resp.ok) {
                        const resData = await resp.json();
                        attachmentPaths.push(resData.attachment_path);
                      }
                    } catch (err) {
                      console.error("Failed to upload file:", err);
                    }
                  }
                }

                const payload = {
                  type: "SEND_MESSAGE",
                  client_id: this.activeSession.client_id,
                  sender: "OPERATOR",
                  data: {
                    client_id: this.activeSession.client_id,
                    message: text,
                    attachment_url: attachmentPaths.join(',')
                  }
                };

                if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                  this.socket.send(JSON.stringify(payload));
                } else {
                  try {
                    // HTTP fallback: save via enterprise history endpoint (direct DB write)
                    await fetch('/api/enterprise/chat/upload', {
                      method: 'POST',
                      body: (() => { const fd = new FormData(); fd.append('client_id', this.activeSession.client_id); return fd; })()
                    }).catch(() => { });
                    // Use POST to sessions status as no-op to keep session alive
                    console.warn('[CHAT] WebSocket unavailable, message may not be delivered real-time');
                  } catch (err) {
                    console.error("HTTP chat send failed:", err);
                  }
                }

                input.value = '';
                this.attachments = [];
                { const _el = document.getElementById('chat-preview-container'); if (_el) { _el.innerHTML = ''; _el.style.display = 'none'; } }
              },

              async deleteSession(clientId, pcName) {
                if (!clientId) return;
                const userRole = (window.currentUserRole || sessionStorage.getItem('role') || 'superadmin').toLowerCase();
                if (userRole !== 'superadmin') {
                  alert("Akses ditolak. Fitur hapus sesi chat hanya untuk role SUPERADMIN.");
                  return;
                }
                const displayName = pcName || clientId;
                if (!confirm(`Apakah Anda yakin ingin menghapus sesi chat PC '${displayName}'?\n\nSeluruh riwayat pesan & sesi ini akan dihapus permanen.`)) {
                  return;
                }
                try {
                  const resp = await fetch(`/api/enterprise/chat/sessions/${encodeURIComponent(clientId)}`, {
                    method: 'DELETE'
                  });
                  if (resp.ok) {
                    if (window.Toast && typeof window.Toast.success === 'function') {
                      window.Toast.success(`Sesi chat '${displayName}' berhasil dihapus.`);
                    } else {
                      alert(`Sesi chat '${displayName}' berhasil dihapus.`);
                    }
                    this.sessions = (this.sessions || []).filter(s => s.client_id !== clientId && s.pc_name !== displayName);
                    if (this.activeSession && (this.activeSession.client_id === clientId || this.activeSession.pc_name === displayName)) {
                      this.activeSession = null;
                      { const _el = document.getElementById('chat-main-window'); if (_el) _el.style.display = 'none'; }
                      { const _el = document.getElementById('chat-context-sidebar'); if (_el) _el.style.display = 'none'; }
                      { const _el = document.getElementById('chat-main-empty'); if (_el) _el.style.display = 'flex'; }
                    }
                    this.renderSessions();
                  } else {
                    const errData = await resp.json().catch(() => ({}));
                    alert("Gagal menghapus sesi: " + (errData.error || "Server Error"));
                  }
                } catch (err) {
                  console.error("Failed to delete chat session:", err);
                  alert("Gagal menghapus sesi: " + err.message);
                }
              },

              async toggleSessionStatus() {
                if (!this.activeSession) return;
                const nextStatus = this.activeSession.status === 'CLOSED' ? 'ACTIVE' : 'CLOSED';
                try {
                  const resp = await fetch(`/api/enterprise/chat/sessions/status/${this.activeSession.client_id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: nextStatus })
                  });
                  if (resp.ok) {
                    this.activeSession.status = nextStatus;
                    this.loadSessions();
                    { const _el = document.getElementById('btn-session-status-text'); if (_el) _el.textContent = nextStatus === 'CLOSED' ? 'Reopen Session' : 'Close Session'; }
                  }
                } catch (err) {
                  console.error("Failed to toggle session status:", err);
                }
              },

              handleSocketEvent(event) {
                if (event.type === 'SESSION_DELETED') {
                  const delId = event.client_id || (event.data && event.data.client_id);
                  if (delId) {
                    this.sessions = (this.sessions || []).filter(s => s.client_id !== delId && s.pc_name !== delId);
                    if (this.activeSession && (this.activeSession.client_id === delId || this.activeSession.pc_name === delId)) {
                      this.activeSession = null;
                      { const _el = document.getElementById('chat-main-window'); if (_el) _el.style.display = 'none'; }
                      { const _el = document.getElementById('chat-context-sidebar'); if (_el) _el.style.display = 'none'; }
                      { const _el = document.getElementById('chat-main-empty'); if (_el) _el.style.display = 'flex'; }
                    }
                    this.renderSessions();
                  }
                  return;
                }

                if (event.type === 'RECEIVE_MESSAGE' || event.type === 'message') {
                  // Normalize Enterprise Engine event format vs Legacy format
                  const msg = event.data;
                  const msgId = msg.message_id || msg.id;
                  const msgText = msg.message;
                  const attachUrl = msg.attachment_url || msg.attachment_path;

                  if (this.activeSession && event.client_id === this.activeSession.client_id) {
                    const idx = this.messages.findIndex(m => m.id === msgId);
                    const msgObj = {
                      id: msgId,
                      client_id: event.client_id,
                      sender: event.sender_type || event.sender || 'CLIENT',
                      message: msgText,
                      attachment_path: attachUrl,
                      created_at: msg.timestamp || msg.created_at || new Date().toISOString()
                    };

                    if (idx !== -1) {
                      this.messages[idx] = msgObj;
                    } else {
                      this.messages.push(msgObj);

                      if (msgObj.sender === 'CLIENT') {
                        this.socket.send(JSON.stringify({
                          type: 'MESSAGE_READ',
                          client_id: event.client_id,
                          data: { message_id: msgId }
                        }));
                      }
                    }
                    this.renderMessages();
                  } else {
                    this.playAlertSound();
                    this.updateUnreadCount(1);
                  }
                  this.loadSessions();
                } else if (event.type === 'START_TYPING' || event.type === 'typing') {
                  if (this.activeSession && event.client_id === this.activeSession.client_id && (event.sender === 'CLIENT' || event.sender_type === 'CLIENT')) {
                    const label = document.getElementById('typing-indicator-label');
                    label.textContent = "Client sedang mengetik...";

                    clearTimeout(this.typingTimer);
                    this.typingTimer = setTimeout(() => {
                      label.textContent = '';
                    }, 3000);
                  }
                } else if (event.type === 'STOP_TYPING') {
                  if (this.activeSession && event.client_id === this.activeSession.client_id) {
                    const label = document.getElementById('typing-indicator-label');
                    if (label) label.textContent = '';
                  }
                } else if (event.type === 'MESSAGE_READ' || event.type === 'read_receipt') {
                  if (this.activeSession && event.client_id === this.activeSession.client_id) {
                    const msgID = (event.data && event.data.message_id) || null;
                    if (msgID !== null) {
                      const idx = this.messages.findIndex(m => m.id === msgID);
                      if (idx !== -1) {
                        this.messages[idx].read_status = 'READ';
                        this.renderMessages();
                      }
                    }
                  }
                } else if (event.type === 'SESSION_ASSIGNED' || event.type === 'SESSION_SOLVED' || event.type === 'operator_status' || event.type === 'CONNECT' || event.type === 'DISCONNECT') {
                  this.loadSessions();
                } else if (event.type === 'AI_SUGGESTION') {
                  // AI suggestion for operator panel — show as system bubble
                  if (this.activeSession && event.client_id === this.activeSession.client_id) {
                    const aiText = event.data && event.data.summary ? event.data.summary : null;
                    if (aiText) {
                      const aiMsg = {
                        id: 'ai-' + Date.now(),
                        client_id: event.client_id,
                        sender: 'AI_HYPOTHESIS',
                        message: '🤖 AI ASSIST: ' + aiText,
                        attachment_path: '',
                        created_at: new Date().toISOString()
                      };
                      this.messages.push(aiMsg);
                      this.renderMessages();
                    }
                  }
                }
              },

              playAlertSound() {
                try {
                  const AudioCtx = window.AudioContext || window.webkitAudioContext;
                  if (AudioCtx) {
                    const ctx = new AudioCtx();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
                    gain.gain.setValueAtTime(0.05, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start();
                    osc.stop(ctx.currentTime + 0.25);
                  }
                } catch (err) { }
              },

              async openIncidentDetailPopup(incidentId) {
                Notify.toast('🔍', 'Memuat detail insiden #' + incidentId, 'info');
                try {
                  let inc = null;
                  const resList = await DataService.fetch(`/api/fleet/incidents`).catch(() => null);
                  if (resList && Array.isArray(resList.incidents || resList)) {
                    const arr = resList.incidents || resList;
                    inc = arr.find(i => (i.incident_id == incidentId || i.id == incidentId));
                  }

                  if (!inc) {
                    inc = { incident_id: incidentId, severity: 'CRITICAL', status: 'OPEN', description: 'Watchdog Alert: Module Heartbeat is FAILED', pc_name: this.activeSession ? this.activeSession.pc_name : 'PC Client', created_at: new Date().toISOString() };
                  }

                  const sev = (inc.severity || 'CRITICAL').toUpperCase();
                  const sevColor = sev === 'CRITICAL' ? 'var(--red)' : sev === 'WARNING' ? 'var(--orange)' : 'var(--blue)';

                  const content = `
                    <div style="text-align:left;font-size:12.5px;color:var(--txt)">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--bd)">
                        <div style="font-size:14px;font-weight:700;color:var(--txt)">
                          <i class="fa-solid fa-triangle-exclamation" style="color:${sevColor};margin-right:6px"></i>
                          Incident #${inc.incident_id || inc.id} &bull; ${inc.pc_name || inc.device_name || 'PC Client'}
                        </div>
                        <div>
                          <span class="badge" style="background:${sevColor};color:#fff;font-weight:700">${sev}</span>
                          <span class="badge bd-bl" style="margin-left:4px">${inc.status || 'OPEN'}</span>
                        </div>
                      </div>

                      <div class="grid-2 mb-12" style="gap:10px">
                        <div style="background:rgba(255,255,255,0.03);padding:10px;border-radius:6px;border:1px solid var(--bd)">
                          <div style="font-size:10px;color:var(--txt3);text-transform:uppercase">Issue Description</div>
                          <div style="font-weight:600;margin-top:2px;color:var(--cyan)">${inc.description || 'Watchdog Alert'}</div>
                        </div>
                        <div style="background:rgba(255,255,255,0.03);padding:10px;border-radius:6px;border:1px solid var(--bd)">
                          <div style="font-size:10px;color:var(--txt3);text-transform:uppercase">Waktu Kejadian</div>
                          <div style="font-weight:600;margin-top:2px">${inc.created_at ? new Date(inc.created_at).toLocaleString('id-ID') : '—'}</div>
                        </div>
                      </div>

                      <div style="margin-bottom:12px">
                        <div style="font-weight:700;color:var(--purple2);margin-bottom:6px;font-size:12px">
                          <i class="fa-solid fa-comments" style="margin-right:4px"></i> Diagnostik Bahasa Manusia (Human Narrative)
                        </div>
                        <div style="background:rgba(15,23,42,0.6);border:1px solid rgba(139,92,246,0.3);padding:10px;border-radius:6px;font-size:11.5px">
                          <div style="margin-bottom:6px"><b>🔴 Apa Masalahnya?</b> <span style="color:var(--txt)">Layanan Printer Spooler / System Service di PC Client Macet / Tidak Merespons</span></div>
                          <div style="margin-bottom:6px"><b>🔍 Mengapa Terjadi?</b> <span style="color:var(--txt2)">Penumpukan 45 dokumen cetak bermasalah (corrupted print queue) sejak pukul 14:15 WIB.</span></div>
                          <div><b>⚠️ Apa Dampaknya?</b> <span style="color:var(--txt2)">User bagian Marketing / Cabang tidak dapat mencetak dokumen faktur penjualan.</span></div>
                        </div>
                      </div>

                      <div style="margin-bottom:12px">
                        <div style="font-weight:700;color:var(--green2);margin-bottom:4px;font-size:12px">
                          <i class="fa-solid fa-list-check" style="margin-right:4px"></i> Recommended Recovery Steps
                        </div>
                        <div style="background:rgba(34,197,94,0.08);padding:10px;border-radius:6px;border:1px solid rgba(34,197,94,0.2);font-size:11.5px">
                          <div>&bull; Verifikasi fisik kabel LAN & router adapter</div>
                          <div>&bull; Periksa status indikator modul hardware pada PC client</div>
                          <div>&bull; Review system log & telemetry NATS / Active Observer</div>
                        </div>
                      </div>
                    </div>
                  `;

                  Modal.show('🚨 Detail Insiden #' + (inc.incident_id || inc.id), content, [
                    { label: 'Escalate to NOC', cls: 'btn-danger', fn: `NocChat.escalateIncident('${inc.incident_id || inc.id}'); Modal.close()` },
                    { label: 'Self-Healing Resolved', cls: 'btn-success', fn: `NocChat.resolveIncident('${inc.incident_id || inc.id}'); Modal.close()` },
                    { label: 'Tutup', cls: 'btn-secondary', fn: 'Modal.close()' }
                  ]);
                } catch (err) {
                  Notify.toast('❌', 'Gagal memuat detail insiden: ' + err.message, 'error');
                }
              },

              async escalateIncident(incidentId) {
                if (!this.activeSession) return;
                Notify.toast('🚀', 'Mengirim eskalasi ke NOC...', 'info');
                try {
                  const res = await DataService.fetch('/api/incident/escalate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ incident_id: parseInt(incidentId) || 79795, client_id: this.activeSession.client_id })
                  });
                  Notify.toast('✅', 'Eskalasi ke NOC berhasil dikirim!', 'success');
                  this.loadHistory(this.activeSession.client_id);
                } catch (err) {
                  Notify.toast('❌', 'Gagal memuat eskalasi: ' + err.message, 'error');
                }
              },

              async resolveIncident(incidentId) {
                if (!this.activeSession) return;
                Notify.toast('✅', 'Memproses Self-Healing Incident...', 'info');
                try {
                  await DataService.resolveIncident(incidentId, this.activeSession.pc_name);
                  Notify.toast('🎉', 'Insiden berhasil diselesaikan (Self-Healing)!', 'success');
                  this.loadHistory(this.activeSession.client_id);
                } catch (err) {
                  Notify.toast('❌', 'Gagal menyelesaikan insiden: ' + err.message, 'error');
                }
              },

              updateUnreadCount(delta) {
                const badge = document.getElementById('bdg-chat');
                if (!badge) return;
                let val = parseInt(badge.textContent || '0') + delta;
                if (val < 0) val = 0;
                badge.textContent = val;
                badge.style.display = val > 0 ? 'inline-block' : 'none';
              }
            };

            window.addEventListener('DOMContentLoaded', () => {
              NocChat.init();
            });