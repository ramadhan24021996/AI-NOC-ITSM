/* modules/4_ai_lifecycle/training.js
 * Atomic Design — 3. Modules Layer (4_ai_lifecycle / training)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,EventBus}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["4_ai_lifecycle"] = window.Modules["4_ai_lifecycle"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      training: {
        _autoRefreshTimer: null,
        _filterTimer: null,
        _wsReloadTimer: null,
        _wsInitialized: false,
        _delegationBound: false,
        _lastStats: null,
        _queueMap: {},
        _skippedIds: new Set(),
        _lastChartSig: '',

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

        _getOperatorName() {
          return window.currentUserName || sessionStorage.getItem('noc_username') || window.currentUserRole || 'NOC_OPERATOR';
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
          const list = document.getElementById('tr-feedback-list');
          if (list) {
            list.addEventListener('click', (e) => {
              const btn = e.target.closest('[data-fb-action]');
              if (!btn) return;
              const action = btn.getAttribute('data-fb-action');
              const incId = parseInt(btn.getAttribute('data-incident-id') || '0', 10);
              if (!incId) return;
              const inc = this._queueMap[String(incId)] || {};
              const flag = inc.flag || '';
              if (action === 'approve') this.approveFeedback(incId);
              else if (action === 'reject') this.openSupervisorRejectModal(incId, flag);
              else if (action === 'correct') this.markFeedback(incId, 'correct', flag);
              else if (action === 'incorrect') this.markFeedback(incId, 'incorrect', flag);
              else if (action === 'skip') this.markFeedback(incId, 'skip', flag);
            });
          }

          const term = document.getElementById('tr-live-log-terminal');
          if (term) {
            term.addEventListener('click', (e) => {
              const btn = e.target.closest('[data-teach-prompt]');
              if (!btn) return;
              const promptText = btn.getAttribute('data-teach-prompt') || '';
              this.teachAIInteractive(promptText);
            });
          }
          if (list && term) {
            this._delegationBound = true;
          }
        },

        _initWSListeners() {
          if (this._wsInitialized) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._wsInitialized = true;

          bus.on('ws:status', (status) => {
            this._syncWsBadge(status);
          });
          bus.on('ws:connected', () => {
            this._syncWsBadge('online');
            this._appendTerminal('OK', 'WS-LIVE', 'WebSocket /ws/logs connected. Live AI Training & Continuous Learning stream active.');
          });
          bus.on('ws:disconnected', () => {
            this._syncWsBadge('offline');
            this._appendTerminal('WARN', 'WS-LIVE', 'WebSocket stream terputus. Mencoba reconnect otomatis...');
          });
          bus.on('feedback:updated', (data) => {
            const payload = data || {};
            if (payload.event === 'knowledge_taught') {
              this._appendTerminal('OK', 'RAG-TEACHER', `Knowledge Item ${payload.item_id || ''} (${payload.category || 'KB'}) oleh ${payload.actor || 'Teacher'}: "${payload.problem || ''}"`);
            } else {
              this._appendTerminal('INFO', 'RLOF-WS', `Feedback Incident #${payload.incident_id || '?'} -> ${payload.status || 'UPDATED'} (Reviewer: ${payload.reviewer || '-'})`);
            }
            this._scheduleLiveReload();
          });
          bus.on('incident:verified', (data) => {
            const payload = data || {};
            this._appendTerminal('OK', 'RULE6-WS', `Dual-Evidence Verified Incident #${payload.incident_id || payload.id || '?'}: ${payload.status || payload.message || 'VERIFIED'}`);
            this._scheduleLiveReload();
          });
          bus.on('incident:status_changed', (data) => {
            const payload = data || {};
            this._appendTerminal('INFO', 'INCIDENT-WS', `Incident #${payload.incident_id || payload.id || '?'} status -> ${payload.status || 'UPDATED'}`);
            this._scheduleLiveReload();
          });
          bus.on('log:entry', (entry) => {
            if (!entry || !entry.message) return;
            const src = String(entry.src || '').toUpperCase();
            if (/RLOF|RAG|TRAIN|HITL|FEEDBACK|TEACH|AI|JARVIS/.test(src)) {
              this._appendTerminal(entry.type || 'INFO', src, entry.message);
            }
          });
        },

        _syncWsBadge(explicitState) {
          const badge = document.getElementById('tr-ws-badge');
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
            badge.className = 'badge bd-gn';
            badge.innerHTML = '<i class="fa-solid fa-signal" style="margin-right:4px"></i>WS Live Active';
          } else if (state === 'connecting') {
            badge.className = 'badge bd-or';
            badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="margin-right:4px"></i>WS Reconnecting...';
          } else {
            badge.className = 'badge bd-rd';
            badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="margin-right:4px"></i>WS Offline';
          }
        },

        _appendTerminal(level, source, text, isSafeHtml = false) {
          const term = document.getElementById('tr-live-log-terminal');
          if (!term) return;
          const ts = new Date().toLocaleTimeString();
          const lvl = String(level || 'INFO').toUpperCase();
          const colorMap = {
            OK: '#34d399',
            WARN: '#fbbf24',
            ERR: '#ef4444',
            ERROR: '#ef4444',
            INFO: '#60a5fa',
            DEBUG: '#a78bfa'
          };
          const color = colorMap[lvl] || '#a7f3d0';
          const row = document.createElement('div');
          row.style.color = color;
          row.style.marginTop = '4px';
          const bodyHtml = isSafeHtml ? text : this._esc(text);
          row.innerHTML = `[${this._esc(ts)}] [${this._esc(source)}] ${bodyHtml}`;
          term.appendChild(row);
          while (term.children.length > 100) {
            term.removeChild(term.firstElementChild);
          }
          term.scrollTop = term.scrollHeight;
        },

        _scheduleLiveReload() {
          if (!document.getElementById('p-training')?.classList.contains('active')) return;
          if (this._wsReloadTimer) clearTimeout(this._wsReloadTimer);
          this._wsReloadTimer = setTimeout(() => {
            this.load();
          }, 400);
        },

        _isUserInteracting() {
          const activeEl = document.activeElement;
          if (activeEl && (activeEl.id === 'tr-search-inp' || activeEl.id === 'tr-teacher-input')) {
            return true;
          }
          const rejModal = document.getElementById('modal-feedback-rejection');
          if (rejModal && rejModal.style.display === 'flex') return true;
          const appModal = document.getElementById('modal-overlay');
          if (appModal && !appModal.classList.contains('hidden')) return true;
          return false;
        },

        startAutoRefresh() {
          this.init();
          this.stopAutoRefresh();
          this._autoRefreshTimer = setInterval(() => {
            if (document.hidden) return;
            if (!document.getElementById('p-training')?.classList.contains('active')) return;
            if (this._isUserInteracting()) return;
            this.load();
          }, 5000);
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
          if (this._lastStats) {
            this.renderQueue(this._lastStats);
          }
          if (this._filterTimer) clearTimeout(this._filterTimer);
          this._filterTimer = setTimeout(() => {
            this.load();
          }, 300);
        },

        resetSkipped() {
          this._skippedIds.clear();
          this._updateSkipButton();
          if (this._lastStats) {
            this.renderQueue(this._lastStats);
          } else {
            this.load();
          }
        },

        _updateSkipButton() {
          const btn = document.getElementById('tr-reset-skip-btn');
          if (!btn) return;
          const count = this._skippedIds.size;
          btn.style.display = count > 0 ? 'inline-flex' : 'none';
          btn.innerHTML = `<i class="fa-solid fa-eye"></i> Skip (${count})`;
        },

        async load() {
          this.init();
          try {
            const searchQ = (document.getElementById('tr-search-inp')?.value || '').trim();
            const statusFilter = (document.getElementById('tr-status-select')?.value || '').trim();
            const params = new URLSearchParams();
            if (statusFilter) params.set('status', statusFilter);
            if (searchQ) params.set('q', searchQ);
            const qs = params.toString() ? `?${params.toString()}` : '';

            const resp = await this._authFetch(`/api/feedback/stats${qs}`);
            if (!resp.ok) {
              console.warn('Failed to fetch feedback stats:', resp.status);
              return;
            }
            const stats = await resp.json();
            if (!stats) return;
            this._lastStats = stats;

            const correct = Number(stats.correct_count || 0);
            const incorrect = Number(stats.incorrect_count || 0);
            const pending = Number(stats.pending_count || 0);
            const accuracy = stats.accuracy_rate !== undefined && stats.accuracy_rate !== null
              ? Number(stats.accuracy_rate).toFixed(1) + '%'
              : '0.0%';
            const vecCount = Number(stats.rag_count || 0);
            const kbCount = Number(stats.kb_count || 0);
            const totalKnowledge = stats.total_knowledge !== undefined
              ? Number(stats.total_knowledge)
              : (vecCount + kbCount);

            setEl('tr-correct', correct);
            setEl('tr-incorrect', incorrect);
            setEl('tr-pending', pending);
            setEl('tr-accuracy', accuracy);
            setEl('tr-rag', totalKnowledge);

            const ragEl = document.getElementById('tr-rag');
            if (ragEl) {
              ragEl.title = `${vecCount} PGVector Embeddings + ${kbCount} Local/Taught KB Rules`;
            }
            const ragStatusEl = document.getElementById('tr-rag-status-text');
            if (ragStatusEl) {
              ragStatusEl.textContent = `Active (${vecCount} Vector + ${kbCount} KB Rules) · Mode: Continuous Learning & HITL Approval Gate`;
            }

            const queueLen = Array.isArray(stats.queue) ? stats.queue.length : 0;
            setEl('bdg-training', pending > 0 ? pending : queueLen);

            this.renderQueue(stats);
            this._updateChart(stats);
          } catch (err) {
            console.error('Error loading training panel:', err);
          }
        },

        renderQueue(stats) {
          const list = document.getElementById('tr-feedback-list');
          if (!list || !stats) return;

          const searchQ = (document.getElementById('tr-search-inp')?.value || '').trim().toLowerCase();
          const statusFilter = (document.getElementById('tr-status-select')?.value || '').trim();
          const rawQueue = Array.isArray(stats.queue) ? stats.queue : [];

          this._queueMap = {};
          rawQueue.forEach(inc => {
            if (inc && inc.incident_id !== undefined) {
              this._queueMap[String(inc.incident_id)] = inc;
            }
          });

          let queueItems = rawQueue.filter(inc => !this._skippedIds.has(String(inc.incident_id)));
          if (searchQ) {
            queueItems = queueItems.filter(inc =>
              String(inc.incident_id).includes(searchQ) ||
              String(inc.device_name || '').toLowerCase().includes(searchQ) ||
              String(inc.flag || '').toLowerCase().includes(searchQ) ||
              String(inc.evidence || '').toLowerCase().includes(searchQ) ||
              String(inc.action || '').toLowerCase().includes(searchQ)
            );
          }
          if (statusFilter) {
            queueItems = queueItems.filter(inc => inc.status === statusFilter);
          }

          setEl('tr-queue-count', queueItems.length);
          this._updateSkipButton();

          list.innerHTML = queueItems.map(inc => {
            const rawConf = Number(inc.confidence);
            const confVal = Number.isFinite(rawConf) && rawConf > 0
              ? Math.round(rawConf <= 1 ? rawConf * 100 : rawConf)
              : 0;
            const confText = confVal > 0 ? `${confVal}%` : '-';

            const deviceName = this._esc(inc.device_name || 'SYSTEM');
            const flag = this._esc(inc.flag || 'UNKNOWN');
            const incId = parseInt(inc.incident_id, 10) || 0;
            const traceRaw = String(inc.trace_id || '');
            const traceTitle = this._esc(traceRaw || '-');
            const traceShort = traceRaw ? `${this._esc(traceRaw.substring(0, 10))}...` : '-';

            const evidenceText = inc.evidence
              ? this._esc(inc.evidence)
              : '<span style="color:var(--txt3);font-style:italic;font-weight:400">Tidak ada rincian telemetri / payload.</span>';
            const actionText = inc.action
              ? this._esc(inc.action)
              : '<span style="color:var(--txt3);font-style:italic;font-weight:400">Belum ada hasil analisis AI.</span>';

            const status = inc.status || 'PENDING_REVIEW';
            const statusBadge = status === 'APPROVED'
              ? '<span class="tag tag-green">APPROVED</span>'
              : status === 'PENDING_APPROVAL'
                ? '<span class="tag tag-orange"><i class="fa-solid fa-hourglass-half"></i> PENDING APPROVAL</span>'
                : status === 'REJECTED'
                  ? '<span class="tag tag-red">REJECTED</span>'
                  : '<span class="tag tag-gray">PENDING REVIEW</span>';

            const supervisorActions = status === 'PENDING_APPROVAL' ? `
              <button class="btn btn-warning btn-sm" style="padding:4px 12px" data-fb-action="approve" data-incident-id="${incId}"><i class="fa-solid fa-user-check" style="margin-right:4px"></i>Persetujuan Reviewer (Approve RAG)</button>
              <button class="btn btn-outline btn-sm" style="padding:4px 10px;border-color:rgba(239,68,68,.5);color:var(--red2)" data-fb-action="reject" data-incident-id="${incId}"><i class="fa-solid fa-ban" style="margin-right:4px"></i>Tolak (Reject)</button>
            ` : '';

            return `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 14px;gap:8px;margin-bottom:10px" id="fb-${incId}">
              <div style="font-size:11.5px;font-weight:500;display:flex;align-items:center;justify-content:space-between;width:100%;flex-wrap:wrap;gap:6px">
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                  <span><i class="fa-solid fa-desktop" style="color:var(--cyan);margin-right:4px"></i><b>${deviceName}</b></span>
                  <span style="color:var(--txt3)">•</span>
                  <code style="color:var(--orange2);background:rgba(249,115,22,.1);padding:1px 6px;border-radius:4px"><i class="fa-solid fa-tag" style="margin-right:4px"></i>${flag}</code>
                  ${statusBadge}
                </div>
                <div style="font-size:10px;color:var(--txt2);display:flex;align-items:center;gap:8px">
                  <span><i class="fa-solid fa-hashtag" style="color:var(--blue);margin-right:2px"></i>ID: <b>${incId}</b></span>
                  <span style="color:var(--txt3)">|</span>
                  <span title="Trace ID: ${traceTitle}"><i class="fa-solid fa-network-wired" style="color:var(--purple2);margin-right:2px"></i>Trace: <b>${traceShort}</b></span>
                  <span style="color:var(--txt3)">|</span>
                  <span><i class="fa-solid fa-brain" style="color:var(--pink);margin-right:4px"></i>Conf: <b style="color:${confVal >= 80 ? 'var(--green2)' : (confVal > 0 ? 'var(--orange2)' : 'var(--txt3)')}">${confText}</b></span>
                </div>
              </div>
              <div style="font-size:11px;color:var(--txt1);background:rgba(0,0,0,0.2);padding:6px 10px;border-radius:6px;width:100%;border-left:3px solid var(--purple2)">
                <div style="font-size:10px;color:var(--txt3);margin-bottom:2px"><i class="fa-solid fa-triangle-exclamation" style="color:var(--orange2);margin-right:4px"></i>Gejala / Telemetri Ringkasan:</div>
                <div style="font-weight:500">${evidenceText}</div>
              </div>
              <div style="font-size:11px;color:var(--txt1);background:rgba(0,0,0,0.2);padding:6px 10px;border-radius:6px;width:100%;border-left:3px solid var(--green2)">
                <div style="font-size:10px;color:var(--txt3);margin-bottom:2px"><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--green2);margin-right:4px"></i>Rekomendasi / Tindakan AI:</div>
                <div style="font-weight:600;color:var(--green2)">${actionText}</div>
              </div>
              <div style="display:flex;gap:8px;margin-top:4px;width:100%;justify-content:flex-end;align-items:center;flex-wrap:wrap">
                ${supervisorActions}
                <button class="btn btn-success btn-sm" style="padding:4px 12px" data-fb-action="correct" data-incident-id="${incId}"><i class="fa-solid fa-circle-check" style="margin-right:4px"></i>Benar</button>
                <button class="btn btn-danger btn-sm" style="padding:4px 12px" data-fb-action="incorrect" data-incident-id="${incId}"><i class="fa-solid fa-circle-xmark" style="margin-right:4px"></i>Salah</button>
                <button class="btn btn-ghost btn-sm" style="padding:4px 10px" data-fb-action="skip" data-incident-id="${incId}"><i class="fa-solid fa-rotate-right" style="margin-right:4px"></i>Skip</button>
              </div>
            </div>`;
          }).join('') || '<div class="empty-state"><div class="es-icon"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i></div><div class="es-text">Tidak ada feedback matching kriteria.</div></div>';
        },

        _updateChart(stats) {
          const correct = Number(stats.correct_count || 0);
          const incorrect = Number(stats.incorrect_count || 0);
          const pending = Number(stats.pending_count || 0);
          const sig = `${correct}:${incorrect}:${pending}`;
          if (sig === this._lastChartSig && Charts._charts && Charts._charts['chart-training-acc']) {
            return;
          }
          this._lastChartSig = sig;

          const canvas = document.getElementById('chart-training-acc');
          if (!canvas) return;
          if (window.Chart && typeof Chart.getChart === 'function') {
            const existing = Chart.getChart(canvas);
            if (existing) existing.destroy();
          }

          const total = correct + incorrect;
          if (total === 0) {
            Charts.create('chart-training-acc', 'doughnut', ['Belum Ada Data Evaluasi'], [
              { data: [1], backgroundColor: ['rgba(139,148,158,.15)'], borderWidth: 0 }
            ], { legend: false, cutout: '75%' });
          } else {
            Charts.create('chart-training-acc', 'doughnut', ['Benar (Verified)', 'Salah (Evaluasi Audit)', 'Pending Approval'], [
              {
                data: [correct, incorrect, pending],
                backgroundColor: ['rgba(34,197,94,.85)', 'rgba(239,68,68,.85)', 'rgba(249,115,22,.8)'],
                borderWidth: 0,
                hoverOffset: 4
              }
            ], { legend: true, cutout: '70%' });
          }
        },

        openSupervisorRejectModal(incidentId, flag = '') {
          const titleEl = document.getElementById('rej-modal-title');
          const subEl = document.getElementById('rej-modal-subtitle');
          const rcaGroup = document.getElementById('rej-human-rca-group');
          if (titleEl) {
            titleEl.innerHTML = '<i class="fa-solid fa-ban" style="margin-right:8px"></i>Penolakan Supervisor Four-Eyes (Reject Feedback)';
          }
          if (subEl) {
            subEl.textContent = `Incident #${incidentId} (${flag || 'Feedback Pending'}) — Feedback akan berstatus REJECTED dan tidak masuk ke RAG Vector Store.`;
          }
          if (rcaGroup) rcaGroup.style.display = 'none';
          document.getElementById('rej-mode').value = 'supervisor_reject';
          document.getElementById('rej-incident-id').value = incidentId;
          document.getElementById('rej-flag').value = flag;
          document.getElementById('rej-reason-text').value = '';
          document.getElementById('rej-human-rca').value = '';
          document.getElementById('modal-feedback-rejection').style.display = 'flex';
        },

        async markFeedback(incidentId, type, flag = '') {
          const card = document.getElementById('fb-' + incidentId);

          if (type === 'skip') {
            this._skippedIds.add(String(incidentId));
            if (card) card.remove();
            this._updateSkipButton();
            const remaining = document.querySelectorAll('#tr-feedback-list .li-row').length;
            setEl('tr-queue-count', remaining);
            Notify.toast('⟳ Skipped', `Feedback insiden #${incidentId} disembunyikan sementara`, 'info', 1800);
            return;
          }

          if (type === 'incorrect') {
            const titleEl = document.getElementById('rej-modal-title');
            const subEl = document.getElementById('rej-modal-subtitle');
            const rcaGroup = document.getElementById('rej-human-rca-group');
            if (titleEl) {
              titleEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="margin-right:8px"></i>Form Evaluasi Umpan Balik (Feedback Salah)';
            }
            if (subEl) {
              subEl.textContent = `Incident #${incidentId} (${flag || 'Incident'}) — Akan dikirim ke antrean Four-Eyes Supervisor sebelum pembelajaran RAG.`;
            }
            if (rcaGroup) rcaGroup.style.display = 'block';
            document.getElementById('rej-mode').value = 'submit';
            document.getElementById('rej-incident-id').value = incidentId;
            document.getElementById('rej-flag').value = flag;
            document.getElementById('rej-reason-text').value = '';
            document.getElementById('rej-human-rca').value = '';
            document.getElementById('modal-feedback-rejection').style.display = 'flex';
            return;
          }

          if (card) {
            card.style.opacity = '.5';
            card.style.pointerEvents = 'none';
          }

          try {
            const resp = await this._authFetch('/api/feedback', {
              method: 'POST',
              body: JSON.stringify({
                incident_id: parseInt(incidentId, 10),
                score: 1.0,
                ai_rca: flag,
                human_rca: 'Manual verification',
                reviewer: this._getOperatorName()
              })
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok && (data.success || data.status === 'APPROVED')) {
              if (card) card.remove();
              Notify.toast('📚 Feedback Approved', `Ditandai BENAR · OTel Trace: ${data.trace_id || 'OK'}`, 'ok', 3000);
              if (typeof LogStreamer !== 'undefined' && LogStreamer.add) {
                LogStreamer.add('OK', 'TRAINING', `Feedback BENAR submitted for Incident ${incidentId} · Trace: ${data.trace_id || ''}`);
              }
              this._appendTerminal('OK', 'TRAINING', `Feedback BENAR submitted for Incident #${incidentId} · Trace: ${data.trace_id || 'OK'}`);
              this.load();
            } else {
              if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
              Notify.toast('❌ Gagal', data.error || data.message || `HTTP ${resp.status}`, 'error', 3500);
            }
          } catch (err) {
            if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
            Notify.toast('❌ Error API', err.message, 'error', 3500);
          }
        },

        async confirmRejection() {
          const incidentId = parseInt(document.getElementById('rej-incident-id').value || '0', 10);
          const flag = document.getElementById('rej-flag').value;
          const mode = document.getElementById('rej-mode')?.value || 'submit';
          const reason = (document.getElementById('rej-reason-text').value || '').trim();
          const humanRca = (document.getElementById('rej-human-rca').value || '').trim();

          if (!reason) {
            Notify.toast('⚠️ Input Wajib', 'Mohon isi Alasan / Catatan Evaluasi Manusia.', 'warn', 3000);
            return;
          }
          if (!incidentId) return;

          document.getElementById('modal-feedback-rejection').style.display = 'none';
          const card = document.getElementById('fb-' + incidentId);
          if (card) { card.style.opacity = '.5'; card.style.pointerEvents = 'none'; }

          const endpoint = mode === 'supervisor_reject' ? '/api/feedback/reject' : '/api/feedback';
          const payload = mode === 'supervisor_reject'
            ? {
                incident_id: incidentId,
                rejection_reason: reason,
                reviewer: this._getOperatorName()
              }
            : {
                incident_id: incidentId,
                score: 0.0,
                ai_rca: flag,
                human_rca: humanRca || reason,
                reviewer: this._getOperatorName(),
                rejection_reason: reason
              };

          try {
            const resp = await this._authFetch(endpoint, {
              method: 'POST',
              body: JSON.stringify(payload)
            });
            const res = await resp.json().catch(() => ({}));

            if (resp.ok && (res.success || res.status === 'success')) {
              if (mode === 'supervisor_reject') {
                Notify.toast('🚫 Feedback Rejected', `Evaluasi Insiden #${incidentId} ditolak Supervisor.`, 'warn', 3500);
                this._appendTerminal('WARN', 'HITL-GATE', `Supervisor menolak feedback Incident #${incidentId}: ${reason}`);
              } else {
                Notify.toast('🛡️ Feedback Evaluasi Tersimpan', `Dikirim ke Four-Eyes Reviewer Queue · Status: ${res.status}`, 'warn', 3500);
                this._appendTerminal('WARN', 'TRAINING', `Feedback SALAH submitted for Incident #${incidentId} · Status: ${res.status}`);
              }
              this.load();
            } else {
              if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
              Notify.toast('❌ Gagal', res.error || res.message || `HTTP ${resp.status}`, 'error', 3500);
            }
          } catch (err) {
            if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
            Notify.toast('❌ Error API', err.message, 'error', 3500);
          }
        },

        async approveFeedback(incidentId) {
          Notify.toast('⚡ Approving', `Reviewer memvalidasi RAG untuk Insiden ${incidentId}...`, 'info', 2000);
          try {
            const resp = await this._authFetch('/api/feedback/approve', {
              method: 'POST',
              body: JSON.stringify({ incident_id: parseInt(incidentId, 10), reviewer: this._getOperatorName() })
            });
            const res = await resp.json().catch(() => ({}));
            if (resp.ok && res.status === 'success') {
              Notify.toast('✅ RAG Ingested', 'Persetujuan Four-Eyes selesai · Data terpublikasi ke RAG', 'ok', 3000);
              this._appendTerminal('OK', 'HITL-GATE', `Four-Eyes Approval selesai untuk Incident #${incidentId} -> Published to RAG`);
              this.load();
            } else {
              Notify.toast('❌ Gagal', res.error || res.message || `HTTP ${resp.status}`, 'error', 3500);
            }
          } catch (e) {
            Notify.toast('❌ Error', e.message, 'error', 3500);
          }
        },

        async export(format) {
          const fmt = format === 'json' ? 'json' : 'csv';
          Notify.toast('📥 Exporting Audit', `Mengunduh riwayat feedback RAG (${fmt.toUpperCase()})...`, 'info', 2000);
          try {
            const resp = await this._authFetch(`/api/feedback/export?format=${encodeURIComponent(fmt)}`);
            if (!resp.ok) {
              const errJson = await resp.json().catch(() => ({}));
              throw new Error(errJson.error || errJson.message || `HTTP ${resp.status}`);
            }
            const checksum = resp.headers.get('X-Audit-Checksum-SHA256') || 'UNKNOWN';
            const blob = await resp.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `training_feedback_audit_${Date.now()}.${fmt}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 1500);
            Notify.toast('✅ Export Completed', `File downloaded. SHA256 Integrity: ${checksum.substring(0, 16)}...`, 'ok', 4000);
          } catch (e) {
            Notify.toast('❌ Export Error', e.message, 'err', 3500);
          }
        },

        async sendTeacherPrompt() {
          const inp = document.getElementById('tr-teacher-input');
          const term = document.getElementById('tr-live-log-terminal');
          if (!inp || !term) return;
          const promptText = inp.value.trim();
          if (!promptText) return;
          inp.value = '';

          this._appendTerminal('INFO', 'TEACHER-PROMPT', `"${promptText}"`);
          this._appendTerminal('WARN', 'AI-REASONING', 'Processing query via 7-Stage Security Gateway & RAG Engine...');

          try {
            const resp = await this._authFetch(`/api/enterprise/chat/ai_assist?client_id=SUPERADMIN_TEACHER&query=${encodeURIComponent(promptText)}`);
            if (resp.ok) {
              const data = await resp.json();
              const rawResult = String(data.suggestion || data.warning || 'AI Response Generated');
              const safeHtmlResult = this._esc(rawResult).replace(/\n/g, '<br>');
              this._appendTerminal('OK', 'AI-OUTPUT', `<br>${safeHtmlResult}`, true);

              const actionRow = document.createElement('div');
              actionRow.style.marginTop = '4px';
              actionRow.style.display = 'flex';
              actionRow.style.gap = '6px';
              actionRow.style.alignItems = 'center';
              actionRow.innerHTML = `<button class="btn btn-warning btn-xs" style="padding:2px 8px;font-size:10px;" data-teach-prompt="${this._esc(promptText)}"><i class="fa-solid fa-graduation-cap" style="margin-right:4px"></i>Ajarkan Solusi Benar ke AI</button>`;
              term.appendChild(actionRow);

              this._appendTerminal('DEBUG', 'SECURITY-GW', '7-Stage 0-Trust Evaluated · Gunakan tombol Ajarkan Solusi jika perlu koreksi ground truth.');
            } else {
              const errJson = await resp.json().catch(() => ({}));
              this._appendTerminal('ERR', 'API-ERROR', errJson.error || resp.statusText || `HTTP ${resp.status}`);
            }
          } catch (e) {
            this._appendTerminal('ERR', 'ERROR', e.message);
          }
          term.scrollTop = term.scrollHeight;
        },

        teachAIInteractive(problemStr) {
          let prob = problemStr || '';
          try {
            if (prob.includes('%')) prob = decodeURIComponent(prob);
          } catch (_) {}
          prob = prob.trim() || 'Insiden / gejala belum dispesifikasikan';

          if (!window.Modal || typeof Modal.show !== 'function') {
            return;
          }

          const bodyHtml = `
            <div style="font-size:12px;display:flex;flex-direction:column;gap:10px">
              <div>
                <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--txt2)">Permasalahan / Gejala (Problem):</label>
                <input id="tr-teach-prob-input" class="inp" style="width:100%" value="${this._esc(prob)}" />
              </div>
              <div>
                <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--txt2)">Kategori Pengetahuan (RAG Category):</label>
                <select id="tr-teach-cat-input" class="inp" style="width:100%">
                  <option value="SUPERADMIN_TEACHER_REVISION">SUPERADMIN_TEACHER_REVISION</option>
                  <option value="NOC_RUNBOOK">NOC_RUNBOOK</option>
                  <option value="INFRASTRUCTURE_FIX">INFRASTRUCTURE_FIX</option>
                  <option value="NETWORK_TROUBLESHOOTING">NETWORK_TROUBLESHOOTING</option>
                  <option value="PRINTER_PERIPHERAL">PRINTER_PERIPHERAL</option>
                </select>
              </div>
              <div>
                <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--txt2)">Solusi Benar / Langkah Remediasi Ground Truth:</label>
                <textarea id="tr-teach-sol-input" class="inp" rows="4" style="width:100%" placeholder="Masukkan langkah perbaikan terverifikasi (satu langkah per baris)..."></textarea>
              </div>
            </div>
          `;

          Modal.show('Ajarkan Solusi Benar ke AI (RAG Store)', bodyHtml, [
            { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() },
            {
              label: 'Simpan & Latih AI',
              cls: 'btn-primary',
              fn: async () => {
                const editedProb = (document.getElementById('tr-teach-prob-input')?.value || '').trim();
                const category = (document.getElementById('tr-teach-cat-input')?.value || '').trim();
                const solution = (document.getElementById('tr-teach-sol-input')?.value || '').trim();
                if (!editedProb || !solution) {
                  Notify.toast('⚠️ Input Wajib', 'Problem dan Solusi wajib diisi.', 'warn', 2500);
                  return;
                }
                Modal.close();
                Notify.toast('🎓 Teaching AI', 'Mengirimkan koreksi solusi ke RAG Engine...', 'info', 2000);
                try {
                  const resp = await this._authFetch('/api/enterprise/chat/teach_ai', {
                    method: 'POST',
                    body: JSON.stringify({ problem: editedProb, solution, category })
                  });
                  const res = await resp.json().catch(() => ({}));
                  if (resp.ok) {
                    Notify.toast('✅ AI Learned Solution!', res.message || 'Tersimpan ke RAG Knowledge Engine', 'ok', 4000);
                    this._appendTerminal(
                      'WARN',
                      'TEACHER-SAVE',
                      `Masalah: "${this._esc(editedProb)}"<br>✅ Solusi: "${this._esc(solution)}"<br>💾 Persisted Item: ${this._esc(res.item_id || 'OK')} (${this._esc(category)})`,
                      true
                    );
                    this.load();
                  } else {
                    Notify.toast('❌ Gagal Mengajar AI', res.error || res.message || `HTTP ${resp.status}`, 'error', 3500);
                  }
                } catch (err) {
                  Notify.toast('❌ Error API', err.message, 'error', 3500);
                }
              }
            }
          ], '🎓');
        }
      },

});

window.Modules["4_ai_lifecycle"]["training"] = window.Panels;
