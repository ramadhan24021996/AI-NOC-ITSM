/* panels/rca.js
 * RCA & Ground Truth panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      rca: {
        async load() {
          const incidents = DataService._incidents;
          const sel = document.getElementById('rca-select');
          if (sel) {
            sel.innerHTML = '<option value="">Pilih insiden...</option>';
            incidents.forEach(i => { const opt = document.createElement('option'); opt.value = i.incident_id || i.id; opt.textContent = (i.incident_id || i.id) + ' · ' + (i.device_name || i.agent) + ' · ' + (i.flag || i.status); sel.appendChild(opt); });
          }
          const target = document.getElementById('rca-target');
          if (target) {
            target.innerHTML = '<option value="">Pilih device target...</option>';
            DataService._devices.forEach(d => { const opt = document.createElement('option'); opt.value = d.name; opt.textContent = d.name + ' (' + d.ip + ')'; target.appendChild(opt); });
          }
          const aiStats = await DataService.loadAIStats();
          const avgConf = aiStats?.avg_confidence || 0;
          const classif = aiStats?.classif_accuracy || 0;
          const consensus = (avgConf + classif) / 2 || 0;
          Charts.create('chart-rca-confidence', 'bar', ['Confidence Avg', 'Evidence Score', 'AI Consensus'], [{ data: [avgConf, classif, consensus], backgroundColor: ['#3b82f6', '#22c55e', '#a855f7'], borderRadius: 4 }], { legend: false, yOpts: { max: 100, min: 0 } });
        },
        async analyze() {
          const id = document.getElementById('rca-select').value;
          if (!id) return;

          const out5why = document.getElementById('rca-5why');
          const outEvidence = document.getElementById('rca-evidence');
          const outTimeline = document.getElementById('rca-timeline');

          if (out5why) out5why.innerHTML = '<div style="color:var(--txt2);font-size:11px;padding:12px"><div style="width:12px;height:12px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block;margin-right:6px"></div> Menganalisis...</div>';

          try {
            const resp = await fetch(`/api/rca/analyze/${id}`);
            const res = await resp.json();
            if (!res || !res.success) {
              Notify.toast('❌ Error', 'Gagal melakukan analisis RCA', 'err');
              return;
            }

            const conf = res.confidence;
            setEl('rca-conf-tag', conf + '% confidence');
            document.getElementById('rca-conf-tag').className = 'tag tag-' + (conf >= 80 ? 'green' : conf >= 60 ? 'orange' : 'red');

            // 5 Why
            htmlEl('rca-5why', `<div style="font-size:11.5px;font-weight:600;color:var(--txt);margin-bottom:10px">${res.device_name} — ${res.flag}</div>` +
              res.whys.map((w, i) => `<div style="display:flex;gap:8px;margin:8px 0;align-items:flex-start"><div style="width:24px;height:24px;background:rgba(59,130,246,.15);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--blue2);flex-shrink:0">${i + 1}</div><div style="font-size:11.5px;color:var(--txt2);padding-top:3px">Why ${i + 1}: ${w}</div></div>`).join(''));

            // Evidence Chain
            let pingStatus = 'tag-green';
            let pingText = 'ONLINE';
            let heartbeatText = 'ONLINE';
            let heartbeatStatus = 'tag-green';

            if (res.flag.includes('OFFLINE') || res.flag.includes('DOWN')) {
              pingStatus = 'tag-red';
              pingText = 'UNREACHABLE';
              heartbeatText = 'TIMEOUT > 180s';
              heartbeatStatus = 'tag-red';
            } else if (res.flag.includes('LATENCY')) {
              pingStatus = 'tag-orange';
              pingText = 'HIGH LATENCY';
              heartbeatText = 'DELAYED';
              heartbeatStatus = 'tag-orange';
            }

            htmlEl('rca-evidence', `
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-heart-pulse" style="margin-right:6px"></i>Heartbeat Status</span><span class="tag ${heartbeatStatus}">${heartbeatText}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-tower-broadcast" style="margin-right:6px"></i>Ping Result</span><span class="tag ${pingStatus}">${pingText}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-brain" style="margin-right:6px"></i>AI Analysis</span><span style="font-size:10.5px;color:var(--txt2)">${res.analysis}</span></div>
          <div class="li-row"><span class="li-name"><i class="fa-solid fa-crosshairs" style="margin-right:6px"></i>Confidence</span><span class="tag tag-blue">${conf}%</span></div>
          ${res.steps.map(s => `<div class="li-row"><span class="li-name"><i class="fa-solid fa-clipboard-list" style="margin-right:6px"></i>${s}</span><span class="tag tag-green">SOP Ready</span></div>`).join('')}
        `);

            // Populate Ground Truth Feedback box
            const fbBox = document.getElementById('rca-feedback-box');
            if (fbBox) fbBox.style.display = 'block';
            const aiPredInput = document.getElementById('rca-ai-pred');
            if (aiPredInput) aiPredInput.value = res.analysis;
            const gtSelect = document.getElementById('rca-human-gt');
            if (gtSelect) gtSelect.value = '';
            const manContainer = document.getElementById('rca-manual-gt-container');
            if (manContainer) manContainer.style.display = 'none';
            const manInput = document.getElementById('rca-manual-gt');
            if (manInput) manInput.value = '';

            // Timeline
            htmlEl('rca-timeline', res.timeline.map(e => `
          <div style="display:flex;gap:12px;margin:8px 0;align-items:flex-start">
            <div style="font-size:10px;color:var(--txt3);min-width:80px;padding-top:2px">${e.time}</div>
            <div>${e.icon}</div>
            <div style="font-size:11.5px;color:var(--txt2)">${e.msg}</div>
          </div>
        `).join(''));

            // Update Chart
            Charts.create('chart-rca-confidence', 'bar', ['Confidence Avg', 'Evidence Score', 'AI Consensus'], [{
              data: [conf, Math.min(100, Math.floor(conf * 0.95)), Math.min(100, Math.floor(conf * 1.05))],
              backgroundColor: ['#3b82f6', '#22c55e', '#a855f7'],
              borderRadius: 4
            }], { legend: false, yOpts: { max: 100, min: 0 } });

            // Auto-select Remote Target Device
            const targetSelect = document.getElementById('rca-target');
            if (targetSelect) {
              targetSelect.value = res.device_name;
              const d = DataService._devices.find(x => x.name === res.device_name);
              setEl('remote-target-ip', d ? d.ip : '—');
            }

            Notify.toast('🔬 RCA', 'Analisis selesai untuk ' + res.device_name, 'ok', 3000);
            LogStreamer.add('OK', 'RCA', '5-Why analysis completed for ' + id + ' · confidence: ' + conf + '%');

          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal menghubungi server untuk analisis RCA', 'err');
          }
        },
        async reanalyze() {
          const id = document.getElementById('rca-select').value;
          if (!id) {
            Notify.toast('⚠️ Warning', 'Pilih insiden terlebih dahulu', 'warn');
            return;
          }
          try {
            const resp = await fetch(`/api/rca/reanalyze/${id}`, { method: 'POST' });
            const res = await resp.json();
            if (resp.ok && res.status === 'SUCCESS') {
              Notify.toast('🔄 Re-Analyze', 'Permintaan Re-Analysis berhasil dikirim ke AI Core', 'ok');
              LogStreamer.add('OK', 'RCA', 'Force Re-Analysis triggered for incident ' + id);
              setTimeout(() => Panels.rca.analyze(), 4000);
            } else {
              Notify.toast('❌ Error', res.message || 'Gagal memicu re-analysis', 'err');
            }
          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal memicu re-analysis', 'err');
          }
        },
        async submitFeedback() {
          const incidentId = document.getElementById('rca-select').value;
          if (!incidentId) {
            Notify.toast('⚠️ Feedback', 'Pilih insiden terlebih dahulu', 'warn');
            return;
          }

          const ai_rca = document.getElementById('rca-ai-pred').value;
          let human_rca = document.getElementById('rca-human-gt').value;
          if (human_rca === 'Other / Manual Cause') {
            human_rca = document.getElementById('rca-manual-gt').value.trim();
            if (!human_rca) {
              Notify.toast('⚠️ Feedback', 'Tulis penyebab manual', 'warn');
              return;
            }
          }
          if (!human_rca) {
            Notify.toast('⚠️ Feedback', 'Pilih atau isi Ground Truth', 'warn');
            return;
          }

          const score = parseFloat(document.getElementById('rca-feedback-score').value);

          try {
            const resp = await fetch('/api/feedback', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                incident_id: parseInt(incidentId),
                ai_rca: ai_rca,
                human_rca: human_rca,
                score: score,
                reviewer: 'NOC_OPERATOR'
              })
            });
            const res = await resp.json();
            if (res && (res.success || res.status === 'SUCCESS' || res.status === 'success')) {
              Notify.toast('✅ Feedback', 'Ground Truth berhasil dikirim!', 'ok');
              LogStreamer.add('OK', 'RCA', `Feedback saved for incident ${incidentId} (Score: ${score})`);
            } else {
              Notify.toast('❌ Error', 'Gagal mengirim feedback: ' + (res.error || ''), 'err');
            }
          } catch (err) {
            console.error(err);
            Notify.toast('❌ Error', 'Gagal menghubungi server', 'err');
          }
        },
        async sendCmd(cmd) {
          const target = document.getElementById('rca-target').value;
          const resultEl = document.getElementById('rca-cmd-result');
          if (!target) { Notify.toast('⚠️ Remote', 'Pilih device target', 'warn'); return; }
          if (resultEl) resultEl.innerHTML = '<span style="color:var(--blue2)">⏳ Mengirim ' + cmd + ' ke ' + target + '...</span>';
          const r = await DataService.sendCommand(cmd, target);
          if (resultEl) resultEl.innerHTML = `<span style="color:var(--green2)">✅ ${cmd} → ${target}: ${r.message || 'SUCCESS'}</span>`;
          Notify.toast('🛠️ Remote', '' + cmd + ' sent to ' + target, 'ok', 3000);
          LogStreamer.add('OK', 'ORCH', cmd + ' executed on ' + target + ' · ' + r.status);
        },
        exportTimeline() {
          const txt = document.getElementById('rca-timeline').innerText;
          const a = document.createElement('a'); a.href = 'data:text/plain,' + encodeURIComponent(txt); a.download = 'rca-timeline.txt'; a.click();
          Notify.toast('📥 Export', 'Timeline diekspor', 'ok');
        }
      },

      /* ---- UNIFIED DAG ---- */


});
