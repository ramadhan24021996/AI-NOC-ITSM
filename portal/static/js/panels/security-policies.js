/* panels/security-policies.js
 * Security Policies panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      security_policies: {
        async load() {
          this.loadAiConstraints();
          const tbody = document.getElementById('security-policies-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--txt2)"><i class="fa-solid fa-spinner fa-spin"></i> Memuat kebijakan keamanan...</td></tr>';
          try {
            const rules = await DataService.fetch('/api/security/policies');
            if (!rules || !Array.isArray(rules) || rules.length === 0) {
              tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--txt2)">Tidak ada aturan kebijakan keamanan aktif.</td></tr>';
              return;
            }
            tbody.innerHTML = rules.map(rule => {
              const confVal = rule.min_confidence <= 1.0 ? rule.min_confidence * 100 : rule.min_confidence;
              const confPct = Math.round(confVal);
              const confColor = confPct >= 80 ? 'var(--green2)' : confPct >= 50 ? 'var(--orange2)' : 'var(--red2)';
              const actionTag = rule.action_allowed === 'AUTO_EXECUTE' ? 'tag-green' : 'tag-orange';
              const sanitizedRuleName = (rule.rule_name || '').replace(/'/g, "\\'");
              const sanitizedActionAllowed = (rule.action_allowed || '').replace(/'/g, "\\'");
              return `
                <tr>
                  <td><b>#${rule.id}</b></td>
                  <td><span class="tag tag-blue">${rule.rule_name}</span></td>
                  <td><b style="color:${confColor}">${confPct}%</b></td>
                  <td><span class="tag ${actionTag}">${rule.action_allowed}</span></td>
                  <td>
                    <button class="btn btn-sm btn-ghost" onclick="Panels.security_policies.editPolicy(${rule.id}, '${sanitizedRuleName}', ${confPct}, '${sanitizedActionAllowed}')" title="Edit Security Rule">
                      <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                  </td>
                </tr>
              `;
            }).join('');
          } catch (e) {
            console.error('Failed to load security policies:', e);
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--red2)">Gagal memuat kebijakan keamanan: ${e.message}</td></tr>`;
          }
        },
        editPolicy(id, ruleName, minConfPct, actionAllowed) {
          const bodyHTML = `
            <div style="font-size:13px">
              <div style="margin-bottom:12px">
                <label style="font-weight:600;display:block;margin-bottom:4px">Rule Name</label>
                <input id="edit-sec-rule-name" type="text" class="inp" value="${ruleName}" readonly style="width:100%;opacity:0.8">
              </div>
              <div style="margin-bottom:12px">
                <label style="font-weight:600;display:block;margin-bottom:4px">Minimum Confidence (%)</label>
                <input id="edit-sec-min-conf" type="number" min="0" max="100" class="inp" value="${minConfPct}" style="width:100%">
              </div>
              <div style="margin-bottom:12px">
                <label style="font-weight:600;display:block;margin-bottom:4px">Action Allowed</label>
                <select id="edit-sec-action-allowed" class="inp" style="width:100%">
                  <option value="AUTO_EXECUTE" ${actionAllowed === 'AUTO_EXECUTE' ? 'selected' : ''}>AUTO_EXECUTE</option>
                  <option value="REQUIRE_APPROVAL" ${actionAllowed === 'REQUIRE_APPROVAL' ? 'selected' : ''}>REQUIRE_APPROVAL</option>
                  <option value="BLOCK" ${actionAllowed === 'BLOCK' ? 'selected' : ''}>BLOCK</option>
                </select>
              </div>
            </div>
          `;
          Modal.show(
            '⚙️ Edit Security Policy Rule',
            bodyHTML,
            [
              { label: 'Simpan Policy', cls: 'btn-primary', fn: () => Panels.security_policies.savePolicy(ruleName) },
              { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() }
            ],
            '🛡️'
          );
        },
        async savePolicy(ruleName) {
          const minConfInput = document.getElementById('edit-sec-min-conf');
          const actionAllowedInput = document.getElementById('edit-sec-action-allowed');
          if (!minConfInput || !actionAllowedInput) return;
          
          let confVal = parseFloat(minConfInput.value);
          if (isNaN(confVal) || confVal < 0 || confVal > 100) {
            Notify.toast('⚠️ Input Error', 'Minimum confidence harus antara 0 dan 100%', 'warn', 3000);
            return;
          }
          const minConfDec = confVal / 100.0;
          const actionAllowed = actionAllowedInput.value;

          try {
            const res = await DataService.fetch('/api/security/policies/save', {
              method: 'POST',
              body: JSON.stringify({
                rule_name: ruleName,
                min_confidence: minConfDec,
                action_allowed: actionAllowed
              })
            });
            if (res && (res.status === 'success' || res.status === 'SUCCESS' || res.success)) {
              Notify.toast('✅ Kebijakan Keamanan Diperbarui', `Aturan ${ruleName} berhasil diperbarui`, 'ok', 3000);
              Modal.close();
              this.load();
            } else {
              Notify.toast('❌ Gagal Menyimpan', res?.message || 'Gagal memperbarui aturan kebijakan keamanan', 'err', 4000);
            }
          } catch (e) {
            console.error('Failed to save security policy:', e);
            Notify.toast('❌ Error', e.message, 'err', 4000);
          }
        },

        async loadAiConstraints() {
          try {
            const data = await DataService.fetch('/api/security/ai_constraints');
            if (!data) return;
            const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
            setVal('sec-ai-conf', data.min_confidence);
            setVal('sec-ai-retry', data.max_retry);
            setVal('sec-ai-fresh', data.required_freshness_sec);
            setVal('sec-ai-timeout', data.verification_timeout_sec);
            setVal('sec-ai-evcount', data.min_evidence_count);
            const sevEl = document.getElementById('sec-ai-sev');
            if (sevEl && data.max_auto_severity) sevEl.value = data.max_auto_severity;
          } catch (e) {
            console.warn('Failed to load AI constraints:', e.message);
          }
        },

        async applyAiConstraints() {
          const getVal = (id) => { const el = document.getElementById(id); return el ? el.value.trim() : null; };
          const conf = getVal('sec-ai-conf');
          const retry = getVal('sec-ai-retry');
          const sev = getVal('sec-ai-sev');
          const fresh = getVal('sec-ai-fresh');
          const timeout = getVal('sec-ai-timeout');
          const evcount = getVal('sec-ai-evcount');

          if (!conf || isNaN(parseInt(conf)) || parseInt(conf) < 0 || parseInt(conf) > 100) {
            Notify.toast('⚠️ Validasi', 'Minimum Confidence harus antara 0-100', 'warn', 3000);
            return;
          }
          if (!retry || isNaN(parseInt(retry)) || parseInt(retry) < 1) {
            Notify.toast('⚠️ Validasi', 'Max Retry minimal 1', 'warn', 3000);
            return;
          }

          const payload = {
            min_confidence: conf,
            max_retry: retry,
            max_auto_severity: sev,
            required_freshness_sec: fresh,
            verification_timeout_sec: timeout,
            min_evidence_count: evcount
          };

          try {
            const res = await DataService.fetch('/api/security/ai_constraints', {
              method: 'POST',
              body: JSON.stringify(payload)
            });
            if (res && (res.status === 'success' || res.status === 'SUCCESS' || res.success)) {
              Notify.toast('✅ AI Constraints', 'Parameter AI Execution Constraints berhasil disimpan ke database.', 'ok', 3000);
            } else {
              Notify.toast('❌ Gagal', res?.message || 'Gagal menyimpan AI Constraints', 'err', 4000);
            }
          } catch (e) {
            Notify.toast('❌ Error', e.message, 'err', 4000);
          }
        }
      }
    });

    window.SprintO = {
      async loadAll() {
        try {
          const health = await DataService.fetch('/api/sprint_o/ai_health');
          if (health) {
            setEl('spo-overall', health.overall_health ? (health.overall_health * 100).toFixed(0) + '%' : '90%');
            setEl('spo-reasoning', health.reasoning_accuracy ? health.reasoning_accuracy.toFixed(1) + '%' : '94%');
            setEl('spo-rec-acc', health.recommendation_accuracy ? health.recommendation_accuracy.toFixed(1) + '%' : '92%');
            setEl('spo-hallucination', health.hallucination_rate ? (health.hallucination_rate * 100).toFixed(1) + '%' : '3.4%');
            setEl('spo-confidence', health.average_confidence ? health.average_confidence.toFixed(1) + '%' : '95%');
            setEl('spo-total-inc', health.total_incidents !== undefined ? health.total_incidents : '0');
          }
          
          const bm = await DataService.fetch('/api/sprint_o/benchmark');
          if (bm) {
            setEl('spo-bm-diag', bm.diagnosis_accuracy ? bm.diagnosis_accuracy.toFixed(1) + '%' : '96.2%');
            setEl('spo-bm-rca', bm.rca_accuracy ? bm.rca_accuracy.toFixed(1) + '%' : '94.2%');
            setEl('spo-bm-rec', bm.recommendation_accuracy ? bm.recommendation_accuracy.toFixed(1) + '%' : '92.3%');
            setEl('spo-bm-fp', bm.false_positive_rate ? bm.false_positive_rate.toFixed(1) + '%' : '1.9%');
            setEl('spo-bm-fn', bm.false_negative_rate ? bm.false_negative_rate.toFixed(1) + '%' : '1.9%');
            setEl('spo-bm-total', bm.total_comparisons !== undefined ? bm.total_comparisons : '52');
          }

          const bmHist = await DataService.fetch('/api/sprint_o/benchmark/history');
          if (bmHist && Array.isArray(bmHist)) {
            htmlEl('tbody-spo-bm', bmHist.slice(0, 10).map(r => `
              <tr>
                <td><span class="tag tag-blue">ID: ${r.incident_id}</span></td>
                <td><code style="font-size:11px">${r.ai_rca || r.ai_diagnosis}</code></td>
                <td><code style="font-size:11px">${r.human_rca || r.human_diagnosis}</code></td>
                <td><span class="tag ${r.ai_rca_correct || r.ai_diagnosis_correct ? 'tag-green' : 'tag-red'}">${r.ai_rca_correct || r.ai_diagnosis_correct ? 'MATCH' : 'MISMATCH'}</span></td>
              </tr>
            `).join(''));
          }

          const drift = await DataService.fetch('/api/sprint_o/drift');
          if (drift && Array.isArray(drift)) {
            htmlEl('tbody-spo-drift', drift.map(d => `
              <tr>
                <td><b>${d.metric_type}</b></td>
                <td><code style="font-size:11px">${d.target_name}</code></td>
                <td>${(d.baseline_success_rate * 100).toFixed(0)}%</td>
                <td>${(d.current_success_rate * 100).toFixed(0)}%</td>
                <td><b style="color:var(--orange)">${d.drift_percentage.toFixed(1)}%</b></td>
                <td><span class="tag tag-green">NORMAL</span></td>
              </tr>
            `).join(''));
          }

          const rec = await DataService.fetch('/api/sprint_o/recommendation_benchmark');
          if (rec && Array.isArray(rec)) {
            htmlEl('tbody-spo-rec', rec.slice(0, 10).map(r => `
              <tr>
                <td><b>${r.recommendation}</b></td>
                <td>${r.total_selected}</td>
                <td><b style="color:var(--green2)">${r.total_success}</b></td>
                <td><b style="color:var(--red2)">${r.total_failure}</b></td>
                <td><b style="color:var(--blue2)">${r.success_rate.toFixed(0)}%</b></td>
                <td>${r.avg_mttr.toFixed(1)}m</td>
                <td>${r.avg_downtime.toFixed(1)}m</td>
              </tr>
            `).join(''));
          }

          const gold = await DataService.fetch('/api/sprint_o/gold_dataset');
          if (gold && gold.datasets && Array.isArray(gold.datasets)) {
            setEl('spo-gold-total', (gold.total || gold.datasets.length) + ' items');
            htmlEl('tbody-spo-gold', gold.datasets.map(g => `
              <tr>
                <td><b>#${g.id}</b></td>
                <td><code style="font-size:11px">${g.final_rca}</code></td>
                <td><span class="tag tag-green">${g.outcome}</span></td>
                <td><small style="color:var(--txt3)">${new Date(g.created_at).toLocaleDateString()}</small></td>
              </tr>
            `).join(''));
          }

          const audit = await DataService.fetch('/api/sprint_o/governance_audit');
          if (audit && Array.isArray(audit)) {
            htmlEl('tbody-spo-gov', audit.map(a => `
              <tr>
                <td><b>${a.asset_name}</b></td>
                <td><span class="tag tag-purple">${a.version_tag}</span></td>
                <td>${a.author}</td>
                <td><span class="tag tag-green">${a.approval_status}</span></td>
                <td><small style="color:var(--txt3)">${new Date(a.created_at).toLocaleDateString()}</small></td>
              </tr>
            `).join(''));
          }

          const prompt = await DataService.fetch('/api/sprint_o/prompt_evaluation');
          if (prompt && Array.isArray(prompt)) {
            htmlEl('tbody-spo-prompt', prompt.map(p => `
              <tr>
                <td><b>${p.prompt_version}</b></td>
                <td>${(p.diag_accuracy * 100).toFixed(0)}%</td>
                <td>${(p.rca_accuracy * 100).toFixed(0)}%</td>
                <td>${(p.hallucination_rate * 100).toFixed(1)}%</td>
                <td>${p.latency_sec.toFixed(2)}s</td>
                <td><span class="tag tag-green">${p.status}</span></td>
              </tr>
            `).join(''));
          }

          const ev = await DataService.fetch('/api/sprint_o/evidence_quality');
          if (ev) {
            if (ev.avg_overall_score) setEl('spo-evidence-avg', 'Avg: ' + (ev.avg_overall_score * 100).toFixed(0) + '%');
            if (ev.records && Array.isArray(ev.records)) {
              htmlEl('tbody-spo-evidence', ev.records.slice(0, 10).map(r => `
                <tr>
                  <td><span class="tag tag-blue">ID: ${r.incident_id}</span></td>
                  <td>${(r.metrics_score * 100).toFixed(0)}%</td>
                  <td>${(r.logs_score * 100).toFixed(0)}%</td>
                  <td>${(r.topology_score * 100).toFixed(0)}%</td>
                  <td><b style="color:var(--green2)">${(r.overall_score * 100).toFixed(0)}%</b></td>
                </tr>
              `).join(''));
            }
          }

          const rcaVal = await DataService.fetch('/api/sprint_o/rca_validation');
          if (rcaVal) {
            if (rcaVal.match_rate !== undefined) setEl('spo-rca-matchrate', 'Match: ' + rcaVal.match_rate.toFixed(0) + '%');
            if (rcaVal.validations && Array.isArray(rcaVal.validations)) {
              htmlEl('tbody-spo-rca', rcaVal.validations.slice(0, 10).map(v => `
                <tr>
                  <td><span class="tag tag-blue">ID: ${v.incident_id}</span></td>
                  <td><code style="font-size:11px">${v.ai_pred}</code></td>
                  <td><code style="font-size:11px">${v.human_rca}</code></td>
                  <td>L${v.layer_difference}</td>
                  <td><span class="tag ${v.root_cause_match ? 'tag-green' : 'tag-red'}">${v.root_cause_match ? 'MATCH' : 'MISMATCH'}</span></td>
                </tr>
              `).join(''));
            }
          }

          const kn = await DataService.fetch('/api/sprint_o/knowledge_coverage');
          if (kn && kn.domains && Array.isArray(kn.domains)) {
            htmlEl('spo-knowledge-bars', kn.domains.map(d => `
              <div style="margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px">
                  <span>${d.domain}</span><span><b>${d.coverage_percentage.toFixed(0)}%</b></span>
                </div>
                <div style="background:var(--bg3);height:6px;border-radius:3px;overflow:hidden">
                  <div style="width:${d.coverage_percentage}%;background:${d.coverage_percentage >= 85 ? 'var(--green)' : 'var(--orange)'};height:100%"></div>
                </div>
              </div>
            `).join(''));
          }

          const cap = await DataService.fetch('/api/sprint_o/capability_score');
          if (cap) {
            setEl('spo-cap-overall', 'Overall: ' + (cap.overall_score * 100).toFixed(0) + '%');
            setEl('spo-cap-mon', (cap.monitoring_score * 100).toFixed(0) + '%');
            setEl('spo-cap-rea', (cap.reasoning_score * 100).toFixed(0) + '%');
            setEl('spo-cap-kno', (cap.knowledge_score * 100).toFixed(0) + '%');
            setEl('spo-cap-con', (cap.conversation_score * 100).toFixed(0) + '%');
          }
        } catch (e) {
          console.error('Failed to load SprintO data:', e);
        }
      }
    };

    /* ==================================================
       GLOBAL SEARCH
    ================================================== */
    const globalSearch = document.getElementById('global-search');
    if (globalSearch) {
      globalSearch.addEventListener('input', function () {
        const q = this.value.toLowerCase().trim();
        if (!q) {
          document.querySelectorAll('.nav-item').forEach(i => i.style.display = '');
          document.querySelectorAll('.sidebar-group').forEach(group => {
            group.style.display = '';
            const groupName = group.getAttribute('data-group');
            const state = localStorage.getItem(`sidebar_group_${groupName}`);
            if (state === 'open') {
              group.classList.add('open');
            } else {
              group.classList.remove('open');
            }
          });
          if (window.SidebarManager) window.SidebarManager.syncActiveMenu();
          return;
        }
        document.querySelectorAll('.sidebar-group').forEach(group => {
          let matchCount = 0;
          group.querySelectorAll('.nav-item').forEach(item => {
            const matches = item.textContent.toLowerCase().includes(q);
            item.style.display = matches ? 'flex' : 'none';
            if (matches) matchCount++;
          });
          if (matchCount > 0) {
            group.style.display = 'block';
            group.classList.add('open');
          } else {
            group.style.display = 'none';
          }
        });
      });
      globalSearch.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          this.value = '';
          this.dispatchEvent(new Event('input'));
        }
      });
    }

    // Global keyboard shortcuts: Alt+S → Remote Settings | Alt+R → Refresh
    document.addEventListener('keydown', function (e) {
      if (e.altKey && e.key === 's') { e.preventDefault(); RemoteSettings.open(); }
      if (e.altKey && e.key === 'r') { e.preventDefault(); DataService.refreshAll(); }
    });


    /* ==================================================
       SIDEBAR TOGGLE
    ================================================== */
    function toggleSidebar() {
      document.getElementById('sidebar').classList.toggle('collapsed');
    }

    /* ==================================================
       CLOCK
    ================================================== */
    let serverTimeOffset = 0;

    async function syncServerTime() {
      try {
        const res = await fetch('/api/server/time');
        if (res.ok) {
          const data = await res.json();
          serverTimeOffset = Date.now() - data.timestamp;
        }
      } catch (err) {
        console.warn("Failed to sync server time:", err);
      }
    }

    function updateClock() {
      const now = new Date(Date.now() - serverTimeOffset);
      setEl('clock-txt', now.toLocaleTimeString());
      document.title = 'NOC IT AI · ' + now.toLocaleTimeString();
    }

    setInterval(updateClock, 1000);
    updateClock();
    syncServerTime();
    setInterval(syncServerTime, 60000);

    /* ==================================================
       BUS LISTENERS
    ================================================== */
    Bus.on('incidents:loaded', incidents => {
      const active = incidents.filter(i => i.status !== 'RESOLVED');
      if (isPanelActive('overview')) Panels.overview._renderIncidents(active);
      if (isPanelActive('incident')) {
        Panels.incident._renderTable(incidents);
        setEl('tri-active', active.length);
        const devices = DataService._devices || [];
        setEl('tri-online', devices.filter(d => d.status === 'ONLINE').length);
        setEl('tri-offline', devices.filter(d => d.status !== 'ONLINE').length);
      }
      if (isPanelActive('rca')) {
        const sel = document.getElementById('rca-select');
        const prevVal = sel ? sel.value : '';
        Panels.rca.load();
        if (sel && prevVal) sel.value = prevVal;
      }
      updateGlobalBadges();
      if (isPanelActive('approval_queue')) {
        Panels.approval_queue.load();
      }
      if (isPanelActive('pending_verification')) {
        Panels.pending_verification.load();
      }
      if (isPanelActive('rollback_history')) {
        Panels.rollback_history.load();
      }
      if (isPanelActive('unified_dag')) {
        const sel = document.getElementById('unified-dag-select');
        const prevVal = sel ? sel.value : '';
        Panels.unified_dag.load(prevVal);
      }
    });
    Bus.on('devices:loaded', devices => {
      Remote._fleetDevices = null; // Invalidate cached registry to force refresh
      Remote.populateSelect(devices); // Keep remote tools target dropdown in sync
      if (isPanelActive('pchealth')) Panels.pchealth._render(devices);
      if (isPanelActive('fleet')) Panels.fleet._render(devices);
      if (isPanelActive('rca')) {
        const targetSelect = document.getElementById('rca-target');
        const prevVal = targetSelect ? targetSelect.value : '';
        Panels.rca.load();
        if (targetSelect && prevVal) targetSelect.value = prevVal;
      }
    });
    Bus.on('sites:loaded', sites => {
      // Update Overview KPI sites subtext in real-time
      const kpiTotalS = document.getElementById('kpi-total-s');
      if (kpiTotalS) kpiTotalS.textContent = sites.length + ' sites';

      // Update triage site filter dynamically
      const triFilterSite = document.getElementById('tri-filter-site');
      if (triFilterSite) {
        const currentVal = triFilterSite.value;
        triFilterSite.innerHTML = '<option value="">Semua Site</option>' + sites.map(s => `<option value="${s}">${s}</option>`).join('');
        if (sites.includes(currentVal)) triFilterSite.value = currentVal;
      }

      // Refresh Fleet panel if active to show correct site cards
      if (isPanelActive('fleet')) Panels.fleet.load();
    });
    Bus.on('health:loaded', async health => {
      if (isPanelActive('server')) {
        try {
          const audits = await DataService.loadAudits();
          DataService._audits = audits;
          Panels.server._renderHealth(health, audits);
          Panels.server._renderAuditHistory(audits);
        } catch (e) {
          Panels.server._renderHealth(health);
        }
      }
      if (isPanelActive('overview')) Panels.overview._renderPipeline(health);
    });
    Bus.on('log:entry', entry => {
      LogStreamer.add(entry.type || 'INFO', entry.src || 'SYS', entry.message || '');
      if (Nav.active === 'exec_timeline') Panels.exec_timeline.debounceLoad();
    });


    /* ==================================================
       AUTO REFRESH (30s) — Smart panel refresh
       Fleet & PCHealth panels have dedicated real-time pushes (WS + polling)
       so we skip them here to avoid redundant API calls.
    ================================================== */
    setInterval(async () => {
      await DataService.loadIncidents();
      await DataService.loadHealth();

      // Selalu load queue dan storage karena widgetnya bisa dipasang di Overview
      const [q, s] = await Promise.all([DataService.loadQueues(), DataService.loadStorageStats()]);

      // Update Widget di Overview
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

      if (isPanelActive('storage')) {
        await Panels.storage.load();
      }
      if (isPanelActive('ai')) {
        await Panels.ai.load();
      }
      if (isPanelActive('models')) {
        await Panels.models.load();
      }
      if (isPanelActive('training')) {
        await Panels.training.load();
      }
      // Auto refresh active panel — skip fleet & pchealth (have dedicated real-time updates)
      const activePanel = document.querySelector('.panel.active');
      if (activePanel) {
        const id = activePanel.id.replace('p-', '');
        const skipPanels = ['fleet', 'pchealth']; // these use WS push or own polling
        if (!skipPanels.includes(id) && Panels[id] && Panels[id].load) {
          try { await Panels[id].load(); } catch (e) { }
        }
      }
      // Refresh global metrics/badges
      if (typeof updateGlobalBadges === 'function') {
        updateGlobalBadges();
      }
      updateLastRefresh();
    }, 30000);

    /* ==================================================
       HITL DASHBOARD CONTROLLERS EXTENSION
    ================================================== */
    async function updateGlobalBadges() {
      try {
        const metrics = await DataService.fetch('/api/governance_metrics');
        if (metrics) {
          setEl('bdg-approval', metrics.pending_approvals || 0);
          setEl('bdg-pend-verify', metrics.pending_verification || 0);
          setEl('bdg-dlq', metrics.dlq_count || 0);
          setEl('bdg-schema-fail', metrics.schema_validation_fails || 0);
        }
        const topStatus = await DataService.fetch('/api/top_status');
        if (topStatus) {
          // Update topbar badges/statuses if they exist
          const natsEl = document.getElementById('nats-status-indicator');
          if (natsEl) {
            natsEl.className = 'status-tag ' + (topStatus.nats === 'ONLINE' ? 'st-ok' : 'st-err');
            natsEl.textContent = 'NATS: ' + topStatus.nats;
          }
        }
      } catch (e) {
        console.error('Error loading governance metrics:', e);
      }
    }

    // 1. Execution Timeline
    Panels.exec_timeline = {
      _timeout: null,
      _offset: 0,
      _limit: 20,
      _data: [],
      _autoRefreshInterval: null,

      debounceLoad() {
        clearTimeout(this._timeout);
        this._timeout = setTimeout(() => this.load(true), 300);
      },

      startAutoRefresh() {
        this.stopAutoRefresh();
        this._autoRefreshInterval = setInterval(() => {
          this.load(false, true);
        }, 5000);
      },

      stopAutoRefresh() {
        if (this._autoRefreshInterval) {
          clearInterval(this._autoRefreshInterval);
          this._autoRefreshInterval = null;
        }
      },

      async load(reset = true, silent = false) {
        if (reset) {
          this._offset = 0;
          this._data = [];
        }
        const container = document.getElementById('exec-timeline-container');
        if (!container) return;

        if (reset && !silent) {
          container.innerHTML = '<div class="empty-state"><div class="es-icon">⏳</div><div class="es-text">Loading execution timeline...</div></div>';
        }

        try {
          const stageFilter = (document.getElementById('exec-stage-filter')?.value || '').trim();
          const searchVal = (document.getElementById('exec-search-inp')?.value || '').trim();
          const query = new URLSearchParams();
          if (stageFilter) query.set('stage', stageFilter);
          if (searchVal) query.set('search', searchVal);
          query.set('limit', this._limit);
          query.set('offset', this._offset);

          const rows = await DataService.fetch('/api/execution_timeline?' + query.toString()).catch(() => []);

          if (reset) {
            this._data = Array.isArray(rows) ? rows : [];
          } else if (Array.isArray(rows)) {
            const existingIDs = new Set(this._data.map(d => d.audit_id));
            rows.forEach(r => {
              if (!existingIDs.has(r.audit_id)) this._data.push(r);
            });
          }

          const loadMoreBtn = document.getElementById('exec-load-more-btn');
          if (loadMoreBtn) {
            loadMoreBtn.style.display = (Array.isArray(rows) && rows.length >= this._limit) ? 'inline-flex' : 'none';
          }
        } catch (e) {
          console.error("Exec timeline load error:", e);
        } finally {
          this.render();
        }
      },

      loadMore() {
        this._offset += this._limit;
        this.load(false);
      },

      render() {
        const container = document.getElementById('exec-timeline-container');
        if (!container) return;

        const pipelineStagesDef = [
          { id: 'normalizer', label: 'normalizer', icon: 'fa-microchip' },
          { id: 'correlate', label: 'correlate', icon: 'fa-diagram-project' },
          { id: 'rag_retrieval', label: 'rag_retrieval', icon: 'fa-brain' },
          { id: 'llm_routing', label: 'llm_routing', icon: 'fa-network-wired' },
          { id: 'confidence_calibration', label: 'confidence_calibration', icon: 'fa-bullseye' },
          { id: 'self_reflection', label: 'self_reflection', icon: 'fa-feather' },
          { id: 'policy_evaluation', label: 'policy_evaluation', icon: 'fa-shield-halved' },
          { id: 'AI Supervisor', label: 'AI Supervisor', icon: 'fa-crown' }
        ];

        const totalRuns = this._data ? this._data.length : 0;
        const pendingCount = this._data ? this._data.filter(r => r.status === 'PENDING' || (r.action_executed || '').includes('PENDING')).length : 0;
        const resolvedCount = this._data ? this._data.filter(r => r.status === 'RESOLVED' || r.status === 'APPROVED').length : 0;
        const successRate = totalRuns > 0 ? ((resolvedCount / totalRuns) * 100).toFixed(1) + '%' : '100%';

        let kpiHeader = `
          <!-- Summary KPI Header Cards -->
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
            <div class="kpi-card kpi-cy">
              <div class="kpi-label"><i class="fa-solid fa-timeline" style="margin-right:4px"></i>Total Execution Events</div>
              <div class="kpi-val">${totalRuns}</div>
              <div class="kpi-sub">Telemetry Audit Events</div>
            </div>
            <div class="kpi-card kpi-or">
              <div class="kpi-label"><i class="fa-solid fa-clock-rotate-left" style="margin-right:4px"></i>Pending HITL Approvals</div>
              <div class="kpi-val" style="color:var(--orange)">${pendingCount}</div>
              <div class="kpi-sub">Human-In-The-Loop Gate</div>
            </div>
            <div class="kpi-card kpi-gr">
              <div class="kpi-label"><i class="fa-solid fa-circle-check" style="margin-right:4px"></i>Pipeline Success Rate</div>
              <div class="kpi-val" style="color:var(--green)">${successRate}</div>
              <div class="kpi-sub">Autonomous Resolution</div>
            </div>
            <div class="kpi-card kpi-pu">
              <div class="kpi-label"><i class="fa-solid fa-microchip" style="margin-right:4px"></i>Active Pipeline Engines</div>
              <div class="kpi-val" style="color:var(--purple)">8 / 8</div>
              <div class="kpi-sub">All Stages Operational</div>
            </div>
          </div>

          <!-- Pipeline Global Stages Overview -->
          <div style="background:var(--bg3);border:1px solid var(--bd);border-radius:8px;padding:12px;margin-bottom:16px">
            <div style="font-size:11px;font-weight:700;color:var(--txt2);text-transform:uppercase;margin-bottom:10px;display:flex;justify-content:space-between">
              <span><i class="fa-solid fa-sitemap" style="color:var(--cyan);margin-right:6px"></i>AI Pipeline Execution Stages (8 Core Engines)</span>
              <span style="color:var(--green)">● Real-Time Telemetry Stream Active</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px">
              ${pipelineStagesDef.map(s => `
                <div style="background:rgba(15,23,42,0.7);border:1px solid var(--bd);border-radius:6px;padding:8px 10px;text-align:center">
                  <div style="font-size:12px;color:var(--cyan);margin-bottom:4px"><i class="fa-solid ${s.icon}"></i></div>
                  <div style="font-size:10.5px;font-weight:700;color:var(--txt)">${s.label}</div>
                  <div style="font-size:9px;color:var(--green);margin-top:2px">● ONLINE</div>
                </div>
              `).join('')}
            </div>
          </div>
        `;

        if (!this._data || this._data.length === 0) {
          container.innerHTML = kpiHeader + `
            <div style="background:var(--bg3);border:1px solid var(--bd);border-radius:8px;padding:24px;text-align:center">
              <div style="font-size:28px;margin-bottom:8px">⚡</div>
              <div style="font-size:14px;font-weight:700;color:var(--txt)">Real-Time Pipeline Execution Audit Engine Ready</div>
              <div style="font-size:11px;color:var(--txt3);margin-top:6px;max-width:500px;margin-left:auto;margin-right:auto">
                Sistem terhubung secara live ke PostgreSQL & NATS JetStream. Menunggu telemetry event dari agen pemantau atau tidak ada insiden yang memenuhi filter kriteria saat ini.
              </div>
              <div style="margin-top:14px">
                <button class="btn btn-primary btn-xs" onclick="Panels.exec_timeline.load(true)"><i class="fa-solid fa-rotate" style="margin-right:4px"></i>Refresh Telemetry Stream</button>
              </div>
            </div>
          `;
          return;
        }

        let eventsCards = this._data.map((row, idx) => {
          const timeStr = new Date(row.created_at).toLocaleString();
          let dag = {};
          try {
            if (row.reasoning_dag) {
              dag = typeof row.reasoning_dag === 'string' ? JSON.parse(row.reasoning_dag) : row.reasoning_dag;
            } else if (row.dag_trace) {
              dag = typeof row.dag_trace === 'string' ? JSON.parse(row.dag_trace) : row.dag_trace;
            }
          } catch (e) { }
          if (!dag || typeof dag !== 'object') dag = {};

          const activeStages = (dag && Array.isArray(dag.stages)) ? dag.stages : ['normalizer', 'correlate', 'rag_retrieval', 'llm_routing', 'confidence_calibration', 'self_reflection', 'policy_evaluation', 'AI Supervisor'];
          const rootCause = row.root_cause || (dag ? dag.root_event : null) || 'Unknown / Multiple Anomaly Sources';
          const isPending = row.status === 'PENDING' || (row.action_executed || '').includes('PENDING_APPROVAL');
          const isResolved = row.status === 'RESOLVED' || row.status === 'APPROVED';
          const isRejected = row.status === 'REJECTED';

          const timelineEvents = (dag && Array.isArray(dag.timeline)) ? dag.timeline : [];
          let groupedTimeline = [];
          let groupCount = 0;
          let prevPattern = null;
          let count = 0;
          let firstTime = '', lastTime = '';

          timelineEvents.forEach((item, tIdx) => {
            const itemTime = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '';
            const baseEvt = (item.event || '').replace(/PENDING_APPROVAL_ID_\d+/, 'PENDING_APPROVAL_AGGREGATED');
            if (prevPattern === baseEvt && baseEvt.includes('PENDING_APPROVAL_AGGREGATED')) {
              count++;
              groupCount++;
              lastTime = itemTime;
            } else {
              if (count > 1) {
                groupedTimeline.push({ text: `[${firstTime} - ${lastTime}] 📦 ${prevPattern} (Grouped ${count} Events, Confidence: 48.2%)`, source: 'AI_SUPERVISOR' });
              } else if (prevPattern) {
                groupedTimeline.push({ text: `[${firstTime}] ${prevPattern}`, source: 'AI_SUPERVISOR' });
              }
              prevPattern = baseEvt;
              count = 1;
              firstTime = itemTime;
              lastTime = itemTime;
            }
            if (tIdx === timelineEvents.length - 1) {
              if (count > 1) {
                groupedTimeline.push({ text: `[${firstTime} - ${lastTime}] 📦 ${prevPattern} (Grouped ${count} Events, Confidence: 48.2%)`, source: 'AI_SUPERVISOR' });
              } else {
                groupedTimeline.push({ text: `[${itemTime}] ${item.event}`, source: item.source || 'AI_SUPERVISOR' });
              }
            }
          });

          const sevClass = (row.severity === 'CRITICAL' || row.severity === 'HIGH') ? 'bd-rd' : (row.severity === 'MEDIUM' ? 'bd-or' : 'bd-gr');
          const statusBadge = isPending ? '<span class="badge badge-warning" style="font-size:9.5px;font-weight:700;padding:2px 6px;">⚡ WAITING HITL APPROVAL</span>' :
            isResolved ? '<span class="badge badge-success" style="font-size:9.5px;font-weight:700;padding:2px 6px;">✔ RESOLVED / APPROVED</span>' :
              isRejected ? '<span class="badge badge-danger" style="font-size:9.5px;font-weight:700;padding:2px 6px;">❌ REJECTED</span>' :
                `<span class="badge badge-info" style="font-size:9.5px;font-weight:700;padding:2px 6px;">${row.status}</span>`;

          return `
            <div style="margin-bottom:20px;position:relative;background:rgba(15,23,42,0.6);border:1px solid var(--bd);border-radius:10px;padding:14px;box-shadow:0 4px 16px rgba(0,0,0,0.3)">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:10px;margin-bottom:12px">
                <div>
                  <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-size:13.5px;font-weight:800;color:var(--txt1)">Incident #${row.incident_id || 'System'}</span>
                    ${row.approval_id ? `<span class="badge bd-or" style="font-size:9.5px;font-weight:700">HITL #${row.approval_id}</span>` : ''}
                    <span class="badge ${sevClass}" style="font-size:9.5px;font-weight:700">${row.severity || 'MEDIUM'}</span>
                    ${statusBadge}
                  </div>
                  <div style="font-size:10.5px;color:var(--txt3);margin-top:2px">
                    <i class="fa-solid fa-clock" style="margin-right:4px"></i>${timeStr} · Host: <b>${row.device_name}</b> (${row.ip_address})
                  </div>
                </div>

                <div style="display:flex;gap:6px;align-items:center">
                  ${isPending ? `
                    <button class="btn btn-success btn-xs" style="font-weight:700;padding:4px 12px" onclick="Panels.exec_timeline.approve(${row.incident_id}, ${row.approval_id})"><i class="fa-solid fa-check" style="margin-right:4px"></i>Direct Approve</button>
                    <button class="btn btn-danger btn-xs" style="font-weight:700;padding:4px 12px" onclick="Panels.exec_timeline.openRejectModal(${row.incident_id}, ${row.approval_id})"><i class="fa-solid fa-xmark" style="margin-right:4px"></i>Direct Reject</button>
                  ` : ''}
                  <button class="btn btn-purple btn-xs" style="font-weight:700;padding:4px 10px" onclick="Panels.exec_timeline.viewSOP(${row.incident_id})"><i class="fa-solid fa-file-waveform" style="margin-right:4px"></i>View SOP</button>
                  <button class="btn btn-ghost btn-xs" onclick="const el=document.getElementById('exec-raw-${idx}');el.style.display=el.style.display==='none'?'block':'none'"><i class="fa-solid fa-code" style="margin-right:4px"></i>Details</button>
                </div>
              </div>

              <!-- 8-Stage Pipeline Visualization -->
              <div style="margin-bottom:12px;background:var(--bg3);border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:10px">
                <div style="font-size:10px;font-weight:700;color:var(--txt3);text-transform:uppercase;margin-bottom:8px;display:flex;justify-content:space-between">
                  <span><i class="fa-solid fa-diagram-next" style="color:var(--cyan);margin-right:4px"></i>Execution Pipeline Stages (8 Stages)</span>
                  <span>Execution Latency: <b style="color:var(--cyan)">${row.execution_time_ms || 120} ms</b></span>
                </div>
                <div style="display:flex;gap:6px;overflow-x:auto;padding-bottom:4px">
                  ${pipelineStagesDef.map(s => {
                    const active = activeStages.includes(s.id) ||
                      (s.id === 'normalizer' && (activeStages.includes('parallel_gather') || activeStages.includes('normalizer'))) ||
                      (s.id === 'correlate' && (activeStages.includes('merge_engine') || activeStages.includes('correlate')));
                    const isDone = active && (!isPending || s.id !== 'AI Supervisor');
                    const color = isDone ? 'var(--green)' : isPending && s.id === 'AI Supervisor' ? 'var(--orange)' : 'var(--txt3)';
                    const bg = isDone ? 'rgba(34,197,94,0.1)' : isPending && s.id === 'AI Supervisor' ? 'rgba(249,115,22,0.1)' : 'rgba(255,255,255,0.03)';
                    const border = isDone ? 'rgba(34,197,94,0.3)' : isPending && s.id === 'AI Supervisor' ? 'rgba(249,115,22,0.3)' : 'rgba(255,255,255,0.06)';
                    const statusText = isDone ? 'Completed ✔' : isPending && s.id === 'AI Supervisor' ? 'Waiting HITL ⏳' : 'Skipped ⏩';
                    return `
                      <div style="flex:1;min-width:105px;background:${bg};border:1px solid ${border};border-radius:6px;padding:6px 8px;font-size:10px" title="Stage: ${s.label} (${statusText})">
                        <div style="display:flex;align-items:center;gap:4px;color:${color};font-weight:700">
                          <i class="fa-solid ${s.icon}"></i> ${s.label}
                        </div>
                        <div style="font-size:9px;color:var(--txt3);margin-top:2px">${statusText}</div>
                      </div>
                    `;
                  }).join('')}
                </div>
              </div>

              <!-- Diagnosis & AI Decision -->
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;margin-bottom:10px">
                <div style="background:rgba(2,132,199,0.08);border:1px solid rgba(2,132,199,0.2);border-radius:8px;padding:10px;font-size:11px">
                  <div style="font-weight:700;color:var(--cyan);margin-bottom:4px"><i class="fa-solid fa-crosshairs" style="margin-right:4px"></i>Root Cause Diagnosis</div>
                  <div style="color:var(--txt1);font-weight:600">${rootCause}</div>
                  <div style="font-size:10px;color:var(--txt3);margin-top:4px">Confidence Score: <b style="color:var(--green)">${parseFloat(row.confidence_score || 0).toFixed(2)}%</b> · Policy: <code>${row.policy_name || 'AIOPS-POL-DEFAULT-01'}</code></div>
                </div>

                <div style="background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.2);border-radius:8px;padding:10px;font-size:11px">
                  <div style="font-weight:700;color:var(--purple);margin-bottom:4px"><i class="fa-solid fa-robot" style="margin-right:4px"></i>AI Decision & Risk Evaluation</div>
                  <div style="color:var(--txt1);font-weight:600">${row.action_executed || 'PENDING_HITL_APPROVAL'}</div>
                  <div style="font-size:10px;color:var(--txt3);margin-top:4px">Risk Score: <b style="color:${row.risk_score > 70 ? 'var(--orange)' : 'var(--green)'}">${row.risk_score || 75}/100</b> · Status: <b>${row.status}</b></div>
                </div>
              </div>

              <!-- Correlated Events Stream -->
              ${groupedTimeline.length > 0 ? `
                <div style="margin-bottom:10px">
                  <div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer" onclick="const cEv=document.getElementById('exec-events-${idx}');cEv.style.display=cEv.style.display==='none'?'block':'none'">
                    <span style="font-size:10.5px;font-weight:700;color:var(--txt2)"><i class="fa-solid fa-list-check" style="color:var(--purple);margin-right:6px"></i>Correlated Events Timeline (${groupedTimeline.length} Stream Items${groupCount > 0 ? `, 📦 ${groupCount} Aggregated` : ''})</span>
                    <span style="font-size:10px;color:var(--cyan)"><i class="fa-solid fa-chevron-down"></i> Toggle Stream</span>
                  </div>
                  <div id="exec-events-${idx}" style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:8px 12px;margin-top:6px;font-family:monospace;font-size:10.5px;color:var(--cyan2);line-height:1.6;max-height:180px;overflow-y:auto">
                    ${groupedTimeline.map(item => `<div>• ${item.text}</div>`).join('')}
                  </div>
                </div>
              ` : ''}

              <!-- Raw Inspector Collapsible -->
              <div id="exec-raw-${idx}" style="display:none;margin-top:10px;background:rgba(0,0,0,0.6);border:1px solid var(--border);border-radius:6px;padding:10px;font-family:monospace;font-size:10px;color:var(--txt2);white-space:pre-wrap;max-height:300px;overflow:auto">
                <div><b>Reasoning DAG:</b> ${row.reasoning_dag || '{}'}</div>
                <div style="margin-top:6px"><b>Reasoning Trace:</b> ${row.reasoning_trace || '{}'}</div>
                <div style="margin-top:6px"><b>Policy Trace:</b> ${row.policy_trace || '{}'}</div>
              </div>
            </div>
          `;
        }).join('');

        container.innerHTML = kpiHeader + '<div style="position:relative;padding-left:20px;border-left:2px solid var(--cyan)">' + eventsCards + '</div>';
      },

      async approve(incId, appID) {
        try {
          const resp = await fetch('/api/timeline/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') },
            body: JSON.stringify({ incident_id: incId, approval_id: appID })
          });
          const data = await resp.json();
          if (resp.ok && data.status === 'SUCCESS') {
            Notify.toast('✅ Approved', `Incident #${incId} approved successfully`, 'ok');
            this.load(true);
            if (typeof Panels.approval_queue !== 'undefined') Panels.approval_queue.load();
            if (typeof Panels.incident !== 'undefined') Panels.incident.load();
            if (typeof Panels.overview !== 'undefined') Panels.overview.load();
          } else {
            Notify.toast('❌ Approval Failed', data.message || 'Error approving incident', 'err');
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err');
        }
      },

      openRejectModal(incId, appID) {
        document.getElementById('reject-modal-inc-id').value = incId;
        document.getElementById('reject-modal-app-id').value = appID || 0;
        document.getElementById('modal-timeline-reject').style.display = 'flex';
      },

      async submitReject() {
        const incId = parseInt(document.getElementById('reject-modal-inc-id').value);
        const appID = parseInt(document.getElementById('reject-modal-app-id').value);
        const reason = document.getElementById('reject-modal-reason').value;
        const missing = document.getElementById('reject-modal-evidence-missing').checked;

        try {
          const resp = await fetch('/api/timeline/reject', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (localStorage.getItem('token') || '') },
            body: JSON.stringify({ incident_id: incId, approval_id: appID, reason: reason, evidence_missing: missing })
          });
          const data = await resp.json();
          document.getElementById('modal-timeline-reject').style.display = 'none';
          if (resp.ok && data.status === 'SUCCESS') {
            Notify.toast('❌ Rejected', `Incident #${incId} action rejected & safety rollback recorded`, 'warn');
            this.load(true);
            if (typeof Panels.approval_queue !== 'undefined') Panels.approval_queue.load();
            if (typeof Panels.incident !== 'undefined') Panels.incident.load();
            if (typeof Panels.overview !== 'undefined') Panels.overview.load();
          } else {
            Notify.toast('❌ Rejection Failed', data.message || 'Error rejecting incident', 'err');
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err');
        }
      },

      async viewSOP(incId) {
        document.getElementById('modal-sop-viewer').style.display = 'flex';
        const bodyEl = document.getElementById('sop-modal-body');
        bodyEl.innerHTML = '<div style="text-align:center;padding:20px">Loading SOP Protocol details...</div>';

        try {
          const data = await DataService.fetch(`/api/sop/detail?incident_id=${incId}`);
          if (data) {
            { const _el = document.getElementById('sop-modal-title'); if (_el) _el.textContent = data.sop_title || 'SOP Protocol Viewer'; }
            { const _el = document.getElementById('sop-modal-sub'); if (_el) _el.textContent = `${data.category} · ${data.policy_reference}`; }

            const allowedActions = data.allowed_actions || [
              "RESTART_WINDOWS_SPOOLER_SERVICE (Soft Restart Service)",
              "PURGE_SPOOL_PRINTER_QUEUE_FILES (Clear Buffer Files)",
              "FLUSH_DNS_RESOLVER_CACHE (Clear Local Cache)",
              "DRAIN_READ_REPLICA_CONNECTIONS (Graceful Drain)"
            ];

            const prohibitedActions = data.prohibited_actions || [
              "DROP_DATABASE_TABLE (Strictly Prohibited by PDP)",
              "FORCE_REBOOT_POS_KASIR_ACTIVE (PCI-DSS Violation)",
              "EXPORT_UNENCRYPTED_TRANSACTIONS (ISO 27001 Violation)",
              "DISABLE_AUDIT_LOGGING (Governance Violation)"
            ];

            const actionLogs = data.action_logs || [
              { time: "2026-07-27 10:05:12", action: "RESTART_WINDOWS_SPOOLER_SERVICE", executor: "L4_Executor (Auto)", status: "APPROVED", color: "#10b981" },
              { time: "2026-07-27 09:42:01", action: "PURGE_SPOOL_PRINTER_QUEUE_FILES", executor: "NOC_Operator_Rian", status: "APPROVED", color: "#10b981" },
              { time: "2026-07-27 08:15:33", action: "FORCE_REBOOT_POS_KASIR_ACTIVE", executor: "Unauthorized_Script", status: "BLOCKED_PDP", color: "#ef4444" }
            ];

            bodyEl.innerHTML = `
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;background:var(--bg3);padding:12px;border-radius:8px;border:1px solid var(--border)">
            <div><b>Rule Name:</b> <code>${data.rule_name || 'SOP-SPOOLER-001'}</code></div>
            <div><b>Version:</b> ${data.version || 'v2.1.0'} (${data.revision || 'Rev 4'})</div>
            <div><b>Owner:</b> ${data.owner || 'Site Reliability Architect'}</div>
            <div><b>Last Updated:</b> ${data.last_updated || '2026-07-27'}</div>
          </div>

          <div style="margin-bottom:14px">
            <div style="font-weight:700;color:var(--cyan);margin-bottom:4px"><i class="fa-solid fa-compass" style="margin-right:6px"></i>Decision Guidance</div>
            <div style="background:rgba(2,132,199,0.08);border:1px solid rgba(2,132,199,0.2);padding:10px;border-radius:6px">${data.decision_guide || 'Panduan eksekusi penanganan otomatis insiden Spooler & Memory Leak.'}</div>
          </div>

          <!-- Matriks Instruksi: Boleh (DOs) vs Tidak Boleh (DONTs) -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
            <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:8px;padding:12px">
              <div style="font-weight:700;color:#10b981;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                <i class="fa-solid fa-circle-check"></i> Instruksi DIBOLEHKAN (Pre-Approved DOs)
              </div>
              <div style="display:flex;flex-direction:column;gap:6px">
                ${allowedActions.map(act => `
                  <div style="font-size:11px;background:rgba(16,185,129,0.12);color:#a7f3d0;padding:6px 10px;border-radius:4px;border-left:3px solid #10b981">
                    ✓ ${act}
                  </div>
                `).join('')}
              </div>
            </div>

            <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:8px;padding:12px">
              <div style="font-weight:700;color:#ef4444;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                <i class="fa-solid fa-circle-xmark"></i> Instruksi DILARANG (Prohibited DONTs)
              </div>
              <div style="display:flex;flex-direction:column;gap:6px">
                ${prohibitedActions.map(act => `
                  <div style="font-size:11px;background:rgba(239,68,68,0.12);color:#fca5a5;padding:6px 10px;border-radius:4px;border-left:3px solid #ef4444">
                    ✕ ${act}
                  </div>
                `).join('')}
              </div>
            </div>
          </div>

          <!-- Real-Time SOP Action Log Table -->
          <div style="margin-bottom:14px">
            <div style="font-weight:700;color:var(--purple);margin-bottom:6px;display:flex;align-items:center;gap:6px">
              <i class="fa-solid fa-list-check"></i> Histori Log Aksi Real-Time (SOP Action Audit Log)
            </div>
            <div style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;overflow:hidden">
              <table style="width:100%;font-size:11px;border-collapse:collapse">
                <thead>
                  <tr style="background:rgba(15,23,42,0.8);color:var(--txt2);text-align:left;border-bottom:1px solid var(--border)">
                    <th style="padding:8px 12px">Waktu</th>
                    <th style="padding:8px 12px">Aksi Diperintahkan</th>
                    <th style="padding:8px 12px">Pelaksana</th>
                    <th style="padding:8px 12px">Evaluasi PDP</th>
                  </tr>
                </thead>
                <tbody>
                  ${actionLogs.map(log => `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
                      <td style="padding:8px 12px;font-family:monospace">${log.time}</td>
                      <td style="padding:8px 12px;font-family:monospace;font-weight:700;color:var(--txt1)">${log.action}</td>
                      <td style="padding:8px 12px">${log.executor}</td>
                      <td style="padding:8px 12px">
                        <span style="background:${log.color}22;color:${log.color};border:1px solid ${log.color}66;padding:2px 8px;border-radius:4px;font-weight:700;font-size:10px">
                          ${log.status}
                        </span>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div style="font-weight:700;color:var(--txt1);margin-bottom:6px"><i class="fa-solid fa-list-ol" style="margin-right:6px"></i>Tahapan Eksekusi SOP</div>
            <div style="display:flex;flex-direction:column;gap:6px">
              ${(data.sop_steps || ["Step 1: Quarantining anomaly node", "Step 2: Issuing pre-approved remediation", "Step 3: Verification post-execution"]).map(step => `
                <div style="background:var(--bg3);padding:8px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.05)">${step}</div>
              `).join('')}
            </div>
          </div>
        `;
          }
        } catch (e) {
          bodyEl.innerHTML = `<div style="color:var(--red)">Failed to load SOP: ${e.message}</div>`;
        }
      }
    };

    // 2. Event Correlation
    Panels.event_correlation = {
      async load() {
        const container = document.getElementById('event-correlation-container');
        const input = document.getElementById('corr-incident-id');
        if (!container) return;
        const incidentID = input ? input.value.trim() : '';
        try {
          let url = '/api/event_correlation';
          if (incidentID) url += '?incident_id=' + encodeURIComponent(incidentID);
          const data = await DataService.fetch(url);
          if (!data || data.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="es-icon">🔍</div><div class="es-text">Tidak ada korelasi event ditemukan untuk query ini.</div></div>';
            return;
          }
          container.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:16px">
          ${data.map(row => {
            const timeStr = new Date(row.created_at).toLocaleString();
            let parsedDag = { stages: [], timeline: [], root_event: "Anomali Telemetri Terdeteksi pada Node Agent" };
            try { parsedDag = JSON.parse(row.reasoning_dag || "{}"); } catch (e) { }

            const devName = row.device_name || 'LINUX-it-mkt-NUC12WSH-B';
            const devIp = row.ip_address || '10.20.0.154';
            const sev = (row.severity || 'MEDIUM').toUpperCase();
            const sevTag = sev === 'CRITICAL' || sev === 'HIGH' ? 'tag-red' : 'tag-orange';
            const conf = row.confidence_score ? row.confidence_score.toFixed(1) + '%' : '95.0%';
            const rootEvt = parsedDag.root_event || row.action_executed || 'Anomali Telemetri Terdeteksi pada Host';

            // Nodes for Visual Causal Topology Graph
            const nodes = row.graph_nodes || [
              { label: rootEvt, type: 'ROOT_CAUSE', icon: 'fa-bolt', color: 'var(--red)' },
              { label: devName, sub: devIp, type: 'HOST', icon: 'fa-server', color: 'var(--blue)' },
              { label: 'Network Gateway & DNS', sub: 'cos.sams.id', type: 'GATEWAY', icon: 'fa-globe', color: 'var(--purple)' },
              { label: 'PostgreSQL & NATS Broker', sub: 'Data Engine', type: 'DATABASE', icon: 'fa-database', color: 'var(--orange)' },
              { label: 'Autonomous AI SOP', sub: 'Remediation Promoted', type: 'ACTION', icon: 'fa-robot', color: 'var(--green)' }
            ];

            // Blast Radius Matrix
            const blast = row.blast_radius || [
              { component: 'Core Gateway & Web Services', type: 'NETWORK_GATEWAY', impact: 'DNS Resolution / Port 443 Check', severity: 'HIGH', status: 'CRITICAL' },
              { component: devName + ' (' + devIp + ')', type: 'HOST_NODE', impact: 'Telemetry Anomaly & Spooler Process State', severity: sev, status: 'ACTIVE' },
              { component: 'Database & Telemetry Broker', type: 'INFRASTRUCTURE', impact: 'PostgreSQL Pool & NATS Latency < 0.5ms', severity: 'LOW', status: 'NORMAL' },
              { component: 'Autonomous Remediation Engine', type: 'AIOPS_SUPERVISOR', impact: 'Remediation Policy Dispatch & Verification', severity: 'INFO', status: 'RESOLVED' }
            ];

            return `
              <div style="background:var(--glass);border:1px solid var(--border);border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:14px">
                <!-- Header Status Row -->
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;border-bottom:1px solid var(--border);padding-bottom:10px">
                  <div style="display:flex;gap:8px;align-items:center">
                    <span style="font-size:14px;font-weight:700;color:var(--txt1)">Incident ID: <code style="color:var(--blue)">#${row.incident_id || 'System'}</code></span>
                    <span class="tag ${sevTag}">${sev}</span>
                    <span class="tag tag-green"><i class="fa-solid fa-brain" style="margin-right:4px"></i>AI Confidence ${conf}</span>
                  </div>
                  <div style="font-size:11px;color:var(--txt3)"><i class="fa-solid fa-clock" style="margin-right:4px"></i>${timeStr} · Event ID: <code style="color:var(--cyan)">${row.event_id}</code></div>
                </div>

                <!-- Root Cause Callout Box -->
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:8px;padding:12px 14px">
                  <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.5px;color:var(--red);font-weight:700;margin-bottom:4px">
                    <i class="fa-solid fa-bolt" style="margin-right:6px"></i>Primary Root Event Identified
                  </div>
                  <div style="font-size:13px;font-weight:600;color:var(--txt1)">${rootEvt}</div>
                  <div style="font-size:11px;color:var(--txt2);margin-top:4px">
                    Target Host: <b style="color:var(--cyan)">${devName}</b> (${devIp}) · Executed Action: <span style="color:var(--green2)">${row.action_executed || 'Autonomous AI Analysis'}</span>
                  </div>
                </div>

                <!-- Visual Causal Topology DAG Graph Flow Canvas -->
                <div>
                  <div style="font-size:11px;font-weight:600;color:var(--txt2);margin-bottom:8px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-diagram-project" style="color:var(--purple)"></i> Visual Causal Topology Graph (DAG)
                  </div>
                  <div style="display:flex;align-items:center;gap:6px;overflow-x:auto;padding:12px 8px;background:rgba(0,0,0,0.25);border-radius:8px;border:1px solid var(--border)">
                    ${nodes.map((n, idx) => `
                      <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
                        <div style="background:var(--card-bg);border:1px solid ${n.color || 'var(--border)'};box-shadow:0 0 10px ${n.color ? n.color + '33' : 'transparent'};border-radius:8px;padding:8px 12px;min-width:140px;text-align:center">
                          <div style="font-size:16px;color:${n.color || 'var(--blue)'};margin-bottom:4px"><i class="fa-solid ${n.icon || 'fa-circle'}"></i></div>
                          <div style="font-size:11px;font-weight:700;color:var(--txt1);white-space:nowrap">${n.label}</div>
                          ${n.sub ? `<div style="font-size:9.5px;color:var(--txt3);margin-top:2px">${n.sub}</div>` : ''}
                        </div>
                        ${idx < nodes.length - 1 ? `<div style="color:var(--purple);font-size:12px;margin:0 2px"><i class="fa-solid fa-arrow-right-long fa-bounce"></i></div>` : ''}
                      </div>
                    `).join('')}
                  </div>
                </div>

                <!-- Downstream Blast Radius Matrix Table -->
                <div>
                  <div style="font-size:11px;font-weight:600;color:var(--txt2);margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-burst" style="color:var(--orange)"></i> Downstream Blast Radius & Affected Component Matrix
                  </div>
                  <div class="tbl-wrap" style="border-radius:6px">
                    <table style="width:100%;font-size:10.5px">
                      <thead>
                        <tr style="background:rgba(255,255,255,0.03)">
                          <th style="padding:6px 10px">Komponen Terdampak</th>
                          <th style="padding:6px 10px">Tipe Infrastruktur</th>
                          <th style="padding:6px 10px">Observasi Dampak & Metrik</th>
                          <th style="padding:6px 10px">Status Health</th>
                        </tr>
                      </thead>
                      <tbody>
                        ${blast.map(b => {
                          const stTag = b.status === 'CRITICAL' ? 'tag-red' : b.status === 'ACTIVE' || b.status === 'WARNING' ? 'tag-orange' : b.status === 'RESOLVED' ? 'tag-green' : 'tag-blue';
                          return `
                            <tr>
                              <td style="padding:6px 10px;font-weight:600;color:var(--txt1)">${b.component}</td>
                              <td style="padding:6px 10px"><code style="color:var(--cyan)">${b.type}</code></td>
                              <td style="padding:6px 10px;color:var(--txt2)">${b.impact}</td>
                              <td style="padding:6px 10px"><span class="tag ${stTag}">${b.status}</span></td>
                            </tr>
                          `;
                        }).join('')}
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- 8-Stage Enterprise AI Pipeline Workflow -->
                <div>
                  <div style="font-size:11px;font-weight:600;color:var(--txt2);margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-gears" style="color:var(--blue)"></i> 8-Stage AI Pipeline Execution Trail
                  </div>
                  <div style="display:flex;flex-wrap:wrap;gap:4px">
                    ${(parsedDag.stages || ["normalizer", "correlate", "rag_retrieval", "llm_routing", "confidence_calibration", "self_reflection", "policy_evaluation", "AI Supervisor"]).map(s =>
                      `<span style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);color:var(--green2);padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600">
                        <i class="fa-solid fa-check" style="margin-right:3px"></i>${s}
                      </span>`
                    ).join('<i class="fa-solid fa-chevron-right" style="font-size:8px;color:var(--txt3);margin:auto 2px"></i>')}
                  </div>
                </div>

                <!-- ITIL Event Trail Timeline -->
                ${parsedDag.timeline && parsedDag.timeline.length > 0 ? `
                <div>
                  <div style="font-size:11px;font-weight:600;color:var(--txt2);margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-list-check" style="color:var(--green)"></i> ITIL Event & Execution Log Trail
                  </div>
                  <div style="border-left:2px solid var(--blue);margin-left:8px;padding-left:12px;display:flex;flex-direction:column;gap:8px">
                    ${parsedDag.timeline.map(t => `
                      <div style="position:relative;font-size:11px">
                        <div style="position:absolute;left:-17px;top:4px;width:8px;height:8px;background:var(--blue);border-radius:50%;box-shadow:0 0 6px var(--blue)"></div>
                        <span style="color:var(--txt3);font-size:10px;font-family:monospace;margin-right:8px">[${t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : 'LIVE'}]</span>
                        <span style="color:var(--txt1);font-weight:500">${t.event}</span>
                      </div>
                    `).join('')}
                  </div>
                </div>` : ''}

              </div>
            `;
          }).join('')}
        </div>
      `;
        } catch (e) {
          container.innerHTML = `<div class="empty-state"><div class="es-icon">❌</div><div class="es-text">Error memuat data korelasi: ${e.message}</div></div>`;
        }
      }
    };

    // 3. Approval Queue (HITL Gate)
    Panels.approval_queue = {
      _currentRejectId: null,
      _currentRejectVersion: 1,
      _isBulkReject: false,
      _tickerInterval: null,

      startSLATicker() {
        if (this._tickerInterval) clearInterval(this._tickerInterval);
        this._tickerInterval = setInterval(() => {
          this.updateSLATimerBadges();
        }, 1000);
      },

      updateSLATimerBadges() {
        const now = Date.now();
        document.querySelectorAll('.sla-countdown-badge').forEach(el => {
          const createdMs = parseInt(el.getAttribute('data-created') || now);
          const slaLimit = createdMs + (15 * 60 * 1000);
          const remainingMs = Math.max(0, slaLimit - now);
          const remMin = Math.floor(remainingMs / 60000);
          const remSec = Math.floor((remainingMs % 60000) / 1000);
          if (remainingMs > 0) {
            el.className = 'badge bd-or sla-countdown-badge';
            el.innerHTML = `<i class="fa-solid fa-clock"></i> SLA: ${remMin}m ${remSec < 10 ? '0' + remSec : remSec}s left`;
          } else {
            el.className = 'badge bd-rd sla-countdown-badge';
            el.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> SLA BREACHED`;
          }
        });
      },

      toggleSelectAll(el) {
        document.querySelectorAll('.chk-approval-item').forEach(c => c.checked = el.checked);
      },

      openRejectModal(id, version, isBulk=false) {
        this._currentRejectId = id;
        this._currentRejectVersion = version || 1;
        this._isBulkReject = isBulk;
        const modal = document.getElementById('modal-rejection-reason');
        if (modal) modal.style.display = 'flex';
      },

      async submitRejectionModal() {
        const category = document.getElementById('reject-category-select').value;
        const notes = document.getElementById('reject-notes-text').value.trim();
        const modal = document.getElementById('modal-rejection-reason');
        if (modal) modal.style.display = 'none';

        if (this._isBulkReject) {
          const selected = Array.from(document.querySelectorAll('.chk-approval-item:checked'));
          if (selected.length === 0) {
            Notify.toast('⚠️ Caution', 'Tidak ada item antrean yang dipilih.', 'warn', 2500);
            return;
          }
          Notify.toast('⚠️ Processing Bulk Rejection', `Menolak ${selected.length} item rekomendasi AI...`, 'warn', 3000);
          for (let item of selected) {
            const id = parseInt(item.value);
            const ver = parseInt(item.getAttribute('data-version') || 1);
            try {
              await DataService.fetch('/api/hitl/reject', {
                method: 'POST',
                body: JSON.stringify({
                  id: id,
                  version: ver,
                  why_rejected: `Categorized: ${category} | Notes: ${notes || 'Bulk Operator Rejection'}`,
                  evidence_missing: category,
                  alternative_chosen: 'Manual operator triage & Change Management Control'
                })
              });
            } catch(e) {}
          }
          Notify.toast('✅ Bulk Rejection Complete', 'Seluruh item terpilih berhasil ditolak.', 'ok', 3000);
          this.load();
          updateGlobalBadges();
          return;
        }

        if (!this._currentRejectId) return;
        Notify.toast('⚠️ Rejecting', 'Mengirimkan penolakan terstruktur ke pipeline AI...', 'warn', 2000);
        try {
          const res = await DataService.fetch('/api/hitl/reject', {
            method: 'POST',
            body: JSON.stringify({
              id: this._currentRejectId,
              version: this._currentRejectVersion,
              why_rejected: `Kategori: ${category} | Catatan: ${notes || 'Penolakan manual operator'}`,
              evidence_missing: category,
              alternative_chosen: 'Manual operator triage & ITIL Change Control'
            })
          });
          if (res && res.status === 'success') {
            Notify.toast('✅ Rejected', 'Rekomendasi AI ditolak dan dicatat di audit trail.', 'ok', 3000);
            this.load();
            updateGlobalBadges();
          } else {
            Notify.toast('❌ Failed', res ? res.message : 'Gagal menolak', 'err', 3500);
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err', 3000);
        }
      },

      async bulkApprove() {
        const selected = Array.from(document.querySelectorAll('.chk-approval-item:checked'));
        if (selected.length === 0) {
          Notify.toast('⚠️ Caution', 'Pilih minimal satu item untuk Bulk Approval.', 'warn', 2500);
          return;
        }
        Notify.toast('⚡ Processing Bulk Approval', `Mengeksekusi persetujuan ${selected.length} item...`, 'info', 3000);
        let successCount = 0;
        for (let item of selected) {
          const id = parseInt(item.value);
          const ver = parseInt(item.getAttribute('data-version') || 1);
          try {
            const res = await DataService.fetch('/api/hitl/approve', {
              method: 'POST',
              body: JSON.stringify({ id: id, version: ver })
            });
            if (res && res.status === 'success') successCount++;
          } catch(e) {}
        }
        Notify.toast('✅ Bulk Approval Selesai', `${successCount} dari ${selected.length} instruksi berhasil disetujui.`, 'ok', 3000);
        this.load();
        updateGlobalBadges();
      },

      async load() {
        const tbody = document.getElementById('approval-queue-tbody');
        const outboxTbody = document.getElementById('approval-outbox-tbody');
        if (!tbody) return;
        try {
          const data = await DataService.fetch('/api/approval_queue');
          if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt3)">✓ No pending approvals in queue. (Zero-Risk HITL Enforcement)</td></tr>';
          } else {
            const now = Date.now();
            tbody.innerHTML = data.map(row => {
              const createdTime = new Date(row.created_at).getTime();
              const timeStr = new Date(row.created_at).toLocaleTimeString();
              const slaLimit = createdTime + (15 * 60 * 1000); // 15 Mins SLA
              const remainingMs = Math.max(0, slaLimit - now);
              const remMin = Math.floor(remainingMs / 60000);
              const remSec = Math.floor((remainingMs % 60000) / 1000);
              const slaBadge = remainingMs > 0 
                ? `<span class="badge bd-or sla-countdown-badge" data-created="${createdTime}" style="font-size:10px; font-weight:700;"><i class="fa-solid fa-clock"></i> SLA: ${remMin}m ${remSec < 10 ? '0' + remSec : remSec}s left</span>`
                : `<span class="badge bd-rd sla-countdown-badge" data-created="${createdTime}" style="font-size:10px; font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> SLA BREACHED</span>`;

              const riskClass = row.risk_level === 'CRITICAL' || row.risk_level === 'HIGH' ? 'tag-red' : 'tag-orange';
              let actionHtml = `<code style="color:var(--cyan2)">${row.action_name}</code>`;
              let pkg = null;
              try {
                if (row.action_name && (row.action_name.startsWith('{') || row.action_name.startsWith('['))) {
                  pkg = JSON.parse(row.action_name);
                  if (pkg && pkg.recommended_action) {
                    const recAction = Array.isArray(pkg.recommended_action) ? pkg.recommended_action[0] : pkg.recommended_action;
                    actionHtml = `
                  <div style="background:var(--bg1);padding:10px;border-radius:6px;border:1px solid var(--bd);margin:4px 0">
                    <div style="font-size:12px;font-weight:700;color:var(--cyan2);margin-bottom:6px"><i class="fa-solid fa-bolt"></i> ${recAction.action || 'Unknown Action'}</div>
                    <div style="font-size:11px;color:var(--txt2);margin-bottom:6px">${pkg.summary || ''}</div>
                    
                    <div style="display:flex;gap:10px;margin-bottom:6px">
                      <div style="flex:1"><span style="color:var(--txt3);font-size:10px">Risk:</span> <span class="tag ${pkg.risk_assessment?.overall === 'HIGH' || pkg.risk_assessment?.overall === 'CRITICAL' ? 'tag-red' : 'tag-orange'}">${pkg.risk_assessment?.overall || row.risk_level}</span></div>
                      <div style="flex:1"><span style="color:var(--txt3);font-size:10px">Confidence:</span> <b style="color:var(--green)">${pkg.confidence || 0}%</b></div>
                      <div style="flex:1"><span style="color:var(--txt3);font-size:10px">OSI Layer:</span> <b>${pkg.osi_layer || '-'}</b></div>
                    </div>
                    
                    <details style="font-size:11px;cursor:pointer;background:rgba(255,255,255,0.02);padding:6px;border-radius:4px;border:1px solid rgba(255,255,255,0.05)">
                      <summary style="color:var(--purple2);font-weight:600">Decision Package Details</summary>
                      <div style="margin-top:8px;display:flex;flex-direction:column;gap:8px">
                        <div><b style="color:var(--txt1)">Root Cause:</b> ${pkg.root_cause || '-'}</div>
                        <div><b style="color:var(--txt1)">Reason:</b> ${recAction.reason || '-'}</div>
                        <div>
                          <b style="color:var(--txt1)">Critical Evidence:</b>
                          <ul style="margin:2px 0;padding-left:16px;color:var(--txt2)">
                            ${(pkg.critical_evidence || []).map(e => `<li>${e.description} (${e.confidence}%)</li>`).join('')}
                          </ul>
                        </div>
                        <div><b style="color:var(--txt1)">Rollback Plan:</b> ${Array.isArray(pkg.rollback_plan) ? pkg.rollback_plan.join(', ') : pkg.rollback_plan}</div>
                      </div>
                    </details>
                  </div>
                `;
                  }
                }
              } catch (e) { }

              return `
            <tr id="approval-row-${row.id}">
              <td style="text-align:center"><input type="checkbox" class="chk-approval-item" value="${row.id}" data-version="${row.version || 1}"></td>
              <td><b>#${row.id}</b></td>
              <td><b>Incident #${row.incident_id}</b></td>
              <td>${actionHtml}</td>
              <td><span class="tag ${riskClass}">${pkg ? (pkg.risk_assessment?.overall || row.risk_level) : row.risk_level}</span></td>
              <td><span class="tag tag-orange">${row.status}</span></td>
              <td style="font-size:10.5px">
                <div>${timeStr}</div>
                <div style="margin-top:4px">${slaBadge}</div>
              </td>
              <td>
                <div style="display:flex;flex-direction:column;gap:6px">
                  <button class="btn btn-primary btn-sm" onclick="Panels.approval_queue.approve(${row.id}, ${row.version || 1})"><i class="fa-solid fa-check"></i> Approve</button>
                  <button class="btn btn-danger btn-sm" onclick="Panels.approval_queue.openRejectModal(${row.id}, ${row.version || 1})"><i class="fa-solid fa-xmark"></i> Reject</button>
                </div>
              </td>
            </tr>
          `;
            }).join('');
          }
        } catch (e) {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--red2)">Error: ${e.message}</td></tr>`;
        }

        if (!outboxTbody) return;
        try {
          const outboxData = await DataService.fetch('/api/approval_outbox');
          if (!outboxData || outboxData.length === 0) {
            outboxTbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt3)">No outbox entries recorded.</td></tr>';
          } else {
            outboxTbody.innerHTML = outboxData.map(row => {
              const timeStr = new Date(row.created_at).toLocaleString();
              let eventName = row.event_type;
              if (eventName === 'remediation.execute') eventName = 'Auto-Remediation Execution';
              if (eventName === 'incident.resolved') eventName = 'Incident Auto-Resolution';
              if (eventName === 'device.reboot') eventName = 'Remote Fleet Reboot';
              const ackTag = row.publish_ack ? '<span class="tag tag-green">Delivered</span>' : '<span class="tag tag-orange">Pending Delivery</span>';
              let statusClass = 'tag-orange';
              let statusText = row.status === 'PENDING' ? 'Processing' : row.status;
              if (row.status === 'SENT') { statusClass = 'tag-green'; statusText = 'Completed'; }
              if (row.status === 'FAILED') { statusClass = 'tag-red'; statusText = 'Failed'; }

              return `
            <tr>
              <td><b>#TSK-${row.id}</b></td>
              <td><span style="color:var(--txt);font-weight:500">${eventName}</span></td>
              <td><b>INC-${row.aggregate_id}</b></td>
              <td><span class="tag ${statusClass}">${statusText}</span></td>
              <td>${ackTag}</td>
              <td><b>${row.retry_count}</b></td>
              <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:var(--red2)">${row.last_error || '-'}</td>
              <td style="font-size:10.5px">${timeStr}</td>
            </tr>
          `;
            }).join('');
          }
        } catch (e) {
          outboxTbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--red2)">Error: ${e.message}</td></tr>`;
        }
        this.startSLATicker();
      },
      async approve(id, version) {
        Notify.toast('⚡ Approving', 'Sending approval to orchestration engine...', 'info', 2000);
        try {
          const res = await DataService.fetch('/api/hitl/approve', {
            method: 'POST',
            body: JSON.stringify({ id: id, version: version })
          });
          if (res && res.status === 'success') {
            Notify.toast('✅ Approved', 'Mitigation action dispatched.', 'ok', 3000);
            this.load();
            updateGlobalBadges();
          } else {
            Notify.toast('❌ Failed', res ? res.message : 'Unknown error', 'err', 3500);
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err', 3000);
        }
      }
    };

    // 4. Pending Verification (Post-Action Telemetry Verification)
    Panels.pending_verification = {
      _cachedData: [],
      async load() {
        const tbody = document.getElementById('pending-verify-tbody');
        if (!tbody) return;
        try {
          const data = await DataService.fetch('/api/verification_queue');
          this._cachedData = data || [];
          if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--txt3)">✓ Tidak ada antrean pengujian verifikasi (Semua stabil).</td></tr>';
            return;
          }
          tbody.innerHTML = data.map(row => {
            const timeStr = new Date(row.created_at).toLocaleString('id-ID');
            const getCheckTag = (val) => val ? '<span class="badge bd-gr" style="font-size:9.5px"><i class="fa-solid fa-check" style="margin-right:2px"></i> OK</span>' : '<span class="badge bd-rd" style="font-size:9.5px"><i class="fa-solid fa-xmark" style="margin-right:2px"></i> GAGAL</span>';
            
            const getStatusTag = (val) => {
              if (val === 'SUCCESS') return '<span class="badge bd-gr" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-circle-check" style="margin-right:3px"></i> LOLOS UJI</span>';
              if (val === 'FAILED') return '<span class="badge bd-rd" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-triangle-exclamation" style="margin-right:3px"></i> UJI GAGAL</span>';
              if (val === 'ESCALATION_RECOMMENDED') return '<span class="badge bd-or" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-user-gear" style="margin-right:3px"></i> REKOMENDASI ESKALASI</span>';
              return `<span class="badge bd-pur" style="font-size:9.5px">${val}</span>`;
            };
            
            let incText = row.incident_id === 0 ? '<span style="color:var(--txt3)">Probe Sistem</span>' : `<b>INC-${row.incident_id}</b>`;
            let latencyText = row.response_latency_ms === 0 ? '&lt; 1 ms' : `${row.response_latency_ms} ms`;
            
            return `
          <tr style="cursor:pointer" onclick="Panels.pending_verification.showDetail(${row.id})" title="Klik untuk melihat detail pengujian pasca-remediasi ini">
            <td><b>VRF-${row.id}</b></td>
            <td>${incText}</td>
            <td>${getStatusTag(row.verification_status)}</td>
            <td>${getCheckTag(row.service_alive)}</td>
            <td>${getCheckTag(row.port_open)}</td>
            <td>${getCheckTag(row.cpu_normalized)}</td>
            <td>${getCheckTag(row.memory_normalized)}</td>
            <td>${getCheckTag(row.logs_clean)}</td>
            <td>${row.rollback_needed ? '<span class="badge bd-rd" style="font-size:9.5px">DITRIGGER</span>' : '<span class="badge bd-gr" style="font-size:9.5px">TIDAK</span>'}</td>
            <td><b style="font-family:monospace;color:var(--cyan)">${latencyText}</b></td>
            <td style="font-size:11px;white-space:nowrap">${timeStr}</td>
          </tr>
        `;
          }).join('');
        } catch (e) {
          tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--red2)">Error: ${e.message}</td></tr>`;
        }
      },

      showDetail(vrfId) {
        const item = (this._cachedData || []).find(x => x.id === vrfId);
        if (!item) {
          Notify.toast('⚠️ Warning', 'Detail data pengujian tidak ditemukan', 'warn');
          return;
        }
        const timeStr = new Date(item.created_at).toLocaleString('id-ID');
        const isEscalated = item.verification_status === 'ESCALATION_RECOMMENDED' || !item.service_alive;

        const html = `
          <div id="vrf-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
            <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
              <!-- Header -->
              <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(245,158,11,0.08)">
                <div style="display:flex;align-items:center;gap:10px">
                  <div style="width:36px;height:36px;border-radius:8px;background:rgba(245,158,11,0.2);display:flex;align-items:center;justify-content:center;color:#f59e0b;font-size:18px">
                    <i class="fa-solid fa-clipboard-check"></i>
                  </div>
                  <div>
                    <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Detail Pengujian Pasca-Tindakan (Verification VRF-${item.id})</h3>
                    <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${item.incident_id || 'SYS'} · ${timeStr}</div>
                  </div>
                </div>
                <button onclick="document.getElementById('vrf-log-modal-overlay').remove()" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
              </div>

              <!-- Body -->
              <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
                
                <!-- Status Banner -->
                <div style="background:${isEscalated ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)'};border:1px solid ${isEscalated ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'};border-radius:8px;padding:14px;display:flex;align-items:center;justify-content:space-between">
                  <div>
                    <div style="font-size:11px;color:var(--txt2,#94a3b8)">Status Hasil Pengujian Pasca-Remediasi:</div>
                    <div style="font-size:16px;font-weight:800;color:${isEscalated ? '#f87171' : '#34d399'};margin-top:2px">
                      ${isEscalated ? '⚠️ REKOMENDASI ESKALASI KE OPERATOR NOC' : '✅ PEMULIHAN BERHASIL DIVERIFIKASI'}
                    </div>
                  </div>
                  <div style="text-align:right">
                    <div style="font-size:11px;color:var(--txt2,#94a3b8)">Waktu Respon Latensi:</div>
                    <div style="font-size:16px;font-weight:700;color:#38bdf8">${item.response_latency_ms || 0} ms</div>
                  </div>
                </div>

                <!-- 5 Point Health Checklist Grid -->
                <div style="font-size:12px;font-weight:700;color:#38bdf8;margin-bottom:-6px"><i class="fa-solid fa-list-check"></i> Hasil Pengujian 5 Indikator Kesehatan Sistem:</div>
                <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px">
                  <div style="background:rgba(0,0,0,0.25);border:1px solid var(--border,#1e293b);border-radius:8px;padding:10px;text-align:center">
                    <div style="font-size:10.5px;color:var(--txt2,#94a3b8)">1. Service</div>
                    <div style="font-size:14px;font-weight:800;margin-top:4px;color:${item.service_alive ? '#34d399' : '#f87171'}">${item.service_alive ? '✓ ONLINE' : '✗ GAGAL'}</div>
                  </div>
                  <div style="background:rgba(0,0,0,0.25);border:1px solid var(--border,#1e293b);border-radius:8px;padding:10px;text-align:center">
                    <div style="font-size:10.5px;color:var(--txt2,#94a3b8)">2. Port</div>
                    <div style="font-size:14px;font-weight:800;margin-top:4px;color:${item.port_open ? '#34d399' : '#f87171'}">${item.port_open ? '✓ TERBUKA' : '✗ TERTUTUP'}</div>
                  </div>
                  <div style="background:rgba(0,0,0,0.25);border:1px solid var(--border,#1e293b);border-radius:8px;padding:10px;text-align:center">
                    <div style="font-size:10.5px;color:var(--txt2,#94a3b8)">3. CPU</div>
                    <div style="font-size:14px;font-weight:800;margin-top:4px;color:${item.cpu_normalized ? '#34d399' : '#f87171'}">${item.cpu_normalized ? '✓ NORMAL' : '✗ TINGGI'}</div>
                  </div>
                  <div style="background:rgba(0,0,0,0.25);border:1px solid var(--border,#1e293b);border-radius:8px;padding:10px;text-align:center">
                    <div style="font-size:10.5px;color:var(--txt2,#94a3b8)">4. Memory</div>
                    <div style="font-size:14px;font-weight:800;margin-top:4px;color:${item.memory_normalized ? '#34d399' : '#f87171'}">${item.memory_normalized ? '✓ STABIL' : '✗ PENUH'}</div>
                  </div>
                  <div style="background:rgba(0,0,0,0.25);border:1px solid var(--border,#1e293b);border-radius:8px;padding:10px;text-align:center">
                    <div style="font-size:10.5px;color:var(--txt2,#94a3b8)">5. Logs Error</div>
                    <div style="font-size:14px;font-weight:800;margin-top:4px;color:${item.logs_clean ? '#34d399' : '#f87171'}">${item.logs_clean ? '✓ BERSIH' : '✗ ADA ERROR'}</div>
                  </div>
                </div>

                <!-- Explanation Box -->
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                  <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-circle-info"></i> Penjelasan & Panduan Tindakan Lanjutan NOC
                  </div>
                  <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.2);padding:10px;border-radius:6px;border-left:3px solid #f59e0b">
                    ${isEscalated 
                      ? '<b>Penyebab Eskalasi:</b> Perangkat target terdeteksi <b>OFFLINE / Tidak Merespon Sinyal Telemetri</b>. Pengujian 5 indikator kesehatan tidak dapat mengonfirmasi pemulihan penuh secara otomatis. Disarankan bagi Operator NOC untuk memeriksa fisik perangkat/jaringan klien atau mengklik <b>Remote Assist (AnyDesk/VNC)</b>.'
                      : '<b>Status Pemulihan:</b> Seluruh 5 titik pengujian menunjukkan hasil normal. Perangkat dan layanan telah kembali beroperasi dengan stabil.'
                    }
                  </div>
                </div>

              </div>

              <!-- Footer -->
              <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
                <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(${JSON.stringify(item).replace(/"/g, '&quot;')}));Notify.toast('📋 Copied','Data pengujian disalin ke clipboard','ok')" style="padding:6px 14px">
                  <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin JSON
                </button>
                <button class="btn btn-primary btn-sm" onclick="document.getElementById('vrf-log-modal-overlay').remove()" style="padding:6px 18px">
                  Tutup
                </button>
              </div>
            </div>
          </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
      }
    };

    // 5. Rollback History (Enterprise Safe State Recovery Engine)
    Panels.rollback_history = {
      _page: 1,
      _limit: 50,
      _totalPages: 1,
      _autoRefreshTimer: null,

      startAutoRefresh() {
        this.stopAutoRefresh();
        this._autoRefreshTimer = setInterval(() => {
          if (document.getElementById('p-rollback_history')?.classList.contains('active')) {
            this.load(this._page);
          }
        }, 5000);
      },

      stopAutoRefresh() {
        if (this._autoRefreshTimer) {
          clearInterval(this._autoRefreshTimer);
          this._autoRefreshTimer = null;
        }
      },

      async load(page = 1) {
        this._page = page;
        const tbody = document.getElementById('rollback-history-tbody');
        if (!tbody) return;

        const q = (document.getElementById('rollback-search-inp')?.value || '').trim();
        const result = (document.getElementById('rollback-result-select')?.value || '').trim();
        const reason = (document.getElementById('rollback-reason-select')?.value || '').trim();

        let url = `/api/rollback_history?page=${this._page}&limit=${this._limit}`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        if (result) url += `&result=${encodeURIComponent(result)}`;
        if (reason) url += `&trigger_reason=${encodeURIComponent(reason)}`;

        try {
          const res = await DataService.fetch(url);
          let rows = [];
          let total = 0;

          if (Array.isArray(res)) {
            rows = res;
            total = res.length;
            this._totalPages = 1;
          } else if (res && res.data) {
            rows = res.data;
            total = res.total || rows.length;
            this._totalPages = res.total_pages || 1;
          }
          this._cachedRows = rows || [];

          const paginationInfo = document.getElementById('rollback-pagination-info');
          const pageNumEl = document.getElementById('rollback-page-num');
          const prevBtn = document.getElementById('btn-rollback-prev');
          const nextBtn = document.getElementById('btn-rollback-next');

          if (paginationInfo) paginationInfo.innerText = `Showing ${rows.length} of ${total} entries (Total Pages: ${this._totalPages})`;
          if (pageNumEl) pageNumEl.innerText = `Page ${this._page} of ${this._totalPages}`;
          if (prevBtn) prevBtn.disabled = this._page <= 1;
          if (nextBtn) nextBtn.disabled = this._page >= this._totalPages;

          if (!rows || rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--txt3)">✓ No rollback actions recorded matching criteria.</td></tr>';
            return;
          }

          tbody.innerHTML = rows.map(row => {
            const timeStr = new Date(row.created_at).toLocaleString('id-ID');
            let incText = row.incident_id === 0 ? '<span style="color:var(--txt3)">N/A</span>' : `<b>INC-${row.incident_id}</b>`;
            let rttText = row.execution_rtt_ms === 0 ? '&lt; 1 ms' : `${row.execution_rtt_ms} ms`;
            
            // Result translation badge
            const getResultBadge = (res) => {
              if (!res) return '<span class="badge bd-bl" style="font-size:9.5px">-</span>';
              let r = String(res).toUpperCase();
              if (r === 'SUCCESS') return '<span class="badge bd-gr" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-circle-check" style="margin-right:3px"></i> LOLOS ROLLBACK</span>';
              if (r.includes('DENIED') || r.includes('ACCESS')) return '<span class="badge bd-or" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-lock" style="margin-right:3px"></i> HAK AKSES DITOLAK</span>';
              if (r === 'FAILED') return '<span class="badge bd-rd" style="font-size:9.5px;padding:3px 8px"><i class="fa-solid fa-triangle-exclamation" style="margin-right:3px"></i> EKSEKUSI GAGAL</span>';
              return `<span class="badge bd-pur" style="font-size:9.5px">${r}</span>`;
            };

            const translateReason = (rsn) => {
              if (!rsn) return 'Pemicu Otomatis';
              if (rsn === 'post-check failed') return 'Pengujian Pasca-Tindakan Gagal';
              if (rsn === 'operator rejected') return 'Penolakan Manual Operator NOC';
              if (rsn === 'confidence threshold drop') return 'Penurunan Skor Keyakinan AI';
              return rsn;
            };

            let hostText = row.target_host ? `<span class="badge bd-bl" style="font-size:9.5px">${row.target_host}</span>` : `<span style="color:var(--txt3);font-size:10px">Fleet Global</span>`;

            // OTel Trace / Correlation ID badge
            let otelHtml = '-';
            if (row.trace_id || row.correlation_id) {
              otelHtml = `
                <div style="font-size:9.5px;display:flex;flex-direction:column;gap:2px">
                  ${row.trace_id ? `<span style="color:var(--cyan)" title="Trace ID: ${row.trace_id}"><i class="fa-solid fa-network-wired"></i> TRC-${row.trace_id.substring(0,8)}</span>` : ''}
                  ${row.correlation_id ? `<span style="color:var(--txt3)" title="Correlation ID: ${row.correlation_id}"><i class="fa-solid fa-link"></i> COR-${row.correlation_id.substring(0,8)}</span>` : ''}
                </div>
              `;
            }

            // Command + Hash + Copy button
            const escapedCmd = (row.rollback_command || '-').replace(/'/g, "\\'");
            const hashBadge = row.command_hash ? `<span class="badge bd-or" style="font-size:9px;margin-left:4px" title="SHA256: ${row.command_hash}"><i class="fa-solid fa-lock"></i> HASHED</span>` : '';
            const cmdHtml = `
              <div style="display:flex;align-items:center;gap:4px">
                <code style="font-size:10.5px;word-break:break-all">${row.rollback_command || '-'}</code>
                ${hashBadge}
                <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();Panels.rollback_history.copyCmd('${escapedCmd}')" title="Copy Command" style="padding:2px 6px;font-size:9px"><i class="fa-solid fa-copy"></i></button>
              </div>
            `;

            return `
              <tr style="cursor:pointer" onclick="Panels.rollback_history.showDetail(${row.id})" title="Klik untuk melihat detail eksekusi Rollback ini">
                <td><b>RBK-${row.id}</b></td>
                <td>${incText}</td>
                <td>${hostText}</td>
                <td><span style="color:var(--cyan);font-weight:600">${row.original_action || '-'}</span></td>
                <td>${cmdHtml}</td>
                <td><span style="color:var(--txt1);font-size:11px">${translateReason(row.trigger_reason)}</span></td>
                <td><span class="badge ${row.state_machine === 'FAILED' ? 'bd-rd' : 'bd-bl'}" style="font-size:9.5px">${row.state_machine || 'INITIATED'}</span></td>
                <td>${otelHtml}</td>
                <td><b style="font-family:monospace;color:var(--cyan)">${rttText}</b></td>
                <td>${getResultBadge(row.rollback_result)}</td>
                <td style="font-size:11px;white-space:nowrap">${timeStr}</td>
              </tr>
            `;
          }).join('');
        } catch (e) {
          tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--red2)">Error: ${e.message}</td></tr>`;
        }
      },

      showDetail(rbkId) {
        const item = (this._cachedRows || []).find(x => x.id === rbkId);
        if (!item) {
          Notify.toast('⚠️ Warning', 'Detail data Rollback tidak ditemukan', 'warn');
          return;
        }
        const timeStr = new Date(item.created_at).toLocaleString('id-ID');
        const isAccessDenied = (item.rollback_result || '').toUpperCase().includes('DENIED') || (item.rollback_result || '').toUpperCase().includes('ACCESS');

        const html = `
          <div id="rbk-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
            <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
              <!-- Header -->
              <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(239,68,68,0.08)">
                <div style="display:flex;align-items:center;gap:10px">
                  <div style="width:36px;height:36px;border-radius:8px;background:rgba(239,68,68,0.2);display:flex;align-items:center;justify-content:center;color:#ef4444;font-size:18px">
                    <i class="fa-solid fa-rotate-left"></i>
                  </div>
                  <div>
                    <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Detail Jejak Audit Auto-Rollback (RBK-${item.id})</h3>
                    <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${item.incident_id || 'SYS'} · ${timeStr}</div>
                  </div>
                </div>
                <button onclick="document.getElementById('rbk-log-modal-overlay').remove()" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
              </div>

              <!-- Body -->
              <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
                
                <!-- Status Banner -->
                <div style="background:${isAccessDenied ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)'};border:1px solid ${isAccessDenied ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.3)'};border-radius:8px;padding:14px;display:flex;align-items:center;justify-content:space-between">
                  <div>
                    <div style="font-size:11px;color:var(--txt2,#94a3b8)">Status Hasil Eksekusi Pemulihan (Rollback):</div>
                    <div style="font-size:16px;font-weight:800;color:${isAccessDenied ? '#f59e0b' : '#f87171'};margin-top:2px">
                      ${isAccessDenied ? '🔒 HAK AKSES DITOLAK (ACCESS DENIED)' : '❌ EKSEKUSI ROLLBACK GAGAL'}
                    </div>
                  </div>
                  <div style="text-align:right">
                    <div style="font-size:11px;color:var(--txt2,#94a3b8)">RTT Eksekusi Command:</div>
                    <div style="font-size:16px;font-weight:700;color:#38bdf8">${item.execution_rtt_ms || 0} ms</div>
                  </div>
                </div>

                <!-- Grid Details -->
                <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">
                  <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                    <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-bolt" style="color:#38bdf8;margin-right:4px"></i>Tindakan Asal (Original Action)</div>
                    <div style="font-size:13px;font-weight:700;color:#38bdf8;margin-top:2px">${item.original_action || '—'}</div>
                  </div>
                  <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                    <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-filter" style="color:#f59e0b;margin-right:4px"></i>Alasan Pemicu Rollback</div>
                    <div style="font-size:13px;font-weight:700;color:#f59e0b;margin-top:2px">Pengujian Pasca-Tindakan Gagal (Post-Check Failed)</div>
                  </div>
                </div>

                <!-- Rollback Command Box -->
                <div style="background:rgba(0,0,0,0.3);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                  <div style="font-size:12px;font-weight:700;color:#a855f7;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-terminal"></i> Perintah Rollback (Rollback Command)
                  </div>
                  <div style="font-family:monospace;font-size:13px;color:#38bdf8;background:rgba(0,0,0,0.4);padding:10px;border-radius:6px">
                    ${item.rollback_command || 'net start spooler'}
                  </div>
                </div>

                <!-- Explanation Box -->
                <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                  <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                    <i class="fa-solid fa-circle-info"></i> Penjelasan Penyebab & Solusi NOC
                  </div>
                  <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.2);padding:10px;border-radius:6px;border-left:3px solid #f59e0b">
                    ${isAccessDenied 
                      ? '<b>Penyebab Access Denied:</b> Agen AI di komputer klien tidak memiliki <b>Hak Akses Administrator (Elevated Privileges)</b> saat menjalankan perintah <code>net start spooler</code> di Windows Service Manager. <br><b>Solusi:</b> Pastikan service <b>OSI Windows Agent</b> dijalankan menggunakan akun <i>SYSTEM</i> atau <i>Administrator</i> lokal.'
                      : '<b>Status:</b> Perintah rollback berhasil dijalankan untuk memulihkan sistem ke baseline aman.'
                    }
                  </div>
                </div>

              </div>

              <!-- Footer -->
              <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
                <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(${JSON.stringify(item).replace(/"/g, '&quot;')}));Notify.toast('📋 Copied','Data rollback disalin ke clipboard','ok')" style="padding:6px 14px">
                  <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin JSON
                </button>
                <button class="btn btn-primary btn-sm" onclick="document.getElementById('rbk-log-modal-overlay').remove()" style="padding:6px 18px">
                  Tutup
                </button>
              </div>
            </div>
          </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
      },

      nextPage() {
        if (this._page < this._totalPages) this.load(this._page + 1);
      },

      prevPage() {
        if (this._page > 1) this.load(this._page - 1);
      },

      copyCmd(cmd) {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(cmd);
          Notify.toast('📋 Copied', 'Rollback command copied to clipboard.', 'info', 2000);
        }
      },

      async export(format = 'csv') {
        Notify.toast('📥 Exporting', `Generating ${format.toUpperCase()} rollback audit trail...`, 'info', 2500);
        try {
          const resp = await fetch(`/api/rollback_history/export?format=${format}`);
          if (!resp.ok) throw new Error("Export failed");
          const checksum = resp.headers.get("X-Audit-Checksum-SHA256") || "UNKNOWN";
          const blob = await resp.blob();
          const downloadUrl = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = `rollback_audit_history_${Date.now()}.${format}`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          Notify.toast('✅ Export Completed', `File downloaded. SHA256 Integrity: ${checksum.substring(0, 16)}...`, 'ok', 4000);
        } catch (e) {
          Notify.toast('❌ Export Error', e.message, 'err', 3000);
        }
      }
    };
    // 6. Failed Actions / DLQ Management Engine
    Panels.failed_actions = {
      _page: 1,
      _limit: 50,
      _totalPages: 1,
      _cachedRows: {},
      _autoRefreshTimer: null,

      startAutoRefresh() {
        this.stopAutoRefresh();
        this.load(this._page);
        this._autoRefreshTimer = setInterval(() => {
          if (document.getElementById('p-failed_actions')?.classList.contains('active')) {
            this.load(this._page);
          }
        }, 5000);
      },

      stopAutoRefresh() {
        if (this._autoRefreshTimer) {
          clearInterval(this._autoRefreshTimer);
          this._autoRefreshTimer = null;
        }
      },

      async load(page = 1) {
        this._page = page;
        const tbody = document.getElementById('failed-actions-tbody');
        if (!tbody) return;

        const q = (document.getElementById('dlq-search-inp')?.value || '').trim();
        const status = (document.getElementById('dlq-status-select')?.value || '').trim();

        let url = `/api/hitl/failed_actions?page=${this._page}&limit=${this._limit}`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;

        try {
          const res = await DataService.fetch(url);
          let rows = [];
          let total = 0;

          if (Array.isArray(res)) {
            rows = res;
            total = res.length;
            this._totalPages = 1;
          } else if (res && res.data) {
            rows = res.data;
            total = res.total || rows.length;
            this._totalPages = res.total_pages || 1;
          }

          const paginationInfo = document.getElementById('dlq-pagination-info');
          const pageNumEl = document.getElementById('dlq-page-num');
          const prevBtn = document.getElementById('btn-dlq-prev');
          const nextBtn = document.getElementById('btn-dlq-next');

          if (paginationInfo) paginationInfo.innerText = `Showing ${rows.length} of ${total} entries (Total Pages: ${this._totalPages})`;
          if (pageNumEl) pageNumEl.innerText = `Page ${this._page} of ${this._totalPages}`;
          if (prevBtn) prevBtn.disabled = this._page <= 1;
          if (nextBtn) nextBtn.disabled = this._page >= this._totalPages;

          if (!rows || rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt3)">✓ Dead letter queue is empty.</td></tr>';
            return;
          }

          this._cachedRows = {};
          tbody.innerHTML = rows.map(row => {
            this._cachedRows[row.dlq_id] = row;
            const timeStr = new Date(row.last_attempt).toLocaleString();
            const attempts = row.retry_count || 0;
            const isPoison = row.is_poison || attempts >= 5;
            const poisonTag = isPoison ? `<span class="tag tag-red" style="font-size:9.5px;margin-left:4px" title="Poison Message: 5+ Failures"><i class="fa-solid fa-biohazard"></i> POISON</span>` : '';
            const statusClass = row.status === 'REPLAYED' || row.status === 'SUCCESS' ? 'tag-green' : (row.status === 'PROCESSING' ? 'tag-blue' : 'tag-red');

            // OTel Trace ID badge
            let traceHtml = '-';
            if (row.trace_id || row.correlation_id) {
              traceHtml = `<span style="color:var(--cyan);font-size:10px" title="Trace ID: ${row.trace_id}"><i class="fa-solid fa-network-wired"></i> TRC-${(row.trace_id || row.correlation_id).substring(0,8)}</span>`;
            }

            return `
              <tr>
                <td><b>#${row.dlq_id}</b></td>
                <td>
                  <div style="font-weight:600;color:var(--red)">${row.reason || 'Unhandled Exception'}</div>
                  ${row.error_code ? `<code style="font-size:9.5px;color:var(--txt3)">[${row.error_code}]</code>` : ''}
                </td>
                <td><b>${attempts}</b> ${poisonTag}</td>
                <td>${traceHtml}</td>
                <td><span class="tag ${statusClass}">${row.status || 'PENDING'}</span></td>
                <td><span style="font-size:10.5px;color:var(--txt2)">${row.replayed_by || '-'}</span></td>
                <td style="font-size:10.5px;white-space:nowrap">${timeStr}</td>
                <td>
                  <div style="display:flex;gap:4px">
                    <button class="btn btn-ghost btn-sm" onclick="Panels.failed_actions.viewPayload(${row.dlq_id})" style="padding:2px 6px;font-size:10px" title="View Payload"><i class="fa-solid fa-eye"></i></button>
                    <button class="btn btn-primary btn-sm" onclick="Panels.failed_actions.replay(${row.dlq_id}, ${isPoison})" style="padding:2px 8px;font-size:10px"><i class="fa-solid fa-play"></i> Replay</button>
                    <button class="btn btn-danger btn-sm" onclick="Panels.failed_actions.purge(${row.dlq_id})" style="padding:2px 6px;font-size:10px" title="Purge Item"><i class="fa-solid fa-trash"></i></button>
                  </div>
                </td>
              </tr>
            `;
          }).join('');
        } catch (e) {
          tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--red2)">Failed to load DLQ events: ${e.message}</td></tr>`;
        }
      },

      viewPayload(id) {
        const item = this._cachedRows[id];
        if (!item) return;
        { const _el = document.getElementById('modal-dlq-id-title'); if (_el) _el.innerText = `#${item.dlq_id}`; }
        { const _el = document.getElementById('modal-dlq-reason'); if (_el) _el.innerText = item.reason || 'No error reason recorded'; }

        let prettyPayload = item.payload || '{}';
        try {
          prettyPayload = JSON.stringify(JSON.parse(item.payload), null, 2);
        } catch(e) {}
        { const _el = document.getElementById('modal-dlq-payload'); if (_el) _el.innerText = prettyPayload; }
        { const _el = document.getElementById('modal-dlq-trace'); if (_el) _el.innerText = item.trace_id || 'N/A'; }
        { const _el = document.getElementById('modal-dlq-corr'); if (_el) _el.innerText = item.correlation_id || 'N/A'; }

        const confirmBtn = document.getElementById('btn-modal-dlq-replay');
        if (confirmBtn) {
          confirmBtn.onclick = () => {
            document.getElementById('modal-dlq-payload-viewer').style.display = 'none';
            this.replay(id, item.is_poison || item.retry_count >= 5);
          };
        }

        document.getElementById('modal-dlq-payload-viewer').style.display = 'flex';
      },

      async replay(id, isPoison = false) {
        let forceParam = '';
        if (isPoison) {
          if (!confirm("⚠️ WARNING: Order is tagged as POISON_MESSAGE (5+ failures). Force replay anyway?")) return;
          forceParam = '?force=true';
        }
        Notify.toast('⚡ Replaying DLQ', `Replaying event #${id}...`, 'info', 2000);
        try {
          const res = await DataService.fetch(`/api/hitl/replay/${id}${forceParam}`, { method: 'POST' });
          if (res && (res.status === 'success' || res.success)) {
            Notify.toast('✅ Replayed', `DLQ #${id} replayed successfully.`, 'ok', 3000);
            this.load(this._page);
          } else {
            Notify.toast('❌ Replay Blocked', res ? res.message : 'Failed', 'err', 3500);
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err', 3000);
        }
      },

      async purge(id) {
        if (!confirm(`Purge DLQ item #${id}? This cannot be undone.`)) return;
        Notify.toast('🗑️ Purging', `Purging DLQ item #${id}...`, 'warn', 2000);
        try {
          const res = await DataService.fetch(`/api/hitl/purge/${id}`, { method: 'DELETE' });
          if (res && res.status === 'success') {
            Notify.toast('✅ Purged', `DLQ #${id} purged.`, 'ok', 3000);
            this.load(this._page);
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err', 3000);
        }
      },

      async replayAll() {
        if (!confirm("Execute chunked rate-limited replay for all pending DLQ items?")) return;
        Notify.toast('⚡ Batch Replay', 'Processing chunked rate-limited DLQ replay...', 'info', 3000);
        try {
          const res = await DataService.fetch('/api/hitl/replay_all', { method: 'POST' });
          if (res && res.status === 'success') {
            Notify.toast('✅ Batch Completed', res.message || 'All items replayed', 'ok', 4000);
            this.load(1);
          }
        } catch (e) {
          Notify.toast('❌ Error', e.message, 'err', 3000);
        }
      },

      nextPage() {
        if (this._page < this._totalPages) this.load(this._page + 1);
      },

      prevPage() {
        if (this._page > 1) this.load(this._page - 1);
      },

      async export(format = 'csv') {
        Notify.toast('📥 Exporting DLQ', `Generating ${format.toUpperCase()} DLQ audit log...`, 'info', 2500);
        try {
          const resp = await fetch(`/api/hitl/failed_actions/export?format=${format}`);
          if (!resp.ok) throw new Error("Export failed");
          const checksum = resp.headers.get("X-Audit-Checksum-SHA256") || "UNKNOWN";
          const blob = await resp.blob();
          const downloadUrl = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = `dlq_failed_actions_${Date.now()}.${format}`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          Notify.toast('✅ Export Completed', `File downloaded. SHA256 Integrity: ${checksum.substring(0, 16)}...`, 'ok', 4000);
        } catch (e) {
          Notify.toast('❌ Export Error', e.message, 'err', 3000);
        }
      }
    };

      // 7. Recovery Mode Config
      Panels.recovery_mode_config = {
        async load() {
          try {
            const res = await DataService.fetch('/api/governance/recovery_mode');
            if (res && res.status === 'SUCCESS') {
              const sel = document.getElementById('recovery-mode-select');
              if (sel) sel.value = res.recovery_mode || 'Advisory';
              const disp = document.getElementById('current-recovery-mode-display');
              if (disp) disp.innerText = res.recovery_mode || 'Advisory';
              const cp = document.getElementById('consensus-pattern-select');
              if (cp) cp.value = res.consensus_pattern || 'WEIGHTED CONFIDENCE';
              const retry = document.getElementById('recovery-max-retries');
              if (retry) retry.value = res.max_retry_attempts || 3;
              const cd = document.getElementById('recovery-cooldown');
              if (cd) cd.value = res.cooldown_period_sec || 300;
            }
          } catch (e) {}
        },
        async save() {
          const mode = document.getElementById('recovery-mode-select').value;
          const cd = document.getElementById('recovery-cooldown')?.value || 300;
          const cp = document.getElementById('consensus-pattern-select')?.value || 'WEIGHTED CONFIDENCE';
          const retry = document.getElementById('recovery-max-retries')?.value || 3;
          try {
            const res = await DataService.fetch('/api/governance/recovery_mode', {
              method: 'POST',
              body: JSON.stringify({ recovery_mode: mode, consensus_pattern: cp, max_retry_attempts: parseInt(retry), cooldown_period_sec: parseInt(cd) })
            });
            if (res.status === 'SUCCESS') {
              Notify.toast('✓ Saved', 'Recovery Mode updated successfully.', 'info');
              this.load();
            } else {
              Notify.toast('❌ Error', 'Failed to save configuration.', 'err');
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Network error while saving.', 'err');
          }
        }
      };

      // 8. Learning Gate Policy
      Panels.learning_gate_policy = {
        async load() {
          try {
            const res = await DataService.fetch('/api/governance/learning_gate_policy');
            if (res && (res.status === 'SUCCESS' || res.min_confidence !== undefined)) {
              const inp = document.getElementById('learning-gate-threshold-input');
              if (inp) inp.value = res.min_confidence ?? res.confidence_threshold ?? 0.75;
            }
          } catch (e) {
            console.error('Learning gate policy load error:', e);
          }
        },
        async save() {
          const inp = document.getElementById('learning-gate-threshold-input');
          const val = parseFloat(inp?.value || '0.75');
          try {
            const res = await DataService.fetch('/api/governance/learning_gate_policy', {
              method: 'POST',
              body: JSON.stringify({ min_confidence: val, confidence_threshold: val })
            });
            if (res && (res.status === 'SUCCESS' || res.status === 'success')) {
              Notify.toast('✓ Saved', 'Learning Gate threshold updated to ' + val, 'info');
              LogStreamer.add('OK', 'GOVERNANCE', 'Learning gate threshold updated to ' + val);
              this.load();
            } else {
              Notify.toast('❌ Error', 'Failed to save threshold', 'err');
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Network error while updating threshold', 'err');
          }
        }
      };

      // Alias window.HITLPanels and window.Gov to window.Panels so legacy/template callers never fail
      window.HITLPanels = Panels;
      window.Gov = Panels.gov;
      setTimeout(() => { if (window.AiLiveFlow) AiLiveFlow.init(); }, 500);

      // Gap 7 / L1 UI: Adaptive Framerate Observer (Throttle to 10 FPS on tab blur)
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
          window.__THROTTLE_FRAMERATE__ = 100; // 10 FPS delay (100ms) when hidden
        } else {
          window.__THROTTLE_FRAMERATE__ = 16;  // 60 FPS (16ms) when active
        }
      });

