/* modules/5_security_governance/evidence.js
 * Atomic Design — 3. Modules Layer (5_security_governance / evidence)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["5_security_governance"] = window.Modules["5_security_governance"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      evidence: {
        _network: null,
        _lastPayload: null,
        _lastDetail: null,
        _activeStatusFilter: 'ALL',
        _activeQueryFilter: '',
        _STATUS_TAG: {
          'PASS': 'tag-green', 'CONFLICT': 'tag-red', 'STALE': 'tag-orange',
          'DUPLICATE': 'tag-gray', 'NEED MORE': 'tag-blue', 'REJECTED': 'tag-red'
        },
        _LEVEL_STYLE: {
          ok: { color: 'var(--green)', icon: 'fa-check-circle' },
          warning: { color: 'var(--orange)', icon: 'fa-triangle-exclamation' },
          critical: { color: 'var(--red)', icon: 'fa-ban' },
          none: { color: 'var(--text-gray)', icon: 'fa-circle-question' }
        },
        _esc(v) {
          return String(v === undefined || v === null ? '' : v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        },
        _num(v) {
          const n = Number(v);
          return Number.isFinite(n) ? n : 0;
        },
        _data() {
          return window.Services.Data || (typeof DataService !== 'undefined' ? DataService : null);
        },
        _notify() {
          return (window.UI && window.UI.Atoms && window.UI.Atoms.Notify) || (typeof Notify !== 'undefined' ? Notify : null);
        },
        async load() {
          return this.refresh();
        },
        async refresh() {
          const tbody = document.getElementById('tbody-evidence-explorer');
          if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-gray)"><i class="fa-solid fa-spinner fa-spin"></i> Memuat jejak bukti nyata...</td></tr>';
          }
          const svc = this._data();
          if (!svc) return;
          try {
            const res = await svc.fetch('/api/evidence_explorer');
            if (!res) throw new Error('Empty response');
            this._lastPayload = res;
            this.renderReadiness(res.readiness || {});
            this.renderStats(res.stats || {});
            this.renderCollectors(res.collectors || []);
            this.renderLogs(res.logs || []);
            this.drawGraph(res.graph);
          } catch (e) {
            console.error('Failed to fetch evidence explorer data:', e);
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--red)">Gagal terhubung ke Evidence Engine: ${this._esc(e.message)}</td></tr>`;
            this.renderReadiness({ status: 'EVIDENCE ENGINE UNREACHABLE', level: 'critical', reason: 'Tidak dapat mengambil data /api/evidence_explorer.' });
          }
        },
        renderReadiness(r) {
          const lvl = this._LEVEL_STYLE[r.level] || this._LEVEL_STYLE.none;
          const statusEl = document.getElementById('ev-readiness-status');
          if (statusEl) {
            statusEl.style.color = lvl.color;
            statusEl.innerHTML = `<i class="fa-solid ${lvl.icon}" style="margin-right:8px;"></i>${this._esc(r.status || 'NO EVIDENCE DATA')}`;
          }
          const card = document.getElementById('ev-readiness-card');
          if (card) card.style.borderLeftColor = lvl.color;
          setEl('ev-readiness-reason', r.reason || '—');
          setEl('ev-ready-quality', r.quality || '—');
          setEl('ev-ready-conf', r.confidence || '—');
          setEl('ev-ready-conflicts', r.conflicts !== undefined ? r.conflicts : '—');
          setEl('ev-ready-missing', r.missing !== undefined ? r.missing : '—');
        },
        renderStats(st) {
          setEl('gt-val-pct', st.validated_pct || '—');
          setEl('gt-conf-pct', st.conflict_pct || '—');
          setEl('gt-need-pct', st.need_more_pct || '—');
          setEl('gt-rej-pct', st.rejected_pct || '—');
          const dist = Array.isArray(st.osi_distribution) ? st.osi_distribution : [];
          htmlEl('gt-osi-dist', dist.length
            ? dist.map(d => `<span class="tag tag-blue" style="font-size:11px;">${this._esc(d)}</span>`).join('')
            : '<span class="tag" style="border:1px solid var(--border); background:transparent;">Belum ada insiden 7 hari terakhir</span>');
          const p = st.pipeline || {};
          const map = {
            'ev-pipe-raw': p.raw, 'ev-pipe-normalized': p.normalized, 'ev-pipe-validated': p.validated,
            'ev-pipe-pass': p.pass, 'ev-pipe-conflict': p.conflict, 'ev-pipe-stale': p.stale,
            'ev-pipe-duplicate': p.duplicate, 'ev-pipe-needmore': p.need_more
          };
          Object.keys(map).forEach(id => setEl(id, map[id] !== undefined ? map[id] : '—'));
        },
        renderCollectors(collectors) {
          if (!collectors.length) {
            htmlEl('tbody-collector-perf', '<tr><td colspan="4" style="text-align:center;color:var(--text-gray)">Belum ada data collector</td></tr>');
            return;
          }
          htmlEl('tbody-collector-perf', collectors.map(c => {
            const tag = c.status === 'Healthy' ? 'tag-green' : c.status === 'Warning' ? 'tag-orange' : c.status === 'No Data' ? 'tag-gray' : 'tag-red';
            const rate = c.status === 'No Data' ? '—' : `${this._num(c.success_rate).toFixed(1)}%`;
            return `
              <tr title="${this._esc(c.detail)}">
                <td><b>${this._esc(c.name)}</b></td>
                <td><span class="tag ${tag}">${this._esc(c.status)}</span></td>
                <td><b style="color:var(--green2)">${rate}</b></td>
                <td><small style="color:var(--txt3)">${this._esc(c.last_seen)}</small></td>
              </tr>`;
          }).join(''));
        },
        filterByStatus(status) {
          this._activeStatusFilter = status || 'ALL';
          const sel = document.getElementById('ev-filter-status');
          if (sel && sel.value !== this._activeStatusFilter) sel.value = this._activeStatusFilter;
          this.renderLogs((this._lastPayload && this._lastPayload.logs) || []);
        },
        filterByQuery(query) {
          this._activeQueryFilter = String(query || '').trim().toLowerCase();
          this.renderLogs((this._lastPayload && this._lastPayload.logs) || []);
        },
        exportBundle() {
          const bundle = this._lastDetail || this._lastPayload;
          const n = this._notify();
          if (!bundle) {
            if (n && n.toast) n.toast('⚠️ Export Evidence', 'Belum ada data bukti untuk diekspor.', 'warn', 3000);
            return;
          }
          const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          const incTag = (this._lastDetail && this._lastDetail.incident && this._lastDetail.incident.incident_id)
            ? `inc_${this._lastDetail.incident.incident_id}` : 'all';
          a.href = url;
          a.download = `evidence_audit_bundle_${incTag}_${Date.now()}.json`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          if (n && n.toast) n.toast('✅ Evidence Bundle Exported', `Paket bukti forensik (${incTag}) berhasil diunduh.`, 'ok', 3500);
        },
        renderLogs(logs) {
          const filtered = (logs || []).filter(l => {
            if (this._activeStatusFilter && this._activeStatusFilter !== 'ALL' && l.status !== this._activeStatusFilter) {
              return false;
            }
            if (this._activeQueryFilter) {
              const hay = `${l.trace_id || ''} ${l.source || ''} ${l.host || ''} ${l.status || ''} ${l.decision_reason || ''}`.toLowerCase();
              if (!hay.includes(this._activeQueryFilter)) return false;
            }
            return true;
          });
          if (!filtered.length) {
            htmlEl('tbody-evidence-explorer', '<tr><td colspan="8" style="text-align:center;color:var(--text-gray)">Belum ada jejak bukti yang cocok dengan filter</td></tr>');
            return;
          }
          htmlEl('tbody-evidence-explorer', filtered.map(l => {
            const clickable = l.incident_id ? `style="cursor:pointer" onclick="Panels.evidence.showDetail('${this._esc(l.incident_id)}')"` : '';
            return `
              <tr ${clickable}>
                <td><code style="font-size:11px;color:var(--purple2)">${this._esc(l.trace_id)}</code></td>
                <td><span class="tag tag-blue">${this._esc(l.source)}</span></td>
                <td><b>${this._esc(l.host)}</b></td>
                <td><span class="tag ${this._STATUS_TAG[l.status] || 'tag-gray'}">${this._esc(l.status)}</span></td>
                <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${this._esc(l.decision_reason)}">${this._esc(l.decision_reason)}</td>
                <td><b style="color:var(--green2)">${this._num(l.quality).toFixed(0)}%</b></td>
                <td><b style="color:var(--blue2)">${this._num(l.confidence).toFixed(0)}%</b></td>
                <td><small style="color:var(--txt3)">${this._esc(l.age)}</small></td>
              </tr>`;
          }).join(''));
        },
        async showDetail(incidentId) {
          const card = document.getElementById('card-evidence-detail');
          const tl = document.getElementById('evidence-timeline-container');
          const tb = document.getElementById('evidence-audit-detail-tbody');
          if (!card || !tl || !tb) return;
          card.style.display = 'block';
          tl.innerHTML = '<div style="color:var(--text-gray)"><i class="fa-solid fa-spinner fa-spin"></i> Memuat timeline...</div>';
          tb.innerHTML = '';
          const svc = this._data();
          try {
            const res = await svc.fetch('/api/evidence_explorer/' + encodeURIComponent(incidentId));
            if (!res || res.status !== 'success') throw new Error((res && res.message) || 'Detail tidak tersedia');
            this._lastDetail = res;
            const timeline = Array.isArray(res.timeline) ? res.timeline : [];
            tl.innerHTML = timeline.length ? timeline.map(t => {
              const isExec = /EXECUTION_EVIDENCE|AUTO_MITIGATE|ACTION_EXECUTED/.test(t.type || '');
              const isPost = /POST_REMEDIATION_EVIDENCE|VERIFICATION_SUCCESS/.test(t.type || '');
              const color = isPost ? 'var(--green)' : isExec ? 'var(--blue)' : 'var(--purple)';
              return `
                <div style="position:relative;">
                  <span style="position:absolute;left:-27px;top:3px;width:12px;height:12px;border-radius:50%;background:${color};"></span>
                  <div style="font-size:11px;color:var(--txt3)">${this._esc(new Date(t.at).toLocaleString('id-ID'))} · ${this._esc(t.source)}</div>
                  <div style="font-weight:600;color:${color}">${this._esc(t.type)}</div>
                  <div style="font-size:12px;color:var(--txt2);word-break:break-word">${this._esc(t.summary)}</div>
                </div>`;
            }).join('') : '<div style="color:var(--text-gray)">Belum ada event pada timeline insiden ini.</div>';

            const inc = res.incident || {};
            const state = res.state || {};
            const r6 = res.rule6 || {};
            const fmt = v => (v ? new Date(v).toLocaleString('id-ID') : '—');
            const r6ok = r6.bound || r6.decision_passed;
            const rows = [
              ['Incident', `#${inc.incident_id} · ${inc.device_name || '—'}`],
              ['Flag / Layer', `${inc.flag || '—'} · L${inc.layer || '?'}`],
              ['Confidence', inc.confidence !== undefined && inc.confidence !== null ? `${(this._num(inc.confidence) <= 1 ? this._num(inc.confidence) * 100 : this._num(inc.confidence)).toFixed(0)}%` : '—'],
              ['State (incident_states)', state.status || inc.raw_status || '—'],
              ['Verification Time', fmt(inc.verification_time)],
              ['T_exec (execution_evidence)', fmt(r6.exec_at)],
              ['T_post (post_remediation_evidence)', fmt(r6.post_at)],
              ['HITL Approvals', res.approvals !== undefined ? res.approvals : 0],
              ['Audit Hash (SHA-256)', res.audit_hash ? `${res.audit_hash.slice(0, 24)}…` : '—'],
              ['Evidence', inc.evidence || '—']
            ];
            tb.innerHTML = rows.map(([k, v]) => `<tr><td style="color:var(--txt3);padding:4px 8px;white-space:nowrap">${this._esc(k)}</td><td style="padding:4px 8px;word-break:break-word">${this._esc(v)}</td></tr>`).join('') +
              `<tr><td style="color:var(--txt3);padding:4px 8px">Governance Rule #6</td><td style="padding:4px 8px"><span class="tag ${r6ok ? 'tag-green' : 'tag-red'}">${r6ok ? 'SATISFIED' : 'NOT SATISFIED'}</span> <small>${this._esc(r6.verdict || '')}</small></td></tr>`;
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
          } catch (e) {
            tl.innerHTML = `<div style="color:var(--red)">Gagal memuat detail: ${this._esc(e.message)}</div>`;
            const n = this._notify();
            if (n && n.toast) n.toast('❌ Evidence Detail', e.message, 'err', 4000);
          }
        },
        drawGraph(graphData) {
          const container = document.getElementById('evidence-network-map');
          if (!container) return;
          if (this._network) { this._network.destroy(); this._network = null; }

          const rawNodes = (graphData && Array.isArray(graphData.nodes)) ? graphData.nodes : [];
          const rawEdges = (graphData && Array.isArray(graphData.edges)) ? graphData.edges : [];

          if (rawNodes.length === 0) {
            container.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-gray);font-weight:600;"><i class="fa-solid fa-circle-info" style="margin-right:8px"></i> Belum ada relasi bukti</div>';
            return;
          }

          if (typeof vis === 'undefined') {
            container.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-gray);font-weight:600;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:8px"></i> Library visualisasi (vis-network) tidak tersedia</div>';
            return;
          }
          container.innerHTML = '';

          const nodes = new vis.DataSet(rawNodes);
          const edges = new vis.DataSet(rawEdges.map(e => ({ ...e, font: { size: 10, align: 'middle', color: '#94a3b8' } })));
          const options = {
            layout: { hierarchical: { direction: 'UD', sortMethod: 'directed', nodeSpacing: 150, levelSeparation: 100 } },
            physics: false,
            interaction: { zoomView: true, dragView: true }
          };
          this._network = new vis.Network(container, { nodes, edges }, options);
          this._network.on('selectNode', (params) => {
            const node = params.nodes.length ? nodes.get(params.nodes[0]) : null;
            if (node && node.incident_id) this.showDetail(node.incident_id);
          });
        }
      },

      /* ---- KNOWLEDGE GRAPH ---- */
      kgraph: {
        _network: null,
        _graphData: null,
        _notify() {
          return (window.UI && window.UI.Atoms && window.UI.Atoms.Notify) || (typeof Notify !== 'undefined' ? Notify : null);
        },
        async load() {
          try {
            const res = await (window.Services.Data || DataService).fetch('/api/knowledge_graph');
            if (res) {
              this._graphData = res;
              if (res.metrics) {
                setEl('kg-nodes', Number(res.metrics.nodes || 0).toLocaleString());
                setEl('kg-edges', Number(res.metrics.relationships || 0).toLocaleString());
                setEl('kg-criticality', Number(res.metrics.critical || 0).toLocaleString());
                setEl('kg-coverage', res.metrics.coverage || '—');
              }
              if (res.topology && res.topology.version) {
                setEl('kg-version-tag', res.topology.version);
              }
              this.drawGraph(res);
              this.renderRcaPath(res.rca_path || []);
            }
          } catch (e) {
            console.error('Failed to load Knowledge Graph:', e);
          }
        },
        drawGraph(res) {
          const container = document.getElementById('kgraph-network-map');
          if (!container) return;
          if (this._network) { this._network.destroy(); this._network = null; }

          const nodesData = (res && res.graph && Array.isArray(res.graph.nodes)) ? res.graph.nodes : [];
          const edgesData = (res && res.graph && Array.isArray(res.graph.edges)) ? res.graph.edges : [];

          if (nodesData.length === 0) {
            container.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-gray);font-weight:600;"><i class="fa-solid fa-circle-info" style="margin-right:8px"></i> Belum ada node Knowledge Graph</div>';
            return;
          }

          if (typeof vis === 'undefined') {
            container.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:var(--text-gray);font-weight:600;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:8px"></i> Library visualisasi (vis-network) tidak tersedia</div>';
            return;
          }
          container.innerHTML = '';

          const nodes = new vis.DataSet(nodesData.map(n => ({
            id: n.id,
            label: (n.label || n.id).replace(/\\n/g, '\n'),
            shape: n.shape || 'box',
            color: n.color || '#3b82f6',
            font: { color: '#ffffff' }
          })));

          const edges = new vis.DataSet(edgesData.map(e => ({
            from: e.from,
            to: e.to,
            arrows: 'to',
            label: (e.label || e.relationship || '').replace(/\\n/g, '\n'),
            font: { size: 10, align: 'middle', color: '#94a3b8' }
          })));

          const data = { nodes, edges };
          const options = {
            layout: { hierarchical: { direction: 'UD', sortMethod: 'directed', nodeSpacing: 150, levelSeparation: 100 } },
            physics: false,
            interaction: { zoomView: true, dragView: true }
          };

          this._network = new vis.Network(container, data, options);

          this._network.on("selectNode", (params) => {
            if (params.nodes.length > 0) {
              const nodeId = params.nodes[0];
              const node = nodes.get(nodeId);
              const impactPanel = document.getElementById('kg-impact-panel');
              if (impactPanel) impactPanel.style.display = 'block';
              setEl('kg-sel-node', node ? node.label.replace(/\n/g, ' ') : nodeId);
              const downstream = edgesData.filter(e => e.from === nodeId).map(e => e.to);
              const upstream = edgesData.filter(e => e.to === nodeId).map(e => e.from);
              setEl('kg-blast-radius', downstream.length ? `${downstream.length} node terdampak (${downstream.join(', ')})` : '0 node hilir');
              setEl('kg-upstream', upstream.length ? upstream.join(', ') : 'Root / Mandiri');
              setEl('kg-missing', (downstream.length === 0 && upstream.length === 0) ? 'Node terisolasi — jalankan Sync Topology untuk memperbarui relasi.' : 'Topologi terhubung penuh.');
            }
          });
        },
        renderRcaPath(pathData) {
          const rcaPath = document.getElementById('kg-rca-path');
          if (!rcaPath) return;
          if (!Array.isArray(pathData) || pathData.length === 0) {
            rcaPath.innerHTML = '<div style="color:var(--text-gray)">Belum ada jalur RCA aktif.</div>';
            return;
          }
          rcaPath.innerHTML = pathData.map(item => `
            <div style="padding:4px; border-left:2px solid ${item.status === 'CRITICAL' ? 'var(--red)' : 'var(--blue)'}; ${item.status === 'CRITICAL' ? 'background:rgba(239,68,68,0.1);' : ''}">
              ${item.status === 'CRITICAL' ? '<b>' + item.node + ' (' + item.relationship + ')</b>' : item.node}
            </div>
            ${item.relationship && item.status !== 'CRITICAL' ? `<div style="padding:0 0 0 10px; color:var(--text-gray);"><i class="fa-solid fa-arrow-down"></i> <span style="font-size:0.75rem">${item.relationship}</span></div>` : ''}
          `).join('');
        },
        openRollbackModal() {
          const n = this._notify();
          if (n && n.toast) n.toast('🕒 Topology Snapshot', 'Mengambil versi stabil terakhir dari Knowledge Graph...', 'info', 3000);
          this.load();
        },
        async triggerDiscovery() {
          const n = this._notify();
          try {
            if (n && n.toast) n.toast('📡 Discovery Triggered', 'Initiating live network & topology discovery scan...', 'info', 3000);
            const res = await (window.Services.Data || DataService).fetch('/api/knowledge_graph/discovery', { method: 'POST' });
            if (res && res.status === 'success') {
              if (n && n.toast) n.toast('✅ Discovery Complete', res.message, 'ok', 4000);
              this.load();
            }
          } catch (e) {
            console.error('Failed to trigger discovery:', e);
            if (n && n.toast) n.toast('❌ Error', e.message, 'err', 4000);
          }
        }
      },

      /* ---- SOP ---- */

});
window.Modules["5_security_governance"]["evidence"] = window.Panels;
