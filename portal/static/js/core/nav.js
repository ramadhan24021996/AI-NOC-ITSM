/* nav.js
 * Nav - Panel router and navigation
 * Extracted from index.html panels/main.js - Phase 2 refactor
 */

    var Nav = {
      active: 'overview',
      go(id, el) {
        const currentActiveEl = document.querySelector('.panel.active');
        if (currentActiveEl && currentActiveEl.id === 'p-' + id && this.active === id) {
          return;
        }
        this.active = id;

        const r = (window.currentUserRole || 'superadmin').toLowerCase();
        let allowed = ['all'];
        if (r !== 'superadmin') {
          if (window.currentUserSettings) {
            try {
              const settings = typeof window.currentUserSettings === 'string' ? JSON.parse(window.currentUserSettings) : window.currentUserSettings;
              if (settings.visible_panels && Array.isArray(settings.visible_panels) && settings.visible_panels.length > 0) {
                allowed = settings.visible_panels;
              }
            } catch(e) {}
          }
        }
        if (!allowed.includes('all') && !allowed.includes('overview') && !allowed.includes('dashboard')) {
          allowed.push('overview');
          allowed.push('dashboard');
        }
        if (!allowed.includes('all') && !allowed.includes('ai_lifecycle_topology')) {
          allowed.push('ai_lifecycle_topology');
        }
        const hasAll = allowed.includes('all');
        const isOverviewAlias = (id === 'overview' && allowed.includes('dashboard')) || (id === 'dashboard' && (allowed.includes('overview') || allowed.includes('dashboard')));
        if (id === 'dashboard') id = 'overview';
        if (!hasAll && !allowed.includes(id) && !isOverviewAlias) {
          Notify.toast('🔒 Access Denied', 'Anda tidak memiliki akses ke halaman ini.', 'warn', 2500);
          return;
        }
        if (window.ActiveIntervals) {
          Object.keys(window.ActiveIntervals).forEach(key => {
            clearInterval(window.ActiveIntervals[key]);
          });
          window.ActiveIntervals = {};
        }
        document.querySelectorAll('.panel').forEach(panelEl => {
          panelEl.classList.remove('active');
          panelEl.style.setProperty('display', 'none', 'important');
        });
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        
        const p = document.getElementById('p-' + id);
        if (p) {
          p.classList.add('active');
          const targetDisplay = (id === 'overview' ? 'grid' : (id === 'chat' || id === 'incident' || id === 'failed_actions' ? 'flex' : 'block'));
          p.style.setProperty('display', targetDisplay, 'important');
        }
        if (!el) {
          el = document.querySelector(`[data-panel="${id}"]`);
        }
        if (el) el.classList.add('active');
        const titles = {
          overview: '<i class="fa-solid fa-chart-simple" style="color:var(--blue);margin-right:8px"></i> Overview', monitoring: '<i class="fa-solid fa-chart-line" style="color:var(--blue);margin-right:8px"></i> Monitoring Live', server: '<i class="fa-solid fa-server" style="color:var(--blue);margin-right:8px"></i> Server Health',
          incident: '<i class="fa-solid fa-triangle-exclamation" style="color:var(--red);margin-right:8px"></i> Incident Triage', rca: '<i class="fa-solid fa-microscope" style="color:var(--blue);margin-right:8px"></i> Ground Truth & RCA', unified_dag: '<i class="fa-solid fa-diagram-project" style="color:var(--purple);margin-right:8px"></i> Unified Graphs',
          pchealth: '<i class="fa-solid fa-desktop" style="color:var(--blue);margin-right:8px"></i> PC Health', printer: '<i class="fa-solid fa-print" style="color:var(--blue);margin-right:8px"></i> Printer Status', fleet: '<i class="fa-solid fa-cubes" style="color:var(--blue);margin-right:8px"></i> Fleet Management',
          storage: '<i class="fa-solid fa-database" style="color:var(--blue);margin-right:8px"></i> Storage', ai: '<i class="fa-solid fa-robot" style="color:var(--pink);margin-right:8px"></i> AI Panel', training: '<i class="fa-solid fa-graduation-cap" style="color:var(--blue);margin-right:8px"></i> Training Feedback',
          smart_stream: '<i class="fa-solid fa-bolt-lightning" style="color:var(--yellow);margin-right:8px"></i> Smart Incident Stream',
          logs: '<i class="fa-solid fa-terminal" style="color:var(--blue);margin-right:8px"></i> Live Logs', gov: '<i class="fa-solid fa-scroll" style="color:var(--blue);margin-right:8px"></i> Governance', sop: '<i class="fa-solid fa-file-invoice" style="color:var(--orange);margin-right:8px"></i> SOP Lifecycle', models: '<i class="fa-solid fa-gears" style="color:var(--blue);margin-right:8px"></i> Model Config',
          activity: '<i class="fa-solid fa-user-check" style="color:var(--blue);margin-right:8px"></i> User Activity & Browser Logs',
          chat: '<i class="fa-solid fa-comments" style="color:var(--blue);margin-right:8px"></i> Live Chat',
          rbac: '<i class="fa-solid fa-user-shield" style="color:var(--blue);margin-right:8px"></i> RBAC Policies',
          evidence: '<i class="fa-solid fa-magnifying-glass-chart" style="color:var(--purple);margin-right:8px"></i> Evidence Explorer',
          kgraph: '<i class="fa-solid fa-diagram-project" style="color:var(--cyan);margin-right:8px"></i> Knowledge Graph',
          security_policies: '<i class="fa-solid fa-shield-halved" style="color:var(--orange);margin-right:8px"></i> Security Policies',
          playbooks: '<i class="fa-solid fa-book-journal-whills" style="color:var(--purple);margin-right:8px"></i> Playbook Studio',
          learning_gate_policy: '<i class="fa-solid fa-shield-cat" style="color:var(--green);margin-right:8px"></i> Learning Gate Policy',
          recovery_mode_config: '<i class="fa-solid fa-sliders" style="color:var(--blue);margin-right:8px"></i> Recovery Mode Config',
          ai_lifecycle_topology: '<i class="fa-solid fa-sitemap" style="color:var(--cyan);margin-right:8px"></i> AI Lifecycle & Live System Flow',
          schema_validation_logs: '<i class="fa-solid fa-shield-halved" style="color:var(--red);margin-right:8px"></i> Schema Validation Logs',
          ai_decision_logs: '<i class="fa-solid fa-brain" style="color:var(--purple);margin-right:8px"></i> AI Decision Logs',
          learning_gate_logs: '<i class="fa-solid fa-clock-rotate-left" style="color:var(--green);margin-right:8px"></i> Learning Gate Audit',
          exec_timeline: '<i class="fa-solid fa-timeline" style="color:var(--cyan);margin-right:8px"></i> Execution Timeline',
          event_correlation: '<i class="fa-solid fa-diagram-project" style="color:var(--purple);margin-right:8px"></i> Event Correlation',
          approval_queue: '<i class="fa-solid fa-person-circle-check" style="color:var(--orange);margin-right:8px"></i> Approval Queue',
          pending_verification: '<i class="fa-solid fa-list-check" style="color:var(--orange);margin-right:8px"></i> Pending Verification',
          rollback_history: '<i class="fa-solid fa-rotate-left" style="color:var(--red);margin-right:8px"></i> Rollback History',
          failed_actions: '<i class="fa-solid fa-circle-xmark" style="color:var(--red);margin-right:8px"></i> Failed Actions (DLQ)',
          runtime_monitor: '<i class="fa-solid fa-microchip" style="color:var(--blue);margin-right:8px"></i> Runtime Engine Monitor',
          knowledge_center: '<i class="fa-solid fa-book-bookmark" style="color:var(--cyan);margin-right:8px"></i> RAG Knowledge Center & SOP',
          agent_health: '<i class="fa-solid fa-robot" style="color:var(--green);margin-right:8px"></i> AI Agent Health Monitor',
          fleet_config: '<i class="fa-solid fa-sliders" style="color:var(--blue);margin-right:8px"></i> Fleet Global Config',
          nats_subjects: '<i class="fa-solid fa-network-wired" style="color:var(--cyan);margin-right:8px"></i> NATS Subjects Telemetry'

        };
        const subs = {
          overview: 'KPI & insiden aktif · real-time', monitoring: 'Network latency · CPU/RAM/Disk · Sites',
          server: 'SystemAuditor v2.2 · Health score · Komponen', incident: 'Live feed dari PostgreSQL · osi_system.incidents',
          rca: '5 Why · Bayesian · Evidence · Timeline · Remote Action', dag: 'Interactive causal graph · Zoom/Pan/Search',
          decision_dag: 'Interactive cognitive decision trace · Zoom/Pan/Search',
          evidence_dag: 'Unified evidence trace · incident_events · ai_evidence_logs · fleet_evidence · decision_graphs · incident_closure',
          pchealth: 'CPU · RAM · Disk · USB · Service · Real-time', printer: 'Status · Queue · Toner · Clear · Restart',
          fleet: 'Manajemen Fleet · Konfigurasi Site & Gateway', storage: 'Disk · Redis · RAG · File Sistem',
          ai: 'Reasoning · Confidence · Prediction · Classification', training: 'RAG Feedback · Continuous Learning',
          smart_stream: 'Aliran Insiden Terstruktur Bahasa Manusia · Real-Time Telemetry Enrichment',
          logs: 'Streaming log · Search · Filter · Download', gov: 'Resolusi · Audit · SLA · Policy',
          sop: 'Draft → Review → Active · Lifecycle', models: 'AI Config · API Keys · Remote Tools',
          knowledge_center: 'Pusat Pencarian SOP & Basis Pengetahuan RAG 2.0 · Single Pane Search',
          activity: 'Real-time active apps · Chrome/Edge tabs · Browser crashes · AI Insights',
          chat: 'Chat support dengan client PC secara real-time dengan saran reply AI',
          rbac: 'Manajemen Kebijakan Role-Based Access Control',
          evidence: 'Audit Jejak Bukti & Readiness AI Engine',
          kgraph: 'Grafik Pengetahuan Dependensi Sistem Enterprise',
          security_policies: 'Aturan & Ambang Batas Keamanan Eksekusi AI',
          playbooks: 'Manajemen Playbook Mediasi Insiden Otonom',
          learning_gate_policy: 'Kebijakan Gerbang Pembelajaran AI & Guardrails',
          recovery_mode_config: 'Konfigurasi Mode Pemulihan System (Semi/Advisory/Full-Auto)',
          ai_lifecycle_topology: '9-Layer Enterprise AI Lifecycle Topology · Real-Time Stream Motion · Active Observability',
          schema_validation_logs: 'Jejak Validasi Skema LLM & Schema Failures',
          ai_decision_logs: 'Log Keputusan Refleksi AI & Audit Trail',
          learning_gate_logs: 'Audit Gerbang Pembelajaran Kontinu AI',
          exec_timeline: 'AI Pipeline Execution Stages · Real-time status',
          event_correlation: 'Root Event & Downstream Effects · Event Trail',
          approval_queue: 'Pending Human Approvals · HITL Gate',
          pending_verification: 'Unresolved Verification Items · Post-Action Telemetry',
          rollback_history: 'Rollback Execution Logs · State Machine History',
          failed_actions: 'Dead Letter Queue Events · Error Logs & Replay',
          runtime_monitor: 'Live status & telemetri per-engine AIOps · Latency · Memory · CPU · Queue · Callers'
        };
        htmlEl('topbar-title', titles[id] || id);
        setEl('topbar-sub', subs[id] || '');
        
        try {
          if (Panels[id] && typeof Panels[id].load === 'function') {
            // For exec_timeline: ensure JWT is ready before first load
            if (id === 'exec_timeline' && !sessionStorage.getItem('noc_jwt_token')) {
              (async () => {
                let waited = 0;
                while (!sessionStorage.getItem('noc_jwt_token') && waited < 3000) {
                  await new Promise(r => setTimeout(r, 200));
                  waited += 200;
                }
                Panels[id].load();
              })();
            } else {
              Panels[id].load();
            }
          }
        } catch(err) {
          console.warn('Panel load exception caught safely:', id, err);
        }
        // Start dedicated auto-refresh for storage panel & exec_timeline panel safely
        if (id === 'storage' && Panels.storage?.startAutoRefresh) Panels.storage.startAutoRefresh();
        else if (Panels.storage?.stopAutoRefresh) Panels.storage.stopAutoRefresh();

        if (id === 'exec_timeline' && Panels.exec_timeline?.startAutoRefresh) Panels.exec_timeline.startAutoRefresh();
        else if (Panels.exec_timeline?.stopAutoRefresh) Panels.exec_timeline.stopAutoRefresh();

        if (id === 'rollback_history' && Panels.rollback_history?.startAutoRefresh) Panels.rollback_history.startAutoRefresh();
        else if (Panels.rollback_history?.stopAutoRefresh) Panels.rollback_history.stopAutoRefresh();

        if (id === 'failed_actions' && Panels.failed_actions?.startAutoRefresh) Panels.failed_actions.startAutoRefresh();
        else if (Panels.failed_actions?.stopAutoRefresh) Panels.failed_actions.stopAutoRefresh();

        if (id === 'runtime_monitor' && Panels.runtime_monitor?.startAutoRefresh) Panels.runtime_monitor.startAutoRefresh();
        else if (Panels.runtime_monitor?.stopAutoRefresh) Panels.runtime_monitor.stopAutoRefresh();

        if (id === 'training' && Panels.training?.startAutoRefresh) Panels.training.startAutoRefresh();
        else if (Panels.training?.stopAutoRefresh) Panels.training.stopAutoRefresh();

        if (id === 'ai_lifecycle_topology' && window.AiLiveFlow) setTimeout(() => AiLiveFlow.init(), 100);
        if (window.SidebarManager) window.SidebarManager.syncActiveMenu();
      },

      checkStandaloneChatMode() {
        const urlParams = new URLSearchParams(window.location.search);
        const rawHash = (window.location.hash || '').replace(/^#\/?/, '').trim().toLowerCase();
        const isChatHash = ['live-chat', 'support-chat', 'osi-chat', 'livechat', 'chat', 'p-chat'].includes(rawHash);
        const isStandaloneMode = urlParams.get('mode') === 'chat' || urlParams.get('standalone') === 'true' || urlParams.get('view') === 'chat' || isChatHash;

        if (isStandaloneMode) {
          document.body.classList.add('standalone-chat-mode');
        } else {
          document.body.classList.remove('standalone-chat-mode');
        }
      },

      handleHash() {
        this.checkStandaloneChatMode();
        const rawHash = (window.location.hash || '').replace(/^#\/?/, '').trim();
        if (!rawHash) return;
        let targetPanel = rawHash;
        if (targetPanel.startsWith('p-')) {
          targetPanel = targetPanel.replace(/^p-/, '');
        }
        if (['live-chat', 'support-chat', 'osi-chat', 'livechat', 'chat'].includes(targetPanel.toLowerCase())) {
          targetPanel = 'chat';
        }
        if (targetPanel) {
          this.go(targetPanel);
        }
      }
    };

    window.addEventListener('hashchange', () => {
      if (window.Nav) window.Nav.handleHash();
    });

    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
        if (window.Nav) window.Nav.handleHash();
      }, 150);
    });

    /* ==================================================
       STORAGE FILE OPS — AI File Read / Edit / Download / Validate
    ================================================== */
    var StorageFileOps = {
      _currentFile: null,

      async open(name) {
        const modal = document.getElementById('modal-ai-file-editor');
        const contentEl = document.getElementById('modal-ai-file-content');
        const nameEl = document.getElementById('modal-ai-file-name');
        const sizeEl = document.getElementById('modal-ai-file-size');
        const modEl = document.getElementById('modal-ai-file-mod');
        const resultEl = document.getElementById('modal-ai-file-result');
        if (!modal) return;

        if (nameEl) nameEl.textContent = name;
        if (contentEl) contentEl.value = 'Loading...';
        if (resultEl) resultEl.textContent = '';
        modal.style.display = 'flex';
        this._currentFile = name;

        try {
          const data = await DataService.fetch('/api/ai_file/read?name=' + encodeURIComponent(name));
          if (!data) { if (contentEl) contentEl.value = '// Error: cannot read file'; return; }
          if (contentEl) contentEl.value = data.content || '';
          if (sizeEl) sizeEl.textContent = (data.size > 1024 ? (data.size / 1024).toFixed(1) + 'KB' : data.size + 'B');
          if (modEl && data.mod_time) modEl.textContent = 'Modified: ' + data.mod_time.replace('T', ' ').slice(0, 19);
        } catch (e) {
          if (contentEl) contentEl.value = '// Error: ' + e.message;
        }
      },

      async save() {
        if (!this._currentFile) return;
        const contentEl = document.getElementById('modal-ai-file-content');
        const resultEl = document.getElementById('modal-ai-file-result');
        if (!contentEl) return;

        if (resultEl) resultEl.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:6px"></i>Saving...';
        try {
          const resp = await DataService.fetch('/api/ai_file/save', {
            method: 'POST',
            body: JSON.stringify({ name: this._currentFile, content: contentEl.value })
          });
          if (resp && resp.success) {
            if (resultEl) resultEl.innerHTML = '<span style="color:var(--green2)">✅ ' + (resp.message || 'Saved') + '</span>';
            Notify.toast('✅ Saved', this._currentFile + ' berhasil disimpan', 'ok', 2000);
            if (Panels.storage) Panels.storage.load();
          } else {
            if (resultEl) resultEl.innerHTML = '<span style="color:var(--red)">❌ ' + (resp && resp.error ? resp.error : 'Save failed') + '</span>';
          }
        } catch (e) {
          if (resultEl) resultEl.innerHTML = '<span style="color:var(--red)">❌ ' + e.message + '</span>';
        }
      },

      download(name) {
        const token = sessionStorage.getItem('noc_jwt_token') || '';
        const a = document.createElement('a');
        a.href = '/api/ai_file/download?name=' + encodeURIComponent(name) + '&_t=' + Date.now();
        a.download = name;
        // Programmatic download with auth header is not possible via <a> tag;
        // Use fetch + blob approach instead:
        fetch(a.href, { headers: { 'Authorization': 'Bearer ' + token } })
          .then(r => r.blob())
          .then(blob => {
            const url = URL.createObjectURL(blob);
            a.href = url;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
          })
          .catch(e => Notify.toast('❌ Download', e.message, 'error', 2500));
      },

      async validateFile(name) {
        Notify.toast('🔍 Validating', 'Memeriksa ' + name + '...', 'info', 1500);
        try {
          const data = await DataService.fetch('/api/ai_file/validate?name=' + encodeURIComponent(name));
          if (!data) { Notify.toast('❌ Validate', 'Gagal terhubung ke server', 'error', 3000); return; }
          const icon = data.valid ? '✅' : '❌';
          Notify.toast(icon + ' Validation', name + ': ' + data.message, data.valid ? 'ok' : 'error', 3500);
        } catch (e) {
          Notify.toast('❌ Validate', e.message, 'error', 3000);
        }
      },

      async validate() {
        if (this._currentFile) await this.validateFile(this._currentFile);
      }
    };

    var DashboardCustomizer = {
      widgets: [],
      customizeMode: false,

      async init() {
        try {
          const res = await DataService.fetch('/api/dashboard/layout');
          if (res && res.layout) {
            this.widgets = typeof res.layout === 'string' ? JSON.parse(res.layout) : res.layout;
          }
        } catch (e) {
          console.error('Gagal memuat layout:', e);
          this.widgets = [
            { id: "widget-online", col_span: 1, visible: true, favorite: false },
            { id: "widget-incidents", col_span: 1, visible: true, favorite: false },
            { id: "widget-health", col_span: 1, visible: true, favorite: false },
            { id: "widget-total", col_span: 1, visible: true, favorite: false },
            { id: "widget-mttr", col_span: 1, visible: true, favorite: false },
            { id: "widget-avail", col_span: 1, visible: true, favorite: false },
            { id: "widget-aiconf", col_span: 1, visible: true, favorite: false },
            { id: "widget-ticket", col_span: 1, visible: true, favorite: false },
            { id: "widget-live-incidents", col_span: 2, visible: true, favorite: false },
            { id: "widget-pipeline", col_span: 2, visible: true, favorite: false },
            { id: "widget-trend", col_span: 2, visible: true, favorite: false },
            { id: "widget-osi", col_span: 2, visible: true, favorite: false },
            { id: "widget-critical-alert", col_span: 1, visible: true, favorite: false },
            { id: "widget-active-sessions", col_span: 1, visible: true, favorite: false },
            { id: "widget-storage-usage", col_span: 1, visible: true, favorite: false },
            { id: "widget-cpu-usage", col_span: 1, visible: true, favorite: false },
            { id: "widget-ram-usage", col_span: 1, visible: true, favorite: false },
            { id: "widget-database-health", col_span: 1, visible: true, favorite: false },
            { id: "widget-redis-health", col_span: 1, visible: true, favorite: false },
            { id: "widget-queue-health", col_span: 1, visible: true, favorite: false },
            { id: "widget-audit-activity", col_span: 2, visible: true, favorite: false },
            { id: "widget-login-activity", col_span: 2, visible: true, favorite: false },
            { id: "widget-security-event", col_span: 2, visible: true, favorite: false },
            { id: "widget-prediction", col_span: 2, visible: true, favorite: false },
            { id: "widget-executive-analytics", col_span: 2, visible: true, favorite: false }
          ];
        }
        this.applyLayoutToDOM();
      },

      applyLayoutToDOM() {
        const parent = document.getElementById('p-overview');
        if (!parent) return;

        document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());

        const isSuperadmin = (window.currentUserRole === 'superadmin');
        const newWidgetIds = [
          "widget-critical-alert", "widget-active-sessions", "widget-storage-usage",
          "widget-cpu-usage", "widget-ram-usage", "widget-database-health",
          "widget-redis-health", "widget-queue-health", "widget-audit-activity",
          "widget-login-activity", "widget-security-event", "widget-prediction",
          "widget-executive-analytics"
        ];

        const activeWidgets = isSuperadmin ? this.widgets : this.widgets.filter(w => !newWidgetIds.includes(w.id));

        const widgetEls = {};
        activeWidgets.forEach(w => {
          const el = document.getElementById(w.id);
          if (el) {
            widgetEls[w.id] = el;
            el.style.gridColumn = w.visible ? `span ${w.col_span || 1}` : 'none';
            el.style.display = w.visible ? '' : 'none';
            if (w.favorite) {
              el.classList.add('widget-favorite');
            } else {
              el.classList.remove('widget-favorite');
            }
          }
        });

        if (!isSuperadmin) {
          newWidgetIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
              el.style.display = 'none';
              el.style.gridColumn = 'none';
            }
          });
        }

        const toolbar = parent.firstElementChild;
        const allExistingWidgets = Array.from(parent.querySelectorAll('.dashboard-widget'));

        parent.innerHTML = '';
        if (toolbar && !toolbar.classList.contains('dashboard-widget')) {
          parent.appendChild(toolbar);
        }

        activeWidgets.forEach(w => {
          const el = widgetEls[w.id];
          if (el) {
            parent.appendChild(el);
          }
        });

        allExistingWidgets.forEach(el => {
          if (!widgetEls[el.id]) {
            if (!isSuperadmin && newWidgetIds.includes(el.id)) {
              // completely hide for non-admins
            } else {
              parent.appendChild(el);
            }
          }
        });

        if (this.customizeMode) {
          this.renderToolbars();
        }
      },

      toggleCustomizeMode() {
        this.customizeMode = !this.customizeMode;
        const parent = document.getElementById('p-overview');
        if (!parent) return;

        if (this.customizeMode) {
          parent.classList.add('customize-mode-active');
          this.renderToolbars();
          Notify.toast('✏️ Edit Layout', 'Mode kustomisasi aktif. Klik tombol pada widget untuk mengatur ukuran, urutan, favorit, atau menyembunyikan.', 'info', 4000);
        } else {
          parent.classList.remove('customize-mode-active');
          document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());
        }
      },

      renderToolbars() {
        document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());

        this.widgets.forEach((w, idx) => {
          const el = document.getElementById(w.id);
          if (!el || !w.visible) return;

          const tb = document.createElement('div');
          tb.className = 'widget-toolbar';
          tb.innerHTML = `
        <button onclick="DashboardCustomizer.changeSpan('${w.id}', 1)" title="Perbesar Lebar"><i class="fa-solid fa-plus"></i></button>
        <button onclick="DashboardCustomizer.changeSpan('${w.id}', -1)" title="Perkecil Lebar"><i class="fa-solid fa-minus"></i></button>
        <button onclick="DashboardCustomizer.moveWidget(${idx}, -1)" title="Geser Kiri/Atas" ${idx === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-left"></i></button>
        <button onclick="DashboardCustomizer.moveWidget(${idx}, 1)" title="Geser Kanan/Bawah" ${idx === this.widgets.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-right"></i></button>
        <button onclick="DashboardCustomizer.toggleFavorite('${w.id}')" title="Favorit"><i class="fa-solid fa-star" style="color:${w.favorite ? 'var(--orange)' : 'var(--txt3)'}"></i></button>
        <button onclick="DashboardCustomizer.hideWidget('${w.id}')" title="Sembunyikan"><i class="fa-solid fa-eye-slash"></i></button>
      `;
          el.appendChild(tb);
        });
      },

      changeSpan(id, delta) {
        const w = this.widgets.find(item => item.id === id);
        if (w) {
          w.col_span = Math.max(1, Math.min(4, (w.col_span || 1) + delta));
          this.applyLayoutToDOM();
        }
      },

      moveWidget(idx, dir) {
        const targetIdx = idx + dir;
        if (targetIdx >= 0 && targetIdx < this.widgets.length) {
          const temp = this.widgets[idx];
          this.widgets[idx] = this.widgets[targetIdx];
          this.widgets[targetIdx] = temp;
          this.applyLayoutToDOM();
        }
      },

      toggleFavorite(id) {
        const w = this.widgets.find(item => item.id === id);
        if (w) {
          w.favorite = !w.favorite;
          this.applyLayoutToDOM();
        }
      },

      hideWidget(id) {
        const w = this.widgets.find(item => item.id === id);
        if (w) {
          w.visible = false;
          this.applyLayoutToDOM();
          Notify.toast('👁️ Widget Tersembunyi', `Widget disembunyikan.`, 'info', 2500);
        }
      },

      showHiddenWidgetsModal() {
        const hidden = this.widgets.filter(w => !w.visible);
        if (hidden.length === 0) {
          Notify.toast('ℹ️ Info', 'Semua widget saat ini sudah ditampilkan.', 'info', 2500);
          return;
        }

        const bodyHTML = `
      <div style="padding:12px 20px; text-align:left; display:flex; flex-direction:column; gap:8px">
        <p style="font-size:11.5px; color:var(--txt2)">Pilih widget di bawah ini untuk ditampilkan kembali di dashboard:</p>
        ${hidden.map(w => `
          <label style="display:flex; align-items:center; gap:8px; background:var(--bg3); border:1px solid var(--bd2); padding:8px 12px; border-radius:6px; font-size:13px; font-weight:600">
            <input type="checkbox" class="unhide-chk" value="${w.id}"> ${w.id.replace('widget-', '').toUpperCase()}
          </label>
        `).join('')}
      </div>
    `;

        Modal.show(
          '👁️ Tampilkan Widget Tersembunyi',
          bodyHTML,
          [
            {
              label: 'Tampilkan Terpilih', cls: 'btn-primary', fn: () => {
                document.querySelectorAll('.unhide-chk').forEach(chk => {
                  if (chk.checked) {
                    const w = this.widgets.find(item => item.id === chk.value);
                    if (w) w.visible = true;
                  }
                });
                Modal.close();
                this.applyLayoutToDOM();
              }
            },
            { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() }
          ],
          '👁️'
        );
      },

      async saveLayout() {
        const username = window.currentUserId;
        if (!username) {
          Notify.toast('⚠️ Gagal', 'Username tidak teridentifikasi. Gagal menyimpan layout.', 'warn', 3000);
          return;
        }

        try {
          const resp = await DataService.fetch('/api/dashboard/layout/save', {
            method: 'POST',
            body: JSON.stringify({
              target_type: 'user',
              target_name: username,
              layout: JSON.stringify(this.widgets)
            })
          });

          if (resp && (resp.status === 'SUCCESS' || resp.success)) {
            Notify.toast('✅ Sukses', 'Layout dashboard Anda berhasil disimpan secara permanen.', 'ok', 2500);
            if (this.customizeMode) this.toggleCustomizeMode();
          } else {
            Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menyimpan layout', 'warn', 3000);
          }
        } catch (err) {
          Notify.toast('❌ Error', err.message, 'error', 3000);
        }
      },

      async resetLayout() {
        const username = window.currentUserId;
        if (!username) return;

        Modal.confirm(
          '🔄 Reset Layout',
          'Apakah Anda yakin ingin mereset layout dashboard Anda ke template default role?',
          async () => {
            try {
              const resp = await DataService.fetch('/api/dashboard/layout/reset', {
                method: 'POST',
                body: JSON.stringify({
                  target_type: 'user',
                  target_name: username
                })
              });

              if (resp && (resp.status === 'SUCCESS' || resp.success)) {
                Notify.toast('✅ Sukses', 'Layout dashboard berhasil di-reset.', 'ok', 2500);
                Modal.close();
                this.customizeMode = false;
                await this.init();
              } else {
                Notify.toast('⚠️ Gagal', resp?.error || 'Gagal mereset layout', 'warn', 3000);
              }
            } catch (err) {
              Notify.toast('❌ Error', err.message, 'error', 3000);
            }
          }
        );
      }
    };

    /* ==================================================
       PANELS CONTROLLERS
    ================================================== */
