import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

# I will replace the previously injected UnifiedDAGEngine with an improved one that handles all three graph schemas correctly
start_idx = content.find('/* ==================================================\n       UNIFIED DAG ENGINE')
end_idx = content.find('var DAGEngine = {')

improved_engine = """/* ==================================================
       UNIFIED DAG ENGINE
    ================================================== */
    var UnifiedDAGEngine = {
      _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
      _currentInc: null,
      _cache: { causal: null, decision: null, evidence: null },
      _currentTab: 'causal',
      _collapsedNodes: new Set(),
      _incidentId: '',
      _selectedNodeId: null,

      init() {
        const wrap = document.getElementById('unified-dag-svg-wrap');
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
        const vp = document.getElementById('unified-dag-viewport');
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
        const svg = document.getElementById('unified-dag-svg');
        const data = new XMLSerializer().serializeToString(svg);
        const a = document.createElement('a'); a.href = 'data:image/svg+xml,' + encodeURIComponent(data);
        a.download = `${this._currentTab}-dag.svg`; a.click();
        Notify.toast('📥 SVG', `Exported ${this._currentTab} DAG`, 'ok', 2500);
      },

      switchTab(tab) {
        this._currentTab = tab;
        this._selectedNodeId = null;
        document.getElementById('tab-causal').classList.remove('active');
        document.getElementById('tab-decision').classList.remove('active');
        document.getElementById('tab-evidence').classList.remove('active');
        
        document.getElementById('tab-causal').style.color = 'var(--txt2)';
        document.getElementById('tab-causal').style.borderBottom = 'none';
        document.getElementById('tab-decision').style.color = 'var(--txt2)';
        document.getElementById('tab-decision').style.borderBottom = 'none';
        document.getElementById('tab-evidence').style.color = 'var(--txt2)';
        document.getElementById('tab-evidence').style.borderBottom = 'none';
        
        const activeTab = document.getElementById(`tab-${tab}`);
        activeTab.classList.add('active');
        
        let color = 'var(--blue)';
        if(tab === 'decision') color = 'var(--pink)';
        if(tab === 'evidence') color = 'var(--green)';
        
        activeTab.style.color = color;
        activeTab.style.borderBottom = `2px solid ${color}`;
        
        if (this._incidentId) {
           this._renderFromCache(tab);
        }
      },
      
      _renderFromCache(tab) {
         const data = this._cache[tab];
         if (data) {
             this._rawNodes = data.nodes;
             this._rawEdges = data.edges;
             this._currentInc = data.incident_info || this._incidentId;
             this.resetView();
             this._renderGraph();
             this._updateInsight(tab, data);
         } else {
             this.fetchData(this._incidentId, tab);
         }
      },

      async loadIncident(id) {
         this._incidentId = id;
         // Clear cache on new incident
         this._cache = { causal: null, decision: null, evidence: null };
         if (!id) return;
         this._renderFromCache(this._currentTab);
         
         // Preload other tabs silently
         const otherTabs = ['causal', 'decision', 'evidence'].filter(t => t !== this._currentTab);
         for(let t of otherTabs) {
             this.fetchData(id, t, true);
         }
      },
      
      async fetchData(id, tab, silent=false) {
        if(!silent) document.getElementById('unified-dag-insight-txt').textContent = "Loading analysis...";
        
        let endpoint = '';
        if(tab === 'causal') endpoint = `/api/causal_dag/${id}`;
        if(tab === 'decision') endpoint = `/api/decision_graph/${id}`;
        if(tab === 'evidence') endpoint = `/api/incidents/${id}/evidence_dag`;
        
        try {
          const resp = await fetch(endpoint);
          const res = await resp.json();
          if (res && (res.status === 'success' || res.nodes)) {
              this._cache[tab] = res;
              if (this._currentTab === tab) {
                  this._renderFromCache(tab);
              }
          } else {
              if(!silent) Notify.toast('❌ Error', `Gagal memuat ${tab} DAG`, 'err');
          }
        } catch (err) {
          console.error(err);
          if(!silent) Notify.toast('❌ Error', `Network Error loading ${tab}`, 'err');
        }
      },

      _updateInsight(tab, data) {
          const insight = document.getElementById('unified-dag-insight');
          const txt = document.getElementById('unified-dag-insight-txt');
          if(!insight || !txt || !data) return;
          insight.style.display = 'block';
          
          if(tab === 'causal') {
              const info = data.incident_info || {};
              txt.innerHTML = `Insiden ${this._incidentId} · ${info.device_name || 'Unknown'}: "${info.flag || 'ANOMALY'}" terdeteksi. AI Analysis: ${info.analysis || '-'}`;
          } else if(tab === 'decision') {
              const info = data.incident_info || {};
              txt.innerHTML = `AI Decision Logic for ${this._incidentId}: Policy rules evaluated with ${info.confidence || 0}% confidence`;
          } else if(tab === 'evidence') {
              txt.innerHTML = `Incident <b>${this._incidentId}</b> Trace Audit. Terdeteksi ${data.node_count || data.nodes.length} nodes & ${data.edge_count || data.edges.length} edges. Klik salah satu node untuk menampilkan detail evidence.`;
          }
      },

      expandAll() {
        this._collapsedNodes.clear();
        this._renderGraph();
      },

      collapseAll() {
        if (!this._rawNodes) return;
        this._rawNodes.forEach(n => {
          const id = n.id || n.node_id;
          if (n.type === 'root_cause' || n.type === 'trigger') this._collapsedNodes.add(id);
        });
        this._renderGraph();
      },
      
      selectEvidenceNode(nodeId) {
        this._selectedNodeId = nodeId;
        const node = this._rawNodes.find(n => n.node_id === nodeId);
        if (!node) return;

        const contentSafe = (node.content || '').replace(/`/g, '\\`').replace(/\\n/g, '<br/>');
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
      
      toggleNode(id) {
          if (this._collapsedNodes.has(id)) this._collapsedNodes.delete(id);
          else this._collapsedNodes.add(id);
          this._renderGraph();
      },

      _renderGraph() {
        const edgesEl = document.getElementById('unified-dag-edges');
        const nodesEl = document.getElementById('unified-dag-nodes');
        if (!edgesEl || !nodesEl) return;

        const nodes = this._rawNodes || [];
        const edges = this._rawEdges || [];
        
        let marker = 'arrowhead';
        if(this._currentTab === 'decision') marker = 'decision-arrowhead';
        if(this._currentTab === 'evidence') marker = 'evidence-arrowhead';

        const visibleNodeIds = new Set();
        const visibleEdges = edges.filter(e => {
          let current = e.from || e.source; // evidence has from/to, wait, evidence edges are e.from and e.to. Wait, decision edges are e.from, e.to.
          const f = e.from || e.source;
          const t = e.to || e.target;
          if(!f || !t) return false;
          
          if(this._currentTab === 'causal') {
              let curr = f;
              while (curr) {
                if (this._collapsedNodes.has(curr) && curr !== f) return false;
                const parentEdge = edges.find(p => (p.to || p.target) === curr);
                curr = parentEdge ? (parentEdge.from || parentEdge.source) : null;
              }
          }
          visibleNodeIds.add(f);
          visibleNodeIds.add(t);
          return true;
        });
        const visibleNodes = nodes.filter(n => visibleNodeIds.has(n.id || n.node_id) || nodes.length === 1);

        const levelMap = new Map();
        visibleNodes.forEach(n => levelMap.set(n.id || n.node_id, 0));
        let changed = true;
        while (changed) {
          changed = false;
          visibleEdges.forEach(e => {
            const f = e.from || e.source;
            const t = e.to || e.target;
            const fromLvl = levelMap.get(f) || 0;
            const toLvl = levelMap.get(t) || 0;
            if (fromLvl >= toLvl) { levelMap.set(t, fromLvl + 1); changed = true; }
          });
        }

        const levelCounts = {};
        visibleNodes.forEach(n => {
          const lvl = levelMap.get(n.id || n.node_id) || 0;
          levelCounts[lvl] = (levelCounts[lvl] || 0) + 1;
        });

        const nodePos = new Map();
        const levelY = {};
        const W = 800, H = 320;
        
        if (this._currentTab === 'decision' || this._currentTab === 'evidence') {
            const stepX = W / (visibleNodes.length + 1);
            visibleNodes.forEach((n, idx) => {
              const x = stepX * (idx + 1);
              const offset = this._currentTab === 'evidence' ? 30 : 25;
              const y = H / 2 + (idx % 2 === 0 ? -offset : offset);
              nodePos.set(n.id || n.node_id, { x, y });
            });
        } else {
            const X_SPACING = 200, Y_SPACING = 80;
            visibleNodes.forEach(n => {
              const id = n.id || n.node_id;
              const lvl = levelMap.get(id) || 0;
              const idx = levelY[lvl] || 0;
              levelY[lvl] = idx + 1;
              const total = levelCounts[lvl];
              const x = 100 + lvl * X_SPACING;
              const y = 160 + (idx - (total - 1) / 2) * Y_SPACING;
              nodePos.set(id, { x, y });
            });
        }

        edgesEl.innerHTML = '';
        visibleEdges.forEach(e => {
          const f_id = e.from || e.source;
          const t_id = e.to || e.target;
          const f = nodePos.get(f_id);
          const t = nodePos.get(t_id);
          if (!f || !t) return;

          let startX = f.x, startY = f.y, endX = t.x, endY = t.y;
          let dx = t.x - f.x, dy = t.y - f.y;
          let stroke = '#4b5563';
          
          if(this._currentTab === 'causal') {
              const len = Math.sqrt(dx * dx + dy * dy);
              if (len === 0) return;
              const nx = dx / len, ny = dy / len;
              startX = f.x + nx * 15; startY = f.y + ny * 15;
              endX = t.x - nx * 20; endY = t.y - ny * 20;
              
              const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
              path.setAttribute('d', `M${startX},${startY} C${startX + dx / 2},${startY} ${endX - dx / 2},${endY} ${endX},${endY}`);
              path.setAttribute('fill', 'none');
              path.setAttribute('stroke', stroke);
              path.setAttribute('stroke-width', '1.5');
              path.setAttribute('marker-end', `url(#${marker})`);
              edgesEl.appendChild(path);

              if (e.label) {
                const mx = (startX + endX) / 2;
                const my = (startY + endY) / 2;
                const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                bg.setAttribute('x', mx - 20); bg.setAttribute('y', my - 8);
                bg.setAttribute('width', 40); bg.setAttribute('height', 16);
                bg.setAttribute('fill', '#1f2937'); bg.setAttribute('rx', 4);
                const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                lbl.setAttribute('x', mx); lbl.setAttribute('y', my + 3);
                lbl.setAttribute('fill', '#9ca3af'); lbl.setAttribute('font-size', '9');
                lbl.setAttribute('text-anchor', 'middle');
                lbl.textContent = e.label;
                edgesEl.appendChild(bg); edgesEl.appendChild(lbl);
              }
          } else {
              if(this._currentTab === 'decision') {
                  stroke = '#ec4899';
              } else if(this._currentTab === 'evidence') {
                  stroke = '#10b981';
                  if (e.label === 'ai_evidence') stroke = '#3b82f6';
                  else if (e.label === 'ai_decision') stroke = '#d946ef';
                  else if (e.label === 'resolved_by') stroke = '#8b5cf6';
              }
              const gEdge = document.createElementNS('http://www.w3.org/2000/svg', 'g');
              gEdge.setAttribute('class', 'dag-edge');
              const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
              line.setAttribute('x1', startX); line.setAttribute('y1', startY);
              line.setAttribute('x2', endX); line.setAttribute('y2', endY);
              line.setAttribute('stroke', stroke); line.setAttribute('stroke-width', '2');
              line.setAttribute('opacity', '0.85'); line.setAttribute('marker-end', `url(#${marker})`);
              line.setAttribute('stroke-dasharray', '6,4');
              const anim = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
              anim.setAttribute('attributeName', 'stroke-dashoffset');
              anim.setAttribute('from', '0'); anim.setAttribute('to', '-20');
              anim.setAttribute('dur', '1.2s'); anim.setAttribute('repeatCount', 'indefinite');
              line.appendChild(anim);
              gEdge.appendChild(line);
              
              if(e.label) {
                const mx = (startX + endX) / 2;
                const my = (startY + endY) / 2 - 7;
                const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                lbl.setAttribute('x', mx); lbl.setAttribute('y', my);
                lbl.setAttribute('fill', 'var(--txt1)'); lbl.setAttribute('font-size', '8.5');
                lbl.setAttribute('font-family', 'Inter,sans-serif'); lbl.setAttribute('font-weight', '700');
                lbl.setAttribute('text-anchor', 'middle');
                lbl.textContent = e.label;
                gEdge.appendChild(lbl);
              }
              edgesEl.appendChild(gEdge);
          }
        });

        nodesEl.innerHTML = '';
        visibleNodes.forEach(n => {
          const id = n.id || n.node_id;
          const p = nodePos.get(id);
          const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
          const isSelected = this._selectedNodeId === id;
          g.setAttribute('class', `dag-node ${isSelected ? 'selected' : ''}`);
          g.setAttribute('transform', `translate(${p.x},${p.y})`);
          g.style.cursor = 'pointer';

          if(this._currentTab === 'causal') {
              g.onclick = () => {
                  Notify.toast('Node', n.details || n.label, 'info');
              };
              let fill = '#1f2937', stroke = '#4b5563', glow = '';
              if (n.type === 'root_cause' || n.type === 'trigger') { fill = '#312e81'; stroke = '#6366f1'; glow = 'url(#glow)'; }
              if (n.type === 'blast_radius' || n.type === 'risk') { fill = '#450a0a'; stroke = '#ef4444'; }
              if (n.type === 'healthy' || n.type === 'evidence') { fill = '#064e3b'; stroke = '#10b981'; }

              const hasChildren = edges.some(e => e.from === id);
              const isCollapsed = this._collapsedNodes.has(id);

              const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
              rect.setAttribute('x', -60); rect.setAttribute('y', -18);
              rect.setAttribute('width', 120); rect.setAttribute('height', 36);
              rect.setAttribute('rx', 6);
              rect.setAttribute('fill', fill);
              rect.setAttribute('stroke', stroke);
              rect.setAttribute('stroke-width', '1.5');
              if (glow) rect.setAttribute('filter', glow);
              
              const iconMap = { root_cause: '⚡', blast_radius: '💥', healthy: '✅', device: '🖥️', metric: '📊', trigger: '🔔', action: '🛠️', condition: '🤔', human: '👤', policy: '📜', evidence: '📄', log: '📝' };
              const icon = iconMap[n.type] || '⏺';

              const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
              text.setAttribute('y', -2); text.setAttribute('fill', '#e5e7eb');
              text.setAttribute('font-size', '10'); text.setAttribute('text-anchor', 'middle');
              text.setAttribute('font-weight', '500');
              text.textContent = `${icon} ${n.label || id}`;

              const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
              sub.setAttribute('y', 10); sub.setAttribute('fill', '#9ca3af');
              sub.setAttribute('font-size', '8'); sub.setAttribute('text-anchor', 'middle');
              sub.textContent = n.details ? (n.details.length > 20 ? n.details.substring(0, 20) + '...' : n.details) : '';

              g.appendChild(rect); g.appendChild(text); g.appendChild(sub);

              if (hasChildren) {
                const toggle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                toggle.setAttribute('cx', 60); toggle.setAttribute('cy', 0);
                toggle.setAttribute('r', 6); toggle.setAttribute('fill', '#374151'); toggle.setAttribute('stroke', stroke);
                toggle.style.cursor = 'pointer';

                const toggleLbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                toggleLbl.setAttribute('x', 60); toggleLbl.setAttribute('y', 3);
                toggleLbl.setAttribute('fill', '#e5e7eb'); toggleLbl.setAttribute('font-size', '9');
                toggleLbl.setAttribute('text-anchor', 'middle');
                toggleLbl.style.pointerEvents = 'none';
                toggleLbl.textContent = isCollapsed ? '+' : '-';

                toggle.onclick = (e) => { e.stopPropagation(); this.toggleNode(id); };
                g.appendChild(toggle); g.appendChild(toggleLbl);
              }
              nodesEl.appendChild(g);
          } else if (this._currentTab === 'decision') {
              g.onclick = () => { Notify.toast(n.type.toUpperCase(), (n.details || n.label).replace(/\\n/g, '<br/>'), 'info', 6000); };
              let color = '#311042'; let stroke = '#d946ef';
              if (n.type === 'incident') { color = '#1e293b'; stroke = '#64748b'; }
              else if (n.type === 'consensus') { color = '#1e3a8a'; stroke = '#3b82f6'; }
              else if (n.type === 'critic') { color = '#581c87'; stroke = '#a855f7'; }
              else if (n.type === 'evidence') { color = '#065f46'; stroke = '#10b981'; }
              else if (n.type === 'policy') { color = '#78350f'; stroke = '#f59e0b'; }
              else if (n.type === 'hitl') { color = '#7f1d1d'; stroke = '#ef4444'; }
              else if (n.type === 'final_action') { color = '#831843'; stroke = '#ec4899'; }

              const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
              rect.setAttribute('x', -55); rect.setAttribute('y', -22);
              rect.setAttribute('width', 110); rect.setAttribute('height', 44);
              rect.setAttribute('rx', 8); rect.setAttribute('fill', color); rect.setAttribute('stroke', stroke);
              rect.setAttribute('stroke-width', '1.8'); rect.setAttribute('opacity', '0.95');
              g.appendChild(rect);

              const lines = (n.label || '').split('\\n');
              lines.forEach((l, i) => {
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('text-anchor', 'middle'); text.setAttribute('dy', lines.length > 1 ? (i === 0 ? -6 : 9) : 5);
                text.setAttribute('font-size', '8'); text.setAttribute('font-family', 'Inter,sans-serif');
                text.setAttribute('font-weight', '600'); text.setAttribute('fill', 'white');
                text.textContent = l;
                g.appendChild(text);
              });
              nodesEl.appendChild(g);
          } else if (this._currentTab === 'evidence') {
              g.onclick = () => { this.selectEvidenceNode(id); };
              let color = '#0f172a'; let stroke = '#64748b';
              if (n.source === 'incident_events') { color = '#1e3a8a'; stroke = '#3b82f6'; }
              else if (n.source === 'ai_evidence_logs') { color = '#064e3b'; stroke = '#10b981'; }
              else if (n.source === 'fleet_evidence') { color = '#7c2d12'; stroke = '#f97316'; }
              else if (n.source === 'decision_graphs') { color = '#4c1d95'; stroke = '#d946ef'; }
              else if (n.source === 'incident_closure') { color = '#4c0519'; stroke = '#f43f5e'; }

              const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
              rect.setAttribute('x', -60); rect.setAttribute('y', -25);
              rect.setAttribute('width', 120); rect.setAttribute('height', 50);
              rect.setAttribute('rx', 8); rect.setAttribute('fill', color);
              rect.setAttribute('stroke', stroke); rect.setAttribute('stroke-width', isSelected ? '3.0' : '1.8');
              rect.setAttribute('opacity', '0.95');
              if(isSelected) rect.setAttribute('filter', 'url(#evidence-glow)');
              g.appendChild(rect);

              const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
              text.setAttribute('text-anchor', 'middle'); text.setAttribute('dy', -10);
              text.setAttribute('font-size', '7.5'); text.setAttribute('font-family', 'Inter,sans-serif');
              text.setAttribute('font-weight', '700'); text.setAttribute('fill', 'white');
              text.textContent = n.event_type;
              g.appendChild(text);

              const shortContent = n.content ? (n.content.length > 15 ? n.content.slice(0, 15) + '...' : n.content) : '';
              const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
              sub.setAttribute('text-anchor', 'middle'); sub.setAttribute('dy', 3);
              sub.setAttribute('font-size', '7.0'); sub.setAttribute('font-family', 'Inter,sans-serif');
              sub.setAttribute('fill', 'var(--txt2)');
              sub.textContent = shortContent;
              g.appendChild(sub);

              const meta = document.createElementNS('http://www.w3.org/2000/svg', 'text');
              meta.setAttribute('text-anchor', 'middle'); meta.setAttribute('dy', 14);
              meta.setAttribute('font-size', '6.5'); meta.setAttribute('font-family', 'Inter,sans-serif');
              meta.setAttribute('font-style', 'italic'); meta.setAttribute('fill', 'var(--txt3)');
              meta.textContent = `${n.actor} | ${n.timestamp ? n.timestamp.slice(11, 19) : ''}`;
              g.appendChild(meta);
              
              nodesEl.appendChild(g);
          }
        });
        
        LogStreamer.add('INFO', 'DAG', `Unified Workspace rendered for ${this._currentTab}. Visible: ${visibleNodes.length} nodes`);
      }
    };
"""

content = content[:start_idx] + improved_engine + "\n    " + content[end_idx:]

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
print("Engine refactored completely.")
