/* modules/3_incident_rca/incident.js
 * Atomic Design — 3. Modules Layer (3_incident_rca / incident)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["3_incident_rca"] = window.Modules["3_incident_rca"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      incident: {
        _busBound: false,
        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          const onChange = () => {
            const p = document.getElementById('p-incident');
            if (p && p.classList.contains('active')) this.load();
          };
          bus.on('incident:status_changed', onChange);
          bus.on('incident:verified', onChange);
        },
        async load() {
          this._bindBus();
          try {
            const data = await (window.Services.Data || DataService).loadIncidents();
            this._renderTable(data);
          } catch(e) {
            console.error("Failed to load incidents:", e);
          }
          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.incident_triage) {
            window.ActiveIntervals.incident_triage = setInterval(() => {
              const p = document.getElementById('p-incident');
              if (document.hidden || !p || !p.classList.contains('active')) return;
              this.load();
            }, 10000);
          }
        },
        _renderTable(incidents) {
          const tbody = document.getElementById('tbody-incident');
          if (!tbody) return;
          if (!incidents || !Array.isArray(incidents) || incidents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;color:var(--txt3)">✓ No active incidents in queue.</td></tr>';
            setEl('tri-count-txt', '0 insiden');
            return;
          }

          setEl('tri-count-txt', `${incidents.length} insiden ditemukan`);
          setEl('tri-active', incidents.filter(i => i.status !== 'RESOLVED').length);

          tbody.innerHTML = incidents.map(inc => {
            const id = inc.incident_id || inc.id;
            const traceId = inc.trace_id || (inc.correlation_id ? inc.correlation_id.substring(0,8) : 'N/A');
            const pc = inc.pc_name || inc.device_name || 'System';
            const site = inc.site_id || 'Global';
            const layer = inc.layer || 'L3 (Network)';
            const flag = inc.flag || (inc.severity ? inc.severity + '_ALERT' : 'ALERT');
            const sev = (inc.severity || 'HIGH').toUpperCase();
            const conf = inc.confidence ? (inc.confidence * 100).toFixed(0) + '%' : '92%';
            const time = new Date(inc.created_at || Date.now()).toLocaleString();
            const sevClass = sev === 'CRITICAL' || sev === 'HIGH' ? 'tag-red' : 'tag-orange';

            return `
              <tr>
                <td><b>#${_esc(id)}</b></td>
                <td><code style="font-size:10px;color:var(--cyan)">${_esc(traceId)}</code></td>
                <td><b style="color:var(--blue2)">${_esc(pc)}</b></td>
                <td><span class="tag tag-gray">${_esc(site)}</span></td>
                <td><span class="tag tag-purple">${_esc(layer)}</span></td>
                <td><code style="color:var(--orange2)">${_esc(flag)}</code></td>
                <td><span class="tag ${sevClass}">${_esc(sev)}</span></td>
                <td><b>${_esc(conf)}</b></td>
                <td><small style="color:var(--txt2)">${_esc(time)}</small></td>
              </tr>
            `;
          }).join('');
        }
      },

      /* ---- FLEET CONFIG MANAGER ---- */

});

window.Modules["3_incident_rca"]["incident"] = window.Panels;
