/* modules/2_fleet_health/agent-health.js
 * Atomic Design — 3. Modules Layer (2_fleet_health / agent-health)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      agent_health: {
        _hasLoaded: false,
        _agents: [],
        _formatUptime(sec) {
          const s = Math.max(0, Number(sec) || 0);
          if (s === 0) return '—';
          const d = Math.floor(s / 86400);
          const h = Math.floor((s % 86400) / 3600);
          const m = Math.floor((s % 3600) / 60);
          const rem = Math.floor(s % 60);
          if (d > 0) return `${d}d ${h}h ${m}m`;
          if (h > 0) return `${h}h ${m}m`;
          if (m > 0) return `${m}m ${rem}s`;
          return `${rem}s`;
        },
        _formatLastSeen(ts) {
          if (!ts || String(ts).startsWith('0001-01-01')) return 'Belum ada heartbeat';
          return typeof timeSince === 'function' ? timeSince(ts) : String(ts);
        },
        async load(silent = false) {
          const tbody = document.getElementById('agent-health-tbody');
          if (!tbody) return;
          if (!silent && !this._hasLoaded) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--green);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat AI Agent Health...</div></td></tr>';
          }

          try {
            const agents = await (window.Services.Data || DataService).loadAgentHealth();
            this._agents = Array.isArray(agents) ? agents : [];
            if (this._agents.length === 0) {
              tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:25px;color:var(--txt2)">Tidak ada AI Agent terdaftar</td></tr>';
              setEl('ah-summary-badge', '0 / 0 ONLINE');
              return;
            }
            this._hasLoaded = true;

            const agentMap = {};
            this._agents.forEach(a => {
              const key = String(a && (a.agent || a.subject) || '').toLowerCase().replace(/^(ai\.|agent\.)/, '');
              if (key) agentMap[key] = a;
            });

            const updateKpi = (idPrefix, agentName) => {
              const a = agentMap[agentName];
              const el = document.getElementById('kpi-agent-' + idPrefix);
              if (a) {
                const isOn = a.status === 'ONLINE';
                const rtt = typeof a.latency_ms === 'number' ? a.latency_ms.toFixed(2) : '0.00';
                const cpu = typeof a.cpu === 'number' ? a.cpu.toFixed(2) : '0.00';
                setEl('kpi-agent-' + idPrefix, a.status || 'OFFLINE');
                setEl('kpi-agent-' + idPrefix + '-rtt', isOn ? `RTT: ${rtt} ms | CPU: ${cpu}%` : 'No recent heartbeat');
                if (el) el.style.color = isOn ? 'var(--green)' : 'var(--red)';
              } else {
                setEl('kpi-agent-' + idPrefix, 'OFFLINE');
                setEl('kpi-agent-' + idPrefix + '-rtt', 'No heartbeat received');
                if (el) el.style.color = 'var(--red)';
              }
            };

            updateKpi('incident', 'incident');
            updateKpi('recovery', 'recovery');
            updateKpi('security', 'security');
            updateKpi('verify', 'verify');

            const onlineCount = this._agents.filter(a => a && a.status === 'ONLINE').length;
            const badgeEl = document.getElementById('ah-summary-badge');
            if (badgeEl) {
              badgeEl.textContent = `${onlineCount} / ${this._agents.length} ONLINE`;
              badgeEl.className = `tag ${onlineCount === this._agents.length ? 'tag-green' : onlineCount > 0 ? 'tag-orange' : 'tag-red'}`;
            }
            setEl('ah-last-refresh', 'Refresh: ' + new Date().toLocaleTimeString('id-ID'));

            let html = '';
            for (const a of this._agents) {
              if (!a) continue;
              const rawAgent = String(a.agent || a.subject || 'unknown');
              const isOnline = a.status === 'ONLINE';
              const statusCol = isOnline
                ? '<span style="color:var(--green)"><i class="fa-solid fa-circle-check"></i> ONLINE</span>'
                : '<span style="color:var(--red)"><i class="fa-solid fa-circle-xmark"></i> OFFLINE</span>';
              const latText = isOnline && typeof a.latency_ms === 'number' ? `${a.latency_ms.toFixed(2)} ms` : '—';
              const verText = _esc(a.version || 'v2.2');
              const lastSeenStr = this._formatLastSeen(a.last_seen);
              const lastSeenTitle = a.last_seen && !String(a.last_seen).startsWith('0001-01-01') ? _esc(a.last_seen) : '';
              html += `<tr data-agent="${_esc(rawAgent.toLowerCase())}" data-status="${_esc(a.status || 'OFFLINE')}">
                <td><strong>ai.${_esc(rawAgent.replace(/^(ai\.|agent\.)/, ''))}</strong></td>
                <td><span class="tag tag-blue">${verText}</span></td>
                <td>${statusCol}</td>
                <td style="font-family:monospace">${_esc(latText)}</td>
                <td>${_esc(this._formatUptime(a.uptime))}</td>
                <td>${Number(a.queue_depth) || 0} jobs</td>
                <td>${typeof a.cpu === 'number' ? a.cpu.toFixed(2) : '0.00'}%</td>
                <td style="color:var(--txt2)" title="${lastSeenTitle}">${_esc(lastSeenStr)}</td>
              </tr>`;
            }
            tbody.innerHTML = html;
            this.applyFilters();
          } catch (e) {
            console.error("Failed to load AI agents:", e);
            if (!this._hasLoaded) {
              tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark"></i> Gagal memuat data</td></tr>`;
            }
          }
          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.agent_health) {
            window.ActiveIntervals.agent_health = setInterval(() => {
              const panel = document.getElementById('p-agent_health');
              if (document.hidden || !panel || !panel.classList.contains('active')) return;
              this.load(true);
            }, 10000);
          }
        },
        applyFilters() {
          const q = ((document.getElementById('ah-search') || {}).value || '').toLowerCase().trim();
          const st = ((document.getElementById('ah-filter-status') || {}).value || '').toUpperCase();
          const tbody = document.getElementById('agent-health-tbody');
          if (!tbody) return;
          tbody.querySelectorAll('tr[data-agent]').forEach(tr => {
            const matchQ = !q || (tr.dataset.agent || '').includes(q);
            const matchSt = !st || (tr.dataset.status || '').toUpperCase() === st;
            tr.style.display = (matchQ && matchSt) ? '' : 'none';
          });
        }
      },

});

window.Modules["2_fleet_health"]["agent-health"] = window.Panels;
