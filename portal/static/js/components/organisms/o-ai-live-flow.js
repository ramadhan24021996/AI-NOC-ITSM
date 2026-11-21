/* o-ai-live-flow.js
 * Organism: AiLiveFlow — AI decision pipeline live flow canvas.
 * Extracted from data.service.js (lines 2444-4409) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: DataService (service), Modal (molecule), Toast (atom), LogStreamer (organism)
 */
(function () {
  'use strict';

var AiLiveFlow = {
  _scale: 0.70, _tx: 300, _ty: 120,
  _dragging: false, _sx: 0, _sy: 0,
  _dragNode: null, _dragSwimlane: null, _dragOffsetX: 0, _dragOffsetY: 0, _dragMoved: false,
  _activeMotion: true, _particleInterval: null, _initializedTransform: false, _initialized: false,
  swimlanePos: {},

  _authHeaders() {
    const token = localStorage.getItem('noc_token') || sessionStorage.getItem('noc_token') || '';
    const h = { 'Accept': 'application/json' };
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
  },

  _isPanelActive() {
    if (document.hidden) return false;
    const p = document.getElementById('p-ai_lifecycle_topology');
    return !!(p && p.classList.contains('active'));
  },

  init() {
    const wrap = document.getElementById('ai-flow-wrap');
    if (!wrap) return;
    if (this._initialized) {
      this._pollLiveStatus();
      return;
    }
    this._initialized = true;

    wrap.addEventListener('mousedown', e => {
      if (e.target.closest('.ai-flow-node')) return;
      this._dragging = true;
      this._sx = e.clientX - this._tx;
      this._sy = e.clientY - this._ty;
      wrap.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', () => {
      this._dragging = false;
      if (wrap) wrap.style.cursor = 'grab';
      if (this._dragNode) this._dragNode = null;
      if (this._dragSwimlane !== null) this._dragSwimlane = null;
    });

    window.addEventListener('mousemove', e => {
      if (this._dragNode) {
        const pt = this.getCanvasPoint(e);
        this._dragNode.x = pt.x - this._dragOffsetX;
        this._dragNode.y = pt.y - this._dragOffsetY;
        this._dragMoved = true;

        const g = document.getElementById('gtn-' + this._dragNode.id);
        if (g) g.setAttribute('transform', `translate(${this._dragNode.x},${this._dragNode.y})`);
        this.updateEdges();
        return;
      }

      if (this._dragSwimlane !== null && this._dragSwimlane !== undefined) {
        const pt = this.getCanvasPoint(e);
        this.swimlanePos[this._dragSwimlane] = this.swimlanePos[this._dragSwimlane] || { x: -560, y: 0 };
        this.swimlanePos[this._dragSwimlane].x = pt.x - this._dragOffsetX;
        this.swimlanePos[this._dragSwimlane].y = pt.y - this._dragOffsetY;
        this._dragMoved = true;

        const g = document.getElementById('gtn-swimlane-' + this._dragSwimlane);
        if (g) g.setAttribute('transform', `translate(${this.swimlanePos[this._dragSwimlane].x},${this.swimlanePos[this._dragSwimlane].y})`);
        return;
      }

      if (!this._dragging) return;
      this._tx = e.clientX - this._sx;
      this._ty = e.clientY - this._sy;
      this._applyTransform();
    });

    wrap.addEventListener('wheel', e => {
      e.preventDefault();
      const rect = wrap.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const delta = e.deltaY > 0 ? -0.08 : 0.08;
      const newScale = Math.max(0.15, Math.min(3.0, this._scale + delta));
      const factor = newScale / this._scale;

      this._tx = mouseX - (mouseX - this._tx) * factor;
      this._ty = mouseY - (mouseY - this._ty) * factor;
      this._scale = newScale;
      this._applyTransform();
    }, { passive: false });

    this.render();
    this.startParticles();
    this.startLiveStatus();
  },

  getCanvasPoint(e) {
    const svg = document.getElementById('ai-flow-svg');
    const vp = document.getElementById('ai-flow-viewport');
    if (!svg || !vp) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = vp.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    return pt.matrixTransform(ctm.inverse());
  },

  onNodeMouseDown(e, nodeId) {
    e.stopPropagation();
    const n = this.nodes.find(x => x.id === nodeId);
    if (!n) return;
    const pt = this.getCanvasPoint(e);
    this._dragNode = n;
    this._dragOffsetX = pt.x - n.x;
    this._dragOffsetY = pt.y - n.y;
    this._dragMoved = false;
  },

  onSwimlaneMouseDown(e, layerId) {
    e.stopPropagation();
    this.swimlanePos = this.swimlanePos || {};
    if (!this.swimlanePos[layerId]) {
      const layerNodes = (this.nodes || []).filter(n => n.level === layerId);
      let y = 0;
      if (layerNodes.length > 0) y = layerNodes.reduce((acc, n) => acc + n.y, 0) / layerNodes.length;
      this.swimlanePos[layerId] = { x: -560, y: y };
    }
    const pt = this.getCanvasPoint(e);
    this._dragSwimlane = layerId;
    this._dragOffsetX = pt.x - this.swimlanePos[layerId].x;
    this._dragOffsetY = pt.y - this.swimlanePos[layerId].y;
    this._dragMoved = false;
  },

  _applyTransform() {
    const vp = document.getElementById('ai-flow-viewport');
    if (vp) vp.setAttribute('transform', `translate(${this._tx},${this._ty}) scale(${this._scale})`);
    const lbl = document.getElementById('lbl-zoom-pct');
    if (lbl) lbl.textContent = Math.round(this._scale * 100) + '%';
  },

  zoomIn() {
    const wrap = document.getElementById('ai-flow-wrap');
    let cx = 500, cy = 300;
    if (wrap) { cx = wrap.clientWidth / 2; cy = wrap.clientHeight / 2; }

    const newScale = Math.min(3.0, this._scale + 0.15);
    const factor = newScale / this._scale;
    this._tx = cx - (cx - this._tx) * factor;
    this._ty = cy - (cy - this._ty) * factor;
    this._scale = newScale;
    this._applyTransform();
  },

  zoomOut() {
    const wrap = document.getElementById('ai-flow-wrap');
    let cx = 500, cy = 300;
    if (wrap) { cx = wrap.clientWidth / 2; cy = wrap.clientHeight / 2; }

    const newScale = Math.max(0.15, this._scale - 0.15);
    const factor = newScale / this._scale;
    this._tx = cx - (cx - this._tx) * factor;
    this._ty = cy - (cy - this._ty) * factor;
    this._scale = newScale;
    this._applyTransform();
  },

  resetZoom() {
    let w = 1000;
    let h = 600;
    const wrap = document.getElementById('ai-flow-wrap');
    if (wrap && wrap.clientWidth > 100) { w = wrap.clientWidth; h = wrap.clientHeight || 600; }
    this._tx = w / 2 - 320;
    this._ty = h / 2 - 20;
    this._scale = 0.35;
    this._applyTransform();
  },

  autoArrange() {
    this.swimlanePos = {};
    localStorage.removeItem('osi_ai_flow_custom_positions');
    this.render();
    Toast.show('✨ Tata letak 70 node diset ulang secara simetris & rapi dari Kiri ke Kanan!', 'info');
  },

  saveLayout() {
    const posMap = {};
    this.nodes.forEach(n => {
      posMap[n.id] = { x: Math.round(n.x), y: Math.round(n.y) };
    });
    if (this.swimlanePos) posMap['_swimlanes'] = this.swimlanePos;
    localStorage.setItem('osi_ai_flow_custom_positions', JSON.stringify(posMap));
    Toast.show('💾 Tata letak kanvas 70 node berhasil disimpan secara permanen!', 'success');
  },

  resetLayout() {
    this.swimlanePos = {};
    localStorage.removeItem('osi_ai_flow_custom_positions');
    this.render();
    Toast.show('🔄 Tata letak kanvas diset ulang ke posisi standar simetris!', 'info');
  },

  updateEdges() {
    if (!this.edges || !this.nodes) return;
    this.edges.forEach(e => {
      const s = this.nodes.find(n => n.id === e.source);
      const t = this.nodes.find(n => n.id === e.target);
      if (!s || !t) return;
      const path = document.getElementById('edge-' + e.source + '-' + e.target);
      if (!path) return;
      const dy = Math.max(35, Math.abs(t.y - s.y) * 0.45);
      path.setAttribute('d', `M ${s.x} ${s.y + 20} C ${s.x} ${s.y + 20 + dy}, ${t.x} ${t.y - 20 - dy}, ${t.x} ${t.y - 20}`);
    });
  },

  toggleMotion() {
    this._activeMotion = !this._activeMotion;
    const lbl = document.getElementById('lbl-flow-motion');
    if (lbl) lbl.textContent = this._activeMotion ? 'Live Stream Motion (Active)' : 'Motion Paused';
    
    const elEdges = document.getElementById('ai-flow-edges');
    if (elEdges) {
      const paths = elEdges.querySelectorAll('path');
      paths.forEach(p => {
        if (this._activeMotion) p.classList.add('n8n-live-path');
        else p.classList.remove('n8n-live-path');
      });
    }

    if (this._activeMotion) {
      this.startParticles();
    } else if (this._particleInterval) {
      clearInterval(this._particleInterval);
      this._particleInterval = null;
    }
  },

  startParticles() {
    if (this._particleInterval) clearInterval(this._particleInterval);
    this._particleInterval = setInterval(() => {
      if (!this._activeMotion || !this._isPanelActive()) return;
      this.spawnParticle();
      this.spawnParticle();
    }, 450);
  },

  spawnParticle() {
    const pContainer = document.getElementById('ai-flow-particles');
    if (!pContainer || !this.edges || this.edges.length === 0) return;

    const edge = this.edges[Math.floor(Math.random() * this.edges.length)];
    const sNode = this.nodes.find(n => n.id === edge.source);
    const tNode = this.nodes.find(n => n.id === edge.target);
    if (!sNode || !tNode) return;

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('r', '4.5');
    circle.setAttribute('fill', sNode.color || '#06b6d4');
    circle.setAttribute('filter', 'url(#glow-cyan)');

    const animX = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
    animX.setAttribute('attributeName', 'cx');
    animX.setAttribute('from', sNode.x);
    animX.setAttribute('to', tNode.x);
    animX.setAttribute('dur', '1.2s');
    animX.setAttribute('repeatCount', '1');

    const animY = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
    animY.setAttribute('attributeName', 'cy');
    animY.setAttribute('from', sNode.y);
    animY.setAttribute('to', tNode.y);
    animY.setAttribute('dur', '1.2s');
    animY.setAttribute('repeatCount', '1');

    circle.appendChild(animX);
    circle.appendChild(animY);
    pContainer.appendChild(circle);

    setTimeout(() => circle.remove(), 1200);
  },

  async executeWorkflowTest() {
    Toast.show('⚡ Dispatching Live n8n Workflow Execution across ' + this.nodes.length + ' Nodes...', 'info');

    let delay = 0;
    this.nodes.forEach((n) => {
      setTimeout(() => {
        const g = document.getElementById('gtn-' + n.id);
        if (g) {
          g.style.filter = 'drop-shadow(0 0 14px #ff6d5a)';
          setTimeout(() => g.style.filter = 'none', 600);
        }
      }, delay);
      delay += 25;
    });

    try {
      const svc = (window.Services && window.Services.Data) || DataService;
      const data = await svc.fetch('/api/n8n/trigger', {
        method: 'POST',
        body: JSON.stringify({
          workflow_id: "wf_n8n_ai_ops_master",
          event: "SUPERADMIN_MANUAL_TEST_EXECUTION",
          timestamp: new Date().toISOString()
        })
      });
      if (data && (data.status === "SUCCESS" || data.status === "success")) {
        Toast.show('✓ n8n Live Engine Connected (' + (data.correlation_id || 'OK') + ') — Execution Dispatched!', 'success');
      } else {
        Toast.show('⚠️ n8n Trigger: ' + ((data && (data.message || data.error)) || 'Respons tidak dikenal dari backend'), 'warn');
      }
    } catch (e) {
      Toast.show('❌ Gagal memicu n8n workflow: ' + (e.message || 'Network error'), 'err');
    }
  },

  pulseNode(nodeId) {
    const g = document.getElementById('gtn-' + nodeId);
    if (g) {
      g.style.filter = 'drop-shadow(0 0 18px #ff6d5a)';
      setTimeout(() => g.style.filter = 'none', 1000);
    }
    Toast.show('⚡ Test Run Triggered for node: ' + nodeId, 'success');
  },

  simulateNodeCrash(nodeId = 'L4_Executor') {
    const n = this.nodes.find(x => x.id === nodeId) || this.nodes[0];
    n.isCrashed = true;
    n.status = 'CRASHED_504_TIMEOUT';

    const g = document.getElementById('gtn-' + n.id);
    if (g) {
      g.style.filter = 'drop-shadow(0 0 24px #ef4444)';
      const textEl = g.querySelector('text');
      if (textEl) textEl.setAttribute('fill', '#ef4444');
    }

    Toast.show('🚨 CRITICAL ALERT: Node [' + n.title + '] TIMEOUT / CRASH (504 Gateway Timeout > 5000ms SLA). Circuit Breaker TRIPPED -> Traffic Fallback Active!', 'error');
    this.inspectNode(n.id);
  },

  // ── LIVE STATUS SYSTEM ────────────────────────────────────────────────────
  // Real-time node status polling + crash/warning notification
  // ─────────────────────────────────────────────────────────────────────────

  _liveStatusInterval: null,
  _liveStatusPrev: {},           // previous status per node-id
  _liveAlertCount: 0,            // badge counter (ERRORS + WARNINGS)
  _liveStatusMap: {},            // nodeId → {status, latency, last_ok}

  // Map: serviceId / component key returned by backend → canvas node IDs it covers
  _serviceToNodes: {
    // Container / Runtime Engine names (from /api/system/runtime_monitor & Docker)
    'osi-python-ai-core':    ['L4_PAI','L4_Router','L4_RAG','L4_DAG','L4_DBNEngine','L4_GOV','L4_MemoryGraph','L4_Backpressure','L4_Observer'],
    'osi-ai-daemons':        ['L4_ObsidianSyncDaemon','L4_Chaos','L4_ObsidianVault','L4_PostMortemExporter'],
    'osi-ai-consensus':      ['L4_Consensus','L4_MultiAgentOrch'],
    'osi-ai-critic':         ['L4_Critic','L4_CriticAuditor'],
    'osi-ai-policy':         ['L4_GOV','L4_PDP_Governance','L4_SafetyLayer'],
    'osi-ai-rag':            ['L4_RAG','L4_KnowledgeAutoBuilder','L4_ArchiveFTS'],
    'osi-jarvis-voice-server':['L4_JarvisVoice'],
    'osi-ingestion-server':  ['L3_Ingestion','L2_REST','L2_WS'],
    'osi-scheduler-service': ['L3_Scheduler'],
    'osi-secure-relay':      ['L3_Relay'],
    'osi-dashboard-server':  ['L1_UI','L1_Dash','L1_HITL','L1_Telem','L3_GoCore'],
    'osi-nginx':             ['L2_Nginx'],
    'osi-postgres':          ['L5_SQL_Inc','L5_SQL_RAG','L5_SQL_Cog','L5_SQL_SO'],
    'osi-nats':              ['L5_NATS'],
    'nats-node1':            ['L5_NATS'],
    'nats-node2':            ['L5_NATS'],
    'osi-redis':             ['L5_Redis','L4_DistributedLock'],
    'osi-telegram-bot':      ['L0_Telegram','L9_NocRelay'],
    'osi-portainer':         ['L6_Docker'],
    'osi-pgadmin':           ['L6_CasaOS'],
    'osi-zookeeper':         ['L8_Kafka'],
    'osi-kafka':             ['L8_Kafka'],
    'osi-kafka-ui':          ['L8_Kafka'],
    'netdata':               ['L6_Netdata'],
    'netdata_master':        ['L6_Netdata'],
    'n8n':                   ['L6_N8N','L6_N8N_v4_1','L6_N8N_v4_2'],
    'n8n_workflow_engine':   ['L6_N8N','L6_N8N_v4_1','L6_N8N_v4_2'],
    'ai-supervisor':         ['L4_PAI','L4_ClosedLoop'],
    'intent-router':         ['L4_Router','L4_IntentClassifier'],
    'ai-planner':            ['L4_Planner'],
    'ai-verifier':           ['L4_Verifier','L4_GroundingVerifier'],
    'ai-executor':           ['L4_Executor','L4_RollbackManager'],
    'ai-reflector':          ['L4_Reflector','L4_FeedbackCollector'],
    // /api/system/health -> components keys
    'PostgreSQL':            ['L5_SQL_Inc','L5_SQL_RAG','L5_SQL_Cog','L5_SQL_SO'],
    'Redis':                 ['L5_Redis','L4_DistributedLock'],
    'NATS':                  ['L5_NATS'],
    'Dashboard':             ['L1_UI','L1_Dash','L1_HITL','L1_Telem','L3_GoCore','L2_REST','L2_WS','L2_Nginx'],
    'Ingestion':             ['L3_Ingestion'],
    'RAG Engine':            ['L4_RAG','L4_KnowledgeAutoBuilder','L4_ArchiveFTS'],
    'AI API':                ['L4_Router','L4_ModelRegistry'],
  },

  startLiveStatus() {
    if (this._liveStatusInterval) return; // Already running
    this._injectStatusIndicatorStyles();
    this._injectStatusBanner();
    this._pollLiveStatus();
    this._liveStatusInterval = setInterval(() => {
      if (!this._isPanelActive()) return;
      this._pollLiveStatus();
    }, 15000);
    console.debug('[AiLiveFlow] Live Status Polling started (15s interval)');
  },

  stopLiveStatus() {
    if (this._liveStatusInterval) {
      clearInterval(this._liveStatusInterval);
      this._liveStatusInterval = null;
    }
  },

  async _pollLiveStatus() {
    try {
      const headers = this._authHeaders();
      const [sysResp, rtResp] = await Promise.all([
        fetch('/api/system/health', { headers, signal: AbortSignal.timeout(8000) }).catch(() => null),
        fetch('/api/system/runtime_monitor', { headers, signal: AbortSignal.timeout(8000) }).catch(() => null)
      ]);

      let processed = false;
      if (sysResp && sysResp.ok) {
        const sysData = await sysResp.json();
        this._processHealthData(sysData);
        processed = true;
      }
      if (rtResp && rtResp.ok) {
        const rtData = await rtResp.json();
        if (rtData) {
          this._processHealthData(rtData);
          processed = true;
        }
      }
      if (!processed) {
        this._applyStatusFromPing();
      }
    } catch (e) {
      this._applyStatusFromPing();
    }
  },

  _processHealthData(data) {
    // Accept /api/system/runtime_monitor ({engines: [...]}) or /api/system/health ({components: {...}}) or {services/containers}
    const services = data.engines || data.components || data.services || data.containers || data;
    const newAlerts = [];

    if (Array.isArray(services)) {
      services.forEach(svc => {
        const status = String(svc.status || svc.state || 'unknown').toLowerCase();
        const svcId = svc.engine || svc.name || svc.id || svc.service_id;
        const lat = parseFloat(String(svc.latency || svc.latency_ms || '').replace(/[^0-9.]/g, '')) || null;
        if (svcId) this._applyServiceStatus(svcId, status, lat, newAlerts);
      });
    } else if (services && typeof services === 'object') {
      Object.entries(services).forEach(([svcId, info]) => {
        if (!info || typeof info !== 'object') return;
        const status = String(info.status || info.state || (info.healthy ? 'running' : 'error')).toLowerCase();
        const latency = info.latency_ms || info.response_time_ms || (parseFloat(String(info.detail || '').replace(/[^0-9.]/g, '')) || null);
        this._applyServiceStatus(svcId, status, latency, newAlerts);
      });
    }

    this._fireAlertNotifications(newAlerts);
    this._updateStatusBanner();
  },

  _applyServiceStatus(svcId, status, latencyMs, newAlerts) {
    const nodeIds = this._serviceToNodes[svcId] || [];
    const isError = ['error','crashed','down','stopped','exited','unhealthy','timeout','oom','unavailable','disconnected'].some(s => status.includes(s));
    const isWarn  = ['degraded','slow','warning','restart','restarting','starting','no_heartbeat'].some(s => status.includes(s));
    const isOk    = !isError && !isWarn;

    const visualStatus = isError ? 'ERROR' : (isWarn ? 'WARNING' : 'OK');

    nodeIds.forEach(nodeId => {
      const prev = this._liveStatusMap[nodeId] || {};
      this._liveStatusMap[nodeId] = { status: visualStatus, latency: latencyMs, svcId };

      // Detect status transitions → only notify on NEW problems
      if (!prev.status || prev.status === 'OK') {
        if (isError) newAlerts.push({ nodeId, svcId, level: 'ERROR', status });
        else if (isWarn) newAlerts.push({ nodeId, svcId, level: 'WARNING', status });
      }

      this._applyNodeVisualStatus(nodeId, visualStatus, latencyMs);
    });
  },

  _applyNodeVisualStatus(nodeId, status, latencyMs) {
    const g = document.getElementById('gtn-' + nodeId);
    if (!g) return;

    // Remove old status classes
    g.classList.remove('node-status-ok','node-status-warn','node-status-error');

    const rect = g.querySelector('rect');
    const statusDot = g.querySelector('.node-status-dot');

    if (status === 'ERROR') {
      g.classList.add('node-status-error');
      if (rect) rect.style.stroke = '#ef4444';
      g.style.filter = 'drop-shadow(0 0 8px rgba(239,68,68,0.7))';
      if (statusDot) { statusDot.style.background = '#ef4444'; statusDot.setAttribute('data-status','⚠ DOWN'); }
    } else if (status === 'WARNING') {
      g.classList.add('node-status-warn');
      if (rect) rect.style.stroke = '#f59e0b';
      g.style.filter = 'drop-shadow(0 0 6px rgba(245,158,11,0.6))';
      if (statusDot) { statusDot.style.background = '#f59e0b'; statusDot.setAttribute('data-status','⚡ WARN'); }
    } else {
      g.classList.add('node-status-ok');
      if (rect) rect.style.stroke = '';
      g.style.filter = '';
      const lat = latencyMs ? latencyMs + 'ms' : 'OK';
      if (statusDot) { statusDot.style.background = '#22c55e'; statusDot.setAttribute('data-status','✅ ' + lat); }
    }
  },

  _applyStatusFromPing() {
    // Fallback: ping known endpoints to determine basic health
    const checks = [
      { url: '/api/health', nodeIds: ['L3_GoCore','L1_UI','L2_REST'] },
      { url: '/api/fleet/admin/sites', nodeIds: ['L3_GoCore'] },
    ];
    checks.forEach(({ url, nodeIds }) => {
      fetch(url, { signal: AbortSignal.timeout(3000) })
        .then(r => {
          const ok = r.ok;
          nodeIds.forEach(id => {
            this._applyNodeVisualStatus(id, ok ? 'OK' : 'ERROR', null);
          });
        })
        .catch(() => {
          nodeIds.forEach(id => this._applyNodeVisualStatus(id, 'ERROR', null));
        });
    });
  },

  _fireAlertNotifications(alerts) {
    if (!alerts || alerts.length === 0) return;

    alerts.forEach(alert => {
      if (alert.level === 'ERROR') {
        // Visual crash pulse animation on node only (no toast/sound/badge)
        const g = document.getElementById('gtn-' + alert.nodeId);
        if (g) {
          g.style.animation = 'node-crash-pulse 0.5s ease-in-out 4';
        }
      }
    });
  },

  _injectStatusBanner() {
    // Live status banner di bawah canvas HUD
    let banner = document.getElementById('ai-flow-status-banner');
    if (banner) return;
    banner = document.createElement('div');
    banner.id = 'ai-flow-status-banner';
    banner.style.cssText = `
      position:absolute; bottom:52px; right:16px; z-index:10;
      background:rgba(15,23,42,0.92); padding:6px 14px;
      border:1px solid rgba(34,197,94,0.4); border-radius:6px;
      font-family:'JetBrains Mono',monospace; font-size:11px;
      color:#94a3b8; backdrop-filter:blur(8px);
      display:flex; align-items:center; gap:8px;
    `;
    banner.innerHTML = `
      <span id="ai-flow-live-dot" style="width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 1.5s infinite;display:inline-block"></span>
      <span id="ai-flow-live-label">LIVE · Polling status...</span>
      <span id="ai-flow-live-errors" style="color:#ef4444;font-weight:700;display:none"></span>
      <span id="ai-flow-live-warns" style="color:#f59e0b;font-weight:700;display:none"></span>
    `;
    const wrap = document.getElementById('ai-flow-wrap');
    if (wrap) wrap.style.position = 'relative', wrap.appendChild(banner);
  },

  _updateStatusBanner() {
    const errors = Object.values(this._liveStatusMap).filter(s => s.status === 'ERROR').length;
    const warns  = Object.values(this._liveStatusMap).filter(s => s.status === 'WARNING').length;
    const total  = Object.keys(this._liveStatusMap).length;
    const ok     = total - errors - warns;
    const now    = new Date().toLocaleTimeString('id-ID');

    const dot   = document.getElementById('ai-flow-live-dot');
    const label = document.getElementById('ai-flow-live-label');
    const errEl = document.getElementById('ai-flow-live-errors');
    const wrnEl = document.getElementById('ai-flow-live-warns');

    if (errors > 0 && dot) dot.style.background = '#ef4444';
    else if (warns > 0 && dot) dot.style.background = '#f59e0b';
    else if (dot) dot.style.background = '#22c55e';

    if (label) label.textContent = `LIVE · ${ok}✅ ${warns > 0 ? warns+'⚠️ ' : ''}${errors > 0 ? errors+'❌' : ''} · ${now}`;

    if (errEl) { errEl.style.display = errors > 0 ? '' : 'none'; errEl.textContent = errors > 0 ? `${errors} DOWN` : ''; }
    if (wrnEl) { wrnEl.style.display = warns  > 0 ? '' : 'none'; wrnEl.textContent = warns  > 0 ? `${warns} WARN`  : ''; }
  },

  _injectStatusIndicatorStyles() {
    if (document.getElementById('ai-flow-live-styles')) return;
    const style = document.createElement('style');
    style.id = 'ai-flow-live-styles';
    style.textContent = `
      @keyframes node-crash-pulse {
        0%, 100% { filter: drop-shadow(0 0 4px #ef4444); }
        50%       { filter: drop-shadow(0 0 20px #ef4444) drop-shadow(0 0 40px #ef4444); }
      }
      .node-status-error { animation: node-crash-pulse 0.8s ease-in-out infinite !important; }
      .node-status-warn  { filter: drop-shadow(0 0 6px rgba(245,158,11,0.7)) !important; }
      .node-status-ok    { transition: filter 0.5s ease; }

      .node-status-dot {
        position: absolute; bottom: -4px; right: -4px;
        width: 9px; height: 9px; border-radius: 50%;
        background: #22c55e; border: 1.5px solid #0f172a;
        cursor: help;
      }
      .node-status-dot::after {
        content: attr(data-status);
        display: none; position: absolute; bottom: 14px; right: 0;
        background: rgba(15,23,42,0.95); color: #e2e8f0;
        font-size: 10px; padding: 3px 7px; border-radius: 4px;
        white-space: nowrap; border: 1px solid rgba(255,255,255,0.15);
        font-family: 'JetBrains Mono', monospace;
        pointer-events: none; z-index: 99;
      }
      .node-status-dot:hover::after { display: block; }
    `;
    document.head.appendChild(style);
  },

  getNodeLiveStatus(nodeId) {
    return this._liveStatusMap[nodeId] || { status: 'UNKNOWN' };
  },

  clearAllAlerts() {
    this._liveAlertCount = 0;
    // Reset any crashed nodes back to normal
    Object.keys(this._liveStatusMap).forEach(id => {
      if (this._liveStatusMap[id].status === 'ERROR') {
        this._applyNodeVisualStatus(id, 'OK', null);
      }
    });
  },

  inspectNode(nodeId) {
    if (this._nodeMoved) {
      this._nodeMoved = false;
      return;
    }
    const n = this.nodes.find(x => x.id === nodeId);
    if (!n) return;
    
    let demoInput = {
      event_id: "evt_n8n_" + Math.random().toString(36).substring(2, 9),
      node_id: n.id,
      source_layer: "Layer " + n.level + " (" + n.layerName + ")",
      timestamp: new Date().toISOString(),
      payload: {
        telemetry_topic: "telemetry.site.kantor-pusat.critical",
        metrics: { cpu_usage: 18.5, memory_mb: 4096, status: "HEALTHY" }
      }
    };

    let demoOutput = n.isCrashed ? {
      execution_status: "504_GATEWAY_TIMEOUT",
      error_code: "NODE_SLA_TIMEOUT_EXCEEDED",
      sla_threshold_ms: 5000,
      actual_latency_ms: "5002ms (TIMEOUT_BREACH)",
      circuit_breaker_status: "OPEN (TRIPPED)",
      fallback_route: "Rerouted payload to L5_OfflineCache & L4_RollbackManager",
      diagnostic_trace: "Node " + n.title + " failed to respond within 5000ms SLA limit. Circuit Breaker automatically opened to prevent cascade failures."
    } : {
      execution_status: "200_OK_SUCCESS",
      execution_time_ms: n.latency || "3.8ms",
      reasoning_summary: n.desc,
      action_taken: "FORWARD_TO_NEXT_HOP",
      security_policy: "HITL_SAFEGUARD_ENFORCED"
    };

    if (n.id === 'L4_Planner') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        symptom: "High CPU 98% & DB Connection Lock",
        diagnostics: {
          causal_dag_root_cause: "PostgreSQL Unindexed Query Lock",
          counterfactual_confidence: 0.94,
          blast_radius_level: "HIGH",
          trust_score: 0.98
        }
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        goal: "Pulihkan layanan dari masalah: PostgreSQL Unindexed Query Lock",
        candidate_plans: [
          { id: "plan_a", action: "restart_affected_service", risk: 0.10, success_probability: 0.75, duration_sec: 20 },
          { id: "plan_b", action: "failover_cluster_node", risk: 0.18, success_probability: 0.92, duration_sec: 40 },
          { id: "plan_c", action: "scale_out_deployment", risk: 0.05, success_probability: 0.96, duration_sec: 120 }
        ],
        recommended_plan_id: "plan_c",
        recommendation_reasoning: "Selected 'plan_c' (Auto Scale-out Deployment) due to optimal success probability (96%) and lowest risk factor (5%)."
      };
    }

    if (n.id === 'L4_Executor') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        authorized_plan: {
          plan_id: "plan_c",
          action: "scale_out_deployment",
          target_cluster: "NOC-SRV-PVE01",
          replicas_delta: "+2"
        },
        governance_clearance: {
          policy_check: "PASSED_NO_VIOLATIONS",
          consensus_voting: "UNANIMOUS_APPROVED_3_OF_3",
          hitl_status: "APPROVED_OR_EXEMPT"
        }
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        execution_id: "exec_plan_c_1784809200",
        status: "EXECUTION_SUCCESSFUL",
        auto_rollback_triggered: false,
        health_verification: "STABLE_200_OK",
        steps_completed: [
          { step: 1, name: "Pre-flight Health & Dependency Check", status: "COMPLETED", duration_ms: 12 },
          { step: 2, name: "Dispatch Action Core (scale_out_deployment)", status: "COMPLETED", duration_ms: 145 },
          { step: 3, name: "Verify Post-Execution Metric Stabilization", status: "COMPLETED", duration_ms: 38 },
          { step: 4, name: "Safety Guardrail Check & Rollback Validation", status: "VERIFIED_SAFE", duration_ms: 8 }
        ],
        handoff_target: "L4_Closure"
      };
    }

    if (n.id === 'L4_Verifier') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        verification_targets: {
          pre_execution_plan: "plan_c (scale_out_deployment)",
          post_execution_id: "exec_plan_c_1784809200",
          metrics_stream: "telemetry.site.kantor-pusat.critical"
        }
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        double_gate_results: {
          pre_execution_gate: {
            status: "PASSED",
            policy_compliance: "NO_VIOLATION",
            target_host_heartbeat: "ONLINE_ACTIVE",
            risk_threshold: "ACCEPTABLE_LOW",
            clearance: "GRANTED_PROCEED_TO_EXECUTOR"
          },
          post_execution_gate: {
            status: "PASSED",
            service_health_probe: "HEALTHY_200_OK",
            cpu_delta: "98.5% -> 18.2% (NORMALIZED)",
            error_rate_delta: "14 errors/s -> 0 errors/s",
            side_effect_anomalies: 0,
            clearance: "REMEDIATION_PROVEN_SUCCESSFUL"
          }
        },
        next_action: "HANDOFF_TO_CLOSURE_ENGINE"
      };
    }

    if (n.id === 'L4_RollbackManager') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        trigger_source: "L4_Verifier (Post-Execution Anomaly Detection)",
        checkpoint_id: "chk_pre_remediation_v1"
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        rollback_id: "rb_exec_plan_c_1784809200",
        status: "ROLLBACK_SUCCESSFUL",
        steps: [
          { step: 1, action: "Fetch Execution Checkpoint", status: "COMPLETED", duration_ms: 15 },
          { step: 2, action: "Isolate Disturbed Node", status: "COMPLETED", duration_ms: 42 },
          { step: 3, action: "Restore Previous Baseline State", status: "COMPLETED", duration_ms: 180 },
          { step: 4, action: "Re-verify Telemetry Baseline Post-Rollback", status: "VERIFIED_STABLE", duration_ms: 25 }
        ],
        state_machine_notified: true
      };
    }

    if (n.id === 'L4_Reflector') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        remediation_action: "scale_out_deployment",
        mttr_seconds: 180,
        evaluation_pipeline: "OutcomeAnalyzer -> PatternLearner -> KnowledgeSynthesizer"
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        reflection_id: "refl_INC-2026-9981_1784809200",
        reflection_mode: "EVIDENCE_DRIVEN_RECOMMENDATION_ONLY",
        three_stage_breakdown: {
          outcome_analyzer: {
            target: "CPU < 60% & Zero Timeout",
            reality_cpu: "18.2%",
            goal_achieved: true,
            conclusion: "Goal fully achieved"
          },
          pattern_learner: {
            incidents_analyzed: 42,
            failed_action_pattern: "Restart Service (29/32 failed)",
            successful_action_pattern: "Scale Out / Rolling Deployment (12/12 succeeded)"
          },
          knowledge_synthesizer: {
            confidence_score: "96.0% (HIGH_CONFIDENCE_RECOMMENDED)",
            synthesized_rule: "IF root_cause == 'PostgreSQL Unindexed Query Lock' THEN prioritize 'scale_out_deployment' over 'restart_service'"
          }
        },
        reflection_report: {
          confidence: "96%",
          finding: "Restart Service frequently fails for 'PostgreSQL Unindexed Slow Query Lock' under high query load.",
          recommendation: "Prioritize Rolling Deployment / Scale Out Deployment for similar anomaly patterns.",
          evidence_base: "42 historical incidents analyzed"
        },
        saved_to_cognitive_memory: true,
        direct_mutation_prevented: true,
        feedback_target: "L4_Planner"
      };
    }

    if (n.id === 'L4_SymptomCluster') {
      demoInput.payload = { symptom: "Printer Spooler Deadlock & Memory Leak", telemetry_vector: [0.90, 0.20, 0.10, 0.05] };
      demoOutput = { execution_status: "200_OK_SUCCESS", matched_cluster: "SPOOLER_DEADLOCK_CLUSTER", novelty_score: 0.08, is_novel_anomaly: false, strategy: "STANDARD_TAXONOMY_MATCH" };
    }

    if (n.id === 'L4_RemediationMatrix') {
      demoInput.payload = { incident_category: "PRINT_SPOOLER", symptom: "Printer Spooler Deadlock" };
      demoOutput = { execution_status: "200_OK_SUCCESS", taxonomy: { primary: "RESTART_WINDOWS_SPOOLER_SERVICE", secondary: "PURGE_SPOOL_PRINTER_QUEUE_FILES", isolation: "DISABLE_PRINTER_RPC_PORT" } };
    }

    if (n.id === 'L4_ContinuousReinforcement') {
      demoInput.payload = { action_name: "RESTART_WINDOWS_SPOOLER_SERVICE", sliding_window: 10 };
      demoOutput = { execution_status: "200_OK_SUCCESS", fail_rate: 0.10, performance_decay: false, penalty_multiplier: 1.0, status: "HEALTHY_STABLE" };
    }

    if (n.id === 'L4_RegulatoryGuard') {
      demoInput.payload = { action_name: "RESTART_WINDOWS_SPOOLER_SERVICE", target_device: "POS-Kasir-01" };
      demoOutput = { execution_status: "200_OK_SUCCESS", is_compliant: true, clearance_status: "COMPLIANT_APPROVED", standards: ["ISO_27001", "PCI_DSS_POS_v4", "UU_PDP_DATA_PROTECTION"] };
    }

    if (n.id === 'L4_PDP_Governance') {
      demoInput.payload = { workflow_steps: [{ action: "ACT_RESTART_SPOOLER", target: "POS-Kasir-01" }], profile: "RETAIL" };
      demoOutput = { decision: "AUTOMATIC_CLEARANCE_APPROVED", is_compliant: true, max_risk_score: 0.15, policy_version: "v2.1.0", profile_applied: "Retail & POS POS Terminal Safeguard" };
    }

    if (n.id === 'L4_GoldenRules') {
      demoInput.payload = { requested_action: "ACT_RESTART_SPOOLER", rule_check_priority: "RULE_1_PREAPPROVED_CATALOG_FIRST" };
      demoOutput = { production_clearance: "APPROVED_FOR_PRODUCTION_EXECUTION", all_5_rules_passed: true, rule_1: "PREAPPROVED_CATALOG_OK", rule_2: "DOUBLE_GATE_OK", rule_3: "ROLLBACK_HEALTH_OK" };
    }

    if (n.id === 'L4_TrustCalibrator') {
      demoInput.payload = { total_predictions: 1000, confidence_samples: "binned_0.10_to_1.0" };
      demoOutput = { ece_score: 0.042, threshold: 0.15, status: "WELL_CALIBRATED", recommendation: "Model confidence remains well-calibrated" };
    }

    if (n.id === 'L4_AdversarialGuard') {
      demoInput.payload = { prompt_input: "Restart spooler service on PC-Kasir-01" };
      demoOutput = { status: "CLEARED_SAFE", is_adversarial_attack: false, matched_rules: [] };
    }

    if (n.id === 'L6_N8N') {
      demoInput.payload = {
        workflow_id: "wf_n8n_ai_ops_master",
        triggered_by: "L4_Executor (Step 3 Action Core Dispatch)",
        active_webhook: "https://100.100.10.98:9443/api/n8n/webhook/incident-trigger"
      };
      demoOutput = {
        execution_status: "200_OK_SUCCESS",
        n8n_engine_version: "v3.0",
        nodes_orchestrated: 64,
        active_workflows: [
          { name: "Auto Remediation Dispatch Workflow", status: "ACTIVE_EXECUTING", nodes_hit: 64 },
          { name: "HITL Approval Notification Webhook (Telegram)", status: "LISTENING" },
          { name: "Cognitive Reflection & Memory Update Stream", status: "READY" }
        ],
        latency_ms: 3.8
      };
    }

    if (n.id === 'L4_SecretManager') {
      demoInput.payload = {
        requester: "L4_Executor",
        action_requested: "scale_out_deployment",
        ttl_seconds: 60
      };
      demoOutput = {
        vault_status: "ENCRYPTED_VAULT_OK",
        encryption_cipher: "AES-256-GCM / HMAC-SHA256",
        ephemeral_token_issued: "eph_tok_7a9f81bc33829a10",
        token_ttl: "60 seconds",
        log_redaction_status: "ACTIVE_SANITIZING",
        agent_tokens_rotated: 2
      };
    }

    if (n.id === 'L4_Observability') {
      demoInput.payload = {
        trace_id: "tr_4a899c72e90f",
        telemetry_sources: ["L4_Executor", "L4_Verifier", "L1_Telem"]
      };
      demoOutput = {
        status: "HEALTHY_EXPORTING",
        exporters: ["Prometheus Metrics Exporter v1.4", "OpenTelemetry Collector Span Tracing"],
        metrics_summary: {
          system_cpu_usage_pct: 18.2,
          http_error_rate_per_sec: 0,
          average_mttr_seconds: 165.0,
          sanitized_audit_logs_total: 1280
        },
        plain_text_credential_leak_risk: "ZERO (100% Redacted by Secret Manager)"
      };
    }

    if (n.id === 'L5_OfflineCache') {
      demoInput.payload = {
        buffer_mode: "STORE_AND_FORWARD",
        wan_status: "ONLINE",
        local_sqlite_db: "/tmp/offline_cache.db"
      };
      demoOutput = {
        store_and_forward_status: "ACTIVE_READY",
        queued_packets_in_buffer: 0,
        zero_data_loss_guarantee: "ENFORCED",
        resync_protocol: "FIFO_AUTO_FLUSH_ON_RECONNECT",
        last_resync_flushed_packets: 14,
        upstream_broker: "L5_NATS (JetStream Broker)"
      };
    }

    if (n.id === 'L4_Closure') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        root_cause: "PostgreSQL Unindexed Query Lock",
        remediation_action: "scale_out_deployment",
        mttr_seconds: 180.0
      };
      demoOutput = {
        closure_status: "CLOSED_NORMALIZED",
        itsm_sync_status: "SUCCESSFUL_DISPATCH",
        n8n_webhook_url: "https://100.100.10.98:9443/api/n8n/webhook/closure-itsm-sync",
        destinations_notified: [
          { target: "L0_Telegram Bot Gateway", status: "DELIVERED_200_OK", channel: "NOC Alert Channel" },
          { target: "L8_Kafka Enterprise Bus", status: "ACKNOWLEDGED", topic: "enterprise.itsm.incident.closed" },
          { target: "Enterprise ITSM Ticket Manager", status: "TICKET_CLOSED_RESOLVED" }
        ],
        feedback_sent_to_reflector: true
      };
    }

    if (n.id === 'L4_FeatureStore') {
      demoInput.payload = {
        entity_id: "node_NOC-SRV-PVE01",
        features_requested: ["cpu_5min_avg", "memory_growth_velocity", "http_error_spike_index"]
      };
      demoOutput = {
        feature_store_status: "ONLINE_HEALTHY",
        read_latency_ms: 0.12,
        features_retrieved: {
          cpu_5min_avg: 18.5,
          memory_growth_velocity_mb_per_sec: 0.12,
          http_error_rate_spike_index: 0.0,
          network_latency_p99_ms: 4.2,
          anomaly_score_trend: "STABLE"
        },
        storage_engine: "In-Memory RAM Cache + SQLite Backing"
      };
    }

    if (n.id === 'L4_PromptRegistry') {
      demoInput.payload = {
        prompt_id: "prompt_intent_classifier",
        requested_version: "v2.1"
      };
      demoOutput = {
        registry_status: "ACTIVE_VERSION_LOADED",
        active_version: "v2.1",
        zero_downtime_hot_reload: true,
        available_versions: ["v1.0", "v2.0", "v2.1"],
        template_preview: "You are an AI Ops Intent Classifier. Analyze telemetry payload: {telemetry_json}..."
      };
    }

    if (n.id === 'L4_FeedbackCollector') {
      demoInput.payload = {
        incident_id: "INC-2026-9981",
        plan_id: "plan_c",
        technician_rating: "THUMBS_UP",
        technician_id: "tech_lead_ahmad"
      };
      demoOutput = {
        feedback_status: "FEEDBACK_COLLECTED",
        rlhf_pair_generated: true,
        rlhf_fine_tuning_dataset: "/tmp/feedback_rlhf_dataset.db",
        total_records_indexed: 42,
        fine_tuning_readiness: "READY_FOR_DPO_TRAINING"
      };
    }

    if (n.id === 'L4_ModelRegistry') {
      demoInput.payload = {
        prompt_context: "Incident INC-2026-9981 Anomaly Triage Payload",
        requested_model: "qwen2.5-coder:7b",
        local_endpoint: "http://127.0.0.1:11434"
      };
      demoOutput = {
        gateway_status: "HEALTHY_ROUTING_SUCCESSFUL",
        active_model_used: "qwen2.5-coder:7b",
        endpoint_type: "LOCAL_GPU_NODE",
        latency_ms: 185.2,
        automatic_cloud_failover: "ENABLED_STANDBY",
        cloud_fallback_target: "gemini-1.5-pro-fallback"
      };
    }

    // [FASE0 K-09] Data di panel ini adalah DEMO, bukan bukti eksekusi. Tandai eksplisit.
    demoOutput = { _evidence: "SIMULATED — bukan execution_evidence / post_remediation_evidence", simulated: true, ...demoOutput };
    const html = `
      <div style="font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--txt)">
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,109,90,0.1); padding:10px 14px; border-radius:6px; border:1px solid rgba(255,109,90,0.3); margin-bottom:12px">
          <div style="display:flex; align-items:center; gap:8px">
            <div style="width:12px; height:12px; border-radius:3px; background:${n.color}"></div>
            <b style="font-size:13px; color:#fff">${n.title}</b>
          </div>
          <span class="tag tag-orange" title="Data demo, bukan hasil eksekusi nyata">⚠️ SIMULATED (DEMO)</span>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:12px">
          <div style="background:var(--bg3); padding:10px; border-radius:6px; border:1px solid var(--bd)">
            <div style="font-weight:700; color:var(--cyan); margin-bottom:6px"><i class="fa-solid fa-download" style="margin-right:6px"></i>Node Input JSON</div>
            <pre style="margin:0; font-size:10px; color:#a5f3fc; white-space:pre-wrap; max-height:150px; overflow:auto">${JSON.stringify(demoInput, null, 2)}</pre>
          </div>
          <div style="background:var(--bg3); padding:10px; border-radius:6px; border:1px solid var(--bd)">
            <div style="font-weight:700; color:var(--green); margin-bottom:6px"><i class="fa-solid fa-arrow-up-from-bracket" style="margin-right:6px"></i>Node Output Result</div>
            <pre style="margin:0; font-size:10px; color:#bbf7d0; white-space:pre-wrap; max-height:150px; overflow:auto">${JSON.stringify(demoOutput, null, 2)}</pre>
          </div>
        </div>

        <div style="background:var(--bg3); padding:10px; border-radius:6px; border:1px solid var(--bd); font-size:11px; margin-bottom:14px">
          <b style="color:var(--txt)">Description & Specification:</b><br>
          <span style="color:var(--txt2)">${n.desc}</span>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:8px">
          <button class="btn btn-secondary btn-sm" onclick="Modal.close()">Tutup</button>
          <button class="btn btn-sm" onclick="AiLiveFlow.pulseNode('${n.id}'); Modal.close();" style="background:#ff6d5a; color:#fff; border:none; font-weight:700">
            <i class="fa-solid fa-play" style="margin-right:6px"></i> Test Run Node
          </button>
        </div>
      </div>
    `;

    Modal.show('⚡ n8n Node Inspector: ' + n.title, html, []);
  },

  render() {
    this.nodes = [
      // Layer 0: Client & User Layer (Level 0)
      { id: 'L0_User', title: 'System Administrator NOC', layerName: 'Client Layer', color: '#3b82f6', level: 0, desc: 'Interface operator NOC untuk monitoring, triase, dan eksekusi HITL.' },
      { id: 'L0_Ext', title: 'Chrome Extension Assistant', layerName: 'Client Layer', color: '#3b82f6', level: 0, desc: 'Plugin browser OSI untuk inspeksi insiden otomatis.' },
      { id: 'L0_Telegram', title: 'Telegram Bot Gateway', layerName: 'Client Layer', color: '#3b82f6', level: 0, desc: 'Kanal notifikasi eskalasi insiden kritis P1 & approval remote.' },

      // Layer 1: Web Portal Presentation Layer (Level 1)
      { id: 'L1_UI', title: 'System Portal Web UI', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Framework Web UI Dark Glassmorphism 60 FPS.' },
      { id: 'L1_Dash', title: 'Dashboard Utama (60 FPS)', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Visualisasi metrik sistem, KPI, dan telemetri langsung.' },
      { id: 'L1_HITL', title: 'Incident Triage & HITL Queue', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Antrean persetujuan eksekusi remedi manusia (Zero Risk).' },
      { id: 'L1_Telem', title: 'Telemetry Monitoring Feed', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Feed telemetri real-time perangkat & jaringan.' },
      { id: 'L1_AICog', title: 'AI Ops Cognition & RAG UI', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Tampilan penalaran AI, RAG candidate, dan narasi manusia.' },
      { id: 'L1_KBRag', title: 'Knowledge Base RAG Search', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Pencarian dokumen SOP dan pengetahuan historis RAG.' },
      { id: 'L1_GovUI', title: 'Model Config & Governance', layerName: 'Presentation Layer', color: '#0284c7', level: 1, desc: 'Manajemen kebijakan RBAC, ambang batas, dan model AI.' },

      // Layer 2: API Gateway Controller Layer (Level 2)
      { id: 'L2_Nginx', title: 'Nginx Reverse Proxy Ingress (osi-nginx)', layerName: 'Gateway Layer', color: '#0d9488', level: 2, desc: 'Reverse proxy TLS/HTTP, rate-limiting & WebSocket ingress menuju Go Portal.' },
      { id: 'L2_REST', title: 'HTTP REST API Gateway (:8080)', layerName: 'Gateway Layer', color: '#0d9488', level: 2, desc: 'Pengendali endpoint REST API Gin Go utama.' },
      { id: 'L2_WS', title: 'WebSocket Stream Server (:8080)', layerName: 'Gateway Layer', color: '#0d9488', level: 2, desc: 'Stream push telemetri downsampled 60 FPS.' },

      // Layer 3: Go Core Backend Services (Level 3)
      { id: 'L3_GoCore', title: 'Go Dashboard Server Core', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'Server backend Go utama dengan performa tinggi & auth RBAC.' },
      { id: 'L3_Ingestion', title: 'Go Telemetry Ingestion Server (:18800)', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'osi-ingestion-server penerima telemetri agen & syslog secara paralel ke NATS/PostgreSQL.' },
      { id: 'L3_Scheduler', title: 'Scheduler & Cron Service', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'osi-scheduler-service penjadwal audit periodik, maintenance SLA, & trigger job.' },
      { id: 'L3_Launch', title: 'Launcher Service Manager', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'Pengelola siklus hidup daemon dan agen lokal.' },
      { id: 'L3_Relay', title: 'Secure Encrypted Relay', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'Protokol eksekusi remote terenkripsi AES-256 GCM (osi-secure-relay).' },

      // Layer 4: Python AI Core Engine (Level 4)
      { id: 'L4_JarvisVoice', title: 'Jarvis Voice & Duplex Server', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'osi-jarvis-voice-server: server audio duplex WebSocket, STT/TTS, & kontrol suara NOC.' },
      { id: 'L4_PAI', title: 'Python AI Supervisor Cognition', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Supervisor AI mandiri pengelola alur kognisi insiden.' },
      { id: 'L4_Router', title: 'Multi-LLM Router (2-Step Hybrid Intent)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Verifikasi 2-langkah (TF-IDF + Local Semantic) menghemat 95% kuota token LLM.' },
      { id: 'L4_RAG', title: 'RAG 2.0 Vector Search & Reranker', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pencarian vektor histori terpresisi Top-10 (<120ms).' },
      { id: 'L4_DAG', title: 'Causal DAG Root Cause Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pelacak graf akar masalah berbasis statistik kausalitas.' },
      { id: 'L4_DBNEngine', title: 'Dynamic Bayesian Network (DBN Engine)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Engine deteksi anomali deret waktu berbasis DBN t-1 -> t & 4 Hidden States.' },
      { id: 'L4_DecisionNetwork', title: 'Decision Network (MEU Engine)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Kalkulator Maximum Expected Utility (MEU) yang menyeimbangkan sukses, downtime, & risiko bisnis.' },
      { id: 'L4_ClosedLoop', title: 'Closed-Loop Decision Orchestrator', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Orkestrator siklus keputusan otonom 7-tahap dengan latensi <0.8ms.' },
      { id: 'L4_ArchiveFTS', title: 'Cold Data FTS Archive Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Engine pencarian log historis FTS terindeks tsvector untuk data > 6 bulan (2+ tahun).' },
      { id: 'L4_EscalationChain', title: '3-Level Human Escalation Chain', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Matriks eskalasi 3-tingkat (UI -> Telegram -> SMS/Force Plan A) saat HITL timeout.' },
      { id: 'L4_Backpressure', title: 'Anti-Surge Backpressure Control', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Proteksi Semaphore (Max 10) & NATS Throttling saat lonjakan 500+ telemetri simultan.' },
      { id: 'L4_LocalRules', title: 'Offline Random Forest Fallback', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Model Decision Tree (rules.pkl) trained 298+ insiden untuk fallback saat LLM/Internet down.' },
      { id: 'L4_MemoryGraph', title: 'AI Memory Graph (Causal Sequence)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Graf memori kausalITAS berarah menyimpan rantai sekuensial kejadian (Device->Anomaly->Action->Result).' },
      { id: 'L4_KnowledgeAutoBuilder', title: 'Knowledge Auto-Builder Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Otomatisasi pembuat SOP Markdown & pgvector embeddings secara closed-loop setelah insiden solved.' },
      { id: 'L4_ModelEvaluator', title: 'Dynamic Model Evaluation Scorecard', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Scorecard evaluasi real-time 5 matriks (Latency, Accuracy, Hallucination, Cost, Success Rate) untuk dynamic LLM routing.' },
      { id: 'L4_GOV', title: 'Policy Engine HITL Safeguard', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Penegak aturan keamanan mitigasi tanpa resiko.' },
      { id: 'L4_Observer', title: 'Active Observer Daemon 24/7', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pengamat AI mandiri 24/7 mendeteksi anomali perilaku.' },
      { id: 'L4_Chaos', title: 'Autonomous Chaos Injection Worker', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pekerja uji ketahanan AIRE & auto rollback.' },
      { id: 'L4_SandboxPromoter', title: 'AI Sandbox Promotion Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Engine promosi karantina otomatis 6-tahap (SANDBOX_DRAFT -> APPROVED_GOLDEN) dengan verifikasi dry-run & threat scanner.' },
      { id: 'L4_SOPClarity', title: 'SOP Clarity Synthesizer (5-Section)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Sintesis log insiden mentah menjadi SOP 5-seksi terstruktur (Gejala, Deep RCA, Remedi 3-Tahap, Script, Metrik Pemulihan).' },
      { id: 'L4_PrecisionAnalyzer', title: 'Precision Remediation & 4-Factor RCA Analyzer', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Penganalisis presisi remedi berbasis skor 4-faktor (93.3% Match Rate).' },

      // Layer 5: Persistence & Event Broker Layer (Level 5)
      { id: 'L5_NATS', title: 'NATS JetStream 2-Node Active-Active HA Cluster', layerName: 'Event Broker', color: '#ea580c', level: 5, desc: 'Cluster 2-Node Active-Active (osi-nats, nats-node1 :4222 | nats-node2 :4223) dengan auto-failover & Stream Mirroring.' },
      { id: 'L5_Redis', title: 'Redis Cache & Redlock Cluster (:6379)', layerName: 'Storage', color: '#dc2626', level: 5, desc: 'osi-redis: in-memory cache terdistribusi, session cache, & Redlock distributed locks.' },
      { id: 'L5_SQL_Inc', title: 'PostgreSQL Database (osi_system :5432)', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Database Relasional utama PostgreSQL penampung insiden, telemetri, dan audit trail.' },
      { id: 'L5_SQL_SO', title: 'sprint_o.db (State Machine)', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Database state machine siklus hidup insiden.' },
      { id: 'L5_SQL_RAG', title: 'PostgreSQL pgvector Store (RAG 2.0)', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Database Vektor PostgreSQL penampung embeddings dokumen RAG dan SOP.' },
      { id: 'L5_SQL_Cog', title: 'cognitive_memory.db (Memory DB)', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Memori kognitif pembelajaran mandiri AI.' },
      { id: 'L5_FTP', title: 'FTP / Local Artifact Share', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Penyimpanan artifak laporan dan log mentah.' },

      // Layer 6: Automation & Container Infrastructure (Level 6)
      { id: 'L6_Docker', title: 'Docker Microservices Engine', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Engine kontainerisasi seluruh service AI Ops.' },
      { id: 'L6_Netdata', title: 'Netdata Monitoring Engine (:19999)', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Engine pemantauan performa real-time CPU, RAM, Disk, & Bandwidth.' },
      { id: 'L6_N8N', title: 'n8n Workflow Automation Engine', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Engine otomatisasi alur kerja terintegrasi n8n Engine v3.0.' },
      { id: 'L6_EMTrainer', title: 'Baum-Welch EM Trainer & Replay Gatekeeper', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Batch MLOps trainer & gatekeeper replay 50.000 insiden sebelum promosi model.' },
      { id: 'L6_SCA', title: 'SCA Security & SBOM Scanner', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Otomatisasi pemindaian CVE & pembuat manifest SBOM SPDX untuk Go & Python.' },
      { id: 'L6_CasaOS', title: 'pgAdmin / DBeaver DB Management (:5050)', layerName: 'Infrastructure', color: '#475569', level: 6, desc: 'Manajemen antarmuka GUI & client database PostgreSQL.' },

      // Layer 7: Monitoring Endpoint Agents (Level 7)
      { id: 'L7_WinAgent', title: 'Windows Agent Service (Go)', layerName: 'Agents', color: '#22c55e', level: 7, desc: 'Agen pemantau telemetri perangkat Windows.' },
      { id: 'L7_LinuxAgent', title: 'Linux Agent Service (Go)', layerName: 'Agents', color: '#22c55e', level: 7, desc: 'Agen pemantau telemetri perangkat Linux.' },
      { id: 'L7_Idempotency', title: 'Agent Idempotency Key Guard', layerName: 'Agents', color: '#22c55e', level: 7, desc: 'Cache 5-menit TTL SQLite WAL pencegah eksekusi ganda (Retry Storm Mitigation).' },

      // Layer 8: External Enterprise Integration (Level 8)
      { id: 'L8_LDAP', title: 'LDAP / Active Directory', layerName: 'Enterprise Ext', color: '#dc2626', level: 8, desc: 'Integrasi otentikasi identitas pengguna enterprise.' },
      { id: 'L8_Kafka', title: 'Apache Kafka Enterprise Cluster', layerName: 'Enterprise Ext', color: '#dc2626', level: 8, desc: 'Cluster event stream tingkat enterprise.' },
      { id: 'L8_DNS', title: 'Enterprise DNS / DHCP Server', layerName: 'Enterprise Ext', color: '#dc2626', level: 8, desc: 'Layanan nama domain & alokasi IP lokal.' },
      { id: 'L8_K8S', title: 'Kubernetes Multi-Site Cluster', layerName: 'Enterprise Ext', color: '#dc2626', level: 8, desc: 'Orkestrasi kluster multi-site enterprise.' },

      // Layer 9: Dashboard Analysis & Operations Control Flow (Level 9)
      { id: 'L9_Overview', title: 'Executive Overview & KPI Analytics', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Analisis kinerja keuangan, KPI insiden, dan tren bulanan (Panel Overview, Timeline, Storage).' },
      { id: 'L9_FleetMon', title: 'Fleet & Real-Time Diagnostics Hub', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Pemantauan kesehatan perangkat, server, PC kasir, & printer (Panel Fleet, Server, PC Health).' },
      { id: 'L9_IncidentRCA', title: 'Incident Triage & Causal RCA Portal', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Triase insiden live, graf kausalitas RCA, & korelasi matriks (Panel Incident, RCA, Graphs).' },
      { id: 'L9_GovSafeguard', title: 'HITL Approval & Governance Safeguards', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Antrean persetujuan manual, audit tata kelola AI, & rollback history (Panel Approval Queue & Security).' },
      { id: 'L9_AICognition', title: 'AI Cognition & RAG Knowledge Hub', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Konfigurasi multi-LLM, benchmark training, RAG vector learning, & SOP Registry (Panel AI & SOP).' },
      { id: 'L9_LogStream', title: 'Smart Stream & Log Inspection Center', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Viewer log real-time, NATS subjects explorer, & validation logs (Panel Smart Stream & Logs).' },
      { id: 'L9_NocRelay', title: 'NOC Operator Chat & Telegram Relay', layerName: 'Dashboard Analysis', color: '#06b6d4', level: 9, desc: 'Komunikasi interaktif operator NOC, Telegram bot relay, & manajemen RBAC (Panel Chat & RBAC).' },

      // Layer 3 Extended: Go Core API Sub-Modules
      { id: 'L3_ChatEngine', title: 'Chat Engine / AI Chat API', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'Engine chat AI real-time berbasis WebSocket & streaming token LLM.' },
      { id: 'L3_PredictiveAPI', title: 'Predictive Analytics API', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'API prediksi anomali & tren insiden berbasis ML terpadu.' },
      { id: 'L3_CogMemAPI', title: 'Cognitive Memory API', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'API pembacaan & penulisan memori kognitif AI jangka panjang.' },
      { id: 'L3_SprintOAPI', title: 'Sprint-O State Machine API', layerName: 'Backend Core', color: '#0d9488', level: 3, desc: 'Antarmuka REST untuk mesin state lifecycle insiden Sprint-O.' },

      // Layer 4 Extended: Python AI Engines (dari file nyata di codebase)
      { id: 'L4_BlastRadius', title: 'Blast Radius Impact Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Kalkulasi dampak ledakan insiden ke komponen infrastruktur sekitar.' },
      { id: 'L4_Consensus', title: 'Consensus Engine (Multi-Agent)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Mesin konsensus voting multi-agen AI untuk keputusan remediasi.' },
      { id: 'L4_Critic', title: 'Critic / Self-Evaluation Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Evaluasi mandiri kualitas narasi & keputusan AI per siklus.' },
      { id: 'L4_Counterfactual', title: 'Counterfactual Analysis Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Analisis skenario "what-if" untuk validasi akar masalah kausal.' },
      { id: 'L4_Escalation', title: 'Escalation Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Mesin eskalasi insiden otomatis berbasis prioritas & SLA.' },
      { id: 'L4_IntentClassifier', title: 'Intent Classifier Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Klasifikasi intent pengguna & telemetri untuk routing LLM presisi.' },
      { id: 'L4_Trust', title: 'Trust & Reputation Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Skor kepercayaan & reputasi agen & sumber telemetri.' },
      { id: 'L4_Closure', title: 'Incident Closure Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Validasi & penutupan otomatis insiden setelah remediasi berhasil.' },
      { id: 'L4_Replay', title: 'Incident Replay Engine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pemutaran ulang timeline insiden historis untuk pelatihan & RCA.' },
      { id: 'L4_StateMachine', title: 'Incident State Machine', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Mesin status lifecycle insiden: Open→Triaged→Remediated→Closed.' },
      { id: 'L4_SafetyLayer', title: 'AI Safety & Guardrail Layer', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Lapisan keamanan AI: filter injeksi, batas aksi, dan guardrail HITL.' },
      { id: 'L4_PresenceDaemon', title: 'Presence Daemon (Heartbeat)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Daemon pemantau kehadiran & heartbeat seluruh agen endpoint.' },
      { id: 'L4_CircuitBreaker', title: 'Circuit Breaker (Resilience)', layerName: 'AI Core', color: '#7c3aed', level: 4, desc: 'Pola circuit breaker otomatis untuk mencegah cascade failure.' },

      // Layer 4 Multi-Agent Sub-System
      { id: 'L4_MultiAgentOrch', title: 'Multi-Agent Orchestrator', layerName: 'AI Core', color: '#6d28d9', level: 4, desc: 'Orkestrasi distribusi tugas ke multi-agen AI spesialis secara paralel.' },
      { id: 'L4_AgentRegistry', title: 'Agent Registry Service', layerName: 'AI Core', color: '#6d28d9', level: 4, desc: 'Registri dinamis seluruh agen AI aktif beserta kapabilitas & statusnya.' },

      // Layer 4 Explicit AI Planning Engine (Otak Perencana AI Ops)
      { id: 'L4_Planner', title: 'AI Planning Engine', layerName: 'AI Core', color: '#a855f7', level: 4, desc: 'Otak perencana AI: formulasi skenario tindakan (Plan A, B, C), estimasi risiko, durasi, & probabilitas sukses.' },

      // Layer 4 Explicit AI Execution Engine (Pengawal Eksekusi Otonom & Auto-Rollback)
      { id: 'L4_Executor', title: 'AI Execution Engine', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Pengawal eksekusi otonom: eksekusi bertahap, pemantauan kesehatan real-time, & auto-rollback terproteksi.' },

      // Layer 4 Explicit AI Verification Engine (Double-Gate Quality Verification: Pre & Post Execution)
      { id: 'L4_Verifier', title: 'Execution Verification Engine', layerName: 'AI Core', color: '#06b6d4', level: 4, desc: 'Gerbang kualitas ganda (Pre & Post Execution): validasi kebijakan & batas risiko sebelum eksekusi & pembuktian pemulihan metrik pasca-eksekusi.' },

      // Layer 4 Feedback Collector & RLHF Loop Engine (Penerapan No. 3 / Feedback Collector)
      { id: 'L4_FeedbackCollector', title: 'Feedback Collector & RLHF Loop', layerName: 'AI Core', color: '#f59e0b', level: 4, desc: 'Pengumpul umpan balik HITL teknisi NOC untuk fine-tuning dataset RLHF/DPO.' },

      // Layer 4 Model Serving Gateway & Model Registry (Penerapan No. 4 / Automatic Cloud Failover)
      { id: 'L4_ModelRegistry', title: 'Model Serving Gateway & Registry', layerName: 'AI Core', color: '#ec4899', level: 4, desc: 'Gateway inference terpusat & katalog model AI dengan automatic failover ke Cloud LLM.' },

      // Layer 4 Explicit Observability & Telemetry Stack (Prometheus Metrics & OpenTelemetry Spans)
      { id: 'L4_Observability', title: 'Observability & Telemetry Stack', layerName: 'AI Core', color: '#0284c7', level: 4, desc: 'Pengumpul metrik Prometheus (Golden Signals) & OpenTelemetry distributed tracing spans.' },

      // Layer 4 Explicit Feature Store & Prompt Registry (Rank #1 & #2 Enterprise Expansion)
      { id: 'L4_FeatureStore', title: 'Feature Store Engine', layerName: 'AI Core', color: '#8b5cf6', level: 4, desc: 'Centralized real-time feature store for sub-millisecond anomaly feature retrieval (< 1ms).' },
      { id: 'L4_PromptRegistry', title: 'Prompt Registry & Versioning', layerName: 'AI Core', color: '#8b5cf6', level: 4, desc: 'Centralized LLM prompt registry, versioning (v1, v2), A/B testing, and hot rollback.' },

      // Layer 4 Explicit Dedicated Rollback Manager (Pengelola Rollback Terpisah & Isolation Engine)
      { id: 'L4_RollbackManager', title: 'Rollback Manager Engine', layerName: 'AI Core', color: '#ef4444', level: 4, desc: 'Pengelola rollback terpisah: pemulihan otomatis berbasis checkpoint, isolasi state awal, & intervensi degradasi tertunda.' },

      // Layer 4 Explicit AI Reflector Engine (Refleksi Kognitif & Postmortem)
      { id: 'L4_Reflector', title: 'AI Reflector & Postmortem Engine', layerName: 'AI Core', color: '#f59e0b', level: 4, desc: 'Engine refleksi paska-insiden: evaluasi kualitas keputusan, postmortem otomatis, & kalibrasi Cognitive Memory untuk pembelajaran masa depan.' },

      // Layer 4 Explicit Zero-Trust Secret Manager Vault (Kredensial Terenkripsi & Ephemeral Token)
      { id: 'L4_SecretManager', title: 'Zero-Trust Secret Manager Vault', layerName: 'AI Core', color: '#e11d48', level: 4, desc: 'Vault enkripsi kredensial terpusat (AES-256): penerbitan token ephemeral short-lived, sanitasi log otomatis, & rotasi JWT/Agent.' },

      // Layer 4 Zero-Hallucination Pre-Approved SOP Registry Engine
      { id: 'L4_SOPRegistry', title: 'Zero-Hallucination SOP Registry', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Registri SOP resmi bertanda-tangan digital NOC SysAdmin yang mengunci LLM intent agar 0% risiko halusinasi perintah.' },

      // Layer 4 Dual-Stage Grounding & Hallucination Verifier Engine
      { id: 'L4_GroundingVerifier', title: 'Dual-Stage Grounding Verifier', layerName: 'AI Core', color: '#06b6d4', level: 4, desc: 'Verifikasi ganda bebas halusinasi: Stage 1 RAG 2.0 Grounding Check & Stage 2 Enforce HITL Queue jika skor keyakinan AI < 95%.' },

      // Layer 4 Multi-Agent Critic Auditor Engine (Dua Otak AI Saling Memeriksa)
      { id: 'L4_CriticAuditor', title: 'Multi-Agent Critic Auditor', layerName: 'AI Core', color: '#a855f7', level: 4, desc: 'Agen auditor penilai risiko: menguji & mencari celah halusinasi pada skenario Planner. Wajib 100% konsensus (Score 1.0) atau dialihkan ke HITL.' },

      // Layer 4 Executive Client Summary Generator (Rangkuman Bahasa Indonesia Awam)
      { id: 'L4_ExecSummary', title: 'Executive Client Summary Generator', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Penerjemah log teknis rumit ke Bahasa Indonesia awam yang ringkas & jelas untuk klien & manajemen eksekutif.' },

      // Layer 4 Visual Causal DAG Recommendation Cards (Plan A/B/C Interaktif)
      { id: 'L4_CausalCards', title: 'Visual Causal DAG Cards (Plan A/B/C)', layerName: 'AI Core', color: '#f59e0b', level: 4, desc: 'Kartu rekomendasi interaktif berwarna: 🟢 Hijau (Aman Otomatis), 🟡 Kuning (One-Click HITL), 🔴 Merah (Kritikal Fisik Server).' },

      // Layer 4 Advanced Specialized Cognitive & Compliance Nodes
      { id: 'L4_SymptomCluster', title: 'Symptom Cluster & Novelty Engine', layerName: 'AI Core', color: '#8b5cf6', level: 4, desc: 'Divergent anomaly clustering & novelty distance score calculation (NOVEL_UNSEEN_ANOMALY).' },
      { id: 'L4_RemediationMatrix', title: 'Remediation Divergence Matrix', layerName: 'AI Core', color: '#a855f7', level: 4, desc: 'Dynamic issue-remediation mapping engine (6 distinct action taxonomies).' },
      { id: 'L4_ContinuousReinforcement', title: 'Continuous Feedback Reinforcement', layerName: 'AI Core', color: '#f59e0b', level: 4, desc: 'Meta-learning & sliding window performance decay engine (Negative Reinforcement Weighting).' },
      { id: 'L4_RegulatoryGuard', title: 'Regulatory Compliance Guard', layerName: 'AI Core', color: '#e11d48', level: 4, desc: 'Enterprise compliance & audit guard (ISO 27001, PCI-DSS POS, UU PDP Data Redaction).' },

      // Layer 4 Enterprise Governance & Security Nodes (26-Node Complete Expansion)
      { id: 'L4_PDP_Governance', title: 'Policy Decision Point (PDP)', layerName: 'AI Core', color: '#e11d48', level: 4, desc: 'Enterprise PDP Governance Framework v2.1.0 (7 Sub-modules: Context, Risk, Profiles, Multi-Step Workflow).' },
      { id: 'L4_GoldenRules', title: '5 Golden Rules Enforcer', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Enforces 5 Golden Rules: Action Catalog #1 Priority, Double-Gate, Rollback & Health Check, Audit Trail, Replay Validation.' },
      { id: 'L4_TrustCalibrator', title: 'Model Trust Calibrator (ECE)', layerName: 'AI Core', color: '#06b6d4', level: 4, desc: 'Real-time ECE calculation & Platt Scaling alignment alert when ECE > 0.15.' },
      { id: 'L4_AdversarialGuard', title: 'Adversarial Prompt Guard', layerName: 'AI Core', color: '#dc2626', level: 4, desc: 'Regex & pattern scanner for prompt injections and malicious shell commands.' },

      // Layer 4 Explicit Observability & Telemetry Stack (Prometheus Metrics & OpenTelemetry Spans)

      // Layer 4 & Layer 6 Extensions: Obsidian Vault & Modular n8n Workflows (v4.1 & v4.2)
      { id: 'L4_ObsidianVault', title: 'Obsidian Vault & Dynamic SOP Parser', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Engine pemindaian & parsing file Markdown Obsidian Vault (.md) dengan pembacaan YAML Frontmatter & bi-directional backlinks.' },
      { id: 'L4_ObsidianSyncDaemon', title: 'Obsidian Hot-Reload Sync Daemon', layerName: 'AI Core', color: '#10b981', level: 4, desc: 'Daemon pemantau perubahan file Vault secara real-time (Hot-Reload dengan nol downtime).' },
      { id: 'L4_PostMortemExporter', title: 'Auto Post-Mortem Vault Exporter', layerName: 'AI Core', color: '#f59e0b', level: 4, desc: 'Pemformat & penerbit laporan Post-Mortem otomatis berformat Obsidian Markdown ke DOCUMENTATION/obsidian_vault/incidents/.' },
      { id: 'L6_N8N_v4_1', title: 'n8n Workflow v4.1 (Obsidian Vault Sync)', layerName: 'Infrastructure', color: '#ff6d5a', level: 6, desc: 'Modular n8n Workflow v4.1 khusus pemicu hot-reload katalog SOP dan pemantau kesehatan SOP.' },
      { id: 'L6_N8N_v4_2', title: 'n8n Workflow v4.2 (Auto Post-Mortem Publisher)', layerName: 'Infrastructure', color: '#ff6d5a', level: 6, desc: 'Modular n8n Workflow v4.2 khusus publikasi laporan Post-Mortem Markdown ke Obsidian Vault & broadcast penutupan tiket.' },

      // Layer 5 Extended: Additional Storage
      { id: 'L5_OfflineCache', title: 'Offline Cache DB (SQLite)', layerName: 'Storage', color: '#d97706', level: 5, desc: 'Cache lokal untuk operasi offline saat koneksi terputus.' },

      // ── 4 New Enterprise Agentic AI Architecture Nodes ──────────────────────────
      { id: 'L4_DistributedLock', title: 'Synchronized Memory & Distributed Lock', layerName: 'AI Core', color: '#a855f7', level: 4, desc: 'Manajer lock terdistribusi (Redlock SETNX + Lua Script) yang mengisolasi transaksi pembacaan/penulisan memori kognitif antar-kontainer (osi-python-ai-core, osi-ai-consensus, osi-ai-critic).' },
      { id: 'L4_SemanticCache',   title: 'Semantic Vector Cache Layer (<20ms)',    layerName: 'AI Core', color: '#06b6d4', level: 4, desc: 'Tempat penyimpanan cache vektor TF-IDF sparse embedding untuk respon penalaran insiden serupa (<20ms latensi, -80% biaya LLM Cloud).' },
      { id: 'L4_SOPCanary',        title: 'SOP Canary Deployment & A/B Testing',     layerName: 'AI Core', color: '#eab308', level: 4, desc: 'Engine peluncuran SOP bertahap (10% -> 50% -> 100% Auto-Promotion) dengan perlindungan Instant Safety Rollback jika terdeteksi kegagalan/efek samping.' },
      { id: 'L4_LLMJudge',         title: 'Continuous LLM-as-a-Judge Pipeline',     layerName: 'AI Core', color: '#22c55e', level: 4, desc: 'Pipa evaluasi kualitas penalaran AI otomatis berkelanjutan terhadap 100+ dataset insiden historis (Faithfulness >98%, Hallucination 0%, RCA Precision >95%).' },

      // Sandbox Knowledge Pipeline Nodes (Stage 0 - Stage 5) — Menjelajah area canvas bawah yang kosong
      { id: 'SB_Stage0', title: 'Sandbox Stage 0: Intake', layerName: 'Sandbox Pipeline', color: '#3b82f6', level: 10, desc: 'Penerimaan dokumen SOP, Excel, telemetri & log insiden baru (Status: NEW).' },
      { id: 'SB_Stage1', title: 'Sandbox Stage 1: Staging Area', layerName: 'Sandbox Pipeline', color: '#a855f7', level: 10, desc: 'Area karantina isolasi dengan generasi UUID & verifikasi metadata (SANDBOX_DRAFT).' },
      { id: 'SB_Stage2', title: 'Sandbox Stage 2 & 3: Threat Scan', layerName: 'Sandbox Pipeline', color: '#06b6d4', level: 10, desc: 'Pengujian Simulasi Dry-Run & pemindaian ancaman keamanan prompt/script (VALIDATING).' },
      { id: 'SB_HITL',   title: 'Sandbox HITL Risk Gate', layerName: 'Sandbox Pipeline', color: '#eab308', level: 10, desc: 'Gerbang persetujuan 1-Click NOC Administrator untuk pengetahuan berdampak tinggi (PENDING_HITL_REVIEW).' },
      { id: 'SB_Stage4', title: 'Sandbox Stage 4: Golden Prod', layerName: 'Sandbox Pipeline', color: '#22c55e', level: 10, desc: 'Promosi ke basis pengetahuan produksi setelah lolos pengujian regresi 100% (GOLDEN_PRODUCTION).' },
      { id: 'SB_Stage5', title: 'Sandbox Stage 5: Continuous Learn', layerName: 'Sandbox Pipeline', color: '#14b8a6', level: 10, desc: 'Pembelajaran berkelanjutan, rekristalisasi SOP & recalibration pembobotan model (MONITORING/RETRAIN).' }
    ];

    this.edges = [
      // Obsidian Vault & n8n Modular Workflows (v4.1 & v4.2) Connections
      { source: 'L6_N8N_v4_1', target: 'L4_ObsidianSyncDaemon' },
      { source: 'L4_ObsidianSyncDaemon', target: 'L4_ObsidianVault' },
      { source: 'L4_ObsidianVault', target: 'L4_SOPRegistry' },
      { source: 'L4_Reflector', target: 'L4_PostMortemExporter' },
      { source: 'L4_PostMortemExporter', target: 'L6_N8N_v4_2' },
      { source: 'L6_N8N_v4_2', target: 'L0_Telegram' },
      { source: 'L6_N8N_v4_2', target: 'L8_Kafka' },
      // Layer 0 to Layer 1 & 2
      { source: 'L0_User', target: 'L1_UI' },
      { source: 'L0_Ext', target: 'L2_REST' },
      { source: 'L0_Telegram', target: 'L2_REST' },

      // Layer 1 to Layer 2 (via Nginx Ingress)
      { source: 'L0_User', target: 'L4_JarvisVoice' },
      { source: 'L4_JarvisVoice', target: 'L2_WS' },
      { source: 'L1_UI', target: 'L2_Nginx' },
      { source: 'L1_Dash', target: 'L2_Nginx' },
      { source: 'L2_Nginx', target: 'L2_REST' },
      { source: 'L2_Nginx', target: 'L2_WS' },
      { source: 'L1_HITL', target: 'L2_REST' },
      { source: 'L1_Telem', target: 'L2_WS' },
      { source: 'L1_AICog', target: 'L2_REST' },
      { source: 'L1_KBRag', target: 'L2_REST' },
      { source: 'L1_GovUI', target: 'L2_REST' },

      // Layer 2 to Layer 3 & Scheduler/Ingestion
      { source: 'L2_REST', target: 'L3_GoCore' },
      { source: 'L2_WS', target: 'L3_GoCore' },
      { source: 'L7_WinAgent', target: 'L3_Ingestion' },
      { source: 'L7_LinuxAgent', target: 'L3_Ingestion' },
      { source: 'L3_Ingestion', target: 'L5_NATS' },
      { source: 'L3_Ingestion', target: 'L5_SQL_Inc' },
      { source: 'L3_Scheduler', target: 'L4_PAI' },

      // Layer 3 to Layer 4 & Layer 5
      { source: 'L3_GoCore', target: 'L3_Launch' },
      { source: 'L3_GoCore', target: 'L3_Relay' },
      { source: 'L3_GoCore', target: 'L4_PAI' },
      { source: 'L3_GoCore', target: 'L5_NATS' },
      { source: 'L3_GoCore', target: 'L5_Redis' },
      { source: 'L3_GoCore', target: 'L5_SQL_Inc' },
      { source: 'L3_GoCore', target: 'L5_SQL_SO' },
      { source: 'L4_DistributedLock', target: 'L5_Redis' },

      // Layer 4 Internal & Persistence Connections
      { source: 'L4_PAI', target: 'L4_Router' },
      { source: 'L4_PAI', target: 'L4_RAG' },
      { source: 'L4_PAI', target: 'L4_DAG' },
      { source: 'L4_PAI', target: 'L4_GOV' },
      { source: 'L4_PAI', target: 'L4_Observer' },
      { source: 'L4_PAI', target: 'L4_Chaos' },
      { source: 'L4_RAG', target: 'L5_SQL_RAG' },
      { source: 'L4_PAI', target: 'L5_SQL_Cog' },

      // Layer 5 Broker to Agents (bidirectional: NATS pushes cmd, agents push telemetry back)
      { source: 'L5_NATS', target: 'L7_WinAgent' },
      { source: 'L5_NATS', target: 'L7_LinuxAgent' },
      { source: 'L7_WinAgent', target: 'L5_NATS' },
      { source: 'L7_LinuxAgent', target: 'L5_NATS' },

      // Layer 3 GoCore to FTP Artifact Storage
      { source: 'L3_GoCore', target: 'L5_FTP' },

      // Layer 1 UI distributes to all sub-panels (per blueprint: WP --> sub-menus)
      { source: 'L1_UI', target: 'L1_Dash' },
      { source: 'L1_UI', target: 'L1_HITL' },
      { source: 'L1_UI', target: 'L1_Telem' },
      { source: 'L1_UI', target: 'L1_AICog' },
      { source: 'L1_UI', target: 'L1_KBRag' },
      { source: 'L1_UI', target: 'L1_GovUI' },

      // Layer 6 Docker to Broker & Infra (Netdata & pgAdmin/DBeaver DB Mgmt)
      { source: 'L6_Docker', target: 'L5_NATS' },
      { source: 'L6_Docker', target: 'L6_N8N' },
      { source: 'L6_Docker', target: 'L6_CasaOS' },
      { source: 'L6_Docker', target: 'L6_Netdata' },
      { source: 'L6_Netdata', target: 'L5_NATS' },
      { source: 'L6_Netdata', target: 'L1_Telem' },
      { source: 'L7_WinAgent', target: 'L6_Netdata' },
      { source: 'L7_LinuxAgent', target: 'L6_Netdata' },
      { source: 'L3_GoCore', target: 'L6_CasaOS' },
      { source: 'L6_CasaOS', target: 'L5_SQL_Inc' },
      { source: 'L6_CasaOS', target: 'L5_SQL_RAG' },
      { source: 'L3_GoCore', target: 'L5_SQL_Inc' },
      { source: 'L4_RAG', target: 'L5_SQL_RAG' },
      { source: 'L4_PAI', target: 'L5_SQL_Inc' },

      // Layer 3 to Layer 8 External Enterprise Integration
      { source: 'L3_GoCore', target: 'L8_LDAP' },
      { source: 'L3_GoCore', target: 'L8_Kafka' },
      { source: 'L3_GoCore', target: 'L8_DNS' },
      { source: 'L3_GoCore', target: 'L8_K8S' },

      // Layer 3 GoCore to new Go API sub-modules
      { source: 'L3_GoCore', target: 'L3_ChatEngine' },
      { source: 'L3_GoCore', target: 'L3_PredictiveAPI' },
      { source: 'L3_GoCore', target: 'L3_CogMemAPI' },
      { source: 'L3_GoCore', target: 'L3_SprintOAPI' },

      // Layer 4 PAI & Diagnostics to AI Planning Engine
      { source: 'L4_PAI', target: 'L4_Planner' },
      { source: 'L4_DAG', target: 'L4_Planner' },
      { source: 'L4_Counterfactual', target: 'L4_Planner' },
      { source: 'L4_BlastRadius', target: 'L4_Planner' },
      { source: 'L4_Trust', target: 'L4_Planner' },

      // AI Planning Engine to Governance & Consensus
      { source: 'L4_Planner', target: 'L4_GOV' },
      { source: 'L4_Planner', target: 'L4_Consensus' },
      { source: 'L4_Planner', target: 'L4_StateMachine' },
      { source: 'L4_Planner', target: 'L4_MultiAgentOrch' },

      // Double-Gate AI Verifier (Pre-Execution Checks)
      { source: 'L4_Planner', target: 'L4_Verifier' },
      { source: 'L4_GOV', target: 'L4_Verifier' },
      { source: 'L4_BlastRadius', target: 'L4_Verifier' },
      { source: 'L4_Trust', target: 'L4_Verifier' },
      { source: 'L4_Counterfactual', target: 'L4_Verifier' },
      { source: 'L1_Telem', target: 'L4_Verifier' },

      // Verifier Pre-Check Clearance -> Executor or HITL
      { source: 'L4_Verifier', target: 'L4_Executor' },
      { source: 'L4_Verifier', target: 'L1_HITL' },

      // AI Execution Engine Outlets (Relay, Agents, n8n)
      { source: 'L4_Executor', target: 'L3_Relay' },
      { source: 'L4_Executor', target: 'L7_WinAgent' },
      { source: 'L4_Executor', target: 'L7_LinuxAgent' },
      { source: 'L4_Executor', target: 'L6_N8N' },

      // Double-Gate AI Verifier (Post-Execution Checks)
      { source: 'L4_Executor', target: 'L4_Verifier' },

      // Dedicated Rollback Manager Connections (Executor & Verifier Failure Outlets)
      { source: 'L4_Executor', target: 'L4_RollbackManager' },
      { source: 'L4_Verifier', target: 'L4_RollbackManager' },
      { source: 'L4_RollbackManager', target: 'L3_Relay' },
      { source: 'L4_RollbackManager', target: 'L7_WinAgent' },
      { source: 'L4_RollbackManager', target: 'L7_LinuxAgent' },
      { source: 'L4_RollbackManager', target: 'L4_StateMachine' },

      // Verifier Post-Check Handoff -> Closure, Escalation, StateMachine
      { source: 'L4_Verifier', target: 'L4_Closure' },
      { source: 'L4_Verifier', target: 'L4_Escalation' },
      { source: 'L4_Verifier', target: 'L4_StateMachine' },

      // AI Reflector Engine Connections (Closure/Verifier/Critic/Replay/Planner -> Reflector -> Cognitive Memory & Planner)
      { source: 'L4_Closure', target: 'L4_Reflector' },
      { source: 'L4_Verifier', target: 'L4_Reflector' },
      { source: 'L4_Critic', target: 'L4_Reflector' },
      { source: 'L4_Replay', target: 'L4_Reflector' },
      { source: 'L4_Executor', target: 'L4_Reflector' },
      { source: 'L4_Planner', target: 'L4_Reflector' },
      { source: 'L4_Reflector', target: 'L5_SQL_Cog' },
      { source: 'L4_Reflector', target: 'L3_CogMemAPI' },
      { source: 'L4_Reflector', target: 'L4_Planner' },

      // Zero-Trust Secret Manager Vault Connections (Vault -> Executor/Verifier/NATS/Agents)
      { source: 'L4_SecretManager', target: 'L4_Executor' },
      { source: 'L4_SecretManager', target: 'L4_Verifier' },
      { source: 'L4_SecretManager', target: 'L5_NATS' },
      { source: 'L4_SecretManager', target: 'L7_WinAgent' },
      { source: 'L4_SecretManager', target: 'L7_LinuxAgent' },

      // Observability & Telemetry Stack Connections (Executor/Verifier/Telem -> Observability -> DB)
      { source: 'L4_Executor', target: 'L4_Observability' },
      { source: 'L4_Verifier', target: 'L4_Observability' },
      { source: 'L1_Telem', target: 'L4_Observability' },
      { source: 'L4_Observability', target: 'L5_SQL_Inc' },

      // Store-and-Forward Offline Buffer Connections (Agents -> Offline Cache -> NATS)
      { source: 'L7_WinAgent', target: 'L5_OfflineCache' },
      { source: 'L7_LinuxAgent', target: 'L5_OfflineCache' },
      { source: 'L5_OfflineCache', target: 'L5_NATS' },

      // ITSM Closure Webhook Sync Connections (L4_Closure -> L6_N8N -> L0_Telegram & L8_Kafka)
      { source: 'L4_Closure', target: 'L6_N8N' },
      { source: 'L6_N8N', target: 'L0_Telegram' },
      { source: 'L6_N8N', target: 'L8_Kafka' },

      // Feature Store Connections (Telemetry -> FeatureStore -> DAG & Router)
      { source: 'L1_Telem', target: 'L4_FeatureStore' },
      { source: 'L4_FeatureStore', target: 'L4_DAG' },
      { source: 'L4_FeatureStore', target: 'L4_Router' },

      // Prompt Registry & Versioning Connections (PromptRegistry -> Router & Planner & Reflector)
      { source: 'L4_PromptRegistry', target: 'L4_Router' },
      { source: 'L4_PromptRegistry', target: 'L4_Planner' },
      { source: 'L4_PromptRegistry', target: 'L4_Reflector' },

      // Feedback Collector & RLHF Loop Connections (Telegram/HITL -> FeedbackCollector -> Reflector & Cognitive DB)
      { source: 'L0_Telegram', target: 'L4_FeedbackCollector' },
      { source: 'L4_FeedbackCollector', target: 'L4_Reflector' },
      { source: 'L4_FeedbackCollector', target: 'L5_SQL_Cog' },

      // Model Serving Gateway & Registry Connections (Router -> ModelRegistry -> ChatEngine & Kafka)
      { source: 'L4_Router', target: 'L4_ModelRegistry' },
      { source: 'L4_ModelRegistry', target: 'L3_ChatEngine' },
      { source: 'L4_ModelRegistry', target: 'L8_Kafka' },

      // Layer 4 PAI to other auxiliary AI engines
      { source: 'L4_PAI', target: 'L4_BlastRadius' },
      { source: 'L4_PAI', target: 'L4_Consensus' },
      { source: 'L4_PAI', target: 'L4_Critic' },
      { source: 'L4_PAI', target: 'L4_Counterfactual' },
      { source: 'L4_PAI', target: 'L4_Escalation' },
      { source: 'L4_Router', target: 'L4_IntentClassifier' },
      { source: 'L4_PAI', target: 'L4_Trust' },
      { source: 'L4_PAI', target: 'L4_Closure' },
      { source: 'L4_PAI', target: 'L4_Replay' },
      { source: 'L4_PAI', target: 'L4_StateMachine' },
      { source: 'L4_GOV', target: 'L4_SafetyLayer' },
      { source: 'L5_NATS', target: 'L4_PresenceDaemon' },
      { source: 'L4_PAI', target: 'L4_CircuitBreaker' },

      // Multi-Agent sub-system
      { source: 'L4_MultiAgentOrch', target: 'L4_AgentRegistry' },

      // Layer 5 Offline Cache from GoCore
      { source: 'L3_GoCore', target: 'L5_OfflineCache' },

      // Data Flow Connections for 6 New Strategic Enterprise Nodes (FTS, Escalation, Backpressure, SCA, LocalRules, Idempotency)
      { source: 'L1_KBRag', target: 'L4_ArchiveFTS' },
      { source: 'L4_ArchiveFTS', target: 'L5_SQL_Inc' },
      { source: 'L1_HITL', target: 'L4_EscalationChain' },
      { source: 'L4_EscalationChain', target: 'L0_Telegram' },
      { source: 'L4_EscalationChain', target: 'L4_Executor' },
      { source: 'L5_NATS', target: 'L4_Backpressure' },
      { source: 'L4_Backpressure', target: 'L4_PAI' },
      { source: 'L4_Router', target: 'L4_LocalRules' },
      { source: 'L4_LocalRules', target: 'L4_Planner' },
      { source: 'L6_Docker', target: 'L6_SCA' },
      { source: 'L6_SCA', target: 'L4_SecretManager' },
      { source: 'L5_NATS', target: 'L7_Idempotency' },
      { source: 'L7_Idempotency', target: 'L7_WinAgent' },
      { source: 'L7_Idempotency', target: 'L7_LinuxAgent' },

      // Data Flow Connections for 3 Advanced Cognitive Enhancements (Memory Graph, Knowledge Auto-Builder, Model Evaluator)
      { source: 'L4_DAG', target: 'L4_MemoryGraph' },
      { source: 'L4_MemoryGraph', target: 'L5_SQL_Cog' },
      { source: 'L4_Closure', target: 'L4_KnowledgeAutoBuilder' },
      { source: 'L4_KnowledgeAutoBuilder', target: 'L5_SQL_RAG' },
      { source: 'L4_Router', target: 'L4_ModelEvaluator' },
      { source: 'L4_ModelEvaluator', target: 'L4_ModelRegistry' },

      // Flow Continuity & End-to-End Execution Pipeline (Zero Dead Ends, Zero Blind Sources)
      { source: 'L4_Observer', target: 'L4_PAI' },
      { source: 'L4_Observer', target: 'L4_IntentClassifier' },
      { source: 'L4_Chaos', target: 'L4_PAI' },
      { source: 'L4_Chaos', target: 'L4_Observability' },
      { source: 'L4_IntentClassifier', target: 'L4_Router' },
      { source: 'L4_PAI', target: 'L4_PromptRegistry' },
      { source: 'L4_PAI', target: 'L4_SecretManager' },
      { source: 'L4_SecretManager', target: 'L4_Executor' },
      { source: 'L4_SafetyLayer', target: 'L4_Executor' },
      { source: 'L4_CircuitBreaker', target: 'L5_NATS' },
      { source: 'L4_MultiAgentOrch', target: 'L4_Consensus' },
      { source: 'L4_Consensus', target: 'L4_Escalation' },
      { source: 'L4_Escalation', target: 'L1_HITL' },
      { source: 'L4_AgentRegistry', target: 'L7_LinuxAgent' },
      { source: 'L3_Launch', target: 'L6_Docker' },
      { source: 'L3_Relay', target: 'L5_NATS' },
      { source: 'L3_PredictiveAPI', target: 'L4_FeatureStore' },
      { source: 'L3_CogMemAPI', target: 'L5_SQL_Cog' },
      { source: 'L3_SprintOAPI', target: 'L5_SQL_SO' },
      { source: 'L3_ChatEngine', target: 'L1_AICog' },
      { source: 'L4_StateMachine', target: 'L5_SQL_SO' },
      { source: 'L4_PresenceDaemon', target: 'L5_NATS' },

      // Layer 4 Zero-Hallucination SOP Registry Engine Edges
      { source: 'L4_Router', target: 'L4_SOPRegistry' },
      { source: 'L4_SOPRegistry', target: 'L4_Planner' },
      { source: 'L4_SOPRegistry', target: 'L4_Executor' },

      // Layer 4 Dual-Stage Grounding & Hallucination Verifier Engine Edges
      { source: 'L4_SOPRegistry', target: 'L4_GroundingVerifier' },
      { source: 'L4_GroundingVerifier', target: 'L4_Verifier' },
      { source: 'L4_GroundingVerifier', target: 'L1_HITL' },

      // Layer 4 Multi-Agent Critic Auditor Engine Edges
      { source: 'L4_Planner', target: 'L4_CriticAuditor' },
      { source: 'L4_CriticAuditor', target: 'L4_Consensus' },
      { source: 'L4_CriticAuditor', target: 'L1_HITL' },

      // Layer 4 Executive Client Summary Generator Edges
      { source: 'L4_Reflector', target: 'L4_ExecSummary' },
      { source: 'L4_ExecSummary', target: 'L1_UI' },
      { source: 'L4_ExecSummary', target: 'L0_Telegram' },

      // Layer 4 Visual Causal DAG Cards (Plan A/B/C) Edges
      { source: 'L4_ExecSummary', target: 'L4_CausalCards' },
      { source: 'L4_CausalCards', target: 'L1_UI' },
      { source: 'L4_CausalCards', target: 'L1_HITL' },

      // Layer 9: Dashboard Analysis & Operations Control Flow Edges
      { source: 'L1_UI', target: 'L9_Overview' },
      { source: 'L1_Dash', target: 'L9_Overview' },
      { source: 'L1_Telem', target: 'L9_FleetMon' },
      { source: 'L6_Netdata', target: 'L9_FleetMon' },
      { source: 'L7_WinAgent', target: 'L9_FleetMon' },
      { source: 'L7_LinuxAgent', target: 'L9_FleetMon' },
      { source: 'L4_CausalCards', target: 'L9_IncidentRCA' },
      { source: 'L4_DAG', target: 'L9_IncidentRCA' },
      { source: 'L1_HITL', target: 'L9_GovSafeguard' },
      { source: 'L4_GOV', target: 'L9_GovSafeguard' },
      { source: 'L4_ModelRegistry', target: 'L9_AICognition' },
      { source: 'L4_SOPRegistry', target: 'L9_AICognition' },
      { source: 'L4_Observability', target: 'L9_LogStream' },
      { source: 'L5_NATS', target: 'L9_LogStream' },
      { source: 'L3_ChatEngine', target: 'L9_NocRelay' },
      { source: 'L0_Telegram', target: 'L9_NocRelay' },

      // Layer 4 Enterprise Governance, Compliance & Security Data Flow Edges
      { source: 'L1_Telem', target: 'L4_SymptomCluster' },
      { source: 'L4_SymptomCluster', target: 'L4_Router' },
      { source: 'L4_Router', target: 'L4_RemediationMatrix' },
      { source: 'L4_RemediationMatrix', target: 'L4_Planner' },
      { source: 'L4_Reflector', target: 'L4_ContinuousReinforcement' },
      { source: 'L4_ContinuousReinforcement', target: 'L4_Planner' },
      { source: 'L4_Planner', target: 'L4_RegulatoryGuard' },
      { source: 'L4_RegulatoryGuard', target: 'L4_Verifier' },

      // Layer 4 PDP, 5 Golden Rules, Trust Calibrator, & Adversarial Guard Edges
      { source: 'L1_UI', target: 'L4_AdversarialGuard' },
      { source: 'L0_Telegram', target: 'L4_AdversarialGuard' },
      { source: 'L4_AdversarialGuard', target: 'L4_PromptRegistry' },
      { source: 'L4_Router', target: 'L4_GoldenRules' },
      { source: 'L4_GoldenRules', target: 'L4_Planner' },
      { source: 'L4_GoldenRules', target: 'L4_Executor' },
      { source: 'L4_Planner', target: 'L4_PDP_Governance' },
      { source: 'L4_PDP_Governance', target: 'L4_Verifier' },
      { source: 'L4_PDP_Governance', target: 'L5_SQL_Inc' },
      { source: 'L4_Reflector', target: 'L4_TrustCalibrator' },
      { source: 'L4_TrustCalibrator', target: 'L4_Planner' },

      // Sandbox Knowledge Pipeline Sequential Flow & System Connections (Stage 0 -> Stage 5)
      { source: 'L4_KnowledgeAutoBuilder', target: 'SB_Stage0' },
      { source: 'L4_ObsidianVault', target: 'SB_Stage0' },
      { source: 'SB_Stage0', target: 'SB_Stage1' },
      { source: 'SB_Stage1', target: 'SB_Stage2' },
      { source: 'SB_Stage2', target: 'L4_AdversarialGuard' },
      { source: 'SB_Stage2', target: 'L4_SafetyLayer' },
      { source: 'SB_Stage2', target: 'SB_HITL' },
      { source: 'SB_HITL', target: 'L1_HITL' },
      { source: 'SB_HITL', target: 'L4_GOV' },
      { source: 'SB_HITL', target: 'SB_Stage4' },
      { source: 'SB_Stage4', target: 'L4_SandboxPromoter' },
      { source: 'SB_Stage4', target: 'L5_SQL_RAG' },
      { source: 'SB_Stage4', target: 'L4_RAG' },
      { source: 'SB_Stage4', target: 'SB_Stage5' },
      { source: 'SB_Stage5', target: 'L4_Reflector' },
      { source: 'SB_Stage5', target: 'L4_DPOSynthesizer' },

      // 4 New Enterprise Agentic AI Architecture Edges
      { source: 'L4_MemoryGraph', target: 'L4_DistributedLock' },
      { source: 'L4_DistributedLock', target: 'L5_SQL_Cog' },
      { source: 'L4_Router', target: 'L4_SemanticCache' },
      { source: 'L4_SemanticCache', target: 'L4_LLMs' },
      { source: 'L4_SandboxPromoter', target: 'L4_SOPCanary' },
      { source: 'L4_SOPCanary', target: 'L4_SOPRegistry' },
      { source: 'L4_Reflector', target: 'L4_LLMJudge' },
      { source: 'L4_LLMJudge', target: 'L4_ModelEvaluator' }
    ];

    // Group nodes by level
    let levelGroups = {};
    this.nodes.forEach(n => {
      levelGroups[n.level] = levelGroups[n.level] || [];
      levelGroups[n.level].push(n);
    });

    // Horizontal swimlane layout math (Non-Overlapping Left-to-Right Architecture)
    const layerXOffsets = {
      0: -900,  // L0: Client Layer (X = -900)
      1: -620,  // L1: Presentation UI (X = -620)
      2: -340,  // L2: API Gateway (X = -340)
      3: -60,   // L3: Go Core Server (X = -60)
      4: 925,   // L4: Python AI Engine Sub-cols Center (X = 925)
      5: 1900,  // L5: Broker & Storage (X = 1900)
      6: 2200,  // L6: Infrastructure (X = 2200)
      7: 2500,  // L7: Endpoint Agents (X = 2500)
      8: 2800,  // L8: Enterprise Ext (X = 2800)
      9: 3100,  // L9: Dashboard Analysis Flow (X = 3100)
      10: 625   // SB: Sandbox Knowledge Pipeline Flow (X = 625)
    };

    const layerNames = {
      0: 'L0: Client & User',
      1: 'L1: Presentation UI',
      2: 'L2: API Gateway',
      3: 'L3: Go Core Server',
      4: 'L4: Python AI Core Engine',
      5: 'L5: Broker & Storage',
      6: 'L6: Infrastructure',
      7: 'L7: Endpoint Agents',
      8: 'L8: Enterprise Ext',
      9: 'L9: Dashboard Analysis Flow',
      10: 'SANDBOX KNOWLEDGE PIPELINE (Stage 0 - Stage 5)'
    };

    const layerColors = {
      0: '#3b82f6', 1: '#0284c7', 2: '#0d9488', 3: '#0d9488',
      4: '#7c3aed', 5: '#ea580c', 6: '#475569', 7: '#22c55e', 8: '#dc2626', 9: '#06b6d4', 10: '#a855f7'
    };

    // Layout nodes vertically within each horizontal level column with zero overlap
    const Y_SPACING = 70;

    Object.keys(levelGroups).forEach(lvlStr => {
      const l = parseInt(lvlStr);
      const nodes = levelGroups[l];

      if (l === 4) {
        // Split 50+ Python AI Core nodes into 6 spacious sub-columns (A=220, B=500, C=780, D=1060, E=1340, F=1620)
        const numCols = 6;
        const cols = Array.from({ length: numCols }, () => []);
        nodes.forEach((n, idx) => {
          cols[idx % numCols].push(n);
        });

        const colXPositions = [220, 500, 780, 1060, 1340, 1620];
        cols.forEach((col, cIdx) => {
          const totalH = (col.length - 1) * Y_SPACING;
          const startY = -(totalH / 2);
          col.forEach((n, idx) => {
            n.x = colXPositions[cIdx];
            n.y = startY + idx * Y_SPACING;
          });
        });
      } else if (l === 10) {
        // Level 10: Sandbox Knowledge Pipeline — Horizontally spaced at Y = 520 (Safely below Level 4 with 280px+ clearance)
        const sandboxXCoords = [-620, -200, 220, 780, 1340, 1900];
        nodes.forEach((n, idx) => {
          n.x = sandboxXCoords[idx] !== undefined ? sandboxXCoords[idx] : (idx * 400 - 620);
          n.y = 520;
        });
      } else {
        const baseX = layerXOffsets[l] !== undefined ? layerXOffsets[l] : (l * 320 - 900);
        const totalHeight = (nodes.length - 1) * Y_SPACING;
        const startY = -(totalHeight / 2);

        nodes.forEach((n, idx) => {
          n.x = baseX;
          n.y = startY + idx * Y_SPACING;
        });
      }
    });

    // Restore saved custom node positions if present
    const savedLayout = localStorage.getItem('osi_ai_flow_custom_positions');
    if (savedLayout) {
      try {
        const posMap = JSON.parse(savedLayout);
        if (posMap._swimlanes) this.swimlanePos = posMap._swimlanes;
        this.nodes.forEach(n => {
          if (posMap[n.id] && typeof posMap[n.id].x === 'number') {
            n.x = posMap[n.id].x;
            n.y = posMap[n.id].y;
          }
        });
      } catch(e) {}
    }

    const elNodes = document.getElementById('ai-flow-nodes');
    const elEdges = document.getElementById('ai-flow-edges');
    if (!elNodes || !elEdges) return;

    const ns = 'http://www.w3.org/2000/svg';
    elNodes.innerHTML = '';
    elEdges.innerHTML = '';

    // Render swimlane layer headers above each column
    Object.keys(layerXOffsets).forEach(lStr => {
      const l = parseInt(lStr);
      const layerNodes = this.nodes.filter(n => n.level === l);
      let defaultX = layerXOffsets[l];
      let minY = layerNodes.length > 0 ? Math.min(...layerNodes.map(n => n.y)) - 50 : -300;

      this.swimlanePos = this.swimlanePos || {};
      if (!this.swimlanePos[l]) {
        this.swimlanePos[l] = { x: defaultX, y: minY };
      }
      const posX = this.swimlanePos[l].x;
      const posY = this.swimlanePos[l].y;

      const color = layerColors[l] || '#3b82f6';
      const name = layerNames[l] || `Layer ${l}`;

      const gLvl = document.createElementNS(ns, 'g');
      gLvl.setAttribute('id', 'gtn-swimlane-' + l);
      gLvl.setAttribute('class', 'ai-flow-node');
      gLvl.setAttribute('style', 'cursor:grab; transition: filter 0.3s ease');
      gLvl.setAttribute('transform', `translate(${posX}, ${posY})`);
      gLvl.onmousedown = (e) => AiLiveFlow.onSwimlaneMouseDown(e, l);

      const rectLvl = document.createElementNS(ns, 'rect');
      rectLvl.setAttribute('x', '-80');
      rectLvl.setAttribute('y', '-17');
      rectLvl.setAttribute('width', '160');
      rectLvl.setAttribute('height', '34');
      rectLvl.setAttribute('rx', '6');
      rectLvl.setAttribute('fill', color);
      rectLvl.setAttribute('fill-opacity', '0.18');
      rectLvl.setAttribute('stroke', color);
      rectLvl.setAttribute('stroke-width', '1.5');

      const textLvl = document.createElementNS(ns, 'text');
      textLvl.setAttribute('x', '0');
      textLvl.setAttribute('y', '4');
      textLvl.setAttribute('text-anchor', 'middle');
      textLvl.setAttribute('fill', '#ffffff');
      textLvl.setAttribute('font-size', '10.5');
      textLvl.setAttribute('font-weight', '700');
      textLvl.setAttribute('font-family', "'JetBrains Mono', sans-serif");
      textLvl.textContent = name;

      gLvl.appendChild(rectLvl);
      gLvl.appendChild(textLvl);
      elNodes.appendChild(gLvl);
    });

    // Edge color-coding system per flow type
    const edgeColorMap = {
      // Telemetry push/pull (Agent <-> NATS) — coklat tembaga
      'L7_WinAgent-L5_NATS':   { stroke: 'rgba(194,120,40,0.90)',  width: '2.2' },
      'L7_LinuxAgent-L5_NATS': { stroke: 'rgba(194,120,40,0.90)',  width: '2.2' },
      'L5_NATS-L7_WinAgent':   { stroke: 'rgba(194,120,40,0.90)',  width: '2.2' },
      'L5_NATS-L7_LinuxAgent': { stroke: 'rgba(194,120,40,0.90)',  width: '2.2' },
      'L4_PresenceDaemon-L5_NATS': { stroke: 'rgba(194,120,40,0.85)',  width: '2.0' },
      'L5_NATS-L4_PresenceDaemon': { stroke: 'rgba(194,120,40,0.85)',  width: '2.0' },
    };

    // Classify edge by source/target layer for default coloring
    const getEdgeStyle = (src, tgt) => {
      const key = src + '-' + tgt;
      if (edgeColorMap[key]) return edgeColorMap[key];
      // Sandbox Knowledge Pipeline Flow — Ungu bercahaya khas Sandbox
      if (src.startsWith('SB_') || tgt.startsWith('SB_'))
        return { stroke: 'rgba(168,85,247,0.95)', width: '2.5' };
      // AI Planning Engine flow (L4_Planner input/output) — ungumagenta berkilau
      if (src === 'L4_Planner' || tgt === 'L4_Planner')
        return { stroke: 'rgba(168,85,247,0.95)', width: '2.4' };
      // AI Execution Engine flow (L4_Executor input/output) — hijau zamrud berkilau
      if (src === 'L4_Executor' || tgt === 'L4_Executor')
        return { stroke: 'rgba(16,185,129,0.95)', width: '2.4' };
      // Execution Verification Engine flow (L4_Verifier input/output) — cyan zamrud berkilau
      if (src === 'L4_Verifier' || tgt === 'L4_Verifier')
        return { stroke: 'rgba(6,182,212,0.95)', width: '2.4' };
      // Dedicated Rollback Manager flow (L4_RollbackManager input/output) — merah coral berkilau
      if (src === 'L4_RollbackManager' || tgt === 'L4_RollbackManager')
        return { stroke: 'rgba(239,68,68,0.95)', width: '2.4' };
      // AI Reflector Engine flow (L4_Reflector input/output) — emas amber berkilau
      if (src === 'L4_Reflector' || tgt === 'L4_Reflector')
        return { stroke: 'rgba(245,158,11,0.95)', width: '2.4' };
      const srcLvl = (this.nodes.find(n => n.id === src) || {}).level;
      const tgtLvl = (this.nodes.find(n => n.id === tgt) || {}).level;
      // Storage flow (→ SQLite / Cache / FTP) — coklat amber
      if (['L5_SQL_Inc','L5_SQL_SO','L5_SQL_RAG','L5_SQL_Cog','L5_FTP','L5_OfflineCache'].includes(tgt))
        return { stroke: 'rgba(161,98,7,0.82)', width: '1.8' };
      // AI Engine internal (L4 → L4) — biru indigo
      if (srcLvl === 4 && tgtLvl === 4)
        return { stroke: 'rgba(99,102,241,0.82)', width: '1.8' };
      // External Enterprise Integration (→ L8) — merah gelap hitam
      if (tgtLvl === 8)
        return { stroke: 'rgba(127,29,29,0.85)', width: '1.8' };
      // Presentation Layer (L1 internal) — hitam biru gelap
      if (srcLvl === 1 && tgtLvl === 1)
        return { stroke: 'rgba(30,58,138,0.75)', width: '1.6' };
      // Client → Portal (L0→L1) — biru terang
      if (srcLvl === 0)
        return { stroke: 'rgba(59,130,246,0.80)', width: '1.8' };
      // Infrastructure/Docker (L6) — abu hitam
      if (srcLvl === 6)
        return { stroke: 'rgba(51,65,85,0.85)', width: '1.8' };
      // Default: biru cyan gelap
      return { stroke: 'rgba(14,116,144,0.72)', width: '1.8' };
    };

    // Color-coded moving particle balls per flow category (Insiden, Telemetri, Feedback, Core)
    const getFlowCategory = (src, tgt) => {
      // 1. Pengambilan Telemetri (Agent <-> NATS <-> Observability <-> FeatureStore) — Oranye Tembaga Berkilau
      if (src.includes('Telem') || tgt.includes('Telem') || src.includes('Agent') || tgt.includes('Agent') ||
          src === 'L4_Observability' || tgt === 'L4_Observability' || src === 'L4_FeatureStore' || tgt === 'L4_FeatureStore' ||
          src === 'L4_PresenceDaemon' || tgt === 'L4_PresenceDaemon' || tgt === 'L5_NATS' || src === 'L5_NATS') {
        return { color: '#f97316', glowColor: '#fb923c', radius: '4.5', duration: '2.4s' }; // Telemetri: Orange Tembaga
      }
      // 2. Alur Feedback & RLHF Loop (HITL / Telegram -> FeedbackCollector -> Reflector -> CogDB) — Emas Amber Berkilau
      if (src.includes('Feedback') || tgt.includes('Feedback') || src === 'L4_Reflector' || tgt === 'L4_Reflector' ||
          src === 'L1_HITL' || src === 'L0_Telegram') {
        return { color: '#f59e0b', glowColor: '#fbbf24', radius: '4.5', duration: '2.8s' }; // Feedback: Emas Amber
      }
      // 3. Alur Insiden & Execution Trigger (User/Triggers -> GoCore -> PAI -> Planner -> Executor -> Verifier -> Rollback) — Merah Zamrud Glowing
      if (src === 'L4_Planner' || tgt === 'L4_Planner' || src === 'L4_Executor' || tgt === 'L4_Executor' ||
          src === 'L4_Verifier' || tgt === 'L4_Verifier' || src === 'L4_RollbackManager' || tgt === 'L4_RollbackManager' ||
          src === 'L0_User' || src === 'L0_Ext' || src === 'L2_REST' || src === 'L3_GoCore' || src === 'L4_PAI' || src === 'L4_Router') {
        return { color: '#ef4444', glowColor: '#f87171', radius: '5.2', duration: '1.8s' }; // Insiden: Merah Zamrud Glowing
      }
      // 4. Default Core AI Internal Data Flow — Cyan Electric
      return { color: '#06b6d4', glowColor: '#22d3ee', radius: '4.0', duration: '3.0s' };
    };

    // Render n8n live glowing horizontal cubic bezier curves for edges (Left-to-Right)
    this.edges.forEach(e => {
      const s = this.nodes.find(n => n.id === e.source);
      const t = this.nodes.find(n => n.id === e.target);
      if (!s || !t) return;
      const dx = Math.max(40, Math.abs(t.x - s.x) * 0.45);
      const pathD = `M ${s.x + 85} ${s.y} C ${s.x + 85 + dx} ${s.y}, ${t.x - 85 - dx} ${t.y}, ${t.x - 85} ${t.y}`;
      const path = document.createElementNS(ns, 'path');
      path.setAttribute('id', 'edge-' + e.source + '-' + e.target);
      path.setAttribute('d', pathD);
      const style = getEdgeStyle(e.source, e.target);
      path.setAttribute('stroke', style.stroke);
      path.setAttribute('stroke-width', style.width);
      path.setAttribute('fill', 'none');
      if (this._activeMotion) path.setAttribute('class', 'n8n-live-path');
      elEdges.appendChild(path);

      // Render live animated moving particle balls along path
      if (this._activeMotion) {
        const cat = getFlowCategory(e.source, e.target);
        
        // Primary Particle Ball
        const circle1 = document.createElementNS(ns, 'circle');
        circle1.setAttribute('r', cat.radius);
        circle1.setAttribute('fill', cat.color);
        circle1.setAttribute('style', `filter: drop-shadow(0 0 6px ${cat.glowColor}); opacity: 0.95;`);

        const anim1 = document.createElementNS(ns, 'animateMotion');
        anim1.setAttribute('dur', cat.duration);
        anim1.setAttribute('repeatCount', 'indefinite');
        anim1.setAttribute('path', pathD);

        circle1.appendChild(anim1);
        elEdges.appendChild(circle1);

        // Staggered Secondary Particle Ball (offset by half duration)
        const durSec = parseFloat(cat.duration);
        const circle2 = document.createElementNS(ns, 'circle');
        circle2.setAttribute('r', (parseFloat(cat.radius) * 0.8).toString());
        circle2.setAttribute('fill', cat.color);
        circle2.setAttribute('style', `filter: drop-shadow(0 0 4px ${cat.glowColor}); opacity: 0.75;`);

        const anim2 = document.createElementNS(ns, 'animateMotion');
        anim2.setAttribute('dur', cat.duration);
        anim2.setAttribute('begin', (durSec / 2).toFixed(1) + 's');
        anim2.setAttribute('repeatCount', 'indefinite');
        anim2.setAttribute('path', pathD);

        circle2.appendChild(anim2);
        elEdges.appendChild(circle2);
      }
    });

    // Render n8n node cards with horizontal connector ports (Left In, Right Out)
    this.nodes.forEach((n) => {
      const g = document.createElementNS(ns, 'g');
      g.setAttribute('id', 'gtn-' + n.id);
      g.setAttribute('class', 'ai-flow-node');
      g.setAttribute('style', 'cursor:grab; transition: filter 0.3s ease');
      g.setAttribute('transform', `translate(${n.x},${n.y})`);
      g.onmousedown = (e) => AiLiveFlow.onNodeMouseDown(e, n.id);
      g.onclick = (e) => {
        if (!AiLiveFlow._dragMoved) AiLiveFlow.inspectNode(n.id);
      };

      // Card Outer Rect (Red Glow when crashed/timed out)
      const rect = document.createElementNS(ns, 'rect');
      rect.setAttribute('x', '-85');
      rect.setAttribute('y', '-20');
      rect.setAttribute('width', '170');
      rect.setAttribute('height', '40');
      rect.setAttribute('rx', '8');
      rect.setAttribute('fill', n.isCrashed ? 'rgba(239, 68, 68, 0.28)' : '#111827');
      rect.setAttribute('stroke', n.isCrashed ? '#ef4444' : n.color);
      rect.setAttribute('stroke-width', n.isCrashed ? '2.5' : '1.8');
      if (n.isCrashed) {
        g.setAttribute('style', 'cursor:grab; filter: drop-shadow(0 0 20px #ef4444)');
      }

      // Left Icon Badge
      const iconBg = document.createElementNS(ns, 'rect');
      iconBg.setAttribute('x', '-77');
      iconBg.setAttribute('y', '-14');
      iconBg.setAttribute('width', '28');
      iconBg.setAttribute('height', '28');
      iconBg.setAttribute('rx', '5');
      iconBg.setAttribute('fill', n.isCrashed ? '#ef4444' : n.color);

      const iconDot = document.createElementNS(ns, 'circle');
      iconDot.setAttribute('cx', '-63');
      iconDot.setAttribute('cy', '0');
      iconDot.setAttribute('r', '4');
      iconDot.setAttribute('fill', n.isCrashed ? '#fee2e2' : '#ffffff');

      // Text Title
      const text = document.createElementNS(ns, 'text');
      text.setAttribute('x', '-42');
      text.setAttribute('y', '4');
      text.setAttribute('text-anchor', 'start');
      text.setAttribute('fill', n.isCrashed ? '#fca5a5' : '#ffffff');
      text.setAttribute('font-size', '9.5');
      text.setAttribute('font-weight', '700');
      text.setAttribute('font-family', "'JetBrains Mono', sans-serif");
      text.textContent = n.title.length > 20 ? n.title.substring(0, 18) + '…' : n.title;

      // Input Port Dot (Left Side)
      const inPort = document.createElementNS(ns, 'circle');
      inPort.setAttribute('cx', '-85');
      inPort.setAttribute('cy', '0');
      inPort.setAttribute('r', '3.5');
      inPort.setAttribute('fill', n.isCrashed ? '#ef4444' : '#38bdf8');
      inPort.setAttribute('stroke', '#0f172a');
      inPort.setAttribute('stroke-width', '1.5');

      // Output Port Dot (Right Side)
      const outPort = document.createElementNS(ns, 'circle');
      outPort.setAttribute('cx', '85');
      outPort.setAttribute('cy', '0');
      outPort.setAttribute('r', '3.5');
      outPort.setAttribute('fill', n.isCrashed ? '#ef4444' : '#10b981');
      outPort.setAttribute('stroke', '#0f172a');
      outPort.setAttribute('stroke-width', '1.5');

      g.appendChild(rect);
      g.appendChild(iconBg);
      g.appendChild(iconDot);
      g.appendChild(text);
      g.appendChild(inPort);
      g.appendChild(outPort);

      // Red Crash Badge on Top Right if node timed out / crashed
      if (n.isCrashed) {
        const badgeBg = document.createElementNS(ns, 'rect');
        badgeBg.setAttribute('x', '20');
        badgeBg.setAttribute('y', '-27');
        badgeBg.setAttribute('width', '62');
        badgeBg.setAttribute('height', '14');
        badgeBg.setAttribute('rx', '3');
        badgeBg.setAttribute('fill', '#ef4444');

        const badgeText = document.createElementNS(ns, 'text');
        badgeText.setAttribute('x', '51');
        badgeText.setAttribute('y', '-17');
        badgeText.setAttribute('text-anchor', 'middle');
        badgeText.setAttribute('fill', '#ffffff');
        badgeText.setAttribute('font-size', '8');
        badgeText.setAttribute('font-weight', '900');
        badgeText.setAttribute('font-family', "sans-serif");
        badgeText.textContent = '⚠️ 504 SLA';

        g.appendChild(badgeBg);
        g.appendChild(badgeText);
      }

      elNodes.appendChild(g);
    });

    if (this._initializedTransform) {
      this._applyTransform();
    } else {
      this._initializedTransform = true;
      this.resetZoom();
    }
  }
};

  window.AiLiveFlow = AiLiveFlow;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.AiLiveFlow = AiLiveFlow;
})();
