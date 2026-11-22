/* o-remote.js
 * Organism: Remote — remote desktop access manager (RDP, AnyDesk, RustDesk, VNC, SSH).
 * Extracted from data.service.js (lines 5004-5470) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: Notify (molecule), Modal (molecule), RemoteSettings (organism), DataService (service)
 */
(function () {
  'use strict';

var Remote = {
  _selectedTarget: '',
  _fleetDevices: null,
  _fleetDevicesFetchedAt: 0,
  _escHtml(s) {
    if (typeof _esc === 'function') return _esc(s);
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  },
  async populateSelect(devices) {
    const sel = document.getElementById('remote-target-select');
    if (!sel) return;

    // Cache current selected value or use existing selected target
    const currentVal = sel.value || Remote._selectedTarget;

    // Fetch fleet devices if cache missing or older than 30s
    const now = Date.now();
    if (!Remote._fleetDevices || (now - Remote._fleetDevicesFetchedAt) > 30000) {
      try {
        const svc = (window.Services && window.Services.Data) || DataService;
        const data = await svc.fetch('/api/fleet/admin/devices');
        if (data && Array.isArray(data.devices)) {
          Remote._fleetDevices = data.devices;
          Remote._fleetDevicesFetchedAt = now;
        }
      } catch (e) {
        console.warn("Failed to load fleet devices registry for remote select: ", e);
      }
    }

    // Populate select
    sel.innerHTML = '<option value="">Pilih device target...</option>';
    if (devices && Array.isArray(devices)) {
      devices.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.name;
        opt.textContent = `${d.name} (${d.ip || '—'})`;
        sel.appendChild(opt);
      });
    }

    // Restore selection
    if (currentVal && devices && devices.some(d => d.name === currentVal)) {
      sel.value = currentVal;
      Remote._selectedTarget = currentVal;
    }

    // Define the update function for target details display
    const updateDisplay = () => {
      const selectedName = sel.value;
      const d = (DataService._devices || []).find(x => x.name === selectedName);
      setEl('remote-tools-target-ip', d ? (d.ip || '—') : '—');

      const adEl = document.getElementById('remote-anydesk-id-display');
      const rdEl = document.getElementById('remote-rustdesk-id-display');

      if (!selectedName) {
        if (adEl) adEl.innerHTML = '';
        if (rdEl) rdEl.innerHTML = '';
        return;
      }

      // Lookup in fleet devices cache for AnyDesk & RustDesk IDs
      const fleetDev = (Remote._fleetDevices || []).find(fd =>
        fd.pc_name && (fd.pc_name.toLowerCase() === selectedName.toLowerCase() || fd.pc_name.toLowerCase() === selectedName.toLowerCase().replace('pc-', ''))
      );

      let anydeskId = '';
      let rustdeskId = '';

      if (fleetDev) {
        rustdeskId = fleetDev.rustdesk_id || '';
        let hw = {};
        try {
          hw = (typeof fleetDev.hardware_info === 'string') ? JSON.parse(fleetDev.hardware_info) : (fleetDev.hardware_info || {});
        } catch (e) { hw = {}; }
        anydeskId = (hw && hw.anydesk_id) || '';
      }

      if (adEl) {
        adEl.innerHTML = anydeskId ? `<span class="tag tag-gray" style="border: 1px solid var(--red2); padding: 2px 6px; font-size: 10px;"><i class="fa-solid fa-tower-broadcast" style="margin-right:4px; color:var(--red2)"></i>AnyDesk ID: <b>${Remote._escHtml(anydeskId)}</b></span>` : '';
      }
      if (rdEl) {
        rdEl.innerHTML = rustdeskId ? `<span class="tag tag-gray" style="border: 1px solid var(--orange2); padding: 2px 6px; font-size: 10px;"><i class="fa-solid fa-desktop" style="margin-right:4px; color:var(--orange2)"></i>RustDesk ID: <b>${Remote._escHtml(rustdeskId)}</b></span>` : '';
      }
    };

    sel.onchange = function () {
      Remote._selectedTarget = this.value;
      updateDisplay();
    };

    // Initial display update
    updateDisplay();
  },
  updateButtonStates(launcherOnline, toolStatus) {
    const tools = ['rustdesk', 'anydesk', 'vnc', 'rdp', 'explorer', 'logs', 'settings', 'detect'];
    tools.forEach(tool => {
      const btn = document.getElementById('remote-btn-' + tool);
      if (!btn) return;

      btn.style.opacity = '1';
      btn.style.cursor = 'pointer';

      if (!launcherOnline) {
        btn.title = 'Launcher Service Offline (Click to retry connection)';
        btn.style.border = '1px solid var(--bd)';
      } else {
        btn.title = 'Launcher Online';

        if (tool === 'rustdesk') {
          const installed = toolStatus && toolStatus.rustdesk && toolStatus.rustdesk.installed;
          if (installed) {
            btn.style.border = '1px solid var(--orange2)';
            btn.title = 'RustDesk - Detected (Ready)';
          } else {
            btn.title = 'RustDesk - Ready (Launch/Detect)';
            btn.style.border = '1px solid var(--bd)';
          }
        } else if (tool === 'anydesk') {
          const installed = toolStatus && toolStatus.anydesk && toolStatus.anydesk.installed;
          if (installed) {
            btn.style.border = '1px solid var(--red2)';
            btn.title = 'AnyDesk - Detected (Ready)';
          } else {
            btn.title = 'AnyDesk - Ready (Launch/Detect)';
            btn.style.border = '1px solid var(--bd)';
          }
        } else if (tool === 'vnc') {
          let installed = false;
          if (toolStatus && toolStatus.vnc) {
            for (const k in toolStatus.vnc) {
              if (toolStatus.vnc[k] && toolStatus.vnc[k].installed) {
                installed = true;
                break;
              }
            }
          }
          if (installed) {
            btn.style.border = '1px solid var(--purple2)';
            btn.title = 'VNC Viewer - Detected (Ready)';
          } else {
            btn.title = 'VNC Viewer - Ready (Launch/Detect)';
            btn.style.border = '1px solid var(--bd)';
          }
        } else if (tool === 'rdp') {
          btn.style.border = '1px solid var(--blue2)';
          btn.title = 'RDP (mstsc) - Ready';
        } else {
          btn.style.border = '1px solid var(--bd)';
        }
      }
    });
  },
  launchDefault(targetOverride) {
    const defaultTool = document.querySelector('[name=rs-default-tool]:checked')?.value 
                      || (window.RemoteSettings?._settings?.general?.defaultTool) 
                      || 'rustdesk';
    this.launch(defaultTool, targetOverride);
  },
  async launch(type, targetOverride) {
    const sel = document.getElementById('remote-target-select');
    const target = targetOverride || (sel ? sel.value : '');
    const ip = document.getElementById('remote-tools-target-ip');

    const requiresTarget = ['rustdesk', 'anydesk', 'vnc', 'rdp', 'wol', 'ping', 'restart', 'shutdown', 'cmd', 'powershell', 'filetransfer', 'taskmgr', 'add_route', 'sync_site_route', 'show_route'].includes(type);

    if (requiresTarget && !target) {
      Notify.toast('⚠️ Remote', 'Pilih device target terlebih dahulu', 'warn');
      return;
    }

    // Sync select dropdown if targetOverride is passed (e.g. clicked from card)
    if (targetOverride && sel && sel.value !== targetOverride) {
      sel.value = targetOverride;
      sel.dispatchEvent(new Event('change'));
    }

    Remote._selectedTarget = target;
    const dev = DataService._devices.find(d => d.name === target);
    const devIp = dev ? dev.ip : '';
    if (ip) ip.textContent = devIp || '—';

    const isBackendLaunchTool = ['rustdesk', 'anydesk', 'vnc', 'rdp', 'explorer', 'logs', 'settings', 'detect'].includes(type);

    if (isBackendLaunchTool) {
      Notify.toast('🖥️ Remote Access', `Menghubungkan ke ${Remote._escHtml(target || 'local')} menggunakan ${Remote._escHtml(type)}...`, 'info');
      try {
        const svc = (window.Services && window.Services.Data) || DataService;
        const result = await svc.fetch('/api/remote/launch/' + encodeURIComponent(type), {
          method: 'POST',
          body: JSON.stringify({ device_id: target, pc_name: target, ip: devIp, tool: type })
        });

        if (!result || result.status === 'error') {
          Notify.toast('❌ Error Launch', Remote._escHtml((result && (result.message || result.error)) || 'Gagal memproses remote launch'), 'err', 4000);
          return;
        }

        if (type === 'settings') {
          Notify.toast('⚙️ Settings', 'Membuka Remote Access Settings', 'ok', 2000);
          RemoteSettings.open();
          return;
        }

        if (type === 'detect') {
          Notify.toast('🔍 Detect', 'Memulai deteksi tools...', 'ok', 2000);
          RemoteSettings.open();
          RemoteSettings.switchTab('testconn');
          RemoteSettings.testAllConnections();
          return;
        }

        // Method A: Local launch completed directly by dashboard server (if server is running on local host)
        if (result.launcher_status === 'online' && result.status === 'success') {
          Notify.toast('🚀 Launched', `Berhasil membuka ${Remote._escHtml(type)} secara lokal`, 'ok', 3000);
          LogStreamer.add('INFO', 'REMOTE', type.toUpperCase() + ' launched locally' + (target ? ' for ' + target : ''));
          return;
        }

        // Method B: Operator PC launch (Try local launcher port 44600, fallback to direct URI protocol / RDP file)
        if (result.launcher_status === 'relay_required' || result.launcher_payload) {
          const payload = result.launcher_payload || {};
          const rawId = (payload.id && payload.id !== '---') ? payload.id : (payload.ip || payload.host || devIp || target || '');
          const validId = String(rawId).trim().replace(/[^\w\.\:\-]/g, '');
          const activeScheme = `${type}://${validId}`;
          payload.url_scheme = activeScheme;
          payload.id = validId;
          let launchedViaRelay = false;

          // Try local launcher service on port 44600 with short timeout
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1200);
            const lResponse = await fetch('http://127.0.0.1:44600/launch', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
              signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (lResponse.ok) {
              const lResult = await lResponse.json();
              launchedViaRelay = true;
              Notify.toast('🚀 Remote Access', `Berhasil membuka ${type}` + (target ? ` ke ${target}` : ''), 'ok', 3000);
              LogStreamer.add('INFO', 'REMOTE', type.toUpperCase() + ' launched via local launcher relay' + (target ? ' for ' + target : ''));
              return;
            }
          } catch (lErr) {
            console.warn("Local launcher port 44600 unavailable, attempting direct browser launch...", lErr);
          }

          // Fallback Method C: Direct Browser Protocol Scheme (rustdesk://, anydesk://, vnc://)
          if (activeScheme && (type === 'rustdesk' || type === 'anydesk' || type === 'vnc')) {
            Notify.toast('🚀 Opening App', `Membuka ${type.toUpperCase()} di PC Anda (${validId})...`, 'ok', 4000);
            
            // Show credential helper dialog for operator convenience
            const passVal = payload.password || '';
            const passInfo = passVal ? `<br>🔑 Password: <b style="color:var(--yellow)" id="rd-modal-pass">${passVal}</b>` : '';
            Modal.show('🖥️ Remote Access — ' + type.toUpperCase(), `
              <div style="text-align:center;padding:10px">
                <div style="font-size:14px;font-weight:600;margin-bottom:8px">Menghubungkan ke ${target || 'PC Client'}</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:12px;background:rgba(0,0,0,.3);padding:10px;border-radius:6px;border:1px solid var(--bd);margin-bottom:12px">
                  ID/Host: <b style="color:var(--cyan)" id="rd-modal-host">${validId}</b>${passInfo}
                </div>
                <div style="font-size:11px;color:var(--txt3);margin-bottom:10px">Protokol <code id="rd-modal-scheme">${activeScheme}</code> dipicu secara otomatis di sistem Anda.</div>
                <div style="font-size:11px;background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);padding:8px 12px;border-radius:6px;text-align:left;color:var(--txt2)">
                  <i class="fa-solid fa-circle-info" style="color:var(--blue);margin-right:6px"></i><b>Pilihan & Saran Pengoperasian:</b>
                  <ul style="margin:4px 0 0 16px;padding:0">
                    <li>Klik <b>✏️ Ubah ID / IP</b> jika IP salah / mau pakai ID 9-digit RustDesk.</li>
                    <li>Klik <b>✏️ Ubah Password</b> jika password di PC target berbeda.</li>
                    <li>Klik <b>⚙️ Config Remote</b> untuk pengaturan server relay / default key.</li>
                  </ul>
                </div>
              </div>
            `, [
              { label: '📋 Copy ID/Host', cls: 'btn-ghost', fn: `navigator.clipboard.writeText(document.getElementById('rd-modal-host').textContent); Notify.toast('📋 Copied','ID/Host disalin!','ok');` },
              passVal ? { label: '🔑 Copy Password', cls: 'btn-ghost', fn: `navigator.clipboard.writeText('${passVal}'); Notify.toast('🔑 Copied','Password disalin!','ok');` } : null,
              { label: '✏️ Ubah ID / IP', cls: 'btn-ghost', fn: `
                const curHost = document.getElementById('rd-modal-host').textContent;
                const newHost = prompt('Masukkan ID RustDesk (misal: 982 431 102) atau Alamat IP baru:', curHost);
                if (newHost && newHost.trim()) {
                  const cleanHost = newHost.trim().replace(/\\s+/g, '');
                  { const _el = document.getElementById('rd-modal-host'); if (_el) _el.textContent = cleanHost; }
                  const curPass = document.getElementById('rd-modal-pass')?.textContent || '';
                  if (curPass) { try { navigator.clipboard.writeText(curPass); } catch (_) {} }
                  const newScheme = '${type}://' + cleanHost;
                  const codeEl = document.getElementById('rd-modal-scheme');
                  if (codeEl) codeEl.textContent = newScheme;
                  window.location.href = newScheme;
                  Notify.toast('✏️ Target Updated', 'Target diubah ke ' + cleanHost + ' & menghubungkan ulang...', 'ok');
                }
              ` },
              { label: '✏️ Ubah Password', cls: 'btn-ghost', fn: `
                const curHost = document.getElementById('rd-modal-host').textContent;
                const curPass = document.getElementById('rd-modal-pass')?.textContent || '${passVal}';
                const newPass = prompt('Masukkan password baru untuk ' + curHost + ':', curPass);
                if (newPass !== null) {
                  const passEl = document.getElementById('rd-modal-pass');
                  if (passEl) passEl.textContent = newPass;
                  if (newPass) { try { navigator.clipboard.writeText(newPass); } catch (_) {} }
                  const newScheme = '${type}://' + curHost;
                  const codeEl = document.getElementById('rd-modal-scheme');
                  if (codeEl) codeEl.textContent = newScheme;
                  window.location.href = newScheme;
                  Notify.toast('🔑 Password Updated', 'Password disalin ke clipboard & menghubungkan ulang...', 'ok');
                }
              ` },
              { label: '⚙️ Config Remote', cls: 'btn-ghost', fn: 'Modal.close(); RemoteSettings.open(); RemoteSettings.switchTab("rustdesk");' },
              { label: '🚀 Hubungkan Ulang', cls: 'btn-primary', fn: `
                const curHost = document.getElementById('rd-modal-host').textContent;
                const curPass = document.getElementById('rd-modal-pass')?.textContent || '';
                if (curPass) { try { navigator.clipboard.writeText(curPass); } catch (_) {} }
                window.location.href = '${type}://' + curHost;
              ` },
              { label: 'Tutup', cls: 'btn-ghost', fn: 'Modal.close()' }
            ].filter(Boolean));

            // Trigger application launch in browser immediately
            try {
              window.location.href = activeScheme;
            } catch(e) {
              console.warn("Direct location launch notice:", e);
            }
            LogStreamer.add('INFO', 'REMOTE', type.toUpperCase() + ' launched via browser protocol handler');
            return;
          }

          // Fallback Method D: Dynamic .rdp file generation for Remote Desktop Connection
          if (type === 'rdp') {
            const host = payload.host || devIp || target || '127.0.0.1';
            const rdpContent = `full address:s:${host}\nprompt for credentials:i:1\nadministrative session:i:1\nvisual styles:i:1\n`;
            const blob = new Blob([rdpContent], { type: 'application/x-rdp' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `Connect-${target || 'PC'}-${host}.rdp`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            Notify.toast('💻 File RDP Terunduh', `File RDP ke ${host} berhasil diunduh. Klik file tersebut untuk terhubung.`, 'ok', 5000);
            LogStreamer.add('INFO', 'REMOTE', 'RDP connection file generated for ' + host);
            return;
          }

          Notify.toast('⚠️ Remote Launch', `Tidak dapat membuka ${type}. Pastikan aplikasi ${type} terpasang di PC Anda.`, 'warn', 5000);
        }
      } catch (err) {
        Notify.toast('❌ Connection Error', err.message || err, 'err');
      }
      return;
    }

    const actions = {
      wol: () => { Modal.confirm('Wake On LAN', 'Kirim Magic Packet ke ' + target + ' (' + devIp + ')?', async () => { Modal.close(); const r = await DataService.sendCommand('WAKE_ON_LAN', target, { ip: devIp }); Notify.toast('⚡ WOL', r.message || 'Magic packet sent', 'ok'); }); },
      ping: () => { Notify.toast('<i class="fa-solid fa-signal"></i> Ping', 'Pinging ' + devIp + '...', 'info'); DataService.sendCommand('PING', target, { ip: devIp }).then(r => { Notify.toast('<i class="fa-solid fa-signal"></i> Ping Result', r.message || 'Ping completed', 'ok', 3000); const el = document.getElementById('remote-result'); if (el) el.innerHTML = '<span style="color:var(--green2)">✅ Ping ' + devIp + ': ' + (r.data && r.data.latency ? r.data.latency + 'ms' : (r.message && r.message.match(/[0-9]+ms/) ? r.message.match(/[0-9]+ms/)[0] : 'OK')) + '</span>'; }); },
      restart: () => { Modal.confirm('⚠️ Restart PC', 'Restart ' + target + '? Semua program akan tertutup.', async () => { Modal.close(); const r = await DataService.sendCommand('RESTART', target); Notify.toast('🔄 Restart', r.message || 'Restart command sent', 'warn'); LogStreamer.add('WARN', 'REMOTE', 'Restart command sent to ' + target); }); },
      shutdown: () => { Modal.confirm('⚠️ Shutdown PC', 'Shutdown ' + target + '? PC akan mati.', async () => { Modal.close(); const r = await DataService.sendCommand('SHUTDOWN', target); Notify.toast('⏻ Shutdown', r.message || 'Shutdown command sent', 'warn'); LogStreamer.add('WARN', 'REMOTE', 'Shutdown command sent to ' + target); }); },
      cmd: () => { Modal.show('⌨️ Run CMD di ' + target, '<div><label class="inp-label">Command</label><input class="inp" id="remote-cmd-input" placeholder="ipconfig, netstat, etc."></div>', [{ label: 'Run', cls: 'btn-primary', fn: 'Remote._runCmd(\'' + target + '\')' }]); },
      powershell: () => { Modal.show('💙 PowerShell di ' + target, '<div><label class="inp-label">PowerShell Command</label><textarea class="inp" id="remote-ps-input" rows="3" placeholder="Get-Process, Get-Service, etc."></textarea></div>', [{ label: 'Run', cls: 'btn-purple', fn: 'Remote._runPs(\'' + target + '\')' }]); },
      add_route: () => {
        Modal.show('🌐 Add Route di ' + target, `
      <div>
        <label class="inp-label">Destination Subnet (e.g. 10.10.10.0)</label>
        <input class="inp" id="route-dest" placeholder="10.10.10.0" style="margin-bottom:8px">
        <label class="inp-label">Netmask (e.g. 255.255.255.0)</label>
        <input class="inp" id="route-mask" value="255.255.255.0" style="margin-bottom:8px">
        <label class="inp-label">Gateway IP</label>
        <input class="inp" id="route-gw" placeholder="192.168.1.1">
      </div>
    `, [{ label: 'Add Route', cls: 'btn-success', fn: 'Remote._addRoute(\'' + target + '\')' }]);
      },
      sync_site_route: () => {
        Modal.confirm('🌐 Sync Site Routes', 'Sync static routes for all configured sites on ' + target + '?', async () => {
          Modal.close();
          Notify.toast('🔄 Sync Routes', 'Syncing routes...', 'info');
          const r = await DataService.sendCommand('SYNC_SITE_ROUTE', target);
          Notify.toast('🌐 Sync Routes', r.status === 'SUCCESS' ? 'Routes synchronized' : 'Sync failed', r.status === 'SUCCESS' ? 'ok' : 'err');
          const el = document.getElementById('remote-result');
          if (el) {
            el.innerHTML = `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:8px 10px;gap:2px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">Sync Routes Result on ${target}</div><pre style="font-size:10px;color:var(--green2);white-space:pre-wrap;width:100%;margin-top:5px">${r.message || r.error || 'No output received'}</pre></div>`;
          }
        });
      },
      show_route: () => {
        Notify.toast('🌐 Show Routes', 'Requesting routing table...', 'info');
        DataService.sendCommand('SHOW_ROUTE', target).then(r => {
          Notify.toast('🌐 Show Routes', r.status === 'SUCCESS' ? 'Routes retrieved' : 'Failed to retrieve routes', r.status === 'SUCCESS' ? 'ok' : 'err');
          const el = document.getElementById('remote-result');
          if (el) {
            el.innerHTML = `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:8px 10px;gap:2px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">Routing Table for ${target}</div><pre style="font-size:10px;color:var(--green2);white-space:pre-wrap;width:100%;margin-top:5px">${r.message || r.error || 'No output received'}</pre></div>`;
          }
        });
      },
      filetransfer: () => {
        Modal.show('📁 File Transfer ke ' + target, `
      <div>
        <div style="font-size:11px;color:var(--txt2);margin-bottom:10px">Transfer file ke/dari ${target} (${devIp}) menggunakan SCP/SFTP atau shared folder.</div>
        <label class="inp-label">Mode Transfer</label>
        <select class="inp" id="ft-mode" style="margin-bottom:8px">
          <option value="upload">Upload ke PC</option>
          <option value="download">Download dari PC</option>
        </select>
        <label class="inp-label">Remote Path (Contoh: C:\\\\Users\\\\user\\\\Documents)</label>
        <input class="inp" id="ft-remote-path" placeholder="C:\\Users\\user\\Documents" style="margin-bottom:8px">
        <div style="font-size:10px;color:var(--txt3)">⚡ Memerlukan Launcher Service aktif dan agent terinstall di target.</div>
      </div>
    `, [{ label: '📁 Transfer', cls: 'btn-primary', fn: 'Remote._fileTransfer(\'' + target + '\')' }, { label: 'Batal', cls: 'btn-ghost', fn: 'Modal.close()' }]);
      },
      taskmgr: () => {
        Notify.toast('📊 Task Manager', 'Membuka Task Manager di ' + target + '...', 'info');
        DataService.sendCommand('TASKMGR', target, { ip: devIp }).then(r => {
          const el = document.getElementById('remote-result');
          if (el) el.innerHTML = `<span style="color:var(--green2)">✅ Task Manager launched on ${target}</span>`;
          Notify.toast('📊 Task Manager', r.message || 'Task Manager opened', 'ok', 2000);
        }).catch(() => { Notify.toast('⚠️ Task Manager', 'Launcher Service tidak tersedia', 'warn'); });
        LogStreamer.add('INFO', 'REMOTE', 'TASKMGR launched for ' + target);
      }
    };
    if (actions[type]) { actions[type](); LogStreamer.add('INFO', 'REMOTE', type.toUpperCase() + ' launched for ' + target + ' (' + devIp + ')'); }
  },
  async _runCmd(target) {
    const cmd = document.getElementById('remote-cmd-input').value;
    if (!cmd) return;
    Modal.close();
    Notify.toast('⌨️ CMD', `Running "${cmd}" on ${target}...`, 'info');
    const r = await DataService.sendCommand('CMD', target, { command: cmd });
    Notify.toast('⌨️ CMD', r.status === 'SUCCESS' ? 'Execution successful' : 'Execution failed', r.status === 'SUCCESS' ? 'ok' : 'err');
    LogStreamer.add('OK', 'REMOTE', 'CMD "' + cmd + '" sent to ' + target);
    const el = document.getElementById('remote-result');
    if (el) {
      el.innerHTML = `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:8px 10px;gap:2px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">CMD Output on ${target}</div><pre style="font-size:10px;color:var(--green2);white-space:pre-wrap;width:100%;margin-top:5px">${r.message || r.error || 'No output received'}</pre></div>`;
    }
  },
  async _runPs(target) {
    const cmd = document.getElementById('remote-ps-input').value;
    if (!cmd) return;
    Modal.close();
    Notify.toast('💙 PS', `Running script on ${target}...`, 'info');
    const r = await DataService.sendCommand('POWERSHELL', target, { command: cmd });
    Notify.toast('💙 PS', r.status === 'SUCCESS' ? 'Execution successful' : 'Execution failed', r.status === 'SUCCESS' ? 'ok' : 'err');
    LogStreamer.add('OK', 'REMOTE', 'PowerShell "' + cmd.slice(0, 30) + '" sent to ' + target);
    const el = document.getElementById('remote-result');
    if (el) {
      el.innerHTML = `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:8px 10px;gap:2px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">PowerShell Output on ${target}</div><pre style="font-size:10px;color:var(--green2);white-space:pre-wrap;width:100%;margin-top:5px">${r.message || r.error || 'No output received'}</pre></div>`;
    }
  },
  async _addRoute(target) {
    const dest = document.getElementById('route-dest').value;
    const mask = document.getElementById('route-mask').value;
    const gw = document.getElementById('route-gw').value;
    if (!dest || !gw) { Notify.toast('⚠️ Input', 'Destination and Gateway are required', 'warn'); return; }
    Modal.close();
    Notify.toast('🌐 Add Route', 'Adding route...', 'info');
    const r = await DataService.sendCommand('ADD_ROUTE', target, { destination: dest, mask: mask, gateway: gw });
    Notify.toast('🌐 Add Route', r.status === 'SUCCESS' ? 'Route added' : 'Failed to add route', r.status === 'SUCCESS' ? 'ok' : 'err');
    const el = document.getElementById('remote-result');
    if (el) {
      el.innerHTML = `<div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:6px;padding:8px 10px;gap:2px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">Add Route Result on ${target}</div><pre style="font-size:10px;color:var(--green2);white-space:pre-wrap;width:100%;margin-top:5px">${r.message || r.error || 'No output received'}</pre></div>`;
    }
  },
  async _fileTransfer(target) {
    const mode = document.getElementById('ft-mode')?.value || 'upload';
    const rpath = document.getElementById('ft-remote-path')?.value;
    if (!rpath) { Notify.toast('⚠️ Input', 'Remote path harus diisi', 'warn'); return; }
    Modal.close();
    Notify.toast('📁 File Transfer', 'Preparing ' + mode + ' to/from ' + target + '...', 'info');
    const r = await DataService.sendCommand('FILE_TRANSFER', target, { mode, remote_path: rpath });
    Notify.toast('📁 File Transfer', r.message || 'Transfer initiated', 'ok', 3000);
    LogStreamer.add('INFO', 'REMOTE', 'FILE_TRANSFER ' + mode + ' ' + rpath + ' on ' + target);
  }
};

  window.Remote = Remote;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.Remote = Remote;
})();
