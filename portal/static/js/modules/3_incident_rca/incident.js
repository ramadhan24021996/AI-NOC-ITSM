/* modules/3_incident_rca/incident.js
 * Atomic Design — 3. Modules Layer (3_incident_rca / incident)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["3_incident_rca"] = window.Modules["3_incident_rca"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      incident: {
        _busBound: false,
        _incidents: [],
        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          const onChange = () => {
            const p = document.getElementById('p-incident');
            if (p && p.classList.contains('active')) this.load();
          };
          bus.on('incident:status_changed', onChange);
          bus.on('incident:verified', onChange);
          bus.on('incidents:loaded', (data) => {
            const p = document.getElementById('p-incident');
            if (p && p.classList.contains('active') && Array.isArray(data)) {
              this._renderTable(data);
            }
          });
        },
        async load() {
          this._bindBus();
          const svc = window.Services.Data || DataService;
          try {
            const [data, devices] = await Promise.all([
              svc.loadIncidents(),
              (Array.isArray(svc._devices) && svc._devices.length > 0) ? Promise.resolve(svc._devices) : svc.loadDevices().catch(() => [])
            ]);
            if (Array.isArray(devices)) {
              const onlineCnt = devices.filter(d => d.status === 'ONLINE').length;
              const offlineCnt = devices.length - onlineCnt;
              setEl('tri-online', onlineCnt);
              setEl('tri-offline', offlineCnt);
            }
            this._renderTable(data);
          } catch (e) {
            console.error("Failed to load incidents:", e);
          }
          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.incident_triage) {
            window.ActiveIntervals.incident_triage = setInterval(() => {
              const p = document.getElementById('p-incident');
              if (document.hidden || !p || !p.classList.contains('active')) return;
              this.load();
            }, 10000);
          }
        },
        _sevTag(sev) {
          const s = (sev || 'HIGH').toUpperCase();
          if (s === 'CRITICAL' || s === 'KRITIS') return 'tag-red';
          if (s === 'HIGH' || s === 'TINGGI') return 'tag-orange';
          if (s === 'MEDIUM' || s === 'SEDANG') return 'tag-blue';
          return 'tag-gray';
        },
        _statusTag(st) {
          const s = (st || 'OPEN').toUpperCase();
          if (s === 'RESOLVED' || s === 'CLOSED') return 'tag-green';
          if (s === 'IN_PROGRESS' || s === 'PENDING_VERIFICATION') return 'tag-orange';
          return 'tag-red';
        },
        _renderTable(incidents) {
          const tbody = document.getElementById('tbody-incident');
          if (!tbody) return;
          this._incidents = Array.isArray(incidents) ? incidents : [];

          if (this._incidents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:20px;color:var(--txt3)">✓ No active incidents in queue.</td></tr>';
            setEl('tri-count-txt', '0 insiden');
            setEl('tri-active', 0);
            return;
          }

          setEl('tri-active', this._incidents.filter(i => (i.status || '').toUpperCase() !== 'RESOLVED' && (i.status || '').toUpperCase() !== 'CLOSED').length);

          // Populate site filter dropdown dynamically
          const siteSelect = document.getElementById('tri-filter-site');
          if (siteSelect) {
            const sites = [...new Set(this._incidents.map(i => i.location || i.site_id || '').filter(Boolean))].sort();
            const cur = siteSelect.value;
            siteSelect.innerHTML = '<option value="">Semua Site</option>' + sites.map(s => `<option value="${_esc(s)}">${_esc(s)}</option>`).join('');
            if (cur && sites.includes(cur)) siteSelect.value = cur;
          }

          const sevMap = { CRITICAL: 'KRITIS', HIGH: 'TINGGI', MEDIUM: 'SEDANG', LOW: 'RENDAH' };

          tbody.innerHTML = this._incidents.map(inc => {
            const id = inc.incident_id || inc.id;
            const traceId = inc.trace_id || (inc.correlation_id ? String(inc.correlation_id).substring(0, 8) : '—');
            const pc = inc.device_name || inc.pc_name || 'System';
            const site = inc.location || inc.site_id || 'Global';
            const layer = typeof inc.layer === 'number' ? `L${inc.layer}` : (inc.layer || '—');
            const flag = inc.flag || (inc.severity ? inc.severity + '_ALERT' : 'ALERT');
            const sev = (inc.severity || 'HIGH').toUpperCase();
            const status = (inc.status || 'OPEN').toUpperCase();
            const rawConf = Number(inc.confidence);
            const conf = rawConf > 0 ? Math.round(rawConf <= 1 ? rawConf * 100 : rawConf) + '%' : '—';
            const tsRaw = inc.timestamp || inc.created_at;
            const time = tsRaw ? new Date(tsRaw).toLocaleString('id-ID') : '—';

            return `
              <tr style="cursor:pointer" data-sev="${_esc(sev)}" data-sev-id="${_esc(sevMap[sev] || sev)}" data-site="${_esc(site)}" data-status="${_esc(status)}" onclick="Panels.incident.showDetail(${Number(id) || 0})">
                <td><b>#${_esc(id)}</b></td>
                <td><code style="font-size:10px;color:var(--cyan)">${_esc(traceId)}</code></td>
                <td><b style="color:var(--blue2)">${_esc(pc)}</b></td>
                <td><span class="tag tag-gray">${_esc(site)}</span></td>
                <td><span class="tag tag-purple">${_esc(layer)}</span></td>
                <td><code style="color:var(--orange2)">${_esc(flag)}</code></td>
                <td><span class="tag ${this._sevTag(sev)}">${_esc(sev)}</span></td>
                <td><span class="tag ${this._statusTag(status)}">${_esc(status)}</span></td>
                <td><b>${_esc(conf)}</b></td>
                <td><small style="color:var(--txt2)">${_esc(time)}</small></td>
              </tr>
            `;
          }).join('');

          this.applyFilters();
        },
        applyFilters() {
          const q = ((document.getElementById('tri-search') || {}).value || '').toLowerCase().trim();
          const sev = ((document.getElementById('tri-filter-sev') || {}).value || '').toUpperCase();
          const st = ((document.getElementById('tri-filter-status') || {}).value || '').toUpperCase();
          const site = ((document.getElementById('tri-filter-site') || {}).value || '').toLowerCase();
          const tbody = document.getElementById('tbody-incident');
          if (!tbody) return;

          let visible = 0;
          tbody.querySelectorAll('tr[data-sev]').forEach(tr => {
            const matchQ = !q || tr.textContent.toLowerCase().includes(q);
            const matchSev = !sev || (tr.getAttribute('data-sev') || '').toUpperCase() === sev;
            const matchSt = !st || (tr.getAttribute('data-status') || '').toUpperCase() === st;
            const matchSite = !site || (tr.getAttribute('data-site') || '').toLowerCase() === site;
            const show = matchQ && matchSev && matchSt && matchSite;
            tr.classList.toggle('hidden-row', !show);
            tr.style.display = show ? '' : 'none';
            if (show) visible++;
          });
          setEl('tri-count-txt', `${visible} dari ${this._incidents.length} insiden`);
        },
        showDetail(incidentId) {
          const inc = this._incidents.find(i => Number(i.incident_id || i.id) === Number(incidentId));
          if (!inc || typeof Modal === 'undefined') return;
          const id = inc.incident_id || inc.id;
          const steps = Array.isArray(inc.steps) && inc.steps.length > 0
            ? `<ul style="margin:6px 0 0 16px;font-size:11px;color:var(--txt2)">${inc.steps.map(s => `<li>${_esc(s)}</li>`).join('')}</ul>`
            : '<div style="font-size:11px;color:var(--txt3)">Belum ada langkah remediasi.</div>';
          Modal.confirm(
            `🚨 Incident #${_esc(id)} — ${_esc(inc.device_name || inc.pc_name || 'System')}`,
            `<div style="font-size:11.5px;line-height:1.5;max-height:60vh;overflow-y:auto">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
                <div><span style="color:var(--txt3)">Status:</span> <span class="tag ${this._statusTag(inc.status)}">${_esc(inc.status || 'OPEN')}</span></div>
                <div><span style="color:var(--txt3)">Severity:</span> <span class="tag ${this._sevTag(inc.severity)}">${_esc((inc.severity || 'HIGH').toUpperCase())}</span></div>
                <div><span style="color:var(--txt3)">Site:</span> <b>${_esc(inc.location || inc.site_id || 'Global')}</b></div>
                <div><span style="color:var(--txt3)">Model:</span> <code>${_esc(inc.model_used || '—')}</code></div>
              </div>
              <div style="margin-bottom:8px"><b>Analisis AI:</b><div style="background:rgba(0,0,0,.2);padding:8px;border-radius:6px;margin-top:4px;color:var(--txt2)">${_esc(inc.analysis || 'Tidak ada ringkasan analisis.')}</div></div>
              <div style="margin-bottom:8px"><b>Evidence:</b><div style="background:rgba(0,0,0,.2);padding:8px;border-radius:6px;margin-top:4px;font-family:monospace;font-size:10.5px;color:var(--cyan);word-break:break-word">${_esc(inc.evidence || '—')}</div></div>
              <div><b>Rekomendasi Langkah:</b>${steps}</div>
            </div>`,
            () => {
              Modal.close();
              if (typeof Nav !== 'undefined' && typeof Nav.go === 'function') {
                Nav.go('rca');
              }
            }
          );
        }
      },

});

window.Modules["3_incident_rca"]["incident"] = window.Panels;
