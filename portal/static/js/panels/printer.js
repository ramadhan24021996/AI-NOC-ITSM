/* panels/printer.js
 * Printer Status panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      printer: {
        async load() {
          if (window.PrinterMgr && window.PrinterMgr.load) {
            window.PrinterMgr.load();
          }
          if (!window.ActiveIntervals.printer) {
            window.ActiveIntervals.printer = setInterval(() => {
              if (window.PrinterMgr && window.PrinterMgr.load) {
                window.PrinterMgr.load();
              }
            }, 30000);
          }
        },
        toggleSitePartition(partKey) {
          if (window.PrinterMgr && window.PrinterMgr.toggleSitePartition) {
            window.PrinterMgr.toggleSitePartition(partKey);
          }
        }
      },

});

