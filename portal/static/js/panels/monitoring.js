/* panels/monitoring.js
 * Monitoring live panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      monitoring: {
        async load() {
          const metrics = await DataService.loadHostMetrics();
          this._updateMetrics(metrics);
          this._renderSites();
          if (!window.ActiveIntervals.monitoring) {
            window.ActiveIntervals.monitoring = setInterval(() => {
              this._updateMetrics();
            }, 5000);
          }
          this._initLatencyChart(metrics.history);
        },
        async _updateMetrics(metrics = null) {
          if (!metrics) {
            metrics = await DataService.loadHostMetrics();
          }
          const cpu = Math.round(metrics.cpu || 0);
          const ram = Math.round(metrics.ram || 0);
          const disk = Math.round(metrics.disk || 0);

          const pingData = await DataService.loadPingSites();
          const pings = Array.isArray(pingData) ? pingData : Object.values(pingData);

          const activeTargets = pings.filter(t => t.status === 'ONLINE' || t.status === 'WARNING');
          const avgLat = activeTargets.length > 0 ? Math.round(activeTargets.reduce((sum, t) => sum + (t.latency > 0 ? t.latency : 0), 0) / activeTargets.length) : 0;

          const totalLoss = pings.reduce((sum, t) => sum + (t.packet_loss !== undefined ? parseFloat(t.packet_loss) : (t.status === 'OFFLINE' ? 100 : 0)), 0);
          const pktLoss = pings.length > 0 ? (totalLoss / pings.length).toFixed(1) : "0.0";

          const sysHealth = await DataService.fetch('/api/system/health').catch(() => ({ duration_ms: 15 }));
          const apiRespTime = (sysHealth && sysHealth.duration_ms) ? sysHealth.duration_ms : 15;

          setEl('mon-latency', avgLat + 'ms'); setEl('mon-pktloss', pktLoss + '%'); setEl('mon-resptime', apiRespTime + 'ms'); setEl('mon-cpu', cpu + '%');
          setEl('mon-cpu-pct', cpu + '%'); setEl('mon-ram-pct', ram + '%'); setEl('mon-disk-pct', disk + '%'); setEl('mon-pl-pct', pktLoss + '%');

          const cpuBar = document.getElementById('mon-cpu-bar');
          const ramBar = document.getElementById('mon-ram-bar');
          const diskBar = document.getElementById('mon-disk-bar');
          const plBar = document.getElementById('mon-pl-bar');

          if (cpuBar) {
            cpuBar.style.width = cpu + '%';
            cpuBar.style.background = cpu > 90 ? 'var(--red)' : cpu > 75 ? 'var(--orange)' : 'var(--blue)';
          }
          if (ramBar) {
            ramBar.style.width = ram + '%';
            ramBar.style.background = ram > 90 ? 'var(--red)' : ram > 80 ? 'var(--orange)' : 'var(--purple)';
          }
          if (diskBar) {
            diskBar.style.width = disk + '%';
            diskBar.style.background = disk > 90 ? 'var(--red)' : disk > 80 ? 'var(--orange)' : 'var(--cyan)';
          }
          if (plBar) {
            const lossVal = Math.min(100, Math.max(0, parseFloat(pktLoss)));
            plBar.style.width = lossVal + '%';
            plBar.style.background = lossVal > 15 ? 'var(--red)' : lossVal > 5 ? 'var(--orange)' : 'var(--green)';
          }

          const t = new Date().toTimeString().slice(0, 8);
          Charts.addPoint('chart-latency', t, [avgLat, apiRespTime]);
        },
        _initLatencyChart(history) {
          const labels = (history && history.labels) || Array.from({ length: 15 }, (_, i) => { const d = new Date(Date.now() - (14 - i) * 5000); return d.toTimeString().slice(0, 8); });
          const latData = (history && history.latency) || Array.from({ length: 15 }, () => 35);
          const respData = (history && history.response) || Array.from({ length: 15 }, () => 15);

          Charts.create('chart-latency', 'line', labels, [
            { label: 'Latency (ms)', data: latData, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.1)', tension: .4, fill: true },
            { label: 'Response (ms)', data: respData, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,.05)', tension: .4, fill: false }
          ], { legend: true });
        },
        async _renderSites() {
          await DataService.pingAllSites();
        },
        async deleteSite(gw, siteName) {
          Modal.confirm('🗑️ Hapus Site', 'Apakah Anda yakin ingin menghapus site <b>' + siteName + '</b> secara permanen?', async () => {
            Modal.close();
            try {
              const resp = await fetch('/api/fleet/admin/sites');
              const data = await resp.json();
              const target = data.sites.find(s => s.router_ip === gw && s.site_name === siteName);

              if (!target) {
                Notify.toast('❌ Hapus', 'Site tidak ditemukan di database.', 'err');
                return;
              }

              const delResp = await fetch('/api/fleet/admin/sites/delete/' + target.site_id, { method: 'POST' });
              const delData = await delResp.json();
              if (delData.status === 'success') {
                Notify.toast('✅ Hapus', 'Site ' + siteName + ' berhasil dihapus', 'ok');
                LogStreamer.add('OK', 'CONFIG', 'Site deleted: ' + siteName);
                RemoteSettings.loadSites();
                setTimeout(() => DataService.pingAllSites(), 1000);
              } else {
                Notify.toast('⚠️ Hapus', delData.message || 'Gagal menghapus site', 'warn');
              }
            } catch (e) {
              Notify.toast('❌ Error', 'Koneksi ke server gagal', 'err');
            }
          });
        },
        async pingSite(gw, site) {
          Notify.toast('<i class="fa-solid fa-signal"></i> Pinging', 'Mengecek koneksi ke ' + site + ' (' + gw + ')', 'info', 2000);
          try {
            const pingData = await DataService.loadPingSites();
            const list = Array.isArray(pingData) ? pingData : Object.values(pingData);
            const res = list.find(s => s.gw === gw || s.site_name === site || s.site_id === gw || s.ip === gw) || { status: 'OFFLINE', latency: -1, packet_loss: 100 };
            const ok = res.status === 'ONLINE' || res.status === 'WARNING';
            Notify.toast('<i class="fa-solid fa-signal"></i> Ping Result', site + ': ' + (ok ? res.latency + 'ms — REACHABLE (Loss: ' + (res.packet_loss || 0) + '%)' : 'TIMEOUT'), ok ? 'ok' : 'warn', 3000);
            LogStreamer.add(ok ? 'OK' : 'WARN', 'PING', 'Site ' + site + ' (' + gw + '): ' + (ok ? res.latency + 'ms' : 'TIMEOUT'));
            DataService.pingAllSites();
          } catch (e) {
            Notify.toast('<i class="fa-solid fa-signal"></i> Ping Error', 'Gagal melakukan ping ke ' + site, 'err', 3000);
          }
        }
      },

      /* ---- SERVER HEALTH ---- */

});
