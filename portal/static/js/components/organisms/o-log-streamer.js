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
    _logs: [], _paused: false, _filter: '', _srcFilter: '', _searchQ: '',
    _maxLogs: 500,

    setMaxLogs: function(limit) {
      this._maxLogs = parseInt(limit) || 500;
      if (this._logs.length > this._maxLogs) {
        this._logs = this._logs.slice(-this._maxLogs);
      }
      this._rerender();
      Notify.toast('⚙️ Buffer Limit', 'Max log limit set to ' + this._maxLogs + ' lines', 'info', 1500);
    },

    add: function(type, src, msg) {
      let now = new Date();
      let time = now.toTimeString().slice(0, 8);
      let entry = { time: time, type: type, src: src, msg: msg, ts: now.getTime() };
      this._logs.push(entry);
      if (this._logs.length > this._maxLogs) this._logs.shift();
      if (!this._paused) this._renderLine(entry);
      this._updateCounters();
      Bus.emit('log:new', entry);
    },

    _updateCounters: function() {
      let totalTag = document.getElementById('log-count-tag');
      if (totalTag) totalTag.textContent = this._logs.length + ' baris';

      let okCnt = 0, warnCnt = 0, errCnt = 0;
      for (let i = 0; i < this._logs.length; i++) {
        let t = (this._logs[i].type || '').toUpperCase();
        if (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL') errCnt++;
        else if (t === 'WARN' || t === 'WARNING') warnCnt++;
        else if (t === 'OK' || t === 'SUCCESS') okCnt++;
      }
      let el;
      el = document.getElementById('log-cnt-ok'); if (el) el.innerText = okCnt;
      el = document.getElementById('log-cnt-warn'); if (el) el.innerText = warnCnt;
      el = document.getElementById('log-cnt-err'); if (el) el.innerText = errCnt;
    },

    _renderLine: function(entry) {
      if (!this._matchFilters(entry)) return;
      let box = document.getElementById('log-box');
      if (!box) return;
      let t = (entry.type || '').toUpperCase();
      let cls = (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL') ? 'err' : (t === 'WARN' || t === 'WARNING') ? 'warn' : (t === 'INFO') ? 'info' : (t === 'DEBUG') ? 'debug' : 'ok';
      let div = document.createElement('div');
      div.className = 'log-line';
      let q = this._searchQ;
      let msgH = q ? entry.msg.replace(new RegExp(q, 'gi'), function(m) { return '<span class="search-highlight">' + m + '</span>'; }) : entry.msg;
      div.innerHTML = '<span class="log-time">' + entry.time + '</span><span class="log-src">[' + entry.src + ']</span><span class="log-msg ' + cls + '">' + msgH + '</span>';
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
      while (box.children.length > this._maxLogs) {
        box.removeChild(box.firstChild);
      }
    },

    _matchFilters: function(e) {
      if (this._filter) {
        let f = this._filter.toUpperCase();
        let t = (e.type || '').toUpperCase();
        if (f === 'ERR' || f === 'ERROR') {
          if (t !== 'ERR' && t !== 'ERROR' && t !== 'CRITICAL') return false;
        } else if (f === 'WARN' || f === 'WARNING') {
          if (t !== 'WARN' && t !== 'WARNING') return false;
        } else if (t !== f) {
          return false;
        }
      }
      if (this._srcFilter) {
        let sf = this._srcFilter.toUpperCase();
        let es = (e.src || '').toUpperCase();
        let msg = (e.msg || '').toUpperCase();
        if (sf === 'NETDATA') {
          if (!es.includes('NET') && !es.includes('MONITOR') && !es.includes('PING') && !msg.includes('NETDATA')) return false;
        } else if (sf === 'AI') {
          if (!es.includes('AI') && !es.includes('RAG') && !es.includes('MODEL') && !es.includes('RCA')) return false;
        } else if (sf === 'DB') {
          if (!es.includes('DB') && !es.includes('POSTGRES') && !es.includes('REDIS') && !es.includes('SQL')) return false;
        } else if (sf === 'WS') {
          if (!es.includes('WS') && !es.includes('NATS') && !es.includes('SOCKET')) return false;
        } else if (sf === 'SYS') {
          if (!es.includes('SYS') && !es.includes('CONF') && !es.includes('CONFIG') && !es.includes('REMOTE')) return false;
        } else if (!es.includes(sf) && !msg.includes(sf)) {
          return false;
        }
      }
      if (this._searchQ) {
        let msgL = (e.msg || '').toLowerCase();
        let srcL = (e.src || '').toLowerCase();
        if (!msgL.includes(this._searchQ) && !srcL.includes(this._searchQ)) return false;
      }
      return true;
    },

    togglePause: function() {
      this._paused = !this._paused;
      let btn = document.getElementById('log-pause-btn');
      if (btn) btn.textContent = this._paused ? '▶ Resume' : '⏸ Pause';
      if (btn) btn.classList.toggle('btn-warning', !this._paused);
      if (btn) btn.classList.toggle('btn-success', this._paused);
      let box = document.getElementById('log-box');
      if (box) box.classList.toggle('paused', this._paused);
      if (!this._paused) { this._rerender(); Notify.toast('▶ Resumed', 'Log streaming dilanjutkan', 'ok', 1500); }
      else Notify.toast('⏸ Paused', 'Log streaming dijeda', 'warn', 1500);
    },

    _rerender: function() {
      let box = document.getElementById('log-box');
      if (!box) return;
      box.innerHTML = '';
      let filtered = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });
      if (filtered.length === 0) {
        box.innerHTML = '<div style="padding:20px;text-align:center;color:var(--txt3);font-size:12px;font-family:monospace"><i class="fa-solid fa-filter" style="margin-right:6px"></i> Tidak ada log streaming yang cocok dengan filter.</div>';
      } else {
        filtered.slice(-this._maxLogs).forEach(function(e) { LogStreamer._renderLine(e); });
      }
      this._updateCounters();
    },

    setFilter: function(f) { this._filter = f; this._rerender(); },
    setSourceFilter: function(f) { this._srcFilter = f; this._rerender(); },
    search: function(q) { this._searchQ = q.toLowerCase().trim(); this._rerender(); },
    clear: function() { this._logs = []; let box = document.getElementById('log-box'); if (box) box.innerHTML = ''; this._updateCounters(); Notify.toast('🗑️ Cleared', 'Log dibersihkan', 'info', 1500); },

    download: function(format) {
      if (!format) format = 'txt';
      let content = '';
      let mimeType = 'text/plain';
      let dateStr = new Date().toISOString().slice(0, 10);
      let filename = 'noc-logs-' + dateStr + '.' + format;
      let exportLogs = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });

      if (format === 'json') {
        content = JSON.stringify(exportLogs, null, 2);
        mimeType = 'application/json';
      } else if (format === 'csv') {
        content = 'Time,Source,Type,Message\n' + exportLogs.map(function(e) { return '"' + e.time + '","' + e.src + '","' + e.type + '","' + (e.msg || '').replace(/"/g, '""') + '"'; }).join('\n');
        mimeType = 'text/csv';
      } else if (format === 'log' || format === 'txt') {
        content = exportLogs.map(function(e) { return '[' + e.time + '] [' + e.src + '] [' + e.type + '] ' + e.msg; }).join('\n');
        mimeType = 'text/plain';
      }

      let a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: mimeType }));
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      Notify.toast('📥 Download', 'Log file (' + format.toUpperCase() + ') downloaded', 'ok', 2500);
    },

    copy: function() {
      let exportLogs = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });
      let content = exportLogs.map(function(e) { return '[' + e.time + '] [' + e.src + '] [' + e.type + '] ' + e.msg; }).join('\n');
      navigator.clipboard.writeText(content).then(function() { Notify.toast('📋 Copied', exportLogs.length + ' baris log dicopy', 'ok', 2000); });
    },

    loadBulk: function(entries) {
      this._logs = [];
      let box = document.getElementById('log-box');
      if (box) box.innerHTML = '';

      let reversed = entries.slice().reverse();
      for (let i = 0; i < reversed.length; i++) {
        let e = reversed[i];
        let type = e.type || 'INFO';
        let src = e.category || e.src || 'SYS';
        let msg = e.message || '';
        let time = '--:--:--';
        if (e.timestamp && e.timestamp.length >= 19) {
          time = e.timestamp.slice(11, 19);
        } else {
          time = new Date().toTimeString().slice(0, 8);
        }

        let ts = e.timestamp ? new Date(e.timestamp.replace(' ', 'T')).getTime() : Date.now();
        let entry = { time: time, type: type, src: src, msg: msg, ts: ts };
        this._logs.push(entry);
        if (this._logs.length > this._maxLogs) this._logs.shift();
      }

      this._rerender();
    }
  };

  window.LogStreamer = LogStreamer;
  window.UI = window.UI || {};
  window.UI.Organisms = window.UI.Organisms || {};
  window.UI.Organisms.LogStreamer = LogStreamer;
})();
