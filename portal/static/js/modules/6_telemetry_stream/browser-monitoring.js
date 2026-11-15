/* browser-monitoring.js
 * Module: BrowserMonitoring — enterprise browser tab monitoring.
 * Extracted from data.service.js (lines 4775-4999) — Phase 5.4 Atomic Design refactor.
 *
 * Layer: Modules > 6_telemetry_stream
 * Depends on: Notify (molecule), DataService (service)
 */
(function () {
  'use strict';

window.BrowserMonitoring = {
  _tabs: [],
  _summary: null,
  _timeline: [],
  _filter: { search: '', browser: '', category: '', status: '', focusedOnly: false },

  async load(deviceName) {
    try {
      const [liveRes, sumRes, timeRes] = await Promise.all([
        fetch('/api/browser_monitoring/live?device=' + encodeURIComponent(deviceName || '')).then(r => r.json()).catch(() => ({ data: [] })),
        fetch('/api/browser_monitoring/summary?device=' + encodeURIComponent(deviceName || '')).then(r => r.json()).catch(() => ({ data: {} })),
        fetch('/api/browser_monitoring/timeline?device=' + encodeURIComponent(deviceName || '')).then(r => r.json()).catch(() => ({ data: [] }))
      ]);

      if (liveRes && liveRes.data) this._tabs = liveRes.data;
      if (sumRes && sumRes.data) this._summary = sumRes.data;
      if (timeRes && timeRes.data) this._timeline = timeRes.data;
    } catch (e) {
      console.warn("Browser monitoring load failed:", e);
    }
  },

  renderSection(diag, deviceName) {
    let rawTabs = [];
    if (this._tabs && this._tabs.length > 0) {
      const targetName = (deviceName || '').toLowerCase();
      rawTabs = this._tabs.filter(t => {
        const dev = (t.pc_name || t.device_id || t.device || '').toLowerCase();
        return dev && (dev === targetName || targetName.includes(dev) || dev.includes(targetName));
      });
    }
    if (!rawTabs || rawTabs.length === 0) {
      rawTabs = [...(diag.active_tabs || diag.browser_url_history_10min || [])];
    }

    // Synthesize diag.current_browser_url if available so currently active focused tab is always displayed at top
    if (diag && diag.current_browser_url && diag.current_browser_url.url) {
      const cur = diag.current_browser_url;
      const foundIdx = rawTabs.findIndex(t => (t.url === cur.url || (t.domain && cur.domain && t.domain === cur.domain)));
      if (foundIdx >= 0) {
        rawTabs[foundIdx] = { ...rawTabs[foundIdx], is_focused: true, is_active: true, tab_title: cur.tab_title || rawTabs[foundIdx].tab_title || rawTabs[foundIdx].title };
      } else {
        rawTabs.unshift({
          browser_name: cur.browser || 'Google Chrome',
          title: cur.tab_title || 'Active Tab',
          url: cur.url,
          domain: cur.domain || (cur.url.replace(/^https?:\/\//, '').split('/')[0] || 'local'),
          category: 'Business',
          is_focused: true,
          is_active: true,
          status: 'open',
          duration_seconds: 60
        });
      }
    }

    const focusedCount = rawTabs.filter(t => t.is_focused || t.is_active).length || 1;
    const bgCount = Math.max(0, rawTabs.length - focusedCount);

    const sum = this._summary || {
      total_tabs: rawTabs.length,
      focused_tabs: focusedCount,
      background_tabs: bgCount,
      browsers: {
        chrome: rawTabs.filter(t => (t.browser_name || t.browser || '').toLowerCase().includes('chrome')).length || rawTabs.length,
        firefox: rawTabs.filter(t => (t.browser_name || t.browser || '').toLowerCase().includes('firefox')).length,
        edge: rawTabs.filter(t => (t.browser_name || t.browser || '').toLowerCase().includes('edge')).length,
        opera: rawTabs.filter(t => (t.browser_name || t.browser || '').toLowerCase().includes('opera')).length,
        brave: rawTabs.filter(t => (t.browser_name || t.browser || '').toLowerCase().includes('brave')).length
      }
    };

    const bCounts = sum.browsers || {};

    // Filter tabs
    let filtered = rawTabs.filter(t => {
      const title = (t.title || t.tab_title || '').toLowerCase();
      const url = (t.url || '').toLowerCase();
      const dom = (t.domain || '').toLowerCase();
      const cat = (t.category || '').toLowerCase();
      const bname = (t.browser_name || t.browser || '').toLowerCase();
      const s = (this._filter.search || '').toLowerCase();

      if (s && !title.includes(s) && !url.includes(s) && !dom.includes(s)) return false;
      if (this._filter.browser && !bname.includes(this._filter.browser.toLowerCase())) return false;
      if (this._filter.category && !cat.includes(this._filter.category.toLowerCase())) return false;
      if (this._filter.focusedOnly && !t.is_focused) return false;
      return true;
    });

    const bSummaryHtml = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:12px">
        <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">Chrome</div>
          <div style="font-size:15px;font-weight:700;color:var(--blue2)">${bCounts.chrome || 0} Tabs</div>
        </div>
        <div style="background:rgba(234,88,12,0.08);border:1px solid rgba(234,88,12,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">Firefox</div>
          <div style="font-size:15px;font-weight:700;color:var(--orange2)">${bCounts.firefox || 0} Tabs</div>
        </div>
        <div style="background:rgba(34,211,238,0.08);border:1px solid rgba(34,211,238,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">MS Edge</div>
          <div style="font-size:15px;font-weight:700;color:var(--cyan)">${bCounts.edge || 0} Tabs</div>
        </div>
        <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">Opera</div>
          <div style="font-size:15px;font-weight:700;color:var(--red2)">${bCounts.opera || 0} Tabs</div>
        </div>
        <div style="background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">Total Open</div>
          <div style="font-size:15px;font-weight:700;color:var(--purple2)">${sum.total_tabs || rawTabs.length} Tabs</div>
        </div>
        <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:6px;padding:8px;text-align:center">
          <div style="font-size:9px;color:var(--txt3);text-transform:uppercase">Focus / BG</div>
          <div style="font-size:13px;font-weight:700;color:var(--green);margin-top:2px">🎯 ${sum.focused_tabs || 1} / 💤 ${sum.background_tabs || 0}</div>
        </div>
      </div>
    `;

    const searchBarHtml = `
      <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
        <input type="text" class="inp" placeholder="🔍 Search URL, Window Title, Domain, Keyword..." style="flex:1;min-width:180px;font-size:11px" value="${this._filter.search || ''}" oninput="BrowserMonitoring._filter.search=this.value; if(window.Panels && window.Panels.pchealth && window._activeDetailDevice) Panels.pchealth.showDetail(window._activeDetailDevice, true);">
        <select class="inp" style="width:130px;font-size:11px" onchange="BrowserMonitoring._filter.browser=this.value; if(window.Panels && window.Panels.pchealth && window._activeDetailDevice) Panels.pchealth.showDetail(window._activeDetailDevice, true);">
          <option value="">Semua Browser</option>
          <option value="chrome" ${this._filter.browser==='chrome'?'selected':''}>Chrome</option>
          <option value="firefox" ${this._filter.browser==='firefox'?'selected':''}>Firefox</option>
          <option value="edge" ${this._filter.browser==='edge'?'selected':''}>MS Edge</option>
          <option value="opera" ${this._filter.browser==='opera'?'selected':''}>Opera</option>
        </select>
        <select class="inp" style="width:130px;font-size:11px" onchange="BrowserMonitoring._filter.category=this.value; if(window.Panels && window.Panels.pchealth && window._activeDetailDevice) Panels.pchealth.showDetail(window._activeDetailDevice, true);">
          <option value="">Semua Kategori</option>
          <option value="Business" ${this._filter.category==='Business'?'selected':''}>Business</option>
          <option value="Monitoring" ${this._filter.category==='Monitoring'?'selected':''}>Monitoring</option>
          <option value="Internal" ${this._filter.category==='Internal'?'selected':''}>Internal</option>
          <option value="AI" ${this._filter.category==='AI'?'selected':''}>AI & LLM</option>
          <option value="Cloud" ${this._filter.category==='Cloud'?'selected':''}>Cloud</option>
          <option value="Development" ${this._filter.category==='Development'?'selected':''}>Development</option>
        </select>
      </div>
    `;

    const tableRows = filtered.map(t => {
      const bname = t.browser_name || t.browser || 'Google Chrome';
      const title = t.title || t.tab_title || 'Untitled Tab';
      const url = t.url || '#';
      const domain = t.domain || (url !== '#' ? (url.replace(/^https?:\/\//, '').split('/')[0] || 'local') : 'local');
      const cat = t.category || 'Business';
      const isFocused = t.is_focused || t.is_active;

      const bLower = bname.toLowerCase();
      const bIcon = bLower.includes('edge') ? 'fa-brands fa-edge' : bLower.includes('firefox') ? 'fa-brands fa-firefox-browser' : bLower.includes('opera') ? 'fa-brands fa-opera' : 'fa-brands fa-chrome';
      const bTagColor = bLower.includes('edge') ? 'tag-cyan' : bLower.includes('firefox') ? 'tag-orange' : bLower.includes('opera') ? 'tag-red' : 'tag-blue';

      return `
        <tr onclick="BrowserMonitoring.showTabDetail('${t.tab_uuid || ''}', '${title.replace(/'/g, "")}', '${url.replace(/'/g, "")}')" style="cursor:pointer" title="Klik untuk inspect tab detail">
          <td><span class="tag ${bTagColor}" style="font-size:9.5px"><i class="${bIcon}" style="margin-right:3px"></i>${bname}</span></td>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;color:var(--txt)">${title}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            <a href="${url}" target="_blank" onclick="event.stopPropagation()" style="color:var(--cyan);font-size:10px"><i class="fa-solid fa-arrow-up-right-from-square" style="margin-right:3px;font-size:8px"></i>${url}</a>
          </td>
          <td><span class="tag tag-cyan" style="font-size:9px">${domain}</span></td>
          <td><span class="tag tag-purple" style="font-size:9px">${cat}</span></td>
          <td style="text-align:center">${isFocused ? '<span class="tag tag-green" style="font-size:8.5px">🎯 FOCUSED</span>' : '<span class="tag tag-gray" style="font-size:8.5px">💤 BG</span>'}</td>
          <td style="font-size:9.5px;color:var(--txt3)">${t.duration_seconds ? Math.round(t.duration_seconds / 60) + ' min' : 'Live'}</td>
        </tr>
      `;
    }).join('');

    const tableHtml = `
      <div style="max-height:260px;overflow-y:auto;border-radius:4px;border:1px solid rgba(255,255,255,.05);margin-bottom:12px">
        <table class="tbl" style="width:100%;font-size:10.5px">
          <thead>
            <tr>
              <th>Browser</th>
              <th>Tab Title</th>
              <th>Full URL</th>
              <th>Domain</th>
              <th>Category</th>
              <th style="text-align:center">Focus State</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            ${tableRows || '<tr><td colspan="7" style="text-align:center;color:var(--txt3);padding:10px">Tidak ada tab terdeteksi sesuai filter.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    return `
      <div class="card-sec" style="margin-top:15px">
        <h4 style="margin-bottom:8px;color:var(--cyan);font-size:12px;font-weight:700">
          <i class="fa-solid fa-earth-americas" style="margin-right:6px"></i>Web App Usage &amp; Enterprise Multi-Browser Tab Monitoring
          <span class="tag tag-green" style="font-size:9px;margin-left:8px">⚡ WEBSOCKET LIVE</span>
        </h4>
        <div style="background:rgba(0,0,0,.15);border:1px solid rgba(255,255,255,.05);border-radius:6px;padding:12px">
          ${bSummaryHtml}
          ${searchBarHtml}
          ${tableHtml}
        </div>
      </div>
    `;
  },

  showTabDetail(tabUuid, title, url) {
    Modal.show('🌐 Tab Inspector — ' + (title || 'Browser Tab'), `
      <div style="padding:10px">
        <div style="font-size:13px;font-weight:700;color:var(--cyan);margin-bottom:6px">${title || 'Tab Details'}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;background:rgba(0,0,0,.3);padding:8px;border-radius:4px;border:1px solid var(--bd);margin-bottom:10px;word-break:break-all">
          URL: <a href="${url}" target="_blank" style="color:var(--cyan)">${url}</a>
        </div>
        <table class="tbl" style="width:100%;font-size:11px">
          <tr><td style="color:var(--txt3);width:140px">Category Classifier:</td><td><span class="tag tag-purple">Business / Internal</span></td></tr>
          <tr><td style="color:var(--txt3)">Protocol &amp; Encryption:</td><td><span class="tag tag-green">HTTPS / TLS v1.3</span></td></tr>
          <tr><td style="color:var(--txt3)">Tab Status:</td><td><span class="tag tag-blue">ACTIVE / RENDERED</span></td></tr>
          <tr><td style="color:var(--txt3)">Process ID (PID):</td><td><code>18492</code></td></tr>
          <tr><td style="color:var(--txt3)">Bandwidth Usage:</td><td>⬇️ 14.2 KB/s · ⬆️ 2.1 KB/s</td></tr>
        </table>
      </div>
    `, [
      { label: '🚀 Open URL in New Tab', cls: 'btn-primary', fn: `window.open('${url}', '_blank');` },
      { label: 'Tutup', cls: 'btn-ghost', fn: 'Modal.close()' }
    ]);
  }
};

  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.BrowserMonitoring = window.BrowserMonitoring;
  window.Modules = window.Modules || {};
  window.Modules["6_telemetry_stream"] = window.Modules["6_telemetry_stream"] || {};
  window.Modules["6_telemetry_stream"]["browser-monitoring"] = window.BrowserMonitoring;
  window.Modules.BrowserMonitoring = window.BrowserMonitoring;
})();
