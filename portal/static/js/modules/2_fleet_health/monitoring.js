/* modules/2_fleet_health/monitoring.js
 * Atomic Design — 3. Modules Layer (2_fleet_health / monitoring)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      monitoring: {
        _chartReady: false,
        _loading: false,
        _busBound: false,

        _esc(s) {
          if (typeof _esc === 'function') return _esc(s);
          return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        },

        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          bus.on('devices:loaded', () => {
            if (typeof isPanelActive === 'function' && isPanelActive('monitoring')) {
              this._updateMetrics();
            }
          });
        },

        async load() {
          this._bindBus();
          const metrics = await (window.Services.Data || DataService).loadHostMetrics();
          if (!this._chartReady || !Charts._instances || !Charts._instances['chart-latency']) {
            this._initLatencyChart(metrics.history, metrics.latency, metrics.db_response_ms);
            this._chartReady = true;
          }
          await this._updateMetrics(metrics);

          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.monitoring) {
            window.ActiveIntervals.monitoring = setInterval(() => {
              const panel = document.getElementById('p-monitoring');
              if (document.hidden || !panel || !panel.classList.contains('active')) return;
              this._updateMetrics();
            }, 5000);
          }
        },

        async _updateMetrics(metrics = null) {
          if (this._loading) return;
          this._loading = true;
          try {
            const ds = (window.Services.Data || DataService);
            const t0 = performance.now();
            const [m, pingData] = await Promise.all([
              metrics ? Promise.resolve(metrics) : ds.loadHostMetrics(),
              ds.loadPingSites()
            ]);
            const measuredRtt = Math.max(1, Math.round(performance.now() - t0));

            const cpu = Number((m && m.cpu) || 0).toFixed(1);
            const ram = Number((m && m.ram) || 0).toFixed(1);
            const disk = Number((m && m.disk) || 0).toFixed(1);
            const cpuNum = parseFloat(cpu);
            const ramNum = parseFloat(ram);
            const diskNum = parseFloat(disk);

            // Live render site cards without making a second /api/ping_sites call
            await ds.pingAllSites(false, pingData);

            const pings = (Array.isArray(pingData) ? pingData : Object.values(pingData)).filter(t => t && t.site_id !== '(no sites)');
            const activeTargets = pings.filter(t => t.status === 'ONLINE' || t.status === 'WARNING');
            const avgLat = activeTargets.length > 0
              ? Math.round(activeTargets.reduce((sum, t) => sum + (t.latency > 0 ? t.latency : 0), 0) / activeTargets.length)
              : Math.round((m && m.latency) || 0);

            const totalLoss = pings.reduce((sum, t) => sum + (t.packet_loss !== undefined ? parseFloat(t.packet_loss) : (t.status === 'OFFLINE' ? 100 : 0)), 0);
            const pktLoss = pings.length > 0 ? (totalLoss / pings.length).toFixed(1) : '0.0';

            const apiRespTime = (m && m.db_response_ms > 0) ? Number(m.db_response_ms).toFixed(1) : measuredRtt;

            setEl('mon-latency', avgLat + ' ms');
            setEl('mon-pktloss', pktLoss + '%');
            setEl('mon-resptime', apiRespTime + ' ms');
            setEl('mon-cpu', cpu + '%');

            setEl('mon-cpu-pct', cpu + '%');
            setEl('mon-ram-pct', ram + '%');
            setEl('mon-disk-pct', disk + '%');
            setEl('mon-pl-pct', pktLoss + '%');

            const cpuBar = document.getElementById('mon-cpu-bar');
            const ramBar = document.getElementById('mon-ram-bar');
            const diskBar = document.getElementById('mon-disk-bar');
            const plBar = document.getElementById('mon-pl-bar');

            if (cpuBar) {
              cpuBar.style.width = Math.min(100, cpuNum) + '%';
              cpuBar.style.background = cpuNum > 90 ? 'var(--red)' : cpuNum > 75 ? 'var(--orange)' : 'var(--blue)';
            }
            if (ramBar) {
              ramBar.style.width = Math.min(100, ramNum) + '%';
              ramBar.style.background = ramNum > 90 ? 'var(--red)' : ramNum > 80 ? 'var(--orange)' : 'var(--purple)';
            }
            if (diskBar) {
              diskBar.style.width = Math.min(100, diskNum) + '%';
              diskBar.style.background = diskNum > 90 ? 'var(--red)' : diskNum > 80 ? 'var(--orange)' : 'var(--cyan)';
            }
            if (plBar) {
              const lossVal = Math.min(100, Math.max(0, parseFloat(pktLoss)));
              plBar.style.width = lossVal + '%';
              plBar.style.background = lossVal > 15 ? 'var(--red)' : lossVal > 5 ? 'var(--orange)' : 'var(--green)';
            }

            const t = new Date().toTimeString().slice(0, 8);
            Charts.addPoint('chart-latency', t, [avgLat, parseFloat(apiRespTime)]);
          } finally {
            this._loading = false;
          }
        },

        _initLatencyChart(history, initLat, initResp) {
          const baseLat = parseFloat(initLat) > 0 ? parseFloat(initLat) : 2;
          const baseResp = parseFloat(initResp) > 0 ? parseFloat(initResp) : 1;
          const labels = (history && Array.isArray(history.labels) && history.labels.length > 0)
            ? history.labels
            : Array.from({ length: 15 }, (_, i) => {
                const d = new Date(Date.now() - (14 - i) * 5000);
                return d.toTimeString().slice(0, 8);
              });
          const latData = (history && Array.isArray(history.latency) && history.latency.length > 0)
            ? history.latency
            : Array.from({ length: labels.length }, () => baseLat);
          const respData = (history && Array.isArray(history.response) && history.response.length > 0)
            ? history.response
            : Array.from({ length: labels.length }, () => baseResp);

          Charts.create('chart-latency', 'line', labels, [
            { label: 'Latency (ms)', data: latData, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.1)', tension: .4, fill: true },
            { label: 'DB Response (ms)', data: respData, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,.05)', tension: .4, fill: false }
          ], { legend: true });
        },

        async _renderSites() {
          await (window.Services.Data || DataService).pingAllSites();
        },

        async deleteSite(gw, siteName, siteId = '') {
          const safeName = this._esc(siteName);
          Modal.confirm('🗑️ Hapus Site', 'Apakah Anda yakin ingin menghapus site <b>' + safeName + '</b> secara permanen?', async () => {
            Modal.close();
            try {
              const ds = (window.Services.Data || DataService);
              let targetId = siteId;
              if (!targetId) {
                const data = await ds.fetch('/api/fleet/admin/sites');
                const sites = (data && Array.isArray(data.sites)) ? data.sites : [];
                const target = sites.find(s => s.router_ip === gw || s.site_name === siteName);
                if (target) targetId = target.site_id;
              }

              if (!targetId) {
                Notify.toast('❌ Hapus', 'Site tidak ditemukan di database.', 'err');
                return;
              }

              const delData = await ds.fetch('/api/fleet/admin/sites/delete/' + encodeURIComponent(targetId), { method: 'POST' });
              if (delData && delData.status === 'success') {
                Notify.toast('✅ Hapus', 'Site ' + siteName + ' berhasil dihapus', 'ok');
                LogStreamer.add('OK', 'CONFIG', 'Site deleted: ' + siteName);
                if (typeof RemoteSettings !== 'undefined' && RemoteSettings.loadSites) {
                  RemoteSettings.loadSites();
                }
                setTimeout(() => ds.pingAllSites(), 500);
              } else {
                Notify.toast('⚠️ Hapus', (delData && delData.message) || 'Gagal menghapus site', 'warn');
              }
            } catch (e) {
              Notify.toast('❌ Error', 'Koneksi ke server gagal: ' + e.message, 'err');
            }
          });
        },

        async pingSite(gw, site) {
          Notify.toast('<i class="fa-solid fa-signal"></i> Pinging', 'Mengecek koneksi ke ' + this._esc(site) + ' (' + this._esc(gw) + ')', 'info', 2000);
          try {
            const ds = (window.Services.Data || DataService);
            const pingData = await ds.loadPingSites();
            const list = Array.isArray(pingData) ? pingData : Object.values(pingData);
            const res = list.find(s => s.gw === gw || s.site_name === site || s.site_id === gw || s.ip === gw) || { status: 'OFFLINE', latency: -1, packet_loss: 100 };
            const ok = res.status === 'ONLINE' || res.status === 'WARNING';
            Notify.toast('<i class="fa-solid fa-signal"></i> Ping Result', this._esc(site) + ': ' + (ok ? res.latency + 'ms — REACHABLE (Loss: ' + (res.packet_loss || 0) + '%)' : 'TIMEOUT'), ok ? 'ok' : 'warn', 3000);
            LogStreamer.add(ok ? 'OK' : 'WARN', 'PING', 'Site ' + site + ' (' + gw + '): ' + (ok ? res.latency + 'ms' : 'TIMEOUT'));
            await ds.pingAllSites(false, pingData);
          } catch (e) {
            Notify.toast('<i class="fa-solid fa-signal"></i> Ping Error', 'Gagal melakukan ping ke ' + this._esc(site), 'err', 3000);
          }
        }
      },

      /* ---- SERVER HEALTH ---- */

});

window.Modules["2_fleet_health"]["monitoring"] = window.Panels;
