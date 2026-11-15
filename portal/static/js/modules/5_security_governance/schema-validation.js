/* panels/schema-validation.js
 * Schema Validation Logs panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      schema_validation_logs: {
        async load() {
          const tbody = document.getElementById('schema-validation-logs-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--blue);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat Schema Validation Logs...</div></td></tr>';
          
          const searchVal = document.getElementById('sv-search-input') ? document.getElementById('sv-search-input').value.trim() : '';
          const statusVal = document.getElementById('sv-status-filter') ? document.getElementById('sv-status-filter').value : 'ALL';
          
          try {
            // Load KPI stats
            const stats = await DataService.fetch('/api/schema_validation_logs/stats').catch(() => null);
            if (stats) {
              if (document.getElementById('sv-total-val')) { const _el = document.getElementById('sv-total-val'); if (_el) _el.innerText = stats.total_validations || '0'; }
              if (document.getElementById('sv-pass-rate')) { const _el = document.getElementById('sv-pass-rate'); if (_el) _el.innerText = stats.pass_rate || '100%'; }
              if (document.getElementById('sv-schema-fails')) { const _el = document.getElementById('sv-schema-fails'); if (_el) _el.innerText = stats.schema_failures || '0'; }
            }

            // Fetch validation logs with query parameters
            let url = `/api/schema_validation_logs?limit=50`;
            if (searchVal) url += `&q=${encodeURIComponent(searchVal)}`;
            if (statusVal && statusVal !== 'ALL') url += `&status=${encodeURIComponent(statusVal)}`;

            const logs = await DataService.fetch(url);
            if (!logs || !Array.isArray(logs) || logs.length === 0) {
              tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:25px;color:var(--txt2)"><i class="fa-solid fa-folder-open" style="font-size:24px;margin-bottom:8px;display:block;color:var(--txt3)"></i>Tidak Ada Schema Validation Failure</td></tr>';
              return;
            }

            tbody.innerHTML = logs.map(l => {
              const actionText = l.action_executed || 'PASS';
              const isInvalid = actionText.includes('INVALID') || actionText.includes('ERROR');
              const badgeClass = isInvalid ? 'bd-rd' : actionText.includes('REPLAY') ? 'bd-purple' : 'bd-gr';
              const timeStr = l.created_at ? new Date(l.created_at).toLocaleString('id-ID') : '—';
              
              const safePrompt = (l.raw_prompt || '').replace(/"/g, '&quot;');
              const safeResp = (l.llm_response || '').replace(/"/g, '&quot;');

              return `<tr>
                <td><b>#${l.id}</b></td>
                <td><span class="badge bd-bl">INC-${l.incident_id || 'SYS'}</span></td>
                <td style="font-size:10.5px;color:var(--txt2)"><span class="badge bd-bl" style="font-size:9.5px">${l.event_id || '—'}</span></td>
                <td style="font-size:10.5px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${safePrompt}">${l.raw_prompt || '—'}</td>
                <td style="font-size:10.5px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${safeResp}">${l.llm_response || '—'}</td>
                <td><span class="badge ${badgeClass}" style="font-size:10px">${actionText}</span></td>
                <td style="font-size:10.5px;color:var(--txt2);white-space:nowrap">${timeStr}</td>
                <td>
                  <div style="display:flex;gap:4px">
                    <button class="btn btn-ghost btn-xs" style="padding:2px 6px;font-size:10px" onclick="Panels.schema_validation_logs.inspect(${l.id})"><i class="fa-solid fa-magnifying-glass"></i> Detail</button>
                    <button class="btn btn-primary btn-xs" style="padding:2px 6px;font-size:10px" onclick="Panels.schema_validation_logs.replay(${l.id})"><i class="fa-solid fa-rotate-right"></i> Replay</button>
                  </div>
                </td>
              </tr>`;
            }).join('');
          } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark" style="margin-right:6px"></i>Gagal memuat log: ${err.message}</td></tr>`;
          }
        },

        async inspect(id) {
          try {
            const detail = await DataService.fetch(`/api/schema_validation_logs/detail/${id}`);
            if (!detail || !detail.log) {
              Notify.toast('❌', 'Schema validation detail not found', 'err');
              return;
            }
            const log = detail.log;
            const content = `
              <div style="text-align:left;font-size:12px;color:var(--txt)">
                <div style="display:flex;gap:10px;margin-bottom:12px;font-size:11px">
                  <div><b>Log ID:</b> #${log.id}</div>
                  <div><b>Incident:</b> INC-${log.incident_id || 'SYS'}</div>
                  <div><b>Event:</b> ${log.event_id || '—'}</div>
                  <div><b>Checksum:</b> <code style="font-size:10px;color:var(--cyan)">${(detail.checksum || '').substring(0, 16)}...</code></div>
                </div>
                
                <div style="margin-bottom:10px">
                  <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--blue)">Raw Input Prompt:</label>
                  <pre style="background:rgba(0,0,0,0.4);padding:8px;border-radius:4px;border:1px solid var(--bd);max-height:120px;overflow-y:auto;font-size:10.5px;white-space:pre-wrap;word-break:break-all">${log.raw_prompt || '—'}</pre>
                </div>

                <div style="margin-bottom:10px">
                  <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--green2)">LLM Response Output:</label>
                  <pre style="background:rgba(0,0,0,0.4);padding:8px;border-radius:4px;border:1px solid var(--bd);max-height:140px;overflow-y:auto;font-size:10.5px;white-space:pre-wrap;word-break:break-all;color:var(--txt)">${log.llm_response || '—'}</pre>
                </div>

                <div style="margin-bottom:10px">
                  <label style="font-weight:600;display:block;margin-bottom:4px;color:var(--purple2)">Validation Metadata:</label>
                  <div style="background:rgba(255,255,255,0.03);padding:8px;border-radius:4px;border:1px solid var(--bd);font-size:11px">
                    <div><b>Validation Engine:</b> ${detail.validation_engine || 'Pydantic V2'}</div>
                    <div><b>Schema Version:</b> ${detail.schema_version || 'V2.4 Enterprise'}</div>
                    <div><b>Masking & Sanitization:</b> ${detail.masked_sensitive ? '✅ Sensitive data masked' : '—'}</div>
                  </div>
                </div>
              </div>
            `;
            Modal.show('🔍 Schema Log Detail #' + id, content, [{ label: 'Close', cls: 'btn-secondary', fn: 'Modal.close()' }]);
          } catch (err) {
            Notify.toast('❌', 'Gagal memuat detail log: ' + err.message, 'err');
          }
        },

        async replay(id) {
          Notify.toast('🔄', 'Running Schema Validation Replay...', 'info');
          try {
            const res = await DataService.fetch(`/api/schema_validation_logs/replay/${id}`, { method: 'POST' });
            if (res && res.success) {
              const statusBadge = res.is_valid ? '<span class="badge bd-gr">PASS</span>' : '<span class="badge bd-rd">FAILED</span>';
              const content = `
                <div style="text-align:left;font-size:12px;color:var(--txt)">
                  <div style="margin-bottom:12px;font-size:13px">
                    <b>Replay Result:</b> ${statusBadge}
                  </div>
                  <div style="background:rgba(0,0,0,0.4);padding:10px;border-radius:4px;border:1px solid var(--bd);margin-bottom:12px;font-size:11px">
                    <div><b>Audit ID:</b> #${res.audit_id}</div>
                    <div><b>Event ID:</b> ${res.replayed_event_id}</div>
                    <div><b>Schema Version:</b> ${res.schema_version}</div>
                    <div style="margin-top:6px;color:${res.is_valid ? 'var(--green2)' : 'var(--red2)'}">
                      <b>Validation Output:</b> ${res.error_details}
                    </div>
                  </div>
                </div>
              `;
              Modal.show('🔄 Schema Validation Replay #' + id, content, [{ label: 'Close', cls: 'btn-secondary', fn: 'Modal.close()' }]);
              Panels.schema_validation_logs.load();
            } else {
              Notify.toast('❌', 'Replay failed: ' + (res.error || 'Unknown error'), 'err');
            }
          } catch (err) {
            Notify.toast('❌', 'Gagal replay validation: ' + err.message, 'err');
          }
        }
      },


});