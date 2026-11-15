/* init.js
 * Module: Dashboard initialization — DOMContentLoaded, applyDashboardSettings, loadUserProfile, RBAC.
 * Extracted from data.service.js (lines 6402-6518, 7194-7238) — Phase 5.4 Atomic Design refactor.
 *
 * Layer: Modules > 1_overview
 * Depends on: SidebarManager, RemoteSettings, WSService, DashboardCustomizer, DataService, Nav
 */
(function () {
  'use strict';

// Check Launcher status on model panel load
document.addEventListener('DOMContentLoaded', async () => {
  SidebarManager.init();
  RemoteSettings.load();
  await loadUserProfile();
  await DashboardCustomizer.init();
  
  // Auto-connect native WebSocket for live logs
  WSService.connect();
});

async function applyDashboardSettings() {
  try {
    const res = await fetch('/api/auth/dashboard_settings');
    if (res.ok) {
      const data = await res.json();
      if (data && data.dashboard_settings) {
        let settings = {};
        try {
          settings = JSON.parse(data.dashboard_settings);
        } catch (e) { settings = {}; }

        // Apply theme/appearance
        if (settings.theme === 'light') {
          document.body.classList.add('light-mode');
        } else {
          document.body.classList.remove('light-mode');
        }

        window.currentUserSettings = data.dashboard_settings;

        // Delegate sidebar visibility filtering to updateRbacUi
        if (window.updateRbacUi && window.currentUserRole) {
          window.updateRbacUi(window.currentUserRole);
        }

        // Go to default landing panel if specified and we are on initial load
        let landingPanel = settings.landing_panel;
        if (!landingPanel) {
          const path = window.location.pathname;
          if (path.includes('/dashboard/monitoring')) {
            landingPanel = 'monitoring';
          } else if (path.includes('/dashboard/viewer')) {
            landingPanel = 'overview';
          } else if (path.includes('/dashboard/operator')) {
            landingPanel = 'overview';
          } else if (path.includes('/dashboard/admin')) {
            landingPanel = 'overview';
          } else if (path.includes('/dashboard/executive')) {
            landingPanel = 'overview';
          } else {
            const roleDefaults = {
              'superadmin': 'overview',
              'admin': 'overview',
              'noc_engineering': 'monitoring',
              'operator': 'overview',
              'viewer': 'overview'
            };
            landingPanel = roleDefaults[window.currentUserRole] || 'overview';
          }
        }
        if (landingPanel && !window.hasLanded) {
          window.hasLanded = true;
          const navEl = document.querySelector(`[data-panel="${landingPanel}"]`);
          Nav.go(landingPanel, navEl);
        }
      }
    }
  } catch (e) {
    console.error("Failed to load dashboard settings:", e);
  }
}

async function loadUserProfile() {
  try {
    const resp = await DataService.fetch('/api/auth/verify');
    if (resp && resp.valid) {
      const user = resp.user_id || 'superadmin';
      const role = resp.role || 'superadmin';

      const userTxt = document.getElementById('username-txt');
      if (userTxt) userTxt.textContent = user.charAt(0).toUpperCase() + user.slice(1);

      const roleTxt = document.getElementById('role-txt');
      if (roleTxt) roleTxt.textContent = role.toUpperCase();

      const avatarChar = document.getElementById('avatar-char');
      if (avatarChar) avatarChar.textContent = user.charAt(0).toUpperCase();

      window.currentUserRole = role;
      window.currentUserId = user;

      if (window.updateRbacUi) {
        window.updateRbacUi(role);
      }

      if (role === 'viewer') {
        document.body.classList.add('role-viewer');
      } else {
        document.body.classList.remove('role-viewer');
      }

      // Load and apply dashboard settings as well
      applyDashboardSettings();

      if (window.DashboardCustomizer && typeof DashboardCustomizer.init === 'function') {
        DashboardCustomizer.init();
      }

      if (window.RemoteSettings && typeof RemoteSettings.startStatusMonitoring === 'function') {
        RemoteSettings.startStatusMonitoring();
      }
    }
  } catch (e) {
    console.error('Gagal memuat profil pengguna:', e);
  }
}

/* ==================================================
   NAVIGATION & RBAC
================================================== */
const defaultAllowedPanels = {
  'superadmin': ['all'],
  'admin': ['all'],
  'noc_engineering': ['all'],
  'operator': ['all'],
  'viewer': ['all']
};

window.updateRbacUi = function(role) {
  const r = (role || window.currentUserRole || 'superadmin').toLowerCase();
  window.currentUserRole = r;
  const roleTxt = document.getElementById('role-txt');
  if (roleTxt) roleTxt.textContent = r.toUpperCase();
  let allowed = ['all'];
  if (window.currentUserSettings && r !== 'superadmin') {
    try {
      const settings = typeof window.currentUserSettings === 'string' ? JSON.parse(window.currentUserSettings) : window.currentUserSettings;
      if (settings.visible_panels && Array.isArray(settings.visible_panels) && settings.visible_panels.length > 0) {
        allowed = settings.visible_panels;
      }
    } catch(e) {}
  }
  const hasAll = allowed.includes('all');
  
  // Update sidebar nav items
  document.querySelectorAll('.sidebar .nav-item').forEach(item => {
    const panelId = item.getAttribute('data-panel');
    if (!panelId) return;
    const isOverviewAlias = (panelId === 'overview' && (allowed.includes('overview') || allowed.includes('dashboard')));
    if (hasAll || allowed.includes(panelId) || isOverviewAlias) {
      item.style.display = 'flex';
    } else {
      item.style.display = 'none';
    }
  });
  
  // Update sidebar groups visibility - force all groups visible and open
  document.querySelectorAll('.sidebar-group').forEach(group => {
    group.style.display = 'block';
    group.classList.add('open');
  });
};

  window.applyDashboardSettings = applyDashboardSettings;
  window.loadUserProfile = loadUserProfile;
  window.Modules = window.Modules || {};
  window.Modules["1_overview"] = window.Modules["1_overview"] || {};
  window.Modules.DashboardInit = { applyDashboardSettings: applyDashboardSettings, loadUserProfile: loadUserProfile };
  window.Modules["1_overview"]["init"] = window.Modules.DashboardInit;
})();
