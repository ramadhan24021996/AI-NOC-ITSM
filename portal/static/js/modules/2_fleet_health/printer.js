/* modules/2_fleet_health/printer.js
 * Atomic Design — 3. Modules Layer (2_fleet_health / printer)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      printer: {
        async load() {
          if (window.PrinterMgr && window.PrinterMgr.load) {
            await window.PrinterMgr.load();
          }
        },
        toggleSitePartition(partKey) {
          if (window.PrinterMgr && window.PrinterMgr.toggleSitePartition) {
            window.PrinterMgr.toggleSitePartition(partKey);
          }
        }
      },

});


window.Modules["2_fleet_health"]["printer"] = window.Panels;
