/* show-device-diagnostics.js
 * Module: showDeviceDiagnosticsDetail — deep device diagnostics modal.
 * Extracted from data.service.js (lines 6940-7191) — Phase 5.4 Atomic Design refactor.
 *
 * Layer: Modules > 2_fleet_health
 * Depends on: Modal (molecule), DataService (service), Notify (molecule), BrowserMonitoring
 */
(function () {
  'use strict';

window.showDeviceDiagnosticsDetail = async function (name) {
  if (!name) return;
  const devices = (window.DataService && DataService._devices) ? DataService._devices : [];
  let d = devices.find(x => x.name === name);
  if (!d) {
    d = { name: name, status: 'ONLINE', cpu: 0, ram: 0, metadata: { hostname: name } };
  }

  const title = `Detail: ${name} ${d.status === 'ONLINE' ? '<span class="tag tag-green">ONLINE</span>' : '<span class="tag tag-orange">OFFLINE</span>'}`;

  const loadingHTML = `
<div style="text-align:center;padding:40px;color:var(--txt2)">
  <i class="fa-solid fa-spinner fa-spin" style="font-size:24px;margin-bottom:12px;color:var(--blue)"></i>
  <div>Menjalankan Deep Diagnostics pada ${name}...</div>
  <div style="font-size:11px;color:var(--txt3);margin-top:4px">Ini memerlukan waktu beberapa detik untuk mengumpulkan data jaringan, aplikasi, browser, dan printer.</div>
</div>
  `;

  Modal.show(title, `<div id="pc-detail-modal-body" style="max-height:70vh;overflow-y:auto;text-align:left;padding-right:5px;">${loadingHTML}</div>`, [{ label: 'Tutup', cls: 'btn-ghost', fn: 'Modal.close()' }], '🖥️');

  const body = document.getElementById('pc-detail-modal-body');
  if (!body) return;

  const meta = d.metadata || {};
  const baseItems = [
    { k: 'CPU Usage', v: (d.cpu !== undefined ? d.cpu : (d.cpu_usage !== undefined ? d.cpu_usage : 0)).toFixed(0) + '%' },
    { k: 'RAM Usage', v: (d.ram !== undefined ? d.ram : (d.ram_usage !== undefined ? d.ram_usage : 0)).toFixed(0) + '%' },
    { k: 'Disk Usage', v: (meta.disk_usage !== undefined ? meta.disk_usage : 0) + '%' },
    { k: 'CPU Temp', v: (meta.cpu_temp !== undefined ? meta.cpu_temp : 0) + '°C' },
    { k: 'Login User', v: meta.hostname || 'Unknown' },
    { k: 'OS Version', v: d.os_version || meta.os_version || 'Unknown' },
    { k: 'Uptime', v: meta.uptime || 'Unknown' }
  ];

  let itemsHtml = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:15px">' +
    baseItems.map(i => `<div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">${i.k}</div><div style="font-size:13px;font-weight:600;color:var(--txt);margin-top:3px">${i.v}</div></div>`).join('') +
    '</div>';

  try {
    const resp = await DataService.fetch('/api/agent_deep_diagnostics/' + encodeURIComponent(name), {
      signal: AbortSignal.timeout(50000)
    });

    if (!resp || resp.error || !resp.agent_data) {
      throw new Error((resp && resp.error) || 'Gagal terhubung ke agent atau agent offline.');
    }

    const diag = resp.agent_data;
    const net = diag.network_advanced || {};

    // 1. Build Network Monitoring section
    let netHtml = `
  <div class="card-sec" style="margin-top:15px">
    <h4 style="margin-bottom:8px;color:var(--blue);font-size:12px;font-weight:700"><i class="fa-solid fa-network-wired" style="margin-right:6px"></i>Network Monitoring</h4>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Client IP Address</div><div style="font-size:12px;font-weight:600;color:var(--cyan);margin-top:2px">${diag.ip || net.ip || '—'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Gateway IP</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.gateway || d.gateway || '—'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">DNS Server</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.dns || d.dns || '—'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Subnet Mask</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.subnet || d.subnet || '255.255.255.0'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">MAC Address</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.mac || d.mac || '—'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Vendor</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${diag.vendor || d.vendor || 'Enterprise PC'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">VPN Status</div><div style="font-size:12px;font-weight:600;color:${net.vpn_status === 'Connected' ? 'var(--green2)' : 'var(--txt)'};margin-top:2px">${net.vpn_status || 'Disconnected'}</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px">
        <div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">WiFi</div>
        <div style="font-size:11px;font-weight:600;color:${net.wifi_ssid ? 'var(--green2)' : 'var(--txt3)'};margin-top:2px">
          ${net.wifi_ssid ? '📶 ' + net.wifi_ssid : '📵 Disconnected'}
        </div>
        ${net.wifi_signal && net.wifi_ssid ? `<div style="font-size:10px;color:var(--txt3)">${net.wifi_signal} ${net.wifi_channel ? '· Ch.' + net.wifi_channel : ''}</div>` : ''}
        ${net.wifi_bssid ? `<div style="font-size:9px;color:var(--txt3)">${net.wifi_bssid}</div>` : ''}
        ${net.wifi_security ? `<span style="background:rgba(34,211,238,.1);color:var(--cyan);border:1px solid rgba(34,211,238,.3);border-radius:3px;padding:1px 5px;font-size:8.5px;font-weight:600">${net.wifi_security}</span>` : ''}
      </div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Bandwidth Rate</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">⬇️ ${typeof net.bandwidth_download_kbps === 'number' ? net.bandwidth_download_kbps.toFixed(0) : (net.bandwidth_download_kbps || 0)} KB/s · ⬆️ ${typeof net.bandwidth_upload_kbps === 'number' ? net.bandwidth_upload_kbps.toFixed(0) : (net.bandwidth_upload_kbps || 0)} KB/s</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Packet Loss &amp; Jitter</div><div style="font-size:12px;font-weight:600;color:${(net.packet_loss_pct > 0 || d.packet_loss > 0) ? 'var(--red2)' : 'var(--txt)'};margin-top:2px">${net.packet_loss_pct !== undefined ? net.packet_loss_pct : (d.packet_loss || 0)}% Loss · ${net.jitter_ms || 0} ms Jitter</div></div>
      <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Ping Latency</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.ping_latency_ms !== undefined ? net.ping_latency_ms : (d.latency || 0)} ms</div></div>
    </div>
  </div>
`;

    // 2. Build Enterprise Web App Usage & Multi-Browser Tab Monitoring
    let websHtml = window.BrowserMonitoring ? window.BrowserMonitoring.renderSection(diag, d.name) : '';
    if (!websHtml) {
      const curUrl = (diag.current_browser_url && diag.current_browser_url.url) ? diag.current_browser_url.url : 'Tidak ada tab aktif';
      const currentURLHtml = `<div style="font-size:11px;color:var(--txt);margin-bottom:6px"><strong>Tab Aktif:</strong> ${curUrl}</div>`;
      const histList = Array.isArray(diag.browser_url_history_10min) ? diag.browser_url_history_10min : [];
      const urlHistoryHtml = histList.length > 0
        ? `<div style="font-size:10px;color:var(--txt2)">${histList.slice(0, 5).map(h => `<div>• ${h.title || h.url || '—'}</div>`).join('')}</div>`
        : `<div style="font-size:10px;color:var(--txt3)">Belum ada riwayat URL 10 menit terakhir.</div>`;
      websHtml = `
        <div class="card-sec" style="margin-top:15px">
          <h4 style="margin-bottom:8px;color:var(--cyan);font-size:12px;font-weight:700"><i class="fa-solid fa-earth-americas" style="margin-right:6px"></i>Web App Usage &amp; URL Monitoring</h4>
          <div style="background:rgba(0,0,0,.15);border:1px solid rgba(255,255,255,.05);border-radius:6px;padding:10px">
            ${currentURLHtml}
            ${urlHistoryHtml}
          </div>
        </div>
      `;
    }

    // 3. Build Active Apps & Window Titles
    let appsHtml = '';
    if (diag.apps && diag.apps.length > 0) {
      appsHtml = `
    <div class="card-sec" style="margin-top:15px">
      <h4 style="margin-bottom:8px;color:var(--purple);font-size:12px;font-weight:700"><i class="fa-solid fa-cubes" style="margin-right:6px"></i>Aplikasi &amp; Proses Aktif</h4>
      <table class="tbl" style="width:100%;font-size:11px">
        <thead>
          <tr>
            <th style="text-align:left;width:130px">Nama Proses</th>
            <th style="text-align:right;width:55px">CPU%</th>
            <th style="text-align:right;width:55px">MEM%</th>
            <th style="text-align:center;width:85px">Status</th>
            <th style="text-align:left;width:50px">PID</th>
          </tr>
        </thead>
        <tbody>
          ${diag.apps.slice(0, 15).map(app => {
            const cpu = parseFloat(app.CPU || app.cpu || 0);
            const mem = parseFloat(app.Memory || app.memory || app.MemoryMB || 0);
            const status = app.Status || app.status || 'Sleeping';
            const statusCode = app.StatusCode || app.statusCode || 'S';
            const statusColor = statusCode === 'R' ? 'var(--green)' :
                                statusCode === 'Z' ? 'var(--red2)' :
                                statusCode === 'T' ? 'var(--orange)' :
                                statusCode === 'D' ? 'var(--yellow)' : 'var(--txt3)';
            const cpuColor = cpu > 50 ? 'var(--red2)' : cpu > 20 ? 'var(--orange)' : 'var(--txt2)';
            const memColor = mem > 50 ? 'var(--red2)' : mem > 20 ? 'var(--orange)' : 'var(--txt2)';
            return `<tr>
              <td style="font-weight:600;color:var(--txt)">${_esc(app.Name || app.ProcessName || 'Unknown')}</td>
              <td style="text-align:right;font-weight:700;color:${cpuColor};font-family:monospace">${cpu.toFixed(1)}%</td>
              <td style="text-align:right;font-weight:700;color:${memColor};font-family:monospace">${mem.toFixed(1)}%</td>
              <td style="text-align:center">
                <span style="background:${statusColor}20;color:${statusColor};border:1px solid ${statusColor}40;border-radius:3px;padding:1px 6px;font-size:9.5px;font-weight:600">${status}</span>
              </td>
              <td style="color:var(--txt3);font-family:monospace;font-size:10px">${_esc(app.Id || app.PID || '—')}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      ${diag.apps.length > 15 ? `<div style="font-size:9px;color:var(--txt3);margin-top:4px;text-align:right">+ ${diag.apps.length - 15} proses lainnya</div>` : ''}
    </div>
  `;
    }

    // 4. Build Printers Status
    let printHtml = '';
    if (diag.printers && diag.printers.installed_list && diag.printers.installed_list.length > 0) {
      printHtml = `
    <div class="card-sec" style="margin-top:15px">
      <h4 style="margin-bottom:8px;color:var(--orange);font-size:12px;font-weight:700"><i class="fa-solid fa-print" style="margin-right:6px"></i>Printer status & drivers</h4>
      <table class="tbl" style="width:100%;font-size:11px">
        <thead>
          <tr>
            <th style="text-align:left">Nama Printer</th>
            <th style="text-align:left">Port</th>
            <th style="text-align:left">Status</th>
          </tr>
        </thead>
        <tbody>
          ${diag.printers.installed_list.map(p => `
            <tr>
              <td style="font-weight:600;color:var(--txt)">${_esc(p.name)}</td>
              <td>${_esc(p.port || '—')}</td>
              <td><span class="tag ${p.status === 'ONLINE' ? 'tag-green' : 'tag-orange'}">${_esc(p.status)}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
    }

    // 4b. Build USB Devices Section
    let usbHtml = '';
    const usbList = diag.usb_devices || [];
    if (usbList.length > 0) {
      const usbTypeIcon = t => {
        const tl = (t||'').toLowerCase();
        if (tl.includes('hub')) return '🔌';
        if (tl.includes('storage') || tl.includes('diskdrive')) return '💾';
        if (tl.includes('camera') || tl.includes('webcam') || tl.includes('image')) return '📷';
        if (tl.includes('keyboard')) return '⌨️';
        if (tl.includes('mouse') || tl.includes('input') || tl.includes('hidclass')) return '🖱️';
        if (tl.includes('bluetooth')) return '📡';
        if (tl.includes('audio') || tl.includes('headset') || tl.includes('audioendpoint')) return '🔊';
        if (tl.includes('biometric') || tl.includes('fingerprint')) return '🔐';
        if (tl.includes('printer')) return '🖨️';
        return '🔌';
      };
      usbHtml = `
    <div class="card-sec" style="margin-top:15px">
      <h4 style="margin-bottom:8px;color:var(--cyan);font-size:12px;font-weight:700"><i class="fa-solid fa-plug" style="margin-right:6px"></i>USB Devices (${usbList.length} terdeteksi)</h4>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px">
        ${usbList.filter(u => {
          const desc = (u.description || u.FriendlyName || '').toLowerCase();
          return desc && !desc.includes('root hub') && desc.trim() !== '';
        }).map(u => {
          const desc = u.description || u.FriendlyName || 'Unknown Device';
          const type = u.type || u.Class || 'USB Device';
          const status = u.status || 'Connected';
          const vendorId = u.vendor_id || '';
          const isOk = status === 'Connected' || status === 'OK';
          const statusColor = isOk ? 'var(--green)' : status === 'Error' ? 'var(--red2)' : 'var(--orange)';
          return `<div style="background:var(--glass);border-radius:6px;padding:8px 10px;display:flex;align-items:flex-start;gap:8px">
            <span style="font-size:18px;flex-shrink:0;margin-top:1px">${usbTypeIcon(type)}</span>
            <div style="min-width:0">
              <div style="font-size:11px;font-weight:600;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${desc}">${desc}</div>
              <div style="font-size:9px;color:var(--txt3);margin-top:1px">${type}</div>
              ${vendorId ? `<div style="font-size:8.5px;color:var(--txt3);font-family:monospace">${vendorId.split('\\')[0] || vendorId}</div>` : ''}
              <span style="background:${statusColor}20;color:${statusColor};border:1px solid ${statusColor}40;border-radius:3px;padding:1px 5px;font-size:8.5px;font-weight:600;margin-top:3px;display:inline-block">${status}</span>
            </div>
          </div>`;
        }).join('')}
      </div>
    </div>
  `;
    }

    // 5. Build Critical Services & Stopped Services
    let servicesHtml = '';
    if (diag.service_status && Object.keys(diag.service_status).length > 0) {
      const svcs = Object.entries(diag.service_status);
      const stoppedSvc = diag.stopped_critical || [];
      servicesHtml = `
    <div class="card-sec" style="margin-top:15px">
      <h4 style="margin-bottom:8px;color:var(--red);font-size:12px;font-weight:700"><i class="fa-solid fa-sliders" style="margin-right:6px"></i>Windows Services (Critical)</h4>
      <div style="font-size:11px;margin-bottom:6px">
        Critical stopped: ${stoppedSvc.length > 0 ? stoppedSvc.map(s => `<span class="tag tag-orange" style="margin-right:4px">${s}</span>`).join('') : '<span class="tag tag-green">None (All running)</span>'}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;max-height:120px;overflow-y:auto;padding-right:4px;border:1px solid rgba(255,255,255,.05);border-radius:4px;padding:6px;background:rgba(0,0,0,.1)">
        ${svcs.map(([sname, sstatus]) => `
          <div style="display:flex;justify-content:between;align-items:center;font-size:10px;background:rgba(255,255,255,.02);padding:3px 6px;border-radius:3px">
            <span style="color:var(--txt2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:110px" title="${sname}">${sname}</span>
            <span style="font-weight:700;color:${sstatus === 'Running' ? 'var(--green2)' : 'var(--red2)'}">${sstatus}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
    }

    // Combine all sections!
    body.innerHTML = itemsHtml + netHtml + websHtml + appsHtml + printHtml + usbHtml + servicesHtml;

  } catch (err) {
    body.innerHTML = itemsHtml + `
  <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:6px;padding:12px;margin-top:15px;color:var(--red2);font-size:11.5px">
    <i class="fa-solid fa-circle-exclamation" style="margin-right:8px;color:var(--red)"></i>
    <strong>Deep Diagnostics Offline:</strong> ${err.message || err}
    <div style="font-size:10px;color:var(--txt3);margin-top:6px;line-height:1.4">
      Penyebab potensial:
      <br>1. Client agent belum berjalan atau port 10001 ditutup firewall lokal.
      <br>2. Client PC offline dari jaringan.
      <br>3. Konfigurasi routing VPN/LAN bermasalah.
    </div>
  </div>
`;
  }
};

  window.Modules = window.Modules || {};
  window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};
  window.Modules.ShowDeviceDiagnostics = { show: window.showDeviceDiagnosticsDetail };
  window.Modules["2_fleet_health"]["show-device-diagnostics"] = window.Modules.ShowDeviceDiagnostics;
})();
