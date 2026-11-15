/* m-charts.js
 * Molecule: Charts — Chart.js wrapper with theme-aware color resolution.
 * Extracted from data.service.js (lines 608-692) — Phase 5.2 Atomic Design refactor.
 *
 * Layer: Components > Molecules
 * Depends on: Chart.js (global Chart object)
 */
(function () {
  'use strict';

  let Charts = {
    _charts: {},
    defaults: function() {
      Chart.defaults.color = '#8b9ab5';
      Chart.defaults.font.family = "'Inter', sans-serif";
      Chart.defaults.font.size = 11;
      Chart.defaults.plugins.legend.labels.boxWidth = 10;
      Chart.defaults.plugins.legend.labels.padding = 12;
    },
    _resolveDatasets: function(datasets) {
      let resolveColor = function(c) {
        if (typeof c === 'string' && c.startsWith('var(')) {
          let varName = c.substring(4, c.length - 1);
          return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || c;
        }
        return c;
      };
      return datasets.map(function(ds) {
        let copy = Object.assign({}, ds);
        if (copy.backgroundColor) {
          copy.backgroundColor = Array.isArray(copy.backgroundColor)
            ? copy.backgroundColor.map(resolveColor)
            : resolveColor(copy.backgroundColor);
        }
        if (copy.borderColor) {
          copy.borderColor = Array.isArray(copy.borderColor)
            ? copy.borderColor.map(resolveColor)
            : resolveColor(copy.borderColor);
        }
        if (!copy.hoverBackgroundColor && copy.backgroundColor) {
          copy.hoverBackgroundColor = copy.backgroundColor;
        }
        if (!copy.hoverBorderColor && copy.borderColor) {
          copy.hoverBorderColor = copy.borderColor;
        }
        return copy;
      });
    },
    create: function(id, type, labels, datasets, opts) {
      if (!opts) opts = {};
      if (typeof Chart === 'undefined') {
        console.warn('[Charts] Chart.js library not loaded yet');
        return null;
      }
      if (this._charts[id]) this._charts[id].destroy();
      let ctx = document.getElementById(id);
      if (!ctx) return null;
      let resolved = this._resolveDatasets(datasets);
      let chart = new Chart(ctx, {
        type: type, data: { labels: labels, datasets: resolved },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 600 },
          plugins: {
            legend: { display: !!opts.legend, position: 'bottom' },
            tooltip: { callbacks: opts.tooltipCallbacks || {} }
          },
          scales: type === 'bar' || type === 'line' ? {
            x: { grid: { color: 'rgba(255,255,255,.04)' }, ticks: { color: '#4d5e7a' } },
            y: { grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#4d5e7a' }, ...(opts.yOpts || {}) }
          } : {},
          ...opts
        }
      });
      this._charts[id] = chart;
      return chart;
    },
    update: function(id, labels, datasets) {
      let c = this._charts[id];
      if (!c) return;
      c.data.labels = labels;
      c.data.datasets = this._resolveDatasets(datasets);
      c.update('none');
    },
    addPoint: function(id, label, values) {
      let c = this._charts[id];
      if (!c) return;
      c.data.labels.push(label);
      values.forEach(function(v, i) { if (c.data.datasets[i]) c.data.datasets[i].data.push(v); });
      if (c.data.labels.length > 30) { c.data.labels.shift(); c.data.datasets.forEach(function(ds) { ds.data.shift(); }); }
      c.update('none');
    },
    resetZoom: function(id) { let c = this._charts[id]; if (c) c.resetZoom && c.resetZoom(); }
  };

  window.Charts = Charts;
  window.UI = window.UI || {};
  window.UI.Molecules = window.UI.Molecules || {};
  window.UI.Molecules.Charts = Charts;
})();
