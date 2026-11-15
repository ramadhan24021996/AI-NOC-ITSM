/* core/dom-purify-stub.js
 * DOMPurify stub
 * Extracted from index.html - Phase 2 refactor
 */

window.DOMPurify = window.DOMPurify || { sanitize: function (s) { return s; } };


/* Atomic Design UI Primitives (Atoms Registry) */
window.UI = window.UI || {};
window.UI.Atoms = Object.assign(window.UI.Atoms || {}, {
  DOMPurify: window.DOMPurify,
  Badge({ text, variant = "info", icon = "" }) {
    const map = { critical: "tag-red", high: "tag-orange", warn: "tag-yellow", ok: "tag-green", info: "tag-cyan", purple: "tag-purple" };
    const cls = map[String(variant).toLowerCase()] || "tag-cyan";
    const ic = icon ? `<i class="fa-solid ${icon}" style="margin-right:4px"></i>` : "";
    return `<span class="badge ${cls}" style="font-weight:700">${ic}${text}</span>`;
  },
  Button({ label, onClick = "", variant = "primary", size = "sm", icon = "" }) {
    const ic = icon ? `<i class="fa-solid ${icon}" style="margin-right:4px"></i>` : "";
    return `<button class="btn btn-${variant} btn-${size}" onclick="${onClick}">${ic}${label}</button>`;
  },
  StatusDot({ online = true }) {
    const color = online ? "#22c55e" : "#ef4444";
    return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};box-shadow:0 0 6px ${color}"></span>`;
  }
});
window.UI.Atoms.DOMPurify = window.DOMPurify;
