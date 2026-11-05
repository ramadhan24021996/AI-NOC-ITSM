/* panels/incident.js
 * Incident Triage panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      incident: {
        async load() {
          try {
            const data = await DataService.loadIncidents();
            this._renderTable(data);
          } catch(e) {
            console.error("Failed to load incidents:", e);
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
                <td><b>#${id}</b></td>
                <td><code style="font-size:10px;color:var(--cyan)">${traceId}</code></td>
                <td><b style="color:var(--blue2)">${pc}</b></td>
                <td><span class="tag tag-gray">${site}</span></td>
                <td><span class="tag tag-purple">${layer}</span></td>
                <td><code style="color:var(--orange2)">${flag}</code></td>
                <td><span class="tag ${sevClass}">${sev}</span></td>
                <td><b>${conf}</b></td>
                <td><small style="color:var(--txt2)">${time}</small></td>
              </tr>
            `;
          }).join('');
        }
      },

      /* ---- FLEET CONFIG MANAGER ---- */

});
