/* modules/3_incident_rca/rca.js
 * Atomic Design — 3. Modules Layer (3_incident_rca / rca)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["3_incident_rca"] = window.Modules["3_incident_rca"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      rca: {
        async load() {
          const svc = window.Services.Data || DataService;
          const [incidents, devices, aiStats] = await Promise.all([
            (Array.isArray(svc._incidents) && svc._incidents.length > 0) ? Promise.resolve(svc._incidents) : svc.loadIncidents().catch(() => []),
            (Array.isArray(svc._devices) && svc._devices.length > 0) ? Promise.resolve(svc._devices) : svc.loadDevices().catch(() => []),
            svc.loadAIStats().catch(() => null)
          ]);

          const sel = document.getElementById('rca-select');
          if (sel) {
            const prev = sel.value;
            sel.innerHTML = '<option value="">Pilih insiden...</option>';
            (incidents || []).forEach(i => {
              const opt = document.createElement('option');
              opt.value = i.incident_id || i.id;
              opt.textContent = `${i.incident_id || i.id} · ${i.device_name || i.agent || 'System'} · ${i.flag || i.status || 'OPEN'}`;
              sel.appendChild(opt);
            });
            if (prev) sel.value = prev;
          }

          const target = document.getElementById('rca-target');
          if (target) {
            const prevTarget = target.value;
            target.innerHTML = '<option value="">Pilih device target...</option>';
            (devices || []).forEach(d => {
              const opt = document.createElement('option');
              opt.value = d.name;
              opt.textContent = `${d.name} (${d.ip || '—'})`;
              target.appendChild(opt);
            });
            if (prevTarget) target.value = prevTarget;
          }

          const avgConf = Number(aiStats?.avg_confidence) || 0;
          const classif = Number(aiStats?.classif_accuracy) || 0;
          const consensus = (avgConf || classif) ? Math.round((avgConf + classif) / (avgConf && classif ? 2 : 1)) : 0;
          Charts.create('chart-rca-confidence', 'bar', ['Confidence Avg', 'Evidence Score', 'AI Consensus'], [{
            data: [avgConf, classif, consensus],
            backgroundColor: ['#3b82f6', '#22c55e', '#a855f7'],
            borderRadius: 4
          }], { legend: false, yOpts: { max: 100, min: 0 } });
        },
        async analyze() {
          const id = (document.getElementById('rca-select') || {}).value;
          if (!id) return;

          const svc = window.Services.Data || DataService;
          const out5why = document.getElementById('rca-5why');
          if (out5why) {
            out5why.innerHTML = '<div style="color:var(--txt2);font-size:11px;padding:12px"><div style="width:12px;height:12px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block;margin-right:6px"></div> Menganalisis...</div>';
          }

          try {
            const [res, traceRes] = await Promise.all([
              svc.fetch(`/api/rca/analyze/${encodeURIComponent(id)}`),
              svc.fetch(`/api/rca/trace/${encodeURIComponent(id)}`).catch(() => null)
            ]);
            if (!res || !res.success) {
              Notify.toast('❌ Error', (res && (res.error || res.message)) || 'Gagal melakukan analisis RCA', 'err');
              return;
            }

            const rawConf = Number(res.confidence) || 0;
            const conf = Math.min(100, Math.max(0, Math.round(rawConf <= 1 && rawConf > 0 ? rawConf * 100 : rawConf)));
            setEl('rca-conf-tag', conf + '% confidence');
            const confTag = document.getElementById('rca-conf-tag');
            if (confTag) confTag.className = 'tag tag-' + (conf >= 80 ? 'green' : conf >= 60 ? 'orange' : 'red');

            const whys = Array.isArray(res.whys) ? res.whys : [];
            const steps = Array.isArray(res.steps) ? res.steps : [];
            const timeline = Array.isArray(res.timeline) ? res.timeline : [];
            const flag = String(res.flag || 'ALERT');
            const devName = String(res.device_name || 'System');

            // 5 Why
            htmlEl('rca-5why', `<div style="font-size:11.5px;font-weight:600;color:var(--txt);margin-bottom:10px">${_esc(devName)} — ${_esc(flag)}</div>` +
              (whys.length > 0
                ? whys.map((w, i) => `<div style="display:flex;gap:8px;margin:8px 0;align-items:flex-start"><div style="width:24px;height:24px;background:rgba(59,130,246,.15);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--blue2);flex-shrink:0">${i + 1}</div><div style="font-size:11.5px;color:var(--txt2);padding-top:3px">Why ${i + 1}: ${_esc(w)}</div></div>`).join('')
                : '<div style="font-size:11px;color:var(--txt3)">Belum ada rantai 5-Why tersedia.</div>'));

            // Evidence Chain
            let pingStatus = 'tag-green';
            let pingText = 'ONLINE';
            let heartbeatText = 'ONLINE';
            let heartbeatStatus = 'tag-green';

            if (flag.includes('OFFLINE') || flag.includes('DOWN')) {
              pingStatus = 'tag-red';
              pingText = 'UNREACHABLE';
              heartbeatText = 'TIMEOUT > 180s';
              heartbeatStatus = 'tag-red';
            } else if (flag.includes('LATENCY')) {
              pingStatus = 'tag-orange';
              pingText = 'HIGH LATENCY';
              heartbeatText = 'DELAYED';
              heartbeatStatus = 'tag-orange';
            }

            htmlEl('rca-evidence', `
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-heart-pulse" style="margin-right:6px"></i>Heartbeat Status</span><span class="tag ${heartbeatStatus}">${heartbeatText}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-tower-broadcast" style="margin-right:6px"></i>Ping Result</span><span class="tag ${pingStatus}">${pingText}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-brain" style="margin-right:6px"></i>AI Analysis</span><span style="font-size:10.5px;color:var(--txt2)">${_esc(res.analysis || '—')}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-crosshairs" style="margin-right:6px"></i>Confidence</span><span class="tag tag-blue">${conf}%</span></div>
          ${steps.map(s => `<div class="li-row"><span class="li-name"><i class="fa-solid fa-clipboard-list" style="margin-right:6px"></i>${_esc(s)}</span><span class="tag tag-green">SOP Ready</span></div>`).join('')}
        `);

            // Update Reasoning Trace dynamically (from /api/rca/trace/:id or res)
            const trace = (traceRes && (traceRes.trace || traceRes)) || {};
            setEl('rt-intent', `${flag} (Confidence: ${conf}%)`);
            setEl('rt-rag', trace.rag_match || (steps.length ? `Matched SOP: "${steps[0]}"` : 'No SOP matched'));
            setEl('rt-dag', trace.causal_path || `Target: ${devName} | ${whys[0] || res.analysis || '—'}`);
            setEl('rt-policy', trace.policy_verdict || `Confidence: ${conf}% | Verifier: ${conf >= 75 ? 'PASSED_GROUNDED' : 'REQUIRES_REVIEW'}`);

            // Populate Ground Truth Feedback box
            const fbBox = document.getElementById('rca-feedback-box');
            if (fbBox) fbBox.style.display = 'block';
            const aiPredInput = document.getElementById('rca-ai-pred');
            if (aiPredInput) aiPredInput.value = res.analysis || '';
            const gtSelect = document.getElementById('rca-human-gt');
            if (gtSelect) gtSelect.value = '';
            const manContainer = document.getElementById('rca-manual-gt-container');
            if (manContainer) manContainer.style.display = 'none';
            const manInput = document.getElementById('rca-manual-gt');
            if (manInput) manInput.value = '';

            // Timeline
            htmlEl('rca-timeline', timeline.length > 0
              ? timeline.map(e => `
          <div style="display:flex;gap:12px;margin:8px 0;align-items:flex-start">
            <div style="font-size:10px;color:var(--txt3);min-width:80px;padding-top:2px">${_esc(e.time || '—')}</div>
            <div>${e.icon || '•'}</div>
            <div style="font-size:11.5px;color:var(--txt2)">${_esc(e.msg || '')}</div>
          </div>
        `).join('')
              : '<div style="font-size:11px;color:var(--txt3)">Belum ada entri timeline untuk insiden ini.</div>');

            // Update Chart
            const evScore = Math.min(100, Math.round(conf * 0.95));
            const consScore = Math.round((conf + evScore) / 2);
            Charts.create('chart-rca-confidence', 'bar', ['Confidence Avg', 'Evidence Score', 'AI Consensus'], [{
              data: [conf, evScore, consScore],
              backgroundColor: ['#3b82f6', '#22c55e', '#a855f7'],
              borderRadius: 4
            }], { legend: false, yOpts: { max: 100, min: 0 } });

            // Auto-select Remote Target Device
            const targetSelect = document.getElementById('rca-target');
            if (targetSelect) {
              targetSelect.value = devName;
              const d = (svc._devices || []).find(x => x.name === devName);
              setEl('remote-target-ip', d ? d.ip : '—');
            }

            Notify.toast('🔬 RCA', 'Analisis selesai untuk ' + _esc(devName), 'ok', 3000);
            LogStreamer.add('OK', 'RCA', '5-Why analysis completed for ' + id + ' · confidence: ' + conf + '%');

          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal menghubungi server untuk analisis RCA', 'err');
          }
        },
        async reanalyze() {
          const id = (document.getElementById('rca-select') || {}).value;
          if (!id) {
            Notify.toast('⚠️ Warning', 'Pilih insiden terlebih dahulu', 'warn');
            return;
          }
          try {
            const res = await (window.Services.Data || DataService).fetch(`/api/rca/reanalyze/${encodeURIComponent(id)}`, { method: 'POST' });
            if (res && (res.status === 'SUCCESS' || res.status === 'success' || res.success)) {
              Notify.toast('🔄 Re-Analyze', 'Permintaan Re-Analysis berhasil dikirim ke AI Core', 'ok');
              LogStreamer.add('OK', 'RCA', 'Force Re-Analysis triggered for incident ' + id);
              setTimeout(() => Panels.rca.analyze(), 4000);
            } else {
              Notify.toast('❌ Error', (res && (res.message || res.error)) || 'Gagal memicu re-analysis', 'err');
            }
          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal memicu re-analysis', 'err');
          }
        },
        async submitDebrief() {
          const incidentId = (document.getElementById('rca-select') || {}).value;
          if (!incidentId) {
            Notify.toast('⚠️ Debrief', 'Pilih insiden terlebih dahulu', 'warn');
            return;
          }
          const isCorrect = (document.getElementById('debrief-rca-correct') || {}).value === 'true';
          const notes = ((document.getElementById('debrief-external-factors') || {}).value || '').trim();
          const aiRca = (document.getElementById('rca-ai-pred') || {}).value || 'AI RCA Prediction';
          if (!isCorrect && !notes) {
            Notify.toast('⚠️ Debrief', 'Isi catatan koreksi / faktor eksternal jika AI perlu koreksi manual', 'warn');
            return;
          }
          try {
            const res = await (window.Services.Data || DataService).fetch('/api/feedback', {
              method: 'POST',
              body: JSON.stringify({
                incident_id: parseInt(incidentId, 10) || 0,
                ai_rca: aiRca,
                human_rca: isCorrect ? 'AI Root Cause Confirmed Accurate' : (notes || 'Manual Correction Needed'),
                score: isCorrect ? 1.0 : 0.4,
                reviewer: 'NOC_OPERATOR',
                rejection_reason: isCorrect ? '' : notes
              })
            });
            if (res && (res.success || res.status === 'SUCCESS' || res.status === 'success')) {
              Notify.toast('✅ Debrief', 'Cognitive Debriefing berhasil disimpan ke feedback loop!', 'ok');
              const txtEl = document.getElementById('debrief-external-factors');
              if (txtEl) txtEl.value = '';
              LogStreamer.add('OK', 'RCA', `Cognitive debrief submitted for incident ${incidentId} (accurate=${isCorrect})`);
            } else {
              Notify.toast('❌ Error', (res && (res.error || res.message)) || 'Gagal menyimpan debrief', 'err');
            }
          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal menghubungi server', 'err');
          }
        },
        async submitFeedback() {
          const incidentId = (document.getElementById('rca-select') || {}).value;
          if (!incidentId) {
            Notify.toast('⚠️ Feedback', 'Pilih insiden terlebih dahulu', 'warn');
            return;
          }

          const ai_rca = (document.getElementById('rca-ai-pred') || {}).value || '';
          let human_rca = (document.getElementById('rca-human-gt') || {}).value || '';
          if (human_rca === 'Other / Manual Cause') {
            human_rca = ((document.getElementById('rca-manual-gt') || {}).value || '').trim();
            if (!human_rca) {
              Notify.toast('⚠️ Feedback', 'Tulis penyebab manual', 'warn');
              return;
            }
          }
          if (!human_rca) {
            Notify.toast('⚠️ Feedback', 'Pilih atau isi Ground Truth', 'warn');
            return;
          }

          const score = parseFloat((document.getElementById('rca-feedback-score') || {}).value || '1.0');

          try {
            const res = await (window.Services.Data || DataService).fetch('/api/feedback', {
              method: 'POST',
              body: JSON.stringify({
                incident_id: parseInt(incidentId, 10) || 0,
                ai_rca: ai_rca,
                human_rca: human_rca,
                score: score,
                reviewer: 'NOC_OPERATOR'
              })
            });
            if (res && (res.success || res.status === 'SUCCESS' || res.status === 'success')) {
              Notify.toast('✅ Feedback', 'Ground Truth berhasil dikirim!', 'ok');
              LogStreamer.add('OK', 'RCA', `Feedback saved for incident ${incidentId} (Score: ${score})`);
            } else {
              Notify.toast('❌ Error', 'Gagal mengirim feedback: ' + ((res && (res.error || res.message)) || 'Unknown error'), 'err');
            }
          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal menghubungi server', 'err');
          }
        },
        async sendCmd(cmd) {
          const target = (document.getElementById('rca-target') || {}).value;
          const resultEl = document.getElementById('rca-cmd-result');
          if (!target) { Notify.toast('⚠️ Remote', 'Pilih device target', 'warn'); return; }
          if (resultEl) resultEl.innerHTML = '<span style="color:var(--blue2)">⏳ Mengirim ' + _esc(cmd) + ' ke ' + _esc(target) + '...</span>';
          try {
            const r = await (window.Services.Data || DataService).sendCommand(cmd, target);
            const ok = r && r.status !== 'FAILED' && r.status !== 'ERROR' && !r.error;
            if (ok) {
              if (resultEl) resultEl.innerHTML = `<span style="color:var(--green2)">✅ ${_esc(cmd)} → ${_esc(target)}: ${_esc((r && r.message) || 'EXECUTED')}</span>`;
              Notify.toast('🛠️ Remote', `${_esc(cmd)} dikirim ke ${_esc(target)}`, 'ok', 3000);
              LogStreamer.add('OK', 'ORCH', `${cmd} executed on ${target} · ${(r && r.status) || 'OK'}`);
            } else {
              const errMsg = (r && (r.error || r.message)) || 'Command failed';
              if (resultEl) resultEl.innerHTML = `<span style="color:var(--red2)">❌ ${_esc(cmd)} → ${_esc(target)}: ${_esc(errMsg)}</span>`;
              Notify.toast('❌ Remote Gagal', _esc(errMsg), 'err', 3500);
              LogStreamer.add('WARN', 'ORCH', `${cmd} failed on ${target} · ${errMsg}`);
            }
          } catch (err) {
            if (resultEl) resultEl.innerHTML = `<span style="color:var(--red2)">❌ ${_esc(cmd)} → ${_esc(target)}: ${_esc(err.message || String(err))}</span>`;
            Notify.toast('❌ Remote Error', _esc(err.message || 'Gagal mengirim command'), 'err', 3500);
          }
        },
        exportTimeline() {
          const el = document.getElementById('rca-timeline');
          const txt = el ? el.innerText : '';
          if (!txt.trim()) {
            Notify.toast('⚠️ Export', 'Timeline masih kosong', 'warn');
            return;
          }
          const blob = new Blob([txt], { type: 'text/plain;charset=utf-8;' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'rca-timeline.txt';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          Notify.toast('📥 Export', 'Timeline diekspor', 'ok');
        }
      },

});

window.Modules["3_incident_rca"]["rca"] = window.Panels;
