/* core/theme-init.js
 * Theme + splash screen init
 * Extracted from index.html - Phase 2 refactor
 */

(function () {
      const style = document.createElement('style');
      style.id = 'overlay-dismiss-style';
      const isExplicitLogout = localStorage.getItem('explicit_logout') === '1' || sessionStorage.getItem('explicit_logout') === '1';
      const isAuth = !isExplicitLogout && sessionStorage.getItem('noc_auth') === '1' && sessionStorage.getItem('noc_jwt_token');

      if (isAuth) {
        style.textContent = '#splash-overlay, #login-overlay { display: none !important; }';
        document.head.appendChild(style);
        const savedRole = sessionStorage.getItem('role') || 'viewer';
        if (window.updateRbacUi) window.updateRbacUi(savedRole);
      } else {
        style.textContent = '#splash-overlay { display: none !important; } #login-overlay { opacity: 1 !important; pointer-events: auto !important; display: flex !important; }';
        document.head.appendChild(style);
      }

      window.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
          const splash = document.getElementById('splash-overlay');
          const login = document.getElementById('login-overlay');
          const isExpLogout = localStorage.getItem('explicit_logout') === '1' || sessionStorage.getItem('explicit_logout') === '1';
          if (splash) {
            splash.style.opacity = '0';
            setTimeout(() => {
              splash.style.display = 'none';
              if (login && (isExpLogout || !sessionStorage.getItem('noc_jwt_token'))) {
                const s = document.createElement('style');
                s.innerHTML = '#login-overlay { opacity: 1 !important; pointer-events: auto !important; display: flex !important; transition: opacity 0.5s ease-in-out; }';
                document.head.appendChild(s);
              }
            }, 600);
          }
        }, 1500);
      });
    })();
