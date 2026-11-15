/* a-toast.js
 * Atom: Toast — simple notification bridge to Notify service.
 * Extracted from data.service.js (lines 2433-2442) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Atoms
 * Depends on: Notify (molecule)
 */
(function () {
  'use strict';

  var Toast = window.Toast || {
    show: function(msg, type) {
      if (window.Notify && typeof window.Notify.toast === 'function') {
        var t = type === 'success' ? 'ok' : (type === 'error' ? 'crit' : (type === 'warn' ? 'warn' : 'info'));
        window.Notify.toast('AI Flow Canvas', msg, t, 3500);
      } else {
        console.log('[Toast]', msg);
      }
    }
  };

  window.Toast = Toast;
  window.UI = window.UI || {};
  window.UI.Atoms = window.UI.Atoms || {};
  window.UI.Atoms.Toast = Toast;
})();
