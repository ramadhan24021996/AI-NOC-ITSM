/**
 * Atomic Design — Module Layer: JARVIS Voice Dashboard Controller
 * Path: /static/js/modules/4_ai_lifecycle/jarvis-voice-dashboard.js
 * Coordinates:
 *   - UI.Organisms.JarvisHologram3D
 *   - UI.Organisms.JarvisWorkspaceUI
 *   - UI.Organisms.JarvisMediaPlayer
 *   - UI.Organisms.JarvisTaskManager
 *   - Services.JarvisAutoMic
 */
(function (global) {
  const NAV_MAP = [
    { keys: ['printer', 'cetak', 'printer status'], target: 'printer', name: 'Printer Status' },
    { keys: ['pc health', 'kesehatan pc', 'pc agent', 'komputer', 'pc'], target: 'pchealth', name: 'PC Health' },
    { keys: ['fleet config', 'konfigurasi fleet', 'config fleet'], target: 'fleet_config', name: 'Fleet Global Config' },
    { keys: ['fleet', 'armada', 'perangkat'], target: 'fleet', name: 'Fleet Management' },
    { keys: ['monitoring', 'pemantauan', 'live monitoring'], target: 'monitoring', name: 'Monitoring Live' },
    { keys: ['server health', 'kesehatan server', 'server', 'srv'], target: 'server', name: 'Server Health' },
    { keys: ['incident triage', 'incident', 'insiden', 'triage'], target: 'incident', name: 'Incident Triage' },
    { keys: ['rca', 'root cause', 'ground truth', 'penyebab utama'], target: 'rca', name: 'Ground Truth & RCA' },
    { keys: ['korelasi event', 'event correlation', 'korelasi'], target: 'event_correlation', name: 'Event Correlation' },
    { keys: ['unified dag', 'dag', 'grafik', 'graf'], target: 'unified_dag', name: 'Unified Graphs' },
    { keys: ['storage', 'penyimpanan', 'disk', 'kapasitas'], target: 'storage', name: 'Storage Stats' },
    { keys: ['timeline', 'eksekusi', 'waktu eksekusi'], target: 'exec_timeline', name: 'Execution Timeline' },
    { keys: ['security policy', 'kebijakan keamanan', 'policy'], target: 'security_policies', name: 'Security Policies' },
    { keys: ['governance', 'tata kelola', 'infrastruktur', 'infrastructure'], target: 'gov', name: 'Governance & Infrastructure' },
    { keys: ['knowledge center', 'rag', 'pusat pengetahuan', 'pengetahuan'], target: 'knowledge_center', name: 'RAG Knowledge Center' },
    { keys: ['knowledge graph', 'causal graph', 'grafik pengetahuan'], target: 'kgraph', name: 'Knowledge Graph' },
    { keys: ['sop', 'standar operasional'], target: 'sop', name: 'SOP Lifecycle' },
    { keys: ['playbook', 'playbooks', 'buku panduan'], target: 'playbooks', name: 'Playbook Studio' },
    { keys: ['live logs', 'live log', 'live lock', 'live lok', 'live loc', 'log', 'logs', 'catatan sistem'], target: 'logs', name: 'Live Logs' },
    { keys: ['models', 'model config', 'konfigurasi model', 'model'], target: 'models', name: 'Model Config' },
    { keys: ['training', 'pelatihan', 'latih model'], target: 'training', name: 'Continuous Training' },
    { keys: ['rbac', 'akses', 'hak akses', 'user', 'pengguna'], target: 'rbac', name: 'RBAC Policies' },
    { keys: ['live chat', 'menu chat', 'fitur chat', 'chat room', 'pesan'], target: 'chat', name: 'Live Chat' },
    { keys: ['evidence', 'bukti', 'bukti analisis'], target: 'evidence', name: 'Evidence Explorer' },
    { keys: ['agent health', 'kesehatan agen', 'agen'], target: 'agent_health', name: 'Agent Health Monitor' },
    { keys: ['decision log', 'keputusan ai', 'ai decision'], target: 'ai_decision_logs', name: 'AI Decision Logs' },
    { keys: ['topology', 'topologi', 'ai lifecycle', 'siklus ai'], target: 'ai_lifecycle_topology', name: 'AI Lifecycle Topology' },
    { keys: ['failed actions', 'failed action', 'gagal'], target: 'failed_actions', name: 'Failed Actions' },
    { keys: ['approval queue', 'approval', 'persetujuan', 'antrean'], target: 'approval_queue', name: 'Approval Queue' },
    { keys: ['smart stream', 'telemetri', 'stream'], target: 'smart_stream', name: 'Smart Stream Telemetry' },
    { keys: ['nats', 'nats subject', 'subjek nats'], target: 'nats_subjects', name: 'NATS Subjects' },
    { keys: ['runtime monitor', 'runtime', 'engine monitor'], target: 'runtime_monitor', name: 'Runtime Engine Monitor' },
    { keys: ['pending verification', 'verifikasi tertunda', 'verifikasi rule 6'], target: 'pending_verification', name: 'Pending Verification' },
    { keys: ['rollback history', 'riwayat rollback', 'rollback'], target: 'rollback_history', name: 'Rollback History' },
    { keys: ['schema validation', 'validasi skema', 'skema'], target: 'schema_validation_logs', name: 'Schema Validation Logs' },
    { keys: ['learning gate log', 'audit learning gate'], target: 'learning_gate_logs', name: 'Learning Gate Audit' },
    { keys: ['recovery mode', 'mode pemulihan'], target: 'recovery_mode_config', name: 'Recovery Mode Config' },
    { keys: ['user activity', 'aktivitas pengguna', 'browser log'], target: 'activity', name: 'User Activity & Browser Logs' },
    { keys: ['sandbox', 'sanbox', 'promosi sandbox', 'learning gate'], target: 'learning_gate_policy', name: 'Learning Gate & Sandbox' },
    { keys: ['ai core', 'otak ai', 'ai engine'], target: 'ai', name: 'AI Core Engine' },
    { keys: ['voice', 'jarvis voice', 'suara'], target: 'jarvis_voice_overview', name: 'JARVIS Voice Overview' },
    { keys: ['overview', 'dashboard', 'beranda', 'tampilan utama'], target: 'overview', name: 'Dashboard Overview' }
  ];

  const esc = (v) => (global._esc ? global._esc(v) : String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'));

  const JarvisVoiceDashboardModule = {
    _busBound: false,
    _refreshing: false,

    _isActive() {
      const p = document.getElementById('p-jarvis_voice_overview');
      return Boolean(p && p.classList.contains('active'));
    },

    resolveNavigation(lowerQ) {
      const isExplicitNav = /\b(buka menu|buka panel|tampilkan menu|pindah ke|navigasi ke|buka halaman|go to|goto)\b/i.test(lowerQ || '');
      if (!isExplicitNav) return { navTarget: null, navName: '', navExecuted: false };

      for (const item of NAV_MAP) {
        if (item.keys.some(k => lowerQ.includes(k))) {
          let navExecuted = false;
          if (typeof Nav !== 'undefined' && Nav.go) {
            try {
              Nav.go(item.target);
              navExecuted = true;
            } catch (e) {
              console.error('Navigation error:', e);
            }
          }
          return { navTarget: item.target, navName: item.name, navExecuted };
        }
      }
      return { navTarget: null, navName: '', navExecuted: false };
    },

    _bindLiveBus() {
      if (this._busBound) return;
      const bus = (global.Services && global.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
      if (!bus || typeof bus.on !== 'function') return;
      this._busBound = true;

      bus.on('devices:loaded', (devices) => {
        if (!this._isActive() || this._refreshing) return;
        this._renderActivityRows(devices, null);
      });

      bus.on('incidents:loaded', (incidents) => {
        if (!this._isActive() || this._refreshing) return;
        const svc = (global.Services && global.Services.Data) || global.DataService;
        this._renderSecurityBadges((svc && svc._health) || null, incidents);
      });

      bus.on('health:loaded', (health) => {
        if (!this._isActive() || this._refreshing) return;
        const svc = (global.Services && global.Services.Data) || global.DataService;
        this._renderSecurityBadges(health, (svc && svc._incidents) || []);
      });

      bus.on('telemetry:live', (payload) => {
        if (!this._isActive() || !payload) return;
        const data = (payload.data && typeof payload.data === 'object') ? payload.data : payload;
        const ram = parseFloat(data.memory_percent ?? data.mem_percent ?? data.ram ?? NaN);
        if (!isNaN(ram) && ram > 0) {
          const ramEl = document.getElementById('jrv-footer-ram');
          if (ramEl) ramEl.textContent = Math.round(ram) + '%';
        }
      });
    },

    _renderSecurityBadges(health, incidents) {
      const hScore = Number(health?.health_score ?? 100);
      const activeIncs = Array.isArray(incidents) ? incidents.filter(i => {
        const st = String(i.status || '').toUpperCase();
        return st !== 'RESOLVED' && st !== 'CLOSED' && st !== 'SOLVED VERIFIED';
      }) : [];
      const critCount = activeIncs.filter(i => {
        const sv = String(i.severity || i.flag || '').toUpperCase();
        return sv === 'CRITICAL' || sv === 'HIGH' || sv.includes('CRITICAL');
      }).length;

      const secScore = Math.max(10, Math.min(100, Math.round(hScore - (critCount * 8) - (Math.max(0, activeIncs.length - critCount) * 2))));
      const label = secScore >= 85 ? `AMAN (${secScore}%)` : secScore >= 60 ? `WASPADA (${secScore}%)` : `KRITIS (${secScore}%)`;
      const color = secScore >= 85 ? '#34d399' : secScore >= 60 ? '#f59e0b' : '#ef4444';

      const hdrBadge = document.getElementById('jrv-hdr-sec-badge');
      if (hdrBadge) {
        hdrBadge.style.color = color;
        hdrBadge.innerHTML = `<i class="fa-solid fa-lock"></i> ${esc(label)}`;
      }
      const cardBadge = document.getElementById('jrv-card-sec-badge');
      if (cardBadge) {
        cardBadge.style.color = color;
        cardBadge.textContent = label;
      }
    },

    _renderActivityRows(devices, auditLogs) {
      const container = document.getElementById('jrv-activity-rows');
      if (!container) return;

      const rows = [];
      const devList = Array.isArray(devices) ? devices : [];
      devList.slice(0, 3).forEach(d => {
        const name = d.name || d.pc_name || 'UNKNOWN-NODE';
        const isOnline = d.online || d.status === 'ONLINE';
        const pct = isOnline ? 100 : 15;
        rows.push({
          icon: 'fa-desktop',
          name: name,
          pct: pct,
          color: isOnline ? '#00F0FF' : '#ef4444',
          barClass: isOnline ? 'jrv-bar-fill-cyan' : 'jrv-bar-fill-green',
          statusText: isOnline ? 'ONLINE (100%)' : 'OFFLINE'
        });
      });

      if (rows.length < 3 && Array.isArray(auditLogs)) {
        const seenUsers = new Set(rows.map(r => r.name));
        for (const l of auditLogs) {
          if (rows.length >= 3) break;
          const u = l.username || l.actor;
          if (u && !seenUsers.has(u)) {
            seenUsers.add(u);
            rows.push({
              icon: 'fa-user-shield',
              name: u,
              pct: 95,
              color: '#34d399',
              barClass: 'jrv-bar-fill-green',
              statusText: 'ACTIVE'
            });
          }
        }
      }

      if (rows.length === 0) {
        const curUser = global.currentUserId || 'NOC Operator';
        const curRole = (global.currentUserRole || 'superadmin').toUpperCase();
        rows.push({
          icon: 'fa-user-shield',
          name: `${curUser} (${curRole})`,
          pct: 100,
          color: '#34d399',
          barClass: 'jrv-bar-fill-green',
          statusText: 'SESSION ACTIVE'
        });
      }

      container.innerHTML = rows.map(r => `
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span style="color: #e2e8f0; display: flex; align-items: center; gap: 6px; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${esc(r.name)}">
            <i class="fa-solid ${esc(r.icon)}" style="color:#00F0FF"></i> ${esc(r.name)}
          </span>
          <div class="jrv-bar-bg" style="width: 80px;"><div class="${r.barClass}" style="width: ${Math.max(0, Math.min(100, Number(r.pct) || 0))}%;"></div></div>
          <span style="color: ${r.color}; font-weight: 700; font-size: 9.5px;">${esc(r.statusText)}</span>
        </div>
      `).join('');
    },

    async load(silent = false) {
      this._bindLiveBus();
      const org = (global.UI && global.UI.Organisms) || {};
      if (org.JarvisTaskManager && !silent) {
        org.JarvisTaskManager.render();
      }
      if (org.JarvisHologram3D) {
        org.JarvisHologram3D.init();
        if (typeof org.JarvisHologram3D.resize === 'function') {
          setTimeout(() => org.JarvisHologram3D.resize(), 60);
        }
      }
      await this.refreshLive();
      global.ActiveIntervals = global.ActiveIntervals || {};
      if (!global.ActiveIntervals.jarvis_voice_live) {
        global.ActiveIntervals.jarvis_voice_live = setInterval(() => {
          if (document.hidden || !this._isActive()) return;
          this.refreshLive();
        }, 10000);
      }
    },

    async refreshLive() {
      if (this._refreshing) return;
      this._refreshing = true;
      try {
        const svc = (global.Services && global.Services.Data) || global.DataService;
        if (!svc) return;

        const t0 = performance.now();
        const [devices, incidents, health, aiStats, hostMetrics, voiceCfg, jarvisHealth, auditLogs] = await Promise.all([
          (Array.isArray(svc._devices) && svc._devices.length > 0) ? Promise.resolve(svc._devices) : svc.loadDevices().catch(() => []),
          (Array.isArray(svc._incidents) && svc._incidents.length > 0) ? Promise.resolve(svc._incidents) : svc.loadIncidents().catch(() => []),
          svc.loadHealth().catch(() => null),
          svc.loadAIStats().catch(() => null),
          svc.loadHostMetrics().catch(() => null),
          svc.fetch('/api/jarvis/voice/config').catch(() => null),
          svc.fetch('/api/jarvis/health').catch(() => null),
          svc.fetch('/api/rbac/audit_logs').catch(() => [])
        ]);
        const probeRttMs = Math.max(1, Math.round(performance.now() - t0));

        // 1. Security Badges & Activity Rows
        this._renderSecurityBadges(health, incidents);
        this._renderActivityRows(devices, auditLogs);

        // 2. Neural Processing Unit Metrics
        const activeModels = Number(aiStats?.active_count || 0);
        const ragVectors = Number(aiStats?.rag_count || 0);
        let confVal = parseFloat(aiStats?.avg_confidence || 0);
        if (confVal > 0 && confVal <= 1) confVal *= 100;
        const confStr = confVal > 0 ? `${Math.round(confVal)}%` : 'READY';

        const elModels = document.getElementById('jrv-neural-models');
        if (elModels) elModels.textContent = `Models: ${activeModels} Active`;
        const elVec = document.getElementById('jrv-neural-vectors');
        if (elVec) elVec.textContent = `RAG: ${ragVectors.toLocaleString('id-ID')} Vec`;
        const elConf = document.getElementById('jrv-neural-conf');
        if (elConf) elConf.textContent = `Conf: ${confStr}`;
        const elInitConf = document.getElementById('jrv-init-conf');
        if (elInitConf) elInitConf.textContent = `Conf: ${confStr}`;

        // 3. Cloud Sync Badge
        const syncBadge = document.getElementById('jrv-cloud-sync-badge');
        if (syncBadge) {
          const jrvOnline = jarvisHealth && (jarvisHealth.status === 'ok' || jarvisHealth.status === 'healthy' || jarvisHealth.ready !== false);
          syncBadge.textContent = jrvOnline ? 'LIVE SYNC' : 'LOCAL MODE';
          syncBadge.style.color = jrvOnline ? '#34d399' : '#38bdf8';
        }

        // 4. Footer Status Ticker (RAM Neural, Latency, Persona)
        const ramPct = Math.round(parseFloat(hostMetrics?.ram || 0));
        const ramEl = document.getElementById('jrv-footer-ram');
        if (ramEl) ramEl.textContent = `${ramPct}%`;

        const decMs = Math.round(parseFloat(aiStats?.avg_decision_time_ms || 0));
        const latMs = decMs > 0 ? decMs : probeRttMs;
        const latEl = document.getElementById('jrv-footer-latency');
        if (latEl) latEl.textContent = `${latMs} ms`;

        const personaEl = document.getElementById('jrv-footer-persona');
        if (personaEl && voiceCfg) {
          const personaName = voiceCfg.active_persona || voiceCfg.persona || 'J.A.R.V.I.S.';
          const voiceName = voiceCfg.voice_name || voiceCfg.engine || 'Neural ID';
          personaEl.textContent = `${String(personaName).toUpperCase()} (${voiceName})`;
        }
      } catch (e) {
        console.warn('[JARVIS Overview Live] Refresh warning:', e);
      } finally {
        this._refreshing = false;
      }
    },

    init() {
      const org = (global.UI && global.UI.Organisms) || {};
      if (org.JarvisTaskManager) {
        setTimeout(() => org.JarvisTaskManager.render(), 200);
      }
      if (org.JarvisHologram3D) {
        org.JarvisHologram3D.init();
      }
      if (global.Services && global.Services.JarvisAutoMic) {
        global.Services.JarvisAutoMic.init();
      } else if (global.JarvisAutoMic) {
        global.JarvisAutoMic.init();
      }
      this._bindLiveBus();
    }
  };

  global.Panels = global.Panels || {};
  global.Panels.jarvis_voice_overview = JarvisVoiceDashboardModule;

  global.JarvisVoiceDashboardModule = JarvisVoiceDashboardModule;
  global.Modules = global.Modules || {};
  global.Modules['4_ai_lifecycle'] = global.Modules['4_ai_lifecycle'] || {};
  global.Modules['4_ai_lifecycle']['jarvis-voice-dashboard'] = JarvisVoiceDashboardModule;
  global.Modules.JarvisVoiceDashboard = JarvisVoiceDashboardModule;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => JarvisVoiceDashboardModule.init());
  } else {
    JarvisVoiceDashboardModule.init();
  }
})(window);
