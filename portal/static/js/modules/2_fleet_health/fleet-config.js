/* modules/2_fleet_health/fleet-config.js
 * Atomic Design — 3. Modules Layer (2_fleet_health / fleet-config)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      fleet_config: {
        _versions: [],

        _esc(s) {
          if (typeof _esc === 'function') return _esc(s);
          return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        },

        _authHeaders() {
          const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || '';
          const h = { 'Accept': 'application/json', 'Content-Type': 'application/json' };
          if (token) {
            h['Authorization'] = 'Bearer ' + token;
            h['X-CSRF-Token'] = token;
          }
          return h;
        },

        async load() {
          try {
            const ds = window.Services.Data || DataService;
            const [data, verResp] = await Promise.all([
              ds.fetch('/api/fleet/config/global'),
              ds.fetch('/api/fleet/config/versions').catch(() => null)
            ]);
            if (!data) throw new Error('Network fail');

            const editor = document.getElementById('fleet-global-config-editor');
            if (editor) {
              editor.value = JSON.stringify(data, null, 2);
            }
            this._syncFormFromObj(data);
            this._setValidationState(true, '');

            if (verResp && Array.isArray(verResp.versions)) {
              this._versions = verResp.versions;
              this._renderVersions(verResp.versions);
            }
          } catch (err) {
            Notify.toast('❌ Error', 'Failed to load fleet global configuration', 'err');
            console.error(err);
          }
        },

        _syncFormFromObj(obj) {
          if (!obj || typeof obj !== 'object') return;
          const setVal = (id, v) => {
            const el = document.getElementById(id);
            if (el && v !== undefined && v !== null) el.value = v;
          };
          setVal('fc-q-recovery', obj.recovery_mode || 'HITL');
          setVal('fc-q-interval', obj.check_interval);
          setVal('fc-q-latency', obj.latency_threshold);
          setVal('fc-q-pktloss', obj.packet_loss_threshold);
          setVal('fc-q-conf', obj.confidence_threshold);
          setVal('fc-q-printer', obj.printer_queue_threshold);
        },

        syncFromForm() {
          const editor = document.getElementById('fleet-global-config-editor');
          if (!editor) return;
          try {
            const obj = JSON.parse(editor.value || '{}');
            const gVal = (id) => document.getElementById(id)?.value;
            const gNum = (id, fallback) => {
              const v = parseFloat(gVal(id));
              return isNaN(v) ? fallback : v;
            };
            if (gVal('fc-q-recovery')) obj.recovery_mode = gVal('fc-q-recovery');
            obj.check_interval = Math.round(gNum('fc-q-interval', obj.check_interval || 300));
            obj.latency_threshold = Math.round(gNum('fc-q-latency', obj.latency_threshold || 200));
            obj.packet_loss_threshold = Math.round(gNum('fc-q-pktloss', obj.packet_loss_threshold || 20));
            obj.confidence_threshold = gNum('fc-q-conf', obj.confidence_threshold || 0.75);
            obj.printer_queue_threshold = Math.round(gNum('fc-q-printer', obj.printer_queue_threshold || 10));

            editor.value = JSON.stringify(obj, null, 2);
            this._setValidationState(true, '');
          } catch (e) {
            // Keep manual JSON error visible until user fixes syntax
          }
        },

        onEditorInput() {
          const editor = document.getElementById('fleet-global-config-editor');
          if (!editor) return;
          try {
            const parsed = JSON.parse(editor.value);
            this._setValidationState(true, '');
            this._syncFormFromObj(parsed);
          } catch (e) {
            this._setValidationState(false, e.message);
          }
        },

        _setValidationState(isValid, errMsg) {
          const badge = document.getElementById('fc-json-status');
          const errEl = document.getElementById('fc-json-error');
          if (badge) {
            badge.textContent = isValid ? 'JSON Valid' : 'Syntax Error';
            badge.className = 'tag ' + (isValid ? 'tag-green' : 'tag-red');
          }
          if (errEl) {
            if (isValid || !errMsg) {
              errEl.style.display = 'none';
              errEl.textContent = '';
            } else {
              errEl.style.display = 'block';
              errEl.textContent = '⚠ JSON Syntax Error: ' + errMsg;
            }
          }
        },

        formatJSON() {
          const editor = document.getElementById('fleet-global-config-editor');
          if (!editor) return;
          try {
            const parsed = JSON.parse(editor.value);
            editor.value = JSON.stringify(parsed, null, 2);
            this._setValidationState(true, '');
            Notify.toast('✨ Formatted', 'JSON berhasil dirapikan', 'ok', 1500);
          } catch (e) {
            this._setValidationState(false, e.message);
            Notify.toast('❌ Format Error', 'JSON belum valid: ' + e.message, 'warn');
          }
        },

        _renderVersions(versions) {
          const tbody = document.getElementById('fc-versions-tbody');
          const verBadge = document.getElementById('fc-active-ver');
          const countEl = document.getElementById('fc-ver-count');
          const activeVer = versions.find(v => v.is_active);
          if (verBadge) {
            verBadge.textContent = activeVer ? `Active: v${activeVer.version_number}` : 'Active: —';
          }
          if (countEl) {
            countEl.textContent = versions.length + ' versi';
          }
          if (!tbody) return;
          if (versions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:14px;color:var(--txt3)">Belum ada riwayat versi tersimpan</td></tr>';
            return;
          }
          tbody.innerHTML = versions.map(v => {
            const dt = v.created_at ? new Date(v.created_at) : null;
            const timeStr = (dt && !isNaN(dt.getTime()))
              ? dt.toLocaleString('id-ID', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
              : '—';
            const badge = v.is_active
              ? '<span class="tag tag-green">● ACTIVE</span>'
              : '<span class="tag tag-gray">ARCHIVED</span>';
            return `<tr>
              <td><b style="color:var(--cyan)">v${this._esc(v.version_number)}</b></td>
              <td>${badge}</td>
              <td style="font-size:11px;color:var(--txt2)">${this._esc(v.description || 'Configuration Snapshot')}</td>
              <td style="font-size:10.5px;color:var(--txt3)">${this._esc(timeStr)}</td>
              <td style="text-align:right">
                ${v.is_active
                  ? '<span style="font-size:10px;color:var(--green2)">Sedang Aktif</span>'
                  : `<button class="btn btn-ghost btn-xs" onclick="Panels.fleet_config.rollback(${Number(v.version_number)})"><i class="fa-solid fa-rotate-left" style="margin-right:4px"></i>Rollback ke v${Number(v.version_number)}</button>`
                }
              </td>
            </tr>`;
          }).join('');
        },

        async rollback(versionNumber) {
          Modal.confirm(
            '↩ Rollback Konfigurasi',
            `Aktifkan kembali Fleet Global Configuration versi <b>v${Number(versionNumber)}</b> dan broadcast ke seluruh agen?`,
            async () => {
              Modal.close();
              try {
                const resp = await fetch('/api/fleet/config/rollback', {
                  method: 'POST',
                  headers: this._authHeaders(),
                  body: JSON.stringify({ version_number: Number(versionNumber) })
                });
                const json = await resp.json();
                if (resp.ok && json.status === 'success') {
                  Notify.toast('✅ Rollback Berhasil', json.message, 'ok');
                  if (typeof LogStreamer !== 'undefined' && LogStreamer.add) {
                    LogStreamer.add('WARN', 'CONFIG', `Fleet Global Config rolled back to v${versionNumber}`);
                  }
                  await this.load();
                } else {
                  Notify.toast('❌ Rollback Gagal', json.message || 'Gagal melakukan rollback', 'err');
                }
              } catch (e) {
                Notify.toast('❌ Error', 'Koneksi ke server gagal: ' + e.message, 'err');
              }
            }
          );
        },

        async save() {
          const editor = document.getElementById('fleet-global-config-editor');
          if (!editor) return;
          let parsed;
          try {
            parsed = JSON.parse(editor.value);
            this._setValidationState(true, '');
          } catch (err) {
            this._setValidationState(false, err.message);
            Notify.toast('❌ Format Error', 'Invalid JSON format: ' + err.message, 'warn');
            return;
          }

          const desc = (document.getElementById('fc-commit-desc')?.value || '').trim();
          try {
            const resp = await fetch('/api/fleet/config/global', {
              method: 'POST',
              headers: this._authHeaders(),
              body: JSON.stringify({ config: parsed, description: desc })
            });
            const json = await resp.json();
            if (resp.ok && json.status === 'success') {
              Notify.toast('✅ Deployed', json.message || 'Config saved & broadcasted', 'ok');
              if (typeof LogStreamer !== 'undefined' && LogStreamer.add) {
                LogStreamer.add('OK', 'CONFIG', json.message || 'Fleet Global Config updated');
              }
              const descEl = document.getElementById('fc-commit-desc');
              if (descEl) descEl.value = '';
              await this.load();
            } else {
              Notify.toast('❌ Error', (json && json.message) || 'Failed to save configuration', 'err');
            }
          } catch (err) {
            Notify.toast('❌ Error', 'Network error: ' + err.message, 'err');
          }
        }
      },

      /* ---- STORAGE ---- */

});

window.Modules["2_fleet_health"]["fleet-config"] = window.Panels;
