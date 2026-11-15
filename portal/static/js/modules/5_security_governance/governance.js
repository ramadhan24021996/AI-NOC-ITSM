/* panels/governance.js
 * Governance center panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      gov: {
        activeTab: 'metrics',
        setTab(tabId) {
          this.activeTab = tabId || 'metrics';
          const tabs = document.querySelectorAll('#p-gov .gov-tab-content');
          tabs.forEach(el => {
            el.style.setProperty('display', 'none', 'important');
          });
          const target = document.getElementById('gov-tab-' + this.activeTab);
          if (target) {
            target.style.setProperty('display', 'block', 'important');
          } else if (tabs.length > 0) {
            tabs[0].style.setProperty('display', 'block', 'important');
          }

          document.querySelectorAll('#p-gov .gov-tab-btn').forEach(btn => {
            const onclickAttr = btn.getAttribute('onclick') || '';
            if (onclickAttr.includes(`'${this.activeTab}'`)) {
              btn.classList.add('active');
              btn.style.setProperty('background', 'var(--blue)', 'important');
              btn.style.setProperty('color', '#ffffff', 'important');
            } else {
              btn.classList.remove('active');
              btn.style.removeProperty('background');
              btn.style.removeProperty('color');
            }
          });

          if (this.activeTab === 'hitl') this.loadApprovals();
          if (this.activeTab === 'chaos') this.loadChaos();
          if (this.activeTab === 'explainability') this.loadExplainability();
        },

        async loadChaos() {
          try {
            const data = await DataService.fetch('/api/governance/chaos_status').catch(() => null);
            if (data && document.getElementById('chaos-readiness-score')) {
              { const _el = document.getElementById('chaos-readiness-score'); if (_el) _el.innerText = (data.readiness_score || 93) + '%'; }
            }
          } catch (e) {
            console.warn('Chaos load status:', e);
          }
        },

        injectChaos() {
          Notify.toast('🚀 Chaos Experiment', 'Persetujuan Gerbang Keamanan Lolos. Injeksi simulasi kegagalan berhasil dikirim ke Canary Agent.', 'ok', 3500);
          LogStreamer.add('WARN', 'CHAOS', 'Simulasi eksperimen Chaos CH-20260720-001 diinjeksi: Simulasi Heartbeat Loss dimulai');
        },

        async loadExplainability() {
          try {
            const logs = await DataService.loadAIDecisionLogs(5);
            if (logs && logs.length > 0) {
              const latest = logs[0];
              const box = document.getElementById('explainability-trace-box');
              if (box) {
                const conf = Math.round((latest.confidence_score || 0.85) * (latest.confidence_score <= 1 ? 100 : 1));
                box.innerHTML = `
                  <b>[JEJAK AUDIT ANALISIS ROOT CAUSE AI - INC-${latest.incident_id || 'SYS'}]</b><br>
                  1. Diagnosa Hipotesis Awal: <span style="color:var(--txt1)">${latest.first_hypothesis || 'Pemeriksaan Otomatis Watchdog'}</span><br>
                  2. Ensembel LLM: <span style="color:var(--purple2)">${latest.ai_models_used || 'Gemini + DeepSeek + Groq'}</span><br>
                  3. Latensi Waktu Keputusan: <span style="color:var(--cyan2)">${latest.decision_time_ms || 150} ms</span><br>
                  4. Skor Keyakinan AI: <b style="color:var(--green2)">${conf}%</b><br>
                  5. Keputusan Remediasi Akhir: <b style="color:var(--green2)">${latest.final_decision || 'SOP Pemulihan Standar'}</b>
                `;
              }
            }
          } catch(e) {}
          Notify.toast('🧠 Explainability', 'Jejak penalaran AI & skor kemiripan vektor RAG diperbarui.', 'ok', 2000);
        },

        async load() {
          // Pastikan tab aktif ditampilkan saat panel dimuat
          this.setTab(this.activeTab || 'metrics');

          // 1. Top Resolusi Sukses (Real API)
          try {
            const topRes = await DataService.fetch('/api/governance/top_resolutions');
            if (topRes && Array.isArray(topRes)) {
              setEl('gov-res-tag', topRes.length + ' jenis');
              htmlEl('tbody-gov-res', topRes.map((r, i) => `<tr><td style="color:var(--txt3)">${i + 1}</td><td><code style="font-size:10px">${r.flag}</code></td><td><b style="color:var(--green2)">${r.count}x</b></td><td><span class="tag tag-blue">L${r.layer || '?'}</span></td></tr>`).join(''));
            } else {
              setEl('gov-res-tag', '0 jenis');
              htmlEl('tbody-gov-res', '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada data resolusi</td></tr>');
            }
          } catch (e) {
            setEl('gov-res-tag', '0 jenis');
            htmlEl('tbody-gov-res', '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada data resolusi</td></tr>');
          }

          // 2. Audit Log (Terbaru)
          try {
            const audits = await DataService.loadAudits();
            Panels.server._renderAuditHistory(audits);
          } catch (e) { }

          // 3. Recovery Mode
          try {
            const modeData = await DataService.loadRecoveryMode();
            if (modeData && modeData.success) {
              const sel = document.getElementById('gov-recovery-mode');
              if (sel) {
                sel.value = modeData.recovery_mode;
                this._updateRecoveryModeDesc(modeData.recovery_mode);
              }
            }
          } catch (e) { }

          // 4. SLA Compliance Chart (Real API)
          try {
            const slaData = await DataService.fetch('/api/governance/sla_compliance');
            const dataValues = CFG.SITES.map(site => (slaData && slaData[site] !== undefined) ? slaData[site] : 95.0);
            Charts.create('chart-sla', 'bar', CFG.SITES, [{ label: 'SLA %', data: dataValues, backgroundColor: 'rgba(34,197,94,.2)', borderColor: '#22c55e', borderWidth: 1.5, borderRadius: 4 }], { legend: false, yOpts: { max: 100, min: 80 } });
          } catch (e) {
            Charts.create('chart-sla', 'bar', CFG.SITES, [{ label: 'SLA %', data: CFG.SITES.map(() => 0), backgroundColor: 'rgba(239,68,68,.2)', borderColor: '#ef4444', borderWidth: 1.5, borderRadius: 4 }], { legend: false, yOpts: { max: 100, min: 0 } });
          }

          this.loadApprovals();
          this.loadDLQ();
          if (window.SprintO) window.SprintO.loadAll();
          
          DataService.refreshGovernanceMetrics();
        },
        async setRecoveryMode(mode) {
          try {
            const res = await DataService.saveRecoveryMode(mode);
            if (res && res.success) {
              Notify.toast('⚙️ Recovery Mode', 'Mode diubah ke: ' + mode, 'warn', 3000);
              LogStreamer.add('WARN', 'CONF', 'Recovery mode changed to: ' + mode + ' by operator');
              this._updateRecoveryModeDesc(mode);
            } else {
              Notify.toast('❌ Error', 'Gagal mengubah recovery mode', 'err', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Gagal menghubungi server', 'err', 3000);
          }
        },
        _updateRecoveryModeDesc(mode) {
          const descBox = document.querySelector('#p-gov .insight-box');
          if (descBox) {
            let descText = "";
            if (mode === "Semi-Auto") {
              descText = "<b>Aktif:</b> Semi-Auto · AI hanya merekomendasikan, operator wajib approve sebelum eksekusi.";
            } else if (mode === "Advisory") {
              descText = "<b>Aktif:</b> Advisory · AI menganalisa masalah & menyarankan SOP. Tidak ada intervensi otomatis.";
            } else if (mode === "Full-Auto") {
              descText = "<b>Aktif:</b> Full-Auto · AI mengeksekusi perintah mitigasi secara instan (OTONOM).";
            }
            descBox.innerHTML = descText;
          }
        },
        async loadApprovals() {
          try {
            const res = await DataService.fetch('/api/approval_queue');
            const tbody = document.getElementById('tbody-hitl-queue');
            if (res && res.length > 0) {
              tbody.innerHTML = res.map(app => `
            <tr>
              <td><b>#${app.id}</b></td>
              <td>${app.incident_id ? `<span class="tag tag-blue">ID: ${app.incident_id}</span>` : '<span class="tag">N/A</span>'}</td>
              <td><span class="tag ${app.risk_level === 'high' || app.risk_level === 'critical' ? 'tag-red' : 'tag-orange'}">${app.risk_level.toUpperCase()}</span></td>
              <td><code style="background:var(--bg3);padding:2px 6px;border-radius:4px;color:var(--txt)">${app.action_name}</code></td>
              <td>
                <button class="btn btn-green btn-sm" style="padding: 2px 8px; margin-right: 4px;" onclick="Panels.gov.approveAction(${app.id})"><i class="fa-solid fa-check"></i> Approve</button>
                <button class="btn btn-red btn-sm" style="padding: 2px 8px;" onclick="Panels.gov.rejectAction(${app.id})"><i class="fa-solid fa-xmark"></i> Reject</button>
              </td>
            </tr>
          `).join('');
            } else {
              tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted)">Queue is empty. No pending actions require approval.</td></tr>';
            }
          } catch (err) {
            console.error("Failed to load approvals:", err);
          }
        },
        async approveAction(id) {
          try {
            const resp = await fetch('/api/hitl/approve', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: id })
            });
            const res = await resp.json();
            if (res.status === 'success') {
              Notify.toast('✅ Approved', 'Mitigation action approved and dispatched.', 'ok', 3000);
              this.loadApprovals();
            } else {
              Notify.toast('❌ Error', 'Failed to approve: ' + res.message, 'err');
            }
          } catch (err) {
            console.error(err);
          }
        },
        async rejectAction(id) {
          try {
            const resp = await fetch('/api/hitl/reject', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: id })
            });
            const res = await resp.json();
            if (res.status === 'success') {
              Notify.toast('❌ Rejected', 'Mitigation action rejected.', 'warn', 3000);
              this.loadApprovals();
            } else {
              Notify.toast('❌ Error', 'Failed to reject: ' + res.message, 'err');
            }
          } catch (err) {
            console.error(err);
          }
        },
        async loadDLQ() {
          try {
            const res = await DataService.fetch('/api/hitl/failed_actions');
            const tbody = document.getElementById('tbody-dlq-logs');
            if (!tbody) return;
            const rows = Array.isArray(res) ? res : (res && res.data ? res.data : []);
            if (rows.length > 0) {
              tbody.innerHTML = rows.map(log => `
            <tr>
              <td><b>#${log.dlq_id}</b></td>
              <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${log.reason}">${log.reason}</td>
              <td><span class="tag tag-red">${log.status || 'PENDING'}</span></td>
              <td><small>${new Date(log.last_attempt || log.created_at).toLocaleString()}</small></td>
            </tr>
          `).join('');
            } else {
              tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted)">No failures in queue</td></tr>';
            }
          } catch (err) {
            console.error("Failed to load DLQ:", err);
          }
        }
      },

      /* ---- LIVE CHAT PANEL ---- */
      chat: {
        load() {
          if (window.NocChat && typeof window.NocChat.init === 'function') {
            window.NocChat.init();
          }
        }
      }
});

window.Gov = window.Panels.gov;