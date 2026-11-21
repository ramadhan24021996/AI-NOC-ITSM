/* modules/6_telemetry_stream/runtime-monitor.js
 * Atomic Design — 3. Modules Layer (6_telemetry_stream / runtime-monitor)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["6_telemetry_stream"] = window.Modules["6_telemetry_stream"] || {};

if (!window.Panels) window.Panels = {};
          Panels.runtime_monitor = {
            _hasLoaded: false,
            _timer: null,
            async load(silent = false) {
              const tbody = document.getElementById('runtime-monitor-tbody');
              if (!tbody) return;
              if (!silent && !this._hasLoaded) {
                tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--txt3)">Fetching from runtime...</td></tr>';
              }
              try {
                const resp = await (window.Services.Data || DataService).fetch('/api/system/runtime_monitor');
                if (resp && resp.length > 0) {
                  this._hasLoaded = true;
                  tbody.innerHTML = resp.map(d => `
                    <tr>
                        <td><strong>${_esc(d.engine)}</strong></td>
                        <td><span class="tag tag-${d.status === 'ACTIVE' ? 'green' : (d.status === 'PARTIAL' || d.status === 'STALE') ? 'orange' : d.status === 'STANDALONE' ? 'blue' : (d.status === 'OFFLINE' || d.status === 'UNAVAILABLE' || d.status === 'DISCONNECTED') ? 'red' : 'gray'}">${_esc(d.status)}</span></td>
                        <td>${_esc(d.latency)}</td>
                        <td>${_esc(d.memory)}</td>
                        <td>${_esc(d.cpu)}</td>
                        <td>${_esc(d.queue)}</td>
                        <td>${_esc(d.last_run)}</td>
                        <td>${_esc(d.caller)}</td>
                        <td>${_esc(d.subscriber)}</td>
                        <td>${_esc(d.publish_count)}</td>
                        <td>${_esc(d.error_count)}</td>
                        <td>${_esc(d.restart_count)}</td>
                    </tr>
                `).join('');
                } else if (!this._hasLoaded) {
                  tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--txt3)">No runtime data available.</td></tr>';
                }
              } catch (e) {
                console.error(e);
                if (!this._hasLoaded) {
                  tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--red)">Failed to fetch runtime data.</td></tr>';
                }
              }
              this.startAutoRefresh();
            },
            startAutoRefresh() {
              window.ActiveIntervals = window.ActiveIntervals || {};
              if (window.ActiveIntervals.runtime_monitor) return;
              window.ActiveIntervals.runtime_monitor = setInterval(() => {
                const panel = document.getElementById('p-runtime_monitor');
                if (document.hidden || !panel || !panel.classList.contains('active')) return;
                this.load(true);
              }, 10000);
            },
            stopAutoRefresh() {
              if (window.ActiveIntervals && window.ActiveIntervals.runtime_monitor) {
                clearInterval(window.ActiveIntervals.runtime_monitor);
                delete window.ActiveIntervals.runtime_monitor;
              }
            }
          };

window.Modules["6_telemetry_stream"]["runtime-monitor"] = window.Panels;
