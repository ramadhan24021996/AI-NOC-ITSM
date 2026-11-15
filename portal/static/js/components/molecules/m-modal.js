/* m-modal.js
 * Molecule: Modal — overlay dialog system.
 * Extracted from data.service.js (lines 473-504) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Molecules
 * Depends on: DOM modal-overlay, modal-title, modal-icon, modal-body, modal-footer elements
 */
(function () {
  'use strict';

  var Modal = {
    show: function(title, bodyHTML, buttons, icon) {
      if (!buttons) buttons = [];
      if (!icon) icon = '🔔';
      var _el;
      _el = document.getElementById('modal-title'); if (_el) _el.textContent = title;
      _el = document.getElementById('modal-icon'); if (_el) _el.textContent = icon;
      document.getElementById('modal-body').innerHTML = bodyHTML;
      var footer = document.getElementById('modal-footer');
      footer.innerHTML = '';
      if (buttons.length === 0) {
        buttons = [{ label: 'Tutup', cls: 'btn-ghost', fn: function() { Modal.close(); } }];
      }
      buttons.forEach(function(b) {
        var btn = document.createElement('button');
        btn.className = 'btn ' + (b.cls || 'btn-ghost');
        btn.textContent = b.label;
        if (typeof b.fn === 'function') {
          btn.addEventListener('click', b.fn);
        } else if (typeof b.fn === 'string') {
          btn.setAttribute('onclick', b.fn);
        }
        footer.appendChild(btn);
      });
      document.getElementById('modal-overlay').classList.remove('hidden');
    },
    close: function() { document.getElementById('modal-overlay').classList.add('hidden'); },
    confirm: function(title, msg, onOk) {
      this.show(title, '<p style="font-size:12px;color:var(--txt2)">' + msg + '</p>',
        [{ label: 'Konfirmasi', cls: 'btn-danger', fn: onOk }, { label: 'Batal', cls: 'btn-ghost', fn: function() { Modal.close(); } }]);
    }
  };

  window.Modal = Modal;
  window.UI = window.UI || {};
  window.UI.Molecules = window.UI.Molecules || {};
  window.UI.Molecules.Modal = Modal;
})();
