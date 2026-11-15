/* panels/pc-health.js
 * PC Health panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      pchealth: {
        _allCards: [],
        async load() {
          const devices = await DataService.loadDevices();
          this._render(devices);
          this._populateRemoteSelect(devices);
          // Populate site filter dropdown
          const siteSelect = document.getElementById('pc-filter-site');
          if (siteSelect) {
            const sites = [...new Set(devices.map(d => getSite(d.ip) || d.location || '').filter(Boolean))];
            const currentVal = siteSelect.value;
            siteSelect.innerHTML = '<option value="">Semua Site</option>' + sites.map(s => `<option value="${s}">${s}</option>`).join('');
            if (currentVal) siteSelect.value = currentVal;
          }
        },
        toggleSitePartition(partKey) {
          if (!this.collapsed) this.collapsed = {};
          this.collapsed[partKey] = !this.collapsed[partKey];
          const el = document.getElementById('pc-part-body-' + partKey);
          const icon = document.getElementById('pc-part-icon-' + partKey);
          if (el) {
            if (this.collapsed[partKey]) {
              el.style.display = 'none';
              if (icon) icon.className = 'fa-solid fa-chevron-right';
            } else {
              el.style.display = 'grid';
              if (icon) icon.className = 'fa-solid fa-chevron-down';
            }
          }
        },
        _render(devices) {
          const grid = document.getElementById('pc-grid');
          if (!grid) return;
          // Filter out printers to show only PCs
          const pcs = devices.filter(d => !(d.name || '').toLowerCase().includes('printer') && !(d.metadata && d.metadata.type === 'printer'));
          const isOff = d => d.status !== 'ONLINE';

          if (pcs.length === 0) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--txt3)"><i class="fa-solid fa-desktop" style="font-size:32px;margin-bottom:10px;display:block;opacity:.3"></i><div>Tidak ada PC terdaftar.</div></div>';
            this._allCards = [];
            return;
          }

          // Group PCs by Site & Router Gateway IP
          const siteGroups = {};
          pcs.forEach(d => {
            const site = getSite(d.ip) || d.location || 'Kantor Pusat - NUC';
            const gw = (d.ip && d.ip.includes('.')) ? (d.ip.split('.').slice(0, 3).join('.') + '.1') : (d.gateway || '192.168.1.1');
            const groupKey = site + '___' + gw;
            if (!siteGroups[groupKey]) {
              siteGroups[groupKey] = {
                siteName: site,
                gatewayIP: gw,
                onlineCount: 0,
                offlineCount: 0,
                devices: []
              };
            }
            if (isOff(d)) {
              siteGroups[groupKey].offlineCount++;
            } else {
              siteGroups[groupKey].onlineCount++;
            }
            siteGroups[groupKey].devices.push(d);
          });

          let html = '';
          Object.values(siteGroups).forEach(group => {
            const total = group.devices.length;
            const safeKey = 'pc_part_' + (group.siteName + '_' + group.gatewayIP).replace(/[^a-zA-Z0-9_-]/g, '_');
            const isCollapsed = this.collapsed && this.collapsed[safeKey];
            const displayStyle = isCollapsed ? 'display:none' : 'display:grid';
            const iconClass = isCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-down';
            const siteBadgeCls = group.offlineCount > 0 ? 'border: 1px solid rgba(239,68,68,.35)' : 'border: 1px solid rgba(16,185,129,.35)';
            html += `
              <div class="site-block-section" data-site-group="${group.siteName}" style="grid-column:1/-1;margin-bottom:20px;background:rgba(15,23,42,.6);border-radius:12px;padding:16px;box-shadow:0 4px 20px rgba(0,0,0,.25);${siteBadgeCls}">
                <div class="site-block-header" onclick="Panels.pchealth.toggleSitePartition('${safeKey}')" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.08);cursor:pointer;user-select:none;transition:background .2s" title="Klik untuk melipat / membuka partisi site ini">
                  <div style="display:flex;align-items:center;gap:10px">
                    <button type="button" onclick="event.stopPropagation(); Panels.pchealth.toggleSitePartition('${safeKey}')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:var(--cyan);width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer" title="Toggle Partisi ${group.siteName}">
                      <i id="pc-part-icon-${safeKey}" class="${iconClass}" style="font-size:11px"></i>
                    </button>
                    <div style="width:34px;height:34px;border-radius:8px;background:rgba(59,130,246,.15);display:flex;align-items:center;justify-content:center;color:var(--blue);font-size:16px">
                      <i class="fa-solid fa-building-circle-check"></i>
                    </div>
                    <div>
                      <div style="font-size:13.5px;font-weight:700;color:var(--txt);letter-spacing:0.2px">🏢 ${group.siteName}</div>
                      <div style="font-size:11px;color:var(--txt3);display:flex;align-items:center;gap:6px">
                        <span style="background:rgba(6,182,212,.12);color:var(--cyan);padding:1px 6px;border-radius:4px;font-family:monospace;font-weight:600"><i class="fa-solid fa-network-wired" style="margin-right:4px"></i>GW: ${group.gatewayIP}</span>
                        <span>· Subnet Connected</span>
                      </div>
                    </div>
                  </div>
                  <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-size:11px;font-weight:600;background:rgba(16,185,129,.15);color:var(--green);padding:4px 10px;border-radius:6px;border:1px solid rgba(16,185,129,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.onlineCount} Online</span>
                    ${group.offlineCount > 0 ? `<span style="font-size:11px;font-weight:600;background:rgba(239,68,68,.15);color:var(--red2);padding:4px 10px;border-radius:6px;border:1px solid rgba(239,68,68,.25)"><i class="fa-solid fa-circle" style="font-size:7px;margin-right:5px"></i>${group.offlineCount} Offline</span>` : ''}
                    <span style="font-size:11px;color:var(--txt3);background:rgba(255,255,255,.05);padding:4px 8px;border-radius:6px">${total} PC</span>
                  </div>
                </div>
                <div id="pc-part-body-${safeKey}" class="site-device-subgrid" style="${displayStyle};grid-template-columns:repeat(auto-fill, minmax(260px, 1fr));gap:12px">
            `;

            group.devices.forEach(d => {
              const offline = isOff(d);
              const meta = d.metadata || {};
              const hw = (() => { try { return (typeof d.hardware_info === 'string') ? JSON.parse(d.hardware_info) : (d.hardware_info || {}); } catch (e) { return {}; } })();
              const site = group.siteName;
              const cpu = Math.round(d.cpu || (hw && (hw.cpu_usage || hw.cpu_percent)) || (meta && meta.cpu) || 0);
              const ram = Math.round(d.ram || (hw && (hw.ram_usage || hw.mem_percent)) || (meta && meta.ram) || 0);
              const statusBadge = offline
                ? `<span class="dc-rt-status dc-rt-offline"><span class="dc-rt-pulse"></span>OFFLINE</span>`
                : `<span class="dc-rt-status dc-rt-online"><span class="dc-rt-pulse"></span>ONLINE</span>`;
              html += `<div class="device-card ${offline ? 'offline dc-offline' : 'dc-online'}" data-name="${(d.name || '').toLowerCase()}" data-status="${d.status}" data-site="${site}" id="dc-card-${(d.name || '').replace(/[^a-zA-Z0-9]/g, '-')}" onclick="Panels.pchealth.showDetail('${d.name || ''}')">
            <button class="dc-delete-btn" title="Hapus Device" onclick="event.stopPropagation(); Panels.pchealth.confirmDelete('${d.name || ''}')"><i class="fa-solid fa-xmark"></i></button>
            <div class="dc-name" style="padding-left:20px">${getDeviceIcon(d.layer)} <span class="dc-device-name-text" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${d.name || ''}">${d.name || 'Unidentified'}</span> <span class="dc-rt-badge" id="rt-badge-${(d.name || '').replace(/[^a-zA-Z0-9]/g, '-')}">${statusBadge}</span></div>
            <div class="dc-row"><span class="dc-lbl">IP</span><span class="dc-val" style="font-family:monospace;font-weight:600">${d.ip || '—'}</span></div>
            <div class="dc-row"><span class="dc-lbl">Gateway</span><span class="dc-val" style="font-family:monospace;color:var(--cyan)">${group.gatewayIP}</span></div>
            <div class="dc-row"><span class="dc-lbl">Last Seen</span><span class="dc-val dc-last-seen" id="rt-lastseen-${(d.name || '').replace(/[^a-zA-Z0-9]/g, '-')}" style="color:${offline ? 'var(--red2)' : 'var(--txt2)'}"> ${timeSince(d.last_seen)}</span></div>
            ${meta.hostname ? `<div class="dc-row"><span class="dc-lbl">Hostname</span><span class="dc-val">${meta.hostname}</span></div>` : ''}
            ${!offline ? `<div style="margin-top:8px"><div class="pb-wrap"><div class="pb-label"><span>CPU</span><span>${cpu}%</span></div><div class="pb"><div class="pb-fill ${pbColor(cpu)}" style="width:${cpu}%;animation:none"></div></div></div><div class="pb-wrap"><div class="pb-label"><span>RAM</span><span>${ram}%</span></div><div class="pb"><div class="pb-fill ${pbColor(ram)}" style="width:${ram}%;animation:none"></div></div></div></div>` : '<div style="margin-top:8px"><div class="pb"><div class="pb-fill pb-red" style="width:100%;animation:none"></div></div><div style="font-size:10px;color:var(--red2);text-align:center;margin-top:4px">DEVICE OFFLINE</div></div>'}
            <div style="display:flex;gap:4px;margin-top:8px">
              <button class="btn btn-ghost btn-xs" style="flex:1;display:flex;align-items:center;justify-content:center;gap:4px" onclick="event.stopPropagation(); const sel=document.getElementById('remote-target-select'); if(sel){ sel.value='${d.name}'; sel.dispatchEvent(new Event('change')); } Remote.launch('ping');"><i class="fa-solid fa-signal"></i> Ping</button>
              <button class="btn btn-primary btn-xs" style="flex:1" onclick="event.stopPropagation(); Remote.launchDefault('${d.name || ''}');"><i class="fa-solid fa-desktop" style="margin-right:4px"></i> Remote</button>
            </div>
          </div>`;
            });

            html += `</div></div>`;
          });

          grid.innerHTML = html;
          this._allCards = Array.from(grid.querySelectorAll('.device-card'));
          this.applyFilters();
          // Start real-time status polling if not already running
          this._startStatusPolling();
        },
        _startStatusPolling() {
          if (window.ActiveIntervals.pchealth_status) return; // already running
          window.ActiveIntervals.pchealth_status = setInterval(() => this._pollDeviceStatus(), 30000);
        },
        async _pollDeviceStatus() {
          // Only poll when PC Health panel is active
          const panel = document.getElementById('p-pchealth');
          if (!panel || !panel.classList.contains('active')) return;
          try {
            const devices = await DataService.loadDevices();
            if (!devices || !devices.length) return;
            // Live-patch each card badge without re-rendering the whole grid
            devices.forEach(d => {
              const safeName = (d.name || '').replace(/[^a-zA-Z0-9]/g, '-');
              const badge = document.getElementById('rt-badge-' + safeName);
              const card = document.getElementById('dc-card-' + safeName);
              const lastSeenEl = document.getElementById('rt-lastseen-' + safeName);
              if (!badge || !card) return;
              const isOnline = d.status === 'ONLINE';
              // Update badge
              badge.innerHTML = isOnline
                ? `<span class="dc-rt-status dc-rt-online"><span class="dc-rt-pulse"></span>ONLINE</span>`
                : `<span class="dc-rt-status dc-rt-offline"><span class="dc-rt-pulse"></span>OFFLINE</span>`;
              // Update card border class
              card.classList.toggle('dc-online', isOnline);
              card.classList.toggle('dc-offline', !isOnline);
              card.classList.toggle('offline', !isOnline);
              card.setAttribute('data-status', d.status);
              // Update last seen
              if (lastSeenEl) {
                lastSeenEl.textContent = ' ' + timeSince(d.last_seen);
                lastSeenEl.style.color = isOnline ? 'var(--txt2)' : 'var(--red2)';
              }
            });
            // Re-apply search/filter without full re-render
            this.applyFilters();
          } catch (e) { console.warn('[PCHealth] Poll error:', e); }
        },
        async confirmDelete(name) {
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
              if (res && res.status === 'success') {
                Notify.toast('🗑️ Dihapus', `Device ${name} berhasil dihapus.`, 'ok');
                // Remove card from DOM immediately
                const safeName = (name || '').replace(/[^a-zA-Z0-9]/g, '-');
                const card = document.getElementById('dc-card-' + safeName);
                if (card) { card.style.transition = 'opacity .3s,transform .3s'; card.style.opacity = '0'; card.style.transform = 'scale(.9)'; setTimeout(() => card.remove(), 320); }
                // Refresh device list
                DataService.loadDevices();
              } else {
                Notify.toast('❌ Gagal', `Gagal menghapus device ${name}.`, 'warn');
              }
            }
          );
        },
        closeDetail() {
          const card = document.getElementById('pc-detail-card');
          if (card) card.style.display = 'none';
          if (window._pcDetailTimer) {
            clearInterval(window._pcDetailTimer);
            window._pcDetailTimer = null;
          }
          window._activeDetailDevice = null;
        },
        refreshCurrentDetail() {
          if (window._activeDetailDevice) {
            this.showDetail(window._activeDetailDevice, false);
          }
        },
        async showDetail(name, isSilent = false) {
          if (!name && DataService._devices && DataService._devices.length > 0) {
            name = DataService._devices[0].name;
          }
          if (!name) return;
          const d = (DataService._devices || []).find(x => x.name === name) || { name: name, status: 'ONLINE', ip: '' };
          const card = document.getElementById('pc-detail-card');
          const body = document.getElementById('pc-detail-body');
          const title = document.getElementById('pc-detail-title');
          if (!card || !body) return;

          if (window._pcDetailFetching && isSilent) return;
          window._pcDetailFetching = true;

          window._activeDetailDevice = name;

          title.innerHTML = `<i class="fa-solid fa-desktop" style="margin-right:8px;color:var(--blue)"></i>Detail: ${name} ${d.status === 'ONLINE' ? '<span class="tag tag-green">ONLINE</span>' : '<span class="tag tag-orange">OFFLINE</span>'}`;
          card.style.display = 'block';

          if (!window._pcDetailTimer) {
            window._pcDetailTimer = setInterval(() => {
              const activeCard = document.getElementById('pc-detail-card');
              if (activeCard && activeCard.style.display !== 'none' && window._activeDetailDevice) {
                Panels.pchealth.showDetail(window._activeDetailDevice, true);
              } else {
                if (window._pcDetailTimer) {
                  clearInterval(window._pcDetailTimer);
                  window._pcDetailTimer = null;
                }
              }
            }, 3000);
          }

          if (!isSilent) {
            body.innerHTML = `
        <div style="text-align:center;padding:40px;color:var(--txt2)">
          <i class="fa-solid fa-spinner fa-spin" style="font-size:24px;margin-bottom:12px;color:var(--blue)"></i>
          <div>Menjalankan Deep Diagnostics pada ${name}...</div>
          <div style="font-size:11px;color:var(--txt3);margin-top:4px">Menghubungkan ke Agent via TCP Socket port 10000...</div>
        </div>
      `;
          }

          const meta = d.metadata || {};
          let itemsHtml = '<div style="text-align:center;padding:8px;color:var(--txt3);font-size:11px">Memuat data telemetry...</div>';

          try {
            const resp = await DataService.fetch('/api/agent_deep_diagnostics/' + encodeURIComponent(name), {
              signal: AbortSignal.timeout(15000)
            });

            if (!resp || !resp.agent_data) {
              throw new Error((resp && resp.error) || 'Gagal mengambil data agent dari server.');
            }

            const diag = resp.agent_data;
            const net = diag.network_advanced || {};
            const dataSource = diag.data_source || 'unknown';
            const dataSourceBadge = dataSource === 'live_agent'
              ? '<span class="tag tag-green" style="margin-left:8px">🟢 Live Agent</span>'
              : '<span class="tag tag-orange" style="margin-left:8px">🗄️ DB Snapshot</span>';

            // ─── Rebuild base metrics from agent data ────────────────────────────
            const cpuV = diag.cpu_usage || meta.cpu || 0;
            const ramV = diag.ram_usage || meta.ram || 0;
            const diskV = diag.disk_usage || meta.disk || 0;
            const agentBuild = diag.agent_build || meta.agent_build || '—';
            const agentVersion = diag.agent_version || meta.agent_version || '—';
            const bitlocker = diag.bitlocker || meta.bitlocker || '—';
            const firewallStatus = (diag.firewall !== undefined ? diag.firewall : meta.firewall);
            const cpuColor = cpuV > 85 ? 'var(--red2)' : cpuV > 60 ? 'var(--orange2)' : 'var(--green2)';
            const ramColor = ramV > 90 ? 'var(--red2)' : ramV > 70 ? 'var(--orange2)' : 'var(--txt)';
            const diskColor = diskV > 90 ? 'var(--red2)' : diskV > 75 ? 'var(--orange2)' : 'var(--txt)';

            const baseMetricsArr = [
              { k: 'CPU Usage', v: `${cpuV}%`, color: cpuColor },
              { k: 'RAM Usage', v: `${ramV}%`, color: ramColor },
              { k: 'Disk Usage', v: `${diskV}%`, color: diskColor },
              { k: 'Agent Build', v: agentBuild, color: 'var(--blue)' },
              { k: 'Agent Version', v: agentVersion, color: 'var(--txt)' },
              { k: 'OS Version', v: diag.os_version || meta.os_version || 'Windows', color: 'var(--txt)' },
              { k: 'Bitlocker', v: bitlocker, color: bitlocker === 'Protected' ? 'var(--green2)' : 'var(--orange2)' },
              { k: 'Firewall', v: firewallStatus ? '🛡️ Enabled' : '⚠️ Disabled', color: firewallStatus ? 'var(--green2)' : 'var(--red2)' },
              { k: 'IP Address', v: resp.ip || d.ip || '—', color: 'var(--txt)' },
            ];
            const updatedTimeStr = diag.updated_at || new Date().toLocaleTimeString();
            itemsHtml = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <span style="font-size:11px;color:var(--txt3)">Sumber data: ${dataSourceBadge}</span>
          <span style="font-size:10px;color:var(--txt3)">Terakhir diperbarui: <strong>${updatedTimeStr}</strong> · Auto-refresh 8s</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px;margin-bottom:15px">`
              + baseMetricsArr.map(i => `<div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase;letter-spacing:.5px">${i.k}</div><div style="font-size:13px;font-weight:600;color:${i.color || 'var(--txt)'};margin-top:3px">${i.v}</div></div>`).join('')
              + '</div>';

            // 1. Build Network Monitoring section
            let netHtml = `
          <div class="card-sec" style="margin-top:15px">
            <h4 style="margin-bottom:8px;color:var(--blue);font-size:12px;font-weight:700"><i class="fa-solid fa-network-wired" style="margin-right:6px"></i>Network Monitoring</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px">
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Client IP Address</div><div style="font-size:12px;font-weight:600;color:var(--cyan);margin-top:2px">${diag.ip || net.ip || '—'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Gateway IP</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.gateway || '—'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">DNS Server</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.dns || '—'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">DHCP</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.dhcp || '—'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">MAC Address</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.mac || '—'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">VPN Status</div><div style="font-size:12px;font-weight:600;color:${net.vpn_status === 'Connected' ? 'var(--green2)' : 'var(--txt)'};margin-top:2px">${net.vpn_status || 'Disconnected'}</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px">
                <div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">WiFi</div>
                <div style="font-size:11px;font-weight:600;color:${net.wifi_ssid ? 'var(--green2)' : 'var(--txt3)'};margin-top:2px">
                  ${net.wifi_ssid ? '📶 ' + net.wifi_ssid : '📵 Disconnected'}
                </div>
                ${net.wifi_signal && net.wifi_ssid ? `<div style="font-size:10px;color:var(--txt3)">${net.wifi_signal}</div>` : ''}
                ${net.wifi_bssid ? `<div style="font-size:9px;color:var(--txt3)">${net.wifi_bssid} ${net.wifi_channel ? '· Ch.' + net.wifi_channel : ''}</div>` : ''}
              </div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Bandwidth Rate</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">⬇️ ${typeof net.bandwidth_download_kbps === 'number' ? net.bandwidth_download_kbps.toFixed(0) : (net.bandwidth_download_kbps || 0)} KB/s · ⬆️ ${typeof net.bandwidth_upload_kbps === 'number' ? net.bandwidth_upload_kbps.toFixed(0) : (net.bandwidth_upload_kbps || 0)} KB/s</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Packet Loss & Jitter</div><div style="font-size:12px;font-weight:600;color:${(net.packet_loss_pct > 0) ? 'var(--red2)' : 'var(--txt)'};margin-top:2px">${net.packet_loss_pct || 0}% Loss · ${net.jitter_ms || 0} ms Jitter</div></div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px"><div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">Ping Latency</div><div style="font-size:12px;font-weight:600;color:var(--txt);margin-top:2px">${net.ping_latency_ms || 0} ms</div></div>
            </div>
          </div>
        `;

            // 2. Build Enterprise Web App Usage & Multi-Browser Tab Monitoring
            let websHtml = window.BrowserMonitoring ? window.BrowserMonitoring.renderSection(diag, name || (d && d.name) || '') : '';
            if (!websHtml) {
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
              <h4 style="margin-bottom:8px;color:var(--purple);font-size:12px;font-weight:700"><i class="fa-solid fa-cubes" style="margin-right:6px"></i>Aplikasi & Window Aktif</h4>
              <table class="tbl" style="width:100%;font-size:11px">
                <thead>
                  <tr>
                    <th style="text-align:left;width:120px">Nama Proses</th>
                    <th style="text-align:left">Window Title</th>
                    <th style="text-align:left;width:60px">PID</th>
                  </tr>
                </thead>
                <tbody>
                  ${diag.apps.slice(0, 10).map(app => `
                    <tr>
                      <td style="font-weight:600;color:var(--txt)">${app.Name || app.ProcessName || 'Unknown'}</td>
                      <td style="color:var(--txt2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:250px">${app.MainWindowTitle || '—'}</td>
                      <td>${app.Id || app.PID || '—'}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
              ${diag.apps.length > 10 ? `<div style="font-size:9px;color:var(--txt3);margin-top:4px;text-align:right">+ ${diag.apps.length - 10} aplikasi lainnya</div>` : ''}
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
                      <td style="font-weight:600;color:var(--txt)">${p.name}</td>
                      <td>${p.port || '—'}</td>
                      <td><span class="tag ${p.status === 'ONLINE' ? 'tag-green' : 'tag-orange'}">${p.status}</span></td>
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
              const usbTypeIcon = (t, d) => {
                const tl = ((t || '') + ' ' + (d || '')).toLowerCase();
                if (tl.includes('scanner') || tl.includes('barcode') || tl.includes('reader') || tl.includes('symbol') || tl.includes('honeywell') || tl.includes('datalogic') || tl.includes('zebra') || tl.includes('sunmi') || tl.includes('code') || tl.includes('posbarcodescanner') || tl.includes('wia')) return '📷';
                if (tl.includes('printer')) return '🖨️';
                if (tl.includes('hub')) return '🔌';
                if (tl.includes('storage') || tl.includes('diskdrive')) return '💾';
                if (tl.includes('camera') || tl.includes('webcam') || tl.includes('image')) return '📷';
                if (tl.includes('keyboard')) return '⌨️';
                if (tl.includes('mouse') || tl.includes('input') || tl.includes('hidclass')) return '🖱️';
                if (tl.includes('bluetooth')) return '📡';
                if (tl.includes('audio') || tl.includes('headset') || tl.includes('audioendpoint')) return '🔊';
                if (tl.includes('biometric') || tl.includes('fingerprint')) return '🔐';
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
                      <span style="font-size:18px;flex-shrink:0;margin-top:1px">${usbTypeIcon(type, desc)}</span>
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
              const osStr = ((diag.os_version || diag.os || '') + '').toLowerCase();
              const isLinuxSvc = osStr.includes('linux') || (name || '').toLowerCase().includes('linux');
              const svcTitle = isLinuxSvc ? 'Linux Systemd Services (Critical)' : 'Windows Services (Critical)';
              servicesHtml = `
            <div class="card-sec" style="margin-top:15px">
              <h4 style="margin-bottom:8px;color:var(--red);font-size:12px;font-weight:700"><i class="fa-solid fa-sliders" style="margin-right:6px"></i>${svcTitle}</h4>
              <div style="font-size:11px;margin-bottom:6px">
                Critical stopped: ${stoppedSvc.length > 0 ? stoppedSvc.map(s => `<span class="tag tag-orange" style="margin-right:4px">${s}</span>`).join('') : '<span class="tag tag-green">None (All running)</span>'}
              </div>
              <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:6px;max-height:140px;overflow-y:auto;padding-right:4px;border:1px solid rgba(255,255,255,.05);border-radius:4px;padding:6px;background:rgba(0,0,0,.1)">
                ${svcs.map(([sname, sstatus]) => `
                  <div style="display:flex;justify-content:space-between;align-items:center;font-size:10px;background:rgba(255,255,255,.03);padding:4px 8px;border-radius:4px">
                    <span style="color:var(--txt2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:115px" title="${sname}">${sname}</span>
                    <span style="padding:1px 6px;border-radius:3px;font-weight:700;font-size:9px;background:${sstatus === 'Running' ? 'rgba(52,211,153,.15)' : 'rgba(239,68,68,.15)'};color:${sstatus === 'Running' ? 'var(--green2)' : 'var(--red2)'};border:1px solid ${sstatus === 'Running' ? 'rgba(52,211,153,.3)' : 'rgba(239,68,68,.3)'}">${sstatus}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
            }

            // ─── 6. Remote Access (Anydesk / Rustdesk) ────────────────────────
            const rd = diag.rustdesk || {};
            const ad = diag.anydesk || {};
            const remoteHtml = `
          <div class="card-sec" style="margin-top:15px">
            <h4 style="margin-bottom:8px;color:var(--green);font-size:12px;font-weight:700"><i class="fa-solid fa-display" style="margin-right:6px"></i>Remote Access (Agent)</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px">
                <div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">RustDesk</div>
                <div style="font-size:12px;font-weight:600;margin-top:4px;color:var(--txt);display:flex;align-items:center;justify-content:space-between">
                  <span>ID: <code style="color:var(--cyan);font-weight:700">${rd.id && rd.id !== '---' ? rd.id : '—'}</code></span>
                  <span class="tag ${rd.running ? 'tag-green' : 'tag-orange'}">${rd.running ? '🟢 Running' : '⚪ Stopped'}</span>
                </div>
              </div>
              <div style="background:var(--glass);border-radius:6px;padding:8px 10px">
                <div style="font-size:9.5px;color:var(--txt3);text-transform:uppercase">AnyDesk</div>
                <div style="font-size:12px;font-weight:600;margin-top:4px;color:var(--txt);display:flex;align-items:center;justify-content:space-between">
                  <span>ID: <code style="color:var(--cyan);font-weight:700">${ad.id && ad.id !== '---' ? ad.id : '—'}</code></span>
                  <span class="tag ${ad.running ? 'tag-green' : 'tag-orange'}">${ad.running ? '🟢 Running' : '⚪ Stopped'}</span>
                </div>
              </div>
            </div>
          </div>
        `;

            // ─── 7. Recent Activity from telemetry_logs ───────────────────────
            let recentActivityHtml = '';
            const recentAct = diag.recent_activity || [];
            if (recentAct.length > 0) {
              recentActivityHtml = `
            <div class="card-sec" style="margin-top:15px">
              <h4 style="margin-bottom:8px;color:var(--blue);font-size:12px;font-weight:700"><i class="fa-solid fa-user-check" style="margin-right:6px"></i>Recent User Activity (Agent 05)</h4>
              <table class="tbl" style="width:100%;font-size:11px">
                <thead><tr><th>Waktu</th><th>App Aktif</th><th>Window Title</th><th>Status</th></tr></thead>
                <tbody>
                  ${recentAct.map(a => `<tr>
                    <td style="font-size:10px;color:var(--txt3)">${a.timestamp || '—'}</td>
                    <td><span class="tag tag-blue">${a.app_name || '—'}</span></td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.window_title || '—'}</td>
                    <td><span class="tag ${a.is_idle ? 'tag-orange' : 'tag-green'}">${a.is_idle ? 'Idle' : 'Active'}</span></td>
                  </tr>`).join('')}
                </tbody>
              </table>
            </div>
          `;
            }

            // ─── 8. Recent Issues from telemetry_logs ─────────────────────────
            let recentIssuesHtml = '';
            const recentIss = diag.recent_issues || [];
            if (recentIss.length > 0) {
              recentIssuesHtml = `
            <div class="card-sec" style="margin-top:15px">
              <h4 style="margin-bottom:8px;color:var(--red);font-size:12px;font-weight:700"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px"></i>Detected Issues (Dari Telemetry Agent)</h4>
              <table class="tbl" style="width:100%;font-size:11px">
                <thead><tr><th>Waktu</th><th>Tipe</th><th>Severity</th><th>Browser</th><th>Detail</th></tr></thead>
                <tbody>
                  ${recentIss.map(iss => {
                const sevC = iss.severity === 'high' || iss.severity === 'critical' ? 'tag-red' : 'tag-orange'; return `<tr>
                    <td style="font-size:10px;color:var(--txt3)">${iss.timestamp || '—'}</td>
                    <td><code style="color:var(--orange2)">${iss.type || '—'}</code></td>
                    <td><span class="tag ${sevC}">${(iss.severity || '').toUpperCase()}</span></td>
                    <td>${iss.browser || '—'}</td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${iss.details || ''}"> ${iss.details || '—'}</td>
                  </tr>`;
              }).join('')}
                </tbody>
              </table>
            </div>
          `;
            }

            // Combine all sections!
            body.innerHTML = itemsHtml + netHtml + websHtml + appsHtml + printHtml + usbHtml + servicesHtml + remoteHtml + recentActivityHtml + recentIssuesHtml;

          } catch (err) {
            if (isSilent) {
              console.warn("Background Deep Diagnostics refresh skipped due to network/timeout:", err);
              return;
            }
            body.innerHTML = `<div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);border-radius:6px;padding:12px;margin-top:15px;color:var(--red2);font-size:11.5px">
          <i class="fa-solid fa-circle-exclamation" style="margin-right:8px;color:var(--red)"></i>
          <strong>Deep Diagnostics Error:</strong> ${err.message || err}
          <div style="font-size:10px;color:var(--txt3);margin-top:6px;line-height:1.4">
            Kemungkinan penyebab:<br>
            1. Agent PC offline atau tidak terjangkau dari server.<br>
            2. Port command agent (10000) diblokir firewall.<br>
            3. Data belum tersedia di database — coba kirim telemetry dari agent.
          </div>
        </div>`;
          } finally {
            window._pcDetailFetching = false;
          }

        },
        exportCSV() {
          // Filter out printers to export only PCs
          const allDevs = DataService._devices || [];
          const devices = allDevs.filter(d => !(d.name || '').toLowerCase().includes('printer') && !(d.metadata && d.metadata.type === 'printer'));
          if (devices.length === 0) {
            Notify.toast('WARNING: Export', 'Tidak ada data PC untuk diekspor', 'warn');
            return;
          }
          const headers = ['Nama', 'IP', 'Layer', 'Site', 'Status', 'Last Seen', 'Hostname'];
          const rows = devices.map(d => {
            const site = getSite(d.ip) || d.location || '---';
            const hostname = (d.metadata && d.metadata.hostname) || '';
            return [
              d.name,
              d.ip || '',
              d.layer ? 'L' + d.layer : '',
              site,
              d.status || '',
              timeSince(d.last_seen),
              hostname
            ];
          });
          const csvContent = "data:text/csv;charset=utf-8,"
            + [headers.join(','), ...rows.map(e => e.map(val => `"${(val || '').replace(/"/g, '""')}"`).join(','))].join('\n');
          const encodedUri = encodeURI(csvContent);
          const link = document.createElement("a");
          link.setAttribute("href", encodedUri);
          link.setAttribute("download", "pc_health_fleet.csv");
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          Notify.toast('SUCCESS: Export', 'Data PC Health berhasil diekspor ke CSV', 'ok');
        },
        applyFilters() {
          const q = (document.getElementById('pc-search').value || '').toLowerCase();
          const st = document.getElementById('pc-filter-status').value;
          const si = document.getElementById('pc-filter-site').value;
          this._allCards.forEach(c => {
            const visible = (!q || c.dataset.name.includes(q)) && (!st || c.dataset.status === st) && (!si || c.dataset.site === si);
            c.style.display = visible ? '' : 'none';
          });
          document.querySelectorAll('.site-block-section').forEach(sec => {
            const siteName = sec.getAttribute('data-site-group');
            if (si && siteName !== si) {
              sec.style.display = 'none';
              return;
            }
            const hasVisibleCard = sec.querySelector('.device-card:not([style*="display: none"])');
            sec.style.display = hasVisibleCard ? '' : 'none';
          });
        },
        _populateRemoteSelect(devices) {
          Remote.populateSelect(devices);
        },
        handleLiveTelemetry(ev) {
          if (!ev) return;
          const devName = (ev.device || (ev.data && (ev.data.pc_name || ev.data.agent_id)) || '').toLowerCase();
          const activeDev = (window._activeDetailDevice || '').toLowerCase();

          // 1. If Deep Diagnostics detail modal is currently open for this device, refresh immediately in real time
          if (activeDev && devName && (devName === activeDev || activeDev.includes(devName) || devName.includes(activeDev))) {
            const card = document.getElementById('pc-detail-card');
            if (card && card.style.display !== 'none') {
              this.showDetail(window._activeDetailDevice, true);
            }
          }

          // 2. Hot-patch matching card in PC Health grid if data contains metrics
          if (ev.data && devName && this._allCards) {
            const card = this._allCards.find(c => (c.dataset.name || '').toLowerCase() === devName);
            if (card) {
              const cpuVal = ev.data.cpu_usage || ev.data.cpu || ev.data.cpu_percent;
              const ramVal = ev.data.ram_usage || ev.data.ram || ev.data.memory_percent || ev.data.mem_percent;
              const diskVal = ev.data.disk_usage || ev.data.disk || ev.data.disk_percent;
              if (cpuVal !== undefined) {
                const cpuBar = card.querySelector('.metric-bar[data-type="cpu"] .fill') || card.querySelector('.bar-fill:first-child');
                if (cpuBar) cpuBar.style.width = Math.min(100, Math.max(0, cpuVal)) + '%';
              }
              if (ramVal !== undefined) {
                const ramBar = card.querySelector('.metric-bar[data-type="ram"] .fill');
                if (ramBar) ramBar.style.width = Math.min(100, Math.max(0, ramVal)) + '%';
              }
            }
          }
        }
      },

      /* ---- PRINTER (kept as stub for backward compat) ---- */

});
