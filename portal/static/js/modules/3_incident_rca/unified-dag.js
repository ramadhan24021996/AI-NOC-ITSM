/* modules/3_incident_rca/unified-dag.js
 * Atomic Design — 3. Modules Layer (3_incident_rca / unified-dag)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["3_incident_rca"] = window.Modules["3_incident_rca"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      unified_dag: {
        async load(targetId = null) {
          if (window.UnifiedDAGEngine) UnifiedDAGEngine.init();
          let incidents = (window.Services.Data || DataService)._incidents;
          if (!incidents || incidents.length === 0) {
            incidents = await (window.Services.Data || DataService).loadIncidents();
          }
          incidents = incidents || [];
          const sel = document.getElementById('unified-dag-select');
          if (sel) {
            const currentVal = targetId || sel.value;
            sel.innerHTML = '<option value="">Pilih Insiden...</option>';
            incidents.forEach(i => {
              const opt = document.createElement('option');
              opt.value = i.incident_id || i.id;
              opt.textContent = (i.incident_id || i.id) + ' · ' + (i.device_name || i.agent);
              sel.appendChild(opt);
            });
            if (currentVal) {
              sel.value = currentVal;
            } else {
              sel.value = incidents.length > 0 ? (incidents[0].incident_id || incidents[0].id) : '';
            }
            if (sel.value) {
              UnifiedDAGEngine.loadIncident(sel.value);
            } else {
              const edgesEl = document.getElementById('unified-dag-edges');
              const nodesEl = document.getElementById('unified-dag-nodes');
              const insight = document.getElementById('unified-dag-insight');
              const txt = document.getElementById('unified-dag-insight-txt');
              if (edgesEl) edgesEl.innerHTML = '';
              if (nodesEl) nodesEl.innerHTML = '';
              if (insight) insight.style.display = 'block';
              if (txt) txt.textContent = 'Belum ada insiden yang dapat divisualisasikan pada Unified Graphs.';
            }
          }
        }
      },

});

window.Modules["3_incident_rca"]["unified-dag"] = window.Panels;
