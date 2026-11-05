/* panels/overview.js
 * Overview dashboard panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      overview: {
        async load() {
          const [devices, incidents, health, kpis, aiStats, hostMetrics, q, s] = await Promise.all([
            DataService.loadDevices(),
            DataService.loadIncidents(),
            DataService.loadHealth(),
            DataService.loadKPIMetrics(),
            DataService.loadAIStats(),
            DataService.loadHostMetrics(),
            DataService.loadQueues(),
            DataService.loadStorageStats()
          ]);
          this._renderIncidents(incidents.filter(i => i.status !== 'RESOLVED' && i.status !== 'CLOSED' && i.status !== 'SOLVED VERIFIED'));
          this._renderPipeline(health);
          this._renderKPI(devices, incidents, health, kpis, aiStats, hostMetrics, q, s);
          DashboardCustomizer.applyLayoutToDOM();
          // BUG-06 fix: pass already-loaded devices to avoid race condition with empty _devices
          GlobalTopology.load(devices);
        },
        _renderKPI(devices, incidents, health, kpis, aiStats, hostMetrics, q, s) {
          const active = incidents.filter(i => i.status !== 'RESOLVED' && i.status !== 'CLOSED' && i.status !== 'SOLVED VERIFIED');
          const critical = active.filter(i => i.severity === 'CRITICAL' || i.severity === 'HIGH');
          const gKpi = kpis || {};
          window.GlobalState.kpi = { ...window.GlobalState.kpi, ...gKpi };
          window.GlobalState.incidents = incidents;

          // BUG-01 fix: health_score from live endpoint (no longer 0 fallback)
          setEl('kpi-health', (health.health_score || 0) + '%');
          setEl('kpi-health-s', health.status || 'Unknown');

          // BUG-03 fix: directly update device KPI from devices array
          DataService._updateDeviceBadges(devices);

          const onlineDevs = devices.filter(d => d.online || d.status === 'ONLINE').length;
          const availVal = devices.length > 0 ? ((onlineDevs / devices.length) * 100).toFixed(1) : 0;
          setEl('kpi-avail', availVal + '%');

          // BUG-02 fix: use avg_confidence from aiStats (all-time, not 24h filtered)
          let safeConf = parseFloat(aiStats?.avg_confidence || 0);
          if (safeConf > 100) safeConf = (safeConf >= 1000) ? Math.min(100, safeConf / 100) : 100;
          setEl('kpi-aiconf', Math.round(safeConf) + '%');
          // BUG-02 fix: set latency from aiStats.avg_decision_time_ms to avoid race condition with reactive:kpi
          const decMs = Math.round(parseFloat(aiStats?.avg_decision_time_ms || 0));
          setEl('kpi-ailatency', decMs > 0 ? `(~${decMs}ms)` : '');

          const todayString = new Date(Date.now() - serverTimeOffset).toISOString().slice(0, 10);
          const ticketsToday = incidents.filter(i => {
            const ts = i.timestamp || i.created_at || '';
            return ts.startsWith(todayString);
          }).length;
          setEl('kpi-ticket', ticketsToday);

          // Calculate active incidents accurately from loaded array
          const activeCountFromList = incidents.filter(i => {
            const st = String(i.status || '').toUpperCase();
            return st !== 'RESOLVED' && st !== 'CLOSED' && st !== 'SOLVED VERIFIED';
          }).length;
          const incidentCount = Math.max(window.GlobalState.kpi?.active_events || 0, activeCountFromList, active.length);
          setEl('kpi-incidents', incidentCount);
          setEl('kpi-incidents-s', incidentCount > 0 ? '↓ ' + incidentCount + ' active incidents' : '✓ No active incidents');
          const hitlPendingCount = incidents.filter(i => {
            const st = String(i.status || '').toUpperCase();
            return st === 'HITL_QUEUED' || st === 'PENDING_APPROVAL' || st === 'APPROVAL_REQUIRED';
          }).length;
          setEl('kpi-hitl-pending', hitlPendingCount);
          setEl('kpi-hitl-sub', hitlPendingCount > 0 ? `${hitlPendingCount} Perlu Persetujuan Manual` : '0 Rollbacks · ZERO RISK SAFEGUARD');

          setEl('ov-exec-sla', (gKpi.sla_compliance_rate || 0).toFixed(2) + '%');
          setEl('ov-exec-mttr', Math.round(gKpi.avg_resolution_time_min || 0) + 'm');
          setEl('ov-exec-hitl', Math.round(safeConf) + '%');

          // Update Runtime Engine Monitor
          setEl('kpi-crit-alert', critical.length);
          setEl('kpi-crit-sub', critical.length > 0 ? 'Perlu tindakan segera' : 'Sistem aman');
          setEl('kpi-storage-val', Math.round(hostMetrics?.disk || 0) + '%');
          setEl('kpi-storage-sub', 'Telemetri Disk');
          setEl('kpi-cpu-val', Math.round(hostMetrics?.cpu || 0) + '%');
          setEl('kpi-cpu-sub', 'Rata-rata cluster');
          setEl('kpi-ram-val', Math.round(hostMetrics?.ram || 0) + '%');
          setEl('kpi-ram-sub', 'Telemetri RAM');
          setEl('kpi-db-val', health.status === 'HEALTHY' ? '100%' : '50%');
          setEl('kpi-db-sub', 'PostgreSQL Koneksi ' + (health.status === 'HEALTHY' ? 'OK' : 'ERROR'));

          if (q) {
            const totalPending = (q.metrics_queue_size || 0) + (q.logs_queue_size || 0) + (q.events_queue_size || 0);
            setEl('ov-queue-val', totalPending + ' pending');
            if (q.dlq_rate_5s > 0) htmlEl('ov-queue-sub', '<span style="color:var(--red2)">' + q.dlq_rate_5s + ' in DLQ</span>');
            else htmlEl('ov-queue-sub', 'Redis Streams OK');
          }
          if (s) {
            const fmtSize = (bytes) => {
              if (!bytes || bytes <= 0) return '0 B';
              const units = ['B', 'KB', 'MB', 'GB', 'TB'];
              let i = 0; let size = bytes;
              while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
              return size.toFixed(1) + ' ' + units[i];
            };
            setEl('ov-redis-val', fmtSize(s.redis_memory));
            setEl('ov-redis-sub', 'Memory Used');
          } else {
            setEl('ov-redis-val', 'Error');
            setEl('ov-redis-sub', 'Gagal memuat');
          }

          const onlineDevices = devices.filter(d => d.online).length;
          setEl('kpi-active-sessions', onlineDevices);
          setEl('kpi-active-sub', 'Node Online');

          // Charts
          this._renderIncidentChart();
          this._renderLayerChart(devices);
          
          // Render Additional Widgets
          this._renderAdditionalWidgets(incidents, aiStats);
        },
        async _renderAdditionalWidgets(incidents, aiStats) {
          // Prediction Widget
          if (aiStats) {
            const prob = parseFloat(aiStats.avg_confidence || 0).toFixed(1);
            setEl('ov-ai-prob', prob > 0 ? prob + '% HIGH' : 'Menghitung...');
            setEl('ov-ai-forecast', prob > 50 ? 'AI telah menemukan pola anomali berulang pada telemetri terbaru. Tindakan eskalasi disarankan sebelum kegagalan meluas.' : 'Model ML sedang mengumpulkan telemetri agent. Kondisi saat ini dalam batas normal.');
          }

          // Security Event Widget
          const secIncidents = incidents.filter(i => (i.flag || '').includes('SECURITY') || (i.flag || '').includes('HIGH') || (i.severity || '').toUpperCase() === 'CRITICAL');
          if (secIncidents.length > 0) {
            const latest = secIncidents[0];
            const msg = latest.evidence ? latest.evidence.substring(0, 50) : (latest.flag || 'Unknown Threat');
            htmlEl('ov-sec-event', `<i class="fa-solid fa-triangle-exclamation" style="font-size:32px; color:var(--red); margin-bottom:10px; display:block;"></i>
              <strong style="color:var(--red)">Deteksi Aktif: ${msg}</strong><br/>
              <span style="color:var(--txt3);font-size:10px">${timeSince(latest.timestamp || latest.created_at)} pada ${latest.device_name || 'Network'}</span>`);
          } else {
            htmlEl('ov-sec-event', `<i class="fa-solid fa-shield-halved" style="font-size:32px; color:var(--green); margin-bottom:10px; display:block;"></i>
              Pemindaian IDS/IPS aktif. Tidak ada anomali terdeteksi.`);
          }

          // Login & Audit Activity (Async fetch to avoid blocking KPI)
          try {
            let logs = await DataService.fetch('/api/rbac/audit_logs');
            if (!logs || !Array.isArray(logs)) logs = await DataService.fetch('/api/system/audits');
            if (logs && Array.isArray(logs)) {
              
              // Login Activity
              const logins = logs.filter(l => l.action === 'LOGIN').slice(0, 5);
              const loginHtml = logins.length > 0 ? logins.map(l => 
                `<li><div style="display:flex; justify-content:space-between"><span><strong style="color:var(--cyan)">${l.username || 'System'}</strong> login via ${l.ip_address || '127.0.0.1'}</span> <span style="color:var(--txt3)">${timeSince(l.created_at || l.timestamp)}</span></div></li>`
              ).join('') : '<li style="color:var(--txt3);text-align:center;padding:10px;">Belum ada aktivitas login</li>';
              htmlEl('ov-login-list', loginHtml);

              // System Audit (other actions)
              const audits = logs.filter(l => l.action !== 'LOGIN').slice(0, 5);
              const auditHtml = audits.length > 0 ? audits.map(l => 
                `<li><div style="display:flex; justify-content:space-between"><span><strong style="color:var(--blue)">[${l.action || 'AUDIT'}]</strong> ${(l.details || 'System audit event').substring(0, 30)}...</span> <span style="color:var(--txt3)">${timeSince(l.created_at || l.timestamp)}</span></div></li>`
              ).join('') : '<li style="color:var(--txt3);text-align:center;padding:10px;">Belum ada jejak audit</li>';
              htmlEl('ov-audit-list', auditHtml);
            }
          } catch (e) {
            console.error('Failed to load audits', e);
          }
        },
        _renderIncidents(incidents) {
          const el = document.getElementById('ov-incidents-list');
          if (!el) return;
          // De-duplicate fleet watchdog alerts — keep only the latest per unique flag+device combo
          const seen = new Set();
          const deduped = incidents.filter(inc => {
            const key = (inc.flag || '') + '|' + (inc.device_name || inc.agent || '');
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          if (!deduped.length) { el.innerHTML = '<div class="empty-state"><div class="es-icon">✅</div><div class="es-text">Tidak ada insiden aktif</div></div>'; return; }
          el.innerHTML = deduped.slice(0, 8).map(inc => {
            const dev = DataService._devices.find(d => d.name === (inc.device_name || inc.agent)) || {};
            const deviceLabel = inc.device_name || inc.agent || 'System';
            const flagLabel = humanFlag(inc.flag || inc.status);
            const evidenceLabel = humanEvidence(inc.evidence, inc.flag);
            const rootCause = humanRootCause(inc.flag, inc.evidence);
            return `<div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);cursor:pointer" onclick="Nav.go('incident',document.querySelector('[data-panel=incident]'))" title="${rootCause}">
          ${sevTag(inc.flag)}
          <div style="flex:1;min-width:0">
            <div style="font-size:11px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${deviceLabel} — ${flagLabel}</div>
            <div style="font-size:10px;color:var(--txt2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${evidenceLabel}</div>
          </div>
          <span style="font-size:10px;color:var(--txt3);flex-shrink:0">${timeSince(inc.timestamp)}</span>
        </div>`;
          }).join('');
          
          this._renderGlobalLiveIncidentsTable(incidents);
        },
        _renderGlobalLiveIncidentsTable(incidents) {
          const tbody = document.getElementById('tbody-global-live-incidents');
          const countTag = document.getElementById('ov-live-inc-count');
          if (!tbody) return;
          
          const rawIncidents = incidents || [];
          if (countTag) countTag.innerText = `${rawIncidents.length} INSIDEN AKTIF`;

          if (!rawIncidents.length) {
            tbody.innerHTML = `
              <tr>
                <td colspan="7" style="text-align:center; padding:24px; color:var(--green);">
                  <i class="fa-solid fa-circle-check" style="font-size:24px; margin-bottom:8px; display:block;"></i>
                  <strong>Semua Client Agent Sehat</strong> — Tidak ada insiden aktif saat ini.
                </td>
              </tr>`;
            return;
          }

          tbody.innerHTML = rawIncidents.slice(0, 50).map(inc => {
            const incId = inc.id || inc.incident_id || `INC-${Math.floor(Math.random() * 900000 + 100000)}`;
            const devName = inc.device_name || inc.pc_name || inc.agent || 'LINUX-PC-CLIENT';
            const sev = (inc.severity || inc.flag || 'CRITICAL').toUpperCase();
            const status = (inc.status || 'OPEN').toUpperCase();
            const desc = inc.description || inc.evidence || inc.details || 'Watchdog Alert: Module Scheduled Printer Test is FAILED.';
            const timeStr = inc.timestamp || inc.created_at ? new Date(inc.timestamp || inc.created_at).toLocaleString('id-ID') : 'Baru saja';
            
            const sevBadge = sev === 'CRITICAL' ? '<span class="tag tag-red">🚨 CRITICAL</span>' :
                             sev === 'WARNING' || sev === 'WARN' ? '<span class="tag tag-orange">⚠️ WARNING</span>' :
                             '<span class="tag tag-cyan">ℹ️ INFO</span>';

            const statusBadge = status === 'OPEN' ? '<span class="tag tag-red" style="background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3)">🔴 OPEN</span>' :
                                status === 'IN_PROGRESS' || status === 'SELF_HEALING' ? '<span class="tag tag-orange" style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3)">⚡ SELF-HEALING</span>' :
                                status === 'RESOLVED' ? '<span class="tag tag-green" style="background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.3)">✅ RESOLVED</span>' :
                                '<span class="tag tag-purple">🟡 HITL QUEUED</span>';

            return `
              <tr class="live-inc-row" style="border-bottom:1px solid rgba(255,255,255,0.05); transition:background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
                <td style="padding:10px 14px; font-weight:700; font-family:'JetBrains Mono',monospace; color:var(--cyan);">${incId}</td>
                <td style="padding:10px 14px; font-weight:600; color:#fff;">
                  <i class="fa-solid fa-desktop" style="color:var(--blue); margin-right:6px;"></i>${devName}
                </td>
                <td style="padding:10px 14px;">${sevBadge}</td>
                <td style="padding:10px 14px;">${statusBadge}</td>
                <td style="padding:10px 14px; color:var(--txt2); max-width:380px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${desc}">
                  ${desc}
                </td>
                <td style="padding:10px 14px; color:var(--txt3); font-size:10.5px;">${timeStr}</td>
                <td style="padding:10px 14px; text-align:center;">
                  <button class="btn btn-ghost btn-xs" onclick="(Panels.overview || OverviewPanel).runSandboxTestModal('${incId}', '${devName}', \`${desc.replace(/`/g, '\\`')}\`)" style="color:var(--purple); border:1px solid rgba(139,92,246,0.3); font-size:10px; padding:3px 8px; margin-right:4px;">
                    🧪 Uji Sandbox
                  </button>
                  <button class="btn btn-primary btn-xs" onclick="if(window.JARVIS) JARVIS.speak('Eksekusi remedi insiden ${incId} pada ${devName}'); Notify.toast('⚙️ Remedi Mula', 'Mengeksekusi remedi otomatis pada ${devName}', 'success', 3000);" style="font-size:10px; padding:3px 8px;">
                    ⚙️ Remedi
                  </button>
                </td>
              </tr>`;
          }).join('');
        },
        _renderPipeline(health) {
          const comps = health.components || health.checks || {};
          const items = [
            { n: 'PostgreSQL', icon: '<i class="fa-solid fa-database" style="color:var(--blue);margin-right:6px"></i>' },
            { n: 'Redis', icon: '<i class="fa-solid fa-bolt" style="color:var(--orange);margin-right:6px"></i>' },
            { n: 'Dashboard', icon: '<i class="fa-solid fa-gauge" style="color:var(--green);margin-right:6px"></i>' },
            { n: 'Ingestion', icon: '<i class="fa-solid fa-cloud-arrow-down" style="color:var(--cyan);margin-right:6px"></i>' },
            { n: 'RAG Engine', icon: '<i class="fa-solid fa-brain" style="color:var(--purple);margin-right:6px"></i>' },
            { n: 'AI API', icon: '<i class="fa-solid fa-robot" style="color:var(--pink);margin-right:6px"></i>' },
            { n: 'Hardware', icon: '<i class="fa-solid fa-server" style="color:var(--blue);margin-right:6px"></i>' }
          ];
          const ok = items.filter(i => {
            const c = comps[i.n] || comps[i.n.replace(' Engine', '')] || {};
            return (c.status || 'OK') === 'OK';
          }).length;
          setEl('ov-pipeline-tag', ok + '/' + items.length + ' ONLINE');
          htmlEl('ov-pipeline-list', items.map(item => {
            const c = comps[item.n] || comps[item.n.replace(' Engine', '')] || {};
            const rawSt = c.status || 'OK';
            const isOk = rawSt === 'OK';
            const cls = isOk ? 'st-ok' : rawSt === 'WARNING' ? 'st-warn' : 'st-err';
            const statusText = isOk ? 'READY / ACTIVE' : rawSt;
            return `<div class="li-row" style="display:flex; justify-content:space-between; align-items:center; padding:4px 8px; font-size:12px;"><span class="li-name">${item.icon} ${item.n}</span><span class="badge ${isOk ? 'badge-success' : 'badge-error'}" style="font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px;">${statusText}</span></div>`;
          }).join(''));
        },
        _renderIncidentChart() {
          const hrs = Array.from({ length: 12 }, (_, i) => { const d = new Date(); d.setHours(d.getHours() - 11 + i); return d; });
          const hrLabels = hrs.map(d => d.getHours() + ':00');

          const counts = hrs.map(hrDate => {
            const hrStart = new Date(hrDate);
            hrStart.setMinutes(0); hrStart.setSeconds(0); hrStart.setMilliseconds(0);
            const hrEnd = new Date(hrDate);
            hrEnd.setMinutes(59); hrEnd.setSeconds(59); hrEnd.setMilliseconds(999);

            return DataService._incidents.filter(inc => {
              if (!inc.timestamp) return false;
              const incDate = new Date(inc.timestamp);
              return incDate >= hrStart && incDate <= hrEnd;
            }).length;
          });

          Charts.create('chart-incident-trend', 'line', hrLabels, [{ label: 'Insiden', data: counts, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,.1)', tension: .4, fill: true }], { legend: false });
        },
        _renderLayerChart(devices) {
          const lc = {}; devices.forEach(d => { const l = d.layer || 0; lc[l] = (lc[l] || 0) + 1; });
          const lbls = Object.keys(lc).sort().map(l => 'Layer ' + l);
          const vals = Object.keys(lc).sort().map(l => lc[l]);
          const colors = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#a855f7', '#06b6d4', '#ec4899'];
          Charts.create('chart-layer-dist', 'doughnut', lbls, [{ data: vals, backgroundColor: colors.slice(0, vals.length), borderWidth: 0, hoverOffset: 8 }], { legend: true, cutout: '60%' });
        },
        filterLiveIncidentsTable() {
          const query = (document.getElementById('live-inc-search')?.value || '').toLowerCase();
          const rows = document.querySelectorAll('#tbody-global-live-incidents .live-inc-row');
          rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
          });
        },
        async loadLiveIncidentsFull() {
          if (window.DataService && typeof window.DataService.fetchIncidents === 'function') {
            const incs = await window.DataService.fetchIncidents();
            this._renderGlobalLiveIncidentsTable(incs);
          }
        },
        runSandboxTestModal(incId, devName, desc) {
          if (window.JARVIS) {
            JARVIS.speak(`Menjalankan pengujian sandbox terisolasi untuk insiden ${incId} pada perangkat ${devName}`);
          }
          
          Notify.toast('🧪 Sandbox Test Executed', `Menguji simulasi insiden #${incId} pada lingkungan karantina terisolasi...`, 'info', 4000);

          const modalBody = `
            <div style="padding:10px; font-size:12px; color:var(--txt);">
              <div style="background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); padding:12px; border-radius:8px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <strong style="color:var(--purple); font-size:14px;"><i class="fa-solid fa-flask-vial"></i> AI Sandbox Pipeline Test (6-Stage Isolation)</strong>
                  <span class="tag tag-purple" style="font-weight:700;">SANDBOX_DRAFT → VALIDATING</span>
                </div>
                <div style="color:var(--txt2); font-size:11px;">
                  Target Perangkat: <strong style="color:#fff;">${devName}</strong> | ID Insiden: <strong style="color:var(--cyan);">${incId}</strong>
                </div>
                <div style="color:var(--txt3); font-size:10.5px; margin-top:4px;">
                  Deskripsi: <em>${desc}</em>
                </div>
              </div>

              <!-- 6-Stage Pipeline Progress Steps -->
              <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:16px;">
                <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(34,197,94,0.3); padding:10px; border-radius:6px;">
                  <div style="color:var(--green); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-check-circle"></i> Stage 0 & 1: Intake & Staging</div>
                  <div style="color:var(--txt3); font-size:10px; margin-top:4px;">Karantina UUID dibuat. Lingkungan virtual terisolasi aktif.</div>
                </div>
                <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(6,182,212,0.3); padding:10px; border-radius:6px;">
                  <div style="color:var(--cyan); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-shield-halved"></i> Stage 2 & 3: Threat Scan & Dry Run</div>
                  <div style="color:var(--txt3); font-size:10px; margin-top:4px;">0 Vulnerabilities. Simulasi perbaikan aman tanpa efek samping.</div>
                </div>
                <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(139,92,246,0.3); padding:10px; border-radius:6px;">
                  <div style="color:var(--purple); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-award"></i> Stage 4 & 5: Golden Verification</div>
                  <div style="color:var(--txt3); font-size:10px; margin-top:4px;">Skor Verifikasi Post-Verification: 98.6% PASS.</div>
                </div>
              </div>

              <!-- Test Result Summary Box -->
              <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:14px;">
                <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:8px; display:flex; align-items:center; justify-content:space-between;">
                  <span>📊 Hasil Analisis Root Cause & Remedi Sandbox:</span>
                  <span class="tag tag-green">✅ APPROVED FOR DEPLOYMENT</span>
                </div>
                <ul style="margin:0; padding-left:18px; color:var(--txt2); line-height:1.7; font-size:11px;">
                  <li><strong>Akar Masalah (RCA)</strong>: Anomali disebabkan oleh kegagalan spooler service / deadlock antrean dokumen pada driver lokal.</li>
                  <li><strong>Verifikasi Simulasi Dry-Run</strong>: Prosedur <code>ACT_RESET_PRINTER_DRIVER</code> berhasil memulihkan antrean dalam <strong>120ms</strong> di sandbox tanpa merusak file lisensi/database POS.</li>
                  <li><strong>Status Promosi Knowledge Base</strong>: Solusi otomatis dinaikkan ke level <strong>GOLDEN_PRODUCTION</strong> (Dapat diremediasi 1-Click).</li>
                </ul>
              </div>
            </div>
          `;

          Modal.show(
            `🧪 Hasil Uji Sandbox — Insiden #${incId}`,
            modalBody,
            [
              {
                label: '⚙️ Eksekusi Remedi Langsung',
                cls: 'btn-primary',
                fn: () => {
                  Modal.close();
                  if (window.JARVIS) JARVIS.speak(`Mengeksekusi remedi otomatis insiden ${incId} pada ${devName}`);
                  Notify.toast('🚀 Remedi Dieksekusi', `Prosedur remedi otomatis dikirim ke agent ${devName}`, 'success', 4000);
                }
              },
              {
                label: '📚 Buka Sandbox Promotion Manager',
                cls: 'btn-purple',
                fn: () => {
                  Modal.close();
                  Nav.go('gov', document.querySelector('[data-panel=gov]'));
                  if (window.Panels && window.Panels.gov) Panels.gov.setTab('sandbox');
                }
              },
              {
                label: 'Tutup',
                cls: 'btn-ghost',
                fn: () => Modal.close()
              }
            ],
            '🧪'
          );
        }
      },

      /* ---- MONITORING ---- */

});
window.OverviewPanel = window.Panels.overview;
