/* modules/4_ai_lifecycle/ai-decision-logs.js
 * Atomic Design — 3. Modules Layer (4_ai_lifecycle / ai-decision-logs)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,EventBus}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["4_ai_lifecycle"] = window.Modules["4_ai_lifecycle"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      ai_decision_logs: {
        _cachedLogs: [],
        _totalCount: 0,
        _offset: 0,
        _filterTimer: null,
        _autoRefreshTimer: null,
        _wsReloadTimer: null,
        _wsInitialized: false,
        _delegationBound: false,
        _activeDetailPayload: null,
        _escKeyHandler: null,

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
          return fetch(url, Object.assign({}, options, { headers }));
        },

        _normConf(val) {
          const num = Number(val);
          if (!Number.isFinite(num) || num <= 0) return 0;
          return Math.round(num <= 1 ? num * 100 : num);
        },

        _stripMarkdown(txt) {
          return String(txt || '')
            .replace(/^#{1,6}\s*/gm, '')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/\s+/g, ' ')
            .trim();
        },

        _formatMarkdownSafe(txt) {
          const escaped = this._esc(txt);
          return escaped
            .replace(/^###\s+(.+)$/gm, '<div style="font-size:13px;font-weight:700;color:#c084fc;margin:6px 0 3px">$1</div>')
            .replace(/^##\s+(.+)$/gm, '<div style="font-size:14px;font-weight:700;color:#38bdf8;margin:8px 0 4px">$1</div>')
            .replace(/^#\s+(.+)$/gm, '<div style="font-size:15px;font-weight:800;color:#f8fafc;margin:8px 0 4px">$1</div>')
            .replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>')
            .replace(/`([^`\n]+)`/g, '<code style="background:rgba(15,23,42,.8);padding:1px 5px;border-radius:4px;color:#38bdf8">$1</code>')
            .replace(/^---\s*$/gm, '<hr style="border:none;border-top:1px solid rgba(255,255,255,.1);margin:8px 0">')
            .replace(/\n/g, '<br>');
        },

        _formatHumanReadableSafe(txt) {
          if (!txt) return '<span style="color:var(--txt3);font-style:italic">Belum ada data analisis tersimpan.</span>';
          const str = String(txt).trim();

          const staticMap = {
            'UNKNOWN_OFFLINE': 'Perangkat / Sistem Tidak Merespons (Offline / Terputus dari Jaringan)',
            'OFFLINE': 'Perangkat / Sistem Tidak Merespons (Offline / Terputus dari Jaringan)',
            'PRINTER_STALLED': 'Antrean Cetak Macet / Layanan Printer Mengalami Stall (PRINTER_STALLED)',
            'PRINTER_SPOOLER_STUCK': 'Layanan Cetak (Print Spooler) Terhenti / Dokumen Cetak Macet',
            'PRINT_SPOOLER_OFFLINE': 'Layanan Cetak (Print Spooler) Offline / Tidak Berjalan',
            'HIGH_CPU': 'Penggunaan Processor (CPU) Sangat Tinggi (>95% Terus-Menerus)',
            'CPU_CRITICAL': 'Penggunaan Processor (CPU) Sangat Tinggi (>95% Terus-Menerus)',
            'RAM_LEAK': 'Alokasi Memori (RAM) Penuh / Indikasi Memory Leak',
            'MEMORY_FULL': 'Alokasi Memori (RAM) Penuh / Indikasi Memory Leak',
            'NETWORK_DISRUPTION': 'Disrupsi Jalur Jaringan / Packet Loss Tinggi',
            'PING_RTO': 'Koneksi Jaringan Timeout (Ping RTO)',
          };
          if (staticMap[str]) {
            return this._esc(staticMap[str]);
          }

          if (str.includes('OFFLINE RULE ENGINE FALLBACK') || str.includes('Model Reasoning')) {
            const intentMatch = str.match(/Diagnosed Intent:\s*([^\(\n]+)/i);
            const confMatch = str.match(/Confidence:\s*([\d\.]+%?)/i);
            const reasonMatch = str.match(/Model Reasoning\s*:\s*([^–\n]+)/i);
            const recMatch = str.match(/Recommendation\s*:\s*([^–\n]+)/i);

            let intentText = intentMatch ? intentMatch[1].trim() : 'FALLBACK_RULE_ENGINE';
            if (staticMap[intentText]) intentText = staticMap[intentText];

            const confText = confMatch ? confMatch[1].trim() : 'Rule Engine Confidence';
            const reasonText = reasonMatch ? reasonMatch[1].trim() : 'Menggunakan aturan lokal Decision Tree saat LLM cloud tidak aktif/terbatas.';
            const recText = recMatch
              ? recMatch[1].trim().replace(/Execute standard SOP for/g, 'Jalankan SOP Standar untuk')
              : 'Jalankan SOP Pemulihan Standar dengan verifikasi Rule #6.';

            return `
              <div style="display:flex;flex-direction:column;gap:5px">
                <div><b>📌 Diagnosa Rule Engine:</b> ${this._esc(intentText)}</div>
                <div><b>🎯 Skor Lokal:</b> ${this._esc(confText)}</div>
                <div><b>💡 Penalaran Model:</b> ${this._esc(reasonText)}</div>
                <div><b>🛠️ Rekomendasi Tindakan:</b> ${this._esc(recText)}</div>
                ${!reasonMatch ? `<details style="margin-top:4px;font-size:11px;color:var(--txt2)"><summary style="cursor:pointer">Teks Lengkap Upstream</summary><div style="margin-top:4px">${this._formatMarkdownSafe(str)}</div></details>` : ''}
              </div>
            `;
          }

          return this._formatMarkdownSafe(str);
        },

        _shortLabel(txt, fallback) {
          const str = String(txt || '').trim();
          if (!str) return fallback || '—';
          if (str === 'UNKNOWN_OFFLINE' || str === 'OFFLINE') return 'Perangkat / Klien Offline';
          if (str === 'PRINTER_STALLED') return 'Printer Stalled (Antrean Macet)';
          if (str.includes('OFFLINE RULE ENGINE FALLBACK') || str.includes('Random Forest Model')) {
            const intentMatch = str.match(/Diagnosed Intent:\s*([^\(\n]+)/i);
            const intent = intentMatch ? intentMatch[1].trim() : '';
            return intent ? `Rule Engine Fallback (${intent})` : 'Local Decision Tree (Fallback)';
          }
          return this._stripMarkdown(str);
        },

        init() {
          this._bindDelegatedEvents();
          this._initWSListeners();
          this._syncWsBadge();
        },

        _bindDelegatedEvents() {
          if (this._delegationBound) return;
          const tbody = document.getElementById('ai-decision-logs-tbody');
          if (tbody) {
            tbody.addEventListener('click', (e) => {
              const btn = e.target.closest('[data-log-detail]');
              const row = e.target.closest('tr[data-log-id]');
              const target = btn || row;
              if (!target) return;
              const logId = parseInt(target.getAttribute('data-log-detail') || target.getAttribute('data-log-id') || '0', 10);
              if (logId > 0) this.showDetail(logId);
            });
            this._delegationBound = true;
          }
        },

        _initWSListeners() {
          if (this._wsInitialized) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._wsInitialized = true;

          bus.on('ws:status', (status) => this._syncWsBadge(status));
          bus.on('ws:connected', () => this._syncWsBadge('online'));
          bus.on('ws:disconnected', () => this._syncWsBadge('offline'));

          const onRealtimeEvent = () => {
            if (!document.getElementById('p-ai_decision_logs')?.classList.contains('active')) return;
            if (document.getElementById('ai-log-modal-overlay')) return;
            if (this._wsReloadTimer) clearTimeout(this._wsReloadTimer);
            this._wsReloadTimer = setTimeout(() => this.load(false), 600);
          };
          bus.on('incident:verified', onRealtimeEvent);
          bus.on('incident:status_changed', onRealtimeEvent);
          bus.on('incidents:loaded', onRealtimeEvent);
        },

        _syncWsBadge(explicitState) {
          const badge = document.getElementById('dl-ws-badge');
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
            if (!document.getElementById('p-ai_decision_logs')?.classList.contains('active')) return;
            const activeEl = document.activeElement;
            if (activeEl && activeEl.id === 'dl-search-inp') return;
            if (document.getElementById('ai-log-modal-overlay')) return;
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
          if (this._wsReloadTimer) {
            clearTimeout(this._wsReloadTimer);
            this._wsReloadTimer = null;
          }
        },

        onFilterChange() {
          this._offset = 0;
          if (this._filterTimer) clearTimeout(this._filterTimer);
          this._filterTimer = setTimeout(() => {
            this.load(true);
          }, 280);
        },

        prevPage() {
          const limit = parseInt(document.getElementById('dl-limit-select')?.value || '50', 10) || 50;
          if (this._offset <= 0) return;
          this._offset = Math.max(0, this._offset - limit);
          this.load(true);
        },

        nextPage() {
          const limit = parseInt(document.getElementById('dl-limit-select')?.value || '50', 10) || 50;
          if (this._offset + limit >= this._totalCount) return;
          this._offset += limit;
          this.load(true);
        },

        _getFilterQueryString(includePaging = true) {
          const search = (document.getElementById('dl-search-inp')?.value || '').trim();
          const source = (document.getElementById('dl-source-select')?.value || 'incident').trim();
          const conf = (document.getElementById('dl-conf-select')?.value || '').trim();
          const limit = parseInt(document.getElementById('dl-limit-select')?.value || '50', 10) || 50;

          const params = new URLSearchParams();
          if (source) params.set('source', source);
          if (search) params.set('search', search);
          if (conf) params.set('conf', conf);
          if (includePaging) {
            params.set('limit', String(limit));
            params.set('offset', String(this._offset));
          }
          return params.toString();
        },

        async loadStats(qs) {
          try {
            const resp = await this._authFetch(`/api/ai_decision_logs/stats?${qs}`);
            if (!resp.ok) return;
            const s = await resp.json();
            if (!s) return;

            const totalInc = Number(s.total_incident_logs || 0);
            const totalChat = Number(s.total_chat_logs || 0);
            const totalFiltered = Number(s.total_filtered || 0);
            setEl('dl-kpi-total', totalFiltered.toLocaleString('id-ID'));
            setEl('dl-kpi-chat-note', `${totalInc.toLocaleString('id-ID')} insiden · ${totalChat} chat terfilter`);
            setEl('dl-kpi-conf', Number(s.avg_confidence || 0).toFixed(1) + '%');
            setEl('dl-kpi-latency', Math.round(Number(s.avg_decision_ms || 0)) + ' ms');
            setEl('dl-kpi-consensus', `${s.consensus_count || 0} / ${s.fallback_count || 0}`);
            setEl('dl-kpi-fallback-sub', `${s.consensus_count || 0} LLM/Engine · ${s.fallback_count || 0} Rule Fallback`);
            setEl('dl-kpi-audit', Number(s.immutable_audit_count || 0).toLocaleString('id-ID'));
            setEl('dl-kpi-audit-sub', `${s.ai_audit_trail_count || 0} pipeline · ${s.immutable_audit_count || 0} immutable`);
          } catch (e) {
            console.warn('Failed to load AI decision log stats:', e);
          }
        },

        async load(showSpinner = true) {
          this.init();
          const tbody = document.getElementById('ai-decision-logs-tbody');
          if (!tbody) return;

          if (showSpinner && this._cachedLogs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Decision Logs...</div></td></tr>';
          }

          const qs = this._getFilterQueryString(true);
          const limit = parseInt(document.getElementById('dl-limit-select')?.value || '50', 10) || 50;

          try {
            const [logsResp] = await Promise.all([
              this._authFetch(`/api/ai_decision_logs?${qs}`),
              this.loadStats(qs)
            ]);
            if (!logsResp.ok) {
              throw new Error(`HTTP ${logsResp.status}`);
            }
            const totalHeader = parseInt(logsResp.headers.get('X-Total-Count') || '0', 10);
            const raw = await logsResp.json();
            const logs = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.data) ? raw.data : []);
            this._cachedLogs = logs;
            this._totalCount = Number.isFinite(totalHeader) && totalHeader > 0 ? totalHeader : logs.length;

            this._updatePaginationUI(logs.length, limit);

            if (logs.length === 0) {
              tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Tidak ada Decision Log sesuai filter.</td></tr>';
              return;
            }

            tbody.innerHTML = logs.map(l => {
              const id = parseInt(l.id, 10) || 0;
              const conf = this._normConf(l.confidence_score);
              const ts = l.timestamp ? new Date(l.timestamp).toLocaleString('id-ID') : '—';
              const confColor = conf >= 80 ? 'var(--green2)' : conf >= 50 ? 'var(--orange2)' : 'var(--red2)';
              const modelDisplay = this._esc((l.ai_models_used || 'consensus-engine').replace(/,/g, ' · '));

              const parentSpanVal = String(l.parent_span || '').trim();
              let parentSpanHTML = '<span class="badge bd-bl" style="font-size:9.5px">Root Trace</span>';
              if (parentSpanVal === 'ai-supervisor') {
                parentSpanHTML = '<span class="badge bd-pu" style="font-size:9.5px">ai-supervisor</span>';
              } else if (parentSpanVal === 'ai-panel-ui') {
                parentSpanHTML = '<span class="badge bd-or" style="font-size:9.5px">ai-panel-ui</span>';
              } else if (parentSpanVal === 'UNKNOWN_OFFLINE') {
                parentSpanHTML = '<span class="badge bd-or" style="font-size:9.5px">Root (Offline)</span>';
              } else if (parentSpanVal && parentSpanVal !== 'NONE' && parentSpanVal !== '—') {
                parentSpanHTML = `<code style="font-size:9.5px;color:var(--cyan2)">${this._esc(parentSpanVal.substring(0, 14))}</code>`;
              }

              const firstHypoRaw = String(l.first_hypothesis || '').trim();
              const firstHypoShort = this._esc(this._shortLabel(firstHypoRaw, '—'));
              const finalDecRaw = String(l.final_decision || '').trim();
              const finalDecShort = this._esc(this._shortLabel(finalDecRaw, '—'));

              const incLabel = `INC-${parseInt(l.incident_id, 10) || 'SYS'}`;
              const deviceTag = l.device_name ? `<div style="font-size:9.5px;color:var(--txt3);margin-top:2px">${this._esc(l.device_name)}</div>` : '';

              const traceFull = String(l.trace_id || '');
              const traceShort = traceFull ? `${this._esc(traceFull.substring(0, 14))}${traceFull.length > 14 ? '...' : ''}` : '—';
              const spanShort = this._esc(String(l.span_id || '—').substring(0, 8));

              const fallbackBadge = l.is_fallback ? ' <span class="badge bd-or" style="font-size:9px">Fallback</span>' : '';

              return `<tr style="cursor:pointer" data-log-id="${id}" title="Klik untuk melihat detail & audit trail AI #${id}">
                <td><b>#${id}</b></td>
                <td><span class="badge bd-bl">${this._esc(incLabel)}</span>${deviceTag}</td>
                <td>
                  <span style="font-size:10.5px;font-weight:600">${this._esc(ts)}</span><br>
                  <code style="font-size:9.5px;color:var(--purple2)" title="${this._esc(traceFull)}">${traceShort}</code> / <code style="font-size:9.5px;color:var(--cyan2)">${spanShort}</code>
                </td>
                <td>${parentSpanHTML}</td>
                <td style="font-size:11px;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--txt1)" title="${this._esc(this._stripMarkdown(firstHypoRaw))}">${firstHypoShort}</td>
                <td style="font-size:11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:700;color:var(--green2)" title="${this._esc(this._stripMarkdown(finalDecRaw))}">${finalDecShort}${fallbackBadge}</td>
                <td><b style="color:${confColor}">${conf}%</b></td>
                <td><span class="badge bd-pu" style="font-size:9.5px;max-width:150px;overflow:hidden;text-overflow:ellipsis;display:inline-block;vertical-align:middle" title="${modelDisplay}">${modelDisplay}</span></td>
                <td><span style="font-family:monospace;font-size:10.5px;color:var(--cyan)">${parseInt(l.decision_time_ms, 10) || 0} ms</span></td>
                <td><button type="button" class="btn btn-primary btn-xs" style="padding:2px 8px;font-size:10px" data-log-detail="${id}"><i class="fa-solid fa-brain" style="margin-right:3px"></i> Detail</button></td>
              </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat log: ${this._esc(err.message)}</td></tr>`;
          }
        },

        _updatePaginationUI(pageRows, limit) {
          const pageInfo = document.getElementById('dl-page-info');
          const prevBtn = document.getElementById('dl-prev-btn');
          const nextBtn = document.getElementById('dl-next-btn');
          if (pageInfo) {
            if (pageRows === 0) {
              pageInfo.textContent = 'Menampilkan 0 entri';
            } else {
              const start = this._offset + 1;
              const end = this._offset + pageRows;
              pageInfo.textContent = `Menampilkan ${start}–${end} dari ${this._totalCount.toLocaleString('id-ID')} entri`;
            }
          }
          if (prevBtn) prevBtn.disabled = this._offset <= 0;
          if (nextBtn) nextBtn.disabled = (this._offset + limit) >= this._totalCount;
        },

        _closeDetailModal() {
          const existing = document.getElementById('ai-log-modal-overlay');
          if (existing) existing.remove();
          if (this._escKeyHandler) {
            document.removeEventListener('keydown', this._escKeyHandler);
            this._escKeyHandler = null;
          }
          this._activeDetailPayload = null;
        },

        async showDetail(logId) {
          const log = (this._cachedLogs || []).find(x => Number(x.id) === Number(logId));
          if (!log) {
            Notify.toast('⚠️ Warning', 'Detail log tidak ditemukan', 'warn');
            return;
          }

          this._closeDetailModal();

          const id = parseInt(log.id, 10) || 0;
          const incId = parseInt(log.incident_id, 10) || 0;
          const conf = this._normConf(log.confidence_score);
          const ts = log.timestamp ? new Date(log.timestamp).toLocaleString('id-ID') : '—';
          const confColor = conf >= 80 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444';

          const rawModels = String(log.ai_models_used || 'consensus-engine').trim();
          let modelsList = [];
          if (rawModels === 'consensus-engine' || rawModels === 'multi-agent-consensus' || rawModels === 'all') {
            modelsList = ['Multi-Agent Consensus Engine (configured ensemble)'];
          } else {
            modelsList = rawModels.split(/[\/,]/).map(m => m.trim()).filter(Boolean);
          }
          if (modelsList.length === 0) modelsList = ['AI Core Engine'];

          const modelSectionTitle = log.is_fallback
            ? `Model & Rule Fallback Aktif (${modelsList.length} komponen)`
            : `Model / Komponen Terlibat (${modelsList.length} entri)`;

          const confLabel = conf >= 80
            ? 'Tinggi (Menunggu / Cek Verifikasi Rule #6)'
            : conf >= 50
              ? 'Sedang (Perlu Tinjauan Operator HITL)'
              : 'Rendah (Fallback / Eskalasi HITL Disarankan)';

          const firstHypothesisHTML = this._formatHumanReadableSafe(log.first_hypothesis);
          const secondHypothesisHTML = this._formatHumanReadableSafe(log.second_hypothesis);
          const finalDecisionHTML = this._formatHumanReadableSafe(log.final_decision);

          this._activeDetailPayload = { reflection: log, audit: null };

          const html = `
            <div id="ai-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
              <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:860px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
                <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(124,58,237,0.08)">
                  <div style="display:flex;align-items:center;gap:10px">
                    <div style="width:36px;height:36px;border-radius:8px;background:rgba(124,58,237,0.2);display:flex;align-items:center;justify-content:center;color:#a855f7;font-size:18px">
                      <i class="fa-solid fa-brain"></i>
                    </div>
                    <div>
                      <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Detail Refleksi AI &amp; Audit Trail #${id}</h3>
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${incId || 'SYS'}${log.device_name ? ` (${this._esc(log.device_name)})` : ''} · ${this._esc(ts)} · Source: <code>${this._esc(log.parent_span || 'root')}</code></div>
                    </div>
                  </div>
                  <button type="button" id="ai-log-modal-close-top" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
                </div>

                <div style="padding:20px;display:flex;flex-direction:column;gap:14px">
                  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-shield-halved" style="color:#38bdf8;margin-right:4px"></i>Skor Keyakinan AI</div>
                      <div style="font-size:20px;font-weight:800;color:${confColor}">${conf}%</div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">${this._esc(confLabel)}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-bolt" style="color:#f59e0b;margin-right:4px"></i>Waktu Analisis</div>
                      <div style="font-size:20px;font-weight:800;color:#38bdf8">${parseInt(log.decision_time_ms, 10) || 0} ms</div>
                      <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">${log.is_fallback ? 'Offline Rule Engine Path' : 'Cognitive Reasoning Path'}</div>
                    </div>
                    <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                      <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-layer-group" style="color:#a855f7;margin-right:4px"></i>Stage &amp; Rule #6 Status</div>
                      <div style="font-size:13px;font-weight:700;margin-top:4px"><span class="badge bd-pu">${this._esc(log.stage_version || 'v7_hitl')}</span></div>
                      <div id="dl-modal-rule6-sub" style="font-size:10px;color:var(--txt3,#64748b);margin-top:4px">Memuat status verifikasi &amp; audit trail...</div>
                    </div>
                  </div>

                  <div style="background:rgba(124,58,237,0.05);border:1px solid rgba(124,58,237,0.2);border-radius:8px;padding:12px 14px">
                    <div style="font-size:12px;font-weight:700;color:#c084fc;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-layer-group"></i> ${this._esc(modelSectionTitle)}
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:8px">
                      ${modelsList.map(m => `
                        <div style="background:rgba(15,23,42,0.6);border:1px solid rgba(168,85,247,0.3);border-radius:6px;padding:5px 12px;font-size:11.5px;display:flex;align-items:center;gap:6px">
                          <i class="fa-solid fa-microchip" style="color:#10b981"></i>
                          <span style="font-weight:600;color:#e2e8f0">${this._esc(m)}</span>
                        </div>
                      `).join('')}
                    </div>
                  </div>

                  <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#38bdf8;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-stethoscope"></i> 1. Hipotesis Diagnosa Awal (First Hypothesis)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #38bdf8">
                      ${firstHypothesisHTML}
                    </div>
                  </div>

                  <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#f59e0b;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-code-compare"></i> 2. Evaluasi Sekunder &amp; Analisis Risiko (Second Hypothesis)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #f59e0b">
                      ${secondHypothesisHTML}
                    </div>
                  </div>

                  <div style="background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.2);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#10b981;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-circle-check"></i> 3. Keputusan Akhir &amp; Tindakan Remediasi (Final Decision)
                    </div>
                    <div style="font-size:12.5px;line-height:1.6;color:#e2e8f0;background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;border-left:3px solid #10b981">
                      ${finalDecisionHTML}
                    </div>
                  </div>

                  <div id="dl-modal-audit-trail" style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                    <div style="font-size:12.5px;font-weight:700;color:#c084fc;margin-bottom:8px;display:flex;align-items:center;gap:6px">
                      <i class="fa-solid fa-fingerprint"></i> 4. Audit Trail &amp; Korelasi OTel / Hash Ledger
                    </div>
                    <div id="dl-modal-audit-body" style="font-size:11.5px;color:var(--txt2,#94a3b8)">
                      Memuat korelasi <code>ai_audit_trail</code> dan <code>immutable_audit_log</code>...
                    </div>
                  </div>

                  <div style="font-size:11px;color:var(--txt3,#64748b);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:4px 2px">
                    <span>Trace ID: <code style="color:#a855f7">${this._esc(log.trace_id || '—')}</code></span>
                    <span>Span ID: <code style="color:#38bdf8">${this._esc(log.span_id || '—')}</code></span>
                    <span>Parent Span: <code style="color:#f59e0b">${this._esc(log.parent_span || '—')}</code></span>
                  </div>
                </div>

                <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
                  <button type="button" id="ai-log-modal-copy-btn" class="btn btn-ghost btn-sm" style="padding:6px 14px">
                    <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin Detail JSON
                  </button>
                  <button type="button" id="ai-log-modal-close-bottom" class="btn btn-primary btn-sm" style="padding:6px 18px">
                    Tutup
                  </button>
                </div>
              </div>
            </div>
          `;

          document.body.insertAdjacentHTML('beforeend', html);

          const overlay = document.getElementById('ai-log-modal-overlay');
          if (overlay) {
            overlay.addEventListener('click', (e) => {
              if (e.target === overlay) this._closeDetailModal();
            });
          }
          document.getElementById('ai-log-modal-close-top')?.addEventListener('click', () => this._closeDetailModal());
          document.getElementById('ai-log-modal-close-bottom')?.addEventListener('click', () => this._closeDetailModal());
          document.getElementById('ai-log-modal-copy-btn')?.addEventListener('click', async () => {
            try {
              const payloadStr = JSON.stringify(this._activeDetailPayload || log, null, 2);
              await navigator.clipboard.writeText(payloadStr);
              Notify.toast('📋 Copied', 'Detail refleksi & audit log disalin ke clipboard', 'ok');
            } catch (copyErr) {
              Notify.toast('❌ Gagal Copy', copyErr.message, 'warn');
            }
          });

          this._escKeyHandler = (ev) => {
            if (ev.key === 'Escape') this._closeDetailModal();
          };
          document.addEventListener('keydown', this._escKeyHandler);

          this._loadDetailAudit(id);
        },

        async _loadDetailAudit(logId) {
          const ruleSub = document.getElementById('dl-modal-rule6-sub');
          const auditBody = document.getElementById('dl-modal-audit-body');
          if (!auditBody) return;

          try {
            const resp = await this._authFetch(`/api/ai_decision_logs/${logId}/audit`);
            if (!resp.ok) {
              auditBody.textContent = `Gagal memuat korelasi audit trail (HTTP ${resp.status}).`;
              if (ruleSub) ruleSub.textContent = 'Status verifikasi tidak tersedia';
              return;
            }
            const data = await resp.json();
            if (!document.getElementById('ai-log-modal-overlay')) return;
            this._activeDetailPayload = data;

            if (ruleSub) {
              const vCount = Number(data.verification_count || 0);
              const aCount = Number(data.approval_count || 0);
              ruleSub.innerHTML = data.rule6_verified
                ? `<span style="color:#10b981;font-weight:600">Rule #6 Verified (${vCount} verify · ${aCount} HITL approval)</span>`
                : `<span style="color:#f59e0b">Belum Terverifikasi Rule #6 (${vCount} verify · ${aCount} HITL approval)</span>`;
            }

            const sections = [];
            const inc = data.incident || {};
            if (inc.incident_id) {
              sections.push(`
                <div style="margin-bottom:8px;padding:8px 10px;background:rgba(0,0,0,.22);border-radius:6px">
                  <b>Insiden Terkait #${parseInt(inc.incident_id, 10)}:</b>
                  <span style="color:var(--txt1)">${this._esc(inc.device_name || 'SYSTEM')}</span> ·
                  <code>${this._esc(inc.flag || 'UNKNOWN')}</code> ·
                  Layer ${parseInt(inc.layer, 10) || 0}
                  ${inc.evidence ? `<div style="margin-top:3px;color:var(--txt3)">${this._esc(inc.evidence.substring(0, 220))}</div>` : ''}
                </div>
              `);
            }

            const trail = Array.isArray(data.ai_audit_trail) ? data.ai_audit_trail : [];
            if (trail.length > 0) {
              sections.push(`<div style="margin-bottom:8px"><b>Pipeline Audit Trail (${trail.length}):</b>` + trail.map(t => `
                <div style="margin-top:4px;padding:6px 8px;background:rgba(0,0,0,.22);border-radius:6px;border-left:2px solid #a855f7">
                  <div><b>Audit #${parseInt(t.audit_id, 10)}</b> · Action: <code>${this._esc(t.action_executed)}</code> · State: <span class="badge bd-pu">${this._esc(t.worker_state || '-')}</span> · ${parseInt(t.execution_time_ms, 10) || 0}ms</div>
                </div>
              `).join('') + `</div>`);
            } else {
              sections.push(`<div style="margin-bottom:8px;color:var(--txt3)">• Belum ada entri <code>ai_audit_trail</code> terhubung untuk Trace/Incident ini.</div>`);
            }

            const imm = Array.isArray(data.immutable_audit_log) ? data.immutable_audit_log : [];
            if (imm.length > 0) {
              sections.push(`<div><b>Immutable Audit Ledger (${imm.length}):</b>` + imm.map(m => `
                <div style="margin-top:4px;padding:6px 8px;background:rgba(0,0,0,.22);border-radius:6px;border-left:2px solid #38bdf8;font-size:11px">
                  <b>#${parseInt(m.log_id, 10)}</b> · <code>${this._esc(m.action_type)}</code> · Actor: <b>${this._esc(m.actor)}</b> · Target: <code>${this._esc(m.target)}</code> · Hash: <code>${this._esc((m.hash_signature || '').substring(0, 14))}...</code>
                </div>
              `).join('') + `</div>`);
            } else {
              sections.push(`<div style="color:var(--txt3)">• Belum ada entri <code>immutable_audit_log</code> untuk Trace/Incident ini.</div>`);
            }

            auditBody.innerHTML = sections.join('');
          } catch (err) {
            if (auditBody) auditBody.textContent = `Gagal memuat korelasi audit trail: ${err.message}`;
          }
        },

        async export(format) {
          const fmt = format === 'json' ? 'json' : 'csv';
          const qs = this._getFilterQueryString(false);
          Notify.toast('📥 Exporting', `Mengunduh AI Decision Logs (${fmt.toUpperCase()})...`, 'info', 2000);
          try {
            const resp = await this._authFetch(`/api/ai_decision_logs/export?format=${fmt}&${qs}`);
            if (!resp.ok) {
              const errJson = await resp.json().catch(() => ({}));
              throw new Error(errJson.error || `HTTP ${resp.status}`);
            }
            const checksum = resp.headers.get('X-Audit-Checksum-SHA256') || 'UNKNOWN';
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ai_decision_logs_${Date.now()}.${fmt}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => window.URL.revokeObjectURL(url), 1500);
            Notify.toast('✅ Export Selesai', `File berhasil diunduh. SHA256: ${checksum.substring(0, 16)}...`, 'ok', 3500);
          } catch (e) {
            Notify.toast('❌ Export Gagal', e.message, 'err', 3500);
          }
        }
      },

});

window.Modules["4_ai_lifecycle"]["ai-decision-logs"] = window.Panels;
