/**
 * Atomic Design — Atom Layer: JARVIS Voice Badges, Pills & Status Tokens
 * Path: /static/js/components/atoms/a-jarvis-badges.js
 * Provides: window.UI.Atoms.JarvisBadges
 */
(function (global) {
  const INTENT_COLORS = {
    QUERY: '#38bdf8',
    REMEDIATE: '#f59e0b',
    HITL: '#c084fc',
    REMOTE: '#34d399',
    CHAT: '#fb923c',
    ISSUE: '#f87171'
  };

  const JarvisBadges = {
    renderUrgencyBadge(urgencyLevel) {
      if (urgencyLevel === 'EMERGENCY') {
        return '<span style="background:#ef4444;color:#fff;font-size:8px;padding:1px 5px;border-radius:3px;margin-right:4px;font-weight:700;letter-spacing:1px;">🚨 EMERGENCY</span>';
      }
      if (urgencyLevel === 'HIGH') {
        return '<span style="background:#f59e0b;color:#000;font-size:8px;padding:1px 5px;border-radius:3px;margin-right:4px;font-weight:700;letter-spacing:1px;">⚠️ HIGH</span>';
      }
      return '';
    },

    getIntentStatusStyle(intent, confScore) {
      const safeIntent = intent || 'QUERY';
      return {
        text: `INTENT: ${safeIntent} (${confScore || '98%'})`,
        color: INTENT_COLORS[safeIntent] || '#00F0FF'
      };
    },

    renderTaskAddedBadge(taskContent, taskId) {
      return `
        <div style="margin-top:6px; padding:8px 12px; background:rgba(6,182,212,0.12); border:1px solid #06b6d4; border-radius:6px; display:flex; align-items:center; justify-content:space-between;">
          <span style="font-size:11px; color:#06b6d4; font-weight:bold;">📌 TASK DITAMBAHKAN: "${taskContent}"</span>
          <span style="font-size:9px; color:#94a3b8; font-family:monospace;">${taskId || ''}</span>
        </div>
      `;
    },

    renderMediaLinkButton(actionUrl) {
      if (!actionUrl) return '';
      return `<div style="margin-top:8px;"><a href="${actionUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:6px 14px;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;font-weight:700;font-size:11px;border-radius:4px;text-decoration:none;box-shadow:0 0 10px rgba(239,68,68,0.5);letter-spacing:0.5px;">▶ BUKA TAB MEDIA: ${actionUrl}</a></div>`;
    }
  };

  global.UI = global.UI || {};
  global.UI.Atoms = global.UI.Atoms || {};
  global.UI.Atoms.JarvisBadges = JarvisBadges;
})(window);
