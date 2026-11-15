/* o-decision-dag.js
 * Organism: DecisionDAGEngine — AI decision path DAG visualization.
 * Extracted from data.service.js (lines 4411-4576) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: LogStreamer (organism), Notify (molecule), DataService (service)
 */
(function () {
  'use strict';

var DecisionDAGEngine = {
  _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
  _currentInc: null,
  _rawNodes: null,
  _rawEdges: null,

  init() {
    const wrap = document.getElementById('decision-dag-svg-wrap');
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
    const vp = document.getElementById('decision-dag-viewport');
    const t = `translate(${this._tx},${this._ty}) scale(${this._scale})`;
    if (vp) vp.setAttribute('transform', t);
  },

  zoomIn() { this._scale = Math.min(3, this._scale + .2); this._applyTransform(); },
  zoomOut() { this._scale = Math.max(.3, this._scale - .2); this._applyTransform(); },
  resetView() { this._scale = 1; this._tx = 0; this._ty = 0; this._applyTransform(); },

  searchNode(q) {
    document.querySelectorAll('#decision-dag-svg .dag-node').forEach(n => {
      const lbl = n.querySelector('text') || { textContent: '' };
      const match = !q || lbl.textContent.toLowerCase().includes(q.toLowerCase());
      n.style.opacity = match ? '1' : '0.2';
    });
  },

  exportSVG() {
    const svg = document.getElementById('decision-dag-svg');
    const data = new XMLSerializer().serializeToString(svg);
    const a = document.createElement('a'); a.href = 'data:image/svg+xml,' + encodeURIComponent(data);
    a.download = 'decision-dag.svg'; a.click();
    Notify.toast('📥 SVG', 'Decision Graph exported', 'ok', 2500);
  },

  async loadIncident(id) {
    const insightTxt = document.getElementById('decision-dag-insight-txt');
    const insight = document.getElementById('decision-dag-insight');
    if (!id) return;

    if (insightTxt) insightTxt.textContent = "Loading decision analysis...";

    try {
      const resp = await fetch(`/api/decision_graph/${id}`);
      const res = await resp.json();
      if (!res || res.status !== 'success') {
        Notify.toast('❌ Error', 'Gagal memuat Decision Graph', 'err');
        return;
      }

      this._currentInc = res.incident_info;
      this._rawNodes = res.nodes;
      this._rawEdges = res.edges;
      this.resetView();
      this._renderGraph();

      if (insight) insight.style.display = 'block';
      if (insightTxt) {
        const info = res.incident_info;
        const devName = info.device_name || 'Unknown';
        insightTxt.textContent = `Incident ${info.incident_id || id} on ${devName} decision lineage. The system evaluated the consensus recommendations, verified against telemetry evidence, and applied OPA policy checks.`;
      }
    } catch (err) {
      console.error(err);
      Notify.toast('❌ Error', 'Gagal memuat Decision Graph dari server', 'err');
    }
  },

  _renderGraph() {
    const edgesEl = document.getElementById('decision-dag-edges');
    const nodesEl = document.getElementById('decision-dag-nodes');
    if (!edgesEl || !nodesEl) return;

    const nodes = this._rawNodes || [];
    const edges = this._rawEdges || [];

    const W = 800, H = 320;
    const nodeCoords = {};
    const stepX = W / (nodes.length + 1);

    nodes.forEach((n, idx) => {
      const x = stepX * (idx + 1);
      const y = H / 2 + (idx % 2 === 0 ? -25 : 25);
      nodeCoords[n.id] = { x, y };
    });

    edgesEl.innerHTML = edges.map(e => {
      const fn = nodeCoords[e.from];
      const tn = nodeCoords[e.to];
      if (!fn || !tn) return '';

      let strokeColor = '#ec4899';
      return `
    <g class="dag-edge">
      <line x1="${fn.x}" y1="${fn.y}" x2="${tn.x}" y2="${tn.y}" stroke="${strokeColor}" stroke-width="2" opacity="0.85" marker-end="url(#decision-arrowhead)" stroke-dasharray="6,4">
        <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite"/>
      </line>
      <text x="${(fn.x + tn.x) / 2}" y="${(fn.y + tn.y) / 2 - 7}" font-size="8.5" font-family="Inter,sans-serif" font-weight="700" fill="var(--txt1)" text-anchor="middle">${e.label || ''}</text>
    </g>
  `;
    }).join('');

    nodesEl.innerHTML = nodes.map(n => {
      const coords = nodeCoords[n.id];
      if (!coords) return '';

      const lines = n.label.split('\n');
      let color = '#311042';
      let stroke = '#d946ef';

      if (n.type === 'incident') {
        color = '#1e293b';
        stroke = '#64748b';
      } else if (n.type === 'consensus') {
        color = '#1e3a8a';
        stroke = '#3b82f6';
      } else if (n.type === 'critic') {
        color = '#581c87';
        stroke = '#a855f7';
      } else if (n.type === 'evidence') {
        color = '#065f46';
        stroke = '#10b981';
      } else if (n.type === 'policy') {
        color = '#78350f';
        stroke = '#f59e0b';
      } else if (n.type === 'hitl') {
        color = '#7f1d1d';
        stroke = '#ef4444';
      } else if (n.type === 'final_action') {
        color = '#831843';
        stroke = '#ec4899';
      }

      return `
    <g class="dag-node" transform="translate(${coords.x},${coords.y})" style="cursor:pointer;" onclick="Notify.toast('${n.type.toUpperCase()}', \`${n.details.replace(/`/g, '\\`').replace(/\\n/g, '<br/>')}\`, 'info', 6000)" title="${n.details || n.label}">
      <rect x="-55" y="-22" width="110" height="44" rx="8" fill="${color}" stroke="${stroke}" stroke-width="1.8" opacity="0.95" />
      ${lines.map((l, i) => {
        return `<text text-anchor="middle" dy="${lines.length > 1 ? (i === 0 ? -6 : 9) : 5}" font-size="8" font-family="Inter,sans-serif" font-weight="600" fill="white">${l}</text>`;
      }).join('')}
    </g>
  `;
    }).join('');

    LogStreamer.add('INFO', 'DAG', `Decision Graph rendered. Visible: \${nodes.length} nodes`);
  }
};

  window.DecisionDAGEngine = DecisionDAGEngine;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.DecisionDAGEngine = DecisionDAGEngine;
})();
