/* o-dag-engine.js
 * Organism: DAGEngine — causal DAG visualization engine.
 * Extracted from data.service.js (lines 1389-1741) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: LogStreamer (organism), Notify (molecule), DataService (service)
 */
(function () {
  'use strict';

var DAGEngine = {
  _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
  _currentInc: null,
  _rawNodes: null,
  _rawEdges: null,
  _collapsedNodes: new Set(),

  init() {
    const wrap = document.getElementById('dag-svg-wrap');
    if (!wrap) return;
    wrap.addEventListener('mousedown', e => {
      if (e.target.closest('.dag-node')) return;
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
      const delta = e.deltaY > 0 ? -.1 : .1;
      this._scale = Math.max(.3, Math.min(3, this._scale + delta));
      this._applyTransform();
    }, { passive: false });
  },

  _applyTransform() {
    const vp = document.getElementById('dag-viewport');
    const t = `translate(${this._tx},${this._ty}) scale(${this._scale})`;
    if (vp) vp.setAttribute('transform', t);
  },

  zoomIn() { this._scale = Math.min(3, this._scale + .2); this._applyTransform(); },
  zoomOut() { this._scale = Math.max(.3, this._scale - .2); this._applyTransform(); },
  resetView() { this._scale = 1; this._tx = 0; this._ty = 0; this._applyTransform(); },

  searchNode(q) {
    document.querySelectorAll('.dag-node').forEach(n => {
      const lbl = n.querySelector('text') || { textContent: '' };
      const match = !q || lbl.textContent.toLowerCase().includes(q.toLowerCase());
      n.style.opacity = match ? '1' : '0.2';
    });
  },

  exportSVG() {
    const svg = document.getElementById('dag-svg');
    const data = new XMLSerializer().serializeToString(svg);
    const a = document.createElement('a'); a.href = 'data:image/svg+xml,' + encodeURIComponent(data);
    a.download = 'causal-dag.svg'; a.click();
    Notify.toast('📥 SVG', 'Causal DAG diexport', 'ok', 2500);
  },

  async loadIncident(id) {
    const insightTxt = document.getElementById('dag-insight-txt');
    const insight = document.getElementById('dag-insight');

    if (!id) {
      this._currentInc = {
        incident_id: "1310",
        device_name: "PC-FNBCBD02",
        flag: "PORT_DOWN",
        timestamp: "2026-06-15 06:28:21",
        confidence: 0.95,
        analysis: 'Insiden "PORT_DOWN" terdeteksi Layer 1. AI merekomendasikan verifikasi koneksi fisik dan restart agent service.'
      };
      this._rawNodes = [
        { id: "PORT_DOWN", label: "PORT_DOWN", type: "root_cause", details: "Interface Ethernet status changed to DOWN" },
        { id: "Device", label: "Device", type: "device", details: "Core Network Switch Device" },
        { id: "degraded_perf", label: "Degraded Perf", type: "blast_radius", details: "Device performance degradation detected" },
        { id: "alert_triggered", label: "Alert Triggered", type: "blast_radius", details: "SNMP Alert Triggered" },
        { id: "noc_notified", label: "NOC Notified", type: "healthy", details: "NOC Team notified via alert channel" }
      ];
      this._rawEdges = [
        { from: "PORT_DOWN", to: "Device", label: "" },
        { from: "PORT_DOWN", to: "alert_triggered", label: "" },
        { from: "Device", to: "degraded_perf", label: "" },
        { from: "Device", to: "noc_notified", label: "" }
      ];
      this._collapsedNodes = new Set();
      this.resetView();
      this._renderGraph();

      if (insight) insight.style.display = 'block';
      if (insightTxt) {
        insightTxt.textContent = `Insiden 1310 - PC-FNBCBD02: "PORT_DOWN" terdeteksi Layer 1. AI merekomendasikan verifikasi koneksi fisik dan restart agent service.`;
      }
      return;
    }

    if (insightTxt) insightTxt.textContent = "Loading causal analysis...";

    try {
      const resp = await fetch(`/api/causal_dag/${id}`);
      const res = await resp.json();
      if (!res || res.status !== 'success') {
        Notify.toast('❌ Error', 'Gagal memuat Causal DAG', 'err');
        return;
      }

      this._currentInc = res.incident_info;
      this._rawNodes = res.nodes;
      this._rawEdges = res.edges;
      this._collapsedNodes = new Set();
      this.resetView();
      this._renderGraph();

      if (insight) insight.style.display = 'block';
      if (insightTxt) {
        const info = res.incident_info;
        const devName = info.device_name || 'Unknown';
        insightTxt.textContent = `Insiden ${id} · ${devName}: "${info.flag || 'ANOMALY'}" terdeteksi. AI Analysis: ${info.analysis || 'No analysis available'}`;
      }
    } catch (err) {
      console.error(err);
      Notify.toast('❌ Error', 'Gagal memuat Causal DAG dari server', 'err');
    }
  },

  _renderGraph() {
    const edgesEl = document.getElementById('dag-edges');
    const nodesEl = document.getElementById('dag-nodes');
    if (!edgesEl || !nodesEl) return;

    const nodes = this._rawNodes || [];
    const edges = this._rawEdges || [];

    const visibleNodeIds = new Set();
    const collapsedNodeIds = this._collapsedNodes || new Set();

    const adj = {};
    nodes.forEach(n => adj[n.id] = []);
    edges.forEach(e => {
      if (adj[e.from]) adj[e.from].push(e.to);
    });

    const inDegree = {};
    nodes.forEach(n => inDegree[n.id] = 0);
    edges.forEach(e => {
      if (inDegree[e.to] !== undefined) inDegree[e.to]++;
    });

    const roots = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id);
    if (roots.length === 0 && nodes.length > 0) {
      roots.push(nodes[0].id);
    }

    const depths = {};
    const queue = [];

    roots.forEach(rId => {
      depths[rId] = 0;
      queue.push(rId);
    });

    const visibleNodes = [];
    const hiddenNodeIds = new Set();

    const markHidden = (nodeId) => {
      if (collapsedNodeIds.has(nodeId)) {
        const traverse = (id) => {
          (adj[id] || []).forEach(childId => {
            if (!hiddenNodeIds.has(childId)) {
              hiddenNodeIds.add(childId);
              traverse(childId);
            }
          });
        };
        traverse(nodeId);
      }
    };

    const visited = new Set();
    roots.forEach(r => visited.add(r));

    while (queue.length > 0) {
      const curr = queue.shift();
      const currDepth = depths[curr];

      if (hiddenNodeIds.has(curr)) {
        (adj[curr] || []).forEach(child => {
          hiddenNodeIds.add(child);
        });
      }

      markHidden(curr);

      (adj[curr] || []).forEach(child => {
        if (!visited.has(child)) {
          visited.add(child);
          depths[child] = Math.max(depths[child] || 0, currDepth + 1);
          queue.push(child);
        }
      });
    }

    nodes.forEach(n => {
      if (depths[n.id] === undefined) {
        depths[n.id] = 0;
      }
    });

    nodes.forEach(n => {
      if (!hiddenNodeIds.has(n.id)) {
        visibleNodes.push(n);
        visibleNodeIds.add(n.id);
      }
    });

    const layers = {};
    visibleNodes.forEach(n => {
      const d = depths[n.id] || 0;
      if (!layers[d]) layers[d] = [];
      layers[d].push(n);
    });

    const W = 780, H = 280;
    const nodeCoords = {};

    const numLayers = Object.keys(layers).length;
    Object.keys(layers).forEach((depthStr, layerIndex) => {
      const depth = parseInt(depthStr);
      const layerNodes = layers[depth];
      const k = layerNodes.length;
      const x = numLayers > 1 ? W * (0.15 + 0.70 * (layerIndex / (numLayers - 1))) : W * 0.5;

      layerNodes.forEach((node, i) => {
        const y = H * ((i + 1) / (k + 1));
        nodeCoords[node.id] = { x, y };
      });
    });

    const visibleEdges = edges.filter(e => visibleNodeIds.has(e.from) && visibleNodeIds.has(e.to));

    edgesEl.innerHTML = visibleEdges.map(e => {
      const fn = nodeCoords[e.from];
      const tn = nodeCoords[e.to];
      if (!fn || !tn) return '';

      let strokeColor = '#3b82f6';
      if (e.from === 'PORT_DOWN' && e.to === 'alert_triggered') {
        strokeColor = '#ef4444';
      } else if (e.to === 'noc_notified') {
        strokeColor = '#10b981';
      } else if (e.to === 'degraded_perf') {
        strokeColor = '#0d9488';
      } else if (e.label && (e.label.includes('90') || e.label.includes('93') || e.label.includes('95'))) {
        strokeColor = '#ef4444';
      } else if (e.label && e.label.includes('8')) {
        strokeColor = '#f59e0b';
      } else if (e.label && e.label.includes('Spreading')) {
        strokeColor = '#06b6d4';
      }

      let markerId = 'arrowhead';
      if (strokeColor === '#ef4444') markerId = 'arrowhead-red';
      else if (strokeColor === '#10b981') markerId = 'arrowhead-green';
      else if (strokeColor === '#0d9488') markerId = 'arrowhead-cyan';

      return `
    <g class="dag-edge">
      <line x1="${fn.x}" y1="${fn.y}" x2="${tn.x}" y2="${tn.y}" stroke="${strokeColor}" stroke-width="1.8" opacity="0.8" marker-end="url(#${markerId})" stroke-dasharray="6,4">
        <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite"/>
      </line>
      <text x="${(fn.x + tn.x) / 2}" y="${(fn.y + tn.y) / 2 - 5}" font-size="8.5" font-family="Inter,sans-serif" font-weight="700" fill="var(--txt2)" text-anchor="middle">${e.label || ''}</text>
    </g>
  `;
    }).join('');

    nodesEl.innerHTML = visibleNodes.map(n => {
      const coords = nodeCoords[n.id];
      if (!coords) return '';

      const lines = n.label.split('\n');
      const isRoot = n.type === 'root_cause';
      const isCollapsed = collapsedNodeIds.has(n.id);
      const hasChildren = (adj[n.id] || []).length > 0;

      let color = '#1e3a5f';
      let stroke = '#3b82f6';

      if (n.type === 'root_cause' || n.id.includes('alert')) {
        color = '#7f1d1d';
        stroke = '#ef4444';
      } else if (n.type === 'blast_radius' || n.id.includes('degraded')) {
        if (n.id.includes('impact') || n.id.includes('degraded')) {
          color = '#0f766e';
          stroke = '#0d9488';
        } else {
          color = '#b45309';
          stroke = '#d97706';
        }
      } else if (n.type === 'healthy' || n.id.includes('noc')) {
        color = '#064e3b';
        stroke = '#10b981';
      }

      const collapseIndicator = hasChildren ? (isCollapsed ? ' ➕' : ' ➖') : '';

      return `
    <g class="dag-node ${isRoot ? 'selected' : ''}" transform="translate(${coords.x},${coords.y})" onclick="DAGEngine.toggleNode('${n.id}')" style="cursor:pointer;" title="${n.details || n.label}">
      <rect x="-65" y="-22" width="130" height="44" rx="8" fill="${color}" stroke="${stroke}" stroke-width="${isRoot ? 2.5 : 1.2}" opacity="0.95" ${isRoot ? 'filter="url(#glow)"' : ''}/>
      ${lines.map((l, i) => {
        const labelText = i === 0 ? l + collapseIndicator : l;
        return `<text text-anchor="middle" dy="${lines.length > 1 ? (i === 0 ? -6 : 9) : 5}" font-size="9" font-family="Inter,sans-serif" font-weight="600" fill="white">${labelText}</text>`;
      }).join('')}
    </g>
  `;
    }).join('');

    LogStreamer.add('INFO', 'DAG', `Causal DAG rendered. Visible: ${visibleNodes.length}/${nodes.length} nodes`);
  },

  toggleNode(nodeId) {
    if (!this._rawNodes) return;
    if (this._collapsedNodes.has(nodeId)) {
      this._collapsedNodes.delete(nodeId);
      Notify.toast('⊞ DAG', `Node expanded`, 'info', 1000);
    } else {
      this._collapsedNodes.add(nodeId);
      Notify.toast('⊟ DAG', `Node collapsed`, 'info', 1000);
    }
    this._renderGraph();
  },

  expandAll() {
    if (!this._rawNodes) return;
    this._collapsedNodes.clear();
    this._renderGraph();
    Notify.toast('⊞ DAG', 'All nodes expanded', 'ok', 1500);
  },

  collapseAll() {
    if (!this._rawNodes) return;
    const adj = {};
    this._rawNodes.forEach(n => adj[n.id] = []);
    this._rawEdges.forEach(e => {
      if (adj[e.from]) adj[e.from].push(e.to);
    });

    this._collapsedNodes.clear();
    this._rawNodes.forEach(n => {
      if ((adj[n.id] || []).length > 0) {
        this._collapsedNodes.add(n.id);
      }
    });
    this._renderGraph();
    Notify.toast('⊟ DAG', 'All non-leaf nodes collapsed', 'warn', 1500);
  }
};

  window.DAGEngine = DAGEngine;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.DAGEngine = DAGEngine;
})();
