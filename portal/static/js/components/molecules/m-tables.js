/* m-tables.js
 * Molecule: Tables — sort, filter, export helpers for data tables.
 * Extracted from data.service.js (lines 506-606) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Molecules
 * Depends on: Notify (molecule), XLSX (optional, for Excel export)
 */
(function () {
  'use strict';

  let Tables = {
    _state: {},
    _getData: function(tableId) {
      let tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return [];
      return Array.from(tbody.querySelectorAll('tr:not(.hidden-row)'));
    },
    sort: function(th, tableId, colIdx) {
      let s = this._state[tableId] || { col: -1, dir: 1 };
      let dir = s.col === colIdx ? -s.dir : 1;
      this._state[tableId] = { col: colIdx, dir: dir };
      let tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return;
      let rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b) {
        let av = (a.cells[colIdx] || {}).textContent || '';
        let bv = (b.cells[colIdx] || {}).textContent || '';
        let an = parseFloat(av.replace(/[^0-9.-]/g, '')), bn = parseFloat(bv.replace(/[^0-9.-]/g, ''));
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
      let searchEl = document.getElementById(tableId.replace('tbl-', '') + '-search') || document.getElementById('tri-search');
      let q = (searchEl || { value: '' }).value.toLowerCase().trim();

      let sevSelect = document.getElementById('tri-filter-sev');
      let siteSelect = document.getElementById('tri-filter-site');
      let targetSev = sevSelect ? sevSelect.value : '';
      let targetSite = siteSelect ? siteSelect.value : '';

      let tbody = document.getElementById('tbody-' + tableId.replace('tbl-', ''));
      if (!tbody) return;

      let visible = 0;
      let sevMap = {
        'CRITICAL': 'KRITIS',
        'HIGH': 'TINGGI',
        'MEDIUM': 'SEDANG',
        'LOW': 'RENDAH'
      };
      let mappedSev = sevMap[targetSev] || '';

      tbody.querySelectorAll('tr').forEach(function(tr) {
        let site = tr.getAttribute('data-site') || '';
        let sev = tr.getAttribute('data-sev') || '';

        let matchQuery = !q || tr.textContent.toLowerCase().includes(q);
        let matchSev = !mappedSev || sev === mappedSev;
        let matchSite = !targetSite || site.toLowerCase().includes(targetSite.toLowerCase());

        let show = matchQuery && matchSev && matchSite;
        tr.classList.toggle('hidden-row', !show);
        if (show) visible++;
      });

      let cntEl = document.getElementById(tableId.replace('tbl-', '').split('-')[0] + '-count-txt') || document.getElementById('tri-count-txt');
      if (cntEl) cntEl.textContent = visible + ' insiden';
    },
    exportCSV: function(tableId, filename) {
      let table = document.getElementById(tableId);
      if (!table) return;
      let rows = Array.from(table.querySelectorAll('tr:not(.hidden-row)'));
      let csv = rows.map(function(r) { return Array.from(r.querySelectorAll('th,td')).map(function(c) { return '"' + c.textContent.replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
      this._download(csv, filename + '.csv', 'text/csv');
      Notify.toast('📥 Export', 'CSV berhasil didownload', 'ok', 2500);
    },
    exportJSON: function(tableId, filename) {
      let table = document.getElementById(tableId);
      if (!table) return;
      let headers = Array.from(table.querySelectorAll('thead th')).map(function(h) { return h.textContent.trim(); });
      let rows = Array.from(table.querySelectorAll('tbody tr:not(.hidden-row)')).map(function(r) {
        return Object.fromEntries(Array.from(r.querySelectorAll('td')).map(function(c, i) { return [headers[i] || i, c.textContent.trim()]; }));
      });
      this._download(JSON.stringify(rows, null, 2), filename + '.json', 'application/json');
      Notify.toast('📥 Export', 'JSON berhasil didownload', 'ok', 2500);
    },
    exportExcel: function(tableId, filename) {
      if (typeof XLSX === 'undefined') { Notify.toast('⚠️ Error', 'SheetJS tidak tersedia', 'warn'); return; }
      let table = document.getElementById(tableId);
      if (!table) return;
      let wb = XLSX.utils.book_new();
      let ws = XLSX.utils.table_to_sheet(table);
      XLSX.utils.book_append_sheet(wb, ws, 'Data');
      XLSX.writeFile(wb, filename + '.xlsx');
      Notify.toast('📥 Export', 'Excel berhasil didownload', 'ok', 2500);
    },
    _download: function(content, filename, mime) {
      let a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([content], { type: mime }));
      a.download = filename; a.click(); URL.revokeObjectURL(a.href);
    }
  };

  window.Tables = Tables;
  window.UI = window.UI || {};
  window.UI.Molecules = window.UI.Molecules || {};
  window.UI.Molecules.Tables = Tables;
})();
