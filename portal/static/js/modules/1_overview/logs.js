/* modules/1_overview/logs.js
 * Atomic Design — 3. Modules Layer (1_overview / logs)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["1_overview"] = window.Modules["1_overview"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      logs: {
        _busBound: false,
        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          bus.on('incident:status_changed', (data) => {
            if (!data || !window.LogStreamer) return;
            const st = String(data.status || 'IN_PROGRESS').toUpperCase();
            const lv = st === 'RESOLVED' ? 'OK' : (st === 'REJECTED' || st === 'CRITICAL') ? 'ERR' : 'INFO';
            window.LogStreamer.add(lv, 'ORCH', `[Incident #${data.incident_id || '?'}] Status transitioned to ${st}${data.approval_status ? ' (HITL: ' + data.approval_status + ')' : ''}`);
          });
          bus.on('incident:verified', (data) => {
            if (!data || !window.LogStreamer) return;
            window.LogStreamer.add('OK', 'AUDIT', `[Rule #6 Dual-Evidence Verified] Incident #${data.incident_id || '?'} verified & closed`);
          });
        },
        async load(silent = false) {
          this._bindBus();
          try {
            const limitEl = document.getElementById('log-limit-select');
            const limit = parseInt(limitEl?.value, 10) || (window.LogStreamer && window.LogStreamer._maxLogs) || 500;
            const logs = await (window.Services.Data || DataService).loadServerLogs(limit);
            if (logs && Array.isArray(logs) && window.LogStreamer) {
              window.LogStreamer.loadBulk(logs, false);
            }
          } catch (err) {
            console.error("Failed to load server logs:", err);
          }
          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.live_logs) {
            window.ActiveIntervals.live_logs = setInterval(() => {
              const panel = document.getElementById('p-logs');
              if (document.hidden || !panel || !panel.classList.contains('active')) return;
              if (window.LogStreamer && window.LogStreamer._paused) return;
              this.load(true);
            }, 15000);
          }
        }
      },

      smart_stream: {
        _data: [],
        _busBound: false,
        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          const reloadIfActive = () => {
            const p = document.getElementById('p-smart_stream');
            if (p && p.classList.contains('active')) this.load(true);
          };
          bus.on('incidents:loaded', reloadIfActive);
          bus.on('incident:status_changed', reloadIfActive);
          bus.on('incident:verified', reloadIfActive);
        },
        async load(silent = false) {
          this._bindBus();
          const container = document.getElementById('ss-feed-container');
          if (!container) return;
          if (!silent && this._data.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--txt3);"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px;margin-bottom:8px;color:var(--blue)"></i><div>Memuat Smart Incident Stream terstruktur bahasa manusia...</div></div>';
          }

          try {
            const [logs, fleet] = await Promise.all([
              (window.Services.Data || DataService).loadAIDecisionLogs(50).catch(() => []),
              (window.Services.Data || DataService).fetch('/api/fleet/admin/devices').catch(() => [])
            ]);

            const onlineMap = {};
            if (Array.isArray(fleet)) {
              fleet.forEach(d => {
                const name = (d.pc_name || d.name || d.hostname || '').toLowerCase();
                if (name) onlineMap[name] = d.status === 'ONLINE' || d.online === true;
              });
            }

            if (!logs || !Array.isArray(logs) || logs.length === 0) {
              this._data = [];
              this.updateKpis();
              container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--txt3);"><i class="fa-solid fa-circle-check" style="font-size:24px;margin-bottom:8px;color:var(--green2)"></i><div>Tidak ada insiden terdeteksi. Sistem berjalan normal.</div></div>';
              return;
            }

            this._data = logs.map(l => {
              const pcName = l.host || l.device_name || l.node_id || 'UNKNOWN-DEVICE';
              const pcKey = String(pcName).toLowerCase();
              const isOnline = onlineMap[pcKey] !== undefined ? onlineMap[pcKey] : false;
              const rawConf = parseFloat(l.confidence_score || 0);
              const confPct = Math.round(rawConf * (rawConf <= 1 ? 100 : 1));
              const isResolved = (l.final_decision || '').includes('RESOLVED') || (l.action_executed || '').includes('APPROVED');
              const isPending = (l.action_executed || '').includes('PENDING') || l.execution_mode === 'WAITING_APPROVAL';
              
              let statusTag = isResolved ? 'AUTO_RESOLVED' : isPending ? 'WAITING_APPROVAL' : 'PLAYBOOK_RUNNING';
              if (l.severity === 'CRITICAL') statusTag = 'FAILED';

              return {
                id: l.id || l.incident_id,
                incident_id: l.incident_id || l.id,
                pc_name: pcName,
                pc_online: isOnline,
                summary: l.first_hypothesis || 'Anomali Telemetri Terdeteksi pada ' + pcName,
                root_cause: l.root_cause || 'Anomali telemetri layanan terdeteksi oleh agen.',
                recommended_action: l.final_decision || l.action_executed || 'Evaluasi Playbook Remediasi',
                confidence: confPct,
                status: statusTag,
                severity: l.severity || (confPct > 90 ? 'HIGH' : 'MEDIUM'),
                timestamp: l.timestamp ? new Date(l.timestamp).toLocaleString('id-ID') : '—'
              };
            });

            this.updateKpis();
            this.render();
          } catch (e) {
            console.error("Failed to load Smart Incident Stream:", e);
            if (container && this._data.length === 0) {
              container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--red2)">Gagal terhubung ke AI Stream Engine: ' + _esc(e.message) + '</div>';
            }
          }
          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.smart_stream) {
            window.ActiveIntervals.smart_stream = setInterval(() => {
              const panel = document.getElementById('p-smart_stream');
              if (document.hidden || !panel || !panel.classList.contains('active')) return;
              this.load(true);
            }, 10000);
          }
        },

        updateKpis() {
          const total = this._data.length;
          const resolved = this._data.filter(d => d.status === 'AUTO_RESOLVED').length;
          const hitl = this._data.filter(d => d.status === 'WAITING_APPROVAL').length;
          const avgConf = total > 0 ? (this._data.reduce((a, b) => a + b.confidence, 0) / total).toFixed(1) + '%' : '0.0%';

          setEl('ss-kpi-total', total);
          setEl('ss-kpi-resolved', resolved);
          setEl('ss-kpi-hitl', hitl);
          setEl('ss-kpi-confidence', avgConf);
        },

        render() {
          const container = document.getElementById('ss-feed-container');
          if (!container) return;

          const searchQ = (document.getElementById('ss-search-inp')?.value || '').toLowerCase().trim();
          const statusF = document.getElementById('ss-filter-status')?.value || '';
          const deviceF = document.getElementById('ss-filter-device')?.value || '';

          const filtered = this._data.filter(item => {
            if (statusF && item.status !== statusF) return false;
            if (deviceF === 'ONLINE' && !item.pc_online) return false;
            if (deviceF === 'OFFLINE' && item.pc_online) return false;
            if (searchQ) {
              const nameM = item.pc_name.toLowerCase().includes(searchQ);
              const summaryM = item.summary.toLowerCase().includes(searchQ);
              const rootM = item.root_cause.toLowerCase().includes(searchQ);
              const actionM = item.recommended_action.toLowerCase().includes(searchQ);
              const statusM = item.status.toLowerCase().includes(searchQ);
              const devStatusM = item.pc_online ? 'online'.includes(searchQ) : 'offline'.includes(searchQ);
              if (!nameM && !summaryM && !rootM && !actionM && !statusM && !devStatusM) return false;
            }
            return true;
          });

          if (filtered.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:25px;color:var(--txt3);font-family:monospace;"><i class="fa-solid fa-filter" style="margin-right:6px"></i> Tidak ada insiden yang cocok dengan filter pencarian.</div>';
            return;
          }

          container.innerHTML = filtered.map(item => {
            const isOnline = item.pc_online;
            const deviceBadge = isOnline ? '<span class="tag tag-green" style="font-size:9.5px;">● ONLINE</span>' : '<span class="tag tag-gray" style="font-size:9.5px;">○ OFFLINE</span>';
            
            let statusBadge = '<span class="tag tag-blue">PLAYBOOK RUNNING</span>';
            if (item.status === 'AUTO_RESOLVED') statusBadge = '<span class="tag tag-green">✔ AUTO-RESOLVED</span>';
            else if (item.status === 'WAITING_APPROVAL') statusBadge = '<span class="tag tag-orange">⚡ WAITING HITL APPROVAL</span>';
            else if (item.status === 'FAILED') statusBadge = '<span class="tag tag-red">❌ CRITICAL / FAILED</span>';

            const sevBorder = item.severity === 'CRITICAL' ? 'var(--red)' : item.severity === 'HIGH' ? 'var(--orange)' : 'var(--blue)';

            return `
              <div style="background:rgba(15,23,42,0.65); border:1px solid var(--bd2); border-left:4px solid ${sevBorder}; border-radius:8px; padding:14px; box-shadow:0 4px 12px rgba(0,0,0,0.25);">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <b style="font-size:13px; color:var(--txt1);"><i class="fa-solid fa-desktop" style="color:var(--blue);margin-right:4px"></i> ${_esc(item.pc_name)}</b>
                    ${deviceBadge}
                    <span class="badge bd-bl" style="font-size:10px;">INC-${_esc(item.incident_id)}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:8px;">
                    ${statusBadge}
                    <span style="font-size:11px; color:var(--purple2); font-weight:600;"><i class="fa-solid fa-brain" style="margin-right:3px"></i> Conf: ${_esc(item.confidence)}%</span>
                    <span style="font-size:10.5px; color:var(--txt3);">${_esc(item.timestamp)}</span>
                  </div>
                </div>

                <div style="font-weight:600; font-size:12.5px; color:var(--txt1); margin-bottom:6px;">
                  🚨 ${_esc(item.summary)}
                </div>

                <div style="background:rgba(0,0,0,0.3); border-radius:6px; padding:8px 12px; margin-bottom:10px; font-size:11.5px; color:var(--txt2); border:1px solid rgba(255,255,255,0.05);">
                  <div style="margin-bottom:4px;"><b>Sebab Masalah:</b> <span style="color:var(--txt1);">${_esc(item.root_cause)}</span></div>
                  <div><b>Rekomendasi AI:</b> <code style="color:var(--cyan2);">${_esc(item.recommended_action)}</code></div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                  <div style="display:flex; gap:6px;">
                    <button class="btn btn-ghost btn-xs" onclick="Nav.go('rca');"><i class="fa-solid fa-magnifying-glass" style="margin-right:4px"></i>RCA 5-Why</button>
                    <button class="btn btn-ghost btn-xs" onclick="Nav.go('kgraph');"><i class="fa-solid fa-diagram-project" style="margin-right:4px"></i>Knowledge Graph</button>
                  </div>
                  ${item.status === 'WAITING_APPROVAL' ? `<button class="btn btn-success btn-xs" onclick="Nav.go('approval_queue');"><i class="fa-solid fa-check" style="margin-right:4px"></i>Approve Remediasi (HITL)</button>` : ''}
                </div>
              </div>
            `;
          }).join('');
        }
      },


});

window.Modules["1_overview"]["logs"] = window.Panels;
