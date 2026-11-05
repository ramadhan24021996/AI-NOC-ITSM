/* panels/nats-subjects.js
 * NATS Subjects panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      nats_subjects: {
        _data: null,
        async load() {
          const tbody = document.getElementById('nats-subjects-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--cyan);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat NATS Subjects...</div></td></tr>';

          try {
            const res = await DataService.loadNatsSubjects();
            if (!res) {
              if (document.getElementById('nats-subj-status')) {
                const el = document.getElementById('nats-subj-status');
                el.innerText = 'RECHECKING';
                el.style.color = 'var(--orange)';
              }
              tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--orange)"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px"></i>Gagal memuat telemetri NATS. Sesi token Anda mungkin telah diperbarui. Silakan muat ulang halaman (F5).</td></tr>';
              return;
            }
            this._data = res;

            if (res) {
              const subjects = res.subjects || [];
              const status = res.nats_status || 'OFFLINE';
              const server = res.server_url || 'nats://nats:4222';
              const rtt = res.rtt_ms !== undefined ? (res.rtt_ms < 1 ? '< 1.0 ms' : res.rtt_ms.toFixed(1) + ' ms') : '< 1.0 ms';

              if (document.getElementById('nats-subj-total')) { const _el = document.getElementById('nats-subj-total'); if (_el) _el.innerText = subjects.length; }
              if (document.getElementById('nats-subj-status')) {
                const el = document.getElementById('nats-subj-status');
                el.innerText = status;
                el.style.color = status === 'CONNECTED' ? 'var(--green)' : 'var(--red)';
              }
              if (document.getElementById('nats-subj-server')) { const _el = document.getElementById('nats-subj-server'); if (_el) _el.innerText = server; }
              if (document.getElementById('nats-subj-rtt')) { const _el = document.getElementById('nats-subj-rtt'); if (_el) _el.innerText = rtt; }

              const uniqueRoles = new Set(subjects.map(s => s.role)).size;
              if (document.getElementById('nats-subj-roles')) { const _el = document.getElementById('nats-subj-roles'); if (_el) _el.innerText = uniqueRoles + ' Roles'; }
            }

            this.render();
          } catch (err) {
            console.error("Failed to load NATS subjects:", err);
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat NATS subjects: ${err.message}</td></tr>`;
          }
        },

        render() {
          const tbody = document.getElementById('nats-subjects-tbody');
          if (!tbody || !this._data) return;

          const searchVal = (document.getElementById('nats-subj-search') ? document.getElementById('nats-subj-search').value : '').toLowerCase().trim();
          const filterVal = document.getElementById('nats-subj-filter') ? document.getElementById('nats-subj-filter').value : '';

          const subjects = (this._data.subjects || []).filter(s => {
            if (filterVal && s.nats_status !== filterVal) return false;
            if (searchVal) {
              const subj = (s.subject || '').toLowerCase();
              const role = (s.role || '').toLowerCase();
              const mode = (s.mode || '').toLowerCase();
              if (!subj.includes(searchVal) && !role.includes(searchVal) && !mode.includes(searchVal)) return false;
            }
            return true;
          });

          if (subjects.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Tidak Ada NATS Subject Ditemukan</td></tr>';
            return;
          }

          tbody.innerHTML = subjects.map(s => {
            const st = s.nats_status || 'CONNECTED';
            const badgeCls = st === 'CONNECTED' ? 'bd-gr' : 'bd-rd';
            const rttText = s.rtt_ms !== undefined ? (s.rtt_ms < 1 ? '< 1.0 ms' : s.rtt_ms.toFixed(1) + ' ms') : '< 1.0 ms';
            const modeBadge = s.mode === 'Wildcard Queue' ? 'bd-purple' : s.mode === 'Stream Ingest' ? 'bd-or' : 'bd-bl';

            return `<tr>
              <td><code style="color:var(--cyan);font-weight:600;font-size:11.5px"><i class="fa-solid fa-network-wired" style="margin-right:6px;font-size:10px"></i>${s.subject}</code></td>
              <td><b>${s.role}</b></td>
              <td><span class="badge ${modeBadge}" style="font-size:10px">${s.mode || 'Pub/Sub'}</span></td>
              <td><span style="font-family:monospace;font-size:11px;color:var(--cyan)">${rttText}</span></td>
              <td><span class="badge ${badgeCls}" style="font-size:10px">${st}</span></td>
            </tr>`;
          }).join('');
        }
      },

      /* ---- GOVERNANCE ---- */

});