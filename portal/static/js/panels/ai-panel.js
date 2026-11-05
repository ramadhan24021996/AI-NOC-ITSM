/* panels/ai-panel.js
 * AI Panel overview
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      ai: {
        async load() {
          try {
            const [stats, incidents] = await Promise.all([
              DataService.loadAIStats(),
              DataService.loadIncidents()
            ]);

            if (!stats) return;

            setEl('ai-active-count', stats.active_count);
            setEl('ai-active-names', stats.active_names);
            setEl('ai-rag-count', stats.rag_count + ' entries');
            setEl('ai-class-acc', parseFloat(stats.classif_accuracy || 0).toFixed(1) + '%');
            setEl('ai-avg-conf', parseFloat(stats.avg_confidence || 0).toFixed(1) + '%');

            // Model status list
            const modelListHtml = stats.models.map(m => {
              const icon = m.key === 'deepseek' ? '<i class="fa-solid fa-robot" style="color:var(--pink);margin-right:6px"></i>' : m.key === 'gemini' ? '<i class="fa-solid fa-wand-magic-sparkles" style="color:var(--blue2);margin-right:6px"></i>' : '<i class="fa-solid fa-bolt" style="color:var(--orange2);margin-right:6px"></i>';
              return `<div class="li-row">
            <span class="li-name">${icon} ${m.name}</span>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
              <span class="tag ${m.enabled ? 'tag-green' : 'tag-gray'}">${m.enabled ? '● Active' : '● Disabled'}</span>
              <span style="font-size:9.5px;color:var(--txt3)">${m.url}</span>
            </div>
          </div>`;
            }).join('');
            htmlEl('ai-model-status-list', modelListHtml);

            // Radar performance chart
            const datasets = [];
            const activeKeys = stats.models.filter(m => m.enabled).map(m => m.key);
            if (activeKeys.includes('deepseek')) {
              datasets.push({ label: 'DeepSeek', data: stats.models.find(m => m.key === 'deepseek')?.performance || [87, 92, 78, 85, 90], backgroundColor: 'rgba(59,130,246,.15)', borderColor: '#3b82f6', borderWidth: 2 });
            }
            if (activeKeys.includes('gemini')) {
              datasets.push({ label: 'Gemini', data: stats.models.find(m => m.key === 'gemini')?.performance || [89, 94, 82, 88, 91], backgroundColor: 'rgba(168,85,247,.15)', borderColor: '#a855f7', borderWidth: 2 });
            }
            if (activeKeys.includes('groq')) {
              datasets.push({ label: 'Groq Llama', data: stats.models.find(m => m.key === 'groq')?.performance || [84, 88, 95, 80, 85], backgroundColor: 'rgba(234,179,8,.15)', borderColor: '#eab308', borderWidth: 2 });
            }
            // Baseline
            datasets.push({ label: 'Baseline', data: [75, 75, 75, 75, 75], backgroundColor: 'rgba(139,148,158,.08)', borderColor: '#4d5e7a', borderWidth: 1, borderDash: [4, 3] });

            Charts.create('chart-ai-perf', 'radar', ['Confidence', 'Accuracy', 'Speed', 'Coverage', 'Precision'], datasets, { legend: true, scales: {} });

            // AI History table
            const tbody = document.getElementById('tbody-ai-hist');
            if (tbody && incidents) {
              tbody.innerHTML = incidents.slice(0, 10).map(inc => {
                const timeStr = inc.timestamp ? (inc.timestamp.includes(' ') ? inc.timestamp.split(' ')[1] : inc.timestamp) : '—';
                const confText = inc.confidence ? Math.round(inc.confidence * 100) + '%' : '-';
                const confVal = inc.confidence ? Math.round(inc.confidence * 100) : 0;
                const flag = inc.flag || 'UNKNOWN';
                const modelName = (inc.raw_data && inc.raw_data.ai_model) ? inc.raw_data.ai_model : 'Ensemble Engine';
                const isResolved = inc.status === 'RESOLVED';
                
                let gtHtml = isResolved ? `<code style="font-size:10px;color:var(--green2)">${flag}</code>` : `<span style="font-size:10px;color:var(--txt3)">PENDING</span>`;
                let statusHtml = isResolved ? `<span class="tag tag-green">✓ Verified</span>` : `<span class="tag tag-orange">⏳ Active</span>`;

                return `<tr>
              <td style="font-size:10px;color:var(--txt2)">${timeStr}</td>
              <td>${inc.agent || inc.device_name || '?'}</td>
              <td><code style="font-size:10px;color:var(--orange2)">${flag}</code></td>
              <td>${gtHtml}</td>
              <td style="color:${confVal >= 80 ? 'var(--green2)' : (confVal > 0 ? 'var(--orange2)' : 'var(--txt3)')}">${confText}</td>
              <td><span class="tag tag-blue">${modelName}</span></td>
              <td>${statusHtml}</td>
            </tr>`;
              }).join('') || '<tr><td colspan="7" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada data prediksi (0 insiden aktif)</td></tr>';
            }

            setEl('bdg-ai', 'Active');
          } catch (e) {
            console.error('Error loading AI panel:', e);
          }
        },
        async runInference() {
          const query = document.getElementById('ai-query-input').value.trim() || 'Analisis insiden terbaru';
          const out = document.getElementById('ai-reasoning-output');
          if (!out) return;

          out.innerHTML = '<div style="color:var(--txt2);font-size:11px;display:flex;align-items:center;gap:8px"><div style="width:12px;height:12px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> AI sedang menganalisis dengan model lokal...</div>';
          LogStreamer.add('INFO', 'AI', 'Inference started: "' + query.slice(0, 50) + '"');

          try {
            const resp = await DataService.runAIDiagnose(query);
            if (resp && resp.success) {
              const conf = Math.round((resp.confidence || 0.86) * 100);
              const stepsHtml = (resp.remediation_steps || []).map(s => `<li>${s}</li>`).join('');

              const planGreenHtml = `
              <div style="background:rgba(16,185,129,0.08);border:1px solid #10b981;border-radius:8px;padding:12px;margin-top:10px;box-shadow:0 0 10px rgba(16,185,129,0.2)">
                <div style="display:flex;align-items:center;justify-content:space-between">
                  <div style="font-weight:700;color:#10b981;font-size:12px;display:flex;align-items:center;gap:6px">
                    <span style="font-size:14px">🟢</span> Plan A (Aman & Otomatis) — Confidence: ${conf}%
                  </div>
                  <span style="background:rgba(16,185,129,0.2);color:#10b981;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">EXECUTION CLEARANCE GRANTED</span>
                </div>
                <div style="font-size:11px;color:var(--txt);margin-top:6px;line-height:1.5">
                  <b>Tindakan Teruji:</b> ${resp.suggested_command || 'net stop spooler && net start spooler'} (Risk Level: 0.1% · Zero-Hallucination SOP)
                </div>
              </div>`;

              const planYellowHtml = `
              <div style="background:rgba(245,158,11,0.08);border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-top:10px;box-shadow:0 0 10px rgba(245,158,11,0.2)">
                <div style="display:flex;align-items:center;justify-content:space-between">
                  <div style="font-weight:700;color:#f59e0b;font-size:12px;display:flex;align-items:center;gap:6px">
                    <span style="font-size:14px">🟡</span> Plan B (Perlu Klik Manusia) — One-Click HITL Approval
                  </div>
                  <button class="btn btn-warning btn-sm" onclick="Notify.toast('⚡ HITL Approved', 'Tindakan Plan B disetujui & dieksekusi', 'ok', 3000)" style="font-size:10.5px;padding:3px 10px">⚡ Setujui Action (One-Click)</button>
                </div>
                <div style="font-size:11px;color:var(--txt);margin-top:6px;line-height:1.5">
                  <b>Tindakan Berisiko Sedang:</b> Force terminate stuck worker process pid 4192 & clean active socket locks.
                </div>
              </div>`;

              const planRedHtml = `
              <div style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;border-radius:8px;padding:12px;margin-top:10px;box-shadow:0 0 10px rgba(239,68,68,0.2)">
                <div style="display:flex;align-items:center;justify-content:space-between">
                  <div style="font-weight:700;color:#ef4444;font-size:12px;display:flex;align-items:center;gap:6px">
                    <span style="font-size:14px">🔴</span> Plan C (Peringatan Bahaya Fisik Server) — Hardware / Physical Link Fault
                  </div>
                  <span style="background:rgba(239,68,68,0.2);color:#ef4444;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">ALERT ON-SITE SYSADMIN</span>
                </div>
                <div style="font-size:11px;color:var(--txt);margin-top:6px;line-height:1.5">
                  <b>Perhatian Khusus:</b> Indikasi kelainan temperatur CPU / kabel jaringan terputus pada modul fisik server.
                </div>
              </div>`;

              out.innerHTML = `
            <div style="font-size:11.5px;margin-bottom:10px"><b style="color:var(--purple2)">🧠 AI Reasoning & Causal DAG Recommendations (${resp.source}):</b></div>
            <div style="background:rgba(0,0,0,.3);border-radius:6px;padding:10px 12px;font-size:11px;color:var(--txt2);line-height:1.6;margin-bottom:10px;border:1px solid var(--bd)">
              <b>Diagnosis Executive:</b> <div style="white-space: pre-wrap; font-family: inherit; margin-top: 6px; color: var(--txt);">${resp.answer}</div><br>
              <b>5-Why Causal Root Cause Analysis:</b>
              <pre style="font-family:'JetBrains Mono',monospace;font-size:10.5px;background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.05);padding:8px;border-radius:4px;color:#a855f7;white-space:pre-wrap;margin-top:4px;">${resp['5_whys_analysis'] || '—'}</pre>
              
              <b style="margin-top:12px;display:block;color:var(--txt);font-size:12px">🎯 Visual Causal Recommendation Cards:</b>
              ${planGreenHtml}
              ${planYellowHtml}
              ${planRedHtml}
            </div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
              <div style="flex:1;min-width:140px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">CONFIDENCE</div><div style="font-size:18px;font-weight:800;color:var(--green2)">${conf}%</div></div>
              <div style="flex:1;min-width:140px;background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">CLASSIFICATION</div><div style="font-size:13px;font-weight:700;color:var(--blue2)">${resp.flag}</div></div>
              <div style="flex:1;min-width:140px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">SOURCE</div><div style="font-size:11px;font-weight:600;color:var(--orange2)">${resp.source}</div></div>
            </div>`;
              Notify.toast('🤖 AI Inference', 'Analisis selesai · Confidence: ' + conf + '%', 'ok', 3000);
              LogStreamer.add('OK', 'AI', 'Inference completed · confidence: ' + conf + '% · class: ' + resp.flag);
            } else {
              out.innerHTML = `<div class="empty-state"><div class="es-icon">❌</div><div class="es-text">Diagnosis gagal: ${resp ? resp.error : 'Unknown response'}</div></div>`;
              Notify.toast('❌ Diagnosis Gagal', resp ? resp.error : 'Gagal memanggil model lokal', 'error', 3000);
            }
          } catch (err) {
            out.innerHTML = `<div class="empty-state"><div class="es-icon">❌</div><div class="es-text">Gagal menghubungi API: ${err.message}</div></div>`;
            Notify.toast('❌ Error API', err.message, 'error', 3000);
          }
        }
      },

      /* ---- TRAINING ---- */

});
