/* o-sidebar-manager.js
 * Organism: SidebarManager — sidebar navigation group manager.
 * Extracted from data.service.js (lines 6317-6400) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: DOM sidebar elements
 */
(function () {
  'use strict';

const SidebarManager = {
  init() {
    // 1. Group Headers click handler (independent toggle)
    document.querySelectorAll(".sidebar-group-header").forEach(header => {
      header.addEventListener("click", () => {
        const group = header.closest(".sidebar-group");
        const groupName = group.getAttribute("data-group");
        const sidebar = document.getElementById("sidebar");

        // Expand sidebar first if it was collapsed
        if (sidebar && sidebar.classList.contains("collapsed")) {
          sidebar.classList.remove("collapsed");
        }

        // Toggle this group independently
        const isOpen = group.classList.toggle("open");
        localStorage.setItem(`sidebar_group_${groupName}`, isOpen ? "open" : "closed");
      });
    });

    // 2. Open all sidebar groups by default so all 27+ menus are visible immediately
    document.querySelectorAll(".sidebar-group").forEach(group => {
      const groupName = group.getAttribute("data-group");
      const state = localStorage.getItem(`sidebar_group_${groupName}`);
      if (state === "closed") {
        group.classList.remove("open");
      } else {
        group.classList.add("open");
      }
    });

    // 3. Highlight and open group for current active panel
    this.syncActiveMenu();

    // 4. Start parent badge propagation updates on 1-second interval
    setInterval(() => {
      this.propagateBadges();
    }, 1000);
    this.propagateBadges();
  },

  syncActiveMenu() {
    const activeItem = document.querySelector(".submenu .nav-item.active");
    if (activeItem) {
      const parentGroup = activeItem.closest(".sidebar-group");
      if (parentGroup) {
        parentGroup.classList.add("open");
      }
    }

    // Toggle RBAC sub-menu display
    const rbacSub = document.getElementById("rbac-submenu");
    if (rbacSub) {
      const rbacNavItem = document.querySelector('.nav-item[data-panel="rbac"]');
      const isRbacActive = rbacNavItem && rbacNavItem.classList.contains('active');
      rbacSub.style.display = isRbacActive ? "block" : "none";
    }
  },

  propagateBadges() {
    document.querySelectorAll('.sidebar-group').forEach(group => {
      const groupBadge = group.querySelector('.sidebar-group-header .badge');
      if (!groupBadge) return;

      const childBadges = group.querySelectorAll('.submenu .badge');
      let sum = 0;
      childBadges.forEach(cb => {
        // Skip display:none badges
        if (cb.style.display === 'none') return;
        const val = parseInt(cb.textContent.trim(), 10);
        if (!isNaN(val) && val > 0) {
          sum += val;
        }
      });

      if (sum > 0) {
        groupBadge.textContent = sum;
        groupBadge.style.display = 'inline-block';
      } else {
        groupBadge.style.display = 'none';
      }
    });
  }
};

  window.SidebarManager = SidebarManager;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.SidebarManager = SidebarManager;
})();
