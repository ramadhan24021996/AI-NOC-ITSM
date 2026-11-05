/* panels/storage.js
 * Storage stats panel
 * Part of window.Panels - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      storage: {
        _interval: null,
        _loading: false,

        async load() {
          if (this._loading) return; // prevent duplicate requests
          this._loading = true;
          try {
            const [q, s] = await Promise.all([DataService.loadQueues(), DataService.loadStorageStats()]);

            // ── Redis Queue Metrics ──────────────────────────────────────────
            const mq = (q && q.metrics_queue_size) || 0;
            const lq = (q && q.logs_queue_size) || 0;
            const eq = (q && q.events_queue_size) || 0;
            setEl('st-mq', mq + ' msgs');
            setEl('st-lq', lq + ' msgs');
            setEl('st-eq', eq + ' msgs');
            const totalQ = mq + lq + eq;
            setEl('st-total-queue', totalQ + ' Items ' + (totalQ === 0 ? '(Clean)' : '(Processing)'));
            setEl('st-queue-hdr-tag', totalQ + ' msgs queued');
            const mqBar = document.getElementById('st-mq-bar');
            const lqBar = document.getElementById('st-lq-bar');
            const eqBar = document.getElementById('st-eq-bar');
            if (mqBar) { mqBar.style.transition = 'width .6s ease'; mqBar.style.width = Math.min(100, mq / 200 * 100) + '%'; }
            if (lqBar) { lqBar.style.transition = 'width .6s ease'; lqBar.style.width = Math.min(100, lq / 100 * 100) + '%'; }
            if (eqBar) { eqBar.style.transition = 'width .6s ease'; eqBar.style.width = Math.min(100, eq / 100 * 100) + '%'; }
            const ll = (q && q.load_shedding_level) || 0;
            const llEl = document.getElementById('st-load-lv');
            if (llEl) { llEl.textContent = 'L' + ll + ' ' + (ll === 0 ? 'Normal' : ll === 1 ? 'Degraded' : ll === 2 ? 'Critical' : 'Shedding'); llEl.className = 'tag ' + (ll === 0 ? 'tag-green' : ll === 1 ? 'tag-orange' : 'tag-red'); }
            setEl('st-throughput', (q && q.processed_throughput_5s) || 0);
            setEl('st-latency', ((q && q.avg_processing_latency_ms) || 0).toFixed(1) + 'ms');

            // ── Disk Usage ───────────────────────────────────────────────────
            if (s) {
              const fmtSize = (bytes) => {
                if (!bytes || bytes <= 0) return '0 B';
                const units = ['B', 'KB', 'MB', 'GB', 'TB'];
                let i = 0, size = bytes;
                while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
                return size.toFixed(1) + ' ' + units[i];
              };

              setEl('st-db', fmtSize(s.db_size));
              setEl('st-redis', fmtSize(s.redis_memory));
              setEl('st-rag', fmtSize(s.rag_vectors_size));

              const pgSize = s.db_size || 0;
              const aiSize = (s.ai_files ? s.ai_files.reduce((sum, f) => sum + (f.size || 0), 0) : 0) + (s.rag_vectors_size || 0);
              const dumpSize = s.redis_dump_size || 0;
              const maxScale = Math.max(pgSize, aiSize, dumpSize, 1024 * 1024);
              const pgPct = Math.min(100, (pgSize / maxScale) * 100).toFixed(1);
              const aiPct = Math.min(100, (aiSize / maxScale) * 100).toFixed(1);
              const dumpPct = Math.min(100, (dumpSize / maxScale) * 100).toFixed(1);

              const hd = s.host_disk || {};
              const hostTotal = hd.total_bytes || 0;
              const hostUsed = hd.used_bytes || 0;
              const hostPct = hd.used_pct || (hostTotal > 0 ? (hostUsed / hostTotal * 100).toFixed(1) : 0);

              const drives = [
                { n: 'Host Partition (/app)', txt: `${fmtSize(hostUsed)} / ${fmtSize(hostTotal)} (${hostPct}% used)`, u: hostPct, cls: 'pb-blue' },
                { n: 'PostgreSQL Data', txt: `${fmtSize(pgSize)} (Live Data)`, u: pgPct, cls: 'pb-green' },
                { n: 'RAG & AI Files', txt: `${fmtSize(aiSize)} (Vector & Models)`, u: aiPct, cls: 'pb-purple' },
                { n: 'Redis Dump', txt: `${fmtSize(dumpSize)} (Cache Persistence)`, u: dumpPct, cls: 'pb-orange' }
              ];
              htmlEl('st-disk-detail', drives.map(d =>
                `<div class="pb-wrap">
              <div class="pb-label"><span>${d.n}</span><span>${d.txt}</span></div>
              <div class="pb"><div class="pb-fill ${d.cls}" style="width:0%;transition:width .7s ease" data-target="${d.u}"></div></div>
            </div>`
              ).join(''));
              // Animate bars after render
              setTimeout(() => {
                document.querySelectorAll('#st-disk-detail .pb-fill[data-target]').forEach(el => {
                  el.style.width = el.getAttribute('data-target') + '%';
                });
              }, 60);

              // ── File Sistem AI ─────────────────────────────────────────────
              if (s.ai_files && s.ai_files.length > 0) {
                const statusEl = document.getElementById('st-ai-files-status');
                if (statusEl) { statusEl.textContent = s.ai_files.length + ' files'; statusEl.className = 'tag tag-green'; }

                htmlEl('st-ai-files', s.ai_files.map(f => {
                  const icon = f.name.endsWith('.py') ? '<i class="fa-solid fa-gears" style="color:var(--blue);margin-right:6px"></i>' :
                    f.name.endsWith('.json') ? '<i class="fa-solid fa-chart-column" style="color:var(--orange2);margin-right:6px"></i>' :
                      '<i class="fa-solid fa-robot" style="margin-right:6px"></i>';
                  const fmtSize2 = (b) => b < 1024 ? b + ' B' : b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB';
                  const readable = f.readable !== false;
                  const fname = f.name.replace(/'/g, "\\'");
                  const hashShort = f.sha256 ? f.sha256.substring(0, 8) : '';
                  return `
                <div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:8px;padding:10px 12px;gap:6px;border:1px solid var(--border);transition:border-color .2s" onmouseover="this.style.borderColor='var(--blue)'" onmouseout="this.style.borderColor='var(--border)'">
                  <div class="li-name" style="font-size:12px;font-weight:600">${icon}${f.name}</div>
                  <div style="font-size:10px;color:var(--txt3)">${fmtSize2(f.size || 0)} · ${f.desc} ${hashShort ? `<code style="color:var(--cyan);margin-left:4px;font-size:9.5px">SHA256:${hashShort}</code>` : ''}</div>
                  <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:2px">
                    ${readable ? `<button class="btn btn-ghost btn-xs" onclick="StorageFileOps.open('${fname}')" title="Buka & Edit"><i class="fa-solid fa-pen-to-square" style="margin-right:3px"></i>Edit</button>` : ''}
                    <button class="btn btn-ghost btn-xs" onclick="StorageFileOps.download('${fname}')" title="Download"><i class="fa-solid fa-download" style="margin-right:3px"></i>Download</button>
                    <button class="btn btn-ghost btn-xs" onclick="StorageFileOps.validateFile('${fname}')" title="Validate Syntax & Integrity"><i class="fa-solid fa-shield-halved" style="margin-right:3px"></i>Validate</button>
                  </div>
                </div>
              `;
                }).join(''));
              } else {
                const statusEl = document.getElementById('st-ai-files-status');
                if (statusEl) { statusEl.textContent = 'No files'; statusEl.className = 'tag tag-gray'; }
                htmlEl('st-ai-files', '<div style="color:var(--txt2);font-size:11px;padding:12px;text-align:center;grid-column:1/-1">Tidak ada file AI ditemukan</div>');
              }
            } else {
              setEl('st-db', 'Error'); setEl('st-redis', '—'); setEl('st-rag', '—');
              const statusEl = document.getElementById('st-ai-files-status');
              if (statusEl) { statusEl.textContent = 'API Error'; statusEl.className = 'tag tag-red'; }
            }
          } catch (e) {
            console.error('[Storage] Load error:', e);
          } finally {
            this._loading = false;
          }
        },

        startAutoRefresh() {
          if (this._interval) return;
          this._interval = setInterval(() => {
            if (isPanelActive('storage')) this.load();
          }, 5000);
        },

        stopAutoRefresh() {
          if (this._interval) { clearInterval(this._interval); this._interval = null; }
        },

        refresh() {
          this.load();
          Notify.toast('🔄', 'Storage data refreshed', 'ok', 1500);
        }
      },

      /* ---- AI PANEL ---- */

});
