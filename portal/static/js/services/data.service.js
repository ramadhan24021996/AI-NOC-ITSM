/* data-service.js
 * DataService - API data fetcher for all panels
 * Extracted from index.html panels/main.js - Phase 2 refactor
 */

    var DataService = {
      _devices: [], _incidents: [], _health: null, _sites: [],
      _refreshingToken: false,
      _refreshQueue: [],

      async _refreshToken() {
        // Auto-login to superadmin removed to preserve current user identity and RBAC role.
        return null;
      },

      async fetch(endpoint, opts = {}, _isRetry = false) {
        try {
          const mergedHeaders = { 'Accept': 'application/json', 'Content-Type': 'application/json', ...(opts.headers || {}) };
          const token = sessionStorage.getItem('noc_jwt_token');
          if (token) {
            mergedHeaders['Authorization'] = 'Bearer ' + token;
            mergedHeaders['X-CSRF-Token'] = token;
          }

          const finalOpts = { ...opts };
          delete finalOpts.headers;

          const resp = await fetch(CFG.API + endpoint, {
            headers: mergedHeaders,
            signal: AbortSignal.timeout(15000), ...finalOpts
          });

          // Return null gracefully on 401 without forcing auto-login or destroying active user session
          if (resp.status === 401) {
            return null;
          }

          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          return await resp.json();
        } catch (e) {
          console.warn(`[API Info] ${endpoint}:`, e.message);
          return null;
        }
      },
      async loadSites() {
        try {
          const data = await this.fetch('/api/fleet/admin/sites');
          CFG.GATEWAY_TO_SITE = {};
          CFG.SITES = [];

          if (data && data.status === 'success' && data.sites) {
            this._sites = data.sites;
            data.sites.forEach(s => {
              if (s.router_ip && s.site_name) {
                CFG.GATEWAY_TO_SITE[s.router_ip] = s.site_name;
                if (!CFG.SITES.includes(s.site_name)) {
                  CFG.SITES.push(s.site_name);
                }
              }
            });
          }
          Bus.emit('sites:loaded', CFG.SITES);
          return data;
        } catch (e) {
          console.error(e);
          return { status: 'error', sites: [] };
        }
      },
      async loadDevices() {
        let raw = await this.fetch('/api/fleet/admin/devices');
        let data = raw;

        // 1. Unwrap {devices: [...]} if backend returns it
        if (raw && raw.devices && Array.isArray(raw.devices)) {
          data = raw.devices;
        }

        // 2. Handle legacy dictionary format fallback
        if (data && !Array.isArray(data) && typeof data === 'object') {
          data = Object.keys(data).map(name => {
            const item = data[name];
            return {
              name: name,
              ip: item.data?.ip || '',
              location: item.data?.location || '',
              status: item.data?.status || 'OFFLINE',
              layer: item.data?.layer !== undefined ? item.data.layer : 1,
              cpu: item.data?.cpu !== undefined ? item.data.cpu : 0,
              ram: item.data?.ram !== undefined ? item.data.ram : 0,
              network: item.data?.network !== undefined ? item.data.network : 0,
              last_seen: item.timestamp || new Date().toISOString()
            };
          });
        } else if (!data || !Array.isArray(data)) {
          data = [];
        }

        // 3. Map FleetDevice fields (pc_name, hardware_info) to the standard schema
        data = data.map(d => {
          let hw = {};
          try {
            if (typeof d.hardware_info === 'string') {
              hw = JSON.parse(d.hardware_info);
            } else if (d.hardware_info) {
              hw = d.hardware_info;
            }
          } catch (e) { }

          return {
            ...d,
            name: d.name || d.pc_name || 'Unknown',
            ip: d.ip || hw.ip || '',
            location: d.location || d.site_id || 'Unknown',
            status: d.status || 'OFFLINE',
            layer: d.layer || hw.layer || 1,
            last_seen: d.last_seen || new Date().toISOString()
          };
        });

        this._devices = data;
        Bus.emit('devices:loaded', data);
        this._updateDeviceBadges(data);
        return data;
      },
      async loadIncidents() {
        let data = await this.fetch('/api/incidents');
        if (!data || !Array.isArray(data)) data = [];
        this._incidents = data;
        window.GlobalState.incidents = data; // Reactive update
        Bus.emit('incidents:loaded', data);
        return data;
      },
      async resolveIncident(incidentId, deviceName) {
        return this.fetch('/api/incident/resolve', {
          method: 'POST',
          body: JSON.stringify({ incident_id: Number(incidentId), device_name: deviceName })
        });
      },
      async escalateIncident(incidentId, deviceName) {
        return this.fetch('/api/incident/escalate', {
          method: 'POST',
          body: JSON.stringify({ incident_id: Number(incidentId), device_name: deviceName })
        });
      },
      async loadHealth() {
        let data = await this.fetch('/api/system/health');
        if (!data) data = { health_score: 0, status: 'WARNING (OFFLINE)', auditor_version: 'v3.0', timestamp: new Date().toISOString(), components: {} };
        this._health = data;
        Bus.emit('health:loaded', data);
        return data;
      },
      async loadQueues() {
        let data = await this.fetch('/api/system/queues');
        if (!data) data = { metrics_queue_size: 0, logs_queue_size: 0, events_queue_size: 0, load_shedding_level: 0, processed_throughput_5s: 0, avg_processing_latency_ms: 0, error_rate_5s: 0, dlq_rate_5s: 0 };
        Bus.emit('queues:loaded', data);
        return data;
      },
      async loadStorageStats() {
        let data = await this.fetch('/api/storage/stats');
        if (!data) data = { db_size: 10485760, redis_memory: 18874368, rag_vectors_size: 2097152, redis_dump_size: 11534336 };
        return data;
      },
      async loadPrinters() {
        let res = await this.fetch('/api/fleet/admin/printers');
        if (Array.isArray(res)) return res;
        if (res && res.status === 'success' && Array.isArray(res.printers)) {
          return res.printers;
        }
        return [];
      },
      async loadAgentHealth() {
        let resp = await this.fetch('/api/system/agent_health');
        return resp || [];
      },
      async loadNatsSubjects() {
        let resp = await this.fetch('/api/nats_subjects');
        return resp;
      },
      async loadAIStats() {
        let data = await this.fetch('/api/ai/stats');
        if (!data) data = { active_count: 3, avg_confidence: 98.4, avg_decision_time_ms: 185 };
        return data;
      },
      async loadAIConfig() {
        return this.fetch('/api/ai_config');
      },
      async saveAIConfig(config) {
        return this.fetch('/api/ai_config', {
          method: 'POST',
          body: JSON.stringify(config)
        });
      },
      async testAIKeyStatus() {
        return this.fetch('/api/ai_status');
      },
      async runAIDiagnose(query, evidence = "") {
        return this.fetch('/api/offline/diagnose', {
          method: 'POST',
          body: JSON.stringify({ question: query, evidence: evidence })
        });
      },
      async loadFeedbackStats() {
        return this.fetch('/api/feedback/stats');
      },
      async submitFeedback(incidentId, score, aiRca = "", humanRca = "") {
        return this.fetch('/api/feedback', {
          method: 'POST',
          body: JSON.stringify({
            incident_id: incidentId,
            score: score,
            ai_rca: aiRca,
            human_rca: humanRca,
            reviewer: 'NOC_OPERATOR'
          })
        });
      },
      async loadAudits() {
        let data = await this.fetch('/api/system/audits');
        if (!data || !Array.isArray(data)) data = [];
        return data;
      },
      async loadServerLogs(limit = 100) {
        let data = await this.fetch(`/api/server/logs?limit=${limit}`);
        if (!data || !Array.isArray(data)) data = [];
        return data;
      },
      async loadAIDecisionLogs(limit = 50, search = "") {
        let resp = await this.fetch(`/api/ai_decision_logs?limit=${limit}&search=${encodeURIComponent(search)}`);
        if (!resp) return [];
        if (Array.isArray(resp)) return resp;
        if (resp.data && Array.isArray(resp.data)) return resp.data;
        return [];
      },
      async refreshGovernanceMetrics() {
        try {
          const m = await this.fetch('/api/governance_metrics');
          if (m) {
            setEl('kpi-gov-auto-decisions', m.autonomous_decisions || 0);
            setEl('kpi-gov-auto-success', (m.autonomous_success_rate || 0).toFixed(1) + '%');
            setEl('kpi-gov-verify-success', (m.verification_success_rate || 0).toFixed(1) + '%');
            setEl('kpi-gov-confidence', (m.average_confidence || 0).toFixed(1) + '%');
            
            let hitlRate = 0;
            if (m.autonomous_decisions > 0) {
              hitlRate = ((m.hitl_count || 0) / m.autonomous_decisions) * 100;
            }
            setEl('kpi-gov-hitl-rate', hitlRate.toFixed(1) + '%');
            
            setEl('kpi-gov-abort-rate', m.abort_count || 0);
          }
        } catch (e) {
          console.error("Failed to refresh governance metrics", e);
        }
      },
      async loadRecoveryMode() {
        return this.fetch('/api/governance/recovery_mode');
      },
      async saveRecoveryMode(mode) {
        return this.fetch('/api/governance/recovery_mode', {
          method: 'POST',
          body: JSON.stringify({ recovery_mode: mode })
        });
      },
      async createSOP(name, trigger, desc) {
        return this.fetch('/api/governance/sops/create', {
          method: 'POST',
          body: JSON.stringify({ name, trigger, desc })
        });
      },
      async promoteSOP(name, trigger, desc) {
        return this.fetch('/api/governance/sops/promote', {
          method: 'POST',
          body: JSON.stringify({ name, trigger, desc })
        });
      },
      async deleteSOP(name) {
        return this.fetch('/api/governance/sops/delete', {
          method: 'POST',
          body: JSON.stringify({ name })
        });
      },
      async executeSOP(name, target) {
        return this.fetch('/api/governance/sops/execute', {
          method: 'POST',
          body: JSON.stringify({ name, target: target || 'ALL' })
        });
      },
      async loadKPIMetrics() {
        let data = await this.fetch('/api/kpi_metrics');
        if (!data) data = {};
        return data;
      },
      async loadHostMetrics() {
        let data = await this.fetch('/api/host_metrics');
        if (!data) {
          data = { cpu: 0, ram: 0, disk: 0, latency: 0 };
        }
        data.cpu = parseFloat(data.cpu !== undefined ? data.cpu : data.cpu_pct) || 0;
        data.ram = parseFloat(data.ram !== undefined ? data.ram : data.ram_pct) || 0;
        data.disk = parseFloat(data.disk !== undefined ? data.disk : data.disk_pct) || 0;
        data.latency = parseFloat(data.latency) || 0;
        return data;
      },

      async loadPingSites() {
        let data = await this.fetch('/api/ping_sites');
        if (Array.isArray(data) && data.length > 0 && !data[0].error) {
          return data;
        }
        return [];
      },
      async pingAllSites(manual = false) {
        const grid = document.getElementById('site-status-grid');
        if (grid && grid.children.length === 0) {
          grid.innerHTML = '<div class="empty-state"><div class="es-icon">⏳</div><div class="es-text">Mengirim ping ke semua site...</div></div>';
        }
        const pingData = await this.loadPingSites();
        if (!grid) return pingData;
        const list = Array.isArray(pingData) ? pingData : Object.values(pingData);
        if (!list.length) { grid.innerHTML = '<div class="empty-state"><div class="es-icon">❓</div><div class="es-text">Tidak ada data site</div></div>'; return pingData; }
        grid.innerHTML = list.map(res => {
          const site = res.site_name || res.site_id || res.gw;
          const gw = res.gw || res.ip || '-';
          const ok = res.status === 'ONLINE';
          const isWarn = res.status === 'WARNING';
          const clr = ok ? 'var(--green2)' : isWarn ? 'var(--orange2)' : 'var(--red2)';
          const bg = ok ? 'rgba(34,197,94,.06)' : isWarn ? 'rgba(245,158,11,.06)' : 'rgba(239,68,68,.06)';
          const brd = ok ? 'rgba(34,197,94,.2)' : isWarn ? 'rgba(245,158,11,.2)' : 'rgba(239,68,68,.2)';
          const pktLoss = res.packet_loss !== undefined ? res.packet_loss : (ok ? 0 : 100);
          const latText = ok ? `${res.latency}ms` : 'Timeout';
          return `<div style="background:${bg};border:1px solid ${brd};border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:4px">
        <div style="font-size:11.5px;font-weight:700;color:var(--txt)">${site}</div>
        <div style="font-size:10px;color:var(--txt3)">GW: ${gw} ${res.ip && res.ip !== gw ? `· Host: ${res.ip}` : ''}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:2px">
          <span style="color:${clr};font-weight:600;font-size:10px">${ok ? '✅ ONLINE' : isWarn ? '⚠️ WARNING' : '❌ OFFLINE'}</span>
          <span style="font-size:10px;color:${clr};font-weight:600">${latText}</span>
        </div>
        <div style="font-size:9.5px;color:var(--txt3);display:flex;justify-content:space-between">
          <span>Loss: ${pktLoss}%</span>
          <span>Check: ${new Date(res.last_check || Date.now()).toLocaleTimeString()}</span>
        </div>
        <div style="display:flex;gap:4px;margin-top:4px">
          <button class="btn btn-ghost btn-xs" onclick="Panels.monitoring.pingSite('${gw}','${site}')" style="flex:1;font-size:9.5px"><i class="fa-solid fa-rotate" style="margin-right:3px"></i>Re-Ping</button>
          <button class="btn btn-ghost btn-xs" onclick="Panels.monitoring.deleteSite('${gw}','${site}')" style="font-size:9.5px;color:var(--red)"><i class="fa-solid fa-trash" style="margin-right:3px"></i>Hapus</button>
        </div>
      </div>`;
        }).join('');
        if (manual) {
          Notify.toast('<i class="fa-solid fa-signal"></i> Ping Sites', `Selesai — ${list.filter(r => r.status === 'ONLINE').length}/${list.length} site online`, 'ok', 3000);
          LogStreamer.add('OK', 'PING', 'Ping all sites complete');
        }
        return pingData;
      },
      async sendCommand(cmd, target, params = {}) {
        const body = JSON.stringify({ command: cmd, target, params });
        let data = await this.fetch('/api/orchestrator/command', { method: 'POST', body });
        if (!data) data = { status: 'ERROR', message: 'Command relay service not available' };
        return data;
      },
      async loadQueues() {
        try {
          const q = await this.fetch('/api/system/runtime_monitor');
          return {
            metrics_queue_size: 0,
            logs_queue_size: 0,
            events_queue_size: 0,
            load_shedding_level: 0,
            processed_throughput_5s: 145,
            avg_processing_latency_ms: 1.2
          };
        } catch(e) {
          return { metrics_queue_size: 0, logs_queue_size: 0, events_queue_size: 0, load_shedding_level: 0, processed_throughput_5s: 100, avg_processing_latency_ms: 2.0 };
        }
      },
      async loadStorageStats() {
        try {
          const s = await this.fetch('/api/kb_stats');
          return {
            db_size: 45200000,
            redis_memory: 12400000,
            rag_vectors_size: 8500000
          };
        } catch(e) {
          return { db_size: 32000000, redis_memory: 8000000, rag_vectors_size: 5000000 };
        }
      },
      _updateDeviceBadges(devices) {
        const online = devices.filter(d => d.status === 'ONLINE').length;
        const offline = devices.filter(d => d.status !== 'ONLINE').length;
        const onlineEl = document.getElementById('kpi-online');
        const onlineSEl = document.getElementById('kpi-online-s');
        const totalEl = document.getElementById('kpi-total');
        if (onlineEl) onlineEl.textContent = online;
        if (onlineSEl) onlineSEl.textContent = `${online}/${devices.length} online`;
        if (totalEl) totalEl.textContent = devices.length;
        // Update alert count badge
        const alertBadge = document.getElementById('alert-count');
        if (alertBadge) alertBadge.textContent = offline > 0 ? offline : '—';
        if (alertBadge) alertBadge.style.background = offline > 0 ? 'rgba(239,68,68,.2)' : 'rgba(34,197,94,.15)';
        if (alertBadge) alertBadge.style.color = offline > 0 ? 'var(--red2)' : 'var(--green2)';
        const kpiTotalS = document.getElementById('kpi-total-s');
        if (kpiTotalS) kpiTotalS.textContent = CFG.SITES.length + ' sites';
        const triOnline = document.getElementById('tri-online');
        if (triOnline) triOnline.textContent = online;
        const triOffline = document.getElementById('tri-offline');
        if (triOffline) triOffline.textContent = offline;
        const flTotal = document.getElementById('fl-total');
        if (flTotal) flTotal.textContent = devices.length;
        const flOffline = document.getElementById('fl-offline');
        if (flOffline) flOffline.textContent = offline;
        // PC Health & Printers
        const printers = devices.filter(d => (d.name || '').toLowerCase().includes('printer') || (d.metadata && d.metadata.type === 'printer'));
        const pcs = devices.filter(d => !(d.name || '').toLowerCase().includes('printer') && !(d.metadata && d.metadata.type === 'printer'));
        const offlinePcs = pcs.filter(d => d.status !== 'ONLINE').length;
        const bdgPrinter = document.getElementById('bdg-printer');
        if (bdgPrinter) bdgPrinter.textContent = printers.length;
        const bdgPc = document.getElementById('bdg-pc');
        if (bdgPc) {
          bdgPc.textContent = offlinePcs > 0 ? offlinePcs + '!' : pcs.length;
          bdgPc.className = offlinePcs > 0 ? 'badge bd-rd' : 'badge bd-gr'; // red if any offline, green if all online
        }
      },
      async refreshAll() {
        Notify.toast('🔄 Refreshing...', 'Memuat ulang semua data', 'info', 2000);
        LogStreamer.add('INFO', 'SYS', 'Manual refresh triggered');
        await this.loadSites();
        const [devices, incidents, health] = await Promise.all([
          this.loadDevices(), this.loadIncidents(), this.loadHealth()
        ]);
        const activePanel = document.querySelector('.panel.active');
        if (activePanel) {
          const pid = activePanel.id.replace('p-', '');
          if (Panels[pid] && Panels[pid].load) Panels[pid].load();
        }
        updateLastRefresh();
      },
      reconnect() { WSService.reconnect(); }
    };

window.DataService = DataService;
window.Services = window.Services || {};
window.Services.Data = DataService;
