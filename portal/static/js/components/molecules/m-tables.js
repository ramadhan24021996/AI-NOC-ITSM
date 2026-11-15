/* m-tables.js
 * Molecule: Tables — sort, filter, export helpers for data tables.
 * Extracted from data.service.js (lines 506-606) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Molecules
 * Depends on: Notify (molecule), XLSX (optional, for Excel export)
 */
(function () {
  'use strict';

  var Tables = {
    _state: {},
    _getData: function(tableId) {
      var tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return [];
      return Array.from(tbody.querySelectorAll('tr:not(.hidden-row)'));
    },
    sort: function(th, tableId, colIdx) {
      var s = this._state[tableId] || { col: -1, dir: 1 };
      var dir = s.col === colIdx ? -s.dir : 1;
      this._state[tableId] = { col: colIdx, dir: dir };
      var tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return;
      var rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b) {
        var av = (a.cells[colIdx] || {}).textContent || '';
        var bv = (b.cells[colIdx] || {}).textContent || '';
        var an = parseFloat(av.replace(/[^0-9.-]/g, '')), bn = parseFloat(bv.replace(/[^0-9.-]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir;
        return av.localeCompare(bv) * dir;
      });
      rows.forEach(function(r) { tbody.appendChild(r); });
      document.querySelectorAll('#' + tableId + ' thead th').forEach(function(h, i) { h.classList.remove('sorted-asc', 'sorted-desc'); if (i === colIdx) h.classList.add(dir === 1 ? 'sorted-asc' : 'sorted-desc'); });
    },
    filter: function(tableId, query) {
      this.applyFilters(tableId);
    },
    applyFilters: function(tableId) {
      var searchEl = document.getElementById(tableId.replace('tbl-', '') + '-search') || document.getElementById('tri-search');
      var q = (searchEl || { value: '' }).value.toLowerCase().trim();

      var sevSelect = document.getElementById('tri-filter-sev');
      var siteSelect = document.getElementById('tri-filter-site');
      var targetSev = sevSelect ? sevSelect.value : '';
      var targetSite = siteSelect ? siteSelect.value : '';

      var tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return;

      var visible = 0;
      var sevMap = {
        'CRITICAL': 'KRITIS',
        'HIGH': 'TINGGI',
        'MEDIUM': 'SEDANG',
        'LOW': 'RENDAH'
      };
      var mappedSev = sevMap[targetSev] || '';

      tbody.querySelectorAll('tr').forEach(function(tr) {
        var site = tr.getAttribute('data-site') || '';
        var sev = tr.getAttribute('data-sev') || '';

        var matchQuery = !q || tr.textContent.toLowerCase().includes(q);
        var matchSev = !mappedSev || sev === mappedSev;
        var matchSite = !targetSite || site.toLowerCase().includes(targetSite.toLowerCase());

        var show = matchQuery && matchSev && matchSite;
        tr.classList.toggle('hidden-row', !show);
        if (show) visible++;
      });

      var cntEl = document.getElementById(tableId.replace('tbl-', '').split('-')[0] + '-count-txt') || document.getElementById('tri-count-txt');
      if (cntEl) cntEl.textContent = visible + ' insiden';
    },
    exportCSV: function(tableId, filename) {
      var table = document.getElementById(tableId);
      if (!table) return;
      var rows = Array.from(table.querySelectorAll('tr:not(.hidden-row)'));
      var csv = rows.map(function(r) { return Array.from(r.querySelectorAll('th,td')).map(function(c) { return '"' + c.textContent.replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
      this._download(csv, filename + '.csv', 'text/csv');
      Notify.toast('📥 Export', 'CSV berhasil didownload', 'ok', 2500);
    },
    exportJSON: function(tableId, filename) {
      var table = document.getElementById(tableId);
      if (!table) return;
      var headers = Array.from(table.querySelectorAll('thead th')).map(function(h) { return h.textContent.trim(); });
      var rows = Array.from(table.querySelectorAll('tbody tr:not(.hidden-row)')).map(function(r) {
        return Object.fromEntries(Array.from(r.querySelectorAll('td')).map(function(c, i) { return [headers[i] || i, c.textContent.trim()]; }));
      });
      this._download(JSON.stringify(rows, null, 2), filename + '.json', 'application/json');
      Notify.toast('📥 Export', 'JSON berhasil didownload', 'ok', 2500);
    },
    exportExcel: function(tableId, filename) {
      if (typeof XLSX === 'undefined') { Notify.toast('⚠️ Error', 'SheetJS tidak tersedia', 'warn'); return; }
      var table = document.getElementById(tableId);
      if (!table) return;
      var wb = XLSX.utils.book_new();
      var ws = XLSX.utils.table_to_sheet(table);
      XLSX.utils.book_append_sheet(wb, ws, 'Data');
      XLSX.writeFile(wb, filename + '.xlsx');
      Notify.toast('📥 Export', 'Excel berhasil didownload', 'ok', 2500);
    },
    _download: function(content, filename, mime) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: mime }));
      a.download = filename; a.click(); URL.revokeObjectURL(a.href);
    }
  };

  window.Tables = Tables;
  window.UI = window.UI || {};
  window.UI.Molecules = window.UI.Molecules || {};
  window.UI.Molecules.Tables = Tables;
})();
