/* o-log-streamer.js
 * Organism: LogStreamer — real-time log streaming, filtering, search & export.
 * Extracted from data.service.js (lines 694-880) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: Notify (molecule), Bus (event bus from t-config-globals.js)
 */
(function () {
  'use strict';

  const LogStreamer = {
    _logs: [],
    _seenKeys: new Set(),
    _paused: false,
    _pausedNewCount: 0,
    _filter: '',
    _srcFilter: '',
    _searchQ: '',
    _maxLogs: 500,

    _esc: function (str) {
      if (typeof _esc === 'function') return _esc(str);
      return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    },

    _escapeRegex: function (str) {
      return String(str == null ? '' : str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    },

    _highlightSafe: function (text, query) {
      let raw = String(text == null ? '' : text);
      if (!query) return this._esc(raw);
      let safeRxStr = this._escapeRegex(query);
      if (!safeRxStr) return this._esc(raw);
      try {
        let rx = new RegExp('(' + safeRxStr + ')', 'gi');
        let parts = raw.split(rx);
        let qLower = query.toLowerCase();
        let out = '';
        for (let i = 0; i < parts.length; i++) {
          let part = parts[i];
          if (!part) continue;
          if (part.toLowerCase() === qLower) {
            out += '<span class="search-highlight">' + this._esc(part) + '</span>';
          } else {
            out += this._esc(part);
          }
        }
        return out;
      } catch (e) {
        return this._esc(raw);
      }
    },

    _normalizeType: function (type) {
      let t = String(type || 'INFO').toUpperCase().trim();
      if (t === 'ERROR' || t === 'CRITICAL' || t === 'FATAL' || t === 'ERR') return 'ERR';
      if (t === 'WARNING' || t === 'WARN') return 'WARN';
      if (t === 'SUCCESS' || t === 'OK' || t === 'HEALTHY') return 'OK';
      if (t === 'DEBUG' || t === 'TRACE') return 'DEBUG';
      return 'INFO';
    },

    _makeKey: function (entry) {
      return (entry.fullTs || entry.time || '') + '|' + (entry.src || '') + '|' + (entry.msg || '');
    },

    setMaxLogs: function (limit) {
      let prevMax = this._maxLogs;
      this._maxLogs = parseInt(limit, 10) || 500;
      if (this._logs.length > this._maxLogs) {
        this._logs = this._logs.slice(-this._maxLogs);
        this._rebuildSeenKeys();
      }
      this._rerender();
      if (typeof Notify !== 'undefined' && Notify.toast) {
        Notify.toast('⚙️ Buffer Limit', 'Max log limit set to ' + this._maxLogs + ' lines', 'info', 1500);
      }
      if (this._maxLogs > prevMax && window.Panels && window.Panels.logs && typeof window.Panels.logs.load === 'function') {
        window.Panels.logs.load(true);
      }
    },

    _rebuildSeenKeys: function () {
      this._seenKeys.clear();
      for (let i = 0; i < this._logs.length; i++) {
        this._seenKeys.add(this._makeKey(this._logs[i]));
      }
    },

    add: function (type, src, msg, customTimestamp) {
      let now = customTimestamp ? new Date(String(customTimestamp).replace(' ', 'T')) : new Date();
      if (isNaN(now.getTime())) now = new Date();
      let pad = function (n) { return n < 10 ? '0' + n : '' + n; };
      let time = pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
      let fullTs = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) + ' ' + time;
      let normType = this._normalizeType(type);
      let cleanSrc = String(src || 'SYS').toUpperCase().trim();
      let cleanMsg = String(msg == null ? '' : msg);

      let entry = {
        time: time,
        fullTs: fullTs,
        type: normType,
        src: cleanSrc,
        msg: cleanMsg,
        ts: now.getTime()
      };

      let key = this._makeKey(entry);
      if (this._seenKeys.has(key)) return;
      this._seenKeys.add(key);

      this._logs.push(entry);
      if (this._logs.length > this._maxLogs) {
        let removed = this._logs.shift();
        if (removed) this._seenKeys.delete(this._makeKey(removed));
      }

      if (!this._paused) {
        this._renderLine(entry, true);
      } else {
        this._pausedNewCount++;
        this._updatePauseButton();
      }
      this._updateCounters();
      if (typeof Bus !== 'undefined' && Bus.emit) {
        Bus.emit('log:new', entry);
      }
    },

    _updatePauseButton: function () {
      let btn = document.getElementById('log-pause-btn');
      if (!btn) return;
      if (this._paused) {
        btn.textContent = this._pausedNewCount > 0
          ? '▶ Resume (+' + this._pausedNewCount + ')'
          : '▶ Resume';
      } else {
        btn.textContent = '⏸ Pause';
      }
      btn.classList.toggle('btn-warning', !this._paused);
      btn.classList.toggle('btn-success', this._paused);
    },

    _updateCounters: function () {
      let hasActiveFilter = Boolean(this._filter || this._srcFilter || this._searchQ);
      let targetLogs = hasActiveFilter
        ? this._logs.filter(function (e) { return LogStreamer._matchFilters(e); })
        : this._logs;

      let totalTag = document.getElementById('log-count-tag');
      if (totalTag) {
        totalTag.textContent = hasActiveFilter
          ? (targetLogs.length + ' / ' + this._logs.length + ' baris')
          : (this._logs.length + ' baris');
      }

      let okCnt = 0, infoCnt = 0, warnCnt = 0, errCnt = 0;
      for (let i = 0; i < targetLogs.length; i++) {
        let t = (targetLogs[i].type || '').toUpperCase();
        if (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL') errCnt++;
        else if (t === 'WARN' || t === 'WARNING') warnCnt++;
        else if (t === 'OK' || t === 'SUCCESS') okCnt++;
        else infoCnt++;
      }
      let el;
      el = document.getElementById('log-cnt-ok'); if (el) el.textContent = okCnt;
      el = document.getElementById('log-cnt-info'); if (el) el.textContent = infoCnt;
      el = document.getElementById('log-cnt-warn'); if (el) el.textContent = warnCnt;
      el = document.getElementById('log-cnt-err'); if (el) el.textContent = errCnt;
    },

    _renderLine: function (entry, autoScroll) {
      if (!this._matchFilters(entry)) return;
      let box = document.getElementById('log-box');
      if (!box) return;

      // Remove empty filter placeholder if present
      let emptyNotice = box.querySelector('.log-empty-notice');
      if (emptyNotice) emptyNotice.remove();

      let wasNearBottom = (box.scrollHeight - box.scrollTop - box.clientHeight) <= 75;

      let t = (entry.type || '').toUpperCase();
      let cls = (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL')
        ? 'err'
        : (t === 'WARN' || t === 'WARNING')
          ? 'warn'
          : (t === 'INFO')
            ? 'info'
            : (t === 'DEBUG')
              ? 'debug'
              : 'ok';

      let div = document.createElement('div');
      div.className = 'log-line';

      let q = this._searchQ;
      let timeHtml = this._esc(entry.time || '--:--:--');
      let srcHtml = this._highlightSafe(entry.src || 'SYS', q);
      let msgHtml = this._highlightSafe(entry.msg || '', q);

      div.innerHTML =
        '<span class="log-time" title="' + this._esc(entry.fullTs || entry.time) + '">' + timeHtml + '</span>' +
        '<span class="log-src">[' + srcHtml + ']</span>' +
        '<span class="log-msg ' + cls + '">[' + this._esc(t) + '] ' + msgHtml + '</span>';

      box.appendChild(div);
      while (box.children.length > this._maxLogs) {
        box.removeChild(box.firstChild);
      }

      if (autoScroll && wasNearBottom) {
        box.scrollTop = box.scrollHeight;
      }
    },

    _matchFilters: function (e) {
      if (this._filter) {
        let f = this._filter.toUpperCase();
        let t = (e.type || '').toUpperCase();
        if (f === 'ERR' || f === 'ERROR') {
          if (t !== 'ERR' && t !== 'ERROR' && t !== 'CRITICAL') return false;
        } else if (f === 'WARN' || f === 'WARNING') {
          if (t !== 'WARN' && t !== 'WARNING') return false;
        } else if (f === 'OK' || f === 'SUCCESS') {
          if (t !== 'OK' && t !== 'SUCCESS') return false;
        } else if (t !== f) {
          return false;
        }
      }
      if (this._srcFilter) {
        let sf = this._srcFilter.toUpperCase();
        let es = (e.src || '').toUpperCase();
        let msg = (e.msg || '').toUpperCase();
        if (sf === 'ORCH') {
          if (!es.includes('ORCH') && !es.includes('INCIDENT') && !es.includes('SOP') && !es.includes('PLAYBOOK') && !es.includes('REMEDI') && !msg.includes('PLAYBOOK') && !msg.includes('REMEDI') && !msg.includes('SOP_') && !msg.includes('DIRECT_APPROVE') && !msg.includes('DIRECT_REJECT')) return false;
        } else if (sf === 'AUDIT') {
          if (!es.includes('AUDIT') && !es.includes('RBAC') && !es.includes('GOVERNANCE') && !es.includes('SECURITY') && !es.includes('CHAOS') && !msg.includes('AUDIT')) return false;
        } else if (sf === 'INGEST') {
          if (!es.includes('INGEST') && !es.includes('TELEMETRY') && !es.includes('AGENT') && !es.includes('FLEET') && !es.includes('OTA') && !es.includes('PRINTER') && !msg.includes('HEARTBEAT') && !msg.includes('TELEMETRY')) return false;
        } else if (sf === 'AI') {
          if (!es.includes('AI') && !es.includes('RAG') && !es.includes('MODEL') && !es.includes('RCA') && !es.includes('DAG') && !es.includes('TRAINING') && !es.includes('JARVIS') && !msg.includes('INFERENCE')) return false;
        } else if (sf === 'DB') {
          if (!es.includes('DB') && !es.includes('POSTGRES') && !es.includes('REDIS') && !es.includes('SQL') && !es.includes('STORAGE') && !msg.includes('POSTGRES') && !msg.includes('REDIS') && !msg.includes('DB_')) return false;
        } else if (sf === 'WS') {
          if (!es.includes('WS') && !es.includes('NATS') && !es.includes('SOCKET') && !msg.includes('WEBSOCKET') && !msg.includes('NATS')) return false;
        } else if (sf === 'NETDATA') {
          if (!es.includes('NET') && !es.includes('MONITOR') && !es.includes('PING') && !es.includes('SNMP') && !msg.includes('NETDATA') && !msg.includes('PING')) return false;
        } else if (sf === 'SYS') {
          if (!es.includes('SYS') && !es.includes('BOOT') && !es.includes('CONF') && !es.includes('CONFIG') && !es.includes('REMOTE') && !es.includes('API')) return false;
        } else if (!es.includes(sf) && !msg.includes(sf)) {
          return false;
        }
      }
      if (this._searchQ) {
        let msgL = (e.msg || '').toLowerCase();
        let srcL = (e.src || '').toLowerCase();
        let typeL = (e.type || '').toLowerCase();
        let timeL = (e.fullTs || e.time || '').toLowerCase();
        if (!msgL.includes(this._searchQ) && !srcL.includes(this._searchQ) && !typeL.includes(this._searchQ) && !timeL.includes(this._searchQ)) {
          return false;
        }
      }
      return true;
    },

    togglePause: function () {
      this._paused = !this._paused;
      if (!this._paused) {
        this._pausedNewCount = 0;
      }
      this._updatePauseButton();
      let box = document.getElementById('log-box');
      if (box) box.classList.toggle('paused', this._paused);
      if (!this._paused) {
        this._rerender(true);
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('▶ Resumed', 'Log streaming dilanjutkan', 'ok', 1500);
        }
      } else {
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('⏸ Paused', 'Log streaming dijeda — log baru tetap disimpan di buffer', 'warn', 1500);
        }
      }
    },

    _rerender: function (forceScrollBottom) {
      let box = document.getElementById('log-box');
      if (!box) return;
      let prevScrollTop = box.scrollTop;
      let wasNearBottom = forceScrollBottom || (box.scrollHeight - box.scrollTop - box.clientHeight) <= 75;

      box.innerHTML = '';
      let filtered = this._logs.filter(function (e) { return LogStreamer._matchFilters(e); });
      if (filtered.length === 0) {
        box.innerHTML = '<div class="log-empty-notice" style="padding:24px;text-align:center;color:var(--txt3);font-size:12px;font-family:monospace"><i class="fa-solid fa-filter" style="margin-right:6px"></i> Tidak ada log streaming yang cocok dengan filter saat ini.</div>';
      } else {
        let slice = filtered.slice(-this._maxLogs);
        for (let i = 0; i < slice.length; i++) {
          this._renderLine(slice[i], false);
        }
        if (wasNearBottom && !this._paused) {
          box.scrollTop = box.scrollHeight;
        } else {
          box.scrollTop = prevScrollTop;
        }
      }
      this._updateCounters();
    },

    setFilter: function (f) { this._filter = f; this._rerender(false); },
    setSourceFilter: function (f) { this._srcFilter = f; this._rerender(false); },
    search: function (q) { this._searchQ = String(q || '').toLowerCase().trim(); this._rerender(false); },

    clear: function () {
      this._logs = [];
      this._seenKeys.clear();
      this._pausedNewCount = 0;
      this._updatePauseButton();
      let box = document.getElementById('log-box');
      if (box) {
        box.innerHTML = '<div class="log-empty-notice" style="padding:24px;text-align:center;color:var(--txt3);font-size:12px;font-family:monospace"><i class="fa-solid fa-terminal" style="margin-right:6px"></i> Buffer log dibersihkan. Menunggu stream real-time baru...</div>';
      }
      this._updateCounters();
      if (typeof Notify !== 'undefined' && Notify.toast) {
        Notify.toast('🗑️ Cleared', 'Log buffer dibersihkan', 'info', 1500);
      }
    },

    download: function (format) {
      if (!format) format = 'txt';
      let content = '';
      let mimeType = 'text/plain;charset=utf-8';
      let dateStr = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      let filename = 'noc-live-logs-' + dateStr + '.' + format;
      let exportLogs = this._logs.filter(function (e) { return LogStreamer._matchFilters(e); });

      if (exportLogs.length === 0) {
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('⚠️ Kosong', 'Tidak ada baris log untuk di-download pada filter ini', 'warn', 2000);
        }
        return;
      }

      if (format === 'json') {
        content = JSON.stringify(exportLogs.map(function (e) {
          return {
            timestamp: e.fullTs || e.time,
            source: e.src,
            level: e.type,
            message: e.msg
          };
        }), null, 2);
        mimeType = 'application/json;charset=utf-8';
      } else if (format === 'csv') {
        content = 'Timestamp,Source,Level,Message\n' + exportLogs.map(function (e) {
          return '"' + (e.fullTs || e.time || '').replace(/"/g, '""') + '","' +
                 (e.src || '').replace(/"/g, '""') + '","' +
                 (e.type || '').replace(/"/g, '""') + '","' +
                 (e.msg || '').replace(/"/g, '""') + '"';
        }).join('\n');
        mimeType = 'text/csv;charset=utf-8';
      } else {
        content = exportLogs.map(function (e) {
          return '[' + (e.fullTs || e.time) + '] [' + e.src + '] [' + e.type + '] ' + e.msg;
        }).join('\n');
      }

      let a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: mimeType }));
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
      if (typeof Notify !== 'undefined' && Notify.toast) {
        Notify.toast('📥 Download', exportLogs.length + ' baris log (' + format.toUpperCase() + ') berhasil diunduh', 'ok', 2500);
      }
    },

    copy: function () {
      let exportLogs = this._logs.filter(function (e) { return LogStreamer._matchFilters(e); });
      if (exportLogs.length === 0) {
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('⚠️ Kosong', 'Tidak ada log untuk disalin', 'warn', 1500);
        }
        return;
      }
      let content = exportLogs.map(function (e) {
        return '[' + (e.fullTs || e.time) + '] [' + e.src + '] [' + e.type + '] ' + e.msg;
      }).join('\n');

      let onCopied = function () {
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('📋 Copied', exportLogs.length + ' baris log berhasil disalin ke clipboard', 'ok', 2000);
        }
      };

      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(content).then(onCopied).catch(function () {
          LogStreamer._fallbackCopyText(content, onCopied);
        });
      } else {
        this._fallbackCopyText(content, onCopied);
      }
    },

    _fallbackCopyText: function (text, onSuccess) {
      try {
        let ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.top = '-9999px';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        if (typeof onSuccess === 'function') onSuccess();
      } catch (e) {
        if (typeof Notify !== 'undefined' && Notify.toast) {
          Notify.toast('❌ Copy Gagal', 'Gagal menyalin ke clipboard', 'err', 2000);
        }
      }
    },

    loadBulk: function (entries, replace) {
      if (!Array.isArray(entries)) return;

      if (replace) {
        this._logs = [];
        this._seenKeys.clear();
      }

      let addedCount = 0;
      let reversed = entries.slice().reverse();
      for (let i = 0; i < reversed.length; i++) {
        let e = reversed[i];
        if (!e) continue;
        let type = this._normalizeType(e.type || 'INFO');
        let src = String(e.category || e.src || 'SYS').toUpperCase().trim();
        let msg = String(e.message != null ? e.message : (e.msg || ''));
        let rawTs = String(e.timestamp || e.fullTs || '');
        let time = '--:--:--';
        let fullTs = rawTs;
        let ts = Date.now();

        if (rawTs.length >= 19) {
          time = rawTs.slice(11, 19);
          let parsed = new Date(rawTs.replace(' ', 'T')).getTime();
          if (!isNaN(parsed)) ts = parsed;
        } else if (rawTs.length === 8 && /^\d{2}:\d{2}:\d{2}$/.test(rawTs)) {
          time = rawTs;
        } else {
          let now = new Date();
          time = now.toTimeString().slice(0, 8);
          fullTs = now.toISOString().slice(0, 10) + ' ' + time;
        }

        let entry = { time: time, fullTs: fullTs, type: type, src: src, msg: msg, ts: ts };
        let key = this._makeKey(entry);
        if (!this._seenKeys.has(key)) {
          this._seenKeys.add(key);
          this._logs.push(entry);
          addedCount++;
        }
      }

      if (addedCount > 0 || replace) {
        this._logs.sort(function (a, b) { return (a.ts || 0) - (b.ts || 0); });
        if (this._logs.length > this._maxLogs) {
          this._logs = this._logs.slice(-this._maxLogs);
          this._rebuildSeenKeys();
        }
        if (!this._paused) {
          this._rerender(false);
        } else {
          this._pausedNewCount += addedCount;
          this._updatePauseButton();
          this._updateCounters();
        }
      } else {
        this._updateCounters();
      }
    }
  };

  window.LogStreamer = LogStreamer;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.LogStreamer = LogStreamer;
})();
