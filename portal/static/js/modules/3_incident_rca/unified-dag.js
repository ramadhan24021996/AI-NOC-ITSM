/* panels/unified-dag.js
 * Unified DAG topology panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      unified_dag: {
        async load(targetId = null) {
          if (window.UnifiedDAGEngine) UnifiedDAGEngine.init();
          let incidents = DataService._incidents;
          if (!incidents || incidents.length === 0) {
            incidents = await DataService.loadIncidents();
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
            UnifiedDAGEngine.loadIncident(sel.value || 'latest');
          }
        }
      },

});
