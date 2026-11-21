/* printer-mgr.js
 * Module: PrinterMgr — printer status, queue, spooler management.
 * Extracted from o-nav-router.js (lines 605-1055) — Phase 5.5 Atomic Design refactor.
 *
 * Layer: Modules > 2_fleet_health
 * Depends on: DataService (service), Notify (molecule), Modal (molecule), Charts (molecule)
 */
(function () {
  'use strict';

const PrinterMgr = (() => {
  let _printers = [];
  let _refreshTimer = null;

  function toggleSitePartition(partKey) {
if (!PrinterMgr.collapsed) PrinterMgr.collapsed = {};
PrinterMgr.collapsed[partKey] = !PrinterMgr.collapsed[partKey];
const el = document.getElementById('pr-part-body-' + partKey);
const icon = document.getElementById('pr-part-icon-' + partKey);
if (el) {
  if (PrinterMgr.collapsed[partKey]) {
    el.style.display = 'none';
    if (icon) icon.className = 'fa-solid fa-chevron-right';
  } else {
    el.style.display = 'grid';
    if (icon) icon.className = 'fa-solid fa-chevron-down';
  }
}
  }

  function _findHostAgent(printerName) {
const devices = DataService._devices || [];
const hostDev = devices.find(d => {
  const pInfo = d.metadata && d.metadata.printers;
  if (pInfo && pInfo.installed_list) {
    return pInfo.installed_list.some(p => p.name === printerName);
  }
  return false;
});
// fallback: look for pc_name field on the printer record
const prRecord = _printers.find(p => p.name === printerName);
if (prRecord && prRecord.pc_name) return prRecord.pc_name;
return hostDev ? hostDev.name : null;
  }

  function _renderCard(p) {
const tonerCls = p.toner_pct < 20 ? 'pb-red' : p.toner_pct < 50 ? 'pb-orange' : 'pb-green';
const inkCls   = p.ink_pct   < 20 ? 'pb-red' : p.ink_pct   < 50 ? 'pb-orange' : 'pb-green';
const site = p.site_id || getSite(p.ip) || '—';
const lastPing = p.last_pinged && p.last_pinged !== '0001-01-01T00:00:00Z'
  ? timeSince(p.last_pinged) : 'Belum ping';
return `<div class="printer-card" id="pcard-${Number(p.printer_id) || 0}" data-name="${_esc((p.name || '').toLowerCase())}" data-ip="${_esc((p.ip || '').toLowerCase())}" data-site="${_esc(site.toLowerCase())}" data-status="${_esc(p.status || '')}">
  <div class="printer-header">
    <div>
      <div style="font-size:11.5px;font-weight:700"><i class="fa-solid fa-print" style="color:var(--blue);margin-right:6px"></i>${_esc(p.name)}</div>
      <div style="font-size:10px;color:var(--txt2)">${_esc(p.ip)}:${Number(p.port) || 9100} · ${_esc(site)}${p.model ? ' · ' + _esc(p.model) : ''}</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px">
      ${statusTag(p.status)}
      <span style="font-size:9px;color:var(--txt3)">${lastPing}</span>
    </div>
  </div>
  <div class="printer-body">
    <div class="toner-section">
      <div class="pb-label"><span><i class="fa-solid fa-droplet" style="color:#fff;margin-right:5px"></i>Toner</span><span>${p.toner_pct}%</span></div>
      <div class="pb"><div class="pb-fill ${tonerCls}" style="width:${Math.max(2,p.toner_pct)}%;animation:none"></div></div>
    </div>
    <div class="toner-section">
      <div class="pb-label"><span><i class="fa-solid fa-fill-drip" style="color:var(--cyan);margin-right:5px"></i>Ink Level</span><span>${p.ink_pct}%</span></div>
      <div class="pb"><div class="pb-fill ${inkCls}" style="width:${Math.max(2,p.ink_pct)}%;animation:none"></div></div>
    </div>
    <div class="li-row" style="margin-top:6px">
      <span class="li-name"><i class="fa-solid fa-list-check" style="margin-right:5px"></i>Queue</span>
      <span class="tag ${p.queue_count > 5 ? 'tag-orange' : 'tag-gray'}">${p.queue_count} docs</span>
    </div>
    <div class="li-row">
      <span class="li-name"><i class="fa-solid fa-file" style="margin-right:5px"></i>Paper</span>
      <span class="tag ${p.paper_count < 100 ? 'tag-orange' : 'tag-green'}">${p.paper_count} sheets</span>
    </div>
    ${p.error_msg ? `<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:5px;padding:6px 8px;font-size:10.5px;color:var(--red2);margin:6px 0"><i class="fa-solid fa-circle-exclamation" style="color:var(--red);margin-right:6px"></i>${_esc(p.error_msg)}</div>` : ''}
    <div style="display:flex;gap:5px;margin-top:8px;flex-wrap:wrap">
      <button class="btn btn-ghost btn-xs" onclick="PrinterMgr.ping(${Number(p.printer_id) || 0})" title="TCP Ping"><i class="fa-solid fa-satellite-dish" style="margin-right:4px"></i>Ping</button>
      <button class="btn btn-danger btn-xs" onclick="PrinterMgr.clearQueue(${_jsAttr(p.name)}, ${Number(p.printer_id) || 0})"><i class="fa-solid fa-trash-can" style="margin-right:4px"></i>Clear Queue</button>
      <button class="btn btn-warning btn-xs" onclick="PrinterMgr.restartSpooler(${_jsAttr(p.name)})"><i class="fa-solid fa-rotate" style="margin-right:4px"></i>Restart</button>
      <button class="btn btn-primary btn-xs" onclick="PrinterMgr.testPrint(${_jsAttr(p.name)})"><i class="fa-solid fa-print" style="margin-right:4px"></i>Test Print</button>
      <button class="btn btn-ghost btn-xs" onclick="PrinterMgr.openEditModal(${Number(p.printer_id) || 0})" title="Edit"><i class="fa-solid fa-pen" style="margin-right:3px"></i>Edit</button>
      <button class="btn btn-danger btn-xs" onclick="PrinterMgr.deletePrinter(${Number(p.printer_id) || 0}, ${_jsAttr(p.name)})" title="Hapus"><i class="fa-solid fa-trash" style="margin-right:3px"></i>Hapus</button>
    </div>
  </div>
</div>`;
  }

  function _renderHardwareBanner(hw) {
const banner = document.getElementById('printer-hardware-discovery-banner');
if (!banner) return;
if (!hw || !hw.state_machine) {
  banner.innerHTML = '';
  return;
}
const sm = hw.state_machine;
const isCert = sm.certification_verdict === 'CERTIFIED';
const stBadge = isCert
  ? '<span class="tag tag-green" style="font-size:10px;font-weight:700">🟢 PHYSICAL HARDWARE CERTIFIED</span>'
  : '<span class="tag tag-orange" style="font-size:10px;font-weight:700">🟡 PENDING ON-PREMISE PHYSICAL PRINTER</span>';

const stepPill = (label, ok) => `
  <div style="display:flex;align-items:center;gap:5px;background:rgba(255,255,255,.04);border:1px solid ${ok ? 'rgba(16,185,129,.3)' : 'rgba(245,158,11,.3)'};padding:4px 8px;border-radius:6px;font-size:9.5px">
    <span style="color:${ok ? '#10b981' : '#f59e0b'}">${ok ? '●' : '○'}</span>
    <span style="color:${ok ? '#f8fafc' : '#94a3b8'}">${label}</span>
  </div>`;

banner.innerHTML = `
  <div style="background:linear-gradient(135deg, rgba(15,23,42,.95), rgba(30,41,59,.95));border:1px solid var(--bd2);border-radius:10px;padding:14px 18px;box-shadow:0 8px 24px rgba(0,0,0,.3)">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <i class="fa-solid fa-microchip" style="color:var(--cyan);font-size:15px"></i>
        <span style="font-size:12px;font-weight:700;color:#f8fafc">USB Printer Discovery & Hardware Health State Machine</span>
        <span style="font-size:10px;color:var(--txt3)">(${_esc(hw.host_os || 'Linux OS')})</span>
      </div>
      <div>${stBadge}</div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:8px;margin-bottom:12px">
      <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
        <div style="font-size:9.5px;color:var(--txt3)">USB Enumeration</div>
        <div style="font-size:11px;font-weight:600;color:var(--txt1)">${hw.usb_devices ? hw.usb_devices.length : 0} Devices (${Number(hw.printer_usb_count) || 0} Printers)</div>
      </div>
      <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
        <div style="font-size:9.5px;color:var(--txt3)">CUPS / Spooler Subsystem</div>
        <div style="font-size:11px;font-weight:600;color:${hw.cups_available ? '#10b981' : '#f59e0b'}">${hw.cups_available ? 'Active (lpstat OK)' : 'Not Configured'}</div>
      </div>
      <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
        <div style="font-size:9.5px;color:var(--txt3)">Character Node</div>
        <div style="font-size:11px;font-weight:600;color:var(--txt2)">${(hw.kernel_nodes && hw.kernel_nodes.length) ? _esc(hw.kernel_nodes[0].path) : '/dev/usb/lp0 (Pending)'}</div>
      </div>
      <div style="background:rgba(0,0,0,.25);padding:8px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.05)">
        <div style="font-size:9.5px;color:var(--txt3)">ESC/POS Protocol Format</div>
        <div style="font-size:11px;font-weight:600;color:#10b981">100% PROVEN (ESC @, Cut)</div>
      </div>
    </div>

    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      ${stepPill('1. USB Detected', sm.step_1_usb_device_detected)}
      ${stepPill('2. USB Identified', sm.step_2_usb_identified)}
      ${stepPill('3. Printer Enumerated', sm.step_3_printer_enumerated)}
      ${stepPill('4. CUPS Spooler', sm.step_4_cups_spooler_available)}
      ${stepPill('5. Node Connection', sm.step_5_device_connection_test)}
      ${stepPill('6. ESC/POS Command', sm.step_6_escpos_command_test)}
      ${stepPill('7. Test Print Output', sm.step_7_test_print_verified)}
    </div>

    <div style="font-size:10px;color:${isCert ? '#34d399' : '#fbbf24'};background:rgba(0,0,0,.2);padding:6px 10px;border-radius:5px">
      <i class="fa-solid fa-circle-info" style="margin-right:5px"></i>${_esc(sm.diagnostic_summary || 'Multi-layer hardware inspection ready.')}
    </div>
  </div>`;
  }

  async function runHardwareDiagnostics() {
Notify.toast('🔬 Hardware Diagnostics', 'Memeriksa perangkat USB dan character node...', 'info', 2000);
try {
  const res = await DataService.fetch('/api/printers/hardware_diagnostic_test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_type: 'DEVICE_NODE', endpoint: '/dev/usb/lp0' })
  });
  if (res && res.hardware_present) {
    Notify.toast('🟢 Hardware Detected', `ESC/POS test print berhasil ditransmisikan (${res.bytes_written} bytes)`, 'ok', 4000);
  } else if (res && res.bytes_generated) {
    Notify.toast('🟡 Hardware Pending', `Format ESC/POS siap (${res.bytes_generated} bytes). Perangkat fisik di ${res.endpoint} belum terpasang.`, 'warn', 4500);
  } else {
    Notify.toast('⚠️ Hardware Check', 'Pemeriksaan hardware selesai. Node printer fisik belum terhubung.', 'warn', 3500);
  }
  await load();
} catch (e) {
  Notify.toast('❌ Diagnostic Error', e.message || 'Gagal menjalankan diagnostik hardware', 'err', 3000);
}
  }

  async function load() {
const grid = document.getElementById('printer-grid');
if (!grid) return;
try {
  // 1. Fetch live printers and hardware discovery concurrently
  const [res, hwRes] = await Promise.all([
    DataService.fetch('/api/printers/live'),
    DataService.fetch('/api/printers/hardware_discovery').catch(() => null)
  ]);

  if (hwRes && hwRes.data) {
    _renderHardwareBanner(hwRes.data);
  }

  _printers = (res && res.printers) ? res.printers : [];

  const online = _printers.filter(p => p.status === 'ONLINE').length;
  const errCnt = _printers.filter(p => p.status !== 'ONLINE' && p.status !== 'UNKNOWN').length;
  const totalQ = _printers.reduce((a, p) => a + (p.queue_count || 0), 0);
  const avgToner = _printers.length
    ? Math.round(_printers.reduce((a, p) => a + (p.toner_pct || 0), 0) / _printers.length)
    : 0;

  setEl('pr-online', online);
  setEl('pr-error', errCnt);
  setEl('pr-queue', totalQ);
  setEl('pr-toner', avgToner + '%');
  const lastEl = document.getElementById('pr-last-refresh');
  if (lastEl) lastEl.textContent = 'Refresh: ' + new Date().toLocaleTimeString('id-ID');

  if (_printers.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--txt3)"><i class="fa-solid fa-print" style="font-size:32px;margin-bottom:10px;display:block;opacity:.3"></i><div>Belum ada printer terdaftar. Klik <b>Add Printer</b> untuk menambah.</div></div>`;
  } else {
    // Group Printers by Site & Router Gateway IP
    const siteGroups = {};
    _printers.forEach(p => {
      const site = p.site_id || getSite(p.ip) || 'Kantor Pusat - NUC';
      const gw = (p.ip && p.ip.includes('.')) ? (p.ip.split('.').slice(0, 3).join('.') + '.1') : '192.168.1.1';
      const groupKey = site + '___' + gw;
      if (!siteGroups[groupKey]) {
        siteGroups[groupKey] = {
          siteName: site,
          gatewayIP: gw,
          onlineCount: 0,
          offlineCount: 0,
          totalQueue: 0,
          printers: []
        };
      }
      if (p.status === 'ONLINE') {
        siteGroups[groupKey].onlineCount++;
      } else {
        siteGroups[groupKey].offlineCount++;
      }
      siteGroups[groupKey].totalQueue += (p.queue_count || 0);
      siteGroups[groupKey].printers.push(p);
    });

    let html = '';
    Object.values(siteGroups).forEach(group => {
      const total = group.printers.length;
      const safeKey = 'pr_part_' + (group.siteName + '_' + group.gatewayIP).replace(/[^a-zA-Z0-9_-]/g, '_');
      const isCollapsed = PrinterMgr.collapsed && PrinterMgr.collapsed[safeKey];
      const displayStyle = isCollapsed ? 'display:none' : 'display:grid';
      const iconClass = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';
      const siteBadgeCls = group.offlineCount > 0 ? 'border: 1px solid rgba(239,68,68,.35)' : 'border: 1px solid rgba(16,185,129,.35)';
      const escSite = _esc(group.siteName);
      const escGw = _esc(group.gatewayIP);

      html += `
        <div class="site-block-section" data-site-group="${escSite}" style="grid-column:1/-1;margin-bottom:20px;background:rgba(15,23,42,.6);border-radius:12px;padding:16px;box-shadow:0 4px 20px rgba(0,0,0,.25);${siteBadgeCls}">
          <div class="site-block-header" onclick="PrinterMgr.toggleSitePartition('${safeKey}')" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08);cursor:pointer;user-select:none;transition:background .2s" title="Klik untuk melipat / membuka partisi printer ini">
            <div style="display:flex;align-items:center;gap:10px">
              <button type="button" onclick="event.stopPropagation(); PrinterMgr.toggleSitePartition('${safeKey}')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:var(--cyan);width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer" title="Toggle Partisi ${escSite}">
                <i id="pr-part-icon-${safeKey}" class="${iconClass}" style="font-size:11px"></i>
              </button>
              <div style="width:34px;height:34px;border-radius:8px;background:rgba(59,130,246,.15);display:flex;align-items:center;justify-content:center;color:var(--blue);font-size:16px">
                <i class="fa-solid fa-print"></i>
              </div>
              <div>
                <div style="font-size:13.5px;font-weight:700;color:var(--txt);letter-spacing:0.2px">🏢 ${escSite}</div>
                <div style="font-size:11px;color:var(--txt3);display:flex;align-items:center;gap:6px">
                  <span style="background:rgba(6,182,212,.12);color:var(--cyan);padding:1px 6px;border-radius:4px;font-family:monospace;font-weight:600"><i class="fa-solid fa-network-wired" style="margin-right:4px"></i>GW: ${escGw}</span>
                  <span>· Subnet Connected</span>
                </div>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:11px;font-weight:600;background:rgba(16,185,129,.15);color:var(--green);padding:4px 10px;border-radius:6px;border:1px solid rgba(16,185,129,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.onlineCount} Online</span>
              ${group.offlineCount > 0 ? `<span style="font-size:11px;font-weight:600;background:rgba(239,68,68,.15);color:var(--red2);padding:4px 10px;border-radius:6px;border:1px solid rgba(239,68,68,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.offlineCount} Offline</span>` : ''}
              <span style="font-size:11px;color:var(--txt3);background:rgba(255,255,255,.05);padding:4px 8px;border-radius:6px">${total} Printer · Queue: ${group.totalQueue}</span>
            </div>
          </div>
          <div id="pr-part-body-${safeKey}" class="site-printer-subgrid" style="${displayStyle};grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:12px">
            ${group.printers.map(_renderCard).join('')}
          </div>
        </div>
      `;
    });
    grid.innerHTML = html;
    applyFilters();
  }
} catch (e) {
  console.error('[PrinterMgr] load error:', e);
  if (grid) grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--red2)"><i class="fa-solid fa-triangle-exclamation" style="font-size:24px;margin-bottom:8px;display:block"></i>Gagal memuat data printer: ${_esc(e.message)}</div>`;
}
  }

  async function ping(printerId) {
Notify.toast('📡 Pinging...', 'Menghubungi printer...', 'info', 1500);
try {
  const r = await DataService.fetch('/api/printers/ping/' + printerId, { method: 'POST' });
  const st = r && r.printer_status;
  Notify.toast(st === 'ONLINE' ? '🟢 Online' : '🔴 Offline',
    `Printer status: ${st}`, st === 'ONLINE' ? 'ok' : 'err', 2500);
  await load();
} catch (e) {
  Notify.toast('❌ Ping Failed', e.message, 'err', 3000);
}
  }

  async function pingAll() {
Notify.toast('📡 Ping All', 'Memping semua printer...', 'info', 2000);
try {
  const r = await DataService.fetch('/api/printers/ping_all', { method: 'POST' });
  const results = r && r.results ? r.results : [];
  const onlineC = results.filter(x => x.status === 'ONLINE').length;
  Notify.toast('✅ Ping Selesai', `${onlineC}/${results.length} printer online`, 'ok', 3000);
  await load();
} catch (e) {
  Notify.toast('❌ Ping Gagal', e.message, 'err', 3000);
}
  }

  function openAddModal() {
{ const _el = document.getElementById('printer-modal-title'); if (_el) _el.textContent = 'Add Printer'; }
document.getElementById('pr-edit-id').value = '';
document.getElementById('pr-name').value = '';
document.getElementById('pr-model').value = '';
document.getElementById('pr-ip').value = '';
document.getElementById('pr-port').value = '9100';
document.getElementById('pr-site-id').value = '';
document.getElementById('pr-pc-name').value = '';
const m = document.getElementById('printer-add-modal');
if (m) { m.style.display = 'flex'; }
  }

  function openEditModal(printerId) {
const p = _printers.find(x => x.printer_id === printerId);
if (!p) return;
{ const _el = document.getElementById('printer-modal-title'); if (_el) _el.textContent = 'Edit Printer'; }
document.getElementById('pr-edit-id').value = p.printer_id;
document.getElementById('pr-name').value = p.name;
document.getElementById('pr-model').value = p.model || '';
document.getElementById('pr-ip').value = p.ip;
document.getElementById('pr-port').value = p.port || 9100;
document.getElementById('pr-site-id').value = p.site_id || '';
document.getElementById('pr-pc-name').value = p.pc_name || '';
const m = document.getElementById('printer-add-modal');
if (m) { m.style.display = 'flex'; }
  }

  function closeAddModal() {
const m = document.getElementById('printer-add-modal');
if (m) m.style.display = 'none';
  }

  async function savePrinter() {
const editId  = document.getElementById('pr-edit-id').value;
const name    = document.getElementById('pr-name').value.trim();
const model   = document.getElementById('pr-model').value.trim();
const ip      = document.getElementById('pr-ip').value.trim();
const port    = parseInt(document.getElementById('pr-port').value) || 9100;
const siteId  = document.getElementById('pr-site-id').value.trim();
const pcName  = document.getElementById('pr-pc-name').value.trim();

if (!name || !ip) { Notify.toast('⚠️ Validasi', 'Nama dan IP wajib diisi', 'warn', 2500); return; }

try {
  if (editId) {
    // Edit existing
    const body = { name, model, ip, port, site_id: siteId, pc_name: pcName };
    await DataService.fetch('/api/printers/' + editId, { method: 'PUT', body: JSON.stringify(body) });
    Notify.toast('✅ Disimpan', `Printer ${_esc(name)} berhasil diperbarui`, 'ok', 2500);
  } else {
    // Create new
    const body = { name, ip, port, site_id: siteId || undefined, pc_name: pcName || undefined };
    if (model) body.model = model;
    await DataService.fetch('/api/fleet/admin/printers', { method: 'POST', body: JSON.stringify(body) });
    Notify.toast('✅ Ditambahkan', `Printer ${_esc(name)} berhasil didaftarkan`, 'ok', 2500);
    LogStreamer.add('OK', 'PRINTER', `Printer ${name} (${ip}:${port}) registered`);
  }
  closeAddModal();
  await load();
} catch (e) {
  Notify.toast('❌ Gagal', 'Error: ' + e.message, 'err', 3000);
}
  }

  function deletePrinter(printerId, printerName) {
const escName = _esc(printerName);
Modal.confirm('🗑️ Hapus Printer', `Yakin menghapus printer <b>${escName}</b>? Tindakan ini tidak dapat dibatalkan.`, async () => {
  Modal.close();
  try {
    await DataService.fetch('/api/printers/' + printerId, { method: 'DELETE' });
    Notify.toast('🗑️ Dihapus', `Printer ${escName} berhasil dihapus`, 'ok', 2500);
    LogStreamer.add('WARN', 'PRINTER', `Printer ${printerName} (ID:${printerId}) deleted`);
    await load();
  } catch (e) {
    Notify.toast('❌ Gagal', 'Error: ' + e.message, 'err', 3000);
  }
});
  }

  function clearQueue(printerName, printerId) {
const escName = _esc(printerName);
Modal.confirm('🗑️ Clear Queue', `Hapus semua dokumen antrian pada <b>${escName}</b>?`, async () => {
  Modal.close();
  const host = _findHostAgent(printerName);
  Notify.toast('🗑️ Clearing...', `Mengosongkan antrian ${escName}...`, 'warn', 2000);
  try {
    if (host) {
      const r = await DataService.sendCommand('CLEAR_SPOOLER', host, { printer_name: printerName });
      if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
        Notify.toast('✅ Queue Cleared', `Antrian ${printerName} dikosongkan via ${host}`, 'ok', 2500);
        LogStreamer.add('OK', 'PRINTER', `Queue cleared: ${printerName} via ${host}`);
        // Update queue count in DB
        await DataService.fetch('/api/printers/update_metrics', {
          method: 'POST',
          body: JSON.stringify({ printer_id: printerId, queue_count: 0 })
        });
      } else {
        Notify.toast('⚠️ Partial', `${r.error || r.message || 'Lihat log agent'}`, 'warn', 3000);
      }
    } else {
      Notify.toast('⚠️ No Agent', `Tidak ada PC agent ditemukan untuk ${printerName}. Pastikan pc_name terdaftar.`, 'warn', 4000);
    }
    await load();
  } catch (e) {
    Notify.toast('❌ Error', e.message, 'err', 3000);
  }
});
  }

  function restartSpooler(printerName) {
const host = _findHostAgent(printerName);
if (!host) { Notify.toast('⚠️ No Agent', `Tidak ada PC agent untuk ${printerName}`, 'warn', 3000); return; }
Notify.toast('🔄 Restarting...', `Merestart print spooler via ${host}...`, 'warn', 2000);
DataService.sendCommand('RESTART_SPOOLER', host, { printer_name: printerName })
  .then(r => {
    if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
      Notify.toast('✅ Restarted', `Spooler ${printerName} berhasil direstart`, 'ok', 2500);
      LogStreamer.add('OK', 'PRINTER', `Spooler restarted: ${printerName} via ${host}`);
    } else {
      Notify.toast('❌ Failed', r.error || r.message || 'Gagal restart', 'err', 3000);
    }
  }).catch(e => Notify.toast('❌ Error', e.message, 'err', 3000));
  }

  function testPrint(printerName) {
const host = _findHostAgent(printerName);
if (!host) { Notify.toast('⚠️ No Agent', `Tidak ada PC agent untuk ${printerName}`, 'warn', 3000); return; }
Notify.toast('🖨️ Test Print', `Mengirim halaman test via ${host}...`, 'info', 2000);
DataService.sendCommand('TEST_PRINT', host, { printer_name: printerName })
  .then(r => {
    if (r.status === 'SUCCESS' || (r.message && !r.message.includes('FAILED'))) {
      Notify.toast('✅ Test Sent', `Halaman test terkirim ke ${printerName}`, 'ok', 3000);
      LogStreamer.add('OK', 'PRINTER', `Test print sent: ${printerName} via ${host}`);
    } else {
      Notify.toast('❌ Failed', r.error || r.message || 'Gagal test print', 'err', 3000);
    }
  }).catch(e => Notify.toast('❌ Error', e.message, 'err', 3000));
  }

  function applyFilters() {
const q = ((document.getElementById('pr-search') || {}).value || '').toLowerCase().trim();
const st = ((document.getElementById('pr-filter-status') || {}).value || '').toUpperCase();
const grid = document.getElementById('printer-grid');
if (!grid) return;
grid.querySelectorAll('.printer-card').forEach(c => {
  const matchQ = !q || (c.dataset.name || '').includes(q) || (c.dataset.ip || '').includes(q) || (c.dataset.site || '').includes(q);
  const matchSt = !st || (c.dataset.status || '').toUpperCase() === st;
  c.style.display = (matchQ && matchSt) ? '' : 'none';
});
grid.querySelectorAll('.site-block-section').forEach(sec => {
  const hasVisible = sec.querySelector('.printer-card:not([style*="display: none"])');
  sec.style.display = hasVisible ? '' : 'none';
});
  }

  return { load, ping, pingAll, openAddModal, openEditModal, closeAddModal, savePrinter, deletePrinter, clearQueue, restartSpooler, testPrint, runHardwareDiagnostics, toggleSitePartition, applyFilters };
})();
window.PrinterMgr = PrinterMgr;

// Auto-refresh PrinterMgr when panel is active
setInterval(() => {
  if (document.getElementById('p-printer') &&
  document.getElementById('p-printer').classList.contains('active')) {
PrinterMgr.load();
  }
}, 30000);


  window.Modules = window.Modules || {};
  window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};
  window.Modules["2_fleet_health"]["printer-mgr"] = PrinterMgr;
  window.Modules.PrinterMgr = PrinterMgr;
})();
