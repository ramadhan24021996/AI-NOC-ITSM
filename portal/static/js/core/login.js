/* core/login.js
 * Login flow, clock, logout logic
 * Extracted from index.html - Phase 2 refactor
 */

/* LOGIN SCRIPTS */
    (function () {
      // Clock
      function _tick() { var e = document.getElementById('lk-clock'); if (e) e.textContent = new Date().toLocaleTimeString('id-ID'); }
      _tick(); setInterval(_tick, 1000);

      // Particle canvas
      var cv = document.getElementById('lk-canvas');
      if (!cv) return;
      var cx = cv.getContext('2d'), W, H, nd = [];
      function rsz() { W = cv.width = window.innerWidth; H = cv.height = window.innerHeight; }
      rsz(); window.addEventListener('resize', rsz);
      for (var i = 0; i < 75; i++) nd.push({ x: Math.random() * screen.width, y: Math.random() * screen.height, vx: (Math.random() - .5) * .4, vy: (Math.random() - .5) * .4, r: Math.random() * 2 + 1, c: Math.random() > .7 ? 'rgba(6,182,212,' : 'rgba(59,130,246,' });
      (function draw() {
        cx.clearRect(0, 0, W, H);
        for (var i = 0; i < nd.length; i++) { for (var j = i + 1; j < nd.length; j++) { var dx = nd[i].x - nd[j].x, dy = nd[i].y - nd[j].y, d = Math.sqrt(dx * dx + dy * dy); if (d < 140) { cx.beginPath(); cx.strokeStyle = 'rgba(59,130,246,' + (1 - d / 140) * .16 + ')'; cx.lineWidth = .6; cx.moveTo(nd[i].x, nd[i].y); cx.lineTo(nd[j].x, nd[j].y); cx.stroke(); } } }
        nd.forEach(function (n) { cx.beginPath(); cx.arc(n.x, n.y, n.r, 0, Math.PI * 2); cx.fillStyle = n.c + '.5)'; cx.fill(); n.x += n.vx; n.y += n.vy; if (n.x < 0 || n.x > W) n.vx *= -1; if (n.y < 0 || n.y > H) n.vy *= -1; });
        requestAnimationFrame(draw);
      })();

      // Counter animation
      function animCnt(id, target, dur) { var el = document.getElementById(id); if (!el) return; var s = 0, step = target / ((dur || 1400) / 16); var iv = setInterval(function () { s += step; if (s >= target) { s = target; clearInterval(iv); } el.textContent = Math.floor(s).toLocaleString('id-ID'); }, 16); }
      setTimeout(function () { animCnt('lk-v1', 128750, 1800); animCnt('lk-v2', 2345, 1400); animCnt('lk-v3', 4567, 1600); animCnt('lk-v4', 121838, 1800); }, 300);
    })();

    async function doLoginNOC() {
      var u = document.getElementById('login-user').value.trim();
      var p = document.getElementById('login-pass').value;
      var btn = document.getElementById('lk-btn');
      var btnTx = document.getElementById('lk-btn-tx');
      var err = document.getElementById('lk-err');

      if (btn) btn.disabled = true;
      if (btnTx) btnTx.textContent = 'Memverifikasi...';
      if (err) err.style.display = 'none';

      try {
        const resp = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: u, password: p })
        });

        if (resp.ok) {
          const data = await resp.json();
          localStorage.removeItem('explicit_logout');
          sessionStorage.removeItem('explicit_logout');
          sessionStorage.setItem('noc_auth', '1');
          sessionStorage.setItem('noc_jwt_token', data.token);
          sessionStorage.setItem('role', data.role || 'superadmin');
          sessionStorage.setItem('user_id', data.user_id || u);
          window.currentUserRole = data.role || 'superadmin';
          window.currentUserId = data.user_id || u;
          if (btnTx) btnTx.textContent = '✅ Login Berhasil!';
          let overlayStyle = document.getElementById('overlay-dismiss-style');
          if (!overlayStyle) {
            overlayStyle = document.createElement('style');
            overlayStyle.id = 'overlay-dismiss-style';
            document.head.appendChild(overlayStyle);
          }
          overlayStyle.textContent = '#splash-overlay, #login-overlay { display: none !important; opacity: 0 !important; pointer-events: none !important; visibility: hidden !important; }';

          var ov = document.getElementById('login-overlay');
          if (ov) {
            ov.style.setProperty('display', 'none', 'important');
            ov.style.setProperty('opacity', '0', 'important');
            ov.style.setProperty('pointer-events', 'none', 'important');
          }
          if (btn) btn.disabled = false;
          if (btnTx) btnTx.textContent = 'Sign In ke Dashboard';
          if (window.Notify) Notify.toast('✅ Login', 'Selamat datang ' + u.toUpperCase() + ' — NOC IT AI v3.0', 'ok', 3500);
          if (window.loadUserProfile) loadUserProfile();
          if (window.applyDashboardSettings) applyDashboardSettings();
          if (window.updateRbacUi && window.currentUserRole) updateRbacUi(window.currentUserRole);
          if (window.Nav && window.Nav.go) Nav.go('overview');
        } else {
          if (btn) btn.disabled = false;
          if (btnTx) btnTx.textContent = 'Sign In ke Dashboard';
          if (err) { err.style.display = 'block'; err.textContent = '🔒 Kredensial tidak valid. Silakan periksa username dan password Anda.'; }
          var card = document.getElementById('lk-card');
          if (card) { card.style.transform = 'translateX(-7px)'; setTimeout(function () { card.style.transform = 'translateX(7px)'; }, 80); setTimeout(function () { card.style.transform = 'translateX(-3px)'; }, 160); setTimeout(function () { card.style.transform = 'translateX(0)'; }, 240); }
          var pe = document.getElementById('login-pass');
          if (pe) { pe.value = ''; pe.focus(); pe.style.borderColor = 'rgba(239,68,68,.8)'; setTimeout(function () { pe.style.borderColor = ''; }, 1200); }
        }
      } catch (e) {
        if (btn) btn.disabled = false;
        if (btnTx) btnTx.textContent = 'Sign In ke Dashboard';
        if (err) { err.style.display = 'block'; err.textContent = '⚠️ Gagal terhubung ke server autentikasi.'; }
      }
    }

    async function doLogout() {
      try {
        const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token');
        if (token) {
          await fetch('/api/auth/logout', { 
            method: 'POST',
            headers: { 
              'Authorization': 'Bearer ' + token,
              'Content-Type': 'application/json'
            }
          }).catch(() => {});
        }
      } catch(e) {
        console.error('Logout request failed', e);
      }
      localStorage.setItem('explicit_logout', '1');
      sessionStorage.setItem('explicit_logout', '1');
      sessionStorage.removeItem('noc_jwt_token');
      sessionStorage.removeItem('noc_auth');
      sessionStorage.removeItem('role');
      sessionStorage.removeItem('user_id');
      localStorage.removeItem('noc_jwt_token');
      localStorage.removeItem('noc_auth');
      window.currentUserRole = null;
      window.currentUserId = null;
      
      const overlayStyle = document.getElementById('overlay-dismiss-style');
      if (overlayStyle) {
        overlayStyle.textContent = '#splash-overlay { display: none !important; } #login-overlay { opacity: 1 !important; pointer-events: auto !important; display: flex !important; }';
      }
      const loginOverlay = document.getElementById('login-overlay');
      if (loginOverlay) {
        loginOverlay.style.display = 'flex';
        loginOverlay.style.opacity = '1';
        loginOverlay.style.pointerEvents = 'auto';
      }
      window.location.reload();
    }
