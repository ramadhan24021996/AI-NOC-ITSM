/* panels/playbooks.js
 * Playbook Studio panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      playbooks: {
        async load() {
          const tbody = document.getElementById('tbody-playbooks');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Playbooks...</div></td></tr>';
          try {
            const playbooks = await DataService.fetch('/api/playbooks');

            if (!playbooks || !Array.isArray(playbooks) || playbooks.length === 0) {
              tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Belum ada Playbook tersimpan</td></tr>';
              return;
            }

            tbody.innerHTML = playbooks.map(p => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
            <td><b>#${p.playbook_id}</b></td>
            <td><div style="font-weight:600">${p.name}</div></td>
            <td><div style="font-size:11px;color:var(--txt2);max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${p.description}">${p.description || '-'}</div></td>
            <td style="text-align:center"><span class="tag tag-cyan">L${p.target_layer}</span></td>
            <td style="text-align:center"><span class="tag ${p.status === 'ACTIVE' ? 'tag-green' : 'tag-orange'}">${p.status || 'ACTIVE'}</span></td>
            <td style="text-align:right">
              <button class="btn btn-ghost btn-sm" onclick="Panels.playbooks.execute(${p.playbook_id})" style="padding:2px 6px;color:var(--green2)" title="Execute Playbook"><i class="fa-solid fa-bolt"></i> Run</button>
              <button class="btn btn-ghost btn-sm" onclick="Panels.playbooks.edit(${p.playbook_id})" style="padding:2px 6px" title="Edit"><i class="fa-solid fa-pen"></i></button>
              <button class="btn btn-ghost btn-sm" onclick="Panels.playbooks.delete(${p.playbook_id})" style="padding:2px 6px;color:var(--red)" title="Delete"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
        `).join('');
            this._data = playbooks;
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat playbook: ${err.message}</td></tr>`;
            console.error(err);
          }
        },

        async execute(id, dryRun = false) {
          Modal.confirm('⚡ Eksekusi Playbook #' + id, `Apakah Anda yakin ingin menjalankan Playbook #${id}? Tindakan ini akan dieksekusi oleh AI Engine.`, async () => {
            Modal.close();
            try {
              const res = await DataService.fetch('/api/playbooks/' + id + '/execute', {
                method: 'POST',
                body: JSON.stringify({ dry_run: dryRun })
              });
              if (res && res.status === 'success') {
                Notify.toast('✅ Executed', res.message || 'Playbook executed successfully', 'ok');
                this.load();
              } else {
                Notify.toast('❌ Failed', (res && res.message) || 'Failed to execute playbook', 'err');
              }
            } catch (err) {
              Notify.toast('❌ Error', err.message, 'err');
            }
          });
        },

        openEditor(id = null) {
          let p = { name: '', description: '', script: '', target_layer: 1 };
          if (id && this._data) {
            p = this._data.find(x => x.playbook_id === id) || p;
          }

          const html = `
        <div style="display:flex;flex-direction:column;gap:12px;padding:8px">
          <div><label class="inp-label">Playbook Name</label><input class="inp w-100" id="pb-name" value="${p.name}" placeholder="e.g. Restart Postgres DB"></div>
          <div><label class="inp-label">Description</label><input class="inp w-100" id="pb-desc" value="${p.description}" placeholder="e.g. SOP to recover from deadlock"></div>
          <div style="display:flex;gap:12px">
            <div style="flex:1"><label class="inp-label">Target OSI Layer</label><input class="inp w-100" type="number" id="pb-layer" value="${p.target_layer}" min="1" max="7"></div>
          </div>
          <div>
             <label class="inp-label">Shell Script / Instructions</label>
             <textarea class="inp w-100" id="pb-script" style="height:150px;font-family:monospace;font-size:12px">${p.script}</textarea>
          </div>
        </div>
      `;

          Modal.show(id ? 'Edit Playbook #' + id : 'New Playbook', html, [
            { label: 'Cancel', cls: 'btn-ghost', fn: () => Modal.close() },
            {
              label: 'Save Playbook', cls: 'btn-primary', fn: async () => {
                const req = {
                  playbook_id: id || 0,
                  name: document.getElementById('pb-name').value,
                  description: document.getElementById('pb-desc').value,
                  target_layer: parseInt(document.getElementById('pb-layer').value) || 1,
                  script: document.getElementById('pb-script').value
                };

                try {
                  const res = await DataService.fetch('/api/playbooks', {
                    method: 'POST',
                    body: JSON.stringify(req)
                  });
                  if (res && res.status === 'success') {
                    Notify.toast('✅ Success', 'Playbook saved successfully', 'ok');
                    Modal.close();
                    this.load();
                  } else {
                    Notify.toast('❌ Error', (res && res.message) || 'Failed to save', 'err');
                  }
                } catch (err) {
                  Notify.toast('❌ Error', err.message, 'err');
                }
              }
            }
          ], '📝');
        },

        edit(id) {
          this.openEditor(id);
        },

        delete(id) {
          Modal.confirm('🗑️ Delete Playbook', 'Are you sure you want to delete this playbook?', async () => {
            Modal.close();
            try {
              const res = await DataService.fetch('/api/playbooks/' + id, { method: 'DELETE' });
              if (res && res.status === 'success') {
                Notify.toast('✅ Deleted', 'Playbook has been removed', 'ok');
                this.load();
              } else {
                Notify.toast('❌ Error', (res && res.message) || 'Failed to delete playbook', 'err');
              }
            } catch (err) {
              Notify.toast('❌ Error', err.message, 'err');
            }
          });
        }
      },

      /* ---- MODELS CONFIG ---- */

});
