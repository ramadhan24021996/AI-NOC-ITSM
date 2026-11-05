/* panels/sop.js
 * SOP Lifecycle panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      sop: {
        _drafts: [],
        _active: [],
        async load() {
          let backendActive = [];
          let backendDrafts = [];
          let pendingReviewCount = 0;
          try {
            const res = await DataService.fetch('/api/governance/sops');
            if (res && res.success) {
              backendActive = res.active || [];
              backendDrafts = res.drafts || [];
              pendingReviewCount = (res.pending_review || []).length;
            }
          } catch (e) { console.error('Error fetching SOPs:', e); }

          this._active = backendActive;
          this._drafts = backendDrafts.map(d => ({
            name: d.name,
            trigger: d.trigger || 'SYSTEM_ALERT',
            desc: d.description || d.desc || '',
            type: d.meta && d.meta.includes('Manual') ? 'MANUAL' : 'ANOMALY',
            meta: d.meta || `DRAFT · Trigger: <code>${d.trigger}</code>`
          }));

          setEl('sop-active-kpi', backendActive.length);
          setEl('sop-draft-kpi', this._drafts.length);
          setEl('sop-review-kpi', pendingReviewCount || this._drafts.length);
          setEl('sop-draft-badge', this._drafts.length);
          setEl('sop-active-badge', backendActive.length);
          setEl('bdg-sop', this._drafts.length || 0);

          // Render Draft SOPs
          htmlEl('sop-draft-list', this._drafts.map((d, i) => `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:10px 12px;gap:6px;margin-bottom:8px">
        <div style="display:flex;align-items:center;justify-content:space-between;width:100%">
          <div style="font-size:11.5px;font-weight:600">📄 ${d.name}</div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-warning btn-xs" onclick="Panels.sop.promote(${i})">▲ Promote</button>
            <button class="btn btn-ghost btn-xs" style="color:var(--red2)" onclick="Panels.sop.deleteSOP('${d.name.replace(/'/g, "\\'")}')">🗑️</button>
          </div>
        </div>
        <div style="font-size:10px;color:var(--txt2)">${d.meta}</div>
      </div>`).join('') || '<div class="empty-state"><div class="es-icon"><i class="fa-solid fa-file-invoice"></i></div><div class="es-text">Tidak ada SOP draft</div></div>');

          // Render Active SOPs
          htmlEl('sop-active-list', backendActive.map(s => `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:rgba(34,197,94,.05);border:1px solid rgba(34,197,94,.15);border-radius:6px;padding:10px 12px;gap:4px;margin-bottom:8px">
        <div style="display:flex;align-items:center;justify-content:space-between;width:100%">
          <div style="font-size:11.5px;font-weight:600;color:var(--green2)">✅ ${s.name}</div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-primary btn-xs" onclick="Panels.sop.executeSOP('${s.name.replace(/'/g, "\\'")}')">▶️ Jalankan</button>
            <button class="btn btn-ghost btn-xs" style="color:var(--red2)" onclick="Panels.sop.deleteSOP('${s.name.replace(/'/g, "\\'")}')">🗑️</button>
          </div>
        </div>
        <div style="font-size:10px;color:var(--txt2)">${s.meta || 'ACTIVE · Remediation: ' + (s.remediation || s.trigger || 'AUTO')}</div>
      </div>`).join('') || '<div class="empty-state"><div class="es-icon"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i></div><div class="es-text">Tidak ada SOP aktif</div></div>');
        },
        async promote(idx) {
          const d = this._drafts[idx];
          if (!d) return;
          try {
            const res = await DataService.promoteSOP(d.name, d.trigger, d.desc);
            if (res && res.success) {
              Notify.toast('▲ Promoted', 'SOP "' + d.name + '" dipromosikan ke ACTIVE', 'ok', 3000);
              LogStreamer.add('OK', 'SOP', 'SOP promoted to ACTIVE: ' + d.name);
              await this.load();
            } else {
              Notify.toast('❌ Error', 'Gagal mempromosikan SOP', 'err', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Gagal mempromosikan SOP', 'err', 3000);
          }
        },
        async executeSOP(name) {
          try {
            const res = await DataService.executeSOP(name, 'ALL');
            if (res && res.success) {
              Notify.toast('▶️ SOP Executed', `SOP "${name}" berhasil dijalankan.`, 'ok', 3000);
              LogStreamer.add('OK', 'SOP', `SOP executed: ${name}`);
            } else {
              Notify.toast('❌ Error', res?.error || 'Gagal menjalankan SOP', 'err', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Gagal menjalankan SOP', 'err', 3000);
          }
        },
        async deleteSOP(name) {
          Modal.confirm('🗑️ Hapus SOP', `Apakah Anda yakin ingin menghapus SOP "${name}"?`, async () => {
            Modal.close();
            try {
              const res = await DataService.deleteSOP(name);
              if (res && res.success) {
                Notify.toast('🗑️ Deleted', `SOP "${name}" berhasil dihapus`, 'ok', 3000);
                LogStreamer.add('OK', 'SOP', `SOP deleted: ${name}`);
                await this.load();
              } else {
                Notify.toast('❌ Error', 'Gagal menghapus SOP', 'err', 3000);
              }
            } catch (e) {
              Notify.toast('❌ Error', 'Gagal menghapus SOP', 'err', 3000);
            }
          });
        },
        async create() {
          const n = document.getElementById('sop-new-name').value.trim();
          const t = document.getElementById('sop-new-trigger').value.trim();
          const d = document.getElementById('sop-new-desc').value.trim();
          if (!n || !t) { Notify.toast('⚠️', 'Nama dan Trigger wajib diisi', 'warn'); return; }
          try {
            const res = await DataService.createSOP(n, t, d);
            if (res && res.success) {
              Notify.toast('📄 SOP Created', '"' + n + '" berhasil dibuat sebagai DRAFT', 'ok', 3000);
              LogStreamer.add('OK', 'SOP', 'New SOP draft created: ' + n + ' · trigger: ' + t);
              this.clearForm();
              await this.load();
            } else {
              Notify.toast('❌ Error', 'Gagal membuat SOP draft', 'err', 3000);
            }
          } catch (e) {
            Notify.toast('❌ Error', 'Gagal membuat SOP draft', 'err', 3000);
          }
        },
        clearForm() { ['sop-new-name', 'sop-new-trigger', 'sop-new-desc'].forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; }); }
      },

      /* ---- PLAYBOOK STUDIO ---- */

});
