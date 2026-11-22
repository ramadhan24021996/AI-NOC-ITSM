/* modules/4_ai_lifecycle/playbooks.js
 * Atomic Design — 3. Modules Layer (4_ai_lifecycle / playbooks)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,EventBus}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["4_ai_lifecycle"] = window.Modules["4_ai_lifecycle"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      playbooks: {
        _data: [],
        _catalogData: [],
        _activeTab: 'exec',
        _catOffset: 0,
        _catTotal: 0,
        _filterTimer: null,
        _autoRefreshTimer: null,
        _wsInitialized: false,
        _delegationBound: false,

        _esc(val) {
          if (typeof window._esc === 'function') return window._esc(val);
          return String(val ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        },

        _getToken() {
          return sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || '';
        },

        async _authFetch(url, options = {}) {
          const token = this._getToken();
          const headers = Object.assign({}, options.headers || {});
          if (token) {
            if (!headers['Authorization']) headers['Authorization'] = `Bearer ${token}`;
            if (!headers['X-CSRF-Token']) headers['X-CSRF-Token'] = token;
          }
          if (options.body && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
          }
          return fetch(url, Object.assign({}, options, { headers }));
        },

        init() {
          this._bindDelegatedEvents();
          this._initWSListeners();
          this._syncWsBadge();
        },

        _bindDelegatedEvents() {
          if (this._delegationBound) return;
          const tbodyExec = document.getElementById('tbody-playbooks');
          const tbodyCat = document.getElementById('tbody-playbooks-catalog');

          if (tbodyExec) {
            tbodyExec.addEventListener('click', (e) => {
              const btn = e.target.closest('[data-pb-action]');
              if (!btn) return;
              const action = btn.getAttribute('data-pb-action');
              const id = parseInt(btn.getAttribute('data-pb-id') || '0', 10);
              if (!id) return;
              if (action === 'preview') this.previewScript(id, 'exec');
              else if (action === 'dryrun') this.execute(id, true);
              else if (action === 'run') this.openExecuteModal(id);
              else if (action === 'edit') this.openEditor(id);
              else if (action === 'delete') this.confirmDelete(id);
            });
          }

          if (tbodyCat) {
            tbodyCat.addEventListener('click', (e) => {
              const btn = e.target.closest('[data-cat-action]');
              if (!btn) return;
              const action = btn.getAttribute('data-cat-action');
              const id = parseInt(btn.getAttribute('data-cat-id') || '0', 10);
              if (!id) return;
              if (action === 'preview') this.previewScript(id, 'catalog');
              else if (action === 'promote') this.promoteCatalog(id);
            });
          }

          if (tbodyExec && tbodyCat) {
            this._delegationBound = true;
          }
        },

        _initWSListeners() {
          if (this._wsInitialized) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._wsInitialized = true;

          bus.on('ws:status', (s) => this._syncWsBadge(s));
          bus.on('ws:connected', () => this._syncWsBadge('online'));
          bus.on('ws:disconnected', () => this._syncWsBadge('offline'));
          bus.on('playbook:updated', () => {
            if (!document.getElementById('p-playbooks')?.classList.contains('active')) return;
            const modalOverlay = document.getElementById('modal-overlay');
            if (modalOverlay && !modalOverlay.classList.contains('hidden')) return;
            this.load(false);
          });
        },

        _syncWsBadge(explicitState) {
          const badge = document.getElementById('pb-ws-badge');
          if (!badge) return;
          let state = explicitState;
          if (!state) {
            const ws = (window.Services && window.Services.WS) || (typeof WSService !== 'undefined' ? WSService : null);
            const sock = ws && ws.socket;
            if (sock && sock.readyState === WebSocket.OPEN) state = 'online';
            else if (sock && sock.readyState === WebSocket.CONNECTING) state = 'connecting';
            else state = 'offline';
          }
          if (state === 'online') {
            badge.className = 'badge bd-gr';
            badge.innerHTML = '<i class="fa-solid fa-signal" style="margin-right:4px"></i>WS Live Active';
          } else if (state === 'connecting') {
            badge.className = 'badge bd-or';
            badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="margin-right:4px"></i>WS Connecting...';
          } else {
            badge.className = 'badge bd-rd';
            badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="margin-right:4px"></i>WS Offline';
          }
        },

        startAutoRefresh() {
          this.init();
          this.stopAutoRefresh();
          this._autoRefreshTimer = setInterval(() => {
            if (document.hidden) return;
            if (!document.getElementById('p-playbooks')?.classList.contains('active')) return;
            const modalOverlay = document.getElementById('modal-overlay');
            if (modalOverlay && !modalOverlay.classList.contains('hidden')) return;
            const activeEl = document.activeElement;
            if (activeEl && activeEl.id === 'pb-search-inp') return;
            this.load(false);
          }, 15000);
        },

        stopAutoRefresh() {
          if (this._autoRefreshTimer) {
            clearInterval(this._autoRefreshTimer);
            this._autoRefreshTimer = null;
          }
          if (this._filterTimer) {
            clearTimeout(this._filterTimer);
            this._filterTimer = null;
          }
        },

        switchTab(tab) {
          this._activeTab = tab === 'catalog' ? 'catalog' : 'exec';
          const execPane = document.getElementById('pb-pane-exec');
          const catPane = document.getElementById('pb-pane-catalog');
          const execBtn = document.getElementById('pb-tab-exec');
          const catBtn = document.getElementById('pb-tab-catalog');
          if (execPane) execPane.style.display = this._activeTab === 'exec' ? 'block' : 'none';
          if (catPane) catPane.style.display = this._activeTab === 'catalog' ? 'block' : 'none';
          if (execBtn) execBtn.className = `btn btn-sm ${this._activeTab === 'exec' ? 'btn-primary' : 'btn-ghost'}`;
          if (catBtn) catBtn.className = `btn btn-sm ${this._activeTab === 'catalog' ? 'btn-primary' : 'btn-ghost'}`;
          this.load(true);
        },

        onFilterChange() {
          this._catOffset = 0;
          if (this._filterTimer) clearTimeout(this._filterTimer);
          this._filterTimer = setTimeout(() => {
            this.load(true);
          }, 260);
        },

        prevCatalogPage() {
          if (this._catOffset <= 0) return;
          this._catOffset = Math.max(0, this._catOffset - 50);
          this.load(true);
        },

        nextCatalogPage() {
          if (this._catOffset + 50 >= this._catTotal) return;
          this._catOffset += 50;
          this.load(true);
        },

        _getFilterQueryString(includeCatalogPaging = false) {
          const search = (document.getElementById('pb-search-inp')?.value || '').trim();
          const layer = (document.getElementById('pb-layer-select')?.value || '').trim();
          const status = (document.getElementById('pb-status-select')?.value || '').trim();
          const params = new URLSearchParams();
          if (search) params.set('search', search);
          if (layer) params.set('layer', layer);
          if (status) params.set('status', status);
          if (includeCatalogPaging) {
            params.set('limit', '50');
            params.set('offset', String(this._catOffset));
          }
          return params.toString();
        },

        async load(showSpinner = true) {
          this.init();
          const qs = this._getFilterQueryString(false);
          const catQs = this._getFilterQueryString(true);

          const tbody = document.getElementById('tbody-playbooks');
          if (tbody && showSpinner && this._data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--txt3)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Playbooks...</div></td></tr>';
          }

          try {
            const [execResp, catResp] = await Promise.all([
              this._authFetch(`/api/playbooks${qs ? '?' + qs : ''}`),
              this._authFetch(`/api/playbooks/catalog${catQs ? '?' + catQs : ''}`)
            ]);

            if (catResp.ok) {
              const catJson = await catResp.json();
              this._updateCatalogAndKPIs(catJson);
            }

            if (!execResp.ok) {
              throw new Error(`HTTP ${execResp.status}`);
            }
            const playbooks = await execResp.json();
            this._data = Array.isArray(playbooks) ? playbooks : [];
            this._renderExecTable(this._data);
          } catch (err) {
            if (tbody) {
              tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat playbook: ${this._esc(err.message)}</td></tr>`;
            }
          }
        },

        _updateCatalogAndKPIs(catJson) {
          if (!catJson) return;
          const aiTotal = Number(catJson.ai_playbooks_total || 0);
          const aiActive = Number(catJson.ai_playbooks_active || 0);
          const okTotal = Number(catJson.rlof_success_total || 0);
          const failTotal = Number(catJson.rlof_fail_total || 0);
          const golden = Number(catJson.golden_count || 0);
          const draft = Number(catJson.draft_count || 0);
          const filteredCatalogTotal = Number(catJson.total || 0);

          setEl('pb-kpi-total', aiTotal);
          setEl('pb-kpi-active', aiActive);
          setEl('pb-kpi-rlof', `${okTotal} / ${failTotal}`);
          const totalRuns = okTotal + failTotal;
          const winRate = totalRuns > 0 ? ((okTotal / totalRuns) * 100).toFixed(1) + '%' : '0.0%';
          setEl('pb-kpi-rlof-sub', `Win Rate: ${winRate} (Closed-Loop Rule #6)`);
          setEl('pb-kpi-catalog', (golden + draft).toLocaleString('id-ID'));
          setEl('pb-kpi-catalog-sub', `${golden.toLocaleString('id-ID')} GOLDEN · ${draft} Draft`);
          setEl('pb-catalog-tab-count', filteredCatalogTotal.toLocaleString('id-ID'));

          this._catTotal = filteredCatalogTotal;
          const catalogRows = Array.isArray(catJson.data) ? catJson.data : [];
          if (catalogRows.length === 0 && this._catOffset > 0 && this._catTotal > 0) {
            this._catOffset = 0;
            this.load(false);
            return;
          }
          this._catalogData = catalogRows;
          this._renderCatalogTable(catalogRows);
        },

        _renderExecTable(playbooks) {
          const tbody = document.getElementById('tbody-playbooks');
          if (!tbody) return;

          if (!playbooks || playbooks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:25px;color:var(--txt3)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block"></i>Belum ada Playbook sesuai filter</td></tr>';
            return;
          }

          tbody.innerHTML = playbooks.map(p => {
            const id = parseInt(p.playbook_id, 10) || 0;
            const succ = parseInt(p.success_count, 10) || 0;
            const fail = parseInt(p.fail_count, 10) || 0;
            const bayesianPct = Math.round(((succ + 1) / (succ + fail + 2)) * 100);
            const rawConf = Number(p.confidence_score || 0);
            const status = String(p.status || 'ACTIVE').toUpperCase();
            const statusCls = status === 'ACTIVE' ? 'tag-green' : status === 'DISABLED' ? 'tag-red' : 'tag-orange';
            const scriptLine = this._esc(String(p.script || '').replace(/\s+/g, ' ').trim());

            return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
              <td><b>#${id}</b></td>
              <td><div style="font-weight:600;color:var(--txt1)">${this._esc(p.name)}</div></td>
              <td>
                <div style="font-size:11px;color:var(--txt2);max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${this._esc(p.description || '')}">${this._esc(p.description || '-')}</div>
                <code style="font-size:10px;color:var(--cyan2);display:block;max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px" title="${scriptLine}">${scriptLine || '-'}</code>
              </td>
              <td style="text-align:center"><span class="tag tag-cyan">L${parseInt(p.target_layer, 10) || 1}</span></td>
              <td style="text-align:center">
                <div style="font-size:11px;font-weight:700;color:${bayesianPct >= 75 ? 'var(--green2)' : 'var(--orange2)'}">${bayesianPct}% Reliabilitas</div>
                <div style="font-size:9.5px;color:var(--txt3)" title="Stored decay score: ${rawConf.toFixed(2)}">${succ} ok · ${fail} fail</div>
              </td>
              <td style="text-align:center"><span class="tag ${statusCls}">${this._esc(status)}</span></td>
              <td style="text-align:right;white-space:nowrap">
                <button type="button" class="btn btn-ghost btn-xs" data-pb-action="preview" data-pb-id="${id}" title="Preview Script"><i class="fa-solid fa-eye"></i></button>
                <button type="button" class="btn btn-ghost btn-xs" data-pb-action="dryrun" data-pb-id="${id}" style="color:var(--cyan2)" title="Dry-Run Sandbox Check"><i class="fa-solid fa-flask"></i> Dry</button>
                <button type="button" class="btn btn-ghost btn-xs" data-pb-action="run" data-pb-id="${id}" style="color:var(--green2)" title="Dispatch Playbook (Rule #6)"><i class="fa-solid fa-bolt"></i> Run</button>
                <button type="button" class="btn btn-ghost btn-xs" data-pb-action="edit" data-pb-id="${id}" title="Edit Playbook"><i class="fa-solid fa-pen"></i></button>
                <button type="button" class="btn btn-ghost btn-xs" data-pb-action="delete" data-pb-id="${id}" style="color:var(--red)" title="Hapus Playbook"><i class="fa-solid fa-trash"></i></button>
              </td>
            </tr>`;
          }).join('');
        },

        _renderCatalogTable(rows) {
          const tbody = document.getElementById('tbody-playbooks-catalog');
          const infoEl = document.getElementById('pb-cat-page-info');
          const prevBtn = document.getElementById('pb-cat-prev-btn');
          const nextBtn = document.getElementById('pb-cat-next-btn');

          if (infoEl) {
            if (!rows || rows.length === 0) {
              infoEl.textContent = 'Menampilkan 0 katalog';
            } else {
              const start = this._catOffset + 1;
              const end = this._catOffset + rows.length;
              infoEl.textContent = `Menampilkan ${start}–${end} dari ${this._catTotal.toLocaleString('id-ID')} katalog`;
            }
          }
          if (prevBtn) prevBtn.disabled = this._catOffset <= 0;
          if (nextBtn) nextBtn.disabled = (this._catOffset + 50) >= this._catTotal;

          if (!tbody) return;
          if (!rows || rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:25px;color:var(--txt3)">Tidak ada katalog playbook AI sesuai filter.</td></tr>';
            return;
          }

          tbody.innerHTML = rows.map(c => {
            const id = parseInt(c.id, 10) || 0;
            const status = String(c.status || 'ACTIVE').toUpperCase();
            const statusCls = status === 'ACTIVE' ? 'tag-green' : 'tag-orange';
            const clsTag = c.hitl_approved
              ? '<span class="tag tag-green">GOLDEN · HITL ✓</span>'
              : `<span class="tag tag-purple">${this._esc(c.classification || c.risk_level || 'DRAFT')}</span>`;

            return `<tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
              <td><b>#${id}</b></td>
              <td><div style="font-weight:600;color:var(--txt1)">${this._esc(c.name)}</div><div style="font-size:9.5px;color:var(--txt3)">${this._esc(c.source_vector_id || '')}</div></td>
              <td>
                <div style="font-size:11px;color:var(--txt2);max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${this._esc(c.description || '')}">${this._esc(c.description || '-')}</div>
                <div style="font-size:9.5px;color:var(--cyan2)">${this._esc(c.category || 'General')}</div>
              </td>
              <td style="text-align:center"><span class="tag tag-cyan">L${parseInt(c.target_layer, 10) || 4}</span></td>
              <td style="text-align:center">${clsTag}</td>
              <td style="text-align:center"><span class="tag ${statusCls}">${this._esc(status)}</span></td>
              <td style="text-align:right;white-space:nowrap">
                <button type="button" class="btn btn-ghost btn-xs" data-cat-action="preview" data-cat-id="${id}" title="Lihat SOP & Script"><i class="fa-solid fa-eye"></i> Detail</button>
                <button type="button" class="btn btn-primary btn-xs" data-cat-action="promote" data-cat-id="${id}" title="Promosikan ke Executable Playbooks Studio"><i class="fa-solid fa-arrow-up-right-from-square" style="margin-right:3px"></i>Promote</button>
              </td>
            </tr>`;
          }).join('');
        },

        previewScript(id, source = 'exec') {
          const item = source === 'catalog'
            ? (this._catalogData || []).find(x => Number(x.id) === Number(id))
            : (this._data || []).find(x => Number(x.playbook_id) === Number(id));
          if (!item) return;

          const bodyHtml = `
            <div style="display:flex;flex-direction:column;gap:10px;font-size:12px">
              <div style="color:var(--txt2)">${this._esc(item.description || 'Tidak ada deskripsi')}</div>
              <div>
                <div style="font-size:11px;font-weight:600;color:var(--cyan2);margin-bottom:4px">Script / Instruksi Remediasi:</div>
                <pre style="background:#090d16;border:1px solid var(--bd);border-radius:6px;padding:10px;font-size:11px;color:#a7f3d0;max-height:260px;overflow:auto;white-space:pre-wrap;margin:0">${this._esc(item.script || item.steps || '-')}</pre>
              </div>
            </div>
          `;
          Modal.show(`Preview Playbook #${parseInt(id, 10)} — ${this._esc(item.name)}`, bodyHtml, [
            { label: 'Tutup', cls: 'btn-ghost', fn: () => Modal.close() }
          ], '📖');
        },

        async promoteCatalog(catId) {
          Modal.confirm(
            `Promosikan Katalog #${parseInt(catId, 10)}`,
            `Salin playbook katalog #${parseInt(catId, 10)} menjadi Executable Playbook aktif di Playbook Studio?`,
            async () => {
              Modal.close();
              try {
                const resp = await this._authFetch(`/api/playbooks/promote/${parseInt(catId, 10)}`, { method: 'POST' });
                const res = await resp.json().catch(() => ({}));
                if (resp.ok && res.status === 'success') {
                  Notify.toast('✅ Promoted', res.message || 'Playbook berhasil dipromosikan', 'ok');
                  this.switchTab('exec');
                } else {
                  Notify.toast('❌ Gagal Promote', res.message || res.error || `HTTP ${resp.status}`, 'err');
                }
              } catch (err) {
                Notify.toast('❌ Error', err.message, 'err');
              }
            }
          );
        },

        openExecuteModal(id) {
          const pb = (this._data || []).find(x => Number(x.playbook_id) === Number(id));
          if (!pb) return;

          const html = `
            <div style="display:flex;flex-direction:column;gap:10px;font-size:12px">
              <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:6px;padding:8px 10px;color:var(--txt2)">
                <i class="fa-solid fa-shield-halved" style="color:var(--cyan2);margin-right:4px"></i>
                <b>Governance Rule #6:</b> Dispatch nyata memerlukan broker NATS aktif dan otomatis mengunci status target ke <code>PENDING_VERIFICATION</code> sampai bukti post-remediation terverifikasi.
              </div>
              <div>
                <label class="inp-label">Script yang Akan Dikirim:</label>
                <pre style="background:#090d16;border:1px solid var(--bd);border-radius:6px;padding:8px;font-size:11px;color:#a7f3d0;max-height:140px;overflow:auto;white-space:pre-wrap;margin:0">${this._esc(pb.script)}</pre>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                <div>
                  <label class="inp-label">Incident ID (Opsional · Closed-Loop)</label>
                  <input type="number" class="inp" style="width:100%" id="pb-exec-incident" min="1" placeholder="Contoh: 366">
                </div>
                <div>
                  <label class="inp-label">Target Host / Device (Opsional)</label>
                  <input type="text" class="inp" style="width:100%" id="pb-exec-device" placeholder="Default: FLEET-BROADCAST">
                </div>
              </div>
            </div>
          `;

          Modal.show(`⚡ Dispatch Playbook #${pb.playbook_id} — ${this._esc(pb.name)}`, html, [
            { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() },
            {
              label: 'Dry-Run (Simulasi Aman)',
              cls: 'btn-outline',
              fn: () => {
                const incId = parseInt(document.getElementById('pb-exec-incident')?.value || '0', 10) || 0;
                const dev = (document.getElementById('pb-exec-device')?.value || '').trim();
                Modal.close();
                this.execute(pb.playbook_id, true, incId, dev);
              }
            },
            {
              label: 'Kirim Live Dispatch',
              cls: 'btn-primary',
              fn: () => {
                const incId = parseInt(document.getElementById('pb-exec-incident')?.value || '0', 10) || 0;
                const dev = (document.getElementById('pb-exec-device')?.value || '').trim();
                Modal.close();
                this.execute(pb.playbook_id, false, incId, dev);
              }
            }
          ], '⚡');
        },

        async execute(id, dryRun = false, incidentId = 0, deviceName = '') {
          try {
            const resp = await this._authFetch(`/api/playbooks/${parseInt(id, 10)}/execute`, {
              method: 'POST',
              body: JSON.stringify({
                dry_run: Boolean(dryRun),
                incident_id: incidentId || 0,
                device_name: deviceName || ''
              })
            });
            const res = await resp.json().catch(() => ({}));
            if (resp.ok && (res.status === 'DRY_RUN_PASSED' || res.status === 'PENDING_VERIFICATION' || res.status === 'success')) {
              const title = dryRun ? '🧪 Dry-Run Lulus' : '📡 Dispatched (Rule #6)';
              Notify.toast(title, res.message || 'Berhasil diproses', 'ok', 4000);
              this.load(false);
            } else {
              Notify.toast('❌ Ditolak / Gagal', res.message || res.error || `HTTP ${resp.status}`, 'err', 4500);
            }
          } catch (err) {
            Notify.toast('❌ Error API', err.message, 'err', 4000);
          }
        },

        openEditor(id = null) {
          let p = { name: '', description: '', script: '', target_layer: 1, status: 'ACTIVE' };
          if (id && this._data) {
            p = this._data.find(x => Number(x.playbook_id) === Number(id)) || p;
          }

          const currentStatus = String(p.status || 'ACTIVE').toUpperCase();
          const html = `
            <div style="display:flex;flex-direction:column;gap:12px;padding:4px">
              <div>
                <label class="inp-label">Nama Playbook *</label>
                <input class="inp" style="width:100%" id="pb-name" value="${this._esc(p.name)}" placeholder="e.g. L5 - Restart Spooler Service">
              </div>
              <div>
                <label class="inp-label">Deskripsi &amp; Tujuan SOP</label>
                <input class="inp" style="width:100%" id="pb-desc" value="${this._esc(p.description)}" placeholder="e.g. SOP pemulihan antrean cetak macet">
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div>
                  <label class="inp-label">Target OSI Layer (1–7) *</label>
                  <input class="inp" style="width:100%" type="number" id="pb-layer" value="${parseInt(p.target_layer, 10) || 1}" min="1" max="7">
                </div>
                <div>
                  <label class="inp-label">Status Playbook</label>
                  <select class="inp" style="width:100%" id="pb-status">
                    <option value="ACTIVE" ${currentStatus === 'ACTIVE' ? 'selected' : ''}>ACTIVE</option>
                    <option value="DRAFT" ${currentStatus === 'DRAFT' ? 'selected' : ''}>DRAFT</option>
                    <option value="DISABLED" ${currentStatus === 'DISABLED' ? 'selected' : ''}>DISABLED</option>
                  </select>
                </div>
              </div>
              <div>
                <label class="inp-label">Shell Script / Instruksi Remediasi *</label>
                <textarea class="inp" id="pb-script" style="width:100%;height:150px;font-family:monospace;font-size:12px">${this._esc(p.script)}</textarea>
              </div>
            </div>
          `;

          Modal.show(id ? `Edit Playbook #${parseInt(id, 10)}` : 'Buat Playbook Baru', html, [
            { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() },
            {
              label: 'Simpan Playbook',
              cls: 'btn-primary',
              fn: async () => {
                const name = (document.getElementById('pb-name')?.value || '').trim();
                const description = (document.getElementById('pb-desc')?.value || '').trim();
                const targetLayer = parseInt(document.getElementById('pb-layer')?.value || '0', 10);
                const status = (document.getElementById('pb-status')?.value || 'ACTIVE').trim();
                const script = (document.getElementById('pb-script')?.value || '').trim();

                if (!name || !script) {
                  Notify.toast('⚠️ Input Wajib', 'Nama Playbook dan Script tidak boleh kosong.', 'warn', 3000);
                  return;
                }
                if (!Number.isFinite(targetLayer) || targetLayer < 1 || targetLayer > 7) {
                  Notify.toast('⚠️ Layer Tidak Valid', 'Target OSI Layer harus antara 1 sampai 7.', 'warn', 3000);
                  return;
                }

                try {
                  const resp = await this._authFetch('/api/playbooks', {
                    method: 'POST',
                    body: JSON.stringify({
                      playbook_id: id ? parseInt(id, 10) : 0,
                      name,
                      description,
                      target_layer: targetLayer,
                      status,
                      script
                    })
                  });
                  const res = await resp.json().catch(() => ({}));
                  if (resp.ok && res.status === 'success') {
                    Notify.toast('✅ Tersimpan', res.message || 'Playbook berhasil disimpan', 'ok');
                    Modal.close();
                    this.load(false);
                  } else {
                    Notify.toast('❌ Gagal Simpan', res.message || res.error || `HTTP ${resp.status}`, 'err', 4000);
                  }
                } catch (err) {
                  Notify.toast('❌ Error API', err.message, 'err', 4000);
                }
              }
            }
          ], '📝');
        },

        edit(id) {
          this.openEditor(id);
        },

        confirmDelete(id) {
          const pb = (this._data || []).find(x => Number(x.playbook_id) === Number(id));
          const label = pb ? `#${parseInt(id, 10)} (${this._esc(pb.name)})` : `#${parseInt(id, 10)}`;
          Modal.confirm(
            'Hapus Playbook',
            `Apakah Anda yakin ingin menghapus Playbook <b>${label}</b>? Tindakan ini tercatat dalam Immutable Audit Log.`,
            async () => {
              Modal.close();
              try {
                const resp = await this._authFetch(`/api/playbooks/${parseInt(id, 10)}`, { method: 'DELETE' });
                const res = await resp.json().catch(() => ({}));
                if (resp.ok && res.status === 'success') {
                  Notify.toast('✅ Dihapus', res.message || `Playbook #${id} telah dihapus`, 'ok');
                  this.load(false);
                } else {
                  Notify.toast('❌ Gagal Hapus', res.message || res.error || `HTTP ${resp.status}`, 'err', 3500);
                }
              } catch (err) {
                Notify.toast('❌ Error API', err.message, 'err', 3500);
              }
            }
          );
        },

        delete(id) {
          this.confirmDelete(id);
        },

        async export(format) {
          const fmt = format === 'json' ? 'json' : 'csv';
          Notify.toast('📥 Exporting', `Mengunduh Playbooks (${fmt.toUpperCase()})...`, 'info', 2000);
          try {
            const resp = await this._authFetch(`/api/playbooks/export?format=${fmt}`);
            if (!resp.ok) {
              const errJson = await resp.json().catch(() => ({}));
              throw new Error(errJson.message || errJson.error || `HTTP ${resp.status}`);
            }
            const checksum = resp.headers.get('X-Audit-Checksum-SHA256') || 'UNKNOWN';
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ai_playbooks_${Date.now()}.${fmt}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => window.URL.revokeObjectURL(url), 1500);
            Notify.toast('✅ Export Selesai', `SHA256: ${checksum.substring(0, 16)}...`, 'ok', 3500);
          } catch (e) {
            Notify.toast('❌ Export Gagal', e.message, 'err', 3500);
          }
        }
      },

});

window.Modules["4_ai_lifecycle"]["playbooks"] = window.Panels;
