/* modules/4_ai_lifecycle/models.js
 * Atomic Design — 3. Modules Layer (4_ai_lifecycle / models)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["4_ai_lifecycle"] = window.Modules["4_ai_lifecycle"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      models: {
        _lastStatuses: {},
        _statusTagClass(st) {
          const s = String(st || 'UNKNOWN').toUpperCase();
          if (s === 'ONLINE') return 'tag-green';
          if (s === 'DEPLETED' || s === 'TIMEOUT' || s === 'CONFIG URL') return 'tag-orange';
          if (s === 'INVALID KEY' || s === 'ERROR' || s === 'OFFLINE' || s.startsWith('ERROR')) return 'tag-red';
          return 'tag-gray';
        },
        _renderRightPanelStatus(statusesObj) {
          const targetEl = document.getElementById('model-key-status');
          if (!targetEl) return;

          const curStatuses = statusesObj || this._lastStatuses || {};
          this._lastStatuses = curStatuses;
          window.lastLlmStatuses = curStatuses;

          const telStatus = (curStatuses.telegram && curStatuses.telegram.status) || 'UNKNOWN';
          const netStatus = (curStatuses.netdata && curStatuses.netdata.status) || 'UNKNOWN';

          targetEl.innerHTML = CFG.AI_MODELS.map(m => {
            const statusInfo = (curStatuses && curStatuses[m.key]) ? curStatuses[m.key] : { status: 'UNKNOWN' };
            const rawStatus = statusInfo.status || 'UNKNOWN';
            const isOnline = rawStatus === 'ONLINE';
            const tagCls = this._statusTagClass(rawStatus);
            const rowBg = isOnline ? 'var(--glass)' : (rawStatus === 'NO KEY' || rawStatus === 'UNKNOWN' ? 'rgba(255,255,255,0.02)' : 'rgba(239, 68, 68, 0.08)');
            const rowBorder = isOnline ? '1px solid rgba(16,185,129,0.25)' : (rawStatus === 'NO KEY' || rawStatus === 'UNKNOWN' ? '1px solid var(--bd)' : '1px solid rgba(239, 68, 68, 0.35)');
            const keyNote = isOnline ? 'AES Fernet · Verified' : (rawStatus === 'NO KEY' ? 'Belum dikonfigurasi' : (m.enabled ? 'Periksa API Key / URL' : 'Model dinonaktifkan'));

            return `<div class="li-row" id="llm-row-${_esc(m.key)}" style="background:${rowBg};border:${rowBorder};border-radius:6px;padding:8px 10px;margin-bottom:6px;transition:all 0.2s ease">
              <div style="display:flex;align-items:center;gap:8px">
                <span style="font-size:14px">${m.icon || ''}</span>
                <div>
                  <div class="li-name" style="font-weight:600;font-size:12px;color:var(--txt)">${_esc(m.name)}</div>
                  <div style="font-size:9.5px;color:${isOnline ? 'var(--txt3)' : (rawStatus === 'NO KEY' ? 'var(--txt3)' : '#f87171')}">${_esc(keyNote)}${statusInfo.code ? ' · HTTP ' + Number(statusInfo.code) : ''}</div>
                </div>
              </div>
              <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                <span id="rkey-tag-${_esc(m.key)}" class="tag ${tagCls}">${_esc(rawStatus)}</span>
              </div>
            </div>`;
          }).join('') +
            `<div class="li-row" style="padding:8px 10px"><span class="li-name">📬 Telegram Bot Token</span><span class="tag ${this._statusTagClass(telStatus)}">${_esc(telStatus)}</span></div>
             <div class="li-row" style="padding:8px 10px"><span class="li-name">📊 Netdata Bearer Token</span><span class="tag ${this._statusTagClass(netStatus)}">${_esc(netStatus)}</span></div>`;
        },
        _renderModelList(statuses) {
          const list = document.getElementById('model-config-list');
          if (!list) return;
          list.innerHTML = CFG.AI_MODELS.map(m => {
            const statusInfo = (statuses && statuses[m.key]) ? statuses[m.key] : { status: 'UNKNOWN' };
            const statusClass = this._statusTagClass(statusInfo.status);

            return `<div style="background:var(--glass);border:1px solid var(--bd);border-radius:6px;padding:10px 12px;margin-bottom:8px">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <div style="font-size:12px;font-weight:700">${m.icon || ''} ${_esc(m.name)}</div>
              <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px">
                <input type="checkbox" id="chk-${_esc(m.key)}" ${m.enabled ? 'checked' : ''} onchange="Panels.models.toggleModel('${_esc(m.key)}',this.checked)" style="cursor:pointer">
                <span>${m.enabled ? 'Aktif' : 'Disabled'}</span>
              </label>
            </div>

            <div style="font-size:10px;color:var(--txt3);margin-bottom:4px">API Endpoint URL</div>
            <input type="url" class="inp" id="url-${_esc(m.key)}" value="${_esc(m.url || '')}" placeholder="https://..." style="width:100%;padding:4px 8px;font-size:10.5px;font-family:'JetBrains Mono',monospace;margin-bottom:8px">

            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <span style="font-size:10px;color:var(--txt3)">API Key</span>
                <span style="font-size:9.5px;color:var(--txt3)">Status: <b id="lkey-tag-${_esc(m.key)}" class="tag ${statusClass}" style="padding:1px 4px;font-size:9px">${_esc(statusInfo.status || 'UNKNOWN')}</b></span>
              </div>
              <div style="display:flex;gap:6px">
                <input type="password" class="inp" style="flex:1;padding:4px 8px;font-size:11px;font-family:'JetBrains Mono',monospace" id="key-${_esc(m.key)}" placeholder="Encrypted (Fernet) — Isi key baru untuk ubah..." value="${_esc(m.masked_key || '')}" autocomplete="new-password" data-passbolt-ignore="true" data-1p-ignore="true" data-lpignore="true">
                <button class="btn btn-ghost btn-xs" style="padding:4px 8px;border:1px solid var(--bd)" onclick="Panels.models.toggleKeyVisibility('${_esc(m.key)}')" title="Show/Hide Input">👁</button>
              </div>
            </div>

            <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
              <button class="btn btn-ghost btn-xs" onclick="Panels.models.testKey('${_esc(m.key)}')">🔍 Test Connection</button>
              <button class="btn btn-primary btn-xs" onclick="Panels.models.viewKey('${_esc(m.key)}')">🔑 View Key Status</button>
              <button class="btn btn-primary btn-xs" onclick="Panels.models.saveSingleKey('${_esc(m.key)}')">💾 Save Key</button>
              <button class="btn btn-xs" onclick="Panels.models.deleteKey('${_esc(m.key)}')" style="background:#ef4444;color:white;border:none;cursor:pointer">🗑 Delete Key</button>
            </div>
          </div>`;
          }).join('');
        },
        _populateSysConfig(globalCfg) {
          const cfg = (globalCfg && globalCfg.config) || globalCfg || {};
          if (!cfg || typeof cfg !== 'object') return;
          setEl('syscfg-orch', cfg.orchestrator_port ? ':' + cfg.orchestrator_port : '—');
          setEl('syscfg-dash', cfg.dashboard_port ? ':' + cfg.dashboard_port : ':8080');
          setEl('syscfg-conf', cfg.confidence_threshold !== undefined ? Math.round((Number(cfg.confidence_threshold) <= 1 ? cfg.confidence_threshold * 100 : cfg.confidence_threshold)) + '%' : '—');
          setEl('syscfg-netdata', cfg.netdata_master_url || '—');
          setEl('syscfg-nats', cfg.nats_host ? `${cfg.nats_host}:${cfg.nats_port || 4222}` : '—');
          setEl('syscfg-interval', cfg.check_interval ? cfg.check_interval + 's' : '—');
          setEl('syscfg-db', cfg.db_name || 'osi_system');
          setEl('syscfg-mode', cfg.recovery_mode || '—');
        },
        async load() {
          const list = document.getElementById('model-config-list');
          const keyStatus = document.getElementById('model-key-status');
          if (!list) return;

          // Clear legacy global interval if it existed
          if (window.llmMetricsInterval) {
            clearInterval(window.llmMetricsInterval);
            window.llmMetricsInterval = null;
          }

          list.innerHTML = '<div style="color:var(--txt2);font-size:11px;padding:12px">🔄 Loading configuration and API key status...</div>';

          try {
            const svc = window.Services.Data || DataService;
            const [config, statuses, globalCfg, devices] = await Promise.all([
              svc.loadAIConfig(),
              svc.testAIKeyStatus().catch(() => null),
              svc.fetch('/api/fleet/config/global').catch(() => null),
              svc.loadDevices().catch(() => [])
            ]);

            if (config && !config.error) {
              const cfgMap = config.models || config;
              for (const key in cfgMap) {
                const m = CFG.AI_MODELS.find(x => x.key === key);
                if (m && cfgMap[key] && typeof cfgMap[key] === 'object') {
                  if (cfgMap[key].enabled !== undefined) m.enabled = cfgMap[key].enabled;
                  if (cfgMap[key].api_url) m.url = cfgMap[key].api_url;
                  m.masked_key = cfgMap[key].api_key || '';
                }
              }
            }

            this._renderModelList(statuses);
            if (keyStatus) {
              this._renderRightPanelStatus(statuses);
            }
            this._populateSysConfig(globalCfg);
            if (typeof Remote !== 'undefined' && Remote.populateSelect) {
              Remote.populateSelect(devices);
            }
          } catch (err) {
            console.error(err);
            list.innerHTML = `<div style="color:var(--red);font-size:11px;padding:12px">❌ Error loading config: ${_esc(err.message || String(err))}</div>`;
          }
        },
        async refreshKeyStatuses() {
          Notify.toast('🔍 Testing All', 'Menguji koneksi semua API Keys...', 'info', 2000);
          try {
            const statuses = await (window.Services.Data || DataService).testAIKeyStatus();
            if (statuses) {
              this._renderRightPanelStatus(statuses);
              CFG.AI_MODELS.forEach(m => {
                const tagEl = document.getElementById(`lkey-tag-${m.key}`);
                const st = (statuses[m.key] && statuses[m.key].status) || 'UNKNOWN';
                if (tagEl) {
                  tagEl.textContent = st;
                  tagEl.className = 'tag ' + this._statusTagClass(st);
                }
              });
              Notify.toast('✅ Selesai', 'Status semua API Key telah diperbarui', 'ok', 2500);
            }
          } catch (err) {
            Notify.toast('❌ Gagal', _esc(err.message || 'Gagal menguji API keys'), 'err', 3000);
          }
        },
        toggleModel(key, enabled) {
          const m = CFG.AI_MODELS.find(x => x.key === key);
          if (m) m.enabled = enabled;
          const chk = document.getElementById(`chk-${key}`);
          if (chk) {
            const span = chk.nextElementSibling;
            if (span) span.textContent = enabled ? 'Aktif' : 'Disabled';
          }
          Notify.toast('⚡ Model', `${_esc(key)} ${enabled ? 'diaktifkan' : 'dinonaktifkan'} (klik Save Config untuk simpan)`, 'info', 2200);
          LogStreamer.add('INFO', 'MODEL', key + ' ' + (enabled ? 'ENABLED' : 'DISABLED') + ' by operator');
        },
        toggleKeyVisibility(key) {
          const inp = document.getElementById(`key-${key}`);
          if (!inp) return;
          if (inp.value === '********') {
            Notify.toast('🔒 Protected', 'Key tersimpan terenkripsi di backend dan tidak dapat ditampilkan dalam plaintext.', 'info', 2500);
            return;
          }
          inp.type = inp.type === 'password' ? 'text' : 'password';
        },
        async testKey(key) {
          const inp = document.getElementById(`key-${key}`);
          const rawVal = inp ? inp.value.trim() : '';
          if (rawVal !== '' && rawVal !== '********') {
            Notify.toast('⚠️ Simpan Dahulu', 'Klik "Save Key" terlebih dahulu sebelum melakukan test connection.', 'warn', 3500);
            return;
          }
          Notify.toast('🔍 Testing', 'Menguji koneksi API ' + _esc(key) + '...', 'info', 1500);
          try {
            const statuses = await (window.Services.Data || DataService).testAIKeyStatus(key);
            if (statuses && statuses[key]) {
              const s = statuses[key];
              this._lastStatuses[key] = s;
              const tagEl = document.getElementById(`lkey-tag-${key}`);
              if (tagEl) {
                tagEl.textContent = s.status;
                tagEl.className = 'tag ' + this._statusTagClass(s.status);
              }
              this._renderRightPanelStatus(this._lastStatuses);

              if (s.status === 'ONLINE') {
                Notify.toast('✅ Key Valid', `${_esc(key)} API key valid & berfungsi (${s.code || 200} OK)`, 'ok', 3000);
                LogStreamer.add('OK', 'API', 'API key test: ' + key + ' — ONLINE');
              } else if (s.status === 'DEPLETED') {
                Notify.toast('⚠️ Saldo Habis', `${_esc(key)} API key valid tapi kuota/saldo habis (${s.code})`, 'warn', 4000);
                LogStreamer.add('WARN', 'API', 'API key test: ' + key + ' — DEPLETED');
              } else if (s.status === 'NO KEY') {
                Notify.toast('❌ Key Kosong', `${_esc(key)} API key belum diatur atau kosong`, 'err', 3000);
                LogStreamer.add('ERROR', 'API', 'API key test: ' + key + ' — NO KEY');
              } else if (s.status === 'CONFIG URL') {
                Notify.toast('⚠️ URL Belum Diset', `Isi API Endpoint URL yang valid untuk ${_esc(key)} lalu simpan`, 'warn', 3500);
              } else {
                Notify.toast('❌ Koneksi Error', `${_esc(key)} API error: ${_esc(s.status)} (code: ${s.code || 0})`, 'err', 3000);
                LogStreamer.add('ERROR', 'API', 'API key test: ' + key + ' — ' + s.status);
              }
            } else {
              Notify.toast('❌ Gagal Uji', 'Tidak mendapat respon status untuk ' + _esc(key), 'err', 3000);
            }
          } catch (err) {
            Notify.toast('❌ API Error', _esc(err.message || 'Network error'), 'err', 3000);
          }
        },
        viewKey(key) {
          const m = CFG.AI_MODELS.find(x => x.key === key);
          const hasKey = m && m.masked_key === '********';
          const displayKey = hasKey
            ? '******** (AES Encrypted)<br><br>Token disembunyikan dan dienkripsi di backend untuk alasan keamanan.'
            : 'Tidak ada API Key yang tersimpan pada ai_config.json.';
          Modal.show('🔑 API Key Status — ' + _esc(key), `<div style="font-family:JetBrains Mono,monospace;font-size:11px;color:var(--txt2);background:rgba(0,0,0,.3);padding:10px;border-radius:6px;border:1px solid var(--bd);word-break:break-all">${displayKey}</div>`, [{ label: 'Close', cls: 'btn-ghost', fn: 'Modal.close()' }]);
        },
        async saveSingleKey(key) {
          const chk = document.getElementById(`chk-${key}`);
          const inp = document.getElementById(`key-${key}`);
          const urlInp = document.getElementById(`url-${key}`);
          const api_key = inp ? inp.value.trim() : '';
          const api_url = urlInp ? urlInp.value.trim() : '';
          if (!api_key || api_key === '********') {
            Notify.toast('⚠️ Input Kosong', 'Harap isi API Key baru terlebih dahulu.', 'warn', 2500);
            return;
          }
          if (chk && !chk.checked) chk.checked = true;
          Notify.toast('💾 Saving', 'Menyimpan API Key untuk ' + _esc(key) + '...', 'info', 1500);
          const payload = {};
          payload[key] = {
            enabled: true,
            api_key: api_key
          };
          if (api_url) payload[key].api_url = api_url;

          try {
            const resp = await (window.Services.Data || DataService).saveAIConfig(payload);
            if (resp && resp.success) {
              Notify.toast('💾 Saved', `API Key ${_esc(key)} berhasil disimpan`, 'ok', 2500);
              LogStreamer.add('OK', 'CONF', 'API key for ' + key + ' updated');
              const m = CFG.AI_MODELS.find(x => x.key === key);
              if (m) {
                m.masked_key = '********';
                m.enabled = true;
                if (api_url) m.url = api_url;
              }
              if (inp) inp.value = '********';
              await this.testKey(key);
            } else {
              Notify.toast('❌ Gagal Simpan', _esc((resp && (resp.error || resp.message)) || 'Gagal menyimpan'), 'err', 3000);
            }
          } catch (err) {
            Notify.toast('❌ Error API', _esc(err.message || 'API error'), 'err', 3000);
          }
        },
        deleteKey(key) {
          const escKey = _esc(key);
          Modal.confirm(
            '🗑️ Hapus API Key',
            `<div style="font-size:12px;color:var(--txt2)">Yakin ingin menghapus API Key untuk <b style="color:var(--red2)">${escKey}</b>?</div>`,
            async () => {
              Modal.close();
              Notify.toast('🗑 Deleting', 'Menghapus API Key untuk ' + escKey + '...', 'info', 1500);
              const chk = document.getElementById(`chk-${key}`);
              const payload = {};
              payload[key] = {
                enabled: chk ? chk.checked : false,
                api_key: '__DELETE__'
              };
              try {
                const resp = await (window.Services.Data || DataService).saveAIConfig(payload);
                if (resp && resp.success) {
                  Notify.toast('🗑 Deleted', `API Key ${escKey} berhasil dihapus`, 'ok', 2500);
                  LogStreamer.add('OK', 'CONF', 'API key for ' + key + ' deleted');
                  const m = CFG.AI_MODELS.find(x => x.key === key);
                  if (m) m.masked_key = '';
                  const inp = document.getElementById(`key-${key}`);
                  if (inp) inp.value = '';
                  this._lastStatuses[key] = { status: 'NO KEY', code: 0 };
                  const tagEl = document.getElementById(`lkey-tag-${key}`);
                  if (tagEl) { tagEl.textContent = 'NO KEY'; tagEl.className = 'tag tag-gray'; }
                  this._renderRightPanelStatus(this._lastStatuses);
                } else {
                  Notify.toast('❌ Gagal Hapus', _esc((resp && (resp.error || resp.message)) || 'Gagal menghapus'), 'err', 3000);
                }
              } catch (err) {
                Notify.toast('❌ Error API', _esc(err.message || 'API error'), 'err', 3000);
              }
            }
          );
        },
        async save() {
          Notify.toast('💾 Saving', 'Menyimpan konfigurasi model...', 'info', 1500);
          const payload = {};
          for (const m of CFG.AI_MODELS) {
            const chk = document.getElementById(`chk-${m.key}`);
            const inp = document.getElementById(`key-${m.key}`);
            const urlInp = document.getElementById(`url-${m.key}`);
            if (chk) {
              const entry = {
                enabled: chk.checked,
                api_key: inp ? inp.value.trim() : ''
              };
              if (urlInp && urlInp.value.trim()) {
                entry.api_url = urlInp.value.trim();
                m.url = entry.api_url;
              }
              payload[m.key] = entry;
            }
          }

          try {
            const resp = await (window.Services.Data || DataService).saveAIConfig(payload);
            if (resp && resp.success) {
              Notify.toast('💾 Saved', 'Konfigurasi model AI berhasil disimpan', 'ok', 2500);
              LogStreamer.add('OK', 'CONF', 'AI model config updated by operator');
              await this.load();
            } else {
              Notify.toast('❌ Gagal Simpan', _esc((resp && (resp.error || resp.message)) || 'Gagal menyimpan'), 'err', 3000);
            }
          } catch (err) {
            Notify.toast('❌ Error API', _esc(err.message || 'API error'), 'err', 3000);
          }
        }
      },

});

window.Modules["4_ai_lifecycle"]["models"] = window.Panels;
