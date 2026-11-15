/* modules/5_security_governance/learning-gate.js
 * Atomic Design — 3. Modules Layer (5_security_governance / learning-gate)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["5_security_governance"] = window.Modules["5_security_governance"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      learning_gate_logs: {
        _cachedLogs: [],
        async load() {
          const tbody = document.getElementById('learning-gate-logs-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Learning Gate Logs...</div></td></tr>';
          try {
            const logs = await (window.Services.Data || DataService).fetch('/api/learning_gate_logs');
            this._cachedLogs = logs || [];
            if (!logs || !Array.isArray(logs) || logs.length === 0) {
              tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Tidak Ada Learning Gate Log</td></tr>';
              return;
            }

            const translateEvent = (evt) => {
              if (!evt) return 'Anomali Telemetri Sistem';
              let e = String(evt).trim();
              if (e === 'UNKNOWN_OFFLINE' || e === 'OFFLINE') return 'Perangkat / Klien Offline (Terputus dari Jaringan)';
              if (e === 'HIGH_CPU' || e === 'CPU_CRITICAL') return 'Penggunaan Processor (CPU) Sangat Tinggi';
              if (e === 'RAM_LEAK' || e === 'MEMORY_FULL') return 'Alokasi Memori (RAM) Penuh / Leak';
              if (e === 'PRINTER_SPOOLER_STUCK') return 'Print Spooler Terhenti / Dokumen Macet';
              if (e === 'NETWORK_DISRUPTION') return 'Disrupsi Jalur Jaringan / Ping High RTO';
              return e;
            };

            const translateDecision = (dec) => {
              if (!dec) return '<span class="badge bd-bl" style="font-size:9.5px"><i class="fa-solid fa-magnifying-glass" style="margin-right:3px"></i> Dievaluasi</span>';
              let d = String(dec).toUpperCase();
              if (d.includes('BLOCKED')) {
                return '<span class="badge bd-rd" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-shield-cat" style="margin-right:3px"></i> Ditolak Filter Governance</span>';
              }
              if (d.includes('PASSED') || d.includes('ALLOWED') || d.includes('APPROVED')) {
                return '<span class="badge bd-gr" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-circle-check" style="margin-right:3px"></i> Disetujui untuk AI Learning</span>';
              }
              if (d.includes('PENDING')) {
                return '<span class="badge bd-or" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-clock" style="margin-right:3px"></i> Menunggu Verifikasi Operator</span>';
              }
              return `<span class="badge bd-pur" style="font-size:9.5px">${d}</span>`;
            };

            const translateReasoning = (rsn) => {
              if (!rsn) return 'Evaluasi keamanan kognitif otomatis oleh sistem AI Governance.';
              let r = String(rsn).trim();
              if (r.includes('[GOVERNANCE GATE]') || r.includes('Cognitive Safety Layer')) {
                return '[GERBANG KEAMANAN AI] Filter Gerbang Pembelajaran memblokir otomatis untuk mencegah kebocoran data atau eksekusi tak dikenal di lingkungan produksi.';
              }
              return r;
            };

            tbody.innerHTML = logs.map(l => {
              const conf = Math.round((l.confidence || 0) * (l.confidence <= 1 ? 100 : 1));
              const confColor = conf >= 70 ? 'var(--green2)' : conf >= 50 ? 'var(--orange2)' : 'var(--red2)';
              const eventText = translateEvent(l.event_id);
              const decisionHTML = translateDecision(l.action_executed);
              const reasoningText = translateReasoning(l.reasoning_dag);
              const ts = l.created_at ? new Date(l.created_at).toLocaleString('id-ID') : '—';

              return `<tr style="cursor:pointer" onclick="Panels.learning_gate_logs.showDetail(${l.id})" title="Klik untuk melihat detail Audit Gerbang Pembelajaran AI ini">
                <td><b>#${l.id}</b></td>
                <td><span class="badge bd-bl">INC-${l.incident_id || 'SYS'}</span></td>
                <td style="font-size:11px;font-weight:600;color:var(--txt1);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${eventText}">${eventText}</td>
                <td>${decisionHTML}</td>
                <td><b style="color:${confColor}">${conf}%</b></td>
                <td style="font-size:11px;color:var(--txt2);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${reasoningText}">${reasoningText}</td>
                <td style="font-size:11px;color:var(--txt3);white-space:nowrap">${ts}</td>
              </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat log: ${err.message}</td></tr>`;
          }
        },

        showDetail(logId) {
          const log = (this._cachedLogs || []).find(x => x.id === logId);
          if (!log) {
            Notify.toast('⚠️ Warning', 'Detail Learning Gate Log tidak ditemukan', 'warn');
            return;
          }
          const conf = Math.round((log.confidence || 0) * (log.confidence <= 1 ? 100 : 1));
          const ts = log.created_at ? new Date(log.created_at).toLocaleString('id-ID') : '—';
          const confColor = conf >= 70 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444';
          const isBlocked = (log.action_executed || '').toUpperCase().includes('BLOCKED');

          const eventTitle = log.event_id === 'UNKNOWN_OFFLINE' ? 'Perangkat / Klien Offline (Terputus dari Jaringan)' : (log.event_id || 'Anomali Telemetri Sistem');
          const reasoningText = (log.reasoning_dag || '').includes('[GOVERNANCE GATE]') || (log.reasoning_dag || '').includes('Cognitive Safety Layer')
            ? 'Filter Gerbang Pembelajaran AI memblokir otomatis sinyal anomali ini untuk mencegah regresi sistem atau eksekusi yang belum terverifikasi di Sandbox.'
            : (log.reasoning_dag || 'Evaluasi keamanan kognitif otomatis oleh sistem AI Governance.');

          const cardsMol = window.UI && window.UI.Molecules && window.UI.Molecules.JarvisCards;
          const html = cardsMol && typeof cardsMol.buildLearningGateDetailModal === 'function'
            ? cardsMol.buildLearningGateDetailModal(log, {
                conf,
                ts,
                confColor,
                isBlocked,
                eventTitle,
                reasoningText
              })
            : '';
          if (html) {
            document.body.insertAdjacentHTML('beforeend', html);
          }
        }
      },


});

window.Modules["5_security_governance"]["learning-gate"] = window.Panels;
