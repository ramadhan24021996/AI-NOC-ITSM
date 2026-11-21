/* o-global-topology.js
 * Organism: GlobalTopology — enterprise network topology visualization.
 * Extracted from data.service.js (lines 1746-2431) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: DataService (service), LogStreamer (organism), Notify (molecule)
 */
(function () {
  'use strict';

  const esc = (v) => (window._esc ? window._esc(v) : String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'));
  const jsAttr = (v) => (window._jsAttr ? window._jsAttr(v) : esc(JSON.stringify(v == null ? '' : String(v))));

var GlobalTopology = {
  nodes: [], edges: [], mode: 'fleet',
  _scale: 0.85, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
  _busBound: false,
  _docDragBound: false,
  _hasFittedOnce: false,

  init() {
    this._bindWrapEvents();
    this._bindBusEvents();
  },

  _bindWrapEvents() {
    const wrap = document.getElementById('gt-wrap');
    if (wrap && !wrap._gtEventsBound) {
      wrap._gtEventsBound = true;
      wrap.addEventListener('mousedown', e => {
        if (e.button !== 0) return;
        if (e.target.closest('button')) return;
        this._dragging = true;
        this._dragMoved = false;
        this._sx = e.clientX - this._tx;
        this._sy = e.clientY - this._ty;
        wrap.style.cursor = 'grabbing';
      });

      wrap.addEventListener('wheel', e => {
        if (!e.ctrlKey && !e.metaKey) return;
        e.preventDefault();
        const rect = wrap.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const prevScale = this._scale || 0.85;
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        const nextScale = Math.max(0.18, Math.min(3.0, +(prevScale + delta).toFixed(2)));
        if (nextScale !== prevScale) {
          const ratio = nextScale / prevScale;
          this._tx = mouseX - (mouseX - this._tx) * ratio;
          this._ty = mouseY - (mouseY - this._ty) * ratio;
          this._scale = nextScale;
          this._applyTransform();
          this._updateZoomLabel();
        }
      }, { passive: false });
    }

    if (!this._docDragBound) {
      this._docDragBound = true;
      document.addEventListener('mouseup', () => {
        if (this._dragging) {
          this._dragging = false;
          const w = document.getElementById('gt-wrap');
          if (w) w.style.cursor = 'grab';
        }
      });
      document.addEventListener('mousemove', e => {
        if (!this._dragging) return;
        this._dragMoved = true;
        this._tx = e.clientX - this._sx;
        this._ty = e.clientY - this._sy;
        this._applyTransform();
      });
    }
  },

  _bindBusEvents() {
    if (this._busBound) return;
    const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
    if (!bus || typeof bus.on !== 'function') return;
    this._busBound = true;

    bus.on('devices:loaded', (devices) => {
      this._updateDevices(devices);
    });
    bus.on('health:loaded', () => {
      if (this.mode === 'ai_lifecycle') {
        const svc = (window.Services && window.Services.Data) || window.DataService;
        const prevCount = this.nodes.length;
        this.buildEnterpriseAiTopology((svc && svc._devices) || [], prevCount > 0);
      }
    });
  },

  zoomIn() {
    const wrap = document.getElementById('gt-wrap');
    const cx = wrap ? wrap.clientWidth / 2 : 400;
    const cy = wrap ? wrap.clientHeight / 2 : 275;
    const prev = this._scale || 0.85;
    const next = Math.min(3.0, +(prev + 0.15).toFixed(2));
    const ratio = next / prev;
    this._tx = cx - (cx - this._tx) * ratio;
    this._ty = cy - (cy - this._ty) * ratio;
    this._scale = next;
    this._applyTransform();
    this._updateZoomLabel();
  },

  zoomOut() {
    const wrap = document.getElementById('gt-wrap');
    const cx = wrap ? wrap.clientWidth / 2 : 400;
    const cy = wrap ? wrap.clientHeight / 2 : 275;
    const prev = this._scale || 0.85;
    const next = Math.max(0.18, +(prev - 0.15).toFixed(2));
    const ratio = next / prev;
    this._tx = cx - (cx - this._tx) * ratio;
    this._ty = cy - (cy - this._ty) * ratio;
    this._scale = next;
    this._applyTransform();
    this._updateZoomLabel();
  },

  _fitToViewport() {
    const wrap = document.getElementById('gt-wrap');
    const w = (wrap && wrap.clientWidth > 100) ? wrap.clientWidth : 900;
    const h = (wrap && wrap.clientHeight > 100) ? wrap.clientHeight : 550;

    if (!this.nodes || this.nodes.length === 0) {
      this._scale = 0.85;
      this._tx = w / 2;
      this._ty = 80;
      this._applyTransform();
      this._updateZoomLabel();
      return;
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    this.nodes.forEach(n => {
      const nx = Number(n.x) || 0;
      const ny = Number(n.y) || 0;
      if (nx - 85 < minX) minX = nx - 85;
      if (nx + 85 > maxX) maxX = nx + 85;
      if (ny - 45 < minY) minY = ny - 45;
      if (ny + 70 > maxY) maxY = ny + 70;
    });

    const graphW = Math.max(200, maxX - minX);
    const graphH = Math.max(160, maxY - minY);
    const padX = 70;
    const padY = 80;
    const scaleX = (w - padX) / graphW;
    const scaleY = (h - padY) / graphH;
    const minScale = this.mode === 'ai_lifecycle' ? 0.34 : 0.45;
    const maxScale = this.mode === 'ai_lifecycle' ? 0.85 : 1.05;
    this._scale = +Math.max(minScale, Math.min(maxScale, Math.min(scaleX, scaleY))).toFixed(2);

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    this._tx = Math.round((w / 2) - (centerX * this._scale));
    this._ty = Math.round((h / 2) - (centerY * this._scale) - 8);
    this._applyTransform();
    this._updateZoomLabel();
  },

  resetZoom() {
    this._fitToViewport();
  },

  _updateZoomLabel() {
    const pct = `${Math.round(this._scale * 100)}%`;
    const lbl = document.getElementById('gt-zoom-lbl');
    if (lbl) lbl.textContent = pct;
    const lblHdr = document.getElementById('gt-zoom-lbl-hdr');
    if (lblHdr) lblHdr.textContent = pct;
  },

  _updateDevices(devices) {
    this._bindWrapEvents();
    const prevCount = this.nodes.length;
    if (this.mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(devices, prevCount > 0);
      return;
    }
    this.buildDynamicTopology(devices, prevCount > 0);
  },

  _applyTransform() {
    const vp = document.getElementById('gt-viewport');
    if (vp) vp.setAttribute('transform', `translate(${this._tx},${this._ty}) scale(${this._scale})`);
  },

  async load(devicesOverride) {
    this.init();
    const svc = (window.Services && window.Services.Data) || window.DataService;
    const isManualRefresh = (devicesOverride === undefined);

    let rawDevices = (Array.isArray(devicesOverride) && devicesOverride.length > 0)
      ? devicesOverride
      : (!isManualRefresh && svc && Array.isArray(svc._devices) && svc._devices.length > 0 ? svc._devices : []);

    if ((isManualRefresh || !rawDevices || rawDevices.length === 0) && svc && typeof svc.loadDevices === 'function') {
      try {
        rawDevices = await svc.loadDevices();
      } catch (e) {
        rawDevices = (svc && svc._devices) || [];
      }
    }

    const preserveCamera = this._hasFittedOnce && !isManualRefresh;
    if (this.mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(rawDevices, preserveCamera);
    } else {
      this.buildDynamicTopology(rawDevices, preserveCamera);
    }
    if (!preserveCamera) {
      this._fitToViewport();
      this._hasFittedOnce = true;
    }
  },

  switchMode(mode) {
    this.init();
    this.mode = mode;
    const btnFleet = document.getElementById('btn-topo-fleet');
    const btnAi = document.getElementById('btn-topo-ai');
    if (btnFleet && btnAi) {
      if (mode === 'ai_lifecycle') {
        btnFleet.className = 'btn btn-ghost btn-xs';
        btnAi.className = 'btn btn-primary btn-xs';
      } else {
        btnFleet.className = 'btn btn-primary btn-xs';
        btnAi.className = 'btn btn-ghost btn-xs';
      }
    }
    const svc = (window.Services && window.Services.Data) || window.DataService;
    const rawDevices = (svc && svc._devices) ? svc._devices : [];
    if (mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(rawDevices, false);
    } else {
      this.buildDynamicTopology(rawDevices, false);
    }
    this._fitToViewport();
  },

  buildEnterpriseAiTopology(devicesOverride, preserveCamera = false) {
    this.nodes = [];
    this.edges = [];

    const svc = (window.Services && window.Services.Data) || window.DataService;
    const rawDevices = (devicesOverride && devicesOverride.length > 0)
      ? devicesOverride
      : (svc && svc._devices ? svc._devices : []);

    const comps = (svc && svc._health && (svc._health.components || svc._health.checks)) || {};
    const compStatus = (key) => {
      const c = comps[key] || {};
      if (!c.status) return 'ONLINE';
      return c.status === 'OK' ? 'ONLINE' : 'OFFLINE';
    };
    const pgSt = compStatus('PostgreSQL');
    const ragSt = compStatus('RAG Engine');
    const aiSt = compStatus('AI API');
    const ingSt = compStatus('Ingestion');
    const dashSt = compStatus('Dashboard');

    // ── Layer 0: Client & Gateway ─────────────────────────────────────────
    this.nodes.push({ id: 'L0_User',     label: 'System Admin / NOC\n(User Layer)',         type: 'gateway', status: 'ONLINE', level: 0, navTarget: 'rbac' });
    this.nodes.push({ id: 'L0_Ext',      label: 'Chrome Extension\nOSI Assistant',          type: 'gateway', status: 'ONLINE', level: 0, navTarget: 'activity' });
    this.nodes.push({ id: 'L0_Telegram', label: 'Telegram Bot Gateway\n(P1 Alert Channel)', type: 'gateway', status: 'ONLINE', level: 0, navTarget: 'chat' });

    // ── Layer 1: Web Presentation ─────────────────────────────────────────
    this.nodes.push({ id: 'L1_UI',     label: 'Portal Web UI\n(Dark Glassmorphism)',    type: 'pc', status: dashSt, level: 1, navTarget: 'overview' });
    this.nodes.push({ id: 'L1_Dash',   label: 'Dashboard Utama\n(60 FPS Canvas)',       type: 'pc', status: dashSt, level: 1, navTarget: 'overview' });
    this.nodes.push({ id: 'L1_HITL',   label: 'HITL Approval Queue\n& Incident Triage', type: 'pc', status: dashSt, level: 1, navTarget: 'approval_queue' });
    this.nodes.push({ id: 'L1_Telem',  label: 'Telemetry Feed\n(Live Metrics)',          type: 'pc', status: dashSt, level: 1, navTarget: 'monitoring' });
    this.nodes.push({ id: 'L1_AICog',  label: 'AI Ops Cognition UI\n(RAG & Chat)',      type: 'pc', status: dashSt, level: 1, navTarget: 'ai' });
    this.nodes.push({ id: 'L1_RAG_UI', label: 'Knowledge Base\nRAG Search UI',           type: 'pc', status: dashSt, level: 1, navTarget: 'knowledge_center' });
    this.nodes.push({ id: 'L1_GovUI',  label: 'Model Config &\nGovernance UI',           type: 'pc', status: dashSt, level: 1, navTarget: 'gov' });

    // ── Layer 2: API Gateway ──────────────────────────────────────────────
    this.nodes.push({ id: 'L2_REST', label: 'HTTP REST API\nGateway (:8080)',       type: 'gateway', status: dashSt, level: 2, navTarget: 'server' });
    this.nodes.push({ id: 'L2_WS',   label: 'WebSocket Stream\n(60 FPS Downsample)', type: 'gateway', status: dashSt, level: 2, navTarget: 'logs' });

    // ── Layer 3: Go Core Backend ──────────────────────────────────────────
    this.nodes.push({ id: 'L3_GoCore', label: 'Go Server Core\n(Gin Framework)',        type: 'gateway', status: dashSt, level: 3, navTarget: 'runtime_monitor' });
    this.nodes.push({ id: 'L3_Relay',  label: 'Secure Encrypted Relay\n(Remote Control)', type: 'gateway', status: 'ONLINE', level: 3, navTarget: 'fleet' });
    this.nodes.push({ id: 'L3_Launch', label: 'Launcher Service\nManager',               type: 'gateway', status: 'ONLINE', level: 3, navTarget: 'models' });

    // ── Layer 4: Python AI Core Engines (Neural AI Microchip Icons) ──────
    this.nodes.push({ id: 'L4_PAI',              label: 'Python AI Supervisor\nCognition Engine',      type: 'ai_engine', status: aiSt,  level: 4, navTarget: 'ai' });
    this.nodes.push({ id: 'L4_Router',            label: 'Multi-LLM Router\n(Intent & Failover)',       type: 'ai_engine', status: aiSt,  level: 4, navTarget: 'models' });
    this.nodes.push({ id: 'L4_GOV',              label: 'Policy Engine\nHITL Safeguard',               type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'gov' });
    this.nodes.push({ id: 'L4_Observer',          label: 'Active Observer 24/7\n(Curiosity Engine)',    type: 'ai_engine', status: ingSt, level: 4, navTarget: 'agent_health' });
    this.nodes.push({ id: 'L4_RAG',              label: 'RAG 2.0 Vector Search\n& Reranker (<120ms)', type: 'ai_engine', status: ragSt, level: 4, navTarget: 'knowledge_center' });
    this.nodes.push({ id: 'L4_DAG',              label: 'Causal DAG Engine\n(Root Cause RCA)',         type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'unified_dag' });
    this.nodes.push({ id: 'L4_DBNEngine',         label: 'Dynamic Bayesian\nNetwork (DBN)',             type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'rca' });
    this.nodes.push({ id: 'L4_DecisionNetwork',   label: 'Decision Network\n(MEU / Utility)',           type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'ai_decision_logs' });
    this.nodes.push({ id: 'L4_ClosedLoop',        label: 'Closed-Loop\nDecision Orchestrator',          type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'pending_verification' });
    this.nodes.push({ id: 'L4_Planner',           label: 'AI Planning Engine\n(Plan A/B/C)',            type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'playbooks' });
    this.nodes.push({ id: 'L4_CriticAuditor',     label: 'Multi-Agent Consensus\n& Critic Auditor',    type: 'ai_engine', status: aiSt,  level: 4, navTarget: 'evidence' });
    this.nodes.push({ id: 'L4_Executor',          label: 'AI Execution Engine\n(Remediation)',          type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'exec_timeline' });
    this.nodes.push({ id: 'L4_Verifier',          label: 'Execution Verifier\n(Pre & Post Gate)',       type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'pending_verification' });
    this.nodes.push({ id: 'L4_FeedbackCollector', label: 'Feedback Collector\n(RLHF Loop)',             type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'training' });
    this.nodes.push({ id: 'L4_SOPRegistry',       label: 'SOP Registry\n(Zero-Hallucination)',          type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'sop' });
    this.nodes.push({ id: 'L4_GroundingVerifier', label: 'Dual-Stage Grounding\nVerifier (RAG 2.0)',   type: 'ai_engine', status: ragSt, level: 4, navTarget: 'evidence' });
    this.nodes.push({ id: 'L4_ExecSummary',       label: 'Executive Summary\nGenerator (ID Awam)',     type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'smart_stream' });
    this.nodes.push({ id: 'L4_CausalCards',       label: 'Causal Cards\nPlan A/B/C Visual',            type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'rca' });
    this.nodes.push({ id: 'L4_LLMs',              label: 'Cloud LLMs\nDeepSeek/Gemini/Groq',           type: 'ai_engine', status: aiSt,  level: 4, navTarget: 'models' });
    this.nodes.push({ id: 'L4_MemoryGraph',       label: 'AI Memory Graph\n(Causal Sequence)',         type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'kgraph' });
    this.nodes.push({ id: 'L4_KnowledgeAutoBuilder', label: 'Knowledge Auto-Builder\n(Closed-Loop RAG)', type: 'ai_engine', status: ragSt, level: 4, navTarget: 'learning_gate_logs' });
    this.nodes.push({ id: 'L4_ModelEvaluator',    label: 'Model Evaluation\nScorecard (5 Matrix)',     type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'gov' });
    this.nodes.push({ id: 'L4_DPOSynthesizer',    label: 'DPO Dataset Synthesizer\n(Auto-LoRA Pipeline)', type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'training' });
    this.nodes.push({ id: 'L4_EscalationChain',   label: '3-Level Human\nEscalation Chain',            type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'approval_queue' });
    this.nodes.push({ id: 'L4_Backpressure',      label: 'Anti-Surge\nBackpressure Control',           type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'runtime_monitor' });
    this.nodes.push({ id: 'L4_LocalRules',        label: 'Offline Random Forest\nFallback Engine',     type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'ai' });
    this.nodes.push({ id: 'L4_ArchiveFTS',        label: 'Cold Data FTS\nArchive Engine',              type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'storage' });
    this.nodes.push({ id: 'L4_Chaos',             label: 'Autonomous Chaos\nInjection Worker',         type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'gov' });
    this.nodes.push({ id: 'L4_SandboxPromoter',   label: 'AI Learning Sandbox\nPromotion Engine',       type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'learning_gate_policy' });
    this.nodes.push({ id: 'L4_SOPClarity',        label: 'SOP Clarity Synthesizer\n(Enterprise 5-Section)', type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'sop' });
    this.nodes.push({ id: 'L4_PrecisionAnalyzer', label: 'Precision Remediation &\n4-Factor RCA Analyzer', type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'rca' });

    // ── 12 Additional Backend Nodes (Verified Active Engines) ──────────────────
    this.nodes.push({ id: 'L4_DAG_Refresher',     label: 'Dynamic Causal Graph\nRefresher Service',       type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'kgraph' });
    this.nodes.push({ id: 'L4_DLQ_Processor',     label: 'Dead Letter Queue\nHybrid Processor',           type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'failed_actions' });
    this.nodes.push({ id: 'L4_DigitalTwin',       label: 'Digital Twin\nInfrastructure Simulator',        type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'learning_gate_policy' });
    this.nodes.push({ id: 'L4_ForecastEngine',    label: 'Telemetry Metric\nForecasting Engine',           type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'overview' });
    this.nodes.push({ id: 'L4_CircuitBreaker',    label: 'AI Resilience\nCircuit Breaker',                type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'security_policies' });
    this.nodes.push({ id: 'L4_ProactiveRemediator',label:'Proactive Self-Healing\nRemediator',             type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'recovery_mode_config' });
    this.nodes.push({ id: 'L4_KafkaConsumer',     label: 'Kafka Enterprise\nStream Consumer',             type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'nats_subjects' });
    this.nodes.push({ id: 'L4_KnowledgeGraph',    label: 'Knowledge Graph &\nEntity Linker',              type: 'ai_engine', status: ragSt,  level: 4, navTarget: 'kgraph' });
    this.nodes.push({ id: 'L3_SNMPCollector',     label: 'SNMP Network\nDiscovery Collector',             type: 'gateway',   status: ingSt,  level: 3, navTarget: 'evidence' });
    this.nodes.push({ id: 'L3_SyslogReceiver',    label: 'Enterprise Syslog\nAggregator (:514)',          type: 'gateway',   status: ingSt,  level: 3, navTarget: 'logs' });
    this.nodes.push({ id: 'L4_AIHealth',          label: 'AI Subsystem Health\n& Watchdog Daemon',         type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'agent_health' });
    this.nodes.push({ id: 'L4_N8NWebhook',        label: 'n8n Automation\nWebhook Listener',              type: 'ai_engine', status: 'ONLINE', level: 4, navTarget: 'playbooks' });

    // ── Layer 5: Broker, Persistence & Monitoring ─────────────────────────
    this.nodes.push({ id: 'L5_NATS',        label: 'NATS JetStream HA\n(2-Node Active-Active)',  type: 'gateway',  status: 'ONLINE', level: 5, navTarget: 'nats_subjects' });
    this.nodes.push({ id: 'L5_Netdata',     label: 'Netdata Master Collector\n(:19999 High-Freq)', type: 'gateway',  status: ingSt,  level: 5, navTarget: 'monitoring' });
    this.nodes.push({ id: 'L5_SQL_Inc',     label: 'PostgreSQL\nincident_analysis DB',            type: 'database', status: pgSt,   level: 5, navTarget: 'storage' });
    this.nodes.push({ id: 'L5_SQL_SO',      label: 'sprint_o.db\n(State Machine DB)',              type: 'database', status: pgSt,   level: 5, navTarget: 'storage' });
    this.nodes.push({ id: 'L5_SQL_RAG',     label: 'pgvector RAG Store\n(PostgreSQL :5432)',       type: 'database', status: pgSt,   level: 5, navTarget: 'storage' });
    this.nodes.push({ id: 'L5_SQL_Cog',     label: 'cognitive_memory.db\n(SQLite WAL)',            type: 'database', status: 'ONLINE', level: 5, navTarget: 'storage' });
    this.nodes.push({ id: 'L5_VectorDB',    label: 'Vector Store DB\n(pgvector RAG Store)',        type: 'database', status: ragSt,  level: 5, navTarget: 'knowledge_center' });
    this.nodes.push({ id: 'L5_DPOStore',    label: 'DPO Dataset Store\n(dpo_datasets/ JSONL)',     type: 'database', status: 'ONLINE', level: 5, navTarget: 'training' });
    this.nodes.push({ id: 'L5_FTP',         label: 'FTP / Local Artifact\nShare Server',           type: 'database', status: 'ONLINE', level: 5, navTarget: 'storage' });
    this.nodes.push({ id: 'L5_OfflineCache',label: 'Agent Offline Cache\n(Local Policy Store)',    type: 'database', status: 'ONLINE', level: 5, navTarget: 'fleet_config' });

    // ── Layer 6: Infrastructure & Orchestration ───────────────────────────
    this.nodes.push({ id: 'L6_Docker',    label: 'Docker Microservices\nEngine (Runtime)',       type: 'gateway', status: 'ONLINE', level: 6, navTarget: 'runtime_monitor' });
    this.nodes.push({ id: 'L6_N8N',       label: 'n8n Workflow\nAutomation Engine',              type: 'gateway', status: 'ONLINE', level: 6, navTarget: 'playbooks' });
    this.nodes.push({ id: 'L6_CasaOS',    label: 'pgAdmin / CasaOS\nDB Management (:5050)',      type: 'gateway', status: pgSt,   level: 6, navTarget: 'storage' });
    this.nodes.push({ id: 'L6_EMTrainer', label: 'MLOps Replay\nGatekeeper (EM Trainer)',        type: 'ai_engine', status: 'ONLINE', level: 6, navTarget: 'training' });
    this.nodes.push({ id: 'L6_SCA',       label: 'SCA Security &\nSBOM Scanner',                 type: 'ai_engine', status: 'ONLINE', level: 6, navTarget: 'security_policies' });

    // ── Layer 7: Endpoint Agents (Distributed Real Devices) ──────────────
    const firstAgentEdges = [];
    if (rawDevices && rawDevices.length > 0) {
      rawDevices.forEach((d, idx) => {
        const devName = d.name || d.pc_name || `Agent-Device-${idx+1}`;
        const labelName = devName.length > 22 ? devName.substring(0, 20) + '..' : devName;

        let devIp = d.ip || '';
        if (!devIp && d.hardware_info) {
          try {
            const hw = typeof d.hardware_info === 'string' ? JSON.parse(d.hardware_info) : d.hardware_info;
            devIp = hw.ip || hw.networkAdvanced?.ip || '';
          } catch(e) {}
        }
        if (!devIp) devIp = d.site_gateway || '—';

        const status = (d.status === 'ONLINE' || d.online) ? 'ONLINE' : (d.status || 'OFFLINE');
        const isPrn = devName.toLowerCase().includes('print') || devName.toLowerCase().includes('prn') || (d.metadata && d.metadata.type === 'printer');
        const agentNodeId = devName;

        this.nodes.push({
          id: agentNodeId,
          label: `${labelName}\n(${devIp})`,
          type: isPrn ? 'printer' : 'pc',
          status: status,
          level: 7,
          isDevice: true
        });

        this.edges.push({ source: agentNodeId, target: 'L2_REST' });
        this.edges.push({ source: agentNodeId, target: 'L7_Idempotency' });
        this.edges.push({ source: 'L3_Relay', target: agentNodeId });
        this.edges.push({ source: 'L5_NATS', target: agentNodeId });
        firstAgentEdges.push(agentNodeId);
      });
    } else {
      this.nodes.push({ id: 'L7_WinAgent',   label: 'Windows Agent Service\n(Go - v2.1.1)',    type: 'pc', status: 'ONLINE', level: 7 });
      this.nodes.push({ id: 'L7_LinuxAgent', label: 'Linux Agent Service\n(Go DEB Package)',  type: 'pc', status: 'ONLINE', level: 7 });
      this.edges.push({ source: 'L7_WinAgent', target: 'L2_REST' });
      this.edges.push({ source: 'L7_LinuxAgent', target: 'L2_REST' });
      this.edges.push({ source: 'L5_NATS', target: 'L7_WinAgent' });
      this.edges.push({ source: 'L5_NATS', target: 'L7_LinuxAgent' });
      firstAgentEdges.push('L7_WinAgent', 'L7_LinuxAgent');
    }
    this.nodes.push({ id: 'L7_Idempotency', label: 'Agent Idempotency\nKey Guard',            type: 'pc', status: 'ONLINE', level: 7 });

    // ── Layer 8: Enterprise Integrations ─────────────────────────────────
    this.nodes.push({ id: 'L8_LDAP',   label: 'LDAP / Active Directory\n(Auth Provider)',     type: 'gateway', status: 'ONLINE',  level: 8 });
    this.nodes.push({ id: 'L8_Kafka',  label: 'Apache Kafka\nEnterprise Event Bus',           type: 'gateway', status: 'ONLINE',  level: 8 });
    this.nodes.push({ id: 'L8_DNS',    label: 'Enterprise DNS\nDHCP Server',                  type: 'gateway', status: 'ONLINE',  level: 8 });
    this.nodes.push({ id: 'L8_K8S',    label: 'Kubernetes\nMulti-Site Cluster',               type: 'gateway', status: 'ONLINE',  level: 8 });
    this.nodes.push({ id: 'L8_SMTP',   label: 'Email Gateway\n(P0 Alert Mailer)',              type: 'gateway', status: 'ONLINE',  level: 8 });
    this.nodes.push({ id: 'L8_Syslog', label: 'Syslog RFC-5424\nLog Receiver',                type: 'gateway', status: 'ONLINE',  level: 8 });

    // Connect DNS to first agent node
    if (firstAgentEdges.length > 0) {
      this.edges.push({ source: 'L8_DNS', target: firstAgentEdges[0] });
    }

    // ── Layer 9: Executive Analytics & Operational Portals ─────────────────
    this.nodes.push({ id: 'L9_Overview',     label: 'Executive Overview\n& KPI Analytics',       type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_FleetMon',     label: 'Fleet & Real-Time\nDiagnostics Hub',        type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_IncidentRCA',  label: 'Incident Triage &\nCausal RCA Portal',       type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_GovSafeguard', label: 'HITL Approval &\nGovernance Safeguards',    type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_AICognition',  label: 'AI Cognition &\nRAG Knowledge Hub',        type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_LogStream',    label: 'Smart Stream &\nLog Inspection Center',     type: 'pc', status: 'ONLINE', level: 9 });
    this.nodes.push({ id: 'L9_NocRelay',     label: 'NOC Operator Chat\n& Telegram Relay',       type: 'pc', status: 'ONLINE', level: 9 });

    // ── EDGES: Complete Data Flow (167 connections) ───────────────────────

    // L0 → L1: Users access portal
    this.edges.push({ source: 'L0_User',     target: 'L1_UI' });
    this.edges.push({ source: 'L0_User',     target: 'L1_HITL' });
    this.edges.push({ source: 'L0_User',     target: 'L1_Dash' });
    this.edges.push({ source: 'L0_Ext',      target: 'L2_REST' });

    // L1 → L2: All UI panels route through API Gateway
    this.edges.push({ source: 'L1_UI',     target: 'L2_REST' });
    this.edges.push({ source: 'L1_UI',     target: 'L2_WS' });
    this.edges.push({ source: 'L1_Dash',   target: 'L2_WS' });
    this.edges.push({ source: 'L1_HITL',   target: 'L2_REST' });
    this.edges.push({ source: 'L1_Telem',  target: 'L2_WS' });
    this.edges.push({ source: 'L1_AICog',  target: 'L2_REST' });
    this.edges.push({ source: 'L1_RAG_UI', target: 'L2_REST' });
    this.edges.push({ source: 'L1_GovUI',  target: 'L2_REST' });

    // L2 → L3: Gateway to Go Core
    this.edges.push({ source: 'L2_REST', target: 'L3_GoCore' });
    this.edges.push({ source: 'L2_WS',   target: 'L3_GoCore' });

    // L3: Go Core internal routing
    this.edges.push({ source: 'L3_GoCore', target: 'L3_Relay' });
    this.edges.push({ source: 'L3_GoCore', target: 'L3_Launch' });

    // L3 → L4: Go Core triggers AI engines
    this.edges.push({ source: 'L3_GoCore', target: 'L4_PAI' });
    this.edges.push({ source: 'L3_GoCore', target: 'L4_Observer' });
    this.edges.push({ source: 'L3_GoCore', target: 'L4_Backpressure' });

    // L3 → L5: Go Core direct storage
    this.edges.push({ source: 'L3_GoCore', target: 'L5_NATS' });
    this.edges.push({ source: 'L3_GoCore', target: 'L5_Netdata' });
    this.edges.push({ source: 'L3_GoCore', target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L3_GoCore', target: 'L5_SQL_Cog' });

    // L3 → L0: Alerts
    this.edges.push({ source: 'L3_GoCore', target: 'L0_Telegram' });

    // L4 AI Supervisor routing
    this.edges.push({ source: 'L4_PAI', target: 'L4_Router' });
    this.edges.push({ source: 'L4_PAI', target: 'L4_GOV' });
    this.edges.push({ source: 'L4_PAI', target: 'L4_Observer' });
    this.edges.push({ source: 'L4_PAI', target: 'L4_Backpressure' });
    this.edges.push({ source: 'L4_PAI', target: 'L5_SQL_Inc' });

    // L4 LLM Router
    this.edges.push({ source: 'L4_Router', target: 'L4_LLMs' });
    this.edges.push({ source: 'L4_Router', target: 'L4_ModelEvaluator' });
    this.edges.push({ source: 'L4_Router', target: 'L4_DPOSynthesizer' });
    this.edges.push({ source: 'L4_ModelEvaluator', target: 'L4_LLMs' });

    // L4 Probabilistic AI: Observer → DBN → ClosedLoop → DAG
    this.edges.push({ source: 'L4_Observer',       target: 'L4_DBNEngine' });
    this.edges.push({ source: 'L4_Observer',       target: 'L4_DAG' });
    this.edges.push({ source: 'L4_DBNEngine',      target: 'L4_ClosedLoop' });
    this.edges.push({ source: 'L4_ClosedLoop',     target: 'L4_DecisionNetwork' });
    this.edges.push({ source: 'L4_ClosedLoop',     target: 'L4_DAG' });
    this.edges.push({ source: 'L4_DecisionNetwork',target: 'L4_Planner' });
    this.edges.push({ source: 'L4_DBNEngine',      target: 'L5_SQL_Inc' });

    // L4 RAG & Grounding chain
    this.edges.push({ source: 'L4_DAG',              target: 'L4_RAG' });
    this.edges.push({ source: 'L4_RAG',              target: 'L4_SOPRegistry' });
    this.edges.push({ source: 'L4_SOPRegistry',      target: 'L4_GroundingVerifier' });
    this.edges.push({ source: 'L4_GroundingVerifier',target: 'L4_Planner' });
    this.edges.push({ source: 'L4_RAG',              target: 'L4_Router' });
    this.edges.push({ source: 'L4_RAG',              target: 'L5_VectorDB' });
    this.edges.push({ source: 'L4_RAG',              target: 'L5_SQL_RAG' });

    // L4 Sandbox & Precision Learning Pipeline Flow
    this.edges.push({ source: 'L4_DPOSynthesizer',   target: 'L4_SOPClarity' });
    this.edges.push({ source: 'L4_SOPClarity',        target: 'L4_SandboxPromoter' });
    this.edges.push({ source: 'L4_SandboxPromoter',   target: 'L5_SQL_RAG' });
    this.edges.push({ source: 'L4_SandboxPromoter',   target: 'L4_GOV' });
    this.edges.push({ source: 'L4_PrecisionAnalyzer', target: 'L4_DAG' });
    this.edges.push({ source: 'L4_PrecisionAnalyzer', target: 'L4_Planner' });
    this.edges.push({ source: 'L4_PrecisionAnalyzer', target: 'L1_AICog' });

    // Data Flow Connections for 12 Additional Backend Nodes:
    this.edges.push({ source: 'L4_DAG',              target: 'L4_DAG_Refresher' });
    this.edges.push({ source: 'L4_DAG_Refresher',    target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_Executor',          target: 'L4_DLQ_Processor' });
    this.edges.push({ source: 'L4_DLQ_Processor',    target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_Planner',          target: 'L4_DigitalTwin' });
    this.edges.push({ source: 'L4_DigitalTwin',      target: 'L4_Verifier' });
    this.edges.push({ source: 'L4_Observer',          target: 'L4_ForecastEngine' });
    this.edges.push({ source: 'L4_ForecastEngine',   target: 'L4_ProactiveRemediator' });
    this.edges.push({ source: 'L4_ProactiveRemediator',target: 'L4_GOV' });
    this.edges.push({ source: 'L4_PAI',              target: 'L4_CircuitBreaker' });
    this.edges.push({ source: 'L4_CircuitBreaker',   target: 'L5_NATS' });
    this.edges.push({ source: 'L4_KafkaConsumer',    target: 'L3_GoCore' });
    this.edges.push({ source: 'L4_KafkaConsumer',    target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_RAG',              target: 'L4_KnowledgeGraph' });
    this.edges.push({ source: 'L4_KnowledgeGraph',   target: 'L5_SQL_RAG' });
    this.edges.push({ source: 'L3_SNMPCollector',    target: 'L3_GoCore' });
    this.edges.push({ source: 'L3_SNMPCollector',    target: 'L5_Netdata' });
    this.edges.push({ source: 'L3_SyslogReceiver',   target: 'L3_GoCore' });
    this.edges.push({ source: 'L3_SyslogReceiver',   target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_AIHealth',         target: 'L4_PAI' });
    this.edges.push({ source: 'L4_AIHealth',         target: 'L1_Dash' });
    this.edges.push({ source: 'L6_N8N',              target: 'L4_N8NWebhook' });
    this.edges.push({ source: 'L4_N8NWebhook',       target: 'L3_GoCore' });

    // L4 Planning & Consensus
    this.edges.push({ source: 'L4_GOV',          target: 'L4_Planner' });
    this.edges.push({ source: 'L4_GOV',          target: 'L4_EscalationChain' });
    this.edges.push({ source: 'L4_Planner',      target: 'L4_CriticAuditor' });
    this.edges.push({ source: 'L4_Planner',      target: 'L4_ExecSummary' });
    this.edges.push({ source: 'L4_Planner',      target: 'L4_CausalCards' });
    this.edges.push({ source: 'L4_Planner',      target: 'L5_SQL_SO' });
    this.edges.push({ source: 'L4_CriticAuditor',target: 'L4_Executor' });
    this.edges.push({ source: 'L4_CriticAuditor',target: 'L1_HITL' });

    // L4 Execution → Verification → RLHF feedback
    this.edges.push({ source: 'L4_Executor',          target: 'L4_Verifier' });
    this.edges.push({ source: 'L4_Executor',          target: 'L5_NATS' });
    this.edges.push({ source: 'L4_Executor',          target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_Verifier',          target: 'L4_FeedbackCollector' });
    this.edges.push({ source: 'L4_Verifier',          target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L4_FeedbackCollector', target: 'L4_DBNEngine' });
    this.edges.push({ source: 'L4_FeedbackCollector', target: 'L4_DPOSynthesizer' });
    this.edges.push({ source: 'L4_FeedbackCollector', target: 'L0_Telegram' });

    // L4 Memory & Knowledge auto-build
    this.edges.push({ source: 'L4_DAG',              target: 'L4_MemoryGraph' });
    this.edges.push({ source: 'L4_MemoryGraph',      target: 'L5_SQL_Cog' });
    this.edges.push({ source: 'L4_MemoryGraph',      target: 'L4_RAG' });
    this.edges.push({ source: 'L4_LLMs',             target: 'L4_KnowledgeAutoBuilder' });
    this.edges.push({ source: 'L4_KnowledgeAutoBuilder', target: 'L5_VectorDB' });

    // L4 DPO & Fine-tuning loop
    this.edges.push({ source: 'L4_DPOSynthesizer', target: 'L5_DPOStore' });
    this.edges.push({ source: 'L4_DPOSynthesizer', target: 'L4_LLMs' });

    // L4 Offline fallback & archiving
    this.edges.push({ source: 'L4_LocalRules', target: 'L4_Planner' });
    this.edges.push({ source: 'L4_ArchiveFTS', target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L5_SQL_Inc',    target: 'L4_ArchiveFTS' });

    // L4 Escalation → external channels
    this.edges.push({ source: 'L4_EscalationChain', target: 'L8_SMTP' });
    this.edges.push({ source: 'L4_EscalationChain', target: 'L0_Telegram' });

    // L4 Chaos Injection
    this.edges.push({ source: 'L4_Chaos', target: 'L5_NATS' });
    this.edges.push({ source: 'L4_Chaos', target: 'L4_Verifier' });

    // ExecSummary & CausalCards → back to UI
    this.edges.push({ source: 'L4_ExecSummary',  target: 'L1_AICog' });
    this.edges.push({ source: 'L4_CausalCards',  target: 'L1_AICog' });

    // L5 Storage cross-links
    this.edges.push({ source: 'L5_VectorDB',  target: 'L5_SQL_RAG' });
    this.edges.push({ source: 'L5_Netdata',   target: 'L3_GoCore' });

    // L6 Infrastructure orchestration
    this.edges.push({ source: 'L6_Docker',    target: 'L5_NATS' });
    this.edges.push({ source: 'L6_Docker',    target: 'L3_GoCore' });
    this.edges.push({ source: 'L6_N8N',       target: 'L3_GoCore' });
    this.edges.push({ source: 'L6_N8N',       target: 'L5_NATS' });
    this.edges.push({ source: 'L6_EMTrainer', target: 'L4_DBNEngine' });
    this.edges.push({ source: 'L6_EMTrainer', target: 'L4_ModelEvaluator' });
    this.edges.push({ source: 'L6_SCA',       target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L6_CasaOS',    target: 'L5_SQL_Inc' });
    this.edges.push({ source: 'L6_CasaOS',    target: 'L5_SQL_RAG' });

    // L8 Enterprise Integrations
    this.edges.push({ source: 'L8_LDAP',   target: 'L2_REST' });
    this.edges.push({ source: 'L8_Kafka',  target: 'L5_NATS' });
    this.edges.push({ source: 'L8_Syslog', target: 'L3_GoCore' });

    // L9 Executive Analytics Connections
    this.edges.push({ source: 'L1_UI',        target: 'L9_Overview' });
    this.edges.push({ source: 'L2_WS',        target: 'L9_FleetMon' });
    this.edges.push({ source: 'L4_DAG',       target: 'L9_IncidentRCA' });
    this.edges.push({ source: 'L4_GOV',       target: 'L9_GovSafeguard' });
    this.edges.push({ source: 'L4_RAG',       target: 'L9_AICognition' });
    this.edges.push({ source: 'L3_GoCore',    target: 'L9_LogStream' });
    this.edges.push({ source: 'L0_Telegram',  target: 'L9_NocRelay' });

    // ── Layout: Multi-Row Compact Wrapping per Layer ──────────────────────
    let levelGroups = {};
    this.nodes.forEach(n => {
      levelGroups[n.level] = levelGroups[n.level] || [];
      levelGroups[n.level].push(n);
    });

    const maxPerRow = 11;
    const subRowGap = 105;
    const levelGap = 125;
    let currentY = 0;

    Object.keys(levelGroups).sort((a, b) => Number(a) - Number(b)).forEach(lvl => {
      const l = parseInt(lvl, 10);
      const nodesInLevel = levelGroups[l];
      const count = nodesInLevel.length;
      if (count === 0) return;

      const numRows = Math.ceil(count / maxPerRow);
      for (let r = 0; r < numRows; r++) {
        const slice = nodesInLevel.slice(r * maxPerRow, (r + 1) * maxPerRow);
        const rowCount = slice.length;
        const xSpacing = rowCount > 6 ? 165 : 210;
        const totalWidth = (rowCount - 1) * xSpacing;
        const startX = -(totalWidth / 2);
        const rowY = currentY + (r * subRowGap);

        slice.forEach((n, idx) => {
          n.x = startX + (idx * xSpacing);
          n.y = rowY;
        });
      }
      currentY += ((numRows - 1) * subRowGap) + levelGap;
    });

    this._render();
    this._updateDOM();
    if (!preserveCamera) {
      this._fitToViewport();
    }
  },

  buildDynamicTopology(devices, preserveCamera = false) {
    this.nodes = [];
    this.edges = [];

    const svc = (window.Services && window.Services.Data) || window.DataService;
    const sitesRegistry = (svc && Array.isArray(svc._sites)) ? svc._sites : [];

    // 0: Server Root
    let serverIP = window.location.hostname || '127.0.0.1';
    this.nodes.push({ id: 'Server', label: 'Core Server\n(' + serverIP + ')', type: 'gateway', status: 'ONLINE', level: 0, navTarget: 'server' });

    if (!devices || devices.length === 0) {
      this._render();
      this._updateDOM();
      if (!preserveCamera) this._fitToViewport();
      return;
    }

    // 1: Group by location/site to form site routers with real gateway IPs
    let locations = {};
    devices.forEach(d => {
      let loc = d.location || d.site_name || d.site_id || d.site || 'Main Site';
      if (!locations[loc]) locations[loc] = [];
      locations[loc].push(d);
    });

    let locKeys = Object.keys(locations);
    locKeys.forEach(loc => {
      const siteDevs = locations[loc];
      let routerId = 'RTR-' + loc.replace(/[^a-zA-Z0-9]/g, '_');
      let shortLoc = loc.replace(/_/g, ' ');
      if (shortLoc.length > 18) shortLoc = shortLoc.substring(0, 16) + '..';

      // Resolve real gateway IP from site registry, device site_gateway/hardware_info, or device subnet .1
      let routerIp = '';
      const matchedSite = sitesRegistry.find(s => {
        if (!s || typeof s !== 'object') return false;
        const sid = String(s.site_id || '').toLowerCase();
        const sname = String(s.site_name || '').toLowerCase();
        const locLower = loc.toLowerCase();
        return (sid && sid === locLower) || (sname && sname === locLower);
      });
      if (matchedSite && (matchedSite.gateway || matchedSite.ip || matchedSite.gw)) {
        routerIp = matchedSite.gateway || matchedSite.ip || matchedSite.gw;
      }
      if (!routerIp) {
        for (const d of siteDevs) {
          if (d.site_gateway) { routerIp = d.site_gateway; break; }
          if (d.hardware_info) {
            try {
              const hw = typeof d.hardware_info === 'string' ? JSON.parse(d.hardware_info) : d.hardware_info;
              if (hw && (hw.gateway || hw.default_gateway || (hw.network && hw.network.gateway))) {
                routerIp = hw.gateway || hw.default_gateway || hw.network.gateway;
                break;
              }
            } catch (e) {}
          }
        }
      }
      if (!routerIp) {
        const firstWithIp = siteDevs.find(d => d.ip && /^\d+\.\d+\.\d+\.\d+$/.test(d.ip));
        if (firstWithIp) {
          const parts = firstWithIp.ip.split('.');
          routerIp = `${parts[0]}.${parts[1]}.${parts[2]}.1`;
        } else {
          routerIp = 'Gateway';
        }
      }

      const anyOnline = siteDevs.some(d => d.status === 'ONLINE' || d.online);
      const rtrStatus = anyOnline ? 'ONLINE' : 'OFFLINE';

      this.nodes.push({ id: routerId, label: 'RTR ' + shortLoc + '\n(' + routerIp + ')', type: 'gateway', status: rtrStatus, level: 1, navTarget: 'fleet' });
      this.edges.push({ source: 'Server', target: routerId });

      siteDevs.forEach(d => {
        let name = d.name || d.pc_name || 'Unknown Device';
        let labelName = name.length > 25 ? name.substring(0, 23) + '..' : name;

        let devIp = d.ip || '';
        if (!devIp && d.hardware_info) {
          try {
            let hw = typeof d.hardware_info === 'string' ? JSON.parse(d.hardware_info) : d.hardware_info;
            devIp = hw.ip || hw.networkAdvanced?.ip || '';
          } catch (e) {}
        }
        if (!devIp) devIp = d.site_gateway || '—';

        let status = (d.status === 'ONLINE' || d.online) ? 'ONLINE' : (d.status || 'OFFLINE');
        let dType = 'pc';
        if (name.toLowerCase().includes('print') || name.toLowerCase().includes('prn') || (d.metadata && d.metadata.type === 'printer')) {
          dType = 'printer';
        }

        this.nodes.push({ id: name, label: labelName + '\n(' + devIp + ')', type: dType, status: status, level: 2, isDevice: true });
        this.edges.push({ source: routerId, target: name });
      });
    });

    // Layout algorithm
    let levelGroups = { 0: [], 1: [], 2: [] };
    this.nodes.forEach(n => {
      if (levelGroups[n.level]) levelGroups[n.level].push(n);
    });

    let yStep = 155;
    Object.keys(levelGroups).forEach(lvl => {
      let l = parseInt(lvl, 10);
      let y = l * yStep;
      let nodesInLevel = levelGroups[l];
      let count = nodesInLevel.length;
      if (count === 0) return;

      let xSpacing = l === 2 ? 150 : (l === 1 ? 260 : 0);
      let totalWidth = (count - 1) * xSpacing;
      let startX = -(totalWidth / 2);

      nodesInLevel.forEach((n, idx) => {
        n.x = startX + (idx * xSpacing);
        n.y = y;

        // Vertical staggering for leaf nodes to save horizontal space and prevent overlap
        if (l === 2 && idx % 2 !== 0) {
          n.y += 65;
        }
      });
    });

    this._render();
    this._updateDOM();
    if (!preserveCamera) {
      this._fitToViewport();
    }
  },

  handleNodeClick(nodeId) {
    if (this._dragMoved) return;
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (node.isDevice && typeof showDeviceDiagnosticsDetail === 'function') {
      showDeviceDiagnosticsDetail(node.id);
      return;
    }
    if (node.navTarget && typeof Nav !== 'undefined' && typeof Nav.go === 'function') {
      const cleanLabel = String(node.label || node.id).replace(/\n/g, ' ');
      if (typeof Notify !== 'undefined' && Notify.toast) {
        Notify.toast('🧭 Topology Node', `${cleanLabel} (${node.status || 'ONLINE'}) — Membuka panel ${node.navTarget}`, 'info', 2500);
      }
      Nav.go(node.navTarget, document.querySelector(`[data-panel="${node.navTarget}"]`));
    }
  },

  _render() {
    const elNodes = document.getElementById('gt-nodes');
    const elEdges = document.getElementById('gt-edges');
    if (!elNodes || !elEdges) return;

    // Draw edges with right angles to simulate Visio lines perfectly and add animation
    elEdges.innerHTML = this.edges.map((e, i) => {
      let n1 = this.nodes.find(n => n.id === e.source);
      let n2 = this.nodes.find(n => n.id === e.target);
      if (!n1 || !n2) return '';
      let midY = n1.y + (n2.y - n1.y) / 2;
      let path = `M ${n1.x} ${n1.y} L ${n1.x} ${midY} L ${n2.x} ${midY} L ${n2.x} ${n2.y}`;
      const isOfflineTarget = n2.status && n2.status !== 'ONLINE';
      const strokeBase = isOfflineTarget ? 'rgba(239, 68, 68, 0.35)' : 'rgba(14, 165, 233, 0.38)';
      const strokeFlow = isOfflineTarget ? '#ef4444' : '#38bdf8';
      return `
        <path id="gte-${i}" d="${path}" fill="none" stroke="${strokeBase}" stroke-width="2.5" filter="url(#gt-glow-line)" />
        <path d="${path}" fill="none" stroke="${strokeFlow}" stroke-width="1.8" stroke-dasharray="8 12">
           <animate attributeName="stroke-dashoffset" values="20;0" dur="0.8s" repeatCount="indefinite" />
        </path>
      `;
    }).join('');

    elNodes.innerHTML = this.nodes.map((n) => {
      const isOnline = !n.status || n.status === 'ONLINE';
      const statusColor = isOnline ? '#10b981' : '#ef4444';
      const color = n.type === 'gateway' ? (isOnline ? '#0ea5e9' : '#ef4444')
                  : n.type === 'ai_engine' ? (isOnline ? '#a855f7' : '#ef4444')
                  : n.type === 'database' ? (isOnline ? '#06b6d4' : '#ef4444')
                  : statusColor;
      const filter = 'filter="url(#gt-glow)"';

      let svgGraphic = '';
      if (n.level === 0) { // Core Server / User Gateway
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <rect x="10" y="5" width="40" height="50" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="2" ${filter}/>
            <rect x="14" y="12" width="32" height="8" rx="1" fill="#1e293b"/>
            <circle cx="20" cy="16" r="1.5" fill="#10b981"/>
            <circle cx="25" cy="16" r="1.5" fill="#10b981"/>
            <rect x="14" y="26" width="32" height="8" rx="1" fill="#1e293b"/>
            <circle cx="20" cy="30" r="1.5" fill="#10b981"/>
            <circle cx="25" cy="30" r="1.5" fill="#0ea5e9"/>
            <rect x="14" y="40" width="32" height="8" rx="1" fill="#1e293b"/>
            <circle cx="20" cy="44" r="1.5" fill="#10b981"/>
            <circle cx="25" cy="44" r="1.5" fill="#f59e0b"/>
          </g>
        `;
      } else if (n.type === 'gateway') { // Router / Gateway
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <line x1="15" y1="30" x2="10" y2="10" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
            <line x1="45" y1="30" x2="50" y2="10" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
            <rect x="8" y="25" width="44" height="20" rx="4" fill="#1e293b" stroke="${color}" stroke-width="2" ${filter}/>
            <rect x="8" y="33" width="44" height="12" rx="0" fill="#0f172a"/>
            <circle cx="16" cy="39" r="2" fill="${statusColor}"/>
            <circle cx="24" cy="39" r="2" fill="${statusColor}"/>
            <circle cx="32" cy="39" r="2" fill="#0ea5e9"/>
            <circle cx="40" cy="39" r="2" fill="${statusColor}"/>
          </g>
        `;
      } else if (n.type === 'ai_engine') { // Neural AI Microchip Core
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <line x1="18" y1="3" x2="18" y2="10" stroke="#a855f7" stroke-width="2"/>
            <line x1="30" y1="3" x2="30" y2="10" stroke="#06b6d4" stroke-width="2"/>
            <line x1="42" y1="3" x2="42" y2="10" stroke="#a855f7" stroke-width="2"/>
            <line x1="18" y1="46" x2="18" y2="53" stroke="#a855f7" stroke-width="2"/>
            <line x1="30" y1="46" x2="30" y2="53" stroke="#06b6d4" stroke-width="2"/>
            <line x1="42" y1="46" x2="42" y2="53" stroke="#a855f7" stroke-width="2"/>
            <line x1="3" y1="18" x2="10" y2="18" stroke="#a855f7" stroke-width="2"/>
            <line x1="3" y1="28" x2="10" y2="28" stroke="#06b6d4" stroke-width="2"/>
            <line x1="3" y1="38" x2="10" y2="38" stroke="#a855f7" stroke-width="2"/>
            <line x1="50" y1="18" x2="57" y2="18" stroke="#a855f7" stroke-width="2"/>
            <line x1="50" y1="28" x2="57" y2="28" stroke="#06b6d4" stroke-width="2"/>
            <line x1="50" y1="38" x2="57" y2="38" stroke="#a855f7" stroke-width="2"/>
            <rect x="10" y="10" width="40" height="36" rx="6" fill="#0f172a" stroke="${color}" stroke-width="2" ${filter}/>
            <rect x="17" y="17" width="26" height="22" rx="3" fill="#1e1b4b" stroke="#06b6d4" stroke-width="1.2"/>
            <circle cx="30" cy="28" r="5" fill="${statusColor}"/>
          </g>
        `;
      } else if (n.type === 'database') { // Database Storage Cylinder
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <path d="M 12 14 C 12 8, 48 8, 48 14 L 48 42 C 48 48, 12 48, 12 42 Z" fill="#0f172a" stroke="${color}" stroke-width="2" ${filter}/>
            <ellipse cx="30" cy="14" rx="18" ry="5" fill="#1e293b" stroke="${color}" stroke-width="1.8"/>
            <path d="M 12 24 C 12 29, 48 29, 48 24" fill="none" stroke="${color}" stroke-width="1.4"/>
            <path d="M 12 33 C 12 38, 48 38, 48 33" fill="none" stroke="${color}" stroke-width="1.4"/>
            <circle cx="41" cy="20" r="1.8" fill="${statusColor}"/>
            <circle cx="41" cy="29" r="1.8" fill="${statusColor}"/>
            <circle cx="41" cy="38" r="1.8" fill="${statusColor}"/>
          </g>
        `;
      } else if (n.type === 'printer') { // Physical Printer Device
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <rect x="20" y="5" width="20" height="15" fill="#f1f5f9"/>
            <line x1="24" y1="10" x2="36" y2="10" stroke="#cbd5e1" stroke-width="1"/>
            <path d="M 10 20 L 50 20 L 55 40 L 5 40 Z" fill="#334155" stroke="${color}" stroke-width="2" ${filter}/>
            <rect x="15" y="23" width="30" height="8" rx="2" fill="#0f172a"/>
            <circle cx="10" cy="35" r="2" fill="${color}"/>
            <rect x="18" y="40" width="24" height="12" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>
            <line x1="22" y1="44" x2="38" y2="44" stroke="#94a3b8" stroke-width="1"/>
            <line x1="22" y1="48" x2="34" y2="48" stroke="#94a3b8" stroke-width="1"/>
          </g>
        `;
      } else { // PC / Agent / Portal Node
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <rect x="5" y="10" width="50" height="32" rx="3" fill="#1e293b" stroke="${color}" stroke-width="2" ${filter}/>
            <rect x="8" y="13" width="44" height="26" fill="#0ea5e9" opacity="0.15"/>
            <line x1="12" y1="18" x2="25" y2="18" stroke="${statusColor}" stroke-width="2" stroke-linecap="round"/>
            <line x1="12" y1="24" x2="35" y2="24" stroke="${statusColor}" stroke-width="2" stroke-linecap="round"/>
            <line x1="12" y1="30" x2="20" y2="30" stroke="${statusColor}" stroke-width="2" stroke-linecap="round"/>
          </g>
        `;
      }

      let labelLines = String(n.label || n.id).split('\n');
      let textSvg = labelLines.map((l, idx) => `<tspan x="0" dy="${idx === 0 ? 0 : 15}">${esc(l)}</tspan>`).join('');
      const safeDomId = 'gtn-' + String(n.id).replace(/[^a-zA-Z0-9_-]/g, '_');

      return `<g id="${safeDomId}" data-node-id="${esc(n.id)}" class="gt-node" style="cursor:pointer" onclick="GlobalTopology.handleNodeClick(${jsAttr(n.id)})">
    ${svgGraphic}
    <text y="38" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600" font-family="Inter, sans-serif" style="text-shadow: 0px 2px 4px rgba(0,0,0,0.9);">${textSvg}</text>
  </g>`;
    }).join('');
  },

  _updateDOM() {
    this.nodes.forEach((n) => {
      const safeDomId = 'gtn-' + String(n.id).replace(/[^a-zA-Z0-9_-]/g, '_');
      let g = document.getElementById(safeDomId);
      if (g) g.setAttribute('transform', `translate(${n.x},${n.y})`);
    });
  }
};

  window.GlobalTopology = GlobalTopology;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.GlobalTopology = GlobalTopology;
})();
