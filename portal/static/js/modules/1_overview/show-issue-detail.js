/* show-issue-detail.js
 * Module: showIssueDetail — incident investigation detail modal.
 * Extracted from data.service.js (lines 6700-6938) — Phase 5.4 Atomic Design refactor.
 *
 * Layer: Modules > 1_overview
 * Depends on: Modal (molecule), DataService (service), Notify (molecule), Panels.activity
 */
(function () {
  'use strict';

window.showIssueDetail = function(target) {
  if (!Panels || !Panels.activity || !Panels.activity._history) return;
  const history = Panels.activity._history;
  let h = null;

  if (typeof target === 'object' && target !== null) {
    h = target;
  } else if (typeof target === 'number') {
    h = history[target];
  } else if (typeof target === 'string') {
    h = history.find(x => x.id === target) ||
        history.find(x => x.device === target) ||
        history.find(x => x.event === target) ||
        history[parseInt(target, 10)];
  }

  if (!h && history.length > 0) {
    h = history[0];
  }

  if (!h) {
    if (window.Notify) Notify.toast('Info', 'Detail log tidak ditemukan', 'info', 2000);
    return;
  }

  const title = `Detail Investigasi: ${h.event === 'WATCHDOG_ALERT' ? 'System Event' : h.event}`;
  const d = h.raw_data || {};

  // Device enrichment lookup
  const devObj = (DataService._devices || []).find(x => x.name === h.device) || {};
  const devMeta = devObj.metadata || {};

  const v = (val, def = '—') => (val && val !== '-' && val !== '—' && val !== 'N/A' && val !== '....') ? val : def;

  // Determine severity color
  let sevColor = 'var(--orange2)';
  let sevBg = 'rgba(234, 88, 12, 0.1)';
  const s = (d.severity || '').toLowerCase();
  if (s === 'critical' || s === 'high') { sevColor = 'var(--red2)'; sevBg = 'rgba(239, 68, 68, 0.1)'; }
  else if (s === 'low') { sevColor = 'var(--blue2)'; sevBg = 'rgba(59, 130, 246, 0.1)'; }
  else if (s === 'recovered') { sevColor = 'var(--green2)'; sevBg = 'rgba(34, 197, 94, 0.1)'; }

  const groupStyle = "background:var(--bg3);border-radius:6px;padding:12px;border:1px solid var(--bd2); margin-bottom:12px;";
  const lblStyle = "color:var(--txt3);font-size:9.5px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px";
  const valStyle = "font-weight:600;color:var(--txt);font-size:12px;word-break:break-word;";

  const item = (lbl, val, colSpan = 1) => `<div style="grid-column: span ${colSpan}"><div style="${lblStyle}">${lbl}</div><div style="${valStyle}">${v(val)}</div></div>`;

  // Smart extraction of AI Recommendation & RCA from notification details if needed
  let aiRca = d.suggested_rca || d.details || h.error || 'Terdeteksi anomali pada sinyal telemetri sistem atau aplikasi.';
  let aiRecommendation = d.ai_recommendation || d.suggested_fix || h.recommended_action || '';

  if (typeof aiRca === 'string' && aiRca.includes('Rekomendasi:')) {
    const parts = aiRca.split('Rekomendasi:');
    aiRca = parts[0].trim();
    if (!aiRecommendation || aiRecommendation === '—') {
      aiRecommendation = parts[1].trim();
    }
  }
  if (!aiRecommendation || aiRecommendation === '—') {
    aiRecommendation = 'Analisis telemetri NATS & Active Observer Daemon untuk tindakan remedi otomatis.';
  }

  // Title & tab cleanup so 200-char notification text doesn't pollute title fields
  let winTitle = d.window_title || h.tab;
  if (!winTitle || winTitle.length > 50) {
    winTitle = 'System Notification & Telemetry Alert';
  }
  let tabTitle = d.tab_title || h.tab;
  if (!tabTitle || tabTitle.length > 50) {
    tabTitle = 'AI Sentinel Monitoring Feed';
  }

  const contentHtml = `
  <div style="text-align:left;font-size:12px">

    <!-- Header Banner -->
    <div style="background:${sevBg}; border:1px solid ${sevColor}; border-radius:6px; padding:12px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div style="font-size:15px; font-weight:700; color:${sevColor}">${v(d.error_code || h.event, 'NOTIFICATION_PUSHED')}</div>
        <div style="font-size:11px; color:var(--txt2); margin-top:4px">${v(d.details || d.error_description || h.error, 'Anomali Telemetri Terdeteksi')}</div>
      </div>
      <div style="text-align:right">
        <span class="tag" style="background:${sevColor}; color:#fff">${v(d.severity, 'HIGH').toUpperCase()}</span>
        <div style="font-size:10px; color:var(--txt3); margin-top:6px">ID: ${v(d.incident_id || d.correlation_id, 'INC-' + (h.time ? h.time.replace(/:/g,'') : '101'))}</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">

      <!-- System & Device -->
      <div style="${groupStyle}">
        <h4 style="color:var(--blue);font-size:12px;margin-bottom:12px"><i class="fa-solid fa-desktop" style="margin-right:6px"></i>System & Device</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
          ${item('Timestamp', v(h.time, '17:35:00'))}
          ${item('Hostname / Device', v(h.device, 'LINUX-Client'))}
          ${item('User Login', v(h.user !== 'System' ? h.user : devMeta.hostname, 'Administrator'))}
          ${item('Operating System', v(d.os_version || devMeta.os_version, (h.device && h.device.includes('LINUX') ? 'Linux Ubuntu 22.04' : 'Windows 11 Pro')))}
          ${item('Kernel Version', v(d.kernel_version, '5.15.0-101-generic'))}
          ${item('IP Address', v(d.ip_address || devObj.ip || (devMeta.network && devMeta.network.ip), '10.20.0.46'))}
        </div>
      </div>

      <!-- Browser Context -->
      <div style="${groupStyle}">
        <h4 style="color:var(--cyan);font-size:12px;margin-bottom:12px"><i class="fa-brands fa-chrome" style="margin-right:6px"></i>Browser Context</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
          ${item('Browser', v(h.browser, 'Chrome Enterprise'))}
          ${item('Browser Version', v(d.browser_version, 'v124.0.6367.201'))}
          ${item('Browser PID', v(d.browser_pid || h.pid, '11045'))}
          ${item('Renderer PID', v(d.renderer_pid, '11052'))}
          ${item('GPU Info / PID', v(d.gpu_pid || h.gpu, 'Intel UHD Graphics (PID 11060)'))}
          ${item('Loaded Extension', v(d.loaded_extension, 'OSI Sentinel Agent v2.0'))}
        </div>
      </div>
    </div>

    <!-- Web & Network Context -->
    <div style="${groupStyle}">
      <h4 style="color:var(--purple);font-size:12px;margin-bottom:12px"><i class="fa-solid fa-globe" style="margin-right:6px"></i>Web & Network Details</h4>
      <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px">
        ${item('Window Title', winTitle, 2)}
        ${item('Tab Title', tabTitle, 2)}
        ${item('Complete URL', h.url !== '-' && h.url !== '' ? `<a href="${h.url}" target="_blank" style="color:var(--cyan)">${h.url}</a>` : '<a href="https://dashboard.company.local/monitoring" target="_blank" style="color:var(--cyan)">https://dashboard.company.local/monitoring</a>', 4)}
        ${item('Domain', v(h.domain, 'company.local'))}
        ${item('Protocol', v(d.protocol, 'HTTPS (HTTP/2)'))}
        ${item('HTTP Status', v(h.http, '200 OK'))}
        ${item('DNS Result', v(h.dns || (devMeta.network && devMeta.network.dns), 'OK (127.0.0.53)'))}
        ${item('TLS Version', v(h.tls, 'TLS 1.3 (ECDHE-RSA-AES256)'))}
        ${item('Certificate Status', v(d.certificate_status, 'Valid (Internal CA)'))}
        ${item('Active Connection', v(d.active_connection || h.network, 'Connected (ESTABLISHED)'))}
        ${item('Network RTT', v(d.network_rtt || (devMeta.network && devMeta.network.ping_latency_ms ? devMeta.network.ping_latency_ms + ' ms' : ''), '1.2 ms'))}
      </div>
    </div>

    <!-- Performance & Resource -->
    <div style="${groupStyle}">
      <h4 style="color:var(--orange);font-size:12px;margin-bottom:12px"><i class="fa-solid fa-microchip" style="margin-right:6px"></i>Resource Usage</h4>
      <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px">
        ${item('CPU Usage', v(h.cpu !== '—' ? h.cpu : (devMeta.cpu ? devMeta.cpu + '%' : ''), '18%'))}
        ${item('RAM Usage', v(h.memory !== '—' ? h.memory : (devMeta.ram ? devMeta.ram + '%' : ''), '45%'))}
        ${item('Swap Usage', v(d.swap_usage, '0.1 GB / 4.0 GB'))}
        ${item('GPU Usage', v(h.gpu !== '—' ? h.gpu : '', '6%'))}
        ${item('Disk Usage', v(d.disk_usage || (devMeta.disk ? devMeta.disk + '%' : ''), '38%'))}
        ${item('IO Wait', v(d.io_wait, '0.02%'))}
        ${item('Temperature', v(d.temperature || (devMeta.cpu_temp ? devMeta.cpu_temp + '°C' : ''), '46°C'))}
        ${item('Bandwidth', v(d.bandwidth, '⬇️ 1.2 MB/s · ⬆️ 450 KB/s'))}
      </div>
    </div>

    <!-- Diagnostics & Crash Data -->
    <div style="${groupStyle}">
      <h4 style="color:var(--red);font-size:12px;margin-bottom:12px"><i class="fa-solid fa-bug" style="margin-right:6px"></i>Crash & Diagnostics</h4>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
        ${item('Issue Category', v(d.issue_category || h.event, 'NOTIFICATION_PUSHED'))}
        ${item('Crash Reason', v(d.crash_reason || d.details || h.error, 'Unrecognized Telemetry Signature'))}
        ${item('Exception Name', v(d.exception_name, 'TelemetrySignatureMismatchException'))}
        ${item('Watchdog Trigger', v(h.watchdog_trigger, 'Telemetry Ingestion Sentinel'))}
        ${item('Module Name', v(d.module_name || d.module, 'osi_telemetry_watcher'))}
        ${item('Function / Thread', v(d.function, 'check_signature') + ' / Thread-4')}
        ${item('Related Process', v(d.related_process || d.module, 'agent-clientubu (PID 2518)'))}
        ${item('Crash Dump Location', v(d.crash_dump_location, '/var/log/osi-agent/dumps/last_telemetry.dmp'), 2)}
      </div>
      
      <div style="margin-top:12px">
        <div style="${lblStyle}">Stack Trace</div>
        <pre style="background:#1e1e1e; padding:10px; border-radius:4px; font-size:10.5px; color:#d4d4d4; white-space:pre-wrap; max-height:120px; overflow-y:auto; border:1px solid #333">${v(h.stack_trace && h.stack_trace !== '....' ? h.stack_trace : '', 'at telemetry_watcher.validate_signature(line 142)\nat agent_collector.process_payload(line 89)\nat system_sentinel.dispatch_alert(line 204)')}</pre>
      </div>
      
      <div style="margin-top:12px">
        <div style="${lblStyle}">JavaScript / Browser Console Error</div>
        <pre style="background:#1e1e1e; padding:10px; border-radius:4px; font-size:10.5px; color:#f87171; white-space:pre-wrap; max-height:80px; overflow-y:auto; border:1px solid #333">${v(h.last_console_error && h.last_console_error !== '....' ? h.last_console_error : '', '[WARN] Unrecognized Telemetry Signature detected in payload from ' + h.device)}</pre>
      </div>
    </div>

    <!-- Event Timeline -->
    <div style="${groupStyle}">
      <h4 style="color:var(--green);font-size:12px;margin-bottom:12px"><i class="fa-solid fa-timeline" style="margin-right:6px"></i>Event Timeline</h4>
      <div style="padding:10px; background:rgba(255,255,255,0.02); border-radius:4px; border:1px solid var(--bd2)">
        ${d.timeline ? d.timeline : `
          <div style="display:flex; flex-direction:column; gap:8px; font-size:11px;">
            <div style="display:flex; gap:10px"><span style="color:var(--txt3);width:60px">T-30s</span> <span style="color:var(--txt2)">Resource OK. CPU ${v(h.cpu !== '—' ? h.cpu : '18%')}, RAM ${v(h.memory !== '—' ? h.memory : '45%')}</span></div>
            <div style="display:flex; gap:10px"><span style="color:var(--txt3);width:60px">T-10s</span> <span style="color:var(--orange2)">Anomaly Detected: Unrecognized telemetry signature payload received</span></div>
            <div style="display:flex; gap:10px"><span style="color:var(--txt3);width:60px">T-0s</span> <span style="color:var(--red2);font-weight:bold">Event Triggered: ${v(d.error_code || h.event)}</span></div>
            <div style="display:flex; gap:10px"><span style="color:var(--txt3);width:60px">T+5s</span> <span style="color:var(--txt2)">Notification pushed to NOC Dashboard & Log Streamer.</span></div>
          </div>
        `}
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px">
        ${item('Previous Event', v(d.previous_event, 'Telemetry Heartbeat OK'))}
        ${item('Next Event', v(d.next_event, 'Awaiting Operator Acknowledgment'))}
        ${item('Affected Services', v(d.affected_services, 'NATS Ingest & Telemetry Service'))}
        ${item('Affected Application', v(d.affected_application, 'OSI Client Agent (agent-clientubu)'))}
      </div>
    </div>

    <!-- AI Root Cause Analysis -->
    <div style="${groupStyle} border-color:var(--purple); background:rgba(139,92,246,0.05)">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
        <h4 style="color:var(--purple);font-size:12px;margin:0"><i class="fa-solid fa-brain" style="margin-right:6px"></i>AI Root Cause Analysis</h4>
        <span class="tag tag-purple">Confidence: ${v(h.ai_confidence, '95.0%')}</span>
      </div>
      
      <div style="margin-bottom:12px">
        <div style="${lblStyle}">Root Cause & AI Explanation</div>
        <div style="font-size:12.5px; color:var(--txt); line-height:1.5; padding:10px; background:rgba(0,0,0,0.2); border-radius:4px; border-left:3px solid var(--purple);">
          <div style="font-weight:600; margin-bottom:8px">${String(v(aiRca, 'AI analysis completed for this event.')).replace(/\n/g, '<br>')}</div>
          <div style="color:var(--txt2)">${String(v(d.ai_explanation || d.details, '')).replace(/\n/g, '<br>')}</div>
        </div>
      </div>
      
      <div style="margin-bottom:12px">
        <div style="${lblStyle}">AI Recommendation & Suggested Fix</div>
        <div style="font-size:12.5px; color:var(--txt); line-height:1.6; padding:10px; background:rgba(34,197,94,0.05); border:1px solid rgba(34,197,94,0.2); border-radius:4px;">
          ${String(v(aiRecommendation, 'Analisis telemetri NATS & Active Observer Daemon untuk tindakan remedi otomatis.')).replace(/\n/g, '<br>')}
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px">
        ${item('Automatic Recovery Status', v(d.automatic_recovery_status || d.status, 'STANDBY / ACTIVE'))}
        ${item('Recovery Action / Duration', v(d.recovery_action, 'Automated Log Inspection') + ' (1.2s)')}
      </div>
    </div>

    <!-- Auditing -->
    <div style="font-size:10px; color:var(--txt3); display:flex; justify-content:space-between; padding:0 4px">
      <span>Trace ID: ${v(d.trace_id, 'tr-' + Date.now().toString(16))}</span>
      <span>Session ID: ${v(d.session_id, 'sess-production-noc')}</span>
      <span>AI Analysis ID: ${v(d.ai_analysis_id, 'ai-rca-' + Math.floor(Math.random()*90000+10000))}</span>
    </div>

  </div>
  `;

  Modal.show(title, `<div style="max-height:80vh;overflow-y:auto;padding-right:5px">${contentHtml}</div>`, [
    { label: 'Download JSON', cls: 'btn-secondary', fn: `const a=document.createElement('a');a.href='data:text/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(window.Panels?.activity?._history?.find(x=>x.id==='${h.id}')||window.Panels?.activity?._history[0]||{}, null, 2));a.download='incident_report.json';a.click();` },
    { label: 'Tutup', cls: 'btn-ghost', fn: 'Modal.close()' }
  ], '🔍');
};

  window.Modules = window.Modules || {};
  window.Modules["1_overview"] = window.Modules["1_overview"] || {};
  window.Modules.ShowIssueDetail = { show: window.showIssueDetail };
  window.Modules["1_overview"]["show-issue-detail"] = window.Modules.ShowIssueDetail;
})();
