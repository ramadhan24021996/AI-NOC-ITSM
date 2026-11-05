/* panels/learning-gate.js
 * Learning Gate Logs panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      learning_gate_logs: {
        _cachedLogs: [],
        async load() {
          const tbody = document.getElementById('learning-gate-logs-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Learning Gate Logs...</div></td></tr>';
          try {
            const logs = await DataService.fetch('/api/learning_gate_logs');
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

          const html = `
            <div id="learning-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
              <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
                <!-- Header -->
                <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(16,185,129,0.08)">
                  <div style="display:flex;align-items:center;gap:10px">
                    <div style="width:36px;height:36px;border-radius:8px;background:rgba(16,185,129,0.2);display:flex;align-items:center;justify-content:center;color:#10b981;font-size:18px">
                      <i class="fa-solid fa-graduation-cap"></i>
                    </div>
                    <div>
                      <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Audit Gerbang Pembelajaran Kontinu AI #${log.id}</h3>
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${log.incident_id || 'SYS'} · ${ts}</div>
                    </div>
                  </div>
                  <button onclick="document.getElementById('learning-log-modal-overlay').remove()" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
                </div>

                <!-- Body -->
                <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
                  
                  <!-- Grid Key Metrics -->
                  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-shield-cat" style="color:#10b981;margin-right:4px"></i>Status Keputusan Governance</div>
                      <div style="font-size:15px;font-weight:800;color:${isBlocked ? '#ef4444' : '#10b981'};margin-top:4px">
                        ${isBlocked ? '🛡️ DITOLAK FILTER KEAMANAN' : '✅ DISETUJUI UNTUK PEMBELAJARAN'}
                      </div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Cognitive Safety & Guardrail Filter</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-chart-line" style="color:#38bdf8;margin-right:4px"></i>Tingkat Kepercayaan Pembelajaran</div>
                      <div style="font-size:20px;font-weight:800;color:${confColor}">${conf}%</div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Evaluasi Konsensus Multi-LLM</div>
                    </div>
                  </div>

                  <!-- Event Name -->
                  <div style="background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:14px">
                    <div style="font-size:12px;font-weight:700;color:#38bdf8;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-bell"></i> Peristiwa / Anomali Terdeteksi (Detected Event)
                    </div>
                    <div style="font-size:13px;font-weight:600;color:#f8fafc">
                      ${eventTitle}
                    </div>
                  </div>

                  <!-- Reasoning Explanation -->
                  <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-diagram-project"></i> Alasan & Evaluasi Gerbang Kognitif (Learning Gate Reasoning)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #f59e0b">
                      ${reasoningText}
                    </div>
                  </div>

                </div>

                <!-- Footer -->
                <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
                  <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(${JSON.stringify(log).replace(/"/g, '&quot;')}));Notify.toast('📋 Copied','Log audit disalin ke clipboard','ok')" style="padding:6px 14px">
                    <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin JSON Audit
                  </button>
                  <button class="btn btn-primary btn-sm" onclick="document.getElementById('learning-log-modal-overlay').remove()" style="padding:6px 18px">
                    Tutup
                  </button>
                </div>
              </div>
            </div>
          `;
          document.body.insertAdjacentHTML('beforeend', html);
        }
      },


});
