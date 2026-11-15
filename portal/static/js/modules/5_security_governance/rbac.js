/* panels/rbac.js
 * RBAC Policies panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      rbac: {
        activeTab: 'roles',

        async load() {
          const tab = this.activeTab || 'roles';
          this.setTab(tab);
          this.loadPolicies();
          this.loadUsers();
        },

        setTab(tabId) {
          this.activeTab = tabId;
          document.querySelectorAll('.rbac-tab-content').forEach(el => el.style.display = 'none');
          const target = document.getElementById('rbac-tab-' + tabId);
          if (target) target.style.display = 'block';

          document.querySelectorAll('.rbac-tab-btn').forEach(btn => {
            if (btn.getAttribute('onclick')?.includes(`'${tabId}'`)) {
              btn.classList.add('active');
            } else {
              btn.classList.remove('active');
            }
          });

          document.querySelectorAll('#rbac-submenu .sub-nav-item').forEach(item => {
            if (item.getAttribute('onclick')?.includes(`'${tabId}'`)) {
              item.classList.add('active');
            } else {
              item.classList.remove('active');
            }
          });

          if (tabId === 'policies') {
            this.loadPolicies();
          } else if (tabId === 'templates') {
            this.loadRoleTemplate();
          } else if (tabId === 'overrides') {
            this.loadOverrides();
          } else if (tabId === 'profile') {
            this.loadMyProfile();
          } else if (tabId === 'session') {
            this.loadSessionPolicies();
          } else if (tabId === 'audit') {
            this.loadAuditLogs();
          }
        },

        async loadPolicies() {
          const tbody = document.getElementById('rbac-policies-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="6" style="color:var(--txt2);font-size:11px;padding:12px;text-align:center">🔄 Loading RBAC policies...</td></tr>';

          try {
            const policies = await DataService.fetch('/api/rbac/policies');
            if (!policies) {
              tbody.innerHTML = '<tr><td colspan="6" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Gagal memuat kebijakan RBAC</td></tr>';
              return;
            }

            tbody.innerHTML = policies.map(p => {
              const role = p.role_name;
              const perms = p.permissions || {};
              const isSuperOrAdmin = role === 'admin' || role === 'superadmin';
              const disabledAttr = isSuperOrAdmin ? 'disabled checked' : '';

              return `<tr>
            <td style="padding-left:12px"><b style="color:var(--blue2);text-transform:uppercase">${role}</b></td>
            <td style="text-align:center"><input type="checkbox" class="rbac-chk" data-role="${role}" data-perm="all" ${perms.all ? 'checked' : ''} ${disabledAttr}></td>
            <td style="text-align:center"><input type="checkbox" class="rbac-chk" data-role="${role}" data-perm="access_config" ${perms.access_config ? 'checked' : ''} ${disabledAttr}></td>
            <td style="text-align:center"><input type="checkbox" class="rbac-chk" data-role="${role}" data-perm="remote_access" ${perms.remote_access ? 'checked' : ''} ${disabledAttr}></td>
            <td style="text-align:center"><input type="checkbox" class="rbac-chk" data-role="${role}" data-perm="access_governance" ${perms.access_governance ? 'checked' : ''} ${disabledAttr}></td>
            <td style="text-align:center"><input type="checkbox" class="rbac-chk" data-role="${role}" data-perm="restart_containers" ${perms.restart_containers ? 'checked' : ''} ${disabledAttr}></td>
          </tr>`;
            }).join('');

            await this.loadUsers();
          } catch (err) {
            console.error(err);
            tbody.innerHTML = `<tr><td colspan="6" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Error: ${err.message}</td></tr>`;
          }
        },

        async loadUsers() {
          const tbody = document.getElementById('rbac-users-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="6" style="color:var(--txt2);font-size:11px;padding:12px;text-align:center">🔄 Loading users...</td></tr>';

          try {
            const users = await DataService.fetch('/api/rbac/users');
            if (!users) {
              tbody.innerHTML = '<tr><td colspan="6" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Gagal memuat daftar pengguna</td></tr>';
              return;
            }

            tbody.innerHTML = users.map(u => {
              let settings = {};
              try {
                settings = JSON.parse(u.dashboard_settings || '{}');
              } catch (e) { settings = {}; }

              const theme = settings.theme || 'dark';
              const panels = settings.visible_panels || ['all'];
              const landing = settings.landing_panel || 'overview';
              const panelsStr = panels.includes('all') ? 'Semua Panel' : panels.join(', ');

              const isSuper = u.role_name === 'superadmin';
              const isSelf = u.username === window.currentUserId;
              const showDelete = !isSuper && !isSelf;

              return `<tr>
            <td style="padding-left:12px"><b>${u.username}</b></td>
            <td><span class="tag tag-blue">${u.role_name}</span></td>
            <td><span class="tag ${theme === 'light' ? 'tag-gray' : 'tag-purple'}">${theme.toUpperCase()}</span></td>
            <td style="font-size:11px;color:var(--txt2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${panelsStr}">${panelsStr}</td>
            <td><span class="tag tag-cyan">${landing}</span></td>
            <td style="text-align:center">
              <button class="btn btn-ghost btn-xs" onclick="Panels.rbac.editUserModal('${u.username}', '${u.role_name}', '${theme}', '${landing}', '${panels.join(',')}', '${u.display_name || ''}', '${u.avatar || ''}')">✏️ Edit</button>
              ${showDelete ? `<button class="btn btn-danger btn-xs" onclick="Panels.rbac.deleteUser('${u.username}')">🗑️ Hapus</button>` : ''}
            </td>
          </tr>`;
            }).join('');
          } catch (err) {
            console.error(err);
            tbody.innerHTML = `<tr><td colspan="6" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Error: ${err.message}</td></tr>`;
          }
        },

        newUserModal() {
          this.showUserFormModal('', 'viewer', 'dark', 'overview', [], false, '', '');
        },

        editUserModal(username, role, theme, landing, panelsStr, displayName, avatar) {
          const panels = panelsStr ? panelsStr.split(',') : [];
          this.showUserFormModal(username, role, theme, landing, panels, true, displayName, avatar);
        },

        showUserFormModal(username, role, theme, landing, panels, isEdit, displayName, avatar) {
          const panelKeys = [
            { key: 'overview', label: 'Dashboard Overview' },
            { key: 'monitoring', label: 'Monitoring Live' },
            { key: 'server', label: 'Server Health' },
            { key: 'incident', label: 'Incident Triage' },
            { key: 'rca', label: 'Ground Truth & RCA' },
            { key: 'unified_dag', label: 'Unified Graphs' },
            { key: 'pchealth', label: 'PC Health' },
            { key: 'printer', label: 'Printer Status' },
            { key: 'fleet', label: 'Fleet Management' },
            { key: 'storage', label: 'Storage' },
            { key: 'ai', label: 'AI Panel' },
            { key: 'training', label: 'Training Feedback' },
            { key: 'logs', label: 'Live Logs' },
            { key: 'gov', label: 'Governance' },
            { key: 'sop', label: 'SOP Lifecycle' },
            { key: 'models', label: 'Model Config' },
            { key: 'activity', label: 'Activity & Issues' },
            { key: 'chat', label: 'Live Chat' },
            { key: 'rbac', label: 'RBAC Policies' },
            { key: 'security_policies', label: 'Security Policies' },
            { key: 'recovery_mode_config', label: 'Recovery Mode' },
            { key: 'learning_gate_policy', label: 'Learning Gate Policy' }
          ];

          window.toggleAllUserPanels = function(masterCb) {
            const chks = document.querySelectorAll('.user-panel-chk');
            chks.forEach(c => c.checked = masterCb.checked);
          };

          window.updateUserPanelAllState = function() {
            const chks = Array.from(document.querySelectorAll('.user-panel-chk'));
            const master = document.getElementById('user-panel-all');
            if (master && chks.length > 0) {
              master.checked = chks.every(c => c.checked);
            }
          };

          const roleOptions = ['superadmin', 'admin', 'noc_engineering', 'operator', 'viewer'];
          const isAllChecked = panels.includes('all') || panels.length === 0;

          let panelsHtml = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;max-height:220px;overflow-y:auto;border:1px solid var(--bd2);padding:10px;border-radius:6px;background:var(--bg3)">`;
          panelsHtml += `<label style="display:flex;align-items:center;gap:6px;font-size:11.5px;grid-column:1/-1;border-bottom:1px solid var(--bd);padding-bottom:6px;margin-bottom:4px;cursor:pointer;font-weight:700;color:var(--blue2)">
            <input type="checkbox" id="user-panel-all" ${isAllChecked ? 'checked' : ''} onchange="window.toggleAllUserPanels(this)">
            <span>✨ Semua Panel (Full Access)</span>
          </label>`;

          panelKeys.forEach(p => {
            const isChecked = isAllChecked || panels.includes(p.key);
            panelsHtml += `<label style="display:flex;align-items:center;gap:6px;font-size:11.5px;cursor:pointer;user-select:none">
              <input type="checkbox" class="user-panel-chk" value="${p.key}" ${isChecked ? 'checked' : ''} onchange="window.updateUserPanelAllState()">
              <span>${p.label}</span>
            </label>`;
          });
          panelsHtml += `</div>`;

          const optionsHtml = roleOptions.map(r => {
            const disabled = (r === 'superadmin' && window.currentUserRole !== 'superadmin') ? 'disabled' : '';
            return `<option value="${r}" ${r === role ? 'selected' : ''} ${disabled}>${r.toUpperCase()}</option>`;
          }).join('');

          const bodyHTML = `
        <div style="display:flex;flex-direction:column;gap:12px;padding:12px 20px;text-align:left">
          <div>
            <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Username</label>
            <input type="text" id="user-username" class="inp" value="${username}" placeholder="Masukkan username..." style="width:100%">
          </div>
          <div>
            <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Nama Tampilan (Display Name)</label>
            <input type="text" id="user-displayname" class="inp" value="${displayName || ''}" placeholder="Nama lengkap..." style="width:100%">
          </div>
          <div>
            <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Avatar (Emoji/Initial)</label>
            <input type="text" id="user-avatar" class="inp" value="${avatar || ''}" placeholder="Emoji atau inisial..." style="width:100%">
          </div>
          <div>
            <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">${isEdit ? 'Password Baru (kosongkan jika tidak diubah)' : 'Password'}</label>
            <input type="password" id="user-password" class="inp" placeholder="Masukkan password..." style="width:100%">
          </div>
          <div>
            <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Role Akses</label>
            <select id="user-role" class="inp" style="width:100%">
              ${optionsHtml}
            </select>
          </div>
          <div style="border-top:1px solid var(--bd2);padding-top:10px;margin-top:6px">
            <h4 style="font-size:12px;font-weight:700;margin-bottom:8px;color:var(--blue2)"><i class="fa-solid fa-desktop"></i> Konfigurasi Tampilan Dashboard</h4>
            <div style="margin-bottom:8px">
              <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Dashboard Theme</label>
              <select id="user-theme" class="inp" style="width:100%">
                <option value="dark" ${theme === 'dark' ? 'selected' : ''}>DARK MODE (Sleek Dark)</option>
                <option value="light" ${theme === 'light' ? 'selected' : ''}>LIGHT MODE (Classic Light)</option>
              </select>
            </div>
            <div style="margin-bottom:8px">
              <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Landing Panel Default</label>
              <select id="user-landing" class="inp" style="width:100%">
                ${panelKeys.map(p => `<option value="${p.key}" ${p.key === landing ? 'selected' : ''}>${p.label}</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="inp-label" style="font-weight:600;margin-bottom:4px;display:block">Panel yang Terlihat di Menu</label>
              ${panelsHtml}
            </div>
          </div>
        </div>
      `;

          Modal.show(
            isEdit ? '✏️ Edit Pengguna' : '➕ Tambah Pengguna Baru',
            bodyHTML,
            [
              { label: 'Simpan', cls: 'btn-primary', fn: () => Panels.rbac.saveUser(username, isEdit) },
              { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() }
            ],
            '👤'
          );
        },

        async saveUser(origUsername, isEdit) {
          const newUsername = document.getElementById('user-username').value.trim();
          const displayName = document.getElementById('user-displayname').value.trim();
          const avatar = document.getElementById('user-avatar').value.trim();
          const password = document.getElementById('user-password').value;
          const roleName = document.getElementById('user-role').value;
          const theme = document.getElementById('user-theme').value;
          const landing_panel = document.getElementById('user-landing').value;

          if (!newUsername) {
            Notify.toast('⚠️ Input Error', 'Username wajib diisi', 'warn', 3000);
            return;
          }
          if (!isEdit && !password) {
            Notify.toast('⚠️ Input Error', 'Password wajib diisi untuk pengguna baru', 'warn', 3000);
            return;
          }

          let visible_panels = [];
          const allMaster = document.getElementById('user-panel-all')?.checked;
          const chks = document.querySelectorAll('.user-panel-chk');
          const checkedChks = Array.from(chks).filter(c => c.checked).map(c => c.value);

          if (allMaster || checkedChks.length === chks.length) {
            visible_panels = ['all'];
          } else if (checkedChks.length > 0) {
            visible_panels = checkedChks;
          } else {
            visible_panels = ['overview'];
          }

          const settingsObj = {
            theme: theme,
            visible_panels: visible_panels,
            landing_panel: landing_panel
          };

          try {
            const resp = await DataService.fetch('/api/rbac/users', {
              method: 'POST',
              body: JSON.stringify({
                orig_username: isEdit ? origUsername : '',
                username: newUsername,
                password: password,
                role_name: roleName,
                display_name: displayName,
                avatar: avatar,
                dashboard_settings: JSON.stringify(settingsObj)
              })
            });

            if (resp && (resp.status === 'SUCCESS' || resp.success)) {
              Notify.toast('✅ Sukses', 'Pengguna berhasil disimpan', 'ok', 2500);
              Modal.close();
              this.loadPolicies();

              loadUserProfile();
            } else {
              Notify.toast('⚠️ Error', resp?.error || 'Gagal menyimpan pengguna', 'warn', 4000);
            }
          } catch (err) {
            Notify.toast('❌ Error', err.message, 'error', 3000);
          }
        },

        deleteUser(username) {
          Modal.confirm(
            '🗑️ Hapus Pengguna',
            `Apakah Anda yakin ingin menghapus pengguna "${username}"?`,
            async () => {
              try {
                const resp = await DataService.fetch(`/api/rbac/users/${username}`, { method: 'DELETE' });
                if (resp && (resp.status === 'SUCCESS' || resp.success)) {
                  Notify.toast('✅ Sukses', `Pengguna ${username} berhasil dihapus`, 'ok', 2500);
                  Modal.close();
                  Panels.rbac.loadPolicies();
                } else {
                  Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menghapus pengguna', 'warn', 4000);
                }
              } catch (e) {
                Notify.toast('❌ Error', e.message, 'error', 3000);
              }
            }
          );
        },

        async save() {
          Notify.toast('💾 Saving', 'Menyimpan kebijakan RBAC...', 'info', 1500);

          const rows = {};
          document.querySelectorAll('.rbac-chk').forEach(chk => {
            const role = chk.getAttribute('data-role');
            const perm = chk.getAttribute('data-perm');
            if (!rows[role]) rows[role] = {};
            rows[role][perm] = chk.checked;
          });

          let successCount = 0;
          let totalCount = 0;

          try {
            for (const role of Object.keys(rows)) {
              if (role === 'admin' || role === 'superadmin') continue;
              totalCount++;

              const resp = await DataService.fetch('/api/rbac/policies', {
                method: 'POST',
                body: JSON.stringify({
                  role_name: role,
                  permissions: rows[role]
                })
              });

              if (resp && (resp.status === 'SUCCESS' || resp.success)) {
                successCount++;
              }
            }

            if (successCount === totalCount) {
              Notify.toast('✅ RBAC', 'Semua kebijakan RBAC berhasil disimpan', 'ok', 2500);
              LogStreamer.add('OK', 'RBAC', 'RBAC policies updated by operator');
              this.loadPolicies();
            } else {
              Notify.toast('⚠️ RBAC', 'Beberapa kebijakan gagal disimpan. Pastikan Anda login sebagai Admin.', 'warn', 4000);
            }
          } catch (err) {
            Notify.toast('❌ Error', err.message, 'error', 3000);
          }
        },

        async loadRoleTemplate() {
          const role = document.getElementById('template-role-select').value;
          const listEl = document.getElementById('role-template-widgets-list');
          if (!listEl) return;
          listEl.innerHTML = '<div style="color:var(--txt2);font-size:11px;padding:8px">Loading template widgets...</div>';

          try {
            const res = await DataService.fetch(`/api/dashboard/layout?role_name=${role}`);
            if (!res || !res.layout) {
              listEl.innerHTML = '<div style="color:var(--red);font-size:11px;padding:8px">Gagal memuat template layout.</div>';
              return;
            }

            const widgets = typeof res.layout === 'string' ? JSON.parse(res.layout) : res.layout;

            listEl.innerHTML = widgets.map((w, idx) => {
              return `<div class="li-row" style="display:flex; justify-content:space-between; align-items:center; background:var(--glass); border-radius:6px; padding:8px 12px; margin-bottom:4px">
            <div style="display:flex; align-items:center; gap:8px">
              <span style="color:var(--txt3); font-size:10px; font-weight:700">#${idx + 1}</span>
              <span style="font-size:12.5px; font-weight:600; color:var(--txt)">${w.id.replace('widget-', '').toUpperCase()}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px">
              <label style="font-size:11px; color:var(--txt2); display:flex; align-items:center; gap:4px">
                Col Span:
                <select class="inp template-widget-span" data-widget-id="${w.id}" style="width:50px; padding:2px">
                  <option value="1" ${w.col_span === 1 ? 'selected' : ''}>1</option>
                  <option value="2" ${w.col_span === 2 ? 'selected' : ''}>2</option>
                  <option value="3" ${w.col_span === 3 ? 'selected' : ''}>3</option>
                  <option value="4" ${w.col_span === 4 ? 'selected' : ''}>4</option>
                </select>
              </label>
              <label style="font-size:11px; color:var(--txt2); display:flex; align-items:center; gap:4px">
                <input type="checkbox" class="template-widget-visible" data-widget-id="${w.id}" ${w.visible ? 'checked' : ''}> Visible
              </label>
              <button class="btn btn-ghost btn-xs" onclick="Panels.rbac.moveTemplateWidget('${role}', ${idx}, -1)" ${idx === 0 ? 'disabled' : ''}>▲</button>
              <button class="btn btn-ghost btn-xs" onclick="Panels.rbac.moveTemplateWidget('${role}', ${idx}, 1)" ${idx === widgets.length - 1 ? 'disabled' : ''}>▼</button>
            </div>
          </div>`;
            }).join('');
          } catch (err) {
            listEl.innerHTML = `<div style="color:var(--red);font-size:11px;padding:8px">Error: ${err.message}</div>`;
          }
        },

        moveTemplateWidget(role, idx, dir) {
          const listEl = document.getElementById('role-template-widgets-list');
          if (!listEl) return;
          const rows = listEl.querySelectorAll('.li-row');
          const widgets = [];
          rows.forEach(row => {
            const spanSel = row.querySelector('.template-widget-span');
            const visChk = row.querySelector('.template-widget-visible');
            if (spanSel && visChk) {
              widgets.push({
                id: spanSel.getAttribute('data-widget-id'),
                col_span: parseInt(spanSel.value, 10),
                visible: visChk.checked,
                favorite: false
              });
            }
          });
          
          const targetIdx = idx + dir;
          if (targetIdx < 0 || targetIdx >= widgets.length) return;
          const temp = widgets[idx];
          widgets[idx] = widgets[targetIdx];
          widgets[targetIdx] = temp;

          listEl.innerHTML = widgets.map((w, i) => {
            return `<div class="li-row" style="display:flex; justify-content:space-between; align-items:center; background:var(--glass); border-radius:6px; padding:8px 12px; margin-bottom:4px">
            <div style="display:flex; align-items:center; gap:8px">
              <span style="color:var(--txt3); font-size:10px; font-weight:700">#${i + 1}</span>
              <span style="font-size:12.5px; font-weight:600; color:var(--txt)">${w.id.replace('widget-', '').toUpperCase()}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px">
              <label style="font-size:11px; color:var(--txt2); display:flex; align-items:center; gap:4px">
                Col Span:
                <select class="inp template-widget-span" data-widget-id="${w.id}" style="width:50px; padding:2px">
                  <option value="1" ${w.col_span === 1 ? 'selected' : ''}>1</option>
                  <option value="2" ${w.col_span === 2 ? 'selected' : ''}>2</option>
                  <option value="3" ${w.col_span === 3 ? 'selected' : ''}>3</option>
                  <option value="4" ${w.col_span === 4 ? 'selected' : ''}>4</option>
                </select>
              </label>
              <label style="font-size:11px; color:var(--txt2); display:flex; align-items:center; gap:4px">
                <input type="checkbox" class="template-widget-visible" data-widget-id="${w.id}" ${w.visible ? 'checked' : ''}> Visible
              </label>
              <button class="btn btn-ghost btn-xs" onclick="Panels.rbac.moveTemplateWidget('${role}', ${i}, -1)" ${i === 0 ? 'disabled' : ''}>▲</button>
              <button class="btn btn-ghost btn-xs" onclick="Panels.rbac.moveTemplateWidget('${role}', ${i}, 1)" ${i === widgets.length - 1 ? 'disabled' : ''}>▼</button>
            </div>
          </div>`;
          }).join('');
        },

        async saveRoleTemplate() {
          const role = document.getElementById('template-role-select').value;
          try {
            const listEl = document.getElementById('role-template-widgets-list');
            if (!listEl) return;
            const rows = listEl.querySelectorAll('.li-row');
            const widgets = [];
            rows.forEach(row => {
              const spanSel = row.querySelector('.template-widget-span');
              const visChk = row.querySelector('.template-widget-visible');
              if (spanSel && visChk) {
                widgets.push({
                  id: spanSel.getAttribute('data-widget-id'),
                  col_span: parseInt(spanSel.value, 10),
                  visible: visChk.checked,
                  favorite: false
                });
              }
            });

            if (widgets.length === 0) return;

            const resp = await DataService.fetch('/api/dashboard/layout/save', {
              method: 'POST',
              body: JSON.stringify({
                target_type: 'role',
                target_name: role,
                layout: JSON.stringify(widgets)
              })
            });
            if (resp && (resp.status === 'SUCCESS' || resp.success)) {
              Notify.toast('✅ Sukses', 'Template role berhasil diperbarui', 'ok', 2500);
              this.loadRoleTemplate();
            } else {
              Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menyimpan template', 'warn', 3000);
            }
          } catch (err) {
            Notify.toast('❌ Error', err.message, 'error', 3000);
          }
        },

        async resetRoleTemplate() {
          const role = document.getElementById('template-role-select').value;
          Modal.confirm(
            '🔄 Reset Template',
            `Apakah Anda yakin ingin mereset layout template role "${role}" ke default system?`,
            async () => {
              try {
                const resp = await DataService.fetch('/api/dashboard/layout/reset', {
                  method: 'POST',
                  body: JSON.stringify({
                    target_type: 'role',
                    target_name: role
                  })
                });
                if (resp && (resp.status === 'SUCCESS' || resp.success)) {
                  Notify.toast('✅ Sukses', 'Template berhasil di-reset', 'ok', 2500);
                  Modal.close();
                  this.loadRoleTemplate();
                } else {
                  Notify.toast('⚠️ Gagal', resp?.error || 'Gagal mereset template', 'warn', 3000);
                }
              } catch (e) {
                Notify.toast('❌ Error', e.message, 'error', 3000);
              }
            }
          );
        },

        async loadOverrides() {
          const tbody = document.getElementById('rbac-overrides-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="3" style="color:var(--txt2);font-size:11px;padding:12px;text-align:center">🔄 Loading overrides...</td></tr>';

          try {
            const overrides = await DataService.fetch('/api/dashboard/layout/overrides');
            if (!overrides || overrides.length === 0) {
              tbody.innerHTML = '<tr><td colspan="3" style="color:var(--txt3);font-size:11.5px;padding:12px;text-align:center">ℹ️ Tidak ada user override aktif saat ini. Semua user menggunakan fallback role template.</td></tr>';
              return;
            }

            tbody.innerHTML = overrides.map(o => {
              const t = new Date(o.updated_at).toLocaleString();
              return `<tr>
            <td style="padding-left:12px"><b>${o.username}</b></td>
            <td>${t}</td>
            <td style="text-align:center">
              <button class="btn btn-danger btn-xs" onclick="Panels.rbac.deleteOverride('${o.username}')">🗑️ Reset Override</button>
            </td>
          </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="3" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Error: ${err.message}</td></tr>`;
          }
        },

        async deleteOverride(username) {
          Modal.confirm(
            '🗑️ Hapus Override',
            `Apakah Anda yakin ingin menghapus kustomisasi layout user "${username}"? Tampilan akan kembali mengikuti default template dari rolenya.`,
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
                  Notify.toast('✅ Sukses', 'Kustomisasi layout user berhasil di-reset', 'ok', 2500);
                  Modal.close();
                  this.loadOverrides();
                } else {
                  Notify.toast('⚠️ Gagal', resp?.error || 'Gagal mereset layout', 'warn', 3000);
                }
              } catch (err) {
                Notify.toast('❌ Error', err.message, 'error', 3000);
              }
            }
          );
        },

        async loadMyProfile() {
          try {
            const resp = await DataService.fetch('/api/auth/verify');
            if (resp && resp.valid) {
              const username = resp.user_id;
              const users = await DataService.fetch('/api/rbac/users');
              const user = users.find(u => u.username === username);
              if (user) {
                document.getElementById('prof-username').value = user.username;
                document.getElementById('prof-displayname').value = user.display_name || '';
                document.getElementById('prof-avatar').value = user.avatar || '';
                const apiTokenInput = document.getElementById('prof-apitoken');
                if (apiTokenInput) apiTokenInput.value = user.api_token || '';
                document.getElementById('prof-username').disabled = true;
              }
            }
          } catch (err) {
            Notify.toast('❌ Error', 'Gagal memuat profil: ' + err.message, 'error', 3000);
          }
        },

        async saveMyProfile() {
          const displayName = document.getElementById('prof-displayname').value.trim();
          const avatar = document.getElementById('prof-avatar').value.trim();
          const oldPassword = document.getElementById('prof-oldpassword').value;
          const newPassword = document.getElementById('prof-newpassword').value;
          const apiTokenInput = document.getElementById('prof-apitoken');
          const apiToken = apiTokenInput ? apiTokenInput.value.trim() : '';

          if (!oldPassword) {
            Notify.toast('⚠️ Validasi', 'Silakan masukkan Password Lama Anda untuk konfirmasi perubahan.', 'warn', 4000);
            return;
          }

          try {
            const resp = await DataService.fetch('/api/auth/profile', {
              method: 'POST',
              body: JSON.stringify({
                display_name: displayName,
                avatar: avatar,
                old_password: oldPassword,
                new_password: newPassword,
                api_token: apiToken
              })
            });

            if (resp && (resp.status === 'SUCCESS' || resp.success)) {
              Notify.toast('✅ Sukses', 'Profil berhasil disimpan.', 'ok', 2500);
              document.getElementById('prof-oldpassword').value = '';
              document.getElementById('prof-newpassword').value = '';
              loadUserProfile();
            } else {
              Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menyimpan profil', 'warn', 4000);
            }
          } catch (err) {
            Notify.toast('❌ Error', err.message, 'error', 3000);
          }
        },

        generateApiToken() {
          const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
          let token = 'NOC_AGENT_';
          for (let i = 0; i < 32; i++) {
            token += chars.charAt(Math.floor(Math.random() * chars.length));
          }
          document.getElementById('prof-apitoken').value = token;
          Notify.toast('🔑 API Token', 'API Token berhasil di-generate. Salin token ini untuk konfigurasi agent.', 'ok', 3000);
        },

        logoutAllDevices() {
          Modal.confirm(
            '⚠️ Logout Semua Device',
            'Apakah Anda yakin ingin melakukan force logout ke seluruh device yang terhubung dengan akun Anda? Sesi saat ini juga akan berakhir.',
            async () => {
              try {
                await DataService.fetch('/api/auth/logout', { method: 'POST' });
              } catch (e) {
                console.error('Logout error', e);
              }
              localStorage.setItem('explicit_logout', '1');
              sessionStorage.setItem('explicit_logout', '1');
              sessionStorage.clear();
              localStorage.removeItem('noc_jwt_token');
              localStorage.removeItem('noc_auth');
              window.currentUserRole = null;
              window.currentUserId = null;
              Notify.toast('🔒 Force Logout', 'Membersihkan token sesi, silakan login kembali...', 'info', 2000);
              setTimeout(() => window.location.reload(), 1500);
            }
          );
        },

        async loadSessionPolicies() {
          const tbody = document.getElementById('rbac-sessions-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="5" style="color:var(--txt2);font-size:11px;padding:12px;text-align:center">🔄 Loading session policies...</td></tr>';

          try {
            const policies = await DataService.fetch('/api/rbac/session_policies');
            if (!policies) {
              tbody.innerHTML = '<tr><td colspan="5" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Gagal memuat kebijakan sesi</td></tr>';
              return;
            }

            tbody.innerHTML = policies.map(p => {
              return `<tr>
            <td style="padding-left:12px"><b style="color:var(--blue2);text-transform:uppercase">${p.role_name}</b></td>
            <td>
              <input type="number" class="inp session-timeout-val" data-role="${p.role_name}" value="${p.session_timeout_minutes}" style="width:80px; padding:4px"> Menit
            </td>
            <td>
              <input type="number" class="inp session-max-val" data-role="${p.role_name}" value="${p.max_concurrent_sessions}" style="width:80px; padding:4px"> Sesi
            </td>
            <td style="text-align:center">
              <input type="checkbox" class="session-mfa-val" data-role="${p.role_name}" ${p.enforce_mfa ? 'checked' : ''}>
            </td>
            <td style="text-align:center">
              <button class="btn btn-primary btn-xs" onclick="Panels.rbac.saveSessionPolicy('${p.role_name}')">💾 Simpan</button>
            </td>
          </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Error: ${err.message}</td></tr>`;
          }
        },

        async saveSessionPolicy(roleName) {
          const timeoutInput = document.querySelector(`.session-timeout-val[data-role="${roleName}"]`);
          const maxInput = document.querySelector(`.session-max-val[data-role="${roleName}"]`);
          const mfaInput = document.querySelector(`.session-mfa-val[data-role="${roleName}"]`);

          if (!timeoutInput || !maxInput || !mfaInput) return;

          const timeout = parseInt(timeoutInput.value, 10);
          const maxSessions = parseInt(maxInput.value, 10);
          const enforceMfa = mfaInput.checked;

          try {
            const resp = await DataService.fetch('/api/rbac/session_policies', {
              method: 'POST',
              body: JSON.stringify({
                role_name: roleName,
                session_timeout_minutes: timeout,
                max_concurrent_sessions: maxSessions,
                enforce_mfa: enforceMfa
              })
            });

            if (resp && (resp.status === 'SUCCESS' || resp.success)) {
              Notify.toast('✅ Sukses', `Kebijakan sesi untuk ${roleName.toUpperCase()} berhasil diperbarui.`, 'ok', 2500);
              this.loadSessionPolicies();
            } else {
              Notify.toast('⚠️ Gagal', resp?.error || 'Gagal menyimpan kebijakan sesi', 'warn', 4000);
            }
          } catch (err) {
            Notify.toast('❌ Error', err.message, 'error', 3000);
          }
        },

        async loadAuditLogs() {
          const tbody = document.getElementById('rbac-audit-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="6" style="color:var(--txt2);font-size:11px;padding:12px;text-align:center">🔄 Loading audit logs...</td></tr>';

          try {
            const logs = await DataService.fetch('/api/rbac/audit_logs');
            if (!logs || logs.length === 0) {
              tbody.innerHTML = '<tr><td colspan="6" style="color:var(--txt3);font-size:11px;padding:12px;text-align:center">Tidak ada catatan aktivitas audit.</td></tr>';
              return;
            }

            tbody.innerHTML = logs.map(l => {
              const t = new Date(l.created_at).toLocaleString();
              return `<tr>
            <td style="padding-left:12px; font-size:11px; color:var(--txt2)">${t}</td>
            <td><b style="color:var(--blue2)">${l.username}</b></td>
            <td><span class="tag tag-purple">${l.action}</span></td>
            <td><b>${l.target}</b></td>
            <td style="font-size:11.5px; color:var(--txt2)">${l.details}</td>
            <td style="font-size:11px; color:var(--txt3)">${l.ip_address}</td>
          </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="color:var(--red);font-size:11px;padding:12px;text-align:center">❌ Error: ${err.message}</td></tr>`;
          }
        }
      },

});
