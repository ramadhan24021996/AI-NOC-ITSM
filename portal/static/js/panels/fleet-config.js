/* panels/fleet-config.js
 * Fleet Global Config panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      fleet_config: {
        async load() {
          try {
            const data = await DataService.fetch('/api/fleet/config/global');
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
            const json = await DataService.fetch('/api/fleet/config/global', {
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
