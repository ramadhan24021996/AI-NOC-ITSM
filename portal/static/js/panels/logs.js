/* panels/logs.js
 * Logs + Smart Stream panels
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      logs: {
        async load() {
          try {
            const logs = await DataService.loadServerLogs(100);
            if (logs && Array.isArray(logs)) {
              LogStreamer.loadBulk(logs);
            }
          } catch (err) {
            console.error("Failed to load server logs:", err);
          }
        }
      },

      smart_stream: {
        _data: [],
        async load() {
          const container = document.getElementById('ss-feed-container');
          if (!container) return;
          container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--txt3);"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px;margin-bottom:8px;color:var(--blue)"></i><div>Memuat Smart Incident Stream terstruktur bahasa manusia...</div></div>';

          try {
            const [logs, fleet] = await Promise.all([
              DataService.loadAIDecisionLogs(50).catch(() => []),
              DataService.fetch('/api/fleet/admin/devices').catch(() => [])
            ]);

            const onlineMap = {};
            if (Array.isArray(fleet)) {
              fleet.forEach(d => {
                const name = (d.pc_name || d.name || d.hostname || '').toLowerCase();
                if (name) onlineMap[name] = d.status === 'ONLINE' || d.online === true;
              });
            }

            if (!logs || !Array.isArray(logs) || logs.length === 0) {
              container.innerHTML = '<div style="text-align:center;padding:30px;color:var(--txt3);"><i class="fa-solid fa-circle-check" style="font-size:24px;margin-bottom:8px;color:var(--green2)"></i><div>Tidak ada insiden terdeteksi. Sistem berjalan normal.</div></div>';
              return;
            }

            this._data = logs.map(l => {
              const pcName = l.host || l.device_name || l.node_id || 'PC-MKT-NUC';
              const pcKey = pcName.toLowerCase();
              const isOnline = onlineMap[pcKey] !== undefined ? onlineMap[pcKey] : true;
              const confPct = Math.round((l.confidence_score || 0.96) * (l.confidence_score <= 1 ? 100 : 1));
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
                root_cause: l.root_cause || 'Deadlock alur kerja transaksi atau lonjakan beban kerja jaringan/memory.',
                recommended_action: l.final_decision || l.action_executed || 'Menjalankan Playbook Remediasi Otomatis',
                confidence: confPct,
                status: statusTag,
                severity: l.severity || (confPct > 90 ? 'HIGH' : 'MEDIUM'),
                timestamp: l.timestamp ? new Date(l.timestamp).toLocaleString('id-ID') : new Date().toLocaleString('id-ID')
              };
            });

            this.updateKpis();
            this.render();
          } catch (e) {
            console.error("Failed to load Smart Incident Stream:", e);
            if (container) container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--red2)">Gagal terhubung ke AI Stream Engine: ' + e.message + '</div>';
          }
        },

        updateKpis() {
          const total = this._data.length;
          const resolved = this._data.filter(d => d.status === 'AUTO_RESOLVED').length;
          const hitl = this._data.filter(d => d.status === 'WAITING_APPROVAL').length;
          const avgConf = total > 0 ? (this._data.reduce((a, b) => a + b.confidence, 0) / total).toFixed(1) + '%' : '96.5%';

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
                    <b style="font-size:13px; color:var(--txt1);"><i class="fa-solid fa-desktop" style="color:var(--blue);margin-right:4px"></i> ${item.pc_name}</b>
                    ${deviceBadge}
                    <span class="badge bd-bl" style="font-size:10px;">INC-${item.incident_id}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:8px;">
                    ${statusBadge}
                    <span style="font-size:11px; color:var(--purple2); font-weight:600;"><i class="fa-solid fa-brain" style="margin-right:3px"></i> Conf: ${item.confidence}%</span>
                    <span style="font-size:10.5px; color:var(--txt3);">${item.timestamp}</span>
                  </div>
                </div>

                <div style="font-weight:600; font-size:12.5px; color:var(--txt1); margin-bottom:6px;">
                  🚨 ${item.summary}
                </div>

                <div style="background:rgba(0,0,0,0.3); border-radius:6px; padding:8px 12px; margin-bottom:10px; font-size:11.5px; color:var(--txt2); border:1px solid rgba(255,255,255,0.05);">
                  <div style="margin-bottom:4px;"><b>Sebab Masalah:</b> <span style="color:var(--txt1);">${item.root_cause}</span></div>
                  <div><b>Rekomendasi AI:</b> <code style="color:var(--cyan2);">${item.recommended_action}</code></div>
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
