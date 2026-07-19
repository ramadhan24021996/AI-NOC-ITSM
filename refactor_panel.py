import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

panel_js = """
      unified_dag: {
        async load(targetId = null) {
          const incidents = DataService._incidents || [];
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
"""

# Replace `dag: { ... }, decision_dag: { ... }, evidence_dag: { ... }` with `unified_dag: { ... }`
# Find index of `dag: {` inside `Panels = { ... }`
start_idx = content.find('      /* ---- DAG ---- */\n      dag: {')
end_idx = content.find('      pchealth: {')

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + "      /* ---- UNIFIED DAG ---- */\n" + panel_js + content[end_idx:]

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
print("Panels logic updated.")
