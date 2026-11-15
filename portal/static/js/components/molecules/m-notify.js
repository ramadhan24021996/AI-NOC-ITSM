/* m-notify.js
 * Molecule: Notify — browser notification & toast system.
 * Extracted from data.service.js (lines 440-471) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Molecules
 * Depends on: Modal (molecule), DOM toast-container element
 */
(function () {
  'use strict';

  var Notify = {
    _supported: ('Notification' in window),
    _sounds: true,
    show: function(title, msg, type, duration) {
      if (type === undefined) type = 'info';
      if (duration === undefined) duration = 5000;
      var types = { crit: { css: 'crit-toast', icon: '🚨', color: 'var(--red)' }, warn: { css: 'warn-toast', icon: '⚠️', color: 'var(--orange)' }, ok: { css: 'ok-toast', icon: '✅', color: 'var(--green)' }, info: { css: 'info-toast', icon: 'ℹ️', color: 'var(--blue)' } };
      var t = types[type] || types.info;
      var id = 'toast-' + Date.now();
      var el = document.createElement('div');
      el.className = 'toast ' + t.css;
      el.id = id;
      el.style.setProperty('--toast-color', t.color);
      el.innerHTML = '<span class="toast-icon">' + t.icon + '</span><div class="toast-content"><div class="toast-title">' + title + '</div><div class="toast-body">' + msg + '</div><div class="toast-progress"><div class="toast-progress-bar" style="width:100%;transition-duration:' + duration + 'ms"></div></div></div><button class="toast-close" onclick="Notify.remove(\'' + id + '\')">×</button>';
      document.getElementById('toast-container').appendChild(el);
      setTimeout(function() { el.querySelector('.toast-progress-bar').style.width = '0%'; }, 50);
      if (duration > 0) setTimeout(function() { Notify.remove(id); }, duration + 300);
      return id;
    },
    remove: function(id) { var el = document.getElementById(id); if (el) { el.classList.add('removing'); setTimeout(function() { el.remove(); }, 250); } },
    toast: function(title, msg, type, duration) { if (type === undefined) type = 'info'; if (duration === undefined) duration = 4000; return this.show(title, msg, type, duration); },
    critical: function(title, msg) {
      this.show(title, msg, 'crit', 0);
      Modal.show(title, '<div style="text-align:center;padding:10px"><div style="font-size:40px;margin-bottom:12px">🚨</div><div style="font-size:14px;font-weight:600;color:var(--txt);margin-bottom:8px">' + title + '</div><div style="font-size:12px;color:var(--txt2)">' + msg + '</div></div>',
        [{ label: 'Acknowledge', cls: 'btn-danger', fn: 'Modal.close()' }]);
      if (this._supported && Notification.permission === 'granted') { new Notification(title, { body: msg, icon: '' }).onclick = function() { }; }
    },
    requestBrowserPermission: function() {
      if (this._supported && Notification.permission === 'default') Notification.requestPermission();
    }
  };

  window.Notify = Notify;
  window.UI = window.UI || {};
  window.UI.Molecules = window.UI.Molecules || {};
  window.UI.Molecules.Notify = Notify;
})();
