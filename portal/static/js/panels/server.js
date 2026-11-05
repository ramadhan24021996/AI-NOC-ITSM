/* panels/server.js
 * Server health panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      server: {
        async load() {
          const health = await DataService.loadHealth();
          const audits = await DataService.loadAudits();
          DataService._audits = audits;
          this._renderHealth(health, audits);
          this._renderAuditHistory(audits);
          this._renderOfflineDevices();
        },
        _renderHealth(h, audits) {
          const score = h.health_score || 0;
          const color = score >= 90 ? 'var(--green)' : score >= 70 ? 'var(--orange2)' : 'var(--red2)';
          const el = document.getElementById('srv-score');
          if (el) { el.innerHTML = score + '<span style="font-size:18px">%</span>'; el.style.color = color; }
          setEl('srv-last-update', 'Update: ' + timeSince(h.timestamp) + ' · Auditor ' + h.auditor_version);
          { const _el = document.getElementById('bdg-server'); if (_el) _el.textContent = score + '%'; }
          const comps = h.components || {};
          htmlEl('srv-status-pills', Object.entries(comps).map(([k, v]) => `<span class="tag ${v.status === 'OK' ? 'tag-green' : v.status === 'WARNING' ? 'tag-orange' : 'tag-red'}">${v.status === 'OK' ? '<i class="fa-solid fa-circle-check" style="color:var(--green);margin-right:4px"></i>' : '<i class="fa-solid fa-triangle-exclamation" style="color:var(--orange);margin-right:4px"></i>'} ${k}</span>`).join(''));
          htmlEl('srv-comp-detail', Object.entries(comps).map(([k, v]) => {
            const cls = v.status === 'OK' ? 'st-ok' : v.status === 'WARNING' ? 'st-warn' : 'st-err';
            const pct = v.status === 'OK' ? 100 : v.status === 'WARNING' ? 50 : 0;
            return `<div class="li-row"><span class="li-name"><i class="fa-solid fa-caret-right" style="color:var(--blue);margin-right:6px"></i>${k}</span><div style="text-align:right"><span class="li-status ${cls}">${v.status}</span><div style="font-size:9.5px;color:var(--txt3);margin-top:1px;max-width:200px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap">${v.detail || ''}</div></div></div><div class="pb" style="margin-bottom:6px"><div class="pb-fill ${v.status === 'OK' ? 'pb-green' : v.status === 'WARNING' ? 'pb-orange' : 'pb-red'}" style="width:${pct}%;animation:none"></div></div>`;
          }).join(''));

          // Health chart
          const history = audits || DataService._audits || [];
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
              return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            });
            const scores = trendAudits.map(a => a.health_score || 0);
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
          } else {
            Charts.create('chart-health-score', 'bar', ['Health Score'], [{ data: [score], backgroundColor: resolvedColor, borderRadius: 4, barThickness: 40 }], { yOpts: { max: 100, min: 0 }, legend: false });
          }
        },
        _renderAuditHistory(audits) {
          const tbody = document.getElementById('tbody-gov-audit');
          const srvTbody = document.getElementById('srv-audit-history');
          const html = (Array.isArray(audits) ? audits : []).map(a => `<tr>
        <td style="font-size:10px;color:var(--txt2)">${(a.timestamp || '').toString().slice(0, 16)}</td>
        <td><b style="color:${(a.health_score || 0) >= 80 ? 'var(--green2)' : 'var(--orange2)'}">${a.health_score || '?'}%</b></td>
        <td>${statusTag(a.status)}</td>
        <td style="font-size:10px;color:var(--txt2)">${a.failed_components || 'None'}</td>
      </tr>`).join('');
          if (srvTbody) srvTbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada riwayat audit</td></tr>';
          if (tbody) tbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--txt2)">Tidak ada riwayat audit</td></tr>';
        },
        _renderOfflineDevices() {
          const offDevs = DataService._devices.filter(d => d.status !== 'ONLINE').map(d => d.name);
          setEl('srv-offline-tag', offDevs.length + ' perangkat');
          htmlEl('srv-offline-list', offDevs.length === 0 ? '<div class="empty-state"><div class="es-icon"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i></div><div class="es-text">Tidak ada perangkat offline</div></div>'
            : offDevs.map(name => `<div class="li-row"><span class="li-name"><i class="fa-solid fa-circle-xmark" style="color:var(--red);margin-right:6px"></i>${name}</span><div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px"><span class="tag tag-red">OFFLINE</span><span style="font-size:9.5px;color:var(--txt3)">Dead Man Switch Active</span></div></div>`).join(''));
        },
        _renderTable(incidents) {
          const tbody = document.getElementById('tbody-incident');
          if (!tbody) return;
          // De-duplicate by unique incident ID
          const seen = new Set();
          const deduped = incidents.filter(inc => {
            const id = inc.incident_id || inc.id;
            if (!id) return true;
            if (seen.has(id)) return false;
            seen.add(id);
            return true;
          });
          tbody.innerHTML = deduped.map(inc => {
            const conf = ((inc.confidence || 0) * 100).toFixed(0);
            const rawSev = sevTag(inc.flag);
            const sevText = rawSev.replace(/<[^>]*>/g, '').trim();
            const resolved = inc.status === 'RESOLVED' || inc.status === 'SOLVED VERIFIED';
            const escalated = inc.status === 'ESCALATED';
            const deviceLabel = inc.agent || inc.device_name || 'System';
            const flagLabel = humanFlag(inc.flag || inc.status);
            const rootCause = humanRootCause(inc.flag, inc.evidence);

            let statusBadge = '';
            if (resolved) {
              statusBadge = '<span class="tag tag-green">✅ Selesai</span>';
            } else if (escalated) {
              statusBadge = '<span class="tag tag-orange">📣 Diteruskan</span>';
            }

            return `<tr data-site="${inc.location || ''}" data-sev="${sevText}" class="${resolved ? 'resolved-row' : ''}" onclick="Panels.incident.selectRow(this)" title="${rootCause}">
          <td><code style="font-size:9.5px;color:var(--blue2)">${(inc.incident_id || inc.id || '—').toString().slice(0, 14)}</code></td>
          <td><b>${deviceLabel}</b></td>
          <td><span class="site-badge" onclick="event.stopPropagation(); Panels.incident.filterBySite('${inc.location || ''}')">${inc.location || '—'}</span></td>
          <td><span class="tag tag-blue">L${inc.layer || '?'}</span></td>
          <td style="font-size:11px">${flagLabel}</td>
          <td><span class="sev-tag-clickable" onclick="event.stopPropagation(); Panels.incident.filterBySeverity('${sevText}')">${rawSev}</span></td>
          <td><span style="color:${conf >= 80 ? 'var(--green2)' : conf >= 50 ? 'var(--orange2)' : 'var(--red2)'}">${conf}%</span></td>
          <td style="font-size:10px;color:var(--txt2)">${timeSince(inc.timestamp)}</td>
          <td style="display:flex;gap:4px" onclick="event.stopPropagation()">
            ${resolved || escalated ? statusBadge : `
              <button class="btn btn-success btn-xs" onclick="Panels.incident.resolve('${inc.incident_id || inc.id}','${deviceLabel}')">✓</button>
              <button class="btn btn-primary btn-xs" onclick="Panels.incident.viewDetail('${inc.incident_id || inc.id}')">👁</button>
              <button class="btn btn-purple btn-xs" onclick="Panels.incident.viewTimeline('${inc.incident_id || inc.id}')">⏱️</button>
              <button class="btn btn-warning btn-xs" onclick="Panels.incident.escalate('${inc.incident_id || inc.id}')">↑</button>
            `}
          </td>
        </tr>`;
          }).join('') || '<tr><td colspan="9" style="text-align:center;padding:16px;color:var(--green2)">✅ Tidak ada insiden aktif</td></tr>';
          setEl('tri-count-txt', incidents.length + ' insiden');
        },
        selectRow(tr) {
          document.querySelectorAll('#tbody-incident tr').forEach(r => r.classList.remove('selected-row'));
          tr.classList.add('selected-row');
        },
        filterBySite(site) {
          const siteSelect = document.getElementById('tri-filter-site');
          if (siteSelect) {
            siteSelect.value = site;
            Tables.applyFilters('tbl-incident');
          }
        },
        filterBySeverity(sev) {
          const sevSelect = document.getElementById('tri-filter-sev');
          if (sevSelect) {
            const map = {
              'KRITIS': 'CRITICAL',
              'TINGGI': 'HIGH',
              'SEDANG': 'MEDIUM',
              'RENDAH': 'LOW'
            };
            sevSelect.value = map[sev] || '';
            Tables.applyFilters('tbl-incident');
          }
        },
        resolve(id, device) {
          const devLabel = device || 'System';
          Modal.confirm('✅ Resolve Incident', 'Tandai insiden ' + id + ' (' + devLabel + ') sebagai RESOLVED?', async () => {
            Modal.close();
            if (devLabel !== 'System') await DataService.sendCommand('RESOLVE_ISSUE', devLabel);
            const r = await DataService.resolveIncident(id, devLabel);
            if (r && (r.status === 'success' || r.status === 'SUCCESS')) {
              const inc = DataService._incidents.find(i => (i.incident_id || i.id) == id);
              if (inc) inc.status = 'RESOLVED';
              this.load();
              Notify.toast('✅ Resolved', 'Insiden ' + id + ' ditandai RESOLVED', 'ok');
              LogStreamer.add('OK', 'INCIDENT', 'Incident ' + id + ' resolved by operator');
            } else {
              Notify.toast('❌ Error', 'Gagal menandai insiden sebagai RESOLVED', 'err');
            }
          });
        },
        async viewDetail(id) {
          // Show skeleton immediately
          Modal.show('Detail Insiden ' + id, `<div style="text-align:center;padding:32px;color:var(--txt2)"><div style="width:18px;height:18px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block;margin-right:8px"></div> Memuat data live...</div>`, [], '📋');
          
          try {
            const resp = await fetch('/api/incidents/' + id + '/detail');
            const inc = await resp.json();
            if (!inc || inc.status === 'error') throw new Error(inc?.message || 'not found');

            const analysis = inc.analysis || 'Tidak ada analisis AI';
            const steps = inc.steps || [];
            const devName = inc.device_name || 'Unknown';
            const conf = Math.round((inc.confidence || 0) * 100);

            const flagHuman = humanFlag(inc.flag);
            const evidenceHuman = humanEvidence(inc.evidence, inc.flag);
            const statusHuman = humanStatus(inc.status || 'ACTIVE');
            const rootCauseHuman = humanRootCause(inc.flag, inc.evidence);
            const confColor = conf >= 80 ? 'var(--green2)' : conf >= 50 ? 'var(--orange2)' : 'var(--red2)';

            Modal.show('🔍 Detail Insiden #' + id, `
          <div style="display:flex;flex-direction:column;gap:14px;font-size:12px">

            <!-- Status Banner -->
            <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:8px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center">
              <span style="font-weight:700;font-size:13px">${devName}</span>
              <span style="font-size:11px;color:var(--txt2)">${statusHuman}</span>
            </div>

            <!-- Masalah & Akar Penyebab -->
            <div style="background:var(--bg3);border-radius:8px;padding:12px 14px;border:1px solid var(--bd2)">
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--txt3);margin-bottom:6px">🔍 Masalah Terdeteksi</div>
              <div style="font-weight:600;font-size:13px;color:var(--orange2)">${flagHuman}</div>
            </div>

            <div style="background:var(--bg3);border-radius:8px;padding:12px 14px;border:1px solid var(--bd2)">
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--txt3);margin-bottom:6px">🎯 Akar Penyebab (Root Cause)</div>
              <div style="color:var(--txt2);line-height:1.6">${rootCauseHuman}</div>
            </div>

            <div style="background:var(--bg3);border-radius:8px;padding:12px 14px;border:1px solid var(--bd2)">
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--txt3);margin-bottom:6px">📋 Detail Kondisi</div>
              <div style="color:var(--txt2);line-height:1.6">${evidenceHuman}</div>
            </div>

            <!-- Grid Metadata -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div style="background:var(--bg3);border-radius:6px;padding:8px 10px;border:1px solid var(--bd2)">
                <div style="font-size:9.5px;color:var(--txt3);margin-bottom:3px">Perangkat</div>
                <div style="font-weight:600">${devName}</div>
              </div>
              <div style="background:var(--bg3);border-radius:6px;padding:8px 10px;border:1px solid var(--bd2)">
                <div style="font-size:9.5px;color:var(--txt3);margin-bottom:3px">Lokasi</div>
                <div>${inc.location || 'Tidak diketahui'}</div>
              </div>
              <div style="background:var(--bg3);border-radius:6px;padding:8px 10px;border:1px solid var(--bd2)">
                <div style="font-size:9.5px;color:var(--txt3);margin-bottom:3px">Tingkat Keyakinan AI</div>
                <div style="color:${confColor};font-weight:700">${conf}% — ${conf>=80?'Tinggi':conf>=50?'Sedang':'Rendah'}</div>
              </div>
              <div style="background:var(--bg3);border-radius:6px;padding:8px 10px;border:1px solid var(--bd2)">
                <div style="font-size:9.5px;color:var(--txt3);margin-bottom:3px">Layer Sistem</div>
                <div><span class="tag tag-blue">L${inc.layer || '?'}</span></div>
              </div>
            </div>

            <!-- AI Analysis -->
            ${analysis && analysis !== 'Tidak ada analisis AI' ? `
            <div style="background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.2);border-radius:8px;padding:12px 14px">
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--purple2);margin-bottom:6px">🤖 Analisis AI</div>
              <div style="color:var(--txt2);line-height:1.7;font-size:11.5px">${analysis}</div>
            </div>` : ''}

            <!-- Langkah Perbaikan -->
            ${steps && steps.length > 0 ? `
            <div style="background:rgba(34,197,94,.07);border:1px solid rgba(34,197,94,.2);border-radius:8px;padding:12px 14px">
              <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--green2);margin-bottom:8px">✅ Langkah Perbaikan yang Direkomendasikan</div>
              <ol style="color:var(--txt2);padding-left:18px;line-height:1.8;font-size:11.5px">${steps.map(s => '<li>' + s + '</li>').join('')}</ol>
            </div>` : ''}

          </div>`,
              [
                { label: '✓ Resolve', cls: 'btn-success', fn: `Panels.incident.resolve('${id}','${devName}');Modal.close()` },
                { label: '⏱️ Timeline', cls: 'btn-purple', fn: `Modal.close(); Panels.incident.viewTimeline('${id}')` },
                { label: '🔬 Analyze RCA', cls: 'btn-primary', fn: `Modal.close(); Nav.go('rca', document.querySelector('[data-panel=rca]')); document.getElementById('rca-select').value='${id}'; Panels.rca.analyze()` }
              ], '📋');
          } catch(e) {
            Modal.show('Detail Insiden ' + id, `<div style="color:var(--red2);padding:16px">❌ Gagal memuat detail: ${e.message}</div>`, [{label:'Tutup',cls:'btn-ghost',fn:()=>Modal.close()}], '📋');
          }
        },
        async viewTimeline(id) {
          // Show loading skeleton
          Modal.show('Enterprise Incident Lifecycle Timeline (Sprint L+) - ID ' + id, `<div style="text-align:center;padding:32px;color:var(--txt2)"><div style="width:18px;height:18px;border:2px solid var(--purple);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;display:inline-block;margin-right:8px"></div> Memuat timeline live dari PostgreSQL...</div>`, [], '⏱️');

          let inc;
          try {
            const resp = await fetch('/api/incidents/' + id + '/detail');
            inc = await resp.json();
            if (!inc || inc.status === 'error') throw new Error(inc?.message || 'not found');
          } catch(e) {
            Modal.show('Timeline Error', `<div style="color:var(--red2);padding:16px">❌ Gagal memuat timeline: ${e.message}</div>`, [{label:'Tutup',cls:'btn-ghost',fn:()=>Modal.close()}], '⏱️');
            return;
          }

          const raw = inc.raw_timeline_data || {};
          const formatTime = (isoString) => {
            if (!isoString || isoString === '0001-01-01T00:00:00Z') return '<span style="color:var(--muted)">-</span>';
            const d = new Date(isoString);
            if (isNaN(d.getTime())) return '<span style="color:var(--muted)">-</span>';
            return d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' <span style="font-size:9px;color:var(--muted)">' + d.toLocaleDateString() + '</span>';
          };

          const formatDur = (secs) => {
            if (!secs) return '-';
            if (secs < 60) return secs + 's';
            if (secs < 3600) return Math.floor(secs / 60) + 'm ' + (secs % 60) + 's';
            return Math.floor(secs / 3600) + 'h ' + Math.floor((secs % 3600) / 60) + 'm';
          };

          let stepsHtml = '<div style="color:var(--muted)">No AI cognitive steps logged yet.</div>';
          if (raw.ai_thinking_steps && raw.ai_thinking_steps.length > 0) {
            stepsHtml = raw.ai_thinking_steps.map((s, idx) => `
          <div style="display:flex;flex-direction:column;align-items:center;min-width:80px">
            <div style="background:var(--blue);color:#fff;width:24px;height:24px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold">${idx + 1}</div>
            <div style="font-size:10px;margin-top:4px;font-weight:600;text-align:center">${s.step}</div>
            <div style="font-size:8px;color:var(--muted)">${new Date(s.time).toLocaleTimeString('id-ID')}</div>
          </div>
          ${idx < raw.ai_thinking_steps.length - 1 ? '<div style="flex:1;height:2px;background:rgba(255,255,255,0.1);margin:0 4px;margin-bottom:12px"></div>' : ''}
        `).join('');
          }

          let confHtml = '<div style="color:var(--muted);font-size:10px">No data.</div>';
          if (raw.confidence_timeline && raw.confidence_timeline.length > 0) {
            confHtml = raw.confidence_timeline.map(c => `
          <div style="display:flex;justify-content:space-between;border-bottom:1px dashed rgba(255,255,255,0.05);padding:2px 0;font-size:10.5px">
            <span>${new Date(c.time).toLocaleTimeString('id-ID')}</span>
            <span style="color:var(--green2)">${c.val}%</span>
          </div>
        `).join('');
          }

          let evHtml = '<div style="color:var(--muted);font-size:10px">No data.</div>';
          if (raw.evidence_timeline && raw.evidence_timeline.length > 0) {
            evHtml = raw.evidence_timeline.map(e => `
          <div style="display:flex;justify-content:space-between;border-bottom:1px dashed rgba(255,255,255,0.05);padding:2px 0;font-size:10.5px">
            <span>${new Date(e.time).toLocaleTimeString('id-ID')}</span>
            <span style="color:var(--orange2);text-overflow:ellipsis;overflow:hidden;white-space:nowrap;max-width:120px" title="${e.desc}">${e.desc}</span>
          </div>
        `).join('');
          }

          Modal.show('Enterprise Incident Lifecycle Timeline (Sprint L+) - ID ' + id, `
        <div style="font-size:11.5px;max-height:70vh;overflow-y:auto;padding-right:8px">
          
          <div style="display:flex; justify-content:space-between; margin-bottom:12px; padding:8px; background:rgba(255,255,255,0.05); border-radius:4px; text-align:center">
            <div><div class="inp-label">Detection</div><div style="font-weight:600;color:var(--red2)">${formatDur(inc.detection_duration_sec)}</div></div>
            <div><div class="inp-label">RCA</div><div style="font-weight:600;color:var(--orange2)">${formatDur(raw.rca_duration_sec)}</div></div>
            <div><div class="inp-label">Approval</div><div style="font-weight:600;color:var(--purple2)">${formatDur(inc.approval_duration_sec)}</div></div>
            <div><div class="inp-label">Execution</div><div style="font-weight:600;color:var(--blue2)">${formatDur(raw.execution_duration_sec)}</div></div>
            <div><div class="inp-label">MTTR (Total)</div><div style="font-weight:600;color:var(--green2)">${formatDur(inc.total_incident_duration_sec)}</div></div>
          </div>
          
          <div class="inp-label" style="margin-top:16px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px"><i class="fa-solid fa-brain"></i> AI Thinking Sequence</div>
          <div style="display:flex;gap:2px;overflow-x:auto;padding:12px 0;align-items:center;">
             ${stepsHtml}
          </div>

          <div class="inp-label" style="margin-top:16px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px"><i class="fa-solid fa-chart-area"></i> Historical Metric Overlay (5m Window)</div>
          <div style="background:rgba(0,0,0,0.2);padding:8px;border-radius:4px;margin-top:8px;margin-bottom:16px">
            <div class="chart-box" style="height:140px">
              <canvas id="chart-hist-overlay"></canvas>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; margin-bottom:16px">
            <div style="background:rgba(0,0,0,0.2);padding:8px;border-radius:4px">
              <div style="font-weight:600;margin-bottom:8px;color:var(--txt)"><i class="fa-solid fa-chart-line"></i> Confidence Timeline</div>
              ${confHtml}
            </div>
            <div style="background:rgba(0,0,0,0.2);padding:8px;border-radius:4px">
              <div style="font-weight:600;margin-bottom:8px;color:var(--txt)"><i class="fa-solid fa-magnifying-glass"></i> Evidence Timeline</div>
              ${evHtml}
            </div>
          </div>

          <div class="inp-label" style="border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;margin-bottom:8px"><i class="fa-solid fa-list-check"></i> Standard Milestone Audit</div>
          <table style="width:100%; border-collapse:collapse" class="timeline-table">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:var(--muted)">
                <th style="padding:6px;font-weight:500">Milestone Phase</th>
                <th style="padding:6px;font-weight:500;text-align:right">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-1" style="width:20px;color:var(--txt2)"></i> First Evidence Received</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.first_evidence_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-2" style="width:20px;color:var(--txt2)"></i> Issue Started Tracking</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.issue_started_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-3" style="width:20px;color:var(--txt2)"></i> AI Anomaly Detection</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.ai_detection_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-4" style="width:20px;color:var(--txt2)"></i> Correlation Engine Completed</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.correlation_completed_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-5" style="width:20px;color:var(--txt2)"></i> Root Cause Engine Completed</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.root_cause_completed_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-6" style="width:20px;color:var(--txt2)"></i> AI Recommendation Generated</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.recommendation_generated_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-7" style="width:20px;color:var(--txt2)"></i> Human Operator Approved</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.human_approval_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-8" style="width:20px;color:var(--txt2)"></i> Auto-Remediation Execution</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.execution_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-9" style="width:20px;color:var(--txt2)"></i> Verification Post-Execution</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.verification_time)}</td>
              </tr>
              <tr style="border-bottom:1px dashed rgba(255,255,255,0.05)">
                <td style="padding:6px"><i class="fa-solid fa-check" style="width:20px;color:var(--green)"></i> Incident Solved</td>
                <td style="padding:6px;color:var(--green2);text-align:right">${formatTime(inc.solved_time)}</td>
              </tr>
              <tr>
                <td style="padding:6px"><i class="fa-solid fa-lock" style="width:20px;color:var(--muted)"></i> Incident Closed</td>
                <td style="padding:6px;text-align:right">${formatTime(inc.closed_time)}</td>
              </tr>
            </tbody>
          </table>
        </div>`,
            [{ label: 'Tutup', cls: 'btn-ghost', fn: () => Modal.close() }], '⏱️');

          setTimeout(() => {
            if (!document.getElementById('chart-hist-overlay')) return;
            const labels = [];
            const cpuData = [];
            const memData = [];
            let d = inc.issue_started_time ? new Date(inc.issue_started_time) : new Date(inc.timestamp || Date.now());
            d.setMinutes(d.getMinutes() - 5);
            let cpuBase = inc.cpu || 0;
            let memBase = inc.memory || 0;
            // Use real historical data if available, else flatline (No Fake Data)
            const hist = inc.historical_metrics || [];
            for (let i = 0; i <= 30; i++) {
              labels.push(d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
              let cpuVal = hist[i] ? hist[i].cpu : cpuBase;
              let memVal = hist[i] ? hist[i].memory : memBase;
              cpuData.push(Math.min(100, Math.max(0, cpuVal)));
              memData.push(Math.min(100, Math.max(0, memVal)));
              d.setSeconds(d.getSeconds() + 10);
            }
            Charts.create('chart-hist-overlay', 'line', labels, [
              { label: 'CPU Usage (%)', data: cpuData, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.4, borderWidth: 2 },
              { label: 'Memory (%)', data: memData, borderColor: '#3b82f6', backgroundColor: 'transparent', borderDash: [5, 5], tension: 0.4, borderWidth: 2 }
            ], { legend: true, yOpts: { min: 0, max: 100 }, xOpts: { ticks: { maxTicksLimit: 6 } } });
          }, 100);
        },
        escalate(id) {
          const inc = DataService._incidents.find(i => (i.incident_id || i.id) == id);
          if (!inc) return;
          const devName = inc.agent || inc.device_name || 'Unknown';
          Modal.confirm('↑ Escalate Incident', 'Eskalasi insiden ' + id + ' ke AI Guru?', async () => {
            Modal.close();
            const r = await DataService.escalateIncident(id, devName);
            if (r && (r.status === 'success' || r.status === 'SUCCESS')) {
              inc.status = 'ESCALATED';
              this.load();
              Notify.toast('↑ Escalate', 'Insiden ' + id + ' dieskalasi ke AI Guru', 'warn', 3000);
              LogStreamer.add('WARN', 'INCIDENT', 'Escalation: ' + id + ' → guru_escalation_queue (Redis)');
            } else {
              Notify.toast('❌ Error', 'Gagal mengekskalasi insiden', 'err');
            }
          });
        },
        focusIncident(id) { Nav.go('incident', document.querySelector('[data-panel=incident]')); }
      },

      /* ---- RCA ---- */

});