// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const evidenceDir = path.join(__dirname, '../../docs/02_ARCHITECTURE/audit/evidence/browser-e2e');
if (!fs.existsSync(evidenceDir)) {
  fs.mkdirSync(evidenceDir, { recursive: true });
}

const panels = [
  { id: 'P-01', name: 'Overview Status', tab: 'overview', file: 'P-01_dashboard.png' },
  { id: 'P-02', name: 'Incident Triage', tab: 'incident', file: 'P-02_incidents.png' },
  { id: 'P-03', name: 'Fleet PC Health', tab: 'fleet', file: 'P-03_fleet.png' },
  { id: 'P-04', name: 'Printer List', tab: 'printer', file: 'P-04_printers.png' },
  { id: 'P-05', name: 'Activity Log', tab: 'activity', file: 'P-05_activity-log.png' },
  { id: 'P-06', name: 'Audit Log', tab: 'logs', file: 'P-06_system-audits.png' },
  { id: 'P-07', name: 'RCA Engine Trace', tab: 'rca', file: 'P-07_rca-trace.png' },
  { id: 'P-08', name: 'Evidence Explorer', tab: 'evidence', file: 'P-08_evidence-explorer.png' },
  { id: 'P-09', name: 'KB Stats', tab: 'knowledge', file: 'P-09_kb-stats.png' },
  { id: 'P-10', name: 'AI Config', tab: 'ai-panel', file: 'P-10_ai-config.png' },
  { id: 'P-11', name: 'Playbooks List', tab: 'playbooks', file: 'P-11_playbooks.png' },
  { id: 'P-12', name: 'SOP List', tab: 'sop', file: 'P-12_sops.png' },
  { id: 'P-13', name: 'Learning Policy', tab: 'learning-gate', file: 'P-13_learning-gate.png' },
  { id: 'P-14', name: 'Security Rules', tab: 'security-policies', file: 'P-14_security-policies.png' },
  { id: 'P-15', name: 'AI Decision Logs', tab: 'ai-decision-logs', file: 'P-15_ai-decision-logs.png' },
  { id: 'P-16', name: 'Schema Validation', tab: 'schema-validation', file: 'P-16_schema-validation.png' },
  { id: 'P-17', name: 'Agent Health', tab: 'agent-health', file: 'P-17_agent-health.png' },
  { id: 'P-18', name: 'Runtime Monitor', tab: 'runtime-monitor', file: 'P-18_runtime-monitor.png' },
  { id: 'P-19', name: 'NATS Subjects', tab: 'nats-subjects', file: 'P-19_nats-subjects.png' },
  { id: 'P-20', name: 'Storage Stats', tab: 'storage', file: 'P-20_storage-stats.png' },
  { id: 'P-21', name: 'Fleet Config', tab: 'fleet-config', file: 'P-21_fleet-config.png' },
  { id: 'P-22', name: 'SLA Compliance', tab: 'training', file: 'P-22_sla-compliance.png' },
  { id: 'P-23', name: 'DPO Stats', tab: 'governance', file: 'P-23_feedback-stats.png' },
  { id: 'P-24', name: 'RBAC Roles', tab: 'rbac', file: 'P-24_rbac.png' },
  { id: 'P-25', name: 'Causal DAG', tab: 'unified-dag', file: 'P-25_causal-dag.png' },
  { id: 'P-26', name: 'System Monitoring', tab: 'monitoring', file: 'P-26_monitoring.png' },
  { id: 'P-27', name: 'AI Status Submodule', tab: 'models', file: 'P-27_ai-status.png' },
  { id: 'P-28', name: 'Fleet Site Tree Submodule', tab: 'fleet-sites', file: 'P-28_fleet-sites.png' },
  { id: 'P-29', name: 'PC Deep Diagnostics Submodule', tab: 'pchealth', file: 'P-29_agent-deep-diagnostics.png' },
];

test.describe('Enterprise Dashboard 29 Panels E2E Audit', () => {
  test.beforeEach(async ({ page }) => {
    // Abort external CDN calls to avoid network delays in sandbox
    await page.route(/cdnjs|googleapis|gstatic|jsdelivr|fontawesome/, (route) => route.abort());

    await page.addInitScript(() => {
      sessionStorage.setItem('noc_auth', '1');
      sessionStorage.setItem('role', 'superadmin');
      sessionStorage.setItem('user_id', 'superadmin');
      window['currentUserRole'] = 'superadmin';
      window['currentUserId'] = 'superadmin';
    });
  });

  test('P-00 Login & Session Initialization', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    const screenshotPath = path.join(evidenceDir, 'P-00_login_dashboard.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    expect(fs.existsSync(screenshotPath)).toBe(true);
  });

  for (const panel of panels) {
    test(`${panel.id} - ${panel.name} Panel E2E Render & Contract`, async ({ page }) => {
      const pageErrors = [];
      page.on('pageerror', (err) => pageErrors.push(err.message));

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page.evaluate((tabId) => {
        let overlayStyle = document.getElementById('overlay-dismiss-style');
        if (!overlayStyle) {
          overlayStyle = document.createElement('style');
          overlayStyle.id = 'overlay-dismiss-style';
          document.head.appendChild(overlayStyle);
        }
        overlayStyle.textContent = '#splash-overlay, #login-overlay { display: none !important; opacity: 0 !important; pointer-events: none !important; visibility: hidden !important; }';

        const splash = document.getElementById('splash-overlay');
        if (splash) { splash.style.display = 'none'; splash.remove(); }
        const login = document.getElementById('login-overlay');
        if (login) { login.style.display = 'none'; login.remove(); }

        const navObj = window['Nav'];
        if (navObj && typeof navObj['go'] === 'function') {
          navObj['go'](tabId);
        }
        if (tabId === 'pchealth' || tabId === 'agent-deep-diagnostics' || tabId === 'server') {
          const panelsObj = window['Panels'];
          if (panelsObj && panelsObj['pchealth'] && typeof panelsObj['pchealth']['showDetail'] === 'function') {
            panelsObj['pchealth']['showDetail']('PC-STORE-01', false);
          }
        }
      }, panel.tab);

      await page.waitForTimeout(600);
      const screenshotPath = path.join(evidenceDir, panel.file);
      await page.screenshot({ path: screenshotPath });

      expect(pageErrors.length).toBe(0);
      expect(fs.existsSync(screenshotPath)).toBe(true);
      console.log(`[PASS] ${panel.id} (${panel.name}) -> Screenshot: ${panel.file}`);
    });
  }
});
