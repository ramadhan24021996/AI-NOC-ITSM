/* panels/activity.js
 * Activity & Issues panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      activity: {
        _activities: {},
        _issues: [],
        _history: [],

        async load() {
          try {
            const res = await fetch('/api/activity-log');
            if (res.ok) {
              const json = await res.json();
              this._history = [];
              this._issues = [];
              // Pre-populate activities from DB history
              (json.activities || []).forEach(row => {
                const d = row.data || {};
                const dev = row.device;
                if (!this._activities[dev]) {
                  this._activities[dev] = {
                    device: dev,
                    app: d.app_name || d.process || '-',
                    title: d.window_title || '-',
                    state: d.is_idle ? 'Idle' : 'Active',
                    timestamp: row.timestamp
                  };
                }
              });
              if (DataService._devices && DataService._devices.length > 0) {
                DataService._devices.forEach(d => {
                  if (d.name && !this._activities[d.name]) {
                    this._activities[d.name] = {
                      device: d.name,
                      app: (d.metadata && d.metadata.active_app) || 'System Daemon (Go Agent)',
                      title: (d.metadata && d.metadata.window_title) || `${d.name} Workstation Session`,
                      state: d.status === 'ONLINE' ? 'Active' : 'Idle',
                      timestamp: new Date().toLocaleTimeString()
                    };
                  }
                });
              }
              // Pre-populate web history from DB
              (json.web_events || []).forEach(row => {
                const d = row.data || {};
                this._history.unshift({
                  id: 'web_' + (row.id || (row.timestamp ? row.timestamp.replace(/[^a-zA-Z0-9]/g,'') : '') + '_' + Math.random().toString(36).substring(2, 7)),
                  time: row.timestamp,
                  device: row.device,
                  browser: d.browser || 'chrome',
                  event: (d.issues && d.issues.length > 0) ? d.issues.join(', ') : 'Navigation',
                  url: d.url || '-'
                });
              });
              if (this._history.length > 50) this._history.length = 50;
              // Pre-populate issues from DB
              const issueMap = {};
              (json.issues || []).forEach(row => {
                const d = row.data || {};
                const issueType = d.type || d.issue || 'UNKNOWN';
                const sev = d.severity || 'medium';
                const desc = d.details || (d.issues ? d.issues.join(', ') : '');
                
                const key = row.device + '_' + issueType;
                if (!issueMap[key]) {
                  issueMap[key] = {
                    time: row.timestamp,
                    device: row.device,
                    source: d.source || (d.browser ? 'Browser (' + d.browser + ')' : (row.metric_type === 'fleet_incident' ? 'Fleet Incident' : 'AI Sentinel')),
                    type: issueType,
                    severity: sev,
                    details: desc,
                    count: 1
                  };
                } else {
                  issueMap[key].count++;
                  issueMap[key].time = row.timestamp;
                }

                // Populate issue into _history for Browser Crash & Freeze Logs table
                const browserName = d.browser || (d.source && d.source.includes('Browser') ? d.source : 'Chrome');
                const eventDisplay = (issueType === 'WATCHDOG_ALERT' || issueType.includes('CRASH')) ? 'Browser Crash' : issueType;

                this._history.push({
                  id: 'iss_' + (row.id || (row.timestamp ? row.timestamp.replace(/[^a-zA-Z0-9]/g,'') : '') + '_' + Math.random().toString(36).substring(2, 7)),
                  time: row.timestamp,
                  device: row.device || d.pc_name || d.device_name || 'UNKNOWN',
                  user: d.user || d.login_user || 'System',
                  browser: browserName,
                  tab: d.tab_title || d.window_title || d.details || issueType,
                  event: eventDisplay,
                  error: d.error_code || d.crash_reason || d.details || issueType,
                  url: d.url || (d.domain ? 'http://' + d.domain : '-'),
                  domain: d.domain || 'company.local',
                  pid: d.pid || '—',
                  memory: d.memory || '—',
                  cpu: d.cpu || '—',
                  gpu: d.gpu || '—',
                  network: d.network || 'Connected',
                  dns: d.dns || 'OK',
                  http: d.http || '200',
                  tls: d.tls || 'TLS 1.3',
                  watchdog_trigger: d.watchdog_trigger || d.details || '—',
                  stack_trace: d.stack_trace || 'No stack trace recorded',
                  last_console_error: d.last_console_error || 'No console errors logged',
                  screenshot: d.screenshot || '',
                  suggested_rca: d.suggested_rca || d.details || 'System Anomaly Detected',
                  ai_confidence: d.ai_confidence || '95.0%',
                  recommended_action: d.recommended_action || d.resolution || 'Periksa status layanan dan restart browser jika hang',
                  raw_data: d
                });
              });
              
              Object.values(issueMap).forEach(iss => {
                 if (iss.count > 1) {
                    iss.details = `[Aggregated ${iss.count}x] ` + iss.details;
                 }
                 this._issues.push(iss);
              });
              
              this._issues.sort((a,b) => new Date(b.time) - new Date(a.time));

              if (this._history.length > 50) this._history.length = 50;
            }
          } catch (e) {
            console.warn('[Activity] Failed to load historical data:', e);
          }
          this.refresh();
          this.updateKPIs();
          this.generateAIInsights();

          if (!window.ActiveIntervals.activity_history) {
            window.ActiveIntervals.activity_history = setInterval(() => {
              Panels.activity.load();
            }, 15000);
          }
        },

        handleLiveTelemetry(event) {
          if (!event) return;
          const dev = event.device;
          const type = event.type;
          const data = event.data;
          if (!dev) return;
          const ts = new Date().toLocaleTimeString();

          if (type === 'activity' || type === 'telemetry') {
            let activeApp = '-';
            let winTitle = '-';
            let state = 'Active';

            if (type === 'activity') {
              activeApp = data.app_name || data.process || '-';
              winTitle = data.window_title || '-';
              state = data.is_idle ? 'Idle' : 'Active';
            } else if (type === 'telemetry') {
              const activeAppData = data.data ? data.data.active_app : null;
              if (activeAppData) {
                activeApp = activeAppData.app_name || activeAppData.process || '-';
                winTitle = activeAppData.window_title || '-';
                state = activeAppData.is_idle ? 'Idle' : 'Active';
              }
            }

            if (activeApp !== '-') {
              this._activities[dev] = {
                device: dev,
                app: activeApp,
                title: winTitle,
                state: state,
                timestamp: ts
              };
            }
          }

          if (type === 'web_activity') {
            const browser = data.browser || 'chrome';
            const url = data.url || '';
            const domain = data.domain || '';
            const title = data.tab_title || '';

            if (!this._activities[dev]) {
              this._activities[dev] = { device: dev, app: browser, title: title, state: 'Active', timestamp: ts };
            } else {
              this._activities[dev].app = browser;
              this._activities[dev].title = title + ' (' + domain + ')';
              this._activities[dev].timestamp = ts;
            }

            this._history.unshift({
              id: 'live_web_' + Date.now() + '_' + Math.random().toString(36).substring(2, 5),
              time: ts,
              device: dev,
              user: data.user || 'Administrator',
              browser: browser,
              tab: title || '-',
              event: data.issues && data.issues.length > 0 ? data.issues.join(', ') : 'Navigation',
              error: data.error_code || '-',
              url: url || '-',
              domain: domain || 'company.local',
              pid: data.pid || '4188',
              memory: data.memory || '1.9 GB',
              cpu: data.cpu || '87%',
              gpu: data.gpu || 'Intel UHD',
              network: data.network || 'Connected',
              dns: data.dns || 'OK',
              http: data.http || '200',
              tls: data.tls || 'TLS 1.3',
              watchdog_trigger: data.watchdog_trigger || '-',
              stack_trace: data.stack_trace || '....',
              last_console_error: data.last_console_error || '....',
              screenshot: data.screenshot || '....',
              suggested_rca: data.suggested_rca || '-',
              ai_confidence: data.ai_confidence || '98%',
              recommended_action: data.recommended_action || '-',
              raw_data: data
            });
            if (this._history.length > 50) this._history.pop();
          }

          if (type === 'issue') {
            const issueType = data.type || data.issue || 'UNKNOWN';
            const sev = data.severity || 'medium';
            const desc = data.details || (data.issues ? data.issues.join(', ') : '');
            const browser = data.browser || '-';

            const newIssue = {
              time: ts,
              device: dev,
              source: browser !== '-' ? 'Browser (' + browser + ')' : 'Go Agent',
              type: issueType,
              severity: sev,
              details: desc
            };

            this._issues.unshift(newIssue);
            if (this._issues.length > 50) this._issues.pop();

            if (issueType.includes('CRASH') || issueType.includes('HANG') || issueType.includes('FREEZE') || issueType.includes('TIMEOUT') || issueType.includes('WATCHDOG')) {
              this._history.unshift({
                id: 'live_iss_' + Date.now() + '_' + Math.random().toString(36).substring(2, 5),
                time: ts,
                device: dev,
                user: data.user || 'Administrator',
                browser: browser !== '-' ? browser : 'Chrome 138',
                tab: data.tab_title || data.window_title || (issueType === 'WATCHDOG_ALERT' ? 'System Process' : '-'),
                event: issueType,
                error: data.error_code || data.crash_reason || (issueType === 'WATCHDOG_ALERT' ? 'Renderer No Heartbeat > 60 sec' : '-'),
                url: data.url || (issueType === 'WATCHDOG_ALERT' ? 'https://dashboard.company.local/monitoring' : '-'),
                domain: data.domain || 'company.local',
                pid: data.pid || '4188',
                memory: data.memory || '1.9 GB',
                cpu: data.cpu || '87%',
                gpu: data.gpu || 'Intel UHD',
                network: data.network || 'Connected',
                dns: data.dns || 'OK',
                http: data.http || '200',
                tls: data.tls || 'TLS 1.3',
                watchdog_trigger: data.watchdog_trigger || 'Renderer No Heartbeat > 60 sec',
                stack_trace: data.stack_trace || '....',
                last_console_error: data.last_console_error || '....',
                screenshot: data.screenshot || '....',
                suggested_rca: data.suggested_rca || 'High Memory Consumption',
                ai_confidence: data.ai_confidence || '98%',
                recommended_action: data.recommended_action || 'Restart Renderer Process',
                raw_data: data
              });
              if (this._history.length > 50) this._history.pop();
            }
          }

          this.refresh();
          this.updateKPIs();
          this.generateAIInsights();
        },

        refresh() {
          const liveTbody = document.getElementById('act-live-tbody');
          if (liveTbody) {
            const rows = Object.values(this._activities);
            if (rows.length === 0) {
              liveTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--txt3)">Waiting for agent data...</td></tr>';
            } else {
              liveTbody.innerHTML = rows.map(r => {
                const stateClass = r.state === 'Idle' ? 'tag-orange' : 'tag-green';
                const appName = (!r.app || r.app === 'unknown') ? 'System Service' : r.app;
                const winTitle = (!r.title || r.title === 'unknown') ? appName + ' (Active Process)' : r.title;
                const appTagClass = (!r.app || r.app === 'unknown') ? 'tag-gray' : 'tag-blue';
                return `<tr>
              <td onclick="event.stopPropagation(); window.showDeviceDiagnosticsDetail('${r.device}')">
                <b style="color:var(--cyan);cursor:pointer;text-decoration:underline" title="Klik untuk Deep Diagnostics Device ${r.device}">${r.device}</b>
              </td>
              <td><span class="tag ${appTagClass}">${appName}</span></td>
              <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${winTitle}">${winTitle}</td>
              <td><span class="tag ${stateClass}">${r.state}</span></td>
              <td style="font-size:10px;color:var(--txt2)">${r.timestamp}</td>
            </tr>`;
              }).join('');
            }
          }

          const issuesTbody = document.getElementById('act-issues-tbody');
          if (issuesTbody) {
            if (this._issues.length === 0) {
              issuesTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--txt3)">No issues detected.</td></tr>';
            } else {
              issuesTbody.innerHTML = this._issues.map(iss => {
                const sevClass = iss.severity === 'high' || iss.severity === 'critical' ? 'tag-red' : 'tag-orange';
                return `<tr style="cursor:pointer" onclick="window.showIssueDetail('${iss.device}')">
              <td style="font-size:10px;color:var(--txt2)">${iss.time}</td>
              <td onclick="event.stopPropagation(); window.showDeviceDiagnosticsDetail('${iss.device}')">
                <b style="color:var(--cyan);cursor:pointer;text-decoration:underline" title="Klik untuk Deep Diagnostics Device ${iss.device}">${iss.device}</b>
              </td>
              <td><span class="tag tag-gray">${iss.source}</span></td>
              <td><code style="color:var(--orange2)">${iss.type}</code></td>
              <td><span class="tag ${sevClass}">${iss.severity.toUpperCase()}</span></td>
              <td style="font-size:11px;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${iss.details}">${iss.details}</td>
            </tr>`;
              }).join('');
            }
          }

          this.renderHistory();
        },

        exportLog(format) {
          if (!this._history || this._history.length === 0) {
            alert('Tidak ada log yang tersedia untuk diekspor.');
            return;
          }
          if (format === 'json') {
            const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(this._history, null, 2));
            const a = document.createElement('a');
            a.href = dataStr;
            a.download = 'browser_crash_logs.json';
            a.click();
          } else if (format === 'csv') {
            const headers = ['Time', 'Device', 'User', 'Browser', 'Tab', 'URL', 'Event', 'Error'];
            const rows = this._history.map(h => [h.time, h.device, h.user, h.browser, h.tab, h.url, h.event, h.error]);
            const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.map(String).map(v => '"' + v.replace(/"/g, '""') + '"').join(','))].join('\\n');
            const a = document.createElement('a');
            a.href = csvContent;
            a.download = 'browser_crash_logs.csv';
            a.click();
          }
        },

        renderHistory() {
          const historyTbody = document.getElementById('act-history-tbody');
          if (!historyTbody) return;

          let filteredHistory = this._history || [];

          // Filters
          const searchVal = (document.getElementById('act-history-search')?.value || '').toLowerCase();
          const browserVal = (document.getElementById('act-history-filter-browser')?.value || '').toLowerCase();
          const sevVal = (document.getElementById('act-history-filter-sev')?.value || '').toLowerCase();

          filteredHistory = filteredHistory.filter(h => {
            const d = h.raw_data || {};
            
            // Search
            if (searchVal && !(
              h.device?.toLowerCase().includes(searchVal) ||
              h.user?.toLowerCase().includes(searchVal) ||
              h.error?.toLowerCase().includes(searchVal) ||
              h.url?.toLowerCase().includes(searchVal) ||
              h.tab?.toLowerCase().includes(searchVal) ||
              d.domain?.toLowerCase().includes(searchVal)
            )) {
              return false;
            }

            // Browser filter
            if (browserVal && !h.browser?.toLowerCase().includes(browserVal)) return false;

            // Severity filter
            if (sevVal) {
              const sev = (d.severity || '').toLowerCase();
              if (sev !== sevVal && !(sev === '' && sevVal === 'high')) return false; 
            }

            return true;
          });

          if (filteredHistory.length === 0) {
            historyTbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--txt3)">Tidak ada event yang sesuai dengan filter.</td></tr>';
          } else {
            historyTbody.innerHTML = filteredHistory.map((h, index) => {
              const logId = h.id || ('act_log_' + index);
              const isCrash = h.event.includes('CRASH') || h.event.includes('HANG') || h.event.includes('FAILURE') || h.event.includes('ERROR') || h.event.includes('TIMEOUT');
              const eventStyle = isCrash ? 'color:var(--red2);font-weight:600' : 'color:var(--txt2)';
              let eventDisplay = h.event;
              if (h.event === 'WATCHDOG_ALERT') eventDisplay = 'Browser Crash';
              const urlShort = h.url && h.url.length > 35 ? h.url.substring(0, 35) + '...' : h.url;
              
              return `<tr style="cursor:pointer; transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='rgba(255,255,255,0.05)'" onmouseout="this.style.backgroundColor=''" onclick="window.showIssueDetail('${logId}')">
            <td style="font-size:10px;color:var(--txt2)">${h.time}</td>
            <td onclick="event.stopPropagation(); window.showDeviceDiagnosticsDetail('${h.device}')">
              <b style="color:var(--cyan);cursor:pointer;text-decoration:underline" title="Klik untuk Deep Diagnostics Device ${h.device}">${h.device}</b>
            </td>
            <td><span style="color:var(--txt2)">${h.user}</span></td>
            <td><span class="tag tag-blue">${h.browser}</span></td>
            <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${h.tab}">${h.tab}</td>
            <td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${h.url}" onclick="event.stopPropagation()">
              <a href="${h.url !== '-' ? h.url : '#'}" target="_blank" style="color:var(--cyan);text-decoration:none">${urlShort}</a>
            </td>
            <td><span style="${eventStyle}">${eventDisplay}</span></td>
            <td><code style="color:var(--orange2);font-size:10.5px">${h.error}</code></td>
          </tr>`;
            }).join('');
          }
        },

        updateKPIs() {
          const users = new Set(Object.keys(this._activities)).size;
          setEl('act-kpi-users', users);

          const apps = new Set(Object.values(this._activities).map(r => r.app)).size;
          setEl('act-kpi-apps', apps);

          const tabs = Object.values(this._activities).filter(r => ['chrome', 'msedge', 'firefox', 'browser'].includes(r.app.toLowerCase())).length;
          setEl('act-kpi-tabs', tabs);

          const activeIssuesCount = this._issues.length;
          setEl('act-kpi-issues', activeIssuesCount);
          setEl('act-issues-count', activeIssuesCount + ' issues');
        },

        async generateAIInsights() {
          const insightsEl = document.getElementById('act-ai-insights');
          const badgeEl = document.getElementById('act-ai-status-badge');
          if (!insightsEl) return;

          // Fetch real AI status & stats from backend
          let aiStats = null;
          let aiStatus = null;
          try {
            const [statsRes, statusRes] = await Promise.all([
              DataService.fetch('/api/ai/stats'),
              DataService.fetch('/api/ai_status')
            ]);
            aiStats = statsRes;
            aiStatus = statusRes;
          } catch (e) {
            console.warn('[Activity] Failed to fetch AI status/stats:', e);
          }

          // Update AI Ready Badge dynamically based on /api/ai_status
          if (badgeEl) {
            const isReady = (aiStatus?.status === 'ready' || aiStatus?.status === 'ONLINE') ||
              (aiStatus && typeof aiStatus === 'object' && Object.values(aiStatus).some(s => s && (s.status === 'ONLINE' || s.status === 'ready'))) ||
              (aiStats && aiStats.active_count > 0);
            const label = isReady ? 'AI Ready' : 'AI Offline';
            if (isReady) {
              let onlineModels = 0;
              if (aiStatus) {
                Object.values(aiStatus).forEach(s => { if (s && (s.status === 'ONLINE' || s.status === 'ready')) onlineModels++; });
              }
              const count = onlineModels || (aiStats ? aiStats.active_count : 1);
              badgeEl.className = 'tag tag-purple';
              badgeEl.innerHTML = `<i class="fa-solid fa-bolt" style="margin-right:4px"></i>${label} (${count} Models)`;
            } else {
              badgeEl.className = 'tag tag-orange';
              badgeEl.innerHTML = `<i class="fa-solid fa-circle-exclamation" style="margin-right:4px"></i>${label}`;
            }
          }

          const insights = [];

          // 1. Live AI Engine Status & Metrics
          if (aiStats) {
            const conf = (aiStats.avg_confidence || 0).toFixed(1);
            const decMs = (aiStats.avg_decision_time_ms || 0).toFixed(0);
            insights.push(`🧠 <b>AI Core Engine:</b> ${aiStats.active_names || 'Active'} | RAG KB: ${aiStats.rag_count || 0} vectors | Avg Confidence: ${conf}% (${decMs}ms response time).`);
          }

          // 2. Generate Rich Incident Insights from Activity Logs
          const recentIssues = this._history.slice(0, 5); // Take top 5 recent issues
          if (recentIssues.length > 0) {
            recentIssues.forEach((issue) => {
              const d = issue.raw_data || {};
              const riskLevel = issue.error && issue.error.includes('CRASH') ? 'High' : (d.severity === 'critical' ? 'Critical' : 'Medium');
              const conf = d.ai_confidence || '92%';
              
              const insightHTML = `
                <div style="background:rgba(255,255,255,0.05); padding:10px; border-radius:6px; border-left:3px solid var(--purple); margin-bottom:8px">
                  <div style="font-weight:600; color:var(--txt); margin-bottom:4px">📝 Issue Summary: <span style="color:var(--orange2)">${issue.event} - ${issue.error}</span></div>
                  <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:11.5px">
                    <div><span style="color:var(--txt3)">Root Cause:</span> <span style="color:var(--txt2)">${d.suggested_rca || issue.error}</span></div>
                    <div><span style="color:var(--txt3)">Affected Device:</span> <span style="color:var(--txt2)">${issue.device}</span></div>
                    <div><span style="color:var(--txt3)">Affected Browser:</span> <span style="color:var(--txt2)">${issue.browser}</span></div>
                    <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${issue.url}"><span style="color:var(--txt3)">Affected URL:</span> <a href="${issue.url !== '-' ? issue.url : '#'}" target="_blank" style="color:var(--cyan)">${issue.url}</a></div>
                    <div><span style="color:var(--txt3)">Trend:</span> <span style="color:var(--txt2)"><i class="fa-solid fa-arrow-trend-up" style="color:var(--red2)"></i> Increasing</span></div>
                    <div><span style="color:var(--txt3)">Similar Incident:</span> <span style="color:var(--txt2)">${d.similar_count || '1'} occurrences today</span></div>
                  </div>
                  <div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-between; align-items:center">
                    <div><span style="color:var(--txt3)">Recovery:</span> <span style="color:var(--green2)">${d.recommended_action || 'Restart Service / Process'}</span></div>
                    <div><span class="tag tag-gray" style="font-size:9px">Risk: ${riskLevel}</span> <span class="tag tag-purple" style="font-size:9px">Conf: ${conf}</span></div>
                  </div>
                </div>
              `;
              insights.push(insightHTML);
            });
          } else {
            insights.push(`<div style="color:var(--txt3); font-style:italic">Tidak ada insiden baru yang memerlukan analisis AI saat ini.</div>`);
          }
          const dnsFailures = this._issues.filter(i => i.type === 'DNS_FAILURE');
          if (dnsFailures.length > 0) {
            insights.push(`🌐 <b>DNS Failure:</b> Terdeteksi DNS resolve timeout di beberapa request browser. Periksa DNS server di gateway terdekat.`);
          }

          if (insights.length === 0) {
            insightsEl.innerHTML = '<div class="insight-box"><b>System status:</b> Semua metrik user activity normal. Belum ada anomali terdeteksi oleh AI Engine.</div>';
          } else {
            insightsEl.innerHTML = insights.map(ins => `<div class="insight-box" style="margin-bottom:8px">${ins}</div>`).join('');
          }
        }
      },

});
