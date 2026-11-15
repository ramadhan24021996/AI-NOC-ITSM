/* o-global-topology.js
 * Organism: GlobalTopology — enterprise network topology visualization.
 * Extracted from data.service.js (lines 1746-2431) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: DataService (service), LogStreamer (organism), Notify (molecule)
 */
(function () {
  'use strict';

var GlobalTopology = {
  nodes: [], edges: [], mode: 'fleet',
  _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,

  init() {
    const wrap = document.getElementById('gt-wrap');
    if (!wrap) return;
    wrap.addEventListener('mousedown', e => {
      if (e.target.closest('.gt-node')) return;
      this._dragging = true;
      this._sx = e.clientX - this._tx;
      this._sy = e.clientY - this._ty;
    });
    document.addEventListener('mouseup', () => this._dragging = false);
    document.addEventListener('mousemove', e => {
      if (!this._dragging) return;
      this._tx = e.clientX - this._sx; this._ty = e.clientY - this._sy;
      this._applyTransform();
    });
    wrap.addEventListener('wheel', e => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.08 : 0.08;
      this._scale = Math.max(0.2, Math.min(3.0, +(this._scale + delta).toFixed(2)));
      this._applyTransform();
      this._updateZoomLabel();
    }, { passive: false });

    Bus.on('devices:loaded', (devices) => {
      this._updateDevices(devices);
    });
  },

  zoomIn() {
    this._scale = Math.min(3.0, +(this._scale + 0.15).toFixed(2));
    this._applyTransform();
    this._updateZoomLabel();
  },

  zoomOut() {
    this._scale = Math.max(0.2, +(this._scale - 0.15).toFixed(2));
    this._applyTransform();
    this._updateZoomLabel();
  },

  resetZoom() {
    let w = 800, h = 550;
    const wrap = document.getElementById('gt-wrap');
    if (wrap) { w = wrap.clientWidth; h = wrap.clientHeight; }
    this._scale = (this.mode === 'ai_lifecycle') ? 0.75 : 0.85;
    this._tx = w / 2;
    this._ty = (this.mode === 'ai_lifecycle') ? 40 : 60;
    this._applyTransform();
    this._updateZoomLabel();
  },


  _updateZoomLabel() {
    const pct = `${Math.round(this._scale * 100)}%`;
    const lbl = document.getElementById('gt-zoom-lbl');
    if (lbl) lbl.textContent = pct;
    const lblHdr = document.getElementById('gt-zoom-lbl-hdr');
    if (lblHdr) lblHdr.textContent = pct;
  },


  _updateDevices(devices) {
    if (this.mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(devices);
      return;
    }
    this.buildDynamicTopology(devices);
  },

  _applyTransform() {
    const vp = document.getElementById('gt-viewport');
    if (vp) vp.setAttribute('transform', `translate(${this._tx},${this._ty}) scale(${this._scale})`);
  },

  async load(devicesOverride) {
    let w = 800, h = 550;
    const wrap = document.getElementById('gt-wrap');
    if (wrap) { w = wrap.clientWidth; h = wrap.clientHeight; }
    this._tx = w / 2; this._ty = 60; this._scale = 0.85;
    this._applyTransform();

    let rawDevices = (devicesOverride && devicesOverride.length > 0)
      ? devicesOverride
      : (window.DataService && DataService._devices && DataService._devices.length > 0 ? DataService._devices : []);

    if ((!rawDevices || rawDevices.length === 0) && window.DataService && typeof DataService.loadDevices === 'function') {
      rawDevices = await DataService.loadDevices();
    }

    if (this.mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(rawDevices);
      return;
    }

    this.buildDynamicTopology(rawDevices);
  },

  switchMode(mode) {
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
    const rawDevices = (window.DataService && DataService._devices) ? DataService._devices : [];
    if (mode === 'ai_lifecycle') {
      this.buildEnterpriseAiTopology(rawDevices);
    } else {
      this.buildDynamicTopology(rawDevices);
    }
  },

  buildEnterpriseAiTopology(devicesOverride) {
    this.nodes = [];
    this.edges = [];

    const rawDevices = (devicesOverride && devicesOverride.length > 0)
      ? devicesOverride
      : (window.DataService && DataService._devices ? DataService._devices : []);

    // ── Layer 0: Client & Gateway ─────────────────────────────────────────
    this.nodes.push({ id: 'L0_User',     label: 'System Admin / NOC\n(User Layer)',         type: 'gateway', status: 'ONLINE', level: 0 });
    this.nodes.push({ id: 'L0_Ext',      label: 'Chrome Extension\nOSI Assistant',          type: 'gateway', status: 'ONLINE', level: 0 });
    this.nodes.push({ id: 'L0_Telegram', label: 'Telegram Bot Gateway\n(P1 Alert Channel)', type: 'gateway', status: 'ONLINE', level: 0 });

    // ── Layer 1: Web Presentation ─────────────────────────────────────────
    this.nodes.push({ id: 'L1_UI',     label: 'Portal Web UI\n(Dark Glassmorphism)',    type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_Dash',   label: 'Dashboard Utama\n(60 FPS Canvas)',       type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_HITL',   label: 'HITL Approval Queue\n& Incident Triage', type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_Telem',  label: 'Telemetry Feed\n(Live Metrics)',          type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_AICog',  label: 'AI Ops Cognition UI\n(RAG & Chat)',      type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_RAG_UI', label: 'Knowledge Base\nRAG Search UI',           type: 'pc', status: 'ONLINE', level: 1 });
    this.nodes.push({ id: 'L1_GovUI',  label: 'Model Config &\nGovernance UI',           type: 'pc', status: 'ONLINE', level: 1 });

    // ── Layer 2: API Gateway ──────────────────────────────────────────────
    this.nodes.push({ id: 'L2_REST', label: 'HTTP REST API\nGateway (:8080)',       type: 'gateway', status: 'ONLINE', level: 2 });
    this.nodes.push({ id: 'L2_WS',   label: 'WebSocket Stream\n(60 FPS Downsample)', type: 'gateway', status: 'ONLINE', level: 2 });

    // ── Layer 3: Go Core Backend ──────────────────────────────────────────
    this.nodes.push({ id: 'L3_GoCore', label: 'Go Server Core\n(Gin Framework)',        type: 'gateway', status: 'ONLINE', level: 3 });
    this.nodes.push({ id: 'L3_Relay',  label: 'Secure Encrypted Relay\n(Remote Control)', type: 'gateway', status: 'ONLINE', level: 3 });
    this.nodes.push({ id: 'L3_Launch', label: 'Launcher Service\nManager',               type: 'gateway', status: 'ONLINE', level: 3 });

    // ── Layer 4: Python AI Core Engines (28+ Engines) ────────────────────
    this.nodes.push({ id: 'L4_PAI',              label: 'Python AI Supervisor\nCognition Engine',      type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Router',            label: 'Multi-LLM Router\n(Intent & Failover)',       type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_GOV',              label: 'Policy Engine\nHITL Safeguard',               type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Observer',          label: 'Active Observer 24/7\n(Curiosity Engine)',    type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_RAG',              label: 'RAG 2.0 Vector Search\n& Reranker (<120ms)', type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DAG',              label: 'Causal DAG Engine\n(Root Cause RCA)',         type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DBNEngine',         label: 'Dynamic Bayesian\nNetwork (DBN)',             type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DecisionNetwork',   label: 'Decision Network\n(MEU / Utility)',           type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ClosedLoop',        label: 'Closed-Loop\nDecision Orchestrator',          type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Planner',           label: 'AI Planning Engine\n(Plan A/B/C)',            type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_CriticAuditor',     label: 'Multi-Agent Consensus\n& Critic Auditor',    type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Executor',          label: 'AI Execution Engine\n(Remediation)',          type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Verifier',          label: 'Execution Verifier\n(Pre & Post Gate)',       type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_FeedbackCollector', label: 'Feedback Collector\n(RLHF Loop)',             type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_SOPRegistry',       label: 'SOP Registry\n(Zero-Hallucination)',          type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_GroundingVerifier', label: 'Dual-Stage Grounding\nVerifier (RAG 2.0)',   type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ExecSummary',       label: 'Executive Summary\nGenerator (ID Awam)',     type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_CausalCards',       label: 'Causal Cards\nPlan A/B/C Visual',            type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_LLMs',              label: 'Cloud LLMs (ONLINE)\nDeepSeek/Gemini/Groq', type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_MemoryGraph',       label: 'AI Memory Graph\n(Causal Sequence)',         type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_KnowledgeAutoBuilder', label: 'Knowledge Auto-Builder\n(Closed-Loop RAG)', type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ModelEvaluator',    label: 'Model Evaluation\nScorecard (5 Matrix)',     type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DPOSynthesizer',    label: 'DPO Dataset Synthesizer\n(Auto-LoRA Pipeline)', type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_EscalationChain',   label: '3-Level Human\nEscalation Chain',            type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Backpressure',      label: 'Anti-Surge\nBackpressure Control',           type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_LocalRules',        label: 'Offline Random Forest\nFallback Engine',     type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ArchiveFTS',        label: 'Cold Data FTS\nArchive Engine',              type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_Chaos',             label: 'Autonomous Chaos\nInjection Worker',         type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_SandboxPromoter',   label: 'AI Learning Sandbox\nPromotion Engine',       type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_SOPClarity',        label: 'SOP Clarity Synthesizer\n(Enterprise 5-Section)', type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_PrecisionAnalyzer', label: 'Precision Remediation &\n4-Factor RCA Analyzer', type: 'printer', status: 'ONLINE', level: 4 });

    // ── 12 Additional Backend Nodes (Verified Active Engines) ──────────────────
    this.nodes.push({ id: 'L4_DAG_Refresher',    label: 'Dynamic Causal Graph\nRefresher Service',       type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DLQ_Processor',    label: 'Dead Letter Queue\nHybrid Processor',           type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_DigitalTwin',      label: 'Digital Twin\nInfrastructure Simulator',        type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ForecastEngine',   label: 'Telemetry Metric\nForecasting Engine',           type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_CircuitBreaker',   label: 'AI Resilience\nCircuit Breaker',                type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_ProactiveRemediator',label:'Proactive Self-Healing\nRemediator',             type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_KafkaConsumer',    label: 'Kafka Enterprise\nStream Consumer',             type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_KnowledgeGraph',   label: 'Knowledge Graph &\nEntity Linker',              type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L3_SNMPCollector',    label: 'SNMP Network\nDiscovery Collector',             type: 'gateway', status: 'ONLINE', level: 3 });
    this.nodes.push({ id: 'L3_SyslogReceiver',   label: 'Enterprise Syslog\nAggregator (:514)',          type: 'gateway', status: 'ONLINE', level: 3 });
    this.nodes.push({ id: 'L4_AIHealth',         label: 'AI Subsystem Health\n& Watchdog Daemon',         type: 'printer', status: 'ONLINE', level: 4 });
    this.nodes.push({ id: 'L4_N8NWebhook',       label: 'n8n Automation\nWebhook Listener',              type: 'printer', status: 'ONLINE', level: 4 });

    // ── Layer 5: Broker, Persistence & Monitoring ─────────────────────────
    this.nodes.push({ id: 'L5_NATS',        label: 'NATS JetStream HA\n(2-Node Active-Active)',  type: 'gateway', status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_Netdata',     label: 'Netdata Master Collector\n(:19999 High-Freq)', type: 'gateway', status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_SQL_Inc',     label: 'PostgreSQL\nincident_analysis DB',            type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_SQL_SO',      label: 'sprint_o.db\n(State Machine DB)',              type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_SQL_RAG',     label: 'pgvector RAG Store\n(PostgreSQL :5432)',       type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_SQL_Cog',     label: 'cognitive_memory.db\n(SQLite WAL)',            type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_VectorDB',    label: 'Vector Store DB\n(pgvector RAG Store)',        type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_DPOStore',    label: 'DPO Dataset Store\n(dpo_datasets/ JSONL)',     type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_FTP',         label: 'FTP / Local Artifact\nShare Server',           type: 'pc',      status: 'ONLINE', level: 5 });
    this.nodes.push({ id: 'L5_OfflineCache',label: 'Agent Offline Cache\n(Local Policy Store)',    type: 'pc',      status: 'ONLINE', level: 5 });

    // ── Layer 6: Infrastructure & Orchestration ───────────────────────────
    this.nodes.push({ id: 'L6_Docker',    label: 'Docker Microservices\nEngine (Runtime)',       type: 'gateway', status: 'ONLINE', level: 6 });
    this.nodes.push({ id: 'L6_N8N',       label: 'n8n Workflow\nAutomation Engine',              type: 'gateway', status: 'ONLINE', level: 6 });
    this.nodes.push({ id: 'L6_CasaOS',    label: 'pgAdmin / CasaOS\nDB Management (:5050)',      type: 'gateway', status: 'ONLINE', level: 6 });
    this.nodes.push({ id: 'L6_EMTrainer', label: 'MLOps Replay\nGatekeeper (EM Trainer)',        type: 'pc',      status: 'ONLINE', level: 6 });
    this.nodes.push({ id: 'L6_SCA',       label: 'SCA Security &\nSBOM Scanner',                 type: 'pc',      status: 'ONLINE', level: 6 });

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
        if (!devIp) devIp = d.site_gateway || '10.20.0.x';

        const status = (d.status === 'ONLINE' || d.online) ? 'ONLINE' : (d.status || 'OFFLINE');
        const agentNodeId = devName;

        this.nodes.push({
          id: agentNodeId,
          label: `${labelName}\n(${devIp})`,
          type: 'pc',
          status: status,
          level: 7
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

    // ── Layout: Horizontal Left-to-Right, evenly spaced per level ─────────
    let levelGroups = {};
    this.nodes.forEach(n => {
      levelGroups[n.level] = levelGroups[n.level] || [];
      levelGroups[n.level].push(n);
    });

    let yStep = 100;
    Object.keys(levelGroups).forEach(lvl => {
      let l = parseInt(lvl);
      let y = l * yStep;
      let nodesInLevel = levelGroups[l];
      let count = nodesInLevel.length;
      if (count === 0) return;

      let xSpacing = count > 3 ? 160 : 220;
      let totalWidth = (count - 1) * xSpacing;
      let startX = -(totalWidth / 2);

      nodesInLevel.forEach((n, idx) => {
        n.x = startX + (idx * xSpacing);
        n.y = y;
      });
    });

    this._render();
    this._updateDOM();
  },

  buildDynamicTopology(devices) {
    this.nodes = [];
    this.edges = [];

    // 0: Server Root
    let serverIP = window.location.hostname || '10.20.0.10';
    if (serverIP === 'localhost') serverIP = '127.0.0.1';
    this.nodes.push({ id: 'Server', label: 'Core Server\n(' + serverIP + ')', type: 'gateway', status: 'ONLINE', level: 0 });

    if (!devices || devices.length === 0) {
      this._render();
      this._updateDOM();
      return;
    }

    // 1: Group by location to form routers
    let locations = {};
    devices.forEach(d => {
      let loc = d.location || d.site_name || d.site_id || 'Main Site';
      if (!locations[loc]) locations[loc] = [];
      locations[loc].push(d);
    });

    let locKeys = Object.keys(locations);
    locKeys.forEach(loc => {
      let routerId = 'RTR-' + loc.replace(/[^a-zA-Z0-9]/g, '_');
      let shortLoc = loc.replace(/_/g, ' ');
      if (shortLoc.length > 18) shortLoc = shortLoc.substring(0, 16) + '..';

      let routerIp = '192.168.1.1';
      if (loc.toLowerCase().includes('jakarta') || loc.toLowerCase().includes('mkt') || loc.toLowerCase().includes('pusat')) {
        routerIp = '10.20.0.2';
      }

      this.nodes.push({ id: routerId, label: 'RTR ' + shortLoc + '\n(' + routerIp + ')', type: 'gateway', status: 'ONLINE', level: 1 });
      this.edges.push({ source: 'Server', target: routerId });

      locations[loc].forEach(d => {
        let name = d.name || d.pc_name || 'Unknown Device';
        let labelName = name.length > 25 ? name.substring(0, 23) + '..' : name;

        let devIp = d.ip || '';
        if (!devIp && d.hardware_info) {
          try {
            let hw = typeof d.hardware_info === 'string' ? JSON.parse(d.hardware_info) : d.hardware_info;
            devIp = hw.ip || hw.networkAdvanced?.ip || '';
          } catch (e) {}
        }
        if (!devIp) devIp = d.site_gateway || '10.20.0.x';

        let status = (d.status === 'ONLINE' || d.online) ? 'ONLINE' : (d.status || 'OFFLINE');
        let dType = 'pc';
        if (name.toLowerCase().includes('print') || name.toLowerCase().includes('prn')) dType = 'printer';

        this.nodes.push({ id: name, label: labelName + '\n(' + devIp + ')', type: dType, status: status, level: 2 });
        this.edges.push({ source: routerId, target: name });
      });
    });

    // Layout algorithm
    let levelGroups = { 0: [], 1: [], 2: [] };
    this.nodes.forEach(n => {
      if (levelGroups[n.level]) levelGroups[n.level].push(n);
    });

    let yStep = 150;
    Object.keys(levelGroups).forEach(lvl => {
      let l = parseInt(lvl);
      let y = l * yStep;
      let nodesInLevel = levelGroups[l];
      let count = nodesInLevel.length;
      if (count === 0) return;

      let xSpacing = l === 2 ? 140 : (l === 1 ? 250 : 0);
      let totalWidth = (count - 1) * xSpacing;
      let startX = -(totalWidth / 2);

      nodesInLevel.forEach((n, idx) => {
        n.x = startX + (idx * xSpacing);
        n.y = y;

        // Vertical staggering for leaf nodes to save horizontal space and prevent overlap
        if (l === 2) {
          if (idx % 2 !== 0) {
            n.y += 60;
          }
        }
      });
    });

    this._render();
    this._updateDOM();
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
      // Orthogonal paths (straight down, then across, then down)
      let midY = n1.y + (n2.y - n1.y) / 2;
      let path = `M ${n1.x} ${n1.y} L ${n1.x} ${midY} L ${n2.x} ${midY} L ${n2.x} ${n2.y}`;
      return `
        <path id="gte-${i}" d="${path}" fill="none" stroke="rgba(14, 165, 233, 0.4)" stroke-width="3" filter="url(#gt-glow-line)" />
        <path d="${path}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="8 12">
           <animate attributeName="stroke-dashoffset" values="20;0" dur="0.8s" repeatCount="indefinite" />
        </path>
      `;
    }).join('');

    elNodes.innerHTML = this.nodes.map((n, i) => {
      let color = n.type === 'gateway' ? '#0ea5e9' : (n.status === 'ONLINE' ? '#10b981' : '#ef4444');
      let filter = 'filter="url(#gt-glow)"';

      let svgGraphic = '';
      if (n.level === 0) { // Core Server
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
      } else if (n.level === 1) { // Router
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <line x1="15" y1="30" x2="10" y2="10" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
            <line x1="45" y1="30" x2="50" y2="10" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>
            <rect x="8" y="25" width="44" height="20" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="2" ${filter}/>
            <rect x="8" y="33" width="44" height="12" rx="0" fill="#0f172a"/>
            <circle cx="16" cy="39" r="2" fill="#10b981"/>
            <circle cx="24" cy="39" r="2" fill="#10b981"/>
            <circle cx="32" cy="39" r="2" fill="#0ea5e9"/>
            <circle cx="40" cy="39" r="2" fill="#10b981"/>
          </g>
        `;
      } else if (n.type === 'printer') { // Printer
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
      } else { // PC / Agent Node
        svgGraphic = `
          <g transform="translate(-30, -30)">
            <rect x="5" y="10" width="50" height="32" rx="3" fill="#1e293b" stroke="${color}" stroke-width="2" ${filter}/>
            <rect x="8" y="13" width="44" height="26" fill="#0ea5e9" opacity="0.15"/>
            <line x1="12" y1="18" x2="25" y2="18" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
            <line x1="12" y1="24" x2="35" y2="24" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
            <line x1="12" y1="30" x2="20" y2="30" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
          </g>
        `;
      }

      let labelLines = n.label.split('\n');
      let textSvg = labelLines.map((l, idx) => `<tspan x="0" dy="${idx === 0 ? 0 : 15}">${l}</tspan>`).join('');
      
      return `<g id="gtn-${n.id}" class="gt-node" style="cursor:pointer" onclick="if('${n.type}'!=='gateway') showDeviceDiagnosticsDetail('${n.id}')">
    ${svgGraphic}
    <text y="38" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600" font-family="Inter, sans-serif" style="text-shadow: 0px 2px 4px rgba(0,0,0,0.9);">${textSvg}</text>
  </g>`;
    }).join('');
  },

  _updateDOM() {
    this.nodes.forEach((n) => {
      let g = document.getElementById('gtn-' + n.id);
      if (g) g.setAttribute('transform', `translate(${n.x},${n.y})`);
    });
  }
};

  window.GlobalTopology = GlobalTopology;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.GlobalTopology = GlobalTopology;
})();
