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
          nats_subjects: '<i class="fa-solid fa-network-wired" style="color:var(--cyan);margin-right:8px"></i> NATS Subjects Telemetry',
          jarvis_voice_overview: '<i class="fa-solid fa-microphone-lines" style="color:var(--cyan);margin-right:8px"></i> JARVIS Voice Intelligence'

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
          runtime_monitor: 'Live status & telemetri per-engine AIOps · Latency · Memory · CPU · Queue · Callers',
          agent_health: 'Heartbeat · Telemetry Latency · Agent Version & Status',
          fleet_config: 'Konfigurasi Global Polling, Threshold & Kebijakan Agent Fleet',
          nats_subjects: 'Real-time Stream Broker · NATS JetStream Subjects & Throughput',
          jarvis_voice_overview: 'Full-Duplex Neural Voice Assistant · 3D Volumetric Hologram · NOC Command Center'
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

        if (id === 'ai_decision_logs' && Panels.ai_decision_logs?.startAutoRefresh) Panels.ai_decision_logs.startAutoRefresh();
        else if (Panels.ai_decision_logs?.stopAutoRefresh) Panels.ai_decision_logs.stopAutoRefresh();

        if (id === 'ai_lifecycle_topology' && window.AiLiveFlow) setTimeout(() => AiLiveFlow.init(), 100);
        if (id === 'jarvis_voice_overview') {
          setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
            if (window.JarvisAutoMic && typeof JarvisAutoMic.safeRestart === 'function') {
              JarvisAutoMic.safeRestart();
            }
          }, 150);
        }
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
      },

      refreshCurrent() {
        if (window.DataService && typeof DataService.refreshAll === 'function') {
          DataService.refreshAll();
        } else if (window.Panels && Panels[this.active] && typeof Panels[this.active].load === 'function') {
          Panels[this.active].load();
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

window.Nav = Nav;
window.UI = window.UI || {};
window.UI.Organisms = Object.assign(window.UI.Organisms || {}, {
  Nav: Nav,
  NavRouter: Nav,
  Sidebar: {
    toggle: typeof toggleSidebar !== 'undefined' ? toggleSidebar : () => {},
    toggleGroup: typeof toggleGroup !== 'undefined' ? toggleGroup : () => {},
    filter: typeof filterSidebar !== 'undefined' ? filterSidebar : () => {}
  },
  Topbar: {
    refreshAll: () => { if (typeof Nav !== 'undefined' && Nav.refreshCurrent) Nav.refreshCurrent(); }
  }
});
window.UI.Organisms.Nav = Nav;
