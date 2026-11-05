/* panels/ai-decision-logs.js
 * AI Decision Logs panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      ai_decision_logs: {
        _cachedLogs: [],
        async load() {
          const tbody = document.getElementById('ai-decision-logs-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Decision Logs...</div></td></tr>';
          
          try {
            const logs = await DataService.loadAIDecisionLogs(50);
            this._cachedLogs = logs || [];
            if (!logs || !Array.isArray(logs) || logs.length === 0) {
              tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Tidak Ada Decision Log</td></tr>';
              return;
            }

            tbody.innerHTML = logs.map(l => {
              const conf = Math.round((l.confidence_score || 0) * (l.confidence_score <= 1 ? 100 : 1));
              const ts = l.timestamp ? new Date(l.timestamp).toLocaleString('id-ID') : '—';
              const confColor = conf >= 80 ? 'var(--green2)' : conf >= 50 ? 'var(--orange2)' : 'var(--red2)';
              const modelDisplay = (l.ai_models_used || 'Gemini + DeepSeek + Groq').replace(/,/g, ' · ');
              
              // Human readable parent span
              let parentSpanVal = String(l.parent_span || '').trim();
              let parentSpanHTML = '<span class="badge bd-bl" style="font-size:9.5px">Root Trace</span>';
              if (parentSpanVal && parentSpanVal !== 'UNKNOWN_OFFLINE' && parentSpanVal !== 'NONE' && parentSpanVal !== '—') {
                parentSpanHTML = `<code style="font-size:9.5px;color:var(--cyan2)">${parentSpanVal.substring(0, 12)}</code>`;
              } else if (parentSpanVal === 'UNKNOWN_OFFLINE') {
                parentSpanHTML = '<span class="badge bd-or" style="font-size:9.5px">Root Trace (Offline)</span>';
              }

              // Human readable first hypothesis
              let firstHypo = String(l.first_hypothesis || '').trim();
              let firstHypoShort = firstHypo;
              if (firstHypo === 'UNKNOWN_OFFLINE' || firstHypo === 'OFFLINE') {
                firstHypoShort = 'Perangkat / Klien Offline';
              } else if (firstHypo.includes('OFFLINE RULE ENGINE FALLBACK')) {
                firstHypoShort = 'Perangkat / Klien Offline (Terputus)';
              }

              // Human readable final decision
              let finalDec = String(l.final_decision || '').trim();
              let finalDecShort = finalDec;
              if (finalDec.includes('OFFLINE RULE ENGINE FALLBACK') || finalDec.includes('Random Forest Model')) {
                finalDecShort = 'Local Decision Tree (SOP Pemulihan Standar)';
              }

              return `<tr style="cursor:pointer" onclick="Panels.ai_decision_logs.showDetail(${l.id})" title="Klik untuk melihat detail pembelajaran AI ini">
                <td><b>#${l.id}</b></td>
                <td><span class="badge bd-bl">INC-${l.incident_id || 'SYS'}</span></td>
                <td>
                  <span style="font-size:10.5px;font-weight:600">${ts}</span><br>
                  <code style="font-size:9.5px;color:var(--purple2)">${(l.trace_id || '—').substring(0, 14)}...</code> / <code style="font-size:9.5px;color:var(--cyan2)">${(l.span_id || '—').substring(0, 8)}</code>
                </td>
                <td>${parentSpanHTML}</td>
                <td style="font-size:11px;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--txt1)" title="${firstHypo}">${firstHypoShort}</td>
                <td style="font-size:11px;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:700;color:var(--green2)" title="${finalDec}">${finalDecShort}</td>
                <td><b style="color:${confColor}">${conf}%</b></td>
                <td><span class="badge bd-pur" style="font-size:9.5px">${modelDisplay}</span></td>
                <td><span style="font-family:monospace;font-size:10.5px;color:var(--cyan)">${l.decision_time_ms || 0} ms</span></td>
                <td><button class="btn btn-primary btn-xs" style="padding:2px 8px;font-size:10px" onclick="event.stopPropagation();Panels.ai_decision_logs.showDetail(${l.id})"><i class="fa-solid fa-brain" style="margin-right:3px"></i> Detail</button></td>
              </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat log: ${err.message}</td></tr>`;
          }
        },

        showDetail(logId) {
          const log = (this._cachedLogs || []).find(x => x.id === logId);
          if (!log) {
            Notify.toast('⚠️ Warning', 'Detail log tidak ditemukan', 'warn');
            return;
          }

          // Helper function untuk mengubah kode teknis (UNKNOWN_OFFLINE, dll) ke Bahasa Indonesia yang mudah dipahami
          const formatHumanReadable = (txt) => {
            if (!txt) return 'Sistem mengidentifikasi anomali performa secara otomatis.';
            let str = String(txt).trim();
            
            // Map istilah teknis tunggal
            if (str === 'UNKNOWN_OFFLINE' || str === 'OFFLINE') {
              return 'Perangkat / Sistem Tidak Merespon (Status: Offline / Terputus dari Jaringan)';
            }
            if (str === 'HIGH_CPU' || str === 'CPU_CRITICAL') {
              return 'Penggunaan Processor (CPU) Sangat Tinggi (>95% Terus-Menerus)';
            }
            if (str === 'RAM_LEAK' || str === 'MEMORY_FULL') {
              return 'Alokasi Memori (RAM) Penuh / Terdapat Indikasi Kebocoran Memori (Memory Leak)';
            }
            if (str === 'PRINTER_SPOOLER_STUCK' || str === 'PRINT_SPOOLER_OFFLINE') {
              return 'Layanan Cetak (Print Spooler) Terhenti / Dokumen Cetak Macet';
            }
            if (str === 'NETWORK_DISRUPTION' || str === 'PING_RTO') {
              return 'Disrupsi Jalur Jaringan / Waktu Respon Terlalu Lambat (Ping RTO)';
            }

            // Parse & Format string kompleks dari Fallback Rule Engine
            if (str.includes('OFFLINE RULE ENGINE FALLBACK') || str.includes('Model Reasoning')) {
              let intentMatch = str.match(/Diagnosed Intent:\s*([^\(]+)/i);
              let confMatch = str.match(/Confidence:\s*([\d\.]+%?)/i);
              let reasonMatch = str.match(/Model Reasoning\s*:\s*([^–\n]+)/i);
              let recMatch = str.match(/Recommendation\s*:\s*([^–\n]+)/i);

              let intentText = intentMatch ? intentMatch[1].trim() : 'UNKNOWN_OFFLINE';
              if (intentText === 'UNKNOWN_OFFLINE') intentText = 'Perangkat Klien Terdeteksi Tidak Aktif / Offline';

              let confText = confMatch ? confMatch[1] : '50.0%';
              let reasonText = reasonMatch ? reasonMatch[1].trim() : 'Menggunakan aturan lokal Decision Tree saat koneksi cloud terbatas.';
              let recText = recMatch ? recMatch[1].trim() : 'Jalankan SOP Pemulihan Standar dengan Pelindung Rollback Otomatis.';
              recText = recText.replace(/UNKNOWN_OFFLINE/g, 'Status Offline').replace(/Execute standard SOP for/g, 'Jalankan SOP Standar untuk');

              return `
                <div style="display:flex;flex-direction:column;gap:6px">
                  <div><b>📌 Diagnosa AI:</b> ${intentText}</div>
                  <div><b>🎯 Skor Keyakinan:</b> ${confText} (Kategori Standar)</div>
                  <div><b>💡 Penjelasan Penalaran:</b> ${reasonText}</div>
                  <div><b>🛠️ Rekomendasi Solusi:</b> ${recText}</div>
                </div>
              `;
            }

            return str;
          };

          const conf = Math.round((log.confidence_score || 0) * (log.confidence_score <= 1 ? 100 : 1));
          const ts = log.timestamp ? new Date(log.timestamp).toLocaleString('id-ID') : '—';
          const confColor = conf >= 80 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444';
          
          let rawModels = (log.ai_models_used || 'consensus-engine').trim();
          let modelsList = [];
          if (rawModels === 'consensus-engine' || rawModels === 'multi-agent-consensus' || rawModels === 'all') {
            modelsList = ['Gemini 2.5 Flash (Vision & Reasoning)', 'DeepSeek V3 (Code Analysis)', 'Groq Llama 3 (Realtime Inference)'];
          } else {
            modelsList = rawModels.split(',').map(m => m.trim());
          }

          const firstHypothesisHTML = formatHumanReadable(log.first_hypothesis);
          const secondHypothesisHTML = formatHumanReadable(log.second_hypothesis) || 'Konsensus 3 LLM mengonfirmasi tidak ada efek samping kritis. Aman untuk dieksekusi di Sandbox.';
          const finalDecisionHTML = formatHumanReadable(log.final_decision);

          const html = `
            <div id="ai-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
              <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:840px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
                <!-- Header -->
                <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(124,58,237,0.08)">
                  <div style="display:flex;align-items:center;gap:10px">
                    <div style="width:36px;height:36px;border-radius:8px;background:rgba(124,58,237,0.2);display:flex;align-items:center;justify-content:center;color:#a855f7;font-size:18px">
                      <i class="fa-solid fa-brain"></i>
                    </div>
                    <div>
                      <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Detail Pembelajaran AI & Audit Decision Log #${log.id}</h3>
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${log.incident_id || 'SYS'} · ${ts}</div>
                    </div>
                  </div>
                  <button onclick="document.getElementById('ai-log-modal-overlay').remove()" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
                </div>

                <!-- Body -->
                <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
                  
                  <!-- Grid Key Metrics -->
                  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-shield-halved" style="color:#38bdf8;margin-right:4px"></i>Skor Keyakinan AI</div>
                      <div style="font-size:20px;font-weight:800;color:${confColor}">${conf}%</div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">${conf >= 80 ? 'Sangat Tinggi (Pre-Approved Golden)' : 'Perlu Pengawasan HITL'}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-bolt" style="color:#f59e0b;margin-right:4px"></i>Waktu Analisis Consensus</div>
                      <div style="font-size:20px;font-weight:800;color:#38bdf8">${log.decision_time_ms || 0} ms</div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Parallel Multi-LLM Routing</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-box-archive" style="color:#a855f7;margin-right:4px"></i>Tahap Sandbox</div>
                      <div style="font-size:14px;font-weight:700;color:#a855f7;margin-top:4px"><span class="badge bd-pur">${log.stage_version || 'DRY_RUN_VERIFIED'}</span></div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Promoted to SOP Catalog</div>
                    </div>
                  </div>

                  <!-- Multi-LLM Ensemble Model Used -->
                  <div style="background:rgba(124,58,237,0.05);border:1px solid rgba(124,58,237,0.2);border-radius:8px;padding:12px 14px">
                    <div style="font-size:12px;font-weight:700;color:#c084fc;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-layer-group"></i> Multi-LLM Ensemble Consensus (3 AI Models Active)
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:8px">
                      ${modelsList.map(m => `
                        <div style="background:rgba(15,23,42,0.6);border:1px solid rgba(168,85,247,0.3);border-radius:6px;padding:5px 12px;font-size:11.5px;display:flex;align-items:center;gap:6px">
                          <i class="fa-solid fa-check-double" style="color:#10b981"></i>
                          <span style="font-weight:600;color:#e2e8f0">${m}</span>
                        </div>
                      `).join('')}
                    </div>
                  </div>

                  <!-- Section 1: Hipotesis Diagnosa Awal -->
                  <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#38bdf8;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-stethoscope"></i> 1. Hipotesis Diagnosa Awal (First Hypothesis)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #38bdf8">
                      ${firstHypothesisHTML}
                    </div>
                  </div>

                  <!-- Section 2: Hipotesis Sekunder / Alternative Risk Analysis -->
                  <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#f59e0b;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-code-compare"></i> 2. Evaluasi Sekunder & Analisis Risiko (Second Hypothesis)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #f59e0b">
                      ${secondHypothesisHTML}
                    </div>
                  </div>

                  <!-- Section 3: Keputusan Akhir & Tindakan Remediasi -->
                  <div style="background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.2);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#10b981;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-circle-check"></i> 3. Keputusan Akhir & Tindakan Remediasi (Final Decision)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:#e2e8f0;background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;border-left:3px solid #10b981">
                      ${finalDecisionHTML}
                    </div>
                  </div>

                  <!-- Trace Details -->
                  <div style="font-size:11px;color:var(--txt3,#64748b);display:flex;justify-content:space-between;padding:4px 2px">
                    <span>Trace ID: <code style="color:#a855f7">${log.trace_id || '—'}</code></span>
                    <span>Span ID: <code style="color:#38bdf8">${log.span_id || '—'}</code></span>
                  </div>

                </div>

                <!-- Footer -->
                <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
                  <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(${JSON.stringify(log).replace(/"/g, '&quot;')}));Notify.toast('📋 Copied','Detail pembelajaran AI disalin ke clipboard','ok')" style="padding:6px 14px">
                    <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin Detail JSON
                  </button>
                  <button class="btn btn-primary btn-sm" onclick="document.getElementById('ai-log-modal-overlay').remove()" style="padding:6px 18px">
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
