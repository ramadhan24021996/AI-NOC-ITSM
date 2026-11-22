/* o-remote-settings.js
 * Organism: RemoteSettings — remote access configuration manager.
 * Extracted from data.service.js (lines 5475-6315) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: Notify (molecule), Modal (molecule), LogStreamer (organism), Remote (organism)
 */
(function () {
  'use strict';

var RemoteSettings = {
  _activeTab: 'general',
  _tabs: ['general', 'anydesk', 'rustdesk', 'vnc', 'siterouter', 'devicelist', 'security', 'testconn'],
  _esc(s) {
    if (typeof _esc === 'function') return _esc(s);
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  },
  _jsAttr(s) {
    if (typeof _jsAttr === 'function') return _jsAttr(s);
    return String(s == null ? '' : s).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
  },
  _authHeaders(extra = {}) {
    const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || '';
    const h = { 'Accept': 'application/json', 'Content-Type': 'application/json', ...extra };
    if (token) {
      h['Authorization'] = 'Bearer ' + token;
      h['X-CSRF-Token'] = token;
    }
    return h;
  },
  open() {
    const m = document.getElementById('modal-remote-settings');
    if (m) { m.style.display = 'block'; document.body.style.overflow = 'hidden'; }
    this.switchTab('general');
    this._checkLauncherStatus();
    this.load();
    this.loadSites();
    this.loadDevicesRegistry();
  },
  close() {
    const m = document.getElementById('modal-remote-settings');
    if (m) { m.style.display = 'none'; document.body.style.overflow = ''; }
  },
  switchTab(tab) {
    this._activeTab = tab;
    this._tabs.forEach(t => {
      const pane = document.getElementById('rs-pane-' + t);
      const btn = document.getElementById('rs-tab-' + t);
      if (pane) pane.style.display = t === tab ? '' : 'none';
      if (btn) {
        btn.style.borderBottom = t === tab ? '2px solid var(--blue2)' : '2px solid transparent';
        btn.style.color = t === tab ? 'var(--txt)' : 'var(--txt2)';
        btn.style.fontWeight = t === tab ? '600' : '400';
      }
    });
  },
  load() {
    fetch('/api/remote/settings', { headers: this._authHeaders() })
      .then(r => r.json())
      .then(data => {
        if (data && data.general) {
          const gen = data.general;
          const dt = document.getElementById('rs-dt-' + gen.defaultTool);
          if (dt) dt.checked = true;
          setChk('rs-auto-launch', gen.autoLaunch);
          setChk('rs-auto-connect', gen.autoConnect);
          setChk('rs-remember-device', gen.rememberDevice);
          setVal('rs-timeout', gen.timeout);
          setVal('rs-retry', gen.retry);

          const ad = data.anydesk;
          if (ad) {
            setVal('rs-anydesk-path', ad.path);
            setChk('rs-ad-fullscreen', ad.fullscreen);
            setChk('rs-ad-unattended', ad.unattended);
          }

          const rd = data.rustdesk;
          if (rd) {
            setVal('rs-rustdesk-path', rd.path);
            setVal('rs-rd-relay', rd.relay);
            setVal('rs-rd-api', rd.api);
          }

          const vnc = data.vnc;
          if (vnc) {
            setVal('rs-vnc-viewer', vnc.viewer);
            setVal('rs-vnc-path', vnc.path);
            setVal('rs-vnc-port', vnc.port);
          }

          if (data.passwords) {
            if (data.passwords.anydesk) setVal('rs-anydesk-pass', data.passwords.anydesk);
            if (data.passwords.vnc) setVal('rs-vnc-pass', data.passwords.vnc);
            if (data.passwords.rustdesk_key) setVal('rs-rd-key', data.passwords.rustdesk_key);
          }
        }
      })
      .catch(err => {
        console.error("Failed to load settings:", err);
        Notify.toast('⚠️ Settings', 'Gagal memuat remote settings dari server', 'warn');
      });

    function setVal(id, val) { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; }
    function setChk(id, val) { const el = document.getElementById(id); if (el && val !== undefined) el.checked = !!val; }
  },
  async loadSites() {
    await DataService.loadSites();
    const sites = DataService._sites || [];
    const tbody = document.getElementById('rs-site-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';
    const toolColors = { rustdesk: 'tag-blue', anydesk: 'tag-purple', vnc: 'tag-orange', rdp: 'tag-cyan' };

    sites.forEach(site => {
      const tr = document.createElement('tr');
      tr.style.fontSize = '10.5px';

      const name = site.site_name || '—';
      const gw = site.router_ip || '—';
      const subnet = site.dns_primary || '—';
      const tool = site.default_remote_tool || 'rustdesk';

      tr.innerHTML = `
    <td style="padding:6px 8px;border:1px solid var(--bd)">${this._esc(name)}</td>
    <td style="padding:6px 8px;border:1px solid var(--bd)">${this._esc(gw)}</td>
    <td style="padding:6px 8px;border:1px solid var(--bd)">${this._esc(subnet)}</td>
    <td style="padding:6px 8px;border:1px solid var(--bd)"><span class="tag ${toolColors[tool] || 'tag-gray'}">${this._esc(tool)}</span></td>
    <td style="padding:6px 8px;border:1px solid var(--bd)">
      <div style="display:flex;gap:4px">
        <button class="btn btn-ghost btn-xs" onclick="RemoteSettings.editSite('${this._jsAttr(site.site_id)}')">✏ Edit</button>
        <button class="btn btn-ghost btn-xs" style="color:var(--red2)" onclick="RemoteSettings.deleteSite('${this._jsAttr(site.site_id)}', '${this._jsAttr(name)}')">🗑️ Hapus</button>
      </div>
    </td>
  `;
      tbody.appendChild(tr);
    });
  },
  deleteSite(siteId, name) {
    Modal.confirm(
      `🗑️ Hapus Site`,
      `<div style="text-align:center;padding:8px">
    <div style="font-size:28px;margin-bottom:10px">🏢</div>
    <div style="font-size:13px;font-weight:600;color:var(--txt)">Hapus site <span style="color:var(--red2)">${this._esc(name)}</span>?</div>
    <div style="font-size:11px;color:var(--txt3);margin-top:6px">Site akan dihapus dari database fleet.<br>Perangkat yang terhubung dengan site ini akan kehilangan pemetaan nama site.</div>
  </div>`,
      async () => {
        Modal.close();
        try {
          const resp = await fetch('/api/fleet/admin/sites/delete/' + encodeURIComponent(siteId), {
            method: 'DELETE',
            headers: this._authHeaders()
          });
          const data = await resp.json();
          if (data.status !== 'success') {
            Notify.toast('⚠️ Gagal', data.message || 'Gagal menghapus site', 'warn');
            return;
          }

          Notify.toast('🗑️ Deleted', 'Site berhasil dihapus', 'ok');
          LogStreamer.add('OK', 'CONFIG', 'Site deleted: ' + name);

          // Reload sites map & table
          await this.loadSites();

          // Reload Fleet panel
          if (window.Panels && Panels.fleet) {
            Panels.fleet.load();
          }
          if (window.GlobalTopology) {
            GlobalTopology.load();
          }
        } catch (e) {
          Notify.toast('❌ Error', 'Gagal berkomunikasi dengan server', 'err');
        }
      }
    );
  },
  save() {
    const settings = {
      general: {
        defaultTool: document.querySelector('[name=rs-default-tool]:checked')?.value || 'rustdesk',
        autoLaunch: document.getElementById('rs-auto-launch')?.checked,
        autoConnect: document.getElementById('rs-auto-connect')?.checked,
        rememberDevice: document.getElementById('rs-remember-device')?.checked,
        timeout: document.getElementById('rs-timeout')?.value || 30,
        retry: document.getElementById('rs-retry')?.value || 3
      },
      anydesk: {
        path: document.getElementById('rs-anydesk-path')?.value,
        fullscreen: document.getElementById('rs-ad-fullscreen')?.checked,
        unattended: document.getElementById('rs-ad-unattended')?.checked
      },
      rustdesk: {
        path: document.getElementById('rs-rustdesk-path')?.value,
        relay: document.getElementById('rs-rd-relay')?.value,
        api: document.getElementById('rs-rd-api')?.value
      },
      vnc: {
        viewer: document.getElementById('rs-vnc-viewer')?.value,
        path: document.getElementById('rs-vnc-path')?.value,
        port: document.getElementById('rs-vnc-port')?.value || 5900
      }
    };
    const adPass = document.getElementById('rs-anydesk-pass')?.value;
    const vncPass = document.getElementById('rs-vnc-pass')?.value;
    const rdKey = document.getElementById('rs-rd-key')?.value;

    fetch('/api/remote/settings/save', {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ ...settings, passwords: { anydesk: adPass, vnc: vncPass, rustdesk_key: rdKey } })
    }).then(r => r.json()).then(data => {
      if (data.status === 'SUCCESS' || data.ok) {
        Notify.toast('💾 Settings', 'Remote settings berhasil disimpan', 'ok');
        LogStreamer.add('OK', 'CONFIG', 'Remote settings saved by operator');
        this.close();
      } else {
        Notify.toast('⚠️ Settings', data.message || 'Gagal menyimpan settings', 'warn');
      }
    }).catch(() => {
      try { localStorage.setItem('remote_settings', JSON.stringify(settings)); } catch (e) { }
      Notify.toast('💾 Settings', 'Settings disimpan secara lokal (server tidak tersedia)', 'warn');
      LogStreamer.add('WARN', 'CONFIG', 'Remote settings saved locally (server unavailable)');
      this.close();
    });
  },
  reset() {
    Modal.confirm('↩ Reset Settings', 'Reset semua Remote Access settings ke default?', () => {
      Modal.close();
      document.getElementById('rs-anydesk-path').value = 'C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe';
      document.getElementById('rs-rustdesk-path').value = 'C:\\Program Files\\RustDesk\\rustdesk.exe';
      document.getElementById('rs-vnc-path').value = 'C:\\Program Files\\UltraVNC\\vncviewer.exe';
      document.getElementById('rs-vnc-port').value = '5900';
      document.getElementById('rs-rd-relay').value = 'relay.rustdesk.com';
      document.getElementById('rs-rd-api').value = 'api.rustdesk.com';
      document.getElementById('rs-timeout').value = '30';
      document.getElementById('rs-retry').value = '3';
      Notify.toast('↩ Reset', 'Settings direset ke default', 'ok');
    });
  },
  autoDetect(tool) {
    const safeTool = encodeURIComponent(tool);
    Notify.toast('🔍 Auto Detect', 'Mencari executable ' + this._esc(tool) + '...', 'info');
    fetch('/api/remote/detect?tool=' + safeTool, { headers: this._authHeaders() })
      .then(r => r.json())
      .then(data => {
        if (data.found && data.path) {
          const pathEl = document.getElementById('rs-' + tool + '-path');
          if (pathEl) pathEl.value = data.path;
          Notify.toast('✅ Auto Detect', this._esc(tool) + ' ditemukan: ' + this._esc(data.path), 'ok');
        } else {
          Notify.toast('⚠️ Auto Detect', this._esc(tool) + ' tidak ditemukan di sistem', 'warn');
        }
      })
      .catch(() => {
        Notify.toast('⚠️ Auto Detect', 'Launcher Service tidak tersedia. Periksa path secara manual.', 'warn');
      });
  },
  testTool(tool) {
    const resultId = 'rs-' + tool + '-test-result';
    const resultEl = document.getElementById(resultId);
    if (resultEl) resultEl.textContent = '⏳ Testing...';
    fetch('/api/remote/test/' + encodeURIComponent(tool), { method: 'POST', headers: this._authHeaders() })
      .then(r => {
        if (!r.ok) throw new Error("HTTP error " + r.status);
        return r.json();
      })
      .then(data => {
        if (resultEl) resultEl.innerHTML = data.found
          ? `<span style="color:var(--green2)">✅ ${this._esc(data.version || 'Found')} - READY</span>`
          : `<span style="color:var(--red2)">❌ Not found</span>`;
      })
      .catch(() => {
        if (resultEl) resultEl.innerHTML = `<span style="color:var(--orange2)">⚠️ Gagal menguji tool</span>`;
      });
  },
  testAllConnections() {
    ['anydesk', 'rustdesk', 'vnc', 'rdp'].forEach(tool => {
      const tag = document.getElementById('rs-' + tool + '-status-tag');
      const detail = document.getElementById('rs-' + tool + '-status-detail');
      if (tag) { tag.textContent = 'TESTING...'; tag.className = 'tag tag-orange'; }
      if (detail) detail.textContent = 'Menguji koneksi...';
      const endpoint = tool === 'rdp' ? '/api/remote/test/rdp' : '/api/remote/test/' + encodeURIComponent(tool);
      fetch(endpoint, { method: 'POST', headers: this._authHeaders() })
        .then(r => {
          if (!r.ok) throw new Error("HTTP error " + r.status);
          return r.json();
        })
        .then(data => {
          if (tag) {
            tag.textContent = data.found ? 'READY' : 'NOT FOUND';
            tag.className = 'tag ' + (data.found ? 'tag-green' : 'tag-red');
          }
          if (detail) detail.textContent = data.found
            ? '✅ ' + (data.version || 'Executable found') + (data.path ? ' — ' + data.path : '')
            : '❌ Tidak ditemukan di sistem';
        })
        .catch(() => {
          if (tag) { tag.textContent = 'OFFLINE'; tag.className = 'tag tag-gray'; }
          if (detail) detail.textContent = '⚠️ Launcher Service tidak tersedia';
        });
    });
    Notify.toast('🔄 Test', 'Menguji semua remote tools...', 'info');
  },
  addSite() {
    Modal.show('🌐 Add Site', `
  <div>
    <label class="inp-label">Site Name</label>
    <input class="inp" id="rs-new-site-name" placeholder="Contoh: Kantor Pusat" style="margin-bottom:8px">
    <label class="inp-label">Gateway IP</label>
    <input class="inp" id="rs-new-site-gw" placeholder="10.20.0.1" style="margin-bottom:8px">
    <label class="inp-label">Subnet (CIDR)</label>
    <input class="inp" id="rs-new-site-subnet" placeholder="10.20.0.0/24" style="margin-bottom:8px">
    <label class="inp-label">Default Tool</label>
    <select class="inp" id="rs-new-site-tool">
      <option value="rustdesk">RustDesk</option>
      <option value="anydesk">AnyDesk</option>
      <option value="vnc">VNC</option>
      <option value="rdp">RDP</option>
    </select>
  </div>
`, [{ label: 'Create', cls: 'btn-success', fn: 'RemoteSettings._createSite()' }, { label: 'Batal', cls: 'btn-ghost', fn: 'Modal.close()' }]);
  },
  async _createSite() {
    const name = document.getElementById('rs-new-site-name')?.value;
    const gw = document.getElementById('rs-new-site-gw')?.value;
    const subnet = document.getElementById('rs-new-site-subnet')?.value;
    const tool = document.getElementById('rs-new-site-tool')?.value;
    if (!name || !gw) { Notify.toast('⚠️ Input', 'Site Name dan Gateway harus diisi', 'warn'); return; }
    Modal.close();

    const siteId = name.replace(/\s+/g, '-').toLowerCase() + '-' + Math.floor(Math.random() * 1000);

    try {
      const resp = await fetch('/api/fleet/admin/sites', {
        method: 'POST',
        headers: this._authHeaders(),
        body: JSON.stringify({
          site_id: siteId,
          site_name: name,
          router_ip: gw,
          dns_primary: subnet,
          default_remote_tool: tool
        })
      });
      const data = await resp.json();
      if (data.status === 'success') {
        Notify.toast('✅ Site Added', 'Site ' + name + ' berhasil ditambahkan', 'ok');
        LogStreamer.add('OK', 'CONFIG', 'New site added: ' + name + ' (' + gw + ')');
        await this.loadSites();
        await DataService.loadSites();
        if (window.Panels && Panels.fleet) Panels.fleet.load();
        if (window.GlobalTopology) GlobalTopology.load();
      } else {
        Notify.toast('⚠️ Site Added', data.message || 'Gagal menambahkan site', 'warn');
      }
    } catch (e) {
      Notify.toast('❌ Error', 'Connection failed', 'err');
    }
  },
  async editSite(siteId) {
    try {
      const resp = await fetch('/api/fleet/admin/sites', { headers: this._authHeaders() });
      const data = await resp.json();
      const siteList = data.sites || [];
      const site = siteList.find(s => s.site_id === siteId);
      if (!site) { Notify.toast('⚠️ Edit', 'Site tidak ditemukan', 'warn'); return; }

      Modal.show('✏ Edit Site', `
    <div>
      <label class="inp-label">Site Name</label>
      <input class="inp" id="rs-edit-site-name" value="${this._esc(site.site_name)}" style="margin-bottom:8px">
      <label class="inp-label">Gateway IP</label>
      <input class="inp" id="rs-edit-site-gw" value="${this._esc(site.router_ip || '')}" style="margin-bottom:8px">
      <label class="inp-label">Subnet (CIDR)</label>
      <input class="inp" id="rs-edit-site-subnet" value="${this._esc(site.dns_primary || '')}" style="margin-bottom:8px">
      <label class="inp-label">Default Tool</label>
      <select class="inp" id="rs-edit-site-tool">
        <option value="rustdesk" ${site.default_remote_tool === 'rustdesk' ? 'selected' : ''}>RustDesk</option>
        <option value="anydesk" ${site.default_remote_tool === 'anydesk' ? 'selected' : ''}>AnyDesk</option>
        <option value="vnc" ${site.default_remote_tool === 'vnc' ? 'selected' : ''}>VNC</option>
        <option value="rdp" ${site.default_remote_tool === 'rdp' ? 'selected' : ''}>RDP</option>
      </select>
    </div>
  `, [
        { label: 'Simpan', cls: 'btn-primary', fn: `RemoteSettings._updateSite('${this._jsAttr(siteId)}')` },
        { label: 'Batal', cls: 'btn-ghost', fn: 'Modal.close()' }
      ]);
    } catch (e) {
      Notify.toast('❌ Error', 'Gagal memuat data site', 'err');
    }
  },
  async _updateSite(siteId) {
    const name = document.getElementById('rs-edit-site-name')?.value;
    const gw = document.getElementById('rs-edit-site-gw')?.value;
    const subnet = document.getElementById('rs-edit-site-subnet')?.value;
    const tool = document.getElementById('rs-edit-site-tool')?.value;
    if (!name || !gw) { Notify.toast('⚠️ Input', 'Site Name dan Gateway harus diisi', 'warn'); return; }
    Modal.close();

    try {
      const resp = await fetch('/api/fleet/admin/sites', {
        method: 'POST',
        headers: this._authHeaders(),
        body: JSON.stringify({
          site_id: siteId,
          site_name: name,
          router_ip: gw,
          dns_primary: subnet,
          default_remote_tool: tool
        })
      });
      const data = await resp.json();
      if (data.status === 'success') {
        Notify.toast('✅ Site Updated', 'Site ' + name + ' berhasil diubah', 'ok');
        LogStreamer.add('OK', 'CONFIG', 'Site updated: ' + name);
        await this.loadSites();
        await DataService.loadSites();
        if (window.Panels && Panels.fleet) Panels.fleet.load();
        if (window.GlobalTopology) GlobalTopology.load();
      } else {
        Notify.toast('⚠️ Site Edit', data.message || 'Gagal mengubah site', 'warn');
      }
    } catch (e) {
      Notify.toast('❌ Error', 'Connection failed', 'err');
    }
  },
  syncAllRoutes() {
    Modal.confirm('🔄 Sync Routes', 'Sync routes untuk semua sites yang terkonfigurasi?', async () => {
      Modal.close();
      Notify.toast('🔄 Sync', 'Syncing routes untuk semua sites...', 'info');
      try {
        const r = await DataService.sendCommand('SYNC_ALL_SITE_ROUTES', 'ALL', {});
        Notify.toast('🌐 Sync Complete', r.message || 'All routes synchronized', 'ok');
        LogStreamer.add('OK', 'REMOTE', 'SYNC_ALL_SITE_ROUTES completed');
      } catch (e) {
        Notify.toast('❌ Sync Failed', 'Gagal sync routes: ' + e.message, 'err');
      }
    });
  },
  _reconnectAttempts: 0,
  _reconnectTimer: null,
  _isConnecting: false,
  _reconnectFailed: false,
  _statusInterval: null,

  startStatusMonitoring() {
    if (this._statusInterval) clearInterval(this._statusInterval);
    this._reconnectFailed = false;
    this._isConnecting = false;
    const badge = document.getElementById('launcher-status-badge');
    // Silent initial check for background monitoring
    this._startAutoReconnectFlow(badge, false);

    this._statusInterval = setInterval(() => {
      this._checkPeriodicStatus();
    }, 10000);
    window.ActiveIntervals.remote_status = this._statusInterval;
  },

  retryConnection() {
    this._reconnectFailed = false;
    const badge = document.getElementById('launcher-status-badge');
    // Explicit user click -> show Toast on result
    this._startAutoReconnectFlow(badge, true);
  },

  async _checkPeriodicStatus() {
    if (this._isConnecting || document.hidden) return;
    const modelsPanel = document.getElementById('p-models');
    const modal = document.getElementById('modal-remote-settings');
    const isVisible = (modelsPanel && modelsPanel.classList.contains('active')) || (modal && modal.style.display === 'block');
    if (!isVisible) return;

    const badge = document.getElementById('launcher-status-badge');
    try {
      const r = await fetch('/api/launcher/status', { headers: this._authHeaders() }).catch(() => null);
      if (r && r.ok) {
        const data = await r.json().catch(() => ({}));
        if (data.status === 'online' || data.running) {
          this._setLauncherOnline(badge);
          this._updateToolsStatus();
          this._reconnectFailed = false;
          return;
        }
      }
    } catch (err) {}
    this._setLauncherOffline(badge);
  },

  async _checkLauncherStatus() {
    this.startStatusMonitoring();
  },

  _setLauncherOnline(badge) {
    if (badge) {
      badge.innerHTML = '🟢 Launcher Online';
      badge.className = 'tag tag-green';
      badge.style.cursor = 'pointer';
      badge.title = 'Launcher Service Online (Local Relay Ready)';
    }
    this._isConnecting = false;
    this._reconnectFailed = false;
    if (this._reconnectTimer) {
      clearInterval(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  },

  _setLauncherOffline(badge) {
    if (badge) {
      badge.innerHTML = '⚠️ Launcher Offline (Direct RDP Mode)';
      badge.className = 'tag tag-orange';
      badge.style.cursor = 'pointer';
      badge.title = 'Launcher local service offline. Remote tools will use Direct RDP/SSH protocol handler. Click to retry connection.';
    }
    Remote.updateButtonStates(true, null); // Keep remote buttons enabled via direct browser fallback!
  },

  async _startAutoReconnectFlow(badge, isManual = false) {
    if (this._reconnectTimer) {
      clearInterval(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._isConnecting) return;
    this._isConnecting = true;
    this._reconnectAttempts = 0;

    if (badge) {
      badge.innerHTML = '⏳ Connecting...';
      badge.className = 'tag tag-orange';
      badge.style.cursor = 'default';
      badge.title = 'Mencoba menghubungkan ke Launcher Service';
    }

    try {
      await fetch('/api/launcher/start', { method: 'POST', headers: this._authHeaders() }).catch(() => null);
    } catch (err) {}

    // Shorter background timeout (max 3 attempts) vs manual (up to timeoutVal)
    const maxAttempts = isManual ? (Math.ceil((parseInt(document.getElementById('rs-timeout')?.value) || 30) / 3)) : 3;

    this._reconnectTimer = setInterval(async () => {
      window.ActiveIntervals.remote_reconnect = this._reconnectTimer;
      this._reconnectAttempts++;
      try {
        const r = await fetch('/api/launcher/status', { headers: this._authHeaders() }).catch(() => null);
        if (r && r.ok) {
          const data = await r.json().catch(() => ({}));
          if (data.status === 'online' || data.running) {
            clearInterval(this._reconnectTimer);
            this._reconnectTimer = null;
            this._setLauncherOnline(badge);
            this._updateToolsStatus();
            if (isManual) {
              Notify.toast('🟢 Launcher Online', 'Launcher Service berhasil terhubung!', 'ok', 3000);
            }
            return;
          }
        }
      } catch (e) {}

      if (this._reconnectAttempts >= maxAttempts) {
        clearInterval(this._reconnectTimer);
        this._reconnectTimer = null;
        this._isConnecting = false;
        this._reconnectFailed = true;
        this._setLauncherOffline(badge);
        // Only trigger popup notification if explicitly requested by manual user action
        if (isManual) {
          Notify.toast('⚠️ Launcher Offline', 'Launcher Service offline. Mode Direct RDP/SSH Browser diaktifkan secara otomatis.', 'info', 4000);
        }
      }
    }, 3000);
  },

  async _updateToolsStatus() {
    try {
      const r = await fetch('/api/remote/detect?tool=all', { headers: this._authHeaders() });
      if (r.ok) {
        const toolStatus = await r.json().catch(() => null);
        Remote.updateButtonStates(true, toolStatus);
      } else {
        Remote.updateButtonStates(true, null);
      }
    } catch (e) {
      Remote.updateButtonStates(true, null);
    }
  },

  async loadDevicesRegistry() {
    try {
      const resp = await fetch('/api/fleet/admin/devices', { headers: this._authHeaders() });
      const data = await resp.json();
      const devicesList = Array.isArray(data) ? data : (data && Array.isArray(data.devices) ? data.devices : []);
      const tbody = document.getElementById('rs-device-tbody');
      if (!tbody) return;

      if (devicesList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--txt3)">Belum ada device manual terdaftar.</td></tr>';
        return;
      }

      // Load sites list for lookup
      const sResp = await fetch('/api/fleet/admin/sites', { headers: this._authHeaders() });
      const sData = await sResp.json();
      const sitesMap = {};
      (sData.sites || []).forEach(s => { sitesMap[s.site_id] = s.site_name; });

      tbody.innerHTML = devicesList.map(d => {
        const hw = d.hardware_info || {};
        const pcName = d.pc_name || d.name || 'Unknown';
        const ip = d.ip || hw.ip || '—';

        let ids = [];
        if (d.rustdesk_id || hw.rustdesk_id) ids.push(`RustDesk: <b>${this._esc(d.rustdesk_id || hw.rustdesk_id)}</b>`);
        if (hw.anydesk_id) ids.push(`AnyDesk: <b>${this._esc(hw.anydesk_id)}</b>`);
        const vnc = hw.vnc_info || {};
        if (vnc.host || vnc.port) ids.push(`VNC: <b>${this._esc(vnc.host || ip)}:${this._esc(vnc.port || 5900)}</b>`);

        return `<tr style="font-size:10.5px">
      <td style="padding:6px 8px;border:1px solid var(--bd);font-weight:600;color:var(--txt)">${this._esc(pcName)}</td>
      <td style="padding:6px 8px;border:1px solid var(--bd)">${this._esc(sitesMap[d.site_id] || d.site || d.site_id || '—')}</td>
      <td style="padding:6px 8px;border:1px solid var(--bd);font-family:monospace">${this._esc(ip)}</td>
      <td style="padding:6px 8px;border:1px solid var(--bd);color:var(--txt2);line-height:1.4">${ids.join('<br>') || '—'}</td>
      <td style="padding:6px 8px;border:1px solid var(--bd)">
        <div style="display:flex;gap:4px">
          <button class="btn btn-ghost btn-xs" onclick="RemoteSettings.editDevice('${this._jsAttr(pcName)}')">✏ Edit</button>
          <button class="btn btn-danger btn-xs" onclick="RemoteSettings.deleteDevice('${this._jsAttr(pcName)}')">🗑 Hapus</button>
        </div>
      </td>
    </tr>`;
      }).join('');
    } catch (e) {
      console.error("Failed to load device registry:", e);
    }
  },

  async addDevice() {
    try {
      const resp = await fetch('/api/fleet/admin/sites', { headers: this._authHeaders() });
      const data = await resp.json();
      const sites = data.sites || [];

      const siteOptions = sites.map(s => `<option value="${this._esc(s.site_id)}" data-gw="${this._esc(s.router_ip || '')}">${this._esc(s.site_name)} (${this._esc(s.router_ip || '')})</option>`).join('');

      Modal.show('🖥️ Register Target Device', `
    <div>
      <label class="inp-label">Device PC Name (Hostname)</label>
      <input class="inp" id="rs-dev-name" placeholder="PC-001" style="margin-bottom:8px">
      
      <label class="inp-label">Target Site</label>
      <select class="inp" id="rs-dev-site" style="margin-bottom:8px" onchange="
        const opt = this.options[this.selectedIndex];
        const gw = opt.getAttribute('data-gw');
        const gwEl = document.getElementById('rs-dev-gw');
        if (gwEl && gw) gwEl.value = gw;
      ">
        <option value="">Pilih Site...</option>
        ${siteOptions}
      </select>
      
      <label class="inp-label">Gateway / Router IP</label>
      <input class="inp" id="rs-dev-gw" placeholder="10.20.0.1" style="margin-bottom:8px">
      
      <label class="inp-label">PC IP Address</label>
      <input class="inp" id="rs-dev-ip" placeholder="10.20.0.49" style="margin-bottom:8px">
      
      <div style="border-top:1px solid rgba(255,255,255,0.06);margin:10px 0;padding-top:10px;font-size:11px;font-weight:700;color:var(--blue2)">Remote Tools Config</div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">RustDesk ID</label>
          <input class="inp" id="rs-dev-rd-id" placeholder="ID (RustDesk)">
        </div>
        <div>
          <label class="inp-label">RustDesk Password</label>
          <input class="inp" id="rs-dev-rd-pass" type="password" placeholder="Password (RustDesk)" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">AnyDesk ID</label>
          <input class="inp" id="rs-dev-ad-id" placeholder="ID (AnyDesk)">
        </div>
        <div>
          <label class="inp-label">AnyDesk Password</label>
          <input class="inp" id="rs-dev-ad-pass" type="password" placeholder="Password (AnyDesk)" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">VNC Port / VNC Password</label>
          <div style="display:flex;gap:4px">
            <input class="inp" id="rs-dev-vnc-port" value="5900" style="width:70px">
            <input class="inp" id="rs-dev-vnc-pass" type="password" placeholder="Password (VNC)" style="flex:1" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
          </div>
        </div>
      </div>
    </div>
  `, [
        { label: 'Register', cls: 'btn-success', fn: 'RemoteSettings._saveDevice(false)' },
        { label: 'Batal', cls: 'btn-ghost', fn: 'Modal.close()' }
      ]);
    } catch (e) {
      Notify.toast('❌ Error', 'Gagal memuat daftar site', 'err');
    }
  },

  async editDevice(pcName) {
    try {
      const dResp = await fetch('/api/fleet/admin/devices', { headers: this._authHeaders() });
      const dData = await dResp.json();
      const devicesList = Array.isArray(dData) ? dData : (dData && Array.isArray(dData.devices) ? dData.devices : []);
      const d = devicesList.find(x => (x.pc_name || x.name) === pcName);
      if (!d) { Notify.toast('⚠️ Edit', 'Device tidak ditemukan', 'warn'); return; }

      const sResp = await fetch('/api/fleet/admin/sites', { headers: this._authHeaders() });
      const sData = await sResp.json();
      const sites = sData.sites || [];

      const siteOptions = sites.map(s => `<option value="${this._esc(s.site_id)}" data-gw="${this._esc(s.router_ip || '')}" ${d.site_id === s.site_id ? 'selected' : ''}>${this._esc(s.site_name)} (${this._esc(s.router_ip || '')})</option>`).join('');

      const hw = d.hardware_info || {};
      const vnc = hw.vnc_info || {};
      const passwords = hw.remote_passwords || {};

      const rdPassMasked = passwords.rustdesk ? "********" : "";
      const adPassMasked = passwords.anydesk ? "********" : "";
      const vncPassMasked = passwords.vnc ? "********" : "";
      const devName = d.pc_name || d.name || pcName;
      const devIP = d.ip || hw.ip || '';
      const devGW = d.gateway || hw.gateway || '';

      Modal.show('✏ Edit Target Device', `
    <div>
      <label class="inp-label">Device PC Name (ReadOnly)</label>
      <input class="inp" id="rs-dev-name" value="${this._esc(devName)}" readonly style="margin-bottom:8px;background:var(--bg3);opacity:0.7">
      
      <label class="inp-label">Target Site</label>
      <select class="inp" id="rs-dev-site" style="margin-bottom:8px" onchange="
        const opt = this.options[this.selectedIndex];
        const gw = opt.getAttribute('data-gw');
        const gwEl = document.getElementById('rs-dev-gw');
        if (gwEl && gw) gwEl.value = gw;
      ">
        <option value="">Pilih Site...</option>
        ${siteOptions}
      </select>
      
      <label class="inp-label">Gateway / Router IP</label>
      <input class="inp" id="rs-dev-gw" value="${this._esc(devGW)}" style="margin-bottom:8px">
      
      <label class="inp-label">PC IP Address</label>
      <input class="inp" id="rs-dev-ip" value="${this._esc(devIP)}" style="margin-bottom:8px">
      
      <div style="border-top:1px solid rgba(255,255,255,0.06);margin:10px 0;padding-top:10px;font-size:11px;font-weight:700;color:var(--blue2)">Remote Tools Config</div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">RustDesk ID</label>
          <input class="inp" id="rs-dev-rd-id" value="${this._esc(d.rustdesk_id || hw.rustdesk_id || '')}" placeholder="ID (RustDesk)">
        </div>
        <div>
          <label class="inp-label">RustDesk Password</label>
          <input class="inp" id="rs-dev-rd-pass" type="password" value="${rdPassMasked}" placeholder="${passwords.rustdesk ? '(Unchanged)' : 'Password (RustDesk)'}" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">AnyDesk ID</label>
          <input class="inp" id="rs-dev-ad-id" value="${this._esc(hw.anydesk_id || '')}" placeholder="ID (AnyDesk)">
        </div>
        <div>
          <label class="inp-label">AnyDesk Password</label>
          <input class="inp" id="rs-dev-ad-pass" type="password" value="${adPassMasked}" placeholder="${passwords.anydesk ? '(Unchanged)' : 'Password (AnyDesk)'}" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
        </div>
      </div>
      
      <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:8px;margin-bottom:8px">
        <div>
          <label class="inp-label">VNC Port / VNC Password</label>
          <div style="display:flex;gap:4px">
            <input class="inp" id="rs-dev-vnc-port" value="${this._esc(vnc.port || 5900)}" style="width:70px">
            <input class="inp" id="rs-dev-vnc-pass" type="password" value="${vncPassMasked}" placeholder="${passwords.vnc ? '(Unchanged)' : 'Password (VNC)'}" style="flex:1" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
          </div>
        </div>
      </div>
    </div>
  `, [
        { label: 'Simpan', cls: 'btn-primary', fn: 'RemoteSettings._saveDevice(true)' },
        { label: 'Batal', cls: 'btn-ghost', fn: 'Modal.close()' }
      ]);
    } catch (e) {
      Notify.toast('❌ Error', 'Gagal memuat data device', 'err');
    }
  },

  async _saveDevice(isEdit) {
    const pcName = document.getElementById('rs-dev-name')?.value;
    const siteId = document.getElementById('rs-dev-site')?.value;
    const gw = document.getElementById('rs-dev-gw')?.value;
    const ip = document.getElementById('rs-dev-ip')?.value;
    const rustdeskId = document.getElementById('rs-dev-rd-id')?.value;
    const anydeskId = document.getElementById('rs-dev-ad-id')?.value;
    const vncPort = document.getElementById('rs-dev-vnc-port')?.value;

    const rdPass = document.getElementById('rs-dev-rd-pass')?.value;
    const adPass = document.getElementById('rs-dev-ad-pass')?.value;
    const vncPass = document.getElementById('rs-dev-vnc-pass')?.value;

    if (!pcName || !ip) { Notify.toast('⚠️ Input', 'PC Name dan IP Address harus diisi', 'warn'); return; }
    Modal.close();

    const passwords = {};
    if (rdPass && rdPass !== "********") passwords.rustdesk = rdPass;
    if (adPass && adPass !== "********") passwords.anydesk = adPass;
    if (vncPass && vncPass !== "********") passwords.vnc = vncPass;

    try {
      const resp = await fetch('/api/fleet/admin/devices/save', {
        method: 'POST',
        headers: this._authHeaders(),
        body: JSON.stringify({
          pc_name: pcName,
          site_id: siteId,
          gateway: gw,
          ip: ip,
          rustdesk_id: rustdeskId,
          anydesk_id: anydeskId,
          vnc_port: vncPort,
          passwords: passwords
        })
      });

      const data = await resp.json();
      if (data.status === 'success') {
        Notify.toast('✅ Saved', isEdit ? 'Device berhasil diupdate' : 'Device berhasil terdaftar', 'ok');
        this.loadDevicesRegistry();
        await DataService.loadDevices();
        if (window.Panels && Panels.fleet) Panels.fleet.load();
        if (window.GlobalTopology) GlobalTopology.load();
      } else {
        Notify.toast('⚠️ Gagal', data.message || 'Gagal menyimpan device', 'warn');
      }
    } catch (e) {
      Notify.toast('❌ Error', 'Gagal berkomunikasi dengan server', 'err');
    }
  },

  deleteDevice(pcName) {
    Modal.confirm('🗑 Hapus Device', `Hapus device target <b>${this._esc(pcName)}</b> dari database?`, async () => {
      Modal.close();
      try {
        const resp = await fetch('/api/fleet/admin/devices/delete/' + encodeURIComponent(pcName), {
          method: 'POST',
          headers: this._authHeaders()
        });
        const data = await resp.json();
        if (data.status === 'success') {
          Notify.toast('✅ Deleted', 'Device berhasil dihapus', 'ok');
          this.loadDevicesRegistry();
          await DataService.loadDevices();
          if (window.Panels && Panels.fleet) Panels.fleet.load();
          if (window.GlobalTopology) GlobalTopology.load();
        } else {
          Notify.toast('⚠️ Gagal', data.message || 'Gagal menghapus device', 'warn');
        }
      } catch (e) {
        Notify.toast('❌ Error', 'Gagal berkomunikasi dengan server', 'err');
      }
    });
  }
};

  window.RemoteSettings = RemoteSettings;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.RemoteSettings = RemoteSettings;
})();
