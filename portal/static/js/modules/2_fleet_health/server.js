/* modules/2_fleet_health/server.js
 * Atomic Design — 3. Modules Layer (2_fleet_health / server)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["2_fleet_health"] = window.Modules["2_fleet_health"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      server: {
        _chartReady: false,
        _auditing: false,
        _busBound: false,

        _esc(str) {
          if (typeof _esc === 'function') return _esc(str);
          return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        },

        _bindBus() {
          if (this._busBound) return;
          const bus = (window.Services && window.Services.EventBus) || (typeof Bus !== 'undefined' ? Bus : null);
          if (!bus || typeof bus.on !== 'function') return;
          this._busBound = true;
          bus.on('health:loaded', async (health) => {
            if (typeof isPanelActive === 'function' && isPanelActive('server')) {
              const ds = window.Services.Data || DataService;
              const audits = ds._audits || await ds.loadAudits().catch(() => []);
              this._renderHealth(health, audits);
            }
          });
        },

        async load(silent = false) {
          this._bindBus();
          const ds = window.Services.Data || DataService;
          const [health, audits] = await Promise.all([
            ds.loadHealth(),
            ds.loadAudits()
          ]);
          ds._audits = audits;
          this._renderHealth(health, audits);
          this._renderAuditHistory(audits);

          window.ActiveIntervals = window.ActiveIntervals || {};
          if (!window.ActiveIntervals.server_health) {
            window.ActiveIntervals.server_health = setInterval(() => {
              const panel = document.getElementById('p-server');
              if (document.hidden || !panel || !panel.classList.contains('active')) return;
              this.load(true);
            }, 15000);
          }
        },

        async runAudit() {
          if (this._auditing) return;
          this._auditing = true;
          const btn = document.querySelector('#p-server button[onclick*="runAudit"]');
          const origHtml = btn ? btn.innerHTML : '';
          if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:6px"></i>Auditing...';
          }

          try {
            const ds = window.Services.Data || DataService;
            const res = await ds.fetch('/api/system/audit/run', { method: 'POST' });
            if (res && res.health_score !== undefined) {
              ds._health = res;
              const audits = await ds.loadAudits();
              ds._audits = audits;
              this._renderHealth(res, audits);
              this._renderAuditHistory(audits);
              if (typeof Bus !== 'undefined' && Bus.emit) Bus.emit('health:loaded', res);
              if (typeof Notify !== 'undefined' && Notify.toast) {
                Notify.toast(
                  res.health_score >= 80 ? '✅ Audit Selesai' : '⚠️ Audit Selesai (Degraded)',
                  `Health Score: ${res.health_score}% (${res.status}) · ${res.duration_ms || 1} ms`,
                  res.health_score >= 80 ? 'ok' : 'warn',
                  3000
                );
              }
              if (typeof LogStreamer !== 'undefined' && LogStreamer.add) {
                LogStreamer.add(res.health_score >= 80 ? 'OK' : 'WARN', 'AUDIT', `Manual SystemAuditor v2.2 run: ${res.health_score}% (${res.status})`);
              }
            } else {
              if (typeof Notify !== 'undefined' && Notify.toast) {
                Notify.toast('❌ Audit Gagal', 'Gagal mengeksekusi SystemAuditor v2.2', 'err', 3000);
              }
            }
          } catch (e) {
            if (typeof Notify !== 'undefined' && Notify.toast) {
              Notify.toast('❌ Audit Error', e.message, 'err', 3000);
            }
          } finally {
            this._auditing = false;
            if (btn) {
              btn.disabled = false;
              btn.innerHTML = origHtml || '<i class="fa-solid fa-rotate" style="margin-right:6px"></i>Run Audit';
            }
          }
        },

        _renderHealth(h, audits) {
          if (!h) return;
          const score = Number(h.health_score || 0);
          const color = score >= 90 ? 'var(--green)' : score >= 70 ? 'var(--orange2)' : 'var(--red2)';
          const el = document.getElementById('srv-score');
          if (el) {
            el.innerHTML = `${this._esc(score)}<span style="font-size:18px">%</span>`;
            el.style.color = color;
          }
          const tsLabel = typeof timeSince === 'function' ? timeSince(h.timestamp) : (h.timestamp || '—');
          setEl('srv-last-update', `Update: ${tsLabel} · Auditor ${h.auditor_version || 'v2.2'}${h.duration_ms ? ` · ${h.duration_ms} ms` : ''}`);
          { const _el = document.getElementById('bdg-server'); if (_el) _el.textContent = score + '%'; }

          const comps = h.components || {};
          htmlEl('srv-status-pills', Object.entries(comps).map(([k, v]) => {
            const st = String((v && v.status) || v || 'ERROR').toUpperCase();
            const isOk = st === 'OK';
            const isWarn = st === 'WARNING';
            const cls = isOk ? 'tag-green' : isWarn ? 'tag-orange' : 'tag-red';
            const icon = isOk
              ? '<i class="fa-solid fa-circle-check" style="color:var(--green);margin-right:4px"></i>'
              : '<i class="fa-solid fa-triangle-exclamation" style="color:' + (isWarn ? 'var(--orange)' : 'var(--red)') + ';margin-right:4px"></i>';
            return `<span class="tag ${cls}" title="${this._esc((v && v.detail) || st)}">${icon}${this._esc(k)}</span>`;
          }).join(''));

          htmlEl('srv-comp-detail', Object.entries(comps).map(([k, v]) => {
            const st = String((v && v.status) || v || 'ERROR').toUpperCase();
            const isOk = st === 'OK';
            const isWarn = st === 'WARNING';
            const cls = isOk ? 'st-ok' : isWarn ? 'st-warn' : 'st-err';
            const pct = isOk ? 100 : isWarn ? 50 : 0;
            const detail = (v && v.detail) ? v.detail : (isOk ? 'Operational' : 'Check failed');
            return `<div class="li-row"><span class="li-name"><i class="fa-solid fa-caret-right" style="color:var(--blue);margin-right:6px"></i>${this._esc(k)}</span><div style="text-align:right"><span class="li-status ${cls}">${this._esc(st)}</span><div style="font-size:9.5px;color:var(--txt3);margin-top:1px;max-width:240px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap" title="${this._esc(detail)}">${this._esc(detail)}</div></div></div><div class="pb" style="margin-bottom:6px"><div class="pb-fill ${isOk ? 'pb-green' : isWarn ? 'pb-orange' : 'pb-red'}" style="width:${pct}%;transition:width .5s ease"></div></div>`;
          }).join(''));

          // Health chart (flicker-free update when chart already exists)
          const ds = window.Services.Data || DataService;
          const history = Array.isArray(audits) && audits.length > 0 ? audits : (ds._audits || []);
          const resolveHex = (c) => {
            if (typeof c === 'string' && c.startsWith('var(')) {
              const varName = c.substring(4, c.length - 1);
              return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || c;
            }
            return c;
          };
          const resolvedColor = resolveHex(color);

          if (history.length > 0) {
            const trendAudits = [...history].reverse().slice(-10);
            const labels = trendAudits.map(a => {
              const t = new Date(a.timestamp || Date.now());
              return isNaN(t.getTime()) ? '—' : t.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            });
            const scores = trendAudits.map(a => Number(a.health_score || 0));

            if (this._chartReady && Charts._instances && Charts._instances['chart-health-score'] && typeof Charts.update === 'function') {
              Charts.update('chart-health-score', labels, [scores]);
            } else {
              Charts.create('chart-health-score', 'line', labels, [{
                label: 'Health Score Trend',
                data: scores,
                borderColor: resolvedColor,
                backgroundColor: resolvedColor + '18',
                fill: true,
                tension: 0.4,
                borderWidth: 2.5,
                pointRadius: 3,
                pointHoverRadius: 5
              }], {
                yOpts: { max: 100, min: 0 },
                legend: false
              });
              this._chartReady = true;
            }
          } else {
            Charts.create('chart-health-score', 'bar', ['Health Score'], [{ data: [score], backgroundColor: resolvedColor, borderRadius: 4, barThickness: 40 }], { yOpts: { max: 100, min: 0 }, legend: false });
            this._chartReady = false;
          }
        },

        _renderAuditHistory(audits) {
          const tbody = document.getElementById('tbody-gov-audit');
          const srvTbody = document.getElementById('srv-audit-history');
          const list = Array.isArray(audits) ? audits : [];
          const html = list.map(a => {
            let timeFormatted = '—';
            if (a.timestamp) {
              const dt = new Date(a.timestamp);
              timeFormatted = isNaN(dt.getTime())
                ? this._esc(String(a.timestamp).slice(0, 16))
                : dt.toLocaleString('id-ID', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
            }
            const sc = Number(a.health_score || 0);
            const dur = a.audit_duration_ms ? ` <span style="font-size:9px;color:var(--txt3)">(${a.audit_duration_ms}ms)</span>` : '';
            const failed = a.failed_components && a.failed_components !== 'None'
              ? `<span style="color:var(--red2)">${this._esc(a.failed_components)}</span>`
              : '<span style="color:var(--green2)">None</span>';
            return `<tr>
        <td style="font-size:10px;color:var(--txt2);white-space:nowrap">${timeFormatted}${dur}</td>
        <td><b style="color:${sc >= 80 ? 'var(--green2)' : sc >= 50 ? 'var(--orange2)' : 'var(--red2)'}">${sc}%</b></td>
        <td>${statusTag(a.status)}</td>
        <td style="font-size:10px;color:var(--txt2)">${failed}</td>
      </tr>`;
          }).join('');
          if (srvTbody) srvTbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada riwayat audit</td></tr>';
          if (tbody) tbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada riwayat audit</td></tr>';
        }
      }

});
window.Modules["2_fleet_health"]["server"] = window.Panels;
