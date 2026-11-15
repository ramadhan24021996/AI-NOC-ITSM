/* components/molecules/m-ui-cards.js - Reusable Molecule UI Builders */
window.UI = window.UI || {};
window.UI.Molecules = {
  KPICard({ id, label, value = "—", icon = "fa-chart-line", colorClass = "kpi-bl" }) {
    return `<div class="kpi-card ${colorClass}"><i class="kpi-icon"><i class="fa-solid ${icon}"></i></i><div class="kpi-label">${label}</div><div class="kpi-val" id="${id}">${value}</div></div>`;
  },
  ChatBubble({ sender = "Jarvis", text = "", confidence = "100%", evidence = "OSI AI Engine" }) {
    return `<div class="bubble-jrv">🤖 <strong>${sender}:</strong> "${text}"<div class="jrv-meta"><span class="meta-conf">Confidence: ${confidence}</span><span class="meta-ev">Evidence: ${evidence}</span></div></div>`;
  }
};