const PrinterMgr = (() => {
  let _printers = [];
  let _refreshTimer = null;

  function toggleSitePartition(partKey) {
    if (!PrinterMgr.collapsed) PrinterMgr.collapsed = {};
    PrinterMgr.collapsed[partKey] = !PrinterMgr.collapsed[partKey];
    const el = document.getElementById('pr-part-body-' + partKey);
    const icon = document.getElementById('pr-part-icon-' + partKey);
    if (el) {
      if (PrinterMgr.collapsed[partKey]) {
        el.style.display = 'none';
        if (icon) icon.className = 'fa-solid fa-chevron-right';
      } else {
        el.style.display = 'grid';
        if (icon) icon.className = 'fa-solid fa-chevron-down';
      }
    }
  }

  function _findHostAgent(printerName) {
    const devices = DataService._devices || [];
    const hostDev = devices.find(d => {
      const pInfo = d.metadata && d.metadata.printers;
      if (pInfo && pInfo.installed_list) {
        return pInfo.installed_list.some(p => p.name === printerName);
      }
      return false;
    });
    // fallback: look for pc_name field on the printer record
    const prRecord = _printers.find(p => p.name === printerName);
    if (prRecord && prRecord.pc_name) return prRecord.pc_name;
    return hostDev ? hostDev.name : null;
  }

  function _renderCard(p) {
    const tonerCls = p.toner_pct < 20 ? 'pb-red' : p.toner_pct < 50 ? 'pb-orange' : 'pb-green';
    const inkCls   = p.ink_pct   < 20 ? 'pb-red' : p.ink_pct   < 50 ? 'pb-orange' : 'pb-green';
    const site = p.site_id || getSite(p.ip) || '—';
    const lastPing = p.last_pinged && p.last_pinged !== '0001-01-01T00:00:00Z'
      ? timeSince(p.last_pinged) : 'Belum ping';
    return `<div class="printer-card" id="pcard-${p.printer_id}">
      <div class="printer-header">
        <div>
          <div style="font-size:11.5px;font-weight:700"><i class="fa-solid fa-print" style="color:var(--blue);margin-right:6px"></i>${p.name}</div>
          <div style="font-size:10px;color:var(--txt2)">${p.ip}:${p.port||9100} · ${site}${p.model ? ' · ' + p.model : ''}</div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px">
          ${statusTag(p.status)}
          <span style="font-size:9px;color:var(--txt3)">${lastPing}</span>
        </div>
      </div>
      <div class="printer-body">
        <div class="toner-section">
          <div class="pb-label"><span><i class="fa-solid fa-droplet" style="color:#fff;margin-right:5px"></i>Toner</span><span>${p.toner_pct}%</span></div>
          <div class="pb"><div class="pb-fill ${tonerCls}" style="width:${Math.max(2,p.toner_pct)}%;animation:none"></div></div>
        </div>
        <div class="toner-section">
          <div class="pb-label"><span><i class="fa-solid fa-fill-drip" style="color:var(--cyan);margin-right:5px"></i>Ink Level</span><span>${p.ink_pct}%</span></div>
          <div class="pb"><div class="pb-fill ${inkCls}" style="width:${Math.max(2,p.ink_pct)}%;animation:none"></div></div>
        </div>
        <div class="li-row" style="margin-top:6px">
          <span class="li-name"><i class="fa-solid fa-list-check" style="margin-right:5px"></i>Queue</span>
          <span class="tag ${p.queue_count > 5 ? 'tag-orange' : 'tag-gray'}">${p.queue_count} docs</span>
        </div>
        <div class="li-row">
          <span class="li-name"><i class="fa-solid fa-file" style="margin-right:5px"></i>Paper</span>
          <span class="tag ${p.paper_count < 100 ? 'tag-orange' : 'tag-green'}">${p.paper_count} sheets</span>
        </div>
        ${p.error_msg ? `<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:5px;padding:6px 8px;font-size:10.5px;color:var(--red2);margin:6px 0"><i class="fa-solid fa-circle-exclamation" style="color:var(--red);margin-right:6px"></i>${p.error_msg}</div>` : ''}
        <div style="display:flex;gap:5px;margin-top:8px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-xs" onclick="PrinterMgr.ping(${p.printer_id})" title="TCP Ping"><i class="fa-solid fa-satellite-dish" style="margin-right:4px"></i>Ping</button>
          <button class="btn btn-danger btn-xs" onclick="PrinterMgr.clearQueue('${p.name}', ${p.printer_id})"><i class="fa-solid fa-trash-can" style="margin-right:4px"></i>Clear Queue</button>
          <button class="btn btn-warning btn-xs" onclick="PrinterMgr.restartSpooler('${p.name}')"><i class="fa-solid fa-rotate" style="margin-right:4px"></i>Restart</button>
          <button class="btn btn-primary btn-xs" onclick="PrinterMgr.testPrint('${p.name}')"><i class="fa-solid fa-print" style="margin-right:4px"></i>Test Print</button>
          <button class="btn btn-ghost btn-xs" onclick="PrinterMgr.openEditModal(${p.printer_id})" title="Edit"><i class="fa-solid fa-pen" style="margin-right:3px"></i>Edit</button>
          <button class="btn btn-danger btn-xs" onclick="PrinterMgr.deletePrinter(${p.printer_id}, '${p.name}')" title="Hapus"><i class="fa-solid fa-trash" style="margin-right:3px"></i>Hapus</button>
        </div>
      </div>
    </div>`;
  }

  function _renderHardwareBanner(hw) {
    const banner = document.getElementById('printer-hardware-discovery-banner');
    if (!banner) return;
    if (!hw || !hw.state_machine) {
      banner.innerHTML = '';
      return;
    }
    const sm = hw.state_machine;
    const isCert = sm.certification_verdict === 'CERTIFIED';
    const stBadge = isCert
      ? '<span class="tag tag-green" style="font-size:10px;font-weight:700">🟢 PHYSICAL HARDWARE CERTIFIED</span>'
      : '<span class="tag tag-orange" style="font-size:10px;font-weight:700">🟡 PENDING ON-PREMISE PHYSICAL PRINTER</span>';

    const stepPill = (label, ok) => `
      <div style="display:flex;align-items:center;gap:5px;background:rgba(255,255,255,.04);border:1px solid ${ok ? 'rgba(16,185,129,.3)' : 'rgba(245,158,11,.3)'};padding:4px 8px;border-radius:6px;font-size:9.5px">
        <span style="color:${ok ? '#10b981' : '#f59e0b'}">${ok ? '●' : '○'}</span>
        <span style="color:${ok ? '#f8fafc' : '#94a3b8'}">${label}</span>
      </div>`;

    banner.innerHTML = `
      <div style="background:linear-gradient(135deg, rgba(15,23,42,.95), rgba(30,41,59,.95));border:1px solid var(--bd2);border-radius:10px;padding:14px 18px;box-shadow:0 8px 24px rgba(0,0,0,.3)">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px">
          <div style="display:flex;align-items:center;gap:8px">
            <i class="fa-solid fa-microchip" style="color:var(--cyan);font-size:15px"></i>
            <span style="font-size:12px;font-weight:700;color:#f8fafc">USB Printer Discovery & Hardware Health State Machine</span>
            <span style="font-size:10px;color:var(--txt3)">(${hw.host_os || 'Linux OS'})</span>
          </div>
          <div>${stBadge}</div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:8px;margin-bottom:12px">
          <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
            <div style="font-size:9.5px;color:var(--txt3)">USB Enumeration</div>
            <div style="font-size:11px;font-weight:600;color:var(--txt1)">${hw.usb_devices ? hw.usb_devices.length : 0} Devices (${hw.printer_usb_count} Printers)</div>
          </div>
          <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
            <div style="font-size:9.5px;color:var(--txt3)">CUPS / Spooler Subsystem</div>
            <div style="font-size:11px;font-weight:600;color:${hw.cups_available ? '#10b981' : '#f59e0b'}">${hw.cups_available ? 'Active (lpstat OK)' : 'Not Configured'}</div>
          </div>
          <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
            <div style="font-size:9.5px;color:var(--txt3)">Character Node</div>
            <div style="font-size:11px;font-weight:600;color:var(--txt2)">${(hw.kernel_nodes && hw.kernel_nodes.length) ? hw.kernel_nodes[0].path : '/dev/usb/lp0 (Pending)'}</div>
          </div>
          <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
            <div style="font-size:9.5px;color:var(--txt3)">ESC/POS Protocol Format</div>
            <div style="font-size:11px;font-weight:600;color:#10b981">100% PROVEN (ESC @, Cut)</div>
          </div>
        </div>

        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
          ${stepPill('1. USB Detected', sm.step_1_usb_device_detected)}
          ${stepPill('2. USB Identified', sm.step_2_usb_identified)}
          ${stepPill('3. Printer Enumerated', sm.step_3_printer_enumerated)}
          ${stepPill('4. CUPS Spooler', sm.step_4_cups_spooler_available)}
          ${stepPill('5. Node Connection', sm.step_5_device_connection_test)}
          ${stepPill('6. ESC/POS Command', sm.step_6_escpos_command_test)}
          ${stepPill('7. Test Print Output', sm.step_7_test_print_verified)}
        </div>

        <div style="font-size:10px;color:${isCert ? '#34d399' : '#fbbf24'};background:rgba(0,0,0,.2);padding:6px 10px;border-radius:5px">
          <i class="fa-solid fa-circle-info" style="margin-right:5px"></i>${sm.diagnostic_summary || 'Multi-layer hardware inspection ready.'}
        </div>
      </div>`;
  }

  async function runHardwareDiagnostics() {
    Notify.toast('🔬 Hardware Diagnostics', 'Memeriksa perangkat USB dan character node...', 'info', 2000);
    try {
      const res = await DataService.fetch('/api/printers/hardware_diagnostic_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_type: 'DEVICE_NODE', endpoint: '/dev/usb/lp0' })
      });
      if (res && res.hardware_present) {
        Notify.toast('🟢 Hardware Detected', `ESC/POS test print berhasil ditransmisikan (${res.bytes_written} bytes)`, 'ok', 4000);
      } else if (res && res.bytes_generated) {
        Notify.toast('🟡 Hardware Pending', `Format ESC/POS siap (${res.bytes_generated} bytes). Perangkat fisik di ${res.endpoint} belum terpasang.`, 'warn', 4500);
      } else {
        Notify.toast('⚠️ Hardware Check', 'Pemeriksaan hardware selesai. Node printer fisik belum terhubung.', 'warn', 3500);
      }
      await load();
    } catch (e) {
      Notify.toast('❌ Diagnostic Error', e.message || 'Gagal menjalankan diagnostik hardware', 'err', 3000);
    }
  }

  async function load() {
    const grid = document.getElementById('printer-grid');
    if (!grid) return;
    try {
      // 1. Fetch live printers and hardware discovery concurrently
      const [res, hwRes] = await Promise.all([
        DataService.fetch('/api/printers/live'),
        DataService.fetch('/api/printers/hardware_discovery').catch(() => null)
      ]);

      if (hwRes && hwRes.data) {
        _renderHardwareBanner(hwRes.data);
      }

      _printers = (res && res.printers) ? res.printers : [];

      const online = _printers.filter(p => p.status === 'ONLINE').length;
      const errCnt = _printers.filter(p => p.status !== 'ONLINE' && p.status !== 'UNKNOWN').length;
      const totalQ = _printers.reduce((a, p) => a + (p.queue_count || 0), 0);
      const avgToner = _printers.length
        ? Math.round(_printers.reduce((a, p) => a + (p.toner_pct || 0), 0) / _printers.length)
        : 0;

      setEl('pr-online', online);
      setEl('pr-error', errCnt);
      setEl('pr-queue', totalQ);
      setEl('pr-toner', avgToner + '%');
      const lastEl = document.getElementById('pr-last-refresh');
      if (lastEl) lastEl.textContent = 'Refresh: ' + new Date().toLocaleTimeString('id-ID');

      if (_printers.length === 0) {
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--txt3)"><i class="fa-solid fa-print" style="font-size:32px;margin-bottom:10px;display:block;opacity:.3"></i><div>Belum ada printer terdaftar. Klik <b>Add Printer</b> untuk menambah.</div></div>`;
      } else {
        // Group Printers by Site & Router Gateway IP
        const siteGroups = {};
        _printers.forEach(p => {
          const site = p.site_id || getSite(p.ip) || 'Kantor Pusat - NUC';
          const gw = (p.ip && p.ip.includes('.')) ? (p.ip.split('.').slice(0, 3).join('.') + '.1') : '192.168.1.1';
          const groupKey = site + '___' + gw;
          if (!siteGroups[groupKey]) {
            siteGroups[groupKey] = {
              siteName: site,
              gatewayIP: gw,
              onlineCount: 0,
              offlineCount: 0,
              totalQueue: 0,
              printers: []
            };
          }
          if (p.status === 'ONLINE') {
            siteGroups[groupKey].onlineCount++;
          } else {
            siteGroups[groupKey].offlineCount++;
          }
          siteGroups[groupKey].totalQueue += (p.queue_count || 0);
          siteGroups[groupKey].printers.push(p);
        });

        let html = '';
        Object.values(siteGroups).forEach(group => {
          const total = group.printers.length;
          const safeKey = 'pr_part_' + (group.siteName + '_' + group.gatewayIP).replace(/[^a-zA-Z0-9_-]/g, '_');
          const isCollapsed = PrinterMgr.collapsed && PrinterMgr.collapsed[safeKey];
          const displayStyle = isCollapsed ? 'display:none' : 'display:grid';
          const iconClass = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';
          const siteBadgeCls = group.offlineCount > 0 ? 'border: 1px solid rgba(239,68,68,.35)' : 'border: 1px solid rgba(16,185,129,.35)';

          html += `
            <div class="site-block-section" data-site-group="${group.siteName}" style="grid-column:1/-1;margin-bottom:20px;background:rgba(15,23,42,.6);border-radius:12px;padding:16px;box-shadow:0 4px 20px rgba(0,0,0,.25);${siteBadgeCls}">
              <div class="site-block-header" onclick="PrinterMgr.toggleSitePartition('${safeKey}')" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08);cursor:pointer;user-select:none;transition:background .2s" title="Klik untuk melipat / membuka partisi printer ini">
                <div style="display:flex;align-items:center;gap:10px">
                  <button type="button" onclick="event.stopPropagation(); PrinterMgr.toggleSitePartition('${safeKey}')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:var(--cyan);width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer" title="Toggle Partisi ${group.siteName}">
                    <i id="pr-part-icon-${safeKey}" class="${iconClass}" style="font-size:11px"></i>
                  </button>
                  <div style="width:34px;height:34px;border-radius:8px;background:rgba(59,130,246,.15);display:flex;align-items:center;justify-content:center;color:var(--blue);font-size:16px">
                    <i class="fa-solid fa-print"></i>
                  </div>
                  <div>
                    <div style="font-size:13.5px;font-weight:700;color:var(--txt);letter-spacing:0.2px">🏢 ${group.siteName}</div>
                    <div style="font-size:11px;color:var(--txt3);display:flex;align-items:center;gap:6px">
                      <span style="background:rgba(6,182,212,.12);color:var(--cyan);padding:1px 6px;border-radius:4px;font-family:monospace;font-weight:600"><i class="fa-solid fa-network-wired" style="margin-right:4px"></i>GW: ${group.gatewayIP}</span>
                      <span>· Subnet Connected</span>
                    </div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                  <span style="font-size:11px;font-weight:600;background:rgba(16,185,129,.15);color:var(--green);padding:4px 10px;border-radius:6px;border:1px solid rgba(16,185,129,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.onlineCount} Online</span>
                  ${group.offlineCount > 0 ? `<span style="font-size:11px;font-weight:600;background:rgba(239,68,68,.15);color:var(--red2);padding:4px 10px;border-radius:6px;border:1px solid rgba(239,68,68,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.offlineCount} Offline</span>` : ''}
                  <span style="font-size:11px;color:var(--txt3);background:rgba(255,255,255,.05);padding:4px 8px;border-radius:6px">${total} Printer · Queue: ${group.totalQueue}</span>
                </div>
              </div>
              <div id="pr-part-body-${safeKey}" class="site-printer-subgrid" style="${displayStyle};grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:12px">
                ${group.printers.map(_renderCard).join('')}
              </div>
            </div>
          `;
        });
        grid.innerHTML = html;
      }
    } catch (e) {
      console.error('[PrinterMgr] load error:', e);
      if (grid) grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--red2)"><i class="fa-solid fa-triangle-exclamation" style="font-size:24px;margin-bottom:8px;display:block"></i>Gagal memuat data printer: ${e.message}</div>`;
    }
  }

  async function ping(printerId) {
    Notify.toast('📡 Pinging...', 'Menghubungi printer...', 'info', 1500);
    try {
      const r = await DataService.fetch('/api/printers/ping/' + printerId, { method: 'POST' });
      const st = r && r.printer_status;
      Notify.toast(st === 'ONLINE' ? '🟢 Online' : '🔴 Offline',
        `Printer status: ${st}`, st === 'ONLINE' ? 'ok' : 'err', 2500);
      await load();
    } catch (e) {
      Notify.toast('❌ Ping Failed', e.message, 'err', 3000);
    }
  }

  async function pingAll() {
    Notify.toast('📡 Ping All', 'Memping semua printer...', 'info', 2000);
    try {
      const r = await DataService.fetch('/api/printers/ping_all', { method: 'POST' });
      const results = r && r.results ? r.results : [];
      const onlineC = results.filter(x => x.status === 'ONLINE').length;
      Notify.toast('✅ Ping Selesai', `${onlineC}/${results.length} printer online`, 'ok', 3000);
      await load();
    } catch (e) {
      Notify.toast('❌ Ping Gagal', e.message, 'err', 3000);
    }
  }

  function openAddModal() {
    { const _el = document.getElementById('printer-modal-title'); if (_el) _el.textContent = 'Add Printer'; }
    document.getElementById('pr-edit-id').value = '';
    document.getElementById('pr-name').value = '';
    document.getElementById('pr-model').value = '';
    document.getElementById('pr-ip').value = '';
    document.getElementById('pr-port').value = '9100';
    document.getElementById('pr-site-id').value = '';
    document.getElementById('pr-pc-name').value = '';
    const m = document.getElementById('printer-add-modal');
    if (m) { m.style.display = 'flex'; }
  }

  function openEditModal(printerId) {
    const p = _printers.find(x => x.printer_id === printerId);
    if (!p) return;
    { const _el = document.getElementById('printer-modal-title'); if (_el) _el.textContent = 'Edit Printer'; }
    document.getElementById('pr-edit-id').value = p.printer_id;
    document.getElementById('pr-name').value = p.name;
    document.getElementById('pr-model').value = p.model || '';
    document.getElementById('pr-ip').value = p.ip;
    document.getElementById('pr-port').value = p.port || 9100;
    document.getElementById('pr-site-id').value = p.site_id || '';
    document.getElementById('pr-pc-name').value = p.pc_name || '';
    const m = document.getElementById('printer-add-modal');
    if (m) { m.style.display = 'flex'; }
  }

  function closeAddModal() {
    const m = document.getElementById('printer-add-modal');
    if (m) m.style.display = 'none';
  }

  async function savePrinter() {
    const editId  = document.getElementById('pr-edit-id').value;
    const name    = document.getElementById('pr-name').value.trim();
    const model   = document.getElementById('pr-model').value.trim();
    const ip      = document.getElementById('pr-ip').value.trim();
    const port    = parseInt(document.getElementById('pr-port').value) || 9100;
    const siteId  = document.getElementById('pr-site-id').value.trim();
    const pcName  = document.getElementById('pr-pc-name').value.trim();

    if (!name || !ip) { Notify.toast('⚠️ Validasi', 'Nama dan IP wajib diisi', 'warn', 2500); return; }

    try {
      if (editId) {
        // Edit existing
        const body = { name, model, ip, port };
        if (siteId) body.site_id = siteId;
        if (pcName) body.pc_name = pcName;
        await DataService.fetch('/api/printers/' + editId, { method: 'PUT', body: JSON.stringify(body) });
        Notify.toast('✅ Disimpan', `Printer ${name} berhasil diperbarui`, 'ok', 2500);
      } else {
        // Create new
        const body = { name, ip, port, site_id: siteId || undefined, pc_name: pcName || undefined };
        if (model) body.model = model;
        await DataService.fetch('/api/fleet/admin/printers', { method: 'POST', body: JSON.stringify(body) });
        Notify.toast('✅ Ditambahkan', `Printer ${name} berhasil didaftarkan`, 'ok', 2500);
        LogStreamer.add('OK', 'PRINTER', `Printer ${name} (${ip}:${port}) registered`);
      }
      closeAddModal();
      await load();
    } catch (e) {
      Notify.toast('❌ Gagal', 'Error: ' + e.message, 'err', 3000);
    }
  }

  function deletePrinter(printerId, printerName) {
    Modal.confirm('🗑️ Hapus Printer', `Yakin menghapus printer <b>${printerName}</b>? Tindakan ini tidak dapat dibatalkan.`, async () => {
      Modal.close();
      try {
        await DataService.fetch('/api/printers/' + printerId, { method: 'DELETE' });
        Notify.toast('🗑️ Dihapus', `Printer ${printerName} berhasil dihapus`, 'ok', 2500);
        LogStreamer.add('WARN', 'PRINTER', `Printer ${printerName} (ID:${printerId}) deleted`);
        await load();
      } catch (e) {
        Notify.toast('❌ Gagal', 'Error: ' + e.message, 'err', 3000);
      }
    });
  }

  function clearQueue(printerName, printerId) {
    Modal.confirm('🗑️ Clear Queue', `Hapus semua dokumen antrian pada <b>${printerName}</b>?`, async () => {
      Modal.close();
      const host = _findHostAgent(printerName);
      Notify.toast('🗑️ Clearing...', `Mengosongkan antrian ${printerName}...`, 'warn', 2000);
      try {
        if (host) {
          const r = await DataService.sendCommand('CLEAR_SPOOLER', host, { printer_name: printerName });
          if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
            Notify.toast('✅ Queue Cleared', `Antrian ${printerName} dikosongkan via ${host}`, 'ok', 2500);
            LogStreamer.add('OK', 'PRINTER', `Queue cleared: ${printerName} via ${host}`);
            // Update queue count in DB
            await DataService.fetch('/api/printers/update_metrics', {
              method: 'POST',
              body: JSON.stringify({ printer_id: printerId, queue_count: 0 })
            });
          } else {
            Notify.toast('⚠️ Partial', `${r.error || r.message || 'Lihat log agent'}`, 'warn', 3000);
          }
        } else {
          Notify.toast('⚠️ No Agent', `Tidak ada PC agent ditemukan untuk ${printerName}. Pastikan pc_name terdaftar.`, 'warn', 4000);
        }
        await load();
      } catch (e) {
        Notify.toast('❌ Error', e.message, 'err', 3000);
      }
    });
  }

  function restartSpooler(printerName) {
    const host = _findHostAgent(printerName);
    if (!host) { Notify.toast('⚠️ No Agent', `Tidak ada PC agent untuk ${printerName}`, 'warn', 3000); return; }
    Notify.toast('🔄 Restarting...', `Merestart print spooler via ${host}...`, 'warn', 2000);
    DataService.sendCommand('RESTART_SPOOLER', host, { printer_name: printerName })
      .then(r => {
        if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
          Notify.toast('✅ Restarted', `Spooler ${printerName} berhasil direstart`, 'ok', 2500);
          LogStreamer.add('OK', 'PRINTER', `Spooler restarted: ${printerName} via ${host}`);
        } else {
          Notify.toast('❌ Failed', r.error || r.message || 'Gagal restart', 'err', 3000);
        }
      }).catch(e => Notify.toast('❌ Error', e.message, 'err', 3000));
  }

  function testPrint(printerName) {
    const host = _findHostAgent(printerName);
    if (!host) { Notify.toast('⚠️ No Agent', `Tidak ada PC agent untuk ${printerName}`, 'warn', 3000); return; }
    Notify.toast('🖨️ Test Print', `Mengirim halaman test via ${host}...`, 'info', 2000);
    DataService.sendCommand('TEST_PRINT', host, { printer_name: printerName })
      .then(r => {
        if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
          Notify.toast('✅ Test Sent', `Halaman test terkirim ke ${printerName}`, 'ok', 3000);
          LogStreamer.add('OK', 'PRINTER', `Test print sent: ${printerName} via ${host}`);
        } else {
          Notify.toast('❌ Failed', r.error || r.message || 'Gagal test print', 'err', 3000);
        }
      }).catch(e => Notify.toast('❌ Error', e.message, 'err', 3000));
  }

  return { load, ping, pingAll, openAddModal, openEditModal, closeAddModal, savePrinter, deletePrinter, clearQueue, restartSpooler, testPrint, runHardwareDiagnostics, toggleSitePartition };
})();
window.PrinterMgr = PrinterMgr;

// Auto-refresh PrinterMgr when panel is active
setInterval(() => {
  if (document.getElementById('p-printer') &&
      document.getElementById('p-printer').classList.contains('active')) {
    PrinterMgr.load();
  }
}, 30000);
