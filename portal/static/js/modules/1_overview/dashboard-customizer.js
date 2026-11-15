/* dashboard-customizer.js
 * Module: DashboardCustomizer — widget layout customize/save/reset.
 * Extracted from o-nav-router.js (lines 315-600) — Phase 5.5 Atomic Design refactor.
 *
 * Layer: Modules > 1_overview
 * Depends on: DataService (service), Notify (molecule), Modal (molecule)
 */
(function () {
  'use strict';

var DashboardCustomizer = {
  widgets: [],
  customizeMode: false,

  async init() {
    try {
      const res = await DataService.fetch('/api/dashboard/layout');
      if (res && res.layout) {
        this.widgets = typeof res.layout === 'string' ? JSON.parse(res.layout) : res.layout;
      }
    } catch (e) {
      console.error('Gagal memuat layout:', e);
      this.widgets = [
        { id: "widget-online", col_span: 1, visible: true, favorite: false },
        { id: "widget-incidents", col_span: 1, visible: true, favorite: false },
        { id: "widget-health", col_span: 1, visible: true, favorite: false },
        { id: "widget-total", col_span: 1, visible: true, favorite: false },
        { id: "widget-mttr", col_span: 1, visible: true, favorite: false },
        { id: "widget-avail", col_span: 1, visible: true, favorite: false },
        { id: "widget-aiconf", col_span: 1, visible: true, favorite: false },
        { id: "widget-ticket", col_span: 1, visible: true, favorite: false },
        { id: "widget-live-incidents", col_span: 2, visible: true, favorite: false },
        { id: "widget-pipeline", col_span: 2, visible: true, favorite: false },
        { id: "widget-trend", col_span: 2, visible: true, favorite: false },
        { id: "widget-osi", col_span: 2, visible: true, favorite: false },
        { id: "widget-critical-alert", col_span: 1, visible: true, favorite: false },
        { id: "widget-active-sessions", col_span: 1, visible: true, favorite: false },
        { id: "widget-storage-usage", col_span: 1, visible: true, favorite: false },
        { id: "widget-cpu-usage", col_span: 1, visible: true, favorite: false },
        { id: "widget-ram-usage", col_span: 1, visible: true, favorite: false },
        { id: "widget-database-health", col_span: 1, visible: true, favorite: false },
        { id: "widget-redis-health", col_span: 1, visible: true, favorite: false },
        { id: "widget-queue-health", col_span: 1, visible: true, favorite: false },
        { id: "widget-audit-activity", col_span: 2, visible: true, favorite: false },
        { id: "widget-login-activity", col_span: 2, visible: true, favorite: false },
        { id: "widget-security-event", col_span: 2, visible: true, favorite: false },
        { id: "widget-prediction", col_span: 2, visible: true, favorite: false },
        { id: "widget-executive-analytics", col_span: 2, visible: true, favorite: false }
      ];
    }
    this.applyLayoutToDOM();
  },

  applyLayoutToDOM() {
    const parent = document.getElementById('p-overview');
    if (!parent) return;

    document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());

    const isSuperadmin = (window.currentUserRole === 'superadmin');
    const newWidgetIds = [
      "widget-critical-alert", "widget-active-sessions", "widget-storage-usage",
      "widget-cpu-usage", "widget-ram-usage", "widget-database-health",
      "widget-redis-health", "widget-queue-health", "widget-audit-activity",
      "widget-login-activity", "widget-security-event", "widget-prediction",
      "widget-executive-analytics"
    ];

    const activeWidgets = isSuperadmin ? this.widgets : this.widgets.filter(w => !newWidgetIds.includes(w.id));

    const widgetEls = {};
    activeWidgets.forEach(w => {
      const el = document.getElementById(w.id);
      if (el) {
        widgetEls[w.id] = el;
        el.style.gridColumn = w.visible ? `span ${w.col_span || 1}` : 'none';
        el.style.display = w.visible ? '' : 'none';
        if (w.favorite) {
          el.classList.add('widget-favorite');
        } else {
          el.classList.remove('widget-favorite');
        }
      }
    });

    if (!isSuperadmin) {
      newWidgetIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          el.style.display = 'none';
          el.style.gridColumn = 'none';
        }
      });
    }

    const toolbar = parent.firstElementChild;
    const allExistingWidgets = Array.from(parent.querySelectorAll('.dashboard-widget'));

    parent.innerHTML = '';
    if (toolbar && !toolbar.classList.contains('dashboard-widget')) {
      parent.appendChild(toolbar);
    }

    activeWidgets.forEach(w => {
      const el = widgetEls[w.id];
      if (el) {
        parent.appendChild(el);
      }
    });

    allExistingWidgets.forEach(el => {
      if (!widgetEls[el.id]) {
        if (!isSuperadmin && newWidgetIds.includes(el.id)) {
          // completely hide for non-admins
        } else {
          parent.appendChild(el);
        }
      }
    });

    if (this.customizeMode) {
      this.renderToolbars();
    }
  },

  toggleCustomizeMode() {
    this.customizeMode = !this.customizeMode;
    const parent = document.getElementById('p-overview');
    if (!parent) return;

    if (this.customizeMode) {
      parent.classList.add('customize-mode-active');
      this.renderToolbars();
      Notify.toast('✏️ Edit Layout', 'Mode kustomisasi aktif. Klik tombol pada widget untuk mengatur ukuran, urutan, favorit, atau menyembunyikan.', 'info', 4000);
    } else {
      parent.classList.remove('customize-mode-active');
      document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());
    }
  },

  renderToolbars() {
    document.querySelectorAll('.widget-toolbar').forEach(tb => tb.remove());

    this.widgets.forEach((w, idx) => {
      const el = document.getElementById(w.id);
      if (!el || !w.visible) return;

      const tb = document.createElement('div');
      tb.className = 'widget-toolbar';
      tb.innerHTML = `
    <button onclick="DashboardCustomizer.changeSpan('${w.id}', 1)" title="Perbesar Lebar"><i class="fa-solid fa-plus"></i></button>
    <button onclick="DashboardCustomizer.changeSpan('${w.id}', -1)" title="Perkecil Lebar"><i class="fa-solid fa-minus"></i></button>
    <button onclick="DashboardCustomizer.moveWidget(${idx}, -1)" title="Geser Kiri/Atas" ${idx === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-left"></i></button>
    <button onclick="DashboardCustomizer.moveWidget(${idx}, 1)" title="Geser Kanan/Bawah" ${idx === this.widgets.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-right"></i></button>
    <button onclick="DashboardCustomizer.toggleFavorite('${w.id}')" title="Favorit"><i class="fa-solid fa-star" style="color:${w.favorite ? 'var(--orange)' : 'var(--txt3)'}"></i></button>
    <button onclick="DashboardCustomizer.hideWidget('${w.id}')" title="Sembunyikan"><i class="fa-solid fa-eye-slash"></i></button>
  `;
      el.appendChild(tb);
    });
  },

  changeSpan(id, delta) {
    const w = this.widgets.find(item => item.id === id);
    if (w) {
      w.col_span = Math.max(1, Math.min(4, (w.col_span || 1) + delta));
      this.applyLayoutToDOM();
    }
  },

  moveWidget(idx, dir) {
    const targetIdx = idx + dir;
    if (targetIdx >= 0 && targetIdx < this.widgets.length) {
      const temp = this.widgets[idx];
      this.widgets[idx] = this.widgets[targetIdx];
      this.widgets[targetIdx] = temp;
      this.applyLayoutToDOM();
    }
  },

  toggleFavorite(id) {
    const w = this.widgets.find(item => item.id === id);
    if (w) {
      w.favorite = !w.favorite;
      this.applyLayoutToDOM();
    }
  },

  hideWidget(id) {
    const w = this.widgets.find(item => item.id === id);
    if (w) {
      w.visible = false;
      this.applyLayoutToDOM();
      Notify.toast('👁️ Widget Tersembunyi', `Widget disembunyikan.`, 'info', 2500);
    }
  },

  showHiddenWidgetsModal() {
    const hidden = this.widgets.filter(w => !w.visible);
    if (hidden.length === 0) {
      Notify.toast('ℹ️ Info', 'Semua widget saat ini sudah ditampilkan.', 'info', 2500);
      return;
    }

    const bodyHTML = `
  <div style="padding:12px 20px; text-align:left; display:flex; flex-direction:column; gap:8px">
    <p style="font-size:11.5px; color:var(--txt2)">Pilih widget di bawah ini untuk ditampilkan kembali di dashboard:</p>
    ${hidden.map(w => `
      <label style="display:flex; align-items:center; gap:8px; background:var(--bg3); border:1px solid var(--bd2); padding:8px 12px; border-radius:6px; font-size:13px; font-weight:600">
        <input type="checkbox" class="unhide-chk" value="${w.id}"> ${w.id.replace('widget-', '').toUpperCase()}
      </label>
    `).join('')}
  </div>
`;

    Modal.show(
      '👁️ Tampilkan Widget Tersembunyi',
      bodyHTML,
      [
        {
          label: 'Tampilkan Terpilih', cls: 'btn-primary', fn: () => {
            document.querySelectorAll('.unhide-chk').forEach(chk => {
              if (chk.checked) {
                const w = this.widgets.find(item => item.id === chk.value);
                if (w) w.visible = true;
              }
            });
            Modal.close();
            this.applyLayoutToDOM();
          }
        },
        { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() }
      ],
      '👁️'
    );
  },

  async saveLayout() {
    const username = window.currentUserId;
    if (!username) {
      Notify.toast('⚠️ Gagal', 'Username tidak teridentifikasi. Gagal menyimpan layout.', 'warn', 3000);
      return;
    }

    try {
      const resp = await DataService.fetch('/api/dashboard/layout/save', {
        method: 'POST',
        body: JSON.stringify({
          target_type: 'user',
          target_name: username,
          layout: JSON.stringify(this.widgets)
        })
      });

      if (resp && (resp.status === 'SUCCESS' || resp.success)) {
        Notify.toast('✅ Sukses', 'Layout dashboard Anda berhasil disimpan secara permanen.', 'ok', 2500);
        if (this.customizeMode) this.toggleCustomizeMode();
      } else {
        Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menyimpan layout', 'warn', 3000);
      }
    } catch (err) {
      Notify.toast('❌ Error', err.message, 'error', 3000);
    }
  },

  async resetLayout() {
    const username = window.currentUserId;
    if (!username) return;

    Modal.confirm(
      '🔄 Reset Layout',
      'Apakah Anda yakin ingin mereset layout dashboard Anda ke template default role?',
      async () => {
        try {
          const resp = await DataService.fetch('/api/dashboard/layout/reset', {
            method: 'POST',
            body: JSON.stringify({
              target_type: 'user',
              target_name: username
            })
          });

          if (resp && (resp.status === 'SUCCESS' || resp.success)) {
            Notify.toast('✅ Sukses', 'Layout dashboard berhasil di-reset.', 'ok', 2500);
            Modal.close();
            this.customizeMode = false;
            await this.init();
          } else {
            Notify.toast('⚠️ Gagal', resp?.error || 'Gagal mereset layout', 'warn', 3000);
          }
        } catch (err) {
          Notify.toast('❌ Error', err.message, 'error', 3000);
        }
      }
    );
  }
};

  window.DashboardCustomizer = DashboardCustomizer;
  window.Modules = window.Modules || {};
  window.Modules["1_overview"] = window.Modules["1_overview"] || {};
  window.Modules["1_overview"]["dashboard-customizer"] = DashboardCustomizer;
  window.Modules.DashboardCustomizer = DashboardCustomizer;
})();
