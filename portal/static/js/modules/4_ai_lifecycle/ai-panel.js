/* modules/4_ai_lifecycle/ai-panel.js
 * Atomic Design — 3. Modules Layer (4_ai_lifecycle / ai-panel)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["4_ai_lifecycle"] = window.Modules["4_ai_lifecycle"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      ai: {
        _incidents: [],
        _normConf(val) {
          const n = Number(val);
          if (!n || isNaN(n) || n <= 0) return 0;
          return Math.min(100, Math.round(n <= 1 ? n * 100 : n));
        },
        onPickIncident(id) {
          if (!id) return;
          const inc = this._incidents.find(i => String(i.incident_id || i.id) === String(id));
          const inp = document.getElementById('ai-query-input');
          if (!inc || !inp) return;
          const dev = inc.device_name || inc.agent || 'System';
          const flag = inc.flag || inc.status || 'ALERT';
          const desc = inc.analysis || inc.evidence || '';
          inp.value = `Analisis insiden #${id} pada ${dev} (${flag})${desc ? ': ' + desc : ''}`;
        },
        async load() {
          try {
            const svc = window.Services.Data || DataService;
            const [stats, incidents] = await Promise.all([
              svc.loadAIStats(),
              svc.loadIncidents()
            ]);

            this._incidents = Array.isArray(incidents) ? incidents : [];

            const pickEl = document.getElementById('ai-incident-pick');
            if (pickEl) {
              const cur = pickEl.value;
              pickEl.innerHTML = '<option value="">-- Ketik query manual atau pilih insiden --</option>';
              this._incidents.slice(0, 25).forEach(inc => {
                const id = inc.incident_id || inc.id;
                const opt = document.createElement('option');
                opt.value = id;
                opt.textContent = `#${id} · ${inc.device_name || inc.agent || 'System'} · ${inc.flag || inc.status || 'OPEN'}`;
                pickEl.appendChild(opt);
              });
              if (cur) pickEl.value = cur;
            }

            if (stats) {
              setEl('ai-active-count', stats.active_count ?? 0);
              setEl('ai-active-names', stats.active_names || '—');
              setEl('ai-rag-count', (stats.rag_count ?? 0) + ' entries');
              setEl('ai-class-acc', parseFloat(stats.classif_accuracy || 0).toFixed(1) + '%');
              setEl('ai-avg-conf', parseFloat(stats.avg_confidence || 0).toFixed(1) + '%');

              const models = Array.isArray(stats.models) ? stats.models : [];
              const modelListHtml = models.length > 0 ? models.map(m => {
                const icon = m.key === 'deepseek'
                  ? '<i class="fa-solid fa-robot" style="color:var(--pink);margin-right:6px"></i>'
                  : m.key === 'gemini'
                    ? '<i class="fa-solid fa-wand-magic-sparkles" style="color:var(--blue2);margin-right:6px"></i>'
                    : '<i class="fa-solid fa-bolt" style="color:var(--orange2);margin-right:6px"></i>';
                return `<div class="li-row">
              <span class="li-name">${icon} ${_esc(m.name || m.key || 'Model')}</span>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                <span class="tag ${m.enabled ? 'tag-green' : 'tag-gray'}">${m.enabled ? '● Active' : '● Disabled'}</span>
                <span style="font-size:9.5px;color:var(--txt3)">${_esc(m.url || '—')}</span>
              </div>
            </div>`;
              }).join('') : '<div style="font-size:11px;color:var(--txt3);text-align:center;padding:8px">Belum ada telemetri model terdaftar.</div>';
              htmlEl('ai-model-status-list', modelListHtml);

              // Radar performance chart
              const datasets = [];
              const colorMap = {
                deepseek: { bg: 'rgba(59,130,246,.15)', border: '#3b82f6', label: 'DeepSeek' },
                gemini: { bg: 'rgba(168,85,247,.15)', border: '#a855f7', label: 'Gemini' },
                groq: { bg: 'rgba(234,179,8,.15)', border: '#eab308', label: 'Groq Llama' }
              };
              models.filter(m => m && m.enabled && Array.isArray(m.performance)).forEach(m => {
                const c = colorMap[m.key] || { bg: 'rgba(6,182,212,.15)', border: '#06b6d4', label: m.name || m.key };
                datasets.push({ label: c.label, data: m.performance, backgroundColor: c.bg, borderColor: c.border, borderWidth: 2 });
              });
              datasets.push({ label: 'Baseline', data: [75, 75, 75, 75, 75], backgroundColor: 'rgba(139,148,158,.08)', borderColor: '#4d5e7a', borderWidth: 1, borderDash: [4, 3] });

              Charts.create('chart-ai-perf', 'radar', ['Confidence', 'Accuracy', 'Speed', 'Coverage', 'Precision'], datasets, { legend: true, scales: {} });
            }

            // AI History table
            const tbody = document.getElementById('tbody-ai-hist');
            if (tbody) {
              tbody.innerHTML = this._incidents.slice(0, 20).map(inc => {
                const ts = inc.timestamp || inc.created_at;
                const timeStr = ts ? new Date(ts).toLocaleString('id-ID') : '—';
                const confVal = this._normConf(inc.confidence);
                const confText = confVal > 0 ? confVal + '%' : '—';
                const flag = inc.flag || 'UNKNOWN';
                const modelName = inc.model_used || (inc.raw_data && inc.raw_data.ai_model) || 'Ensemble Engine';
                const st = (inc.status || 'OPEN').toUpperCase();
                const isResolved = st === 'RESOLVED' || st === 'CLOSED';

                const gtHtml = isResolved
                  ? `<code style="font-size:10px;color:var(--green2)">${_esc(flag)}</code>`
                  : `<span style="font-size:10px;color:var(--txt3)">PENDING</span>`;
                const statusHtml = isResolved
                  ? `<span class="tag tag-green">✓ Verified</span>`
                  : `<span class="tag tag-orange">⏳ ${_esc(st)}</span>`;

                return `<tr>
              <td style="font-size:10px;color:var(--txt2)">${_esc(timeStr)}</td>
              <td>${_esc(inc.device_name || inc.agent || 'System')}</td>
              <td><code style="font-size:10px;color:var(--orange2)">${_esc(flag)}</code></td>
              <td>${gtHtml}</td>
              <td style="color:${confVal >= 80 ? 'var(--green2)' : (confVal > 0 ? 'var(--orange2)' : 'var(--txt3)')}">${_esc(confText)}</td>
              <td><span class="tag tag-blue">${_esc(modelName)}</span></td>
              <td>${statusHtml}</td>
            </tr>`;
              }).join('') || '<tr><td colspan="7" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada data prediksi (0 insiden aktif)</td></tr>';
              this.filterHistory();
            }

            setEl('bdg-ai', 'Active');
          } catch (e) {
            console.error('Error loading AI panel:', e);
          }
        },
        filterHistory() {
          const q = ((document.getElementById('ai-hist-search') || {}).value || '').toLowerCase().trim();
          const tbody = document.getElementById('tbody-ai-hist');
          if (!tbody) return;
          tbody.querySelectorAll('tr').forEach(tr => {
            if (tr.querySelector('td[colspan]')) return;
            tr.style.display = (!q || tr.textContent.toLowerCase().includes(q)) ? '' : 'none';
          });
        },
        async runInference() {
          const query = ((document.getElementById('ai-query-input') || {}).value || '').trim() || 'Analisis insiden terbaru';
          const out = document.getElementById('ai-reasoning-output');
          if (!out) return;

          out.innerHTML = '<div style="color:var(--txt2);font-size:11px;display:flex;align-items:center;gap:8px"><div style="width:12px;height:12px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> AI sedang menganalisis dengan model lokal...</div>';
          LogStreamer.add('INFO', 'AI', 'Inference started: "' + query.slice(0, 50) + '"');

          try {
            const resp = await (window.Services.Data || DataService).runAIDiagnose(query);
            if (resp && resp.success) {
              const conf = this._normConf(resp.confidence);
              const steps = Array.isArray(resp.remediation_steps) ? resp.remediation_steps : [];
              const stepsHtml = steps.length > 0
                ? `<ol style="margin:6px 0 0 18px;font-size:11px;color:var(--txt);line-height:1.6">${steps.map(s => `<li>${_esc(s)}</li>`).join('')}</ol>`
                : '<div style="font-size:11px;color:var(--txt3);margin-top:4px">Tidak ada langkah remediasi otomatis yang disarankan.</div>';

              const cmdHtml = resp.suggested_command
                ? `<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.35);border-radius:8px;padding:10px 12px;margin-top:10px">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap">
                      <span style="font-weight:700;color:var(--green2);font-size:11.5px"><i class="fa-solid fa-terminal" style="margin-right:6px"></i>Rekomendasi Command (Manual / HITL Gate)</span>
                      <span class="tag tag-orange" style="font-size:9.5px">PENDING EXECUTION &amp; VERIFICATION</span>
                    </div>
                    <pre style="margin:6px 0 0;padding:8px;background:rgba(0,0,0,0.35);border-radius:5px;font-size:10.5px;color:var(--cyan);overflow-x:auto">${_esc(resp.suggested_command)}</pre>
                  </div>`
                : '';

              out.innerHTML = `
            <div style="font-size:11.5px;margin-bottom:10px"><b style="color:var(--purple2)">🧠 AI Reasoning &amp; Diagnosis (${_esc(resp.source || 'AI Core')}):</b></div>
            <div style="background:rgba(0,0,0,.3);border-radius:6px;padding:10px 12px;font-size:11px;color:var(--txt2);line-height:1.6;margin-bottom:10px;border:1px solid var(--bd)">
              <b>Diagnosis Executive:</b>
              <div style="white-space:pre-wrap;font-family:inherit;margin-top:6px;color:var(--txt)">${_esc(resp.answer || '—')}</div>
              <b style="display:block;margin-top:10px">5-Why Causal Root Cause Analysis:</b>
              <pre style="font-family:'JetBrains Mono',monospace;font-size:10.5px;background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.05);padding:8px;border-radius:4px;color:#a855f7;white-space:pre-wrap;margin-top:4px">${_esc(resp['5_whys_analysis'] || '—')}</pre>
              <b style="display:block;margin-top:10px">Langkah Remediasi yang Disarankan:</b>
              ${stepsHtml}
              ${cmdHtml}
            </div>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
              <div style="flex:1;min-width:140px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">CONFIDENCE</div><div style="font-size:18px;font-weight:800;color:var(--green2)">${conf}%</div></div>
              <div style="flex:1;min-width:140px;background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">CLASSIFICATION</div><div style="font-size:13px;font-weight:700;color:var(--blue2)">${_esc(resp.flag || 'GENERAL')}</div></div>
              <div style="flex:1;min-width:140px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);margin-bottom:4px">SOURCE</div><div style="font-size:11px;font-weight:600;color:var(--orange2)">${_esc(resp.source || 'AI Core')}</div></div>
            </div>`;
              Notify.toast('🤖 AI Inference', 'Analisis selesai · Confidence: ' + conf + '%', 'ok', 3000);
              LogStreamer.add('OK', 'AI', 'Inference completed · confidence: ' + conf + '% · class: ' + (resp.flag || 'GENERAL'));
            } else {
              const errTxt = (resp && (resp.error || resp.message)) || 'Unknown response';
              out.innerHTML = `<div class="empty-state"><div class="es-icon">❌</div><div class="es-text">Diagnosis gagal: ${_esc(errTxt)}</div></div>`;
              Notify.toast('❌ Diagnosis Gagal', _esc(errTxt), 'error', 3000);
            }
          } catch (err) {
            out.innerHTML = `<div class="empty-state"><div class="es-icon">❌</div><div class="es-text">Gagal menghubungi API: ${_esc(err.message || String(err))}</div></div>`;
            Notify.toast('❌ Error API', _esc(err.message || 'API Error'), 'error', 3000);
          }
        }
      },

});

window.Modules["4_ai_lifecycle"]["ai-panel"] = window.Panels;
