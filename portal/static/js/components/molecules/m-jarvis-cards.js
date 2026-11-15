/**
 * Atomic Design — Molecule Layer: JARVIS Conversation Bubbles, HITL Banners & Task Cards
 * Path: /static/js/components/molecules/m-jarvis-cards.js
 * Provides: window.UI.Molecules.JarvisCards
 */
(function (global) {
  const JarvisCards = {
    createUserBubble(cleanQuery) {
      const userBubble = document.createElement('div');
      userBubble.className = 'bubble-usr';
      userBubble.innerHTML = `🎤 <strong>User:</strong> "${cleanQuery}"`;
      return userBubble;
    },

    createJarvisBubble(opts) {
      const {
        replyText = '',
        urgencyLevel = 'NORMAL',
        actionCardHtml = '',
        actionUrl = '',
        confScore = '98%',
        evidenceStr = 'OSI Ensemble Consensus & Knowledge Base'
      } = opts || {};

      const jarvisBubble = document.createElement('div');
      jarvisBubble.className = 'bubble-jrv';

      const badges = (global.UI && global.UI.Atoms && global.UI.Atoms.JarvisBadges) || null;
      const urgencyBadge = badges ? badges.renderUrgencyBadge(urgencyLevel) : '';

      if (urgencyLevel === 'EMERGENCY') {
        jarvisBubble.style.borderLeft = '3px solid #ef4444';
        jarvisBubble.style.boxShadow = '0 0 8px rgba(239,68,68,0.4)';
      } else if (urgencyLevel === 'HIGH') {
        jarvisBubble.style.borderLeft = '3px solid #f59e0b';
      }

      const finalCardHtml = actionCardHtml || (badges && actionUrl ? badges.renderMediaLinkButton(actionUrl) : '');
      jarvisBubble.innerHTML = `${urgencyBadge}🤖 <strong>Jarvis:</strong> "${replyText}"${finalCardHtml}<div class="jrv-meta"><span class="meta-conf">Confidence: ${confScore}</span><span class="meta-ev">Evidence: ${evidenceStr}</span></div>`;
      return jarvisBubble;
    },

    createProactiveBubble(data) {
      const jrvBubble = document.createElement('div');
      jrvBubble.className = 'bubble-jrv';
      jrvBubble.innerHTML = `📢 <strong>Jarvis (Proaktif):</strong> "${data.text}"<div class="jrv-meta"><span class="meta-conf">Severity: ${data.severity || 'INFO'}</span><span class="meta-ev">Device: ${data.device || 'System'}</span></div>`;
      return jrvBubble;
    },

    createHitlBanner(hitlQueueId) {
      const hitlBanner = document.createElement('div');
      hitlBanner.style.cssText = 'margin-top:6px;padding:8px 12px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:6px;font-size:10px;color:#fbbf24;font-weight:bold;';
      hitlBanner.innerHTML = `⚠️ MENUNGGU PERSETUJUAN HITL — Queue: ${hitlQueueId || 'PENDING'} | Konfirmasi wajib melalui tombol HITL di panel Approval Queue Dashboard NOC (Kebijakan K-07)`;
      return hitlBanner;
    },

    renderTaskItem(t) {
      const isDone = t.status === 'COMPLETED';
      return `
        <div style="display:flex; align-items:center; justify-content:space-between; padding:5px 8px; background:rgba(3,10,20,0.8); border:1px solid ${isDone ? '#059669' : 'rgba(0,240,255,0.25)'}; border-radius:6px; font-size:10px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <input type="checkbox" ${isDone ? 'checked' : ''} onchange="JarvisTaskManager.toggle('${t.id}')" style="cursor:pointer; accent-color:#00F0FF;">
            <span style="color:${isDone ? '#64748b' : '#e2e8f0'}; text-decoration:${isDone ? 'line-through' : 'none'}; font-weight:${isDone ? 'normal' : '600'};">${t.text}</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="color:#64748b; font-size:9px; font-family:monospace;">${t.time}</span>
            <button onclick="JarvisTaskManager.deleteTask('${t.id}')" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:11px;">✕</button>
          </div>
        </div>
      `;
    }
  };

  global.UI = global.UI || {};
  global.UI.Molecules = global.UI.Molecules || {};
  global.UI.Molecules.JarvisCards = JarvisCards;
})(window);
