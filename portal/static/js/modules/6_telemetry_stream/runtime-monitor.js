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
            async load() {
              const tbody = document.getElementById('runtime-monitor-tbody');
              if (!tbody) return;
              tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--txt3)">Fetching from runtime...</td></tr>';
              try {
                const resp = await (window.Services.Data || DataService).fetch('/api/system/runtime_monitor');
                if (resp && resp.length > 0) {
                  tbody.innerHTML = resp.map(d => `
                    <tr>
                        <td><strong>${d.engine}</strong></td>
                        <td><span class="tag tag-${d.status === 'ACTIVE' ? 'green' : d.status === 'PARTIAL' ? 'orange' : d.status === 'STANDALONE' ? 'blue' : 'gray'}">${d.status}</span></td>
                        <td>${d.latency}</td>
                        <td>${d.memory}</td>
                        <td>${d.cpu}</td>
                        <td>${d.queue}</td>
                        <td>${d.last_run}</td>
                        <td>${d.caller}</td>
                        <td>${d.subscriber}</td>
                        <td>${d.publish_count}</td>
                        <td>${d.error_count}</td>
                        <td>${d.restart_count}</td>
                    </tr>
                `).join('');
                } else {
                  tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--txt3)">No runtime data available.</td></tr>';
                }
              } catch (e) {
                console.error(e);
                tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--red)">Failed to fetch runtime data.</td></tr>';
              }
            }
          };

window.Modules["6_telemetry_stream"]["runtime-monitor"] = window.Panels;
