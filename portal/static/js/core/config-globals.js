/* config-globals.js
 * CFG, Bus, GlobalState, KPI globals
 * Extracted from index.html panels/main.js - Phase 2 refactor
 */

/* panels/main.js
 * Main panels: WSService, DataService, Nav, Panels.*
 * Extracted from index.html - Phase 2 refactor
 */

'use strict';

    window.ActiveIntervals = {};

    /* ==================================================
       CONFIG
    ================================================== */
    var CFG = {
      API: window.location.origin,
      WS: window.location.origin.replace(/^http/, 'ws') + '/ws/logs',
      REFRESH_MS: 30000,
      LOG_MAX: 500,
      GATEWAY_TO_SITE: {},
      SITES: [],
      AI_MODELS: [
        { key: 'deepseek', name: 'DeepSeek (Opus / Reasoner)', url: 'https://api.deepseek.com/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-brain" style="color:var(--pink);margin-right:6px"></i>' },
        { key: 'gemini', name: 'Google Gemini (2.0 Flash)', url: 'https://generativelanguage.googleapis.com', enabled: true, icon: '<i class="fa-solid fa-wand-magic-sparkles" style="color:var(--blue2);margin-right:6px"></i>' },
        { key: 'groq', name: 'Groq (Llama-3.1 Instant)', url: 'https://api.groq.com/openai/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-bolt" style="color:var(--orange2);margin-right:6px"></i>' },
        { key: 'openrouter', name: 'OpenRouter Free/Paid Gateway', url: 'https://openrouter.ai/api/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-network-wired" style="color:#06b6d4;margin-right:6px"></i>' },
        { key: 'mistral', name: 'Mistral AI (Large / Small)', url: 'https://api.mistral.ai/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-wind" style="color:#a855f7;margin-right:6px"></i>' },
        { key: 'github', name: 'GitHub Models Marketplace', url: 'https://models.inference.ai.azure.com/chat/completions', enabled: true, icon: '<i class="fa-brands fa-github" style="color:var(--txt);margin-right:6px"></i>' },
        { key: 'openai', name: 'OpenAI (GPT-4o Mini)', url: 'https://api.openai.com/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-robot" style="color:#22c55e;margin-right:6px"></i>' },
        { key: 'anthropic', name: 'Anthropic (Claude 3 Haiku)', url: 'https://api.anthropic.com/v1/messages', enabled: true, icon: '<i class="fa-solid fa-feather" style="color:#ef4444;margin-right:6px"></i>' },
        { key: 'kimi', name: 'Kimi AI (K2.6 Moonshot)', url: 'https://api.moonshot.ai/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-moon" style="color:#38bdf8;margin-right:6px"></i>' },
        { key: 'lmstudio', name: 'LM Studio (Local Server)', url: 'http://localhost:1234/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-desktop" style="color:#3b82f6;margin-right:6px"></i>' },
        { key: 'nvidia', name: 'NVIDIA NIM Microservices', url: 'https://integrate.api.nvidia.com/v1/chat/completions', enabled: true, icon: '<i class="fa-solid fa-microchip" style="color:#76b900;margin-right:6px"></i>' },
        { key: 'azure', name: 'Azure OpenAI Services', url: 'https://your-resource.openai.azure.com/...', enabled: true, icon: '<i class="fa-brands fa-microsoft" style="color:#0089d6;margin-right:6px"></i>' }
      ],
      OFFLINE_DEVICES: []
    };

    /* ==================================================
       EVENT BUS
    ================================================== */
    var Bus = {
      _h: {},
      on(ev, fn) { (this._h[ev] = this._h[ev] || []).push(fn); },
      off(ev, fn) { if (this._h[ev]) this._h[ev] = this._h[ev].filter(f => f !== fn); },
      emit(ev, data) { (this._h[ev] || []).forEach(fn => { try { fn(data) } catch (e) { } }); }
    };

    /* ==================================================
       REACTIVE STATE MANAGEMENT
    ================================================== */
    window.gKpi = {};
    window.gIncidents = [];

    window.GlobalState = new Proxy({
      kpi: {},
      incidents: []
    }, {
      set(target, prop, value) {
        target[prop] = value;
        if (prop === 'kpi') {
          window.gKpi = value;
          Bus.emit('reactive:kpi', value);
        }
        if (prop === 'incidents') {
          window.gIncidents = value;
          Bus.emit('reactive:incidents', value);
        }
        return true;
      }
    });

    // Reactive Bindings for KPI
    Bus.on('reactive:kpi', (data) => {
      if (data.resolved_tickets !== undefined) setEl('kpi-ticket', data.resolved_tickets);
      if (data.avg_resolution_time_min !== undefined) {
        setEl('kpi-mttr', Math.round(data.avg_resolution_time_min) + 'm');
        setEl('ov-exec-mttr', Math.round(data.avg_resolution_time_min) + 'm');
      }
      if (data.sla_compliance_rate !== undefined) setEl('ov-exec-sla', data.sla_compliance_rate.toFixed(2) + '%');
      if (data.fcr_rate !== undefined) setEl('kpi-avail', data.fcr_rate.toFixed(1) + '%');
      if (data.active_events !== undefined) {
        const liveIncs = (window.DataService && window.DataService._incidents) ? window.DataService._incidents : [];
        const activeCount = liveIncs.filter(i => {
          const st = String(i.status || '').toUpperCase();
          return st !== 'RESOLVED' && st !== 'CLOSED' && st !== 'SOLVED VERIFIED';
        }).length;
        const countToDisplay = Math.max(data.active_events || 0, activeCount);
        setEl('kpi-incidents', countToDisplay);
        setEl('kpi-incidents-s', countToDisplay > 0 ? '↓ ' + countToDisplay + ' active incidents' : '✓ No active incidents');
        setEl('ov-inc-tag', countToDisplay + ' aktif');
      }
      if (data.confidence_score !== undefined) {
        let confVal = parseFloat(data.confidence_score) || 0;
        if (confVal > 100) confVal = (confVal >= 1000) ? Math.min(100, confVal / 100) : 100;
        setEl('kpi-aiconf', Math.round(confVal) + '%');
        
        // Update Prediction Widget instantly
        const prob = parseFloat(data.confidence_score || 0).toFixed(1);
        setEl('ov-ai-prob', prob > 0 ? prob + '% HIGH' : 'Menghitung...');
        setEl('ov-ai-forecast', prob > 50 ? 'AI telah menemukan pola anomali berulang pada telemetri terbaru. Tindakan eskalasi disarankan sebelum kegagalan meluas.' : 'Model ML sedang mengumpulkan telemetri agent. Kondisi saat ini dalam batas normal.');
      }
      if (data.decision_time_ms !== undefined) {
        const ms = parseFloat(data.decision_time_ms) || 0;
        if (ms > 0) setEl('kpi-ailatency', `(~${ms}ms)`);
        else setEl('kpi-ailatency', '');
      }
      if (data.rca_accuracy !== undefined) {
        setEl('kpi-health', data.rca_accuracy + '%');
      }
    });

    // Reactive Bindings for Incidents
    Bus.on('reactive:incidents', (data) => {
      const active = data.filter(i => {
        const st = String(i.status || '').toUpperCase();
        return st !== 'RESOLVED' && st !== 'CLOSED' && st !== 'SOLVED VERIFIED';
      });
      setEl('bdg-incident', active.length);
      setEl('bdg-overview', active.length);
      setEl('alert-count', active.length);
      setEl('kpi-incidents', active.length);
      setEl('kpi-incidents-s', active.length > 0 ? '↓ ' + active.length + ' active incidents' : '✓ No active incidents');
      setEl('ov-inc-tag', active.length + ' aktif');
      
      const hitlPending = data.filter(i => {
        const st = String(i.status || '').toUpperCase();
        return st === 'HITL_QUEUED' || st === 'PENDING_APPROVAL' || st === 'APPROVAL_REQUIRED';
      }).length;
      setEl('kpi-hitl-pending', hitlPending);
      setEl('kpi-hitl-sub', hitlPending > 0 ? `${hitlPending} Perlu Persetujuan Manual` : '0 Rollbacks · ZERO RISK SAFEGUARD');

      // Update Security Event widget instantly
      const secIncidents = data.filter(i => (i.flag || '').includes('SECURITY') || (i.flag || '').includes('HIGH') || (i.severity || '').toUpperCase() === 'CRITICAL');
      if (secIncidents.length > 0) {
        const latest = secIncidents[0];
        const rawMsg = latest.description || latest.evidence || latest.flag || 'Unknown Threat';
        const msg = rawMsg.length > 90 ? rawMsg.substring(0, 90) + '...' : rawMsg;
        htmlEl('ov-sec-event', `<i class="fa-solid fa-triangle-exclamation" style="font-size:32px; color:var(--red); margin-bottom:10px; display:block;"></i>
          <strong style="color:var(--red)">Deteksi Aktif: ${msg}</strong><br/>
          <span style="color:var(--txt3);font-size:10px">${timeSince(latest.timestamp || latest.created_at)} pada ${latest.device_name || latest.pc_name || 'Network'}</span>`);
      } else {
        htmlEl('ov-sec-event', `<i class="fa-solid fa-shield-halved" style="font-size:32px; color:var(--green); margin-bottom:10px; display:block;"></i>
          Pemindaian IDS/IPS aktif. Tidak ada anomali terdeteksi.`);
      }
    });

    /* ==================================================
       WEBSOCKET SERVICE (Native Browser Implementation)
    ================================================== */
