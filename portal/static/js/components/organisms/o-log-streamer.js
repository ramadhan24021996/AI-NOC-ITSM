/* o-log-streamer.js
 * Organism: LogStreamer — real-time log streaming, filtering, search & export.
 * Extracted from data.service.js (lines 694-880) — Phase 5.3 Atomic Design refactor.
 *
 * Layer: Components > Organisms
 * Depends on: Notify (molecule), Bus (event bus from t-config-globals.js)
 */
(function () {
  'use strict';

  var LogStreamer = {
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
      var now = new Date();
      var time = now.toTimeString().slice(0, 8);
      var entry = { time: time, type: type, src: src, msg: msg, ts: now.getTime() };
      this._logs.push(entry);
      if (this._logs.length > this._maxLogs) this._logs.shift();
      if (!this._paused) this._renderLine(entry);
      this._updateCounters();
      Bus.emit('log:new', entry);
    },

    _updateCounters: function() {
      var totalTag = document.getElementById('log-count-tag');
      if (totalTag) totalTag.textContent = this._logs.length + ' baris';

      var okCnt = 0, warnCnt = 0, errCnt = 0;
      for (var i = 0; i < this._logs.length; i++) {
        var t = (this._logs[i].type || '').toUpperCase();
        if (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL') errCnt++;
        else if (t === 'WARN' || t === 'WARNING') warnCnt++;
        else if (t === 'OK' || t === 'SUCCESS') okCnt++;
      }
      var el;
      el = document.getElementById('log-cnt-ok'); if (el) el.innerText = okCnt;
      el = document.getElementById('log-cnt-warn'); if (el) el.innerText = warnCnt;
      el = document.getElementById('log-cnt-err'); if (el) el.innerText = errCnt;
    },

    _renderLine: function(entry) {
      if (!this._matchFilters(entry)) return;
      var box = document.getElementById('log-box');
      if (!box) return;
      var t = (entry.type || '').toUpperCase();
      var cls = (t === 'ERR' || t === 'ERROR' || t === 'CRITICAL') ? 'err' : (t === 'WARN' || t === 'WARNING') ? 'warn' : (t === 'INFO') ? 'info' : (t === 'DEBUG') ? 'debug' : 'ok';
      var div = document.createElement('div');
      div.className = 'log-line';
      var q = this._searchQ;
      var msgH = q ? entry.msg.replace(new RegExp(q, 'gi'), function(m) { return '<span class="search-highlight">' + m + '</span>'; }) : entry.msg;
      div.innerHTML = '<span class="log-time">' + entry.time + '</span><span class="log-src">[' + entry.src + ']</span><span class="log-msg ' + cls + '">' + msgH + '</span>';
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
      while (box.children.length > this._maxLogs) {
        box.removeChild(box.firstChild);
      }
    },

    _matchFilters: function(e) {
      if (this._filter) {
        var f = this._filter.toUpperCase();
        var t = (e.type || '').toUpperCase();
        if (f === 'ERR' || f === 'ERROR') {
          if (t !== 'ERR' && t !== 'ERROR' && t !== 'CRITICAL') return false;
        } else if (f === 'WARN' || f === 'WARNING') {
          if (t !== 'WARN' && t !== 'WARNING') return false;
        } else if (t !== f) {
          return false;
        }
      }
      if (this._srcFilter) {
        var sf = this._srcFilter.toUpperCase();
        var es = (e.src || '').toUpperCase();
        var msg = (e.msg || '').toUpperCase();
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
        var msgL = (e.msg || '').toLowerCase();
        var srcL = (e.src || '').toLowerCase();
        if (!msgL.includes(this._searchQ) && !srcL.includes(this._searchQ)) return false;
      }
      return true;
    },

    togglePause: function() {
      this._paused = !this._paused;
      var btn = document.getElementById('log-pause-btn');
      if (btn) btn.textContent = this._paused ? '▶ Resume' : '⏸ Pause';
      if (btn) btn.classList.toggle('btn-warning', !this._paused);
      if (btn) btn.classList.toggle('btn-success', this._paused);
      var box = document.getElementById('log-box');
      if (box) box.classList.toggle('paused', this._paused);
      if (!this._paused) { this._rerender(); Notify.toast('▶ Resumed', 'Log streaming dilanjutkan', 'ok', 1500); }
      else Notify.toast('⏸ Paused', 'Log streaming dijeda', 'warn', 1500);
    },

    _rerender: function() {
      var box = document.getElementById('log-box');
      if (!box) return;
      box.innerHTML = '';
      var filtered = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });
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
    clear: function() { this._logs = []; var box = document.getElementById('log-box'); if (box) box.innerHTML = ''; this._updateCounters(); Notify.toast('🗑️ Cleared', 'Log dibersihkan', 'info', 1500); },

    download: function(format) {
      if (!format) format = 'txt';
      var content = '';
      var mimeType = 'text/plain';
      var dateStr = new Date().toISOString().slice(0, 10);
      var filename = 'noc-logs-' + dateStr + '.' + format;
      var exportLogs = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });

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

      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: mimeType }));
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      Notify.toast('📥 Download', 'Log file (' + format.toUpperCase() + ') downloaded', 'ok', 2500);
    },

    copy: function() {
      var exportLogs = this._logs.filter(function(e) { return LogStreamer._matchFilters(e); });
      var content = exportLogs.map(function(e) { return '[' + e.time + '] [' + e.src + '] [' + e.type + '] ' + e.msg; }).join('\n');
      navigator.clipboard.writeText(content).then(function() { Notify.toast('📋 Copied', exportLogs.length + ' baris log dicopy', 'ok', 2000); });
    },

    loadBulk: function(entries) {
      this._logs = [];
      var box = document.getElementById('log-box');
      if (box) box.innerHTML = '';

      var reversed = entries.slice().reverse();
      for (var i = 0; i < reversed.length; i++) {
        var e = reversed[i];
        var type = e.type || 'INFO';
        var src = e.category || e.src || 'SYS';
        var msg = e.message || '';
        var time = '--:--:--';
        if (e.timestamp && e.timestamp.length >= 19) {
          time = e.timestamp.slice(11, 19);
        } else {
          time = new Date().toTimeString().slice(0, 8);
        }

        var ts = e.timestamp ? new Date(e.timestamp.replace(' ', 'T')).getTime() : Date.now();
        var entry = { time: time, type: type, src: src, msg: msg, ts: ts };
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
