/* modules/1_overview/storage.js
 * Atomic Design — 3. Modules Layer (1_overview / storage)
 * Contract: Consumes window.UI.{Atoms,Molecules,Organisms} & window.Services.{Data,WS,ApiInterceptor,JarvisAutoMic,JarvisDuplex}
 */
window.UI = window.UI || { Atoms: {}, Molecules: {}, Organisms: {}, Templates: {} };
window.Services = window.Services || {};
window.Modules = window.Modules || {};
window.Modules["1_overview"] = window.Modules["1_overview"] || {};

if (!window.Panels) window.Panels = {};
Object.assign(window.Panels, {

      storage: {
        _interval: null,
        _loading: false,
        _lastFilesSig: '',

        _esc(str) {
          if (typeof _esc === 'function') return _esc(str);
          return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        },

        _jsAttr(str) {
          if (typeof _jsAttr === 'function') return _jsAttr(str);
          return String(str == null ? '' : str)
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '&quot;');
        },

        async load() {
          if (this._loading) return;
          this._loading = true;
          try {
            const [q, s] = await Promise.all([
              (window.Services.Data || DataService).loadQueues(),
              (window.Services.Data || DataService).loadStorageStats()
            ]);

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
            if (llEl) {
              llEl.textContent = 'L' + ll + ' ' + (ll === 0 ? 'Normal' : ll === 1 ? 'Degraded' : ll === 2 ? 'Critical' : 'Shedding');
              llEl.className = 'tag ' + (ll === 0 ? 'tag-green' : ll === 1 ? 'tag-orange' : 'tag-red');
            }
            setEl('st-throughput', ((q && q.processed_throughput_5s) || 0) + ' ops/5s');
            setEl('st-latency', ((q && q.avg_processing_latency_ms) || 0).toFixed(2) + ' ms');

            // ── Disk Usage & Top KPIs ────────────────────────────────────────
            if (s) {
              const fmtSize = (bytes) => {
                if (!bytes || bytes <= 0) return '0 B';
                const units = ['B', 'KB', 'MB', 'GB', 'TB'];
                let i = 0, size = bytes;
                while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
                return size.toFixed(1) + ' ' + units[i];
              };

              setEl('st-db', fmtSize(s.db_size));
              const tblCnt = s.db_tables_count || 0;
              const connCnt = s.db_active_conns || 0;
              setEl('st-db-sub', `${tblCnt > 0 ? tblCnt + ' tables · ' : ''}${connCnt} active conns · osi_system`);

              setEl('st-redis', fmtSize(s.redis_memory));
              const peakStr = s.redis_peak_memory ? `Peak: ${fmtSize(s.redis_peak_memory)}` : 'In-Memory';
              const keysCnt = s.redis_keys_count != null ? ` · ${Number(s.redis_keys_count).toLocaleString()} keys` : '';
              setEl('st-redis-sub', peakStr + keysCnt);

              setEl('st-rag', fmtSize(s.rag_vectors_size));
              const vecCnt = s.rag_vectors_count != null ? `${Number(s.rag_vectors_count).toLocaleString()} vectors · ` : '';
              setEl('st-rag-sub', `${vecCnt}knowledge_vectors (pgvector)`);

              const pgSize = s.db_size || 0;
              const aiFilesTotal = s.ai_files ? s.ai_files.reduce((sum, f) => sum + (f.size || 0), 0) : 0;
              const aiSize = aiFilesTotal + (s.rag_vectors_size || 0);
              const dumpSize = s.redis_dump_size || s.redis_memory || 0;

              const hd = s.host_disk || {};
              const hostTotal = hd.total_bytes || 0;
              const hostUsed = hd.used_bytes || 0;
              const hostPct = Number(hd.used_pct || (hostTotal > 0 ? (hostUsed / hostTotal * 100) : 0)).toFixed(1);

              // Proportional budget scaling (prevents PostgreSQL bar from permanently pinning at 100%)
              const dbBudget = Math.max(pgSize * 2.5, 512 * 1024 * 1024); // 512 MB baseline or 40% of dynamic tier
              const aiBudget = Math.max(aiSize * 3.0, 32 * 1024 * 1024);  // 32 MB baseline for vectors + engine code
              const redisBudget = Math.max((s.redis_max_memory > 0 ? s.redis_max_memory : dumpSize * 4.0), 64 * 1024 * 1024);

              const pgPct = Math.min(98, Math.max(4, (pgSize / dbBudget) * 100)).toFixed(1);
              const aiPct = Math.min(98, Math.max(4, (aiSize / aiBudget) * 100)).toFixed(1);
              const dumpPct = Math.min(98, Math.max(3, (dumpSize / redisBudget) * 100)).toFixed(1);

              const drives = [
                { id: 'host', n: 'Host Partition (/app)', txt: `${fmtSize(hostUsed)} / ${fmtSize(hostTotal)} (${hostPct}% used)`, u: hostPct, cls: 'pb-blue' },
                { id: 'pg',   n: 'PostgreSQL Data',       txt: `${fmtSize(pgSize)} (${tblCnt || '—'} Tables · Live Data)`, u: pgPct, cls: 'pb-green' },
                { id: 'rag',  n: 'RAG & AI Files',        txt: `${fmtSize(aiSize)} (${(s.rag_vectors_count || 0).toLocaleString()} Vectors & ${s.ai_files ? s.ai_files.length : 0} Engines)`, u: aiPct, cls: 'pb-purple' },
                { id: 'rdb',  n: 'Redis Dump & Cache',    txt: `${fmtSize(dumpSize)} (${(s.redis_keys_count || 0).toLocaleString()} Keys Persistence)`, u: dumpPct, cls: 'pb-orange' }
              ];

              const diskContainer = document.getElementById('st-disk-detail');
              if (diskContainer) {
                const existingBars = diskContainer.querySelectorAll('.pb-wrap[data-drive-id]');
                if (existingBars.length === drives.length) {
                  // Zero-flicker in-place update
                  drives.forEach(d => {
                    const wrap = diskContainer.querySelector(`.pb-wrap[data-drive-id="${d.id}"]`);
                    if (!wrap) return;
                    const lblVal = wrap.querySelector('.pb-drive-txt');
                    const fill = wrap.querySelector('.pb-fill');
                    if (lblVal) lblVal.textContent = d.txt;
                    if (fill) fill.style.width = d.u + '%';
                  });
                } else {
                  diskContainer.innerHTML = drives.map(d => `
                    <div class="pb-wrap" data-drive-id="${d.id}">
                      <div class="pb-label"><span>${this._esc(d.n)}</span><span class="pb-drive-txt">${this._esc(d.txt)}</span></div>
                      <div class="pb"><div class="pb-fill ${d.cls}" style="width:${d.u}%;transition:width .6s ease"></div></div>
                    </div>
                  `).join('');
                }
              }

              // ── File Sistem AI ─────────────────────────────────────────────
              if (s.ai_files && s.ai_files.length > 0) {
                const readableCount = s.ai_files.filter(f => f.readable !== false).length;
                const statusEl = document.getElementById('st-ai-files-status');
                if (statusEl) {
                  statusEl.textContent = `${readableCount} / ${s.ai_files.length} files verified`;
                  statusEl.className = readableCount === s.ai_files.length ? 'tag tag-green' : 'tag tag-orange';
                }

                const filesSig = s.ai_files.map(f => `${f.name}:${f.size}:${f.sha256}`).join('|');
                const filesContainer = document.getElementById('st-ai-files');
                if (filesContainer && (this._lastFilesSig !== filesSig || filesContainer.children.length <= 1)) {
                  this._lastFilesSig = filesSig;
                  filesContainer.innerHTML = s.ai_files.map(f => {
                    const icon = f.name.endsWith('.py')
                      ? '<i class="fa-solid fa-gears" style="color:var(--blue);margin-right:6px"></i>'
                      : f.name.endsWith('.json')
                        ? '<i class="fa-solid fa-file-code" style="color:var(--orange2);margin-right:6px"></i>'
                        : '<i class="fa-solid fa-robot" style="margin-right:6px"></i>';
                    const fmtSize2 = (b) => b < 1024 ? b + ' B' : b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB';
                    const readable = f.readable !== false && (f.size || 0) > 0;
                    const fnameAttr = this._jsAttr(f.name);
                    const hashShort = f.sha256 ? f.sha256.substring(0, 8) : '';
                    return `
                      <div class="li-row" style="flex-direction:column;align-items:flex-start;background:var(--glass);border-radius:8px;padding:10px 12px;gap:6px;border:1px solid var(--border);transition:border-color .2s" onmouseover="this.style.borderColor='var(--blue)'" onmouseout="this.style.borderColor='var(--border)'">
                        <div class="li-name" style="font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:space-between;width:100%">
                          <span>${icon}${this._esc(f.name)}</span>
                          <span class="tag ${readable ? 'tag-green' : 'tag-red'}" style="font-size:9px">${readable ? 'ONLINE' : 'MISSING'}</span>
                        </div>
                        <div style="font-size:10px;color:var(--txt3)">
                          <b>${fmtSize2(f.size || 0)}</b> · ${this._esc(f.desc || '')}
                          ${hashShort ? `<div style="margin-top:2px"><code style="color:var(--cyan);font-size:9.5px">SHA256:${this._esc(hashShort)}</code>${f.mod_time ? ` · <span style="color:var(--txt3)">${this._esc(f.mod_time)}</span>` : ''}</div>` : ''}
                        </div>
                        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:2px">
                          ${readable ? `<button class="btn btn-ghost btn-xs" onclick="StorageFileOps.open('${fnameAttr}')" title="Buka & Edit"><i class="fa-solid fa-pen-to-square" style="margin-right:3px"></i>Edit</button>` : ''}
                          ${readable ? `<button class="btn btn-ghost btn-xs" onclick="StorageFileOps.download('${fnameAttr}')" title="Download"><i class="fa-solid fa-download" style="margin-right:3px"></i>Download</button>` : ''}
                          ${readable ? `<button class="btn btn-ghost btn-xs" onclick="StorageFileOps.validateFile('${fnameAttr}')" title="Validate Syntax & Integrity"><i class="fa-solid fa-shield-halved" style="margin-right:3px"></i>Validate</button>` : ''}
                        </div>
                      </div>
                    `;
                  }).join('');
                }
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
          }, 8000);
        },

        stopAutoRefresh() {
          if (this._interval) { clearInterval(this._interval); this._interval = null; }
        },

        refresh() {
          this._lastFilesSig = '';
          this.load();
          Notify.toast('🔄', 'Storage data refreshed', 'ok', 1500);
        }
      },

      /* ---- AI PANEL ---- */

});

window.Modules["1_overview"]["storage"] = window.Panels;
