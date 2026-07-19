import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

engine_code = """
    /* ==================================================
       UNIFIED DAG ENGINE
    ================================================== */
    var UnifiedDAGEngine = {
      _scale: 1, _tx: 0, _ty: 0, _dragging: false, _sx: 0, _sy: 0,
      _currentInc: null,
      _cache: { causal: null, decision: null, evidence: null },
      _currentTab: 'causal',
      _collapsedNodes: new Set(),
      _incidentId: '',

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
             this._currentInc = data.incident_info;
             this.resetView();
             this._renderGraph();
             this._updateInsight(tab, data.incident_info);
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
        if(tab === 'decision') endpoint = `/api/decision_dag/${id}`;
        if(tab === 'evidence') endpoint = `/api/evidence_dag/${id}`;
        
        try {
          const resp = await fetch(endpoint);
          const res = await resp.json();
          if (res && res.status === 'success') {
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

      _updateInsight(tab, info) {
          const insight = document.getElementById('unified-dag-insight');
          const txt = document.getElementById('unified-dag-insight-txt');
          if(!insight || !txt || !info) return;
          insight.style.display = 'block';
          
          if(tab === 'causal') {
              txt.innerHTML = `Insiden ${this._incidentId} · ${info.device_name || 'Unknown'}: "${info.flag || 'ANOMALY'}" terdeteksi. AI Analysis: ${info.analysis || '-'}`;
          } else if(tab === 'decision') {
              txt.innerHTML = `AI Decision Logic for ${this._incidentId}: Policy rules evaluated with ${info.confidence || 0}% confidence`;
          } else if(tab === 'evidence') {
              txt.innerHTML = `Evidence chain for ${this._incidentId}: Cross-referenced ${info.device_name} anomalies`;
          }
      },

      expandAll() {
        this._collapsedNodes.clear();
        this._renderGraph();
      },

      collapseAll() {
        if (!this._rawNodes) return;
        this._rawNodes.forEach(n => {
          if (n.type === 'root_cause' || n.type === 'trigger') this._collapsedNodes.add(n.id);
        });
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
          let current = e.from;
          while (current) {
            if (this._collapsedNodes.has(current) && current !== e.from) return false;
            const parentEdge = edges.find(p => p.to === current);
            current = parentEdge ? parentEdge.from : null;
          }
          visibleNodeIds.add(e.from);
          visibleNodeIds.add(e.to);
          return true;
        });
        const visibleNodes = nodes.filter(n => visibleNodeIds.has(n.id) || nodes.length === 1);

        const levelMap = new Map();
        visibleNodes.forEach(n => levelMap.set(n.id, 0));
        let changed = true;
        while (changed) {
          changed = false;
          visibleEdges.forEach(e => {
            const fromLvl = levelMap.get(e.from) || 0;
            const toLvl = levelMap.get(e.to) || 0;
            if (fromLvl >= toLvl) { levelMap.set(e.to, fromLvl + 1); changed = true; }
          });
        }

        const levelCounts = {};
        visibleNodes.forEach(n => {
          const lvl = levelMap.get(n.id) || 0;
          levelCounts[lvl] = (levelCounts[lvl] || 0) + 1;
        });

        const nodePos = new Map();
        const levelY = {};
        const X_SPACING = 200, Y_SPACING = 80;

        visibleNodes.forEach(n => {
          const lvl = levelMap.get(n.id) || 0;
          const idx = levelY[lvl] || 0;
          levelY[lvl] = idx + 1;
          const total = levelCounts[lvl];
          const x = 100 + lvl * X_SPACING;
          const y = 160 + (idx - (total - 1) / 2) * Y_SPACING;
          nodePos.set(n.id, { x, y });
        });

        edgesEl.innerHTML = '';
        visibleEdges.forEach(e => {
          const f = nodePos.get(e.from);
          const t = nodePos.get(e.to);
          if (!f || !t) return;

          const dx = t.x - f.x, dy = t.y - f.y;
          const len = Math.sqrt(dx * dx + dy * dy);
          if (len === 0) return;

          const nx = dx / len, ny = dy / len;
          const startX = f.x + nx * 15, startY = f.y + ny * 15;
          const endX = t.x - nx * 20, endY = t.y - ny * 20;
          
          let stroke = '#4b5563';
          if(this._currentTab === 'decision') stroke = '#831843';
          if(this._currentTab === 'evidence') stroke = '#14532d';

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
        });

        nodesEl.innerHTML = '';
        visibleNodes.forEach(n => {
          const p = nodePos.get(n.id);
          const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
          g.setAttribute('class', 'dag-node');
          g.setAttribute('transform', `translate(${p.x},${p.y})`);
          g.style.cursor = 'pointer';

          let fill = '#1f2937', stroke = '#4b5563', glow = '';
          if (n.type === 'root_cause' || n.type === 'trigger') { fill = '#312e81'; stroke = '#6366f1'; glow = 'url(#glow)'; }
          if (n.type === 'blast_radius' || n.type === 'risk') { fill = '#450a0a'; stroke = '#ef4444'; }
          if (n.type === 'healthy' || n.type === 'evidence') { fill = '#064e3b'; stroke = '#10b981'; }
          
          if(this._currentTab === 'decision') {
              if (n.type === 'action' || n.type === 'policy') { fill = '#4a044e'; stroke = '#d946ef'; glow = 'url(#decision-glow)'; }
              if (n.type === 'human') { fill = '#422006'; stroke = '#f97316'; }
          }

          const hasChildren = edges.some(e => e.from === n.id);
          const isCollapsed = this._collapsedNodes.has(n.id);

          const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('x', -60); rect.setAttribute('y', -18);
          rect.setAttribute('width', 120); rect.setAttribute('height', 36);
          rect.setAttribute('rx', 6);
          rect.setAttribute('fill', fill);
          rect.setAttribute('stroke', stroke);
          rect.setAttribute('stroke-width', '1.5');
          if (glow) rect.setAttribute('filter', glow);
          
          const iconMap = {
            root_cause: '⚡', blast_radius: '💥', healthy: '✅', device: '🖥️', metric: '📊',
            trigger: '🔔', action: '🛠️', condition: '🤔', human: '👤', policy: '📜',
            evidence: '📄', log: '📝'
          };
          const icon = iconMap[n.type] || '⏺';

          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('y', -2); text.setAttribute('fill', '#e5e7eb');
          text.setAttribute('font-size', '10'); text.setAttribute('text-anchor', 'middle');
          text.setAttribute('font-weight', '500');
          text.textContent = `${icon} ${n.label || n.id}`;

          const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          sub.setAttribute('y', 10); sub.setAttribute('fill', '#9ca3af');
          sub.setAttribute('font-size', '8'); sub.setAttribute('text-anchor', 'middle');
          sub.textContent = n.details ? (n.details.length > 20 ? n.details.substring(0, 20) + '...' : n.details) : '';

          g.appendChild(rect);
          g.appendChild(text);
          g.appendChild(sub);

          if (hasChildren) {
            const toggle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            toggle.setAttribute('cx', 60); toggle.setAttribute('cy', 0);
            toggle.setAttribute('r', 6);
            toggle.setAttribute('fill', '#374151');
            toggle.setAttribute('stroke', stroke);
            toggle.style.cursor = 'pointer';

            const toggleLbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            toggleLbl.setAttribute('x', 60); toggleLbl.setAttribute('y', 3);
            toggleLbl.setAttribute('fill', '#e5e7eb'); toggleLbl.setAttribute('font-size', '9');
            toggleLbl.setAttribute('text-anchor', 'middle');
            toggleLbl.style.pointerEvents = 'none';
            toggleLbl.textContent = isCollapsed ? '+' : '-';

            toggle.onclick = (e) => {
              e.stopPropagation();
              if (isCollapsed) this._collapsedNodes.delete(n.id);
              else this._collapsedNodes.add(n.id);
              this._renderGraph();
            };

            g.appendChild(toggle);
            g.appendChild(toggleLbl);
          }
          nodesEl.appendChild(g);
        });
      }
    };
"""

# Insert UnifiedDAGEngine right after DAGEngine definition
if "var UnifiedDAGEngine =" not in content:
    content = content.replace("var DAGEngine = {", engine_code + "\n    var DAGEngine = {")

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
print("UnifiedDAGEngine injected.")
