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
    { keys: ['sandbox', 'sanbox', 'promosi sandbox'], target: 'learning_gate_policy', name: 'Learning Gate & Sandbox' },
    { keys: ['ai core', 'otak ai', 'ai engine'], target: 'ai', name: 'AI Core Engine' },
    { keys: ['voice', 'jarvis voice', 'suara'], target: 'jarvis_voice_overview', name: 'JARVIS Voice Overview' },
    { keys: ['overview', 'dashboard', 'beranda', 'tampilan utama'], target: 'overview', name: 'Dashboard Overview' }
  ];

  const JarvisVoiceDashboardModule = {
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
    }
  };

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
