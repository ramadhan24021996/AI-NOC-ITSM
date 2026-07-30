import re

with open('portal/templates/index.html', 'r') as f:
    content = f.read()

# 1. Update Sidebar menu
content = re.sub(
    r'<div class="nav-item" data-panel="dag".*?</div>',
    r'<div class="nav-item" data-panel="unified_dag" onclick="Nav.go(\'unified_dag\',this)"><span class="ni"><i class="fa-solid fa-diagram-project"></i></span><span class="lbl">Unified Graphs</span></div>',
    content, count=1, flags=re.DOTALL
)
content = re.sub(
    r'<div class="nav-item" data-panel="decision_dag".*?</div>\s*',
    '',
    content, count=1, flags=re.DOTALL
)
content = re.sub(
    r'<div class="nav-item" data-panel="evidence_dag".*?</div>\s*',
    '',
    content, count=1, flags=re.DOTALL
)

# 2. Update panel lists
content = content.replace("'dag', 'decision_dag', 'evidence_dag',", "'unified_dag',")
content = content.replace("dag: '<i class=\"fa-solid fa-diagram-project\" style=\"color:var(--blue);margin-right:8px\"></i> Causal DAG',\n          decision_dag: '<i class=\"fa-solid fa-route\" style=\"color:var(--pink);margin-right:8px\"></i> Decision Graph',\n          evidence_dag: '<i class=\"fa-solid fa-diagram-next\" style=\"color:var(--green);margin-right:8px\"></i> Evidence DAG',", "unified_dag: '<i class=\"fa-solid fa-diagram-project\" style=\"color:var(--purple);margin-right:8px\"></i> Unified Graphs',")
content = content.replace("dag: 'AI Root Cause · Causal DAG Analysis',\n          decision_dag: 'AI Decision Path · Policy Graph',\n          evidence_dag: 'Evidence Chain · Validation Graph',", "unified_dag: 'Unified Graph Workspace',")

# 3. Replace the three panels with one unified panel
panel_html = """
        <!-- ============================================================
     PANEL: UNIFIED DAG
============================================================ -->
        <div id="p-unified_dag" class="panel">
          <div class="card mb-12">
            <div class="dag-toolbar">
              <select class="inp" style="width:220px" id="unified-dag-select" onchange="UnifiedDAGEngine.loadIncident(this.value)">
                <option value="">Pilih Insiden...</option>
              </select>
              <button class="btn btn-ghost btn-sm" onclick="UnifiedDAGEngine.zoomIn()">🔍+</button>
              <button class="btn btn-ghost btn-sm" onclick="UnifiedDAGEngine.zoomOut()">🔍-</button>
              <button class="btn btn-ghost btn-sm" onclick="UnifiedDAGEngine.resetView()"><i class="fa-solid fa-arrow-rotate-left" style="margin-right:6px"></i>Reset</button>
              <button class="btn btn-ghost btn-sm" onclick="UnifiedDAGEngine.expandAll()"><i class="fa-solid fa-expand" style="margin-right:6px"></i>Expand</button>
              <button class="btn btn-ghost btn-sm" onclick="UnifiedDAGEngine.collapseAll()"><i class="fa-solid fa-compress" style="margin-right:6px"></i>Collapse</button>
              <div class="tbl-search" style="width:160px"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg><input placeholder="Cari node..." oninput="UnifiedDAGEngine.searchNode(this.value)"></div>
              <button class="btn btn-primary btn-sm" onclick="UnifiedDAGEngine.exportSVG()"><i class="fa-solid fa-download" style="margin-right:6px"></i>SVG</button>
            </div>
            
            <div style="display:flex; border-bottom:1px solid var(--bd); background:var(--bg2);">
               <div class="tab-btn active" id="tab-causal" onclick="UnifiedDAGEngine.switchTab('causal')" style="padding:10px 20px; cursor:pointer; font-weight:bold; color:var(--blue); border-bottom:2px solid var(--blue);">Causal DAG</div>
               <div class="tab-btn" id="tab-decision" onclick="UnifiedDAGEngine.switchTab('decision')" style="padding:10px 20px; cursor:pointer; color:var(--txt2);">Decision Graph</div>
               <div class="tab-btn" id="tab-evidence" onclick="UnifiedDAGEngine.switchTab('evidence')" style="padding:10px 20px; cursor:pointer; color:var(--txt2);">Evidence DAG</div>
            </div>

            <div class="dag-svg-wrap" id="unified-dag-svg-wrap" style="position:relative;">
              <svg id="unified-dag-svg" class="dag-svg" viewBox="0 0 800 320" style="background:var(--bg1)">
                <defs>
                  <!-- Arrowheads -->
                  <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#3b82f6" stroke-width="1.5" /></marker>
                  <marker id="arrowhead-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#ef4444" stroke-width="1.5" /></marker>
                  <marker id="arrowhead-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#10b981" stroke-width="1.5" /></marker>
                  <marker id="arrowhead-cyan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#0d9488" stroke-width="1.5" /></marker>
                  <marker id="decision-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#ec4899" stroke-width="1.5" /></marker>
                  <marker id="evidence-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M2 1L8 5L2 9" fill="none" stroke="#22c55e" stroke-width="1.5" /></marker>
                  
                  <filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur" /><feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                  <filter id="decision-glow"><feGaussianBlur stdDeviation="3" result="coloredBlur" /><feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                  <filter id="evidence-glow"><feGaussianBlur stdDeviation="3" result="coloredBlur" /><feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                </defs>
                <g id="unified-dag-viewport">
                  <g id="unified-dag-edges"></g>
                  <g id="unified-dag-nodes"></g>
                </g>
              </svg>
            </div>
          </div>
          <div class="insight-box" id="unified-dag-insight" style="display:none"><b>🧠 AI Insight:</b> <span id="unified-dag-insight-txt"></span></div>
        </div>
"""

# We need to replace the old panels.
old_panels_regex = r'<!-- ============================================================\s*PANEL: CAUSAL DAG\s*============================================================ -->.*?</div>\s*</div>\s*</div>\s*</div>' # this regex is tricky because of nested divs
# Instead of regex, let's find the indices
start_idx = content.find('<!-- ============================================================\n     PANEL: CAUSAL DAG')
end_idx = content.find('<!-- ============================================================\n     PANEL: STORAGE')
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + panel_html + content[end_idx:]

with open('portal/templates/index.html', 'w') as f:
    f.write(content)
print("Structural replacements done.")
