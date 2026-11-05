/* ws-service.js
 * WSService - WebSocket connection manager
 * Extracted from index.html panels/main.js - Phase 2 refactor
 */

    const WSService = {
      socket: null,
      reconnect() {
        if (this.socket) {
          try { this.socket.close(); } catch (e) { }
          this.socket = null;
        }
        this.connect();
      },
      connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) return;
        this._setStatus('connecting');
        try {
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          const wsToken = sessionStorage.getItem('noc_jwt_token');
          const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
          this.socket = wsToken ? new WebSocket(wsUrl, ['bearer', wsToken]) : new WebSocket(wsUrl);

          this.socket.onopen = () => {
            this._setStatus('online');
            LogStreamer.add('OK', 'WS', 'WebSocket connected (Native)');
            Bus.emit('ws:connected');
          };

          this.socket.onclose = () => {
            this._setStatus('offline');
            Bus.emit('ws:disconnected');
            // Auto-reconnect after 3 seconds
            setTimeout(() => this.connect(), 3000);
          };

          this.socket.onerror = () => {
            this._setStatus('connecting');
          };

          this.socket.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data);
              if (msg.event === 'system_log') {
                let severity = 'INFO';
                const data = msg.data;
                if (data.type === 'warning' || data.type === 'warn') severity = 'WARN';
                else if (data.type === 'critical' || data.type === 'err' || data.type === 'error') severity = 'ERR';
                else if (data.type === 'ok' || data.type === 'success') severity = 'OK';
                else if (data.type === 'debug') severity = 'DEBUG';

                let src = 'SYS';
                if (data.category) {
                  src = data.category;
                }
                Bus.emit('log:entry', { type: severity, src: src, message: data.message });
              } else if (msg.event === 'incident_event') {
                const data = msg.data;
                let severity = 'INFO';
                if (data.type === 'critical') severity = 'ERR';
                else if (data.type === 'warning') severity = 'WARN';
                else if (data.type === 'RESOLVED') severity = 'OK';
                else if (data.type === 'ESCALATED') severity = 'WARN';

                Bus.emit('log:entry', { type: severity, src: 'NETDATA', message: data.message });

                let toastType = 'info';
                if (data.type === 'critical') toastType = 'crit';
                else if (data.type === 'warning' || data.type === 'ESCALATED') toastType = 'warn';
                else if (data.type === 'RESOLVED') toastType = 'ok';

                Notify.toast(
                  data.type === 'critical' ? '🚨 Critical' : (data.type === 'RESOLVED' ? '✅ Resolved' : '⚠️ Alert'),
                  data.message,
                  toastType
                );
                DataService.loadIncidents();
              } else if (msg.event === 'devices_update') {
                const devices = msg.data;
                DataService._devices = devices;
                DataService._updateDeviceBadges(devices);
                Bus.emit('devices:loaded', devices);
              } else if (msg.event === 'metrics_update') {
                const data = msg.data;
                window.GlobalState.kpi = { ...window.GlobalState.kpi, ...data };
              } else if (msg.event === 'fleet_summary') {
                const data = msg.data;
                // Live update Fleet KPI cards
                if (data.total_devices !== undefined) {
                  setEl('fl-total', data.total_devices);
                  setEl('fl-offline', data.offline_devices || 0);
                }
                // Update incident badge if rag vectors info present
                if (data.rag_vectors !== undefined) {
                  setEl('st-rag', data.rag_vectors > 0 ? data.rag_vectors + ' KB' : '—');
                }
              } else if (msg.event === 'live_telemetry') {
                if (Panels.activity && Panels.activity.handleLiveTelemetry) {
                  Panels.activity.handleLiveTelemetry(msg.data);
                }
                if (Panels.pchealth && Panels.pchealth.handleLiveTelemetry) {
                  Panels.pchealth.handleLiveTelemetry(msg.data);
                }
                if (typeof Bus !== 'undefined' && Bus.emit) {
                  Bus.emit('telemetry:live', msg.data);
                }
              } else if (msg.event === 'jarvis_proactive_alert') {
                const data = msg.data;
                if (data && data.text) {
                  // 1. Play audio output automatically if available
                  if (data.audio_b64 && !window._jarvisMuted) {
                    try {
                      const mime = data.audio_format === 'mp3' ? 'audio/mp3' : 'audio/wav';
                      const audioUrl = `data:${mime};base64,${data.audio_b64}`;
                      const audio = new Audio(audioUrl);
                      audio.play().catch(e => console.warn("[JARVIS Proactive Voice] Autoplay blocked:", e));
                    } catch (aErr) {
                      console.warn("[JARVIS Proactive Voice] Audio decode error:", aErr);
                    }
                  }

                  // 2. Display Toast notification with appropriate severity style
                  let toastType = 'info';
                  if (data.severity === 'CRITICAL') toastType = 'crit';
                  else if (data.severity === 'HIGH' || data.severity === 'WARNING') toastType = 'warn';

                  if (typeof Notify !== 'undefined' && Notify.toast) {
                    Notify.toast("🤖 JARVIS Voice", data.text, toastType);
                  }

                  // 3. Emit log entry for LogStreamer
                  if (typeof Bus !== 'undefined' && Bus.emit) {
                    Bus.emit('log:entry', {
                      type: data.severity === 'CRITICAL' ? 'ERR' : 'WARN',
                      src: 'JARVIS',
                      message: data.text
                    });
                  }
                }
              } else if (msg.event === 'jarvis_navigate_panel') {
                const data = msg.data;
                if (data && data.panel_id && typeof Nav !== 'undefined' && Nav.go) {
                  console.log("[JARVIS Auto-Nav] Navigating UI to panel:", data.panel_id);
                  Nav.go(data.panel_id);
                }
              }
            } catch (jsonErr) {
              console.warn("WS JSON Parse Error:", jsonErr);
            }

          };
        } catch (e) {
          this._setStatus('offline');
        }
      },
      _setStatus(s) {
        const pill = document.getElementById('ws-pill');
        const dot = document.getElementById('ws-dot');
        const txt = document.getElementById('ws-txt');
        const clsMap = { online: 'ws-online', offline: 'ws-offline', connecting: 'ws-connecting' };
        const dotCls = { online: 'dot-green', offline: 'dot-red', connecting: 'dot-orange' };
        const label = { online: 'WS Live', offline: 'WS Offline', connecting: 'Connecting...' };
        if (pill) pill.className = 'ws-indicator ' + clsMap[s];
        if (dot) dot.className = 'dot ' + dotCls[s];
        if (txt) txt.textContent = label[s];
        const connDot = document.getElementById('conn-dot');
        if (connDot) connDot.className = 'dot ' + (s === 'online' ? 'dot-green' : s === 'offline' ? 'dot-red' : 'dot-orange');
      },
      disconnect() {
        if (this.socket) this.socket.close();
      },
      reconnect() {
        if (this.socket) {
          try { this.socket.close(); } catch (e) { }
        }
        this.socket = null;
        setTimeout(() => {
          this.connect();
        }, 2000);
      }
    };

    /* ==================================================
       MOCK DATA SERVICE (abstraction layer)
    ================================================== */
    // MockDataService was removed. Dashboard runs on live production database APIs only.

    /* ==================================================
       DATA SERVICE (API + Fallback to Mock)
    ================================================== */
