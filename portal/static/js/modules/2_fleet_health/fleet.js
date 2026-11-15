/* panels/fleet.js
 * Fleet management panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      fleet: {
        viewMode: 'tree',
        setViewMode(mode) {
          this.viewMode = mode;
          const bTree = document.getElementById('fl-btn-tree');
          const bTbl = document.getElementById('fl-btn-table');
          const cTree = document.getElementById('fleet-tree-container');
          const cTbl = document.getElementById('tbl-fleet-wrap');
          if (bTree && bTbl && cTree && cTbl) {
            if (mode === 'tree') {
              bTree.className = 'btn btn-primary btn-sm';
              bTbl.className = 'btn btn-ghost btn-sm';
              cTree.style.display = 'block';
              cTbl.style.display = 'none';
            } else {
              bTbl.className = 'btn btn-primary btn-sm';
              bTree.className = 'btn btn-ghost btn-sm';
              cTree.style.display = 'none';
              cTbl.style.display = 'block';
            }
          }
        },
        toggleSiteTree(siteId) {
          if (!this.collapsed) this.collapsed = {};
          const safeKey = String(siteId).startsWith('site_') ? siteId : 'site_' + String(siteId).replace(/[^a-zA-Z0-9_-]/g, '_');
          this.collapsed[safeKey] = !this.collapsed[safeKey];
          this.collapsed[siteId] = this.collapsed[safeKey];

          const el = document.getElementById('site-tree-body-' + safeKey) || document.getElementById('site-tree-body-' + siteId);
          const icon = document.getElementById('site-tree-icon-' + safeKey) || document.getElementById('site-tree-icon-' + siteId);
          if (el) {
            if (this.collapsed[safeKey]) {
              el.style.display = 'none';
              if (icon) icon.className = 'fa-solid fa-chevron-right';
            } else {
              el.style.display = 'block';
              if (icon) icon.className = 'fa-solid fa-chevron-down';
            }
          }
        },
        toggleGwTree(gwKey) {
          if (!this.collapsedGw) this.collapsedGw = {};
          this.collapsedGw[gwKey] = !this.collapsedGw[gwKey];
          const el = document.getElementById('gw-tree-body-' + gwKey);
          const icon = document.getElementById('gw-tree-icon-' + gwKey);
          if (el) {
            if (this.collapsedGw[gwKey]) {
              el.style.display = 'none';
              if (icon) icon.className = 'fa-solid fa-chevron-right';
            } else {
              el.style.display = 'block';
              if (icon) icon.className = 'fa-solid fa-chevron-down';
            }
          }
        },
        focusSite(safeSiteKey) {
          if (this.viewMode !== 'tree') {
            this.setViewMode('tree');
          }
          if (this.collapsed && this.collapsed[safeSiteKey]) {
            this.toggleSiteTree(safeSiteKey);
          }
          const el = document.getElementById('site-tree-body-' + safeSiteKey);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (el.parentElement) {
              el.parentElement.style.boxShadow = '0 0 15px rgba(6,182,212,0.5)';
              setTimeout(() => {
                if (el.parentElement) el.parentElement.style.boxShadow = '';
              }, 1500);
            }
          }
        },
        async load() {
          const [devices] = await Promise.all([
            DataService.loadDevices(),
            DataService.loadSites()
          ]);
          this._render(devices);
        },
        async openBatchOTAModal() {
          const devices = await DataService.loadDevices().catch(() => []);
          const optionsHtml = devices.map(d => `<option value="${d.name}">${d.name} (${d.ip || 'Offline'}) — ${d.status}</option>`).join('');
          Modal.show(
            `🚀 Fleet Push OTA Update Center`,
            `<div style="padding:12px">
              <div style="font-size:12.5px;color:var(--txt2);margin-bottom:12px;line-height:1.5">
                Kirim pembaruan binary agen (v1.1.0) secara langsung via TCP Socket Port 10000 dengan verifikasi checksum SHA-256 otomatis.
              </div>
              <div style="margin-bottom:14px">
                <label style="font-size:11px;font-weight:700;color:var(--txt3);display:block;margin-bottom:6px">Pilih Perangkat Target:</label>
                <select id="ota-target-select" style="width:100%;padding:8px;background:#1e1e1e;color:#fff;border:1px solid var(--border);border-radius:6px;font-size:12px">
                  <option value="__ALL__">🌐 SEMUA PERANGKAT FLEET (Batch Push Update)</option>
                  ${optionsHtml}
                </select>
              </div>
              <div style="background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.2);padding:10px;border-radius:6px;font-size:11px;color:var(--cyan)">
                <i class="fa-solid fa-circle-info" style="margin-right:6px"></i>Biner target: <b>linux_agent</b> &amp; <b>windows_agent.exe</b> (SHA-256 Verifikasi Terintegrasi).
              </div>
            </div>`,
            [
              {
                label: '🚀 Jalankan Push OTA',
                cls: 'btn-primary',
                fn: async () => {
                  const sel = document.getElementById('ota-target-select');
                  const val = sel ? sel.value : '__ALL__';
                  Modal.close();
                  if (val === '__ALL__') {
                    Notify.toast('🚀 Batch OTA Initiated', 'Mengirim sinyal Push OTA ke seluruh armada perangkat...', 'info', 3000);
                    for (const d of devices) {
                      await this.pushOTA(d.name);
                    }
                  } else {
                    await this.pushOTA(val);
                  }
                }
              },
              { label: 'Batal', cls: 'btn-ghost', fn: () => Modal.close() }
            ],
            '🚀'
          );
        },
        async pushOTA(name) {
          Modal.show(
            `🚀 Memproses Push OTA Update — ${name}`,
            `<div style="text-align:center;padding:24px">
              <div style="font-size:42px;margin-bottom:14px;animation:pulse 1s infinite">📡</div>
              <div style="font-size:15px;font-weight:700;color:var(--txt);margin-bottom:6px">Menghubungkan ke ${name}...</div>
              <div style="font-size:12px;color:var(--txt3);line-height:1.5">Menghitung SHA-256 binary & mengirimkan payload OTA via TCP Socket Port 10000...</div>
            </div>`,
            [],
            '🚀'
          );
          Notify.toast('🚀 OTA Initiated', `Mempersiapkan pembaruan OTA untuk ${name}...`, 'info', 2000);
          try {
            const res = await DataService.fetch('/api/fleet/ota/trigger', {
              method: 'POST',
              body: JSON.stringify({ device_name: name })
            });
            if (res && (res.status === 'success' || res.ota_status === 'SUCCESS')) {
              const isOk = res.ota_status === 'SUCCESS';
              Modal.show(
                isOk ? `✅ OTA Update Berhasil Terkirim` : `⚠️ OTA Payload Queued`,
                `<div style="text-align:center;padding:18px">
                  <div style="font-size:44px;margin-bottom:12px">${isOk ? '🚀' : '⏳'}</div>
                  <div style="font-size:16px;font-weight:700;color:${isOk ? 'var(--green2)' : 'var(--orange)'};margin-bottom:10px">${isOk ? 'BERHASIL DIKIRIM (ONLINE)' : 'TERJADWAL / QUEUED'}</div>
                  <div style="font-size:12.5px;color:var(--txt);line-height:1.6;background:var(--glass);padding:12px;border-radius:8px;border:1px solid var(--border);margin-bottom:12px">${res.message}</div>
                  <div style="font-size:11.5px;color:var(--txt3);background:rgba(0,0,0,.2);padding:8px;border-radius:6px">Platform: <b style="color:var(--cyan)">${(res.platform || 'WINDOWS').toUpperCase()}</b> | Versi: <b style="color:var(--purple2)">${res.version || 'v1.1.0'}</b><br>SHA256: <span style="font-family:monospace;color:var(--cyan)">${(res.sha256 || '').substring(0, 20)}...</span></div>
                </div>`,
                [{ label: 'Tutup & Selesai', cls: 'btn-primary', fn: () => Modal.close() }],
                isOk ? '✅' : '⚠️'
              );
              Notify.toast(isOk ? '🚀 OTA Success' : '⏳ OTA Queued', res.message, isOk ? 'ok' : 'warn', 5000);
              if (window.LogStreamer) LogStreamer.add(isOk ? 'OK' : 'WARN', 'OTA', res.message);
            } else {
              const errMsg = res ? res.message : `Gagal mengirim sinyal OTA ke ${name}. Server tidak merespons.`;
              Modal.show(
                `❌ OTA Update Gagal`,
                `<div style="text-align:center;padding:18px">
                  <div style="font-size:44px;margin-bottom:12px">❌</div>
                  <div style="font-size:16px;font-weight:700;color:var(--red2);margin-bottom:10px">GAGAL MENGIRIM OTA UPDATE</div>
                  <div style="font-size:12.5px;color:var(--txt);background:rgba(239,68,68,.12);padding:12px;border-radius:8px;border:1px solid rgba(239,68,68,.3);margin-bottom:10px">${errMsg}</div>
                  <div style="font-size:11px;color:var(--txt3)">Pastikan service agen pada PC klien (${name}) sudah berjalan di port 10000.</div>
                </div>`,
                [{ label: 'Tutup', cls: 'btn-ghost', fn: () => Modal.close() }],
                '❌'
              );
              Notify.toast('❌ OTA Failed', errMsg, 'crit', 5000);
            }
          } catch (e) {
            Modal.show(
              `❌ OTA Error Exception`,
              `<div style="text-align:center;padding:18px">
                <div style="font-size:44px;margin-bottom:12px">💥</div>
                <div style="font-size:16px;font-weight:700;color:var(--red2);margin-bottom:10px">SYSTEM EXCEPTION ERROR</div>
                <div style="font-size:12.5px;color:var(--txt);background:rgba(239,68,68,.12);padding:12px;border-radius:8px;border:1px solid rgba(239,68,68,.3)">${e.message}</div>
              </div>`,
              [{ label: 'Tutup', cls: 'btn-ghost', fn: () => Modal.close() }],
              '💥'
            );
            Notify.toast('❌ OTA Error', e.message, 'crit', 5000);
          }
        },
        async deleteDevice(name) {
          Modal.confirm(
            `⚠️ Hapus Device`,
            `<div style="text-align:center;padding:8px">
          <div style="font-size:28px;margin-bottom:10px">🗑️</div>
          <div style="font-size:13px;font-weight:600;color:var(--txt)">Hapus <span style="color:var(--red2)">${name}</span>?</div>
          <div style="font-size:11px;color:var(--txt3);margin-top:6px">Device akan dihapus dari database fleet.<br>Data historis tetap tersimpan di telemetry_logs.</div>
        </div>`,
            async () => {
              Modal.close();
              const res = await DataService.fetch('/api/fleet/admin/devices/delete/' + encodeURIComponent(name), { method: 'DELETE' });
              if (res && (res.status === 'success' || res.ok)) {
                Modal.show(
                  `✅ Device Berhasil Dihapus`,
                  `<div style="text-align:center;padding:16px">
                    <div style="font-size:40px;margin-bottom:12px">🗑️</div>
                    <div style="font-size:15px;font-weight:700;color:var(--green2);margin-bottom:8px">PENGHAPUSAN BERHASIL (SUCCESS)</div>
                    <div style="font-size:12px;color:var(--txt);line-height:1.5;background:var(--glass);padding:12px;border-radius:6px;border:1px solid var(--border)">Perangkat <b style="color:var(--cyan)">${name}</b> telah berhasil dihapus dari database Fleet Management.</div>
                  </div>`,
                  [{ label: 'Selesai', cls: 'btn-primary', fn: () => Modal.close() }],
                  '✅'
                );
                Notify.toast('🗑️ Dihapus', `Device ${name} berhasil dihapus.`, 'ok');
                await DataService.loadDevices();
                Panels.fleet.load();
              } else {
                const errMsg = res ? (res.message || res.error) : `Gagal menghapus device ${name}. Server tidak merespons.`;
                Modal.show(
                  `❌ Penghapusan Gagal`,
                  `<div style="text-align:center;padding:16px">
                    <div style="font-size:40px;margin-bottom:12px">❌</div>
                    <div style="font-size:15px;font-weight:700;color:var(--red2);margin-bottom:8px">GAGAL MENGHAPUS DEVICE</div>
                    <div style="font-size:12px;color:var(--txt);background:rgba(239,68,68,.12);padding:12px;border-radius:6px;border:1px solid rgba(239,68,68,.3)">${errMsg}</div>
                  </div>`,
                  [{ label: 'Tutup', cls: 'btn-ghost', fn: () => Modal.close() }],
                  '❌'
                );
                Notify.toast('❌ Gagal', errMsg, 'warn');
              }
            }
          );
        },
        _render(devices) {
          this._devices = devices || [];
          let sites = DataService._sites || [];
          if (!sites || !Array.isArray(sites) || sites.length === 0) {
            const siteNames = [...new Set(this._devices.map(d => d.site || d.site_id || d.location || getSite(d.ip) || 'Kantor Pusat - NUC').filter(Boolean))];
            sites = siteNames.map((name, idx) => ({
              site_id: name === 'Kantor Pusat - NUC' ? 'HQ' : 'SITE-' + (idx + 1),
              site_name: name,
              router_ip: '10.20.0.1',
              criticality: 'HIGH'
            }));
          }

          setEl('fl-sites', sites.length);
          setEl('fl-total', this._devices.length);
          const offlineCount = this._devices.filter(d => d.status !== 'ONLINE').length;
          setEl('fl-offline', offlineCount);

          // Sites list panel
          htmlEl('fl-sites-list', sites.map((s, idx) => {
            const safeSiteKey = 'site_' + String(s.site_id || s.site_name || idx).replace(/[^a-zA-Z0-9_-]/g, '_');
            const siteDevs = devices.filter(d => (d.site_id === s.site_id) || (d.site === s.site_name) || (d.location === s.site_name) || (getSite(d.ip) === s.site_name));
            const ok = siteDevs.filter(d => d.status === 'ONLINE').length;
            const deleteBtn = `<button class="btn btn-xs" style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:var(--red2);padding:2px 6px;margin-left:4px;border-radius:4px;cursor:pointer" onclick="event.stopPropagation(); RemoteSettings.deleteSite('${s.site_id}', '${s.site_name}')" title="Hapus Site"><i class="fa-solid fa-trash-can" style="font-size:9px"></i> Hapus</button>`;
            const gwText = s.router_ip ? `<span style="font-size:10px;font-family:monospace;color:var(--cyan)">GW: ${s.router_ip}:${s.router_port || 80}</span>` : '<span style="font-size:10px;color:var(--txt3)">No Gateway</span>';
            return `<div class="li-row" style="padding:10px 12px;cursor:pointer;transition:background .2s" onclick="Panels.fleet.focusSite('${safeSiteKey}')" title="Klik untuk melipat / melihat perangkat di site ini">
          <div>
            <div style="font-weight:600;color:var(--txt);font-size:12px">🏢 ${s.site_name} <span style="font-size:10px;color:var(--txt3)">(${s.site_id})</span></div>
            <div style="margin-top:2px">${gwText}</div>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <span class="tag ${ok < siteDevs.length && siteDevs.length > 0 ? 'tag-orange' : (siteDevs.length > 0 ? 'tag-green' : 'tag-gray')}">${siteDevs.length ? ok + '/' + siteDevs.length + ' OK' : 'No Devices'}</span>
            ${deleteBtn}
          </div>
        </div>`;
          }).join(''));

          // 1. Render Tree View (Site -> Gateway Partitions -> Devices)
          const treeContainer = document.getElementById('fleet-tree-container');
          if (treeContainer) {
            if (!this.collapsed) this.collapsed = {};
            if (!this.collapsedGw) this.collapsedGw = {};
            let treeHtml = '';
            sites.forEach((s, idx) => {
              const safeSiteKey = 'site_' + String(s.site_id || s.site_name || idx).replace(/[^a-zA-Z0-9_-]/g, '_');
              const siteDevs = devices.filter(d => (d.site_id === s.site_id) || (d.site === s.site_name) || (d.location === s.site_name) || (getSite(d.ip) === s.site_name));
              const okDevs = siteDevs.filter(d => d.status === 'ONLINE').length;
              const statusBadge = siteDevs.length > 0
                ? (okDevs === siteDevs.length ? `<span class="tag tag-green">● ${okDevs}/${siteDevs.length} Online</span>` : `<span class="tag tag-orange">⚠️ ${okDevs}/${siteDevs.length} Online</span>`)
                : `<span class="tag tag-gray">No Devices</span>`;

              const isCollapsed = this.collapsed[safeSiteKey] || this.collapsed[s.site_id] || false;
              const displayStyle = isCollapsed ? 'display:none' : 'display:block';
              const iconClass = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';

              // Sub-group devices by Gateway Partition
              const gwGroups = {};
              siteDevs.forEach(d => {
                const gwIP = (d.gateway || (d.ip && d.ip.includes('.') ? (d.ip.split('.').slice(0, 3).join('.') + '.1') : '') || s.router_ip || '10.20.0.1');
                const subnet = gwIP.includes('.') ? (gwIP.split('.').slice(0, 3).join('.') + '.0/24') : '10.20.0.0/24';
                const gwKey = `${safeSiteKey}_gw_${gwIP.replace(/[^a-zA-Z0-9_-]/g, '_')}`;

                if (!gwGroups[gwKey]) {
                  gwGroups[gwKey] = {
                    gwKey: gwKey,
                    gwIP: gwIP,
                    subnet: subnet,
                    devices: [],
                    onlineCount: 0,
                    offlineCount: 0
                  };
                }
                if (d.status === 'ONLINE') gwGroups[gwKey].onlineCount++;
                else gwGroups[gwKey].offlineCount++;
                gwGroups[gwKey].devices.push(d);
              });

              const gwKeys = Object.keys(gwGroups);
              const gwPartitionsCount = gwKeys.length;

              let gwPartitionsHtml = '';
              if (siteDevs.length === 0) {
                gwPartitionsHtml = '<div style="font-size:11px;color:var(--txt3);padding:12px 0;text-align:center">Belum ada perangkat terdaftar di site ini.</div>';
              } else {
                gwPartitionsHtml = gwKeys.map(gk => {
                  const gwInfo = gwGroups[gk];
                  const isGwCollapsed = this.collapsedGw && this.collapsedGw[gwInfo.gwKey];
                  const gwDisplayStyle = isGwCollapsed ? 'display:none' : 'display:block';
                  const gwIconClass = isGwCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';

                  return `
                  <div style="background:rgba(15,23,42,0.45);border:1px solid rgba(6,182,212,0.18);border-radius:6px;margin-bottom:10px;overflow:hidden">
                    <div onclick="Panels.fleet.toggleGwTree('${gwInfo.gwKey}')" style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:rgba(6,182,212,0.06);cursor:pointer;user-select:none;border-bottom:1px solid rgba(6,182,212,0.15);transition:background .2s" onmouseover="this.style.background='rgba(6,182,212,0.12)'" onmouseout="this.style.background='rgba(6,182,212,0.06)'" title="Klik untuk melipat / membuka partisi gateway ini">
                      <div style="display:flex;align-items:center;gap:8px">
                        <button type="button" onclick="event.stopPropagation(); Panels.fleet.toggleGwTree('${gwInfo.gwKey}')" style="background:rgba(6,182,212,0.15);border:1px solid rgba(6,182,212,0.3);color:var(--cyan);width:22px;height:22px;border-radius:4px;display:flex;align-items:center;justify-content:center;cursor:pointer" title="Toggle Gateway ${gwInfo.gwIP}">
                          <i id="gw-tree-icon-${gwInfo.gwKey}" class="${gwIconClass}" style="font-size:10px"></i>
                        </button>
                        <span style="font-size:12px;font-weight:700;color:var(--txt)"><i class="fa-solid fa-network-wired" style="color:var(--cyan);margin-right:6px"></i>Partisi Gateway: <span style="font-family:monospace;color:var(--cyan)">${gwInfo.gwIP}</span></span>
                        <span style="font-size:10.5px;font-family:monospace;color:var(--purple2);background:rgba(168,85,247,0.1);padding:1px 6px;border-radius:4px">Subnet: ${gwInfo.subnet}</span>
                      </div>
                      <div style="display:flex;align-items:center;gap:8px">
                        <span class="tag ${gwInfo.onlineCount === gwInfo.devices.length ? 'tag-green' : 'tag-orange'}" style="font-size:9.5px">● ${gwInfo.onlineCount}/${gwInfo.devices.length} Online</span>
                        <button class="btn btn-ghost btn-xs" style="padding:2px 8px;font-size:9.5px" onclick="event.stopPropagation(); const sel=document.getElementById('remote-target-select'); if(sel){ sel.value='${gwInfo.devices[0]?.name || ''}'; sel.dispatchEvent(new Event('change')); } Remote.launch('ping');" title="Ping Gateway ${gwInfo.gwIP}"><i class="fa-solid fa-signal" style="margin-right:3px"></i>Ping GW</button>
                      </div>
                    </div>
                    <div id="gw-tree-body-${gwInfo.gwKey}" style="padding:8px 10px;${gwDisplayStyle}">
                      <table class="table-compact" style="width:100%;font-size:11px">
                        <thead>
                          <tr style="color:var(--txt3);border-bottom:1px solid rgba(255,255,255,.05);text-align:left">
                            <th style="padding:5px 6px">Device / Hostname</th>
                            <th style="padding:5px 6px">IP Address</th>
                            <th style="padding:5px 6px">Layer</th>
                            <th style="padding:5px 6px">Version</th>
                            <th style="padding:5px 6px">Status</th>
                            <th style="padding:5px 6px">Telemetry (CPU / RAM / Disk)</th>
                            <th style="padding:5px 6px">Last Seen</th>
                            <th style="padding:5px 6px;text-align:right">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${gwInfo.devices.map(d => {
                            const cpu = Math.round(d.cpu || 0);
                            const ram = Math.round(d.ram || 0);
                            const disk = Math.round(d.disk || 0);
                            return `<tr style="border-bottom:1px solid rgba(255,255,255,.03);cursor:pointer;transition:background .15s" onmouseover="this.style.background='rgba(255,255,255,.04)'" onmouseout="this.style.background='transparent'" onclick="event.stopPropagation(); Nav.go('pchealth'); setTimeout(() => { if (window.Panels && window.Panels.pchealth) Panels.pchealth.showDetail('${d.name}'); }, 150);" title="Klik untuk membuka detail &amp; diagnostik ${d.name}">
                              <td style="padding:6px;font-weight:600;color:var(--txt)">
                                <i class="fa-solid ${d.os_type === 'linux' ? 'fa-linux' : 'fa-desktop'}" style="margin-right:6px;color:var(--blue)"></i><span style="color:var(--cyan);text-decoration:underline;text-underline-offset:3px">${d.name}</span>
                              </td>
                              <td style="padding:6px;font-family:monospace;color:var(--cyan);font-size:10.5px">${d.ip || '—'}</td>
                              <td style="padding:6px"><span class="tag tag-blue" style="font-size:9px">L${d.layer || 1}</span></td>
                              <td style="padding:6px;font-size:10px;color:var(--purple2)">${d.version || d.agent_version || d.os_version || 'v2.0.0-Go'}</td>
                              <td style="padding:6px">${statusTag(d.status)}</td>
                              <td style="padding:6px">
                                <div style="display:flex;align-items:center;gap:6px;font-size:9.5px">
                                  <span style="min-width:40px">C: ${cpu}%</span>
                                  <span style="min-width:40px">R: ${ram}%</span>
                                  <span style="min-width:40px">D: ${disk}%</span>
                                </div>
                              </td>
                              <td style="padding:6px;font-size:10px;color:var(--txt2)">${timeSince(d.last_seen)}</td>
                              <td style="padding:6px;text-align:right" onclick="event.stopPropagation()">
                                <div style="display:flex;gap:4px;justify-content:flex-end">
                                  <button class="btn btn-warning btn-xs" style="padding:2px 6px;font-size:9.5px" onclick="event.stopPropagation(); Panels.fleet.pushOTA('${d.name}')" title="Push OTA Update"><i class="fa-solid fa-cloud-arrow-up"></i> OTA</button>
                                  <button class="btn btn-xs" style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:var(--red2);padding:2px 6px;border-radius:4px;cursor:pointer;font-size:9.5px" onclick="event.stopPropagation(); Panels.fleet.deleteDevice('${d.name}')"><i class="fa-solid fa-trash-can" style="font-size:9px"></i> Hapus</button>
                                </div>
                              </td>
                            </tr>`;
                          }).join('')}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  `;
                }).join('');
              }

              treeHtml += `
            <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:8px;margin-bottom:12px;overflow:hidden">
              <div onclick="Panels.fleet.toggleSiteTree('${safeSiteKey}')" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(255,255,255,.03);cursor:pointer;user-select:none;border-bottom:1px solid var(--border);transition:background .2s" onmouseover="this.style.background='rgba(255,255,255,.07)'" onmouseout="this.style.background='rgba(255,255,255,.03)'" title="Klik untuk melipat / membuka site ini">
                <div style="display:flex;align-items:center;gap:10px">
                  <button type="button" onclick="event.stopPropagation(); Panels.fleet.toggleSiteTree('${safeSiteKey}')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:var(--cyan);width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer" title="Toggle ${s.site_name}">
                    <i id="site-tree-icon-${safeSiteKey}" class="${iconClass}" style="font-size:11px"></i>
                  </button>
                  <span style="font-size:14px;font-weight:700;color:var(--txt)">🏢 ${s.site_name}</span>
                  <span style="font-size:11px;font-family:monospace;color:var(--cyan);background:rgba(34,211,238,.1);padding:2px 8px;border-radius:4px"><i class="fa-solid fa-network-wired" style="margin-right:4px"></i>GW Utama: ${s.router_ip || '10.20.0.1'}</span>
                  <span style="font-size:10.5px;color:var(--purple2);background:rgba(168,85,247,.1);padding:2px 6px;border-radius:4px">${gwPartitionsCount} Partisi Gateway</span>
                  <span style="font-size:10px;color:var(--txt3);background:var(--glass);padding:2px 6px;border-radius:4px">Prioritas: ${s.criticality || 'HIGH'}</span>
                </div>
                <div style="display:flex;align-items:center;gap:12px">
                  ${statusBadge}
                  <span style="font-size:11px;color:var(--txt3)"><i class="fa-solid fa-desktop" style="margin-right:4px"></i>${siteDevs.length} Perangkat</span>
                </div>
              </div>
              <div id="site-tree-body-${safeSiteKey}" style="padding:10px 14px;${displayStyle}">
                ${gwPartitionsHtml}
              </div>
            </div>
              `;
            });

            // Devices with unassigned site
            const unassignedDevs = devices.filter(d => !sites.some(s => s.site_id === d.site_id || s.site_name === d.site || s.site_name === d.location || s.site_name === getSite(d.ip)));
            if (unassignedDevs.length > 0) {
              const safeUnassignedKey = 'site_unassigned';
              const isCollapsed = this.collapsed[safeUnassignedKey] || this.collapsed['unassigned'] || false;
              const displayStyle = isCollapsed ? 'display:none' : 'display:block';
              const iconClass = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';

              treeHtml += `
            <div style="background:var(--card-bg);border:1px dashed var(--border);border-radius:8px;margin-bottom:12px;overflow:hidden">
              <div onclick="Panels.fleet.toggleSiteTree('${safeUnassignedKey}')" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(255,255,255,.01);cursor:pointer;user-select:none;border-bottom:1px solid var(--border);transition:background .2s" onmouseover="this.style.background='rgba(255,255,255,.05)'" onmouseout="this.style.background='rgba(255,255,255,.01)'" title="Klik untuk melipat / membuka perangkat tanpa site">
                <div style="display:flex;align-items:center;gap:10px">
                  <button type="button" onclick="event.stopPropagation(); Panels.fleet.toggleSiteTree('${safeUnassignedKey}')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:var(--cyan);width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer">
                    <i id="site-tree-icon-${safeUnassignedKey}" class="${iconClass}" style="font-size:11px"></i>
                  </button>
                  <span style="font-size:14px;font-weight:700;color:var(--txt2)">🌐 Unassigned Devices</span>
                </div>
                <span style="font-size:11px;color:var(--txt3)"><i class="fa-solid fa-desktop" style="margin-right:4px"></i>${unassignedDevs.length} Perangkat</span>
              </div>
              <div id="site-tree-body-${safeUnassignedKey}" style="padding:10px 14px;${displayStyle}">
                <table class="table-compact" style="width:100%;font-size:11.5px">
                  <thead>
                    <tr style="color:var(--txt3);border-bottom:1px solid rgba(255,255,255,.05);text-align:left">
                      <th style="padding:6px 8px">Device</th>
                      <th style="padding:6px 8px">IP</th>
                      <th style="padding:6px 8px">Version</th>
                      <th style="padding:6px 8px">Status</th>
                      <th style="padding:6px 8px">Last Seen</th>
                      <th style="padding:6px 8px;text-align:right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${unassignedDevs.map(d => `<tr style="border-bottom:1px solid rgba(255,255,255,.03);cursor:pointer" onclick="event.stopPropagation(); Nav.go('pchealth'); setTimeout(() => { if (window.Panels && window.Panels.pchealth) Panels.pchealth.showDetail('${d.name}'); }, 150);" title="Klik untuk membuka detail ${d.name}">
                      <td style="padding:8px;font-weight:600;color:var(--txt)"><span style="color:var(--cyan);text-decoration:underline;text-underline-offset:3px">${d.name}</span></td>
                      <td style="padding:8px;font-family:monospace;color:var(--cyan);font-size:11px">${d.ip || '—'}</td>
                      <td style="padding:8px;font-size:10.5px;color:var(--purple2)">${d.version || d.agent_version || d.os_version || 'v2.0.0-Go'}</td>
                      <td style="padding:8px">${statusTag(d.status)}</td>
                      <td style="padding:8px;font-size:10.5px;color:var(--txt2)">${timeSince(d.last_seen)}</td>
                      <td style="padding:8px;text-align:right" onclick="event.stopPropagation()">
                        <div style="display:flex;gap:6px;justify-content:flex-end">
                          <button class="btn btn-warning btn-xs" onclick="event.stopPropagation(); Panels.fleet.pushOTA('${d.name}')" title="Push OTA Update"><i class="fa-solid fa-cloud-arrow-up"></i> OTA</button>
                        </div>
                      </td>
                    </tr>`).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          `;
            }
            treeContainer.innerHTML = treeHtml;
          }

          // 2. Render Flat Fleet table
          const tbody = document.getElementById('tbody-fleet');
          if (tbody) tbody.innerHTML = devices.map(d => `<tr>
        <td><b>${d.name}</b></td><td style="font-family:'JetBrains Mono',monospace;font-size:10px">${d.ip || '—'}</td>
        <td><span class="tag tag-blue">L${d.layer || '?'}</span></td>
        <td>${d.site || getSite(d.ip) || d.location || '—'}</td>
        <td style="font-size:10.5px;color:var(--purple2)">${d.version || d.agent_version || d.os_version || 'v2.0.0-Go'}</td>
        <td>${statusTag(d.status)}</td>
        <td style="font-size:10px;color:var(--txt2)">${timeSince(d.last_seen)}</td>
        <td>
          <div style="display:flex;gap:6px;align-items:center">
            <button class="btn btn-warning btn-xs" onclick="event.stopPropagation(); Panels.fleet.pushOTA('${d.name}')" title="Push OTA Update"><i class="fa-solid fa-cloud-arrow-up"></i> OTA</button>
            <button class="btn btn-xs" style="background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:var(--red2);padding:2px 6px;border-radius:4px;cursor:pointer" onclick="event.stopPropagation(); Panels.fleet.deleteDevice('${d.name}')" title="Hapus Device"><i class="fa-solid fa-trash-can" style="font-size:9px"></i> Hapus</button>
          </div>
        </td>
      </tr>`).join('');
          setEl('fl-count-txt', devices.length + ' devices');

          // 3. Render per-site Health Gauge Bars (custom SVG)
          const siteMap = {};
          devices.forEach(d => {
            const s = d.site || getSite(d.ip) || d.location || 'Other';
            if (!siteMap[s]) siteMap[s] = { total: 0, online: 0, devices: [] };
            siteMap[s].total++;
            if (d.status === 'ONLINE') siteMap[s].online++;
            siteMap[s].devices.push(d);
          });

          const gaugeContainer = document.getElementById('fleet-health-gauges');
          if (!gaugeContainer) return;

          const paletteColors = ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#ec4899'];
          const siteNames = Object.keys(siteMap);

          if (siteNames.length === 0) {
            gaugeContainer.innerHTML = '<div style="text-align:center;color:var(--txt3);font-size:12px;padding:20px">Tidak ada data perangkat</div>';
            return;
          }

          gaugeContainer.innerHTML = siteNames.map((siteName, idx) => {
            const info = siteMap[siteName];
            const pct = info.total > 0 ? Math.round((info.online / info.total) * 100) : 0;
            const color = pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444';
            const paletteColor = paletteColors[idx % paletteColors.length];

            // SVG half-donut gauge parameters
            const r = 36, cx = 50, cy = 50, stroke = 7;
            const circumference = Math.PI * r; // half circle circumference
            const dashOffset = circumference * (1 - pct / 100);

            // Status badge
            const statusBadge = pct === 100
              ? `<span style="background:rgba(34,197,94,.18);color:#22c55e;border:1px solid rgba(34,197,94,.35);border-radius:4px;font-size:9px;padding:1px 6px;font-weight:700">ALL OK</span>`
              : pct === 0
                ? `<span style="background:rgba(239,68,68,.18);color:#ef4444;border:1px solid rgba(239,68,68,.3);border-radius:4px;font-size:9px;padding:1px 6px;font-weight:700">OFFLINE</span>`
                : `<span style="background:rgba(245,158,11,.18);color:#f59e0b;border:1px solid rgba(245,158,11,.3);border-radius:4px;font-size:9px;padding:1px 6px;font-weight:700">PARTIAL</span>`;

            return `
          <div style="display:flex;align-items:center;gap:14px;background:var(--glass);border-radius:10px;padding:10px 14px;border:1px solid rgba(255,255,255,.05)">
            <!-- SVG half-donut gauge -->
            <div style="position:relative;flex-shrink:0;width:80px;height:48px;overflow:hidden">
              <svg viewBox="0 0 100 55" width="80" height="48" style="overflow:visible">
                <!-- Track arc (gray) -->
                <path
                  d="M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}"
                  fill="none"
                  stroke="rgba(255,255,255,.08)"
                  stroke-width="${stroke}"
                  stroke-linecap="round"
                />
                <!-- Value arc (colored) -->
                <path
                  d="M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}"
                  fill="none"
                  stroke="${color}"
                  stroke-width="${stroke}"
                  stroke-linecap="round"
                  stroke-dasharray="${circumference}"
                  stroke-dashoffset="${dashOffset}"
                  style="filter:drop-shadow(0 0 4px ${color}60)"
                />
                <!-- Center percentage text -->
                <text x="${cx}" y="${cy + 2}" text-anchor="middle" font-size="13" font-weight="700" fill="${color}">${pct}%</text>
              </svg>
            </div>
            <!-- Site info -->
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                <span style="width:8px;height:8px;border-radius:50%;background:${paletteColor};flex-shrink:0"></span>
                <span style="font-size:11.5px;font-weight:700;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${siteName}">${siteName}</span>
                ${statusBadge}
              </div>
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                <span style="font-size:10px;color:var(--txt3)"><i class="fa-solid fa-desktop" style="margin-right:3px;color:${paletteColor}"></i>${info.total} perangkat</span>
                <span style="font-size:10px;color:#22c55e"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:3px"></i>${info.online} online</span>
                <span style="font-size:10px;color:#ef4444"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:3px"></i>${info.total - info.online} offline</span>
              </div>
              <!-- Progress bar -->
              <div style="height:4px;background:rgba(255,255,255,.06);border-radius:9999px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,${color}88,${color});border-radius:9999px;transition:width .6s cubic-bezier(.4,0,.2,1)"></div>
              </div>
            </div>
          </div>`;
          }).join('');
        }
      },

      /* ---- INCIDENT TRIAGE PANEL ---- */

});
