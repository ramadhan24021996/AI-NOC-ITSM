/**
 * Atomic Design — Organism: PortalChat
 * Path: /static/js/components/organisms/o-portal-chat.js
 * Used by: /portal (templates/portal.html) — end-user self-service AI chat.
 * Backend: POST /api/ai_command (portal/dashboard/api/chat_handlers.go)
 *
 * Rule #6: verifyAndSolve() only REQUESTS verification from the backend.
 * It never marks an incident resolved client-side; resolution is decided by
 * the Verification Engine using execution + post-remediation evidence.
 */
(function (global) {
  'use strict';

  const PortalChat = {
    history: [],

    escapeHTML(str) {
      return String(str).replace(/[&<>'"]/g, (tag) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag));
    },

    appendMessage(role, text) {
      const area = document.getElementById('chat-area');
      if (!area) return;
      const div = document.createElement('div');
      div.className = `bubble ${role}-bubble`;

      // Escape HTML first to prevent XSS, then apply safe formatting.
      const safeText = this.escapeHTML(text);
      let formattedText = safeText.replace(/\n/g, '<br>');
      formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

      // Auto-format for Advanced AI-NOC fields if they exist in text
      if (text.includes('IMPACT ANALYSIS:') || text.includes('EVIDENCE:') || text.includes('Historical Match:')) {
        formattedText = formattedText.replace(/IMPACT ANALYSIS:/g, '<br><div style="background:rgba(239, 68, 68, 0.1); padding:8px; border-radius:8px; border-left:4px solid var(--red); margin:10px 0;"><strong>🔥 IMPACT ANALYSIS:</strong>');
        formattedText = formattedText.replace(/EVIDENCE:/g, '</div><div style="background:rgba(16, 185, 129, 0.1); padding:8px; border-radius:8px; border-left:4px solid var(--green); margin:10px 0;"><strong>🔍 EVIDENCE GATHERED:</strong>');
        formattedText = formattedText.replace(/Historical Match:/g, '</div><div style="background:rgba(139, 92, 246, 0.1); padding:8px; border-radius:8px; border-left:4px solid var(--accent-primary); margin:10px 0;"><strong>📚 KNOWN INCIDENT MATCH:</strong>');
        formattedText += '</div>';
      }

      div.innerHTML = formattedText;
      area.appendChild(div);
      area.scrollTop = area.scrollHeight;
    },

    _setTyping(visible) {
      const typing = document.getElementById('typing');
      if (typing) typing.style.display = visible ? 'block' : 'none';
    },

    async _postCommand(command, failMessage, offlineMessage) {
      this._setTyping(true);
      try {
        const res = await fetch('/api/ai_command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: command, history: this.history })
        });
        const data = await res.json();
        this._setTyping(false);
        if (data.success) {
          this.appendMessage('ai', data.response);
          this.history.push({ role: 'assistant', content: data.response });
        } else {
          this.appendMessage('ai', failMessage);
        }
      } catch (err) {
        this._setTyping(false);
        this.appendMessage('ai', offlineMessage);
      }
    },

    async sendMessage() {
      const input = document.getElementById('user-input');
      if (!input) return;
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      this.appendMessage('user', text);
      this.history.push({ role: 'user', content: text });

      await this._postCommand(
        text,
        'Maaf, terjadi kendala saat menghubungi AI Guru. Saya akan meneruskan laporan Anda ke teknisi.',
        'Koneksi terputus. Mohon coba beberapa saat lagi.'
      );
    },

    async verifyAndSolve(incidentId) {
      this.appendMessage('user', 'Memverifikasi perbaikan...');
      await this._postCommand(
        'Tolong verifikasi perbaikan untuk insiden ' + incidentId,
        'Verifikasi gagal menghubungi sistem.',
        'Koneksi terputus saat memverifikasi.'
      );
    }
  };

  global.UI = global.UI || {};
  global.UI.Organisms = global.UI.Organisms || {};
  global.UI.Organisms.PortalChat = PortalChat;

  // Inline handlers in portal.html call these global names.
  global.sendMessage = () => PortalChat.sendMessage();
  global.verifyAndSolve = (incidentId) => PortalChat.verifyAndSolve(incidentId);
  global.appendMessage = (role, text) => PortalChat.appendMessage(role, text);
})(window);
