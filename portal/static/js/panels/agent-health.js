/* panels/agent-health.js
 * Agent Health panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      agent_health: {
        async load() {
          const tbody = document.getElementById('agent-health-tbody');
          if (!tbody) return;
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--txt2)"><div style="display:flex;align-items:center;justify-content:center;gap:8px"><div style="width:14px;height:14px;border:2px solid var(--green);border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite"></div> Memuat AI Agent Health...</div></td></tr>';
          
          try {
            const agents = await DataService.loadAgentHealth();
            if (!agents || agents.length === 0) {
              tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:25px;color:var(--txt2)">Tidak ada AI Agent aktif</td></tr>';
              return;
            }
            
            const agentMap = {};
            agents.forEach(a => agentMap[a.agent.toLowerCase()] = a);
            
            const updateKpi = (idPrefix, agentName) => {
              const a = agentMap[agentName];
              const el = document.getElementById('kpi-agent-'+idPrefix);
              if (a) {
                setEl('kpi-agent-'+idPrefix, a.status);
                setEl('kpi-agent-'+idPrefix+'-rtt', 'Uptime: ' + (a.uptime || 0) + 's | CPU: ' + (typeof a.cpu === 'number' ? a.cpu.toFixed(2) : '0') + '%');
                if (el) el.style.color = a.status === 'ONLINE' ? 'var(--green)' : 'var(--red)';
              } else {
                setEl('kpi-agent-'+idPrefix, 'OFFLINE');
                setEl('kpi-agent-'+idPrefix+'-rtt', 'No heartbeat received');
                if (el) el.style.color = 'var(--red)';
              }
            };
            
            updateKpi('incident', 'incident');
            updateKpi('recovery', 'recovery');
            updateKpi('security', 'security');
            updateKpi('verify', 'verify');
            
            let html = '';
            for (const a of agents) {
              const statusCol = a.status === 'ONLINE' ? '<span style="color:var(--green)"><i class="fa-solid fa-circle-check"></i> ONLINE</span>' : '<span style="color:var(--red)"><i class="fa-solid fa-circle-xmark"></i> OFFLINE</span>';
              html += `<tr>
                <td><strong>ai.${a.agent}</strong></td>
                <td>${statusCol}</td>
                <td>${a.uptime} sec</td>
                <td>${a.queue_depth} jobs</td>
                <td>${a.cpu.toFixed(2)}%</td>
                <td style="color:var(--txt2)">${a.last_seen}</td>
              </tr>`;
            }
            tbody.innerHTML = html;
          } catch(e) {
            console.error("Failed to load AI agents:", e);
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--red)"><i class="fa-solid fa-circle-xmark"></i> Gagal memuat data</td></tr>`;
          }
        }
      },


});
