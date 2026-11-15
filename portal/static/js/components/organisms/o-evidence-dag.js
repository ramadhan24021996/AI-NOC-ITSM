/* o-evidence-dag.js
 * Organism: EvidenceDAGEngine — evidence chain DAG visualization.
 * Extracted from data.service.js (lines 4581-4770) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: LogStreamer (organism), Notify (molecule), DataService (service)
 */
(function () {
  'use strict';

var EvidenceDAGEngine = {
  _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
  _currentInc: null,
  _rawNodes: null,
  _rawEdges: null,
  _selectedNodeId: null,

  init() {
    const wrap = document.getElementById('evidence-dag-svg-wrap');
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
    const vp = document.getElementById('evidence-dag-viewport');
    const t = `translate(${this._tx},${this._ty}) scale(${this._scale})`;
    if (vp) vp.setAttribute('transform', t);
  },

  zoomIn() { this._scale = Math.min(3, this._scale + .2); this._applyTransform(); },
  zoomOut() { this._scale = Math.max(.3, this._scale - .2); this._applyTransform(); },
  resetView() { this._scale = 1; this._tx = 0; this._ty = 0; this._applyTransform(); },

  searchNode(q) {
    document.querySelectorAll('#evidence-dag-svg .dag-node').forEach(n => {
      const lbl = n.querySelector('text') || { textContent: '' };
      const match = !q || lbl.textContent.toLowerCase().includes(q.toLowerCase());
      n.style.opacity = match ? '1' : '0.2';
    });
  },

  exportSVG() {
    const svg = document.getElementById('evidence-dag-svg');
    const data = new XMLSerializer().serializeToString(svg);
    const a = document.createElement('a'); a.href = 'data:image/svg+xml,' + encodeURIComponent(data);
    a.download = 'evidence-dag.svg'; a.click();
    Notify.toast('📥 SVG', 'Evidence DAG exported', 'ok', 2500);
  },

  async loadIncident(id) {
    const insightTxt = document.getElementById('evidence-dag-insight-txt');
    const insight = document.getElementById('evidence-dag-insight');
    if (!id) return;

    if (insightTxt) insightTxt.textContent = "Loading evidence analysis...";

    try {
      const resp = await fetch(`/api/incidents/${id}/evidence_dag`);
      const res = await resp.json();
      if (!res || !res.nodes) {
        Notify.toast('❌ Error', 'Gagal memuat Evidence DAG', 'err');
        return;
      }

      this._currentInc = id;
      this._rawNodes = res.nodes;
      this._rawEdges = res.edges;
      this._selectedNodeId = null;
      this.resetView();
      this._renderGraph();

      if (insight) insight.style.display = 'block';
      if (insightTxt) {
        insightTxt.innerHTML = `Incident <b>${id}</b> Trace Audit. Terdeteksi ${res.node_count} nodes & ${res.edge_count} edges. Klik salah satu node untuk menampilkan detail evidence.`;
      }
    } catch (err) {
      console.error(err);
      Notify.toast('❌ Error', 'Gagal memuat Evidence DAG dari server', 'err');
    }
  },

  selectNode(nodeId) {
    this._selectedNodeId = nodeId;
    const node = this._rawNodes.find(n => n.node_id === nodeId);
    if (!node) return;

    const contentSafe = node.content.replace(/`/g, '\\`').replace(/\\n/g, '<br/>');
    const modalContent = `
  <div style="font-size:12px;color:var(--txt2)">
    <p><b>Node ID:</b> <span class="tag tag-gray">${node.node_id}</span></p>
    <p><b>Source:</b> <span class="tag tag-blue">${node.source}</span></p>
    <p><b>Event Type:</b> <span class="tag tag-orange">${node.event_type}</span></p>
    <p><b>Actor:</b> <span class="tag tag-green">${node.actor}</span></p>
    <p><b>Timestamp:</b> <span style="color:var(--txt)">${node.timestamp}</span></p>
    <div style="margin-top:10px;padding:10px;background:rgba(0,0,0,0.3);border:1px solid var(--bd);border-radius:4px;word-break:break-all;font-family:monospace;max-height:200px;overflow-y:auto">
      <b>Payload/Content:</b><br/>${contentSafe}
    </div>
  </div>
`;
    Modal.show('🔍 Inspect Evidence Node', modalContent, [{ label: 'Close', cls: 'btn-secondary', fn: 'Modal.close()' }]);

    this._renderGraph();
  },

  _renderGraph() {
    const edgesEl = document.getElementById('evidence-dag-edges');
    const nodesEl = document.getElementById('evidence-dag-nodes');
    if (!edgesEl || !nodesEl) return;

    const nodes = this._rawNodes || [];
    const edges = this._rawEdges || [];

    const W = 800, H = 320;
    const nodeCoords = {};
    const stepX = W / (nodes.length + 1);

    nodes.forEach((n, idx) => {
      const x = stepX * (idx + 1);
      const y = H / 2 + (idx % 2 === 0 ? -30 : 30);
      nodeCoords[n.node_id] = { x, y };
    });

    edgesEl.innerHTML = edges.map(e => {
      const fn = nodeCoords[e.from];
      const tn = nodeCoords[e.to];
      if (!fn || !tn) return '';

      let strokeColor = '#10b981';
      if (e.label === 'ai_evidence') strokeColor = '#3b82f6';
      else if (e.label === 'ai_decision') strokeColor = '#d946ef';
      else if (e.label === 'resolved_by') strokeColor = '#8b5cf6';

      return `
    <g class="dag-edge">
      <line x1="${fn.x}" y1="${fn.y}" x2="${tn.x}" y2="${tn.y}" stroke="${strokeColor}" stroke-width="2" opacity="0.85" marker-end="url(#evidence-arrowhead)" stroke-dasharray="6,4">
        <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite"/>
      </line>
      <text x="${(fn.x + tn.x) / 2}" y="${(fn.y + tn.y) / 2 - 7}" font-size="8.5" font-family="Inter,sans-serif" font-weight="700" fill="var(--txt1)" text-anchor="middle">${e.label || ''}</text>
    </g>
  `;
    }).join('');

    nodesEl.innerHTML = nodes.map(n => {
      const coords = nodeCoords[n.node_id];
      if (!coords) return '';

      const isSelected = this._selectedNodeId === n.node_id;

      let color = '#0f172a';
      let stroke = '#64748b';

      if (n.source === 'incident_events') {
        color = '#1e3a8a';
        stroke = '#3b82f6';
      } else if (n.source === 'ai_evidence_logs') {
        color = '#064e3b';
        stroke = '#10b981';
      } else if (n.source === 'fleet_evidence') {
        color = '#7c2d12';
        stroke = '#f97316';
      } else if (n.source === 'decision_graphs') {
        color = '#4c1d95';
        stroke = '#d946ef';
      } else if (n.source === 'incident_closure') {
        color = '#4c0519';
        stroke = '#f43f5e';
      }

      const shortContent = n.content.length > 15 ? n.content.slice(0, 15) + '...' : n.content;

      return `
    <g class="dag-node ${isSelected ? 'selected' : ''}" transform="translate(${coords.x},${coords.y})" style="cursor:pointer;" onclick="EvidenceDAGEngine.selectNode('${n.node_id}')" title="[${n.source}] ${n.event_type}">
      <rect x="-60" y="-25" width="120" height="50" rx="8" fill="${color}" stroke="${stroke}" stroke-width="${isSelected ? 3.0 : 1.8}" opacity="0.95" ${isSelected ? 'filter="url(#evidence-glow)"' : ''} />
      <text text-anchor="middle" dy="-10" font-size="7.5" font-family="Inter,sans-serif" font-weight="700" fill="white">${n.event_type}</text>
      <text text-anchor="middle" dy="3" font-size="7.0" font-family="Inter,sans-serif" fill="var(--txt2)">${shortContent}</text>
      <text text-anchor="middle" dy="14" font-size="6.5" font-family="Inter,sans-serif" font-style="italic" fill="var(--txt3)">${n.actor} | ${n.timestamp ? n.timestamp.slice(11, 19) : ''}</text>
    </g>
  `;
    }).join('');

    LogStreamer.add('INFO', 'DAG', `Evidence Graph rendered. Visible: ${nodes.length} nodes`);
  }
};

  window.EvidenceDAGEngine = EvidenceDAGEngine;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.EvidenceDAGEngine = EvidenceDAGEngine;
})();
