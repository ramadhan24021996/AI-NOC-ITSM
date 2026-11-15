/* panels/training.js
 * Training Feedback panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      training: {
        _autoRefreshTimer: null,

        startAutoRefresh() {
          this.stopAutoRefresh();
          this._autoRefreshTimer = setInterval(() => {
            if (document.getElementById('p-training')?.classList.contains('active')) {
              this.load();
            }
          }, 5000);
        },

        stopAutoRefresh() {
          if (this._autoRefreshTimer) {
            clearInterval(this._autoRefreshTimer);
            this._autoRefreshTimer = null;
          }
        },

        async load() {
          try {
            const stats = await DataService.loadFeedbackStats();
            if (!stats) return;

            setEl('tr-correct', stats.correct_count);
            setEl('tr-incorrect', stats.incorrect_count);
            setEl('tr-pending', stats.pending_count || 0);
            setEl('tr-accuracy', (stats.accuracy_rate || 100).toFixed(1) + '%');
            setEl('tr-rag', stats.rag_count);
            setEl('bdg-training', stats.pending_count || stats.queue.length);
            setEl('tr-queue-count', stats.queue.length);

            const searchQ = (document.getElementById('tr-search-inp')?.value || '').trim().toLowerCase();
            const statusFilter = (document.getElementById('tr-status-select')?.value || '').trim();

            let queueItems = stats.queue || [];
            if (searchQ) {
              queueItems = queueItems.filter(inc => 
                String(inc.incident_id).includes(searchQ) || 
                (inc.device_name || '').toLowerCase().includes(searchQ) || 
                (inc.flag || '').toLowerCase().includes(searchQ)
              );
            }
            if (statusFilter) {
              queueItems = queueItems.filter(inc => inc.status === statusFilter);
            }

            const list = document.getElementById('tr-feedback-list');
            if (list) {
              list.innerHTML = queueItems.map(inc => {
                const confText = inc.confidence ? Math.round(inc.confidence * 100) + '%' : '-';
                const confVal = inc.confidence ? Math.round(inc.confidence * 100) : 0;
                const evidenceText = inc.evidence || '<span style="color:var(--txt3);font-style:italic;font-weight:400">Tidak ada rincian telemetri / payload.</span>';
                const actionText = inc.action || '<span style="color:var(--txt3);font-style:italic;font-weight:400">Belum ada hasil analisis AI.</span>';
                const statusBadge = inc.status === 'APPROVED' ? '<span class="tag tag-green">APPROVED</span>' :
                                    inc.status === 'PENDING_APPROVAL' ? '<span class="tag tag-orange"><i class="fa-solid fa-hourglass-half"></i> PENDING APPROVAL</span>' :
                                    inc.status === 'REJECTED' ? '<span class="tag tag-red">REJECTED</span>' : '<span class="tag tag-gray">PENDING REVIEW</span>';

                return `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 14px;gap:8px;margin-bottom:10px" id="fb-${inc.incident_id}">
              <div style="font-size:11.5px;font-weight:500;display:flex;align-items:center;justify-content:space-between;width:100%">
                <div style="display:flex;align-items:center;gap:6px">
                  <span><i class="fa-solid fa-desktop" style="color:var(--cyan);margin-right:4px"></i><b>${inc.device_name}</b></span>
                  <span style="color:var(--txt3)">•</span>
                  <code style="color:var(--orange2);background:rgba(249,115,22,.1);padding:1px 6px;border-radius:4px"><i class="fa-solid fa-tag" style="margin-right:4px"></i>${inc.flag}</code>
                  ${statusBadge}
                </div>
                <div style="font-size:10px;color:var(--txt2);display:flex;align-items:center;gap:8px">
                  <span><i class="fa-solid fa-hashtag" style="color:var(--blue);margin-right:2px"></i>ID: <b>${inc.incident_id}</b></span>
                  <span style="color:var(--txt3)">|</span>
                  <span title="Trace ID: ${inc.trace_id || '-'}"><i class="fa-solid fa-network-wired" style="color:var(--purple2);margin-right:2px"></i>Trace: <b>${(inc.trace_id || '').substring(0, 10)}...</b></span>
                  <span style="color:var(--txt3)">|</span>
                  <span><i class="fa-solid fa-brain" style="color:var(--pink);margin-right:4px"></i>Conf: <b style="color:${confVal >= 80 ? 'var(--green2)' : (confVal > 0 ? 'var(--orange2)' : 'var(--txt3)')}">${confText}</b></span>
                </div>
              </div>
              <div style="font-size:11px;color:var(--txt1);background:rgba(0,0,0,0.2);padding:6px 10px;border-radius:6px;width:100%;border-left:3px solid var(--purple2)">
                <div style="font-size:10px;color:var(--txt3);margin-bottom:2px"><i class="fa-solid fa-triangle-exclamation" style="color:var(--orange2);margin-right:4px"></i>Gejala / Telemetri Ringkasan:</div>
                <div style="font-weight:500">${evidenceText}</div>
              </div>
              <div style="font-size:11px;color:var(--txt1);background:rgba(0,0,0,0.2);padding:6px 10px;border-radius:6px;width:100%;border-left:3px solid var(--green2)">
                <div style="font-size:10px;color:var(--txt3);margin-bottom:2px"><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--green2);margin-right:4px"></i>Rekomendasi / Tindakan AI:</div>
                <div style="font-weight:600;color:var(--green2)">${actionText}</div>
              </div>
              <div style="display:flex;gap:8px;margin-top:4px;width:100%;justify-content:flex-end;align-items:center">
                ${inc.status === 'PENDING_APPROVAL' ? `
                  <button class="btn btn-warning btn-sm" style="padding:4px 12px" onclick="Panels.training.approveFeedback(${inc.incident_id})"><i class="fa-solid fa-user-check" style="margin-right:4px"></i>Persetujuan Reviewer (Approve RAG)</button>
                ` : ''}
                <button class="btn btn-success btn-sm" style="padding:4px 12px" onclick="Panels.training.markFeedback(${inc.incident_id},'correct','${inc.flag}')"><i class="fa-solid fa-circle-check" style="margin-right:4px"></i>Benar</button>
                <button class="btn btn-danger btn-sm" style="padding:4px 12px" onclick="Panels.training.markFeedback(${inc.incident_id},'incorrect','${inc.flag}')"><i class="fa-solid fa-circle-xmark" style="margin-right:4px"></i>Salah</button>
                <button class="btn btn-ghost btn-sm" style="padding:4px 10px" onclick="Panels.training.markFeedback(${inc.incident_id},'skip')"><i class="fa-solid fa-rotate-right" style="margin-right:4px"></i>Skip</button>
              </div>
            </div>`;
              }).join('') || '<div class="empty-state"><div class="es-icon"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i></div><div class="es-text">Tidak ada feedback pending matching kriteria.</div></div>';
            }

            // Calculate dynamic accuracy point for the chart
            const total = stats.correct_count + stats.incorrect_count;
            document.getElementById('chart-training-acc').parentElement.innerHTML = '<canvas id="chart-training-acc"></canvas>';
            
            if (total === 0) {
              Charts.create('chart-training-acc', 'doughnut', ['Belum Ada Data'], [
                { data: [1], backgroundColor: ['rgba(139,148,158,.1)'], borderWidth: 0 }
              ], { legend: false, cutout: '75%' });
            } else {
              Charts.create('chart-training-acc', 'doughnut', ['Benar (Verified)', 'Salah (Evaluasi Audit)'], [
                {
                  data: [stats.correct_count, stats.incorrect_count],
                  backgroundColor: ['rgba(34,197,94,.8)', 'rgba(239,68,68,.8)'],
                  borderWidth: 0,
                  hoverOffset: 4
                }
              ], { legend: true, cutout: '70%' });
            }
          } catch (err) {
            console.error('Error loading training panel:', err);
          }
        },

        async markFeedback(incidentId, type, flag = "") {
          const card = document.getElementById('fb-' + incidentId);

          if (type === 'skip') {
            if (card) card.remove();
            Notify.toast('⟳ Skipped', 'Feedback untuk insiden ' + incidentId + ' dilewati', 'info', 1500);
            return;
          }

          if (type === 'incorrect') {
            document.getElementById('rej-incident-id').value = incidentId;
            document.getElementById('rej-flag').value = flag;
            document.getElementById('rej-reason-text').value = '';
            document.getElementById('rej-human-rca').value = '';
            document.getElementById('modal-feedback-rejection').style.display = 'flex';
            return;
          }

          if (card) {
            card.style.opacity = '.5';
            card.style.pointerEvents = 'none';
          }

          const score = 1.0;
          try {
            const resp = await DataService.submitFeedback(incidentId, score, flag, 'Manual verification');
            if (resp && (resp.success || resp.status === 'APPROVED')) {
              if (card) card.remove();
              Notify.toast('📚 Feedback Approved', `Ditandai BENAR · OTel Trace: ${resp.trace_id || 'OK'}`, 'ok', 3000);
              LogStreamer.add('OK', 'TRAINING', `Feedback BENAR submitted for Incident ${incidentId} · Trace: ${resp.trace_id}`);
              this.load();
            } else {
              if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
              Notify.toast('❌ Gagal', resp ? resp.error : 'Gagal mengirim feedback', 'error', 3000);
            }
          } catch (err) {
            if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
            Notify.toast('❌ Error API', err.message, 'error', 3000);
          }
        },

        async confirmRejection() {
          const incidentId = document.getElementById('rej-incident-id').value;
          const flag = document.getElementById('rej-flag').value;
          const reason = (document.getElementById('rej-reason-text').value || '').trim();
          const humanRca = (document.getElementById('rej-human-rca').value || '').trim();

          if (!reason) {
            Notify.toast('⚠️ Input Wajib', 'Mohon isi Alasan / Catatan Evaluasi Manusia.', 'warn', 3000);
            return;
          }

          document.getElementById('modal-feedback-rejection').style.display = 'none';
          const card = document.getElementById('fb-' + incidentId);
          if (card) { card.style.opacity = '.5'; card.style.pointerEvents = 'none'; }

          try {
            const res = await DataService.fetch('/api/feedback', {
              method: 'POST',
              body: JSON.stringify({
                incident_id: parseInt(incidentId),
                score: 0.0,
                ai_rca: flag,
                human_rca: humanRca || reason,
                reviewer: window.currentUserRole || 'NOC_OPERATOR',
                rejection_reason: reason
              })
            });

            if (res && res.success) {
              if (card) card.remove();
              Notify.toast('🛡️ Feedback Evaluasi Tersimpan', `Dikirim ke Four-Eyes Reviewer Queue · Status: ${res.status}`, 'warn', 3500);
              LogStreamer.add('WARN', 'TRAINING', `Feedback SALAH (Evaluasi) submitted for Incident ${incidentId} · Status: ${res.status}`);
              this.load();
            } else {
              if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
              Notify.toast('❌ Gagal', res ? res.error : 'Gagal menyimpan evaluasi feedback', 'error', 3000);
            }
          } catch (err) {
            if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
            Notify.toast('❌ Error API', err.message, 'error', 3000);
          }
        },

        async approveFeedback(incidentId) {
          Notify.toast('⚡ Approving', `Reviewer memvalidasi RAG untuk Insiden ${incidentId}...`, 'info', 2000);
          try {
            const res = await DataService.fetch('/api/feedback/approve', {
              method: 'POST',
              body: JSON.stringify({ incident_id: incidentId, reviewer: 'SUPERVISOR' })
            });
            if (res && res.status === 'success') {
              Notify.toast('✅ RAG Ingested', `Persetujuan Four-Eyes selesai · Data terpublikasi ke RAG`, 'ok', 3000);
              this.load();
            } else {
              Notify.toast('❌ Gagal', res ? res.message : 'Gagal menyetujui feedback', 'error', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error', e.message, 'error', 3000);
          }
        },

        async export(format) {
          Notify.toast('📥 Exporting Audit', `Mengunduh riwayat feedback RAG (${format.toUpperCase()})...`, 'info', 2000);
          try {
            const resp = await fetch(`/api/feedback/export?format=${format}`);
            if (!resp.ok) throw new Error("Export failed");
            const checksum = resp.headers.get("X-Audit-Checksum-SHA256") || "UNKNOWN";
            const blob = await resp.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = `training_feedback_audit_${Date.now()}.${format}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            Notify.toast('✅ Export Completed', `File downloaded. SHA256 Integrity: ${checksum.substring(0, 16)}...`, 'ok', 4000);
          } catch (e) {
            Notify.toast('❌ Export Error', e.message, 'err', 3000);
          }
        },

        async sendTeacherPrompt() {
          const inp = document.getElementById('tr-teacher-input');
          const term = document.getElementById('tr-live-log-terminal');
          if (!inp || !term) return;
          const prompt = inp.value.trim();
          if (!prompt) return;
          inp.value = '';

          const ts = new Date().toLocaleTimeString();
          term.innerHTML += `<div style="color:#60a5fa;margin-top:6px;">[${ts}] 👨‍🏫 SUPERADMIN TEACHER PROMPT: "${prompt}"</div>`;
          term.innerHTML += `<div style="color:#fbbf24;">[${ts}] [AI REASONING] Processing query via 7-Stage Security Gateway & RAG Engine...</div>`;
          term.scrollTop = term.scrollHeight;

          try {
            const resp = await fetch(`/api/enterprise/chat/ai_assist?client_id=SUPERADMIN_TEACHER&query=${encodeURIComponent(prompt)}`);
            if (resp.ok) {
              const data = await resp.json();
              const resultText = (data.suggestion || data.warning || 'AI Response Generated').replace(/\n/g, '<br>');
              const escPrompt = encodeURIComponent(prompt);
              term.innerHTML += `<div style="color:#34d399;margin-top:4px;">[${ts}] 🤖 AI REASONING OUTPUT:<br>${resultText}</div>`;
              term.innerHTML += `<div style="margin-top:4px;display:flex;gap:6px;align-items:center;">
                <button class="btn btn-warning btn-xs" style="padding:2px 8px;font-size:10px;" onclick="Panels.training.teachAIInteractive('${escPrompt}')"><i class="fa-solid fa-graduation-cap" style="margin-right:4px"></i>Ajarkan Solusi Benar ke AI</button>
              </div>`;
              term.innerHTML += `<div style="color:#a78bfa;margin-top:4px;">[${ts}] 🛡️ SECURITY GATEWAY: Evaluated 0-Trust Policy · RAG Vector Auto-Persisted to <code>ai_discovered_knowledge.json</code></div>`;
            } else {
              term.innerHTML += `<div style="color:#ef4444;margin-top:4px;">[${ts}] ❌ API ERROR: ${resp.statusText}</div>`;
            }
          } catch (e) {
            term.innerHTML += `<div style="color:#ef4444;margin-top:4px;">[${ts}] ❌ ERROR: ${e.message}</div>`;
          }
          term.scrollTop = term.scrollHeight;
        },

        async teachAIInteractive(problemStr) {
          const prob = decodeURIComponent(problemStr || 'COS pada dasbor tidak ada pilihan tiket, BLANK PUTIH');
          const solution = prompt(`👨‍🏫 AJARKAN SOLUSI BENAR KE AI:\n\nMasalah: "${prob}"\n\nMasukkan langkah-langkah perbaikan / solusi yang benar yang harus dipelajari AI:`, "Coba tekan Ctrl + Shift + R untuk hard-refresh browser cache, atau periksa permission RBAC admin");
          if (!solution || !solution.trim()) return;

          Notify.toast('🎓 Teaching AI', 'Mengirimkan koreksi solusi Superadmin ke RAG Engine...', 'info', 2000);
          try {
            const resp = await fetch('/api/enterprise/chat/teach_ai', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ problem: prob, solution: solution.trim() })
            });
            if (resp.ok) {
              const res = await resp.json();
              Notify.toast('✅ AI Learned Solution!', res.message, 'ok', 4000);
              const term = document.getElementById('tr-live-log-terminal');
              if (term) {
                const ts = new Date().toLocaleTimeString();
                term.innerHTML += `<div style="color:#f59e0b;margin-top:6px;">[${ts}] 👨‍🏫 SUPERADMIN TEACHER CORRECTION REGISTERED:</div>`;
                term.innerHTML += `<div style="color:#a7f3d0;">  📌 Masalah: "${prob}"<br>  ✅ Solusi Benar: "${solution.trim()}"</div>`;
                term.innerHTML += `<div style="color:#38bdf8;">💾 [RAG STORE PERSISTED] Knowledge Item ${res.item_id || ''} saved to <code>ai_discovered_knowledge.json</code>!</div>`;
                term.scrollTop = term.scrollHeight;
              }
            } else {
              Notify.toast('❌ Gagal Mengajar AI', 'Gagal menyimpan solusi ke RAG', 'error', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error API', e.message, 'error', 3000);
          }
        }
      },


});
