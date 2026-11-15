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
        async load() {
          try {
            const data = await (window.Services.Data || DataService).fetch('/api/fleet/config/global');
            if (!data) throw new Error('Network fail');
            const editor = document.getElementById('fleet-global-config-editor');
            if (editor) {
              editor.value = JSON.stringify(data, null, 2);
            }
          } catch (err) {
            Notify.toast('❌ Error', 'Failed to load fleet global configuration', 'err');
            console.error(err);
          }
        },
        async save() {
          const editor = document.getElementById('fleet-global-config-editor');
          if (!editor) return;
          try {
            const payload = JSON.parse(editor.value);
            const json = await (window.Services.Data || DataService).fetch('/api/fleet/config/global', {
              method: 'POST',
              body: JSON.stringify(payload)
            });
            if (json && json.status === 'success') {
              Notify.toast('✅ Deployed', json.message || 'Config saved', 'ok');
              this.load();
            } else {
              Notify.toast('❌ Error', (json && json.message) || 'Failed to save configuration', 'err');
            }
          } catch (err) {
            Notify.toast('❌ Format Error', 'Invalid JSON format: ' + err.message, 'warn');
          }
        }
      },

      /* ---- STORAGE ---- */

});

window.Modules["2_fleet_health"]["fleet-config"] = window.Panels;
