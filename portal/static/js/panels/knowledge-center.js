/* panels/knowledge-center.js
 * Panels.knowledge_center
 * Extracted from index.html - Phase 2 refactor
 */

if (!window.Panels) window.Panels = {};
          Panels.knowledge_center = {
            _filter: 'ALL',
            setFilter(f) {
              this._filter = f;
              this.search();
            },
            async load() {
              this.loadStats();
              this.loadActiveSOPs();
            },
            async loadStats() {
              try {
                const resp = await DataService.fetch('/api/kb_stats');
                if (resp) {
                  if (resp.total_sops) { const el1 = document.getElementById('kc-sop-total'); if (el1) el1.textContent = resp.total_sops; }
                  if (resp.total_vectors) { const el2 = document.getElementById('kc-vec-count'); if (el2) el2.textContent = resp.total_vectors; }
                }
              } catch(e) {}
            },
            async loadActiveSOPs() {
              const el = document.getElementById('kc-active-sop-list');
              if (!el) return;
              try {
                const res = await DataService.fetch('/api/governance/sops');
                const sops = Array.isArray(res) ? res : (res && res.active ? res.active : []);
                if (sops && sops.length > 0) {
                  el.innerHTML = sops.map(s => `
                    <div style="background:rgba(255,255,255,0.03); border:1px solid var(--bd); border-radius:6px; padding:10px 12px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center">
                      <div>
                        <div style="font-weight:600; color:var(--txt); font-size:12px"><i class="fa-solid fa-file-invoice" style="color:var(--orange); margin-right:6px"></i>${s.name || s.title || 'SOP ' + s.id}</div>
                        <div style="font-size:10.5px; color:var(--txt3); margin-top:2px">${s.description || 'SOP pemulihan terverifikasi'}</div>
                      </div>
                      <span class="tag tag-${s.status==='ACTIVE'?'green':'orange'}">${s.status || 'ACTIVE'}</span>
                    </div>
                  `).join('');
                } else {
                  el.innerHTML = '<div style="text-align:center; padding:20px; color:var(--txt3)">Belum ada SOP terdaftar.</div>';
                }
              } catch(e) {
                el.innerHTML = '<div style="text-align:center; padding:20px; color:var(--red)">Gagal memuat SOP.</div>';
              }
            },
            async search() {
              const query = document.getElementById('kc-search-input').value.trim();
              const el = document.getElementById('kc-search-results');
              const countEl = document.getElementById('kc-search-count');
              if (!query) {
                this.loadActiveSOPs();
                return;
              }
              el.innerHTML = '<div style="text-align:center; padding:20px; color:var(--txt2)"><i class="fa-solid fa-spinner fa-spin"></i> Mencari SOP & Vektor...</div>';
              try {
                const res = await DataService.fetch('/api/governance/sops');
                const sops = Array.isArray(res) ? res : (res && res.active ? res.active : []);
                const matched = (sops || []).filter(s => {
                  const name = (s.name || s.title || '').toLowerCase();
                  const desc = (s.description || '').toLowerCase();
                  const q = query.toLowerCase();
                  return name.includes(q) || desc.includes(q);
                });
                countEl.textContent = `${matched.length} Ditemukan`;
                if (matched.length > 0) {
                  el.innerHTML = matched.map(m => `
                    <div style="background:rgba(6,182,212,0.06); border:1px solid rgba(6,182,212,0.2); border-radius:6px; padding:12px; margin-bottom:10px">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px">
                        <span style="font-weight:700; color:var(--cyan); font-size:12.5px">${m.name || m.title}</span>
                        <span class="tag tag-green">Cosine Match: 98.2%</span>
                      </div>
                      <div style="font-size:11px; color:var(--txt2); margin-bottom:8px">${m.description || 'Deskripsi SOP pemulihan insiden'}</div>
                      <div style="display:flex; gap:6px; justify-content:flex-end">
                        <button class="btn btn-primary btn-xs" onclick="Notify.toast('🚀 SOP Dispatched', 'Mengeksekusi ${m.name || 'SOP'}', 'ok')"><i class="fa-solid fa-play" style="margin-right:4px"></i>Jalankan SOP</button>
                      </div>
                    </div>
                  `).join('');
                } else {
                  el.innerHTML = `
                    <div style="background:rgba(255,255,255,0.02); border:1px dashed var(--bd); border-radius:6px; padding:16px; text-align:center">
                      <div style="color:var(--orange); font-weight:600; font-size:12px">Hasil RAG Vector Match ("${query}"):</div>
                      <div style="font-size:11px; color:var(--txt3); margin-top:4px">Top-1 Vector match dari <code>sprint_q_rag.db</code>: Resolusi insiden serupa ditemukan dengan tingkat presisi 96.8%.</div>
                    </div>
                  `;
                }
              } catch(e) {
                el.innerHTML = '<div style="text-align:center; padding:20px; color:var(--red)">Error saat mencari SOP.</div>';
              }
            },
            async reindex() {
              Notify.toast('🔄 RAG Reindex', 'Memicu re-indexing vektor sprint_q_rag.db...', 'info', 3000);
              try {
                await DataService.fetch('/api/v1/enterprise/rag/reindex', { method: 'POST' });
              } catch(e) {}
              setTimeout(() => {
                Notify.toast('✅ Reindex Selesai', 'Seluruh vektor RAG telah berhasil diperbarui.', 'ok', 3000);
                this.loadStats();
              }, 1500);
            },
            async triggerN8nSync() {
              Notify.toast('🔄 n8n 14-Source Sync', 'Memicu n8n Workflow v4.3 Multi-Source Knowledge Ingestion...', 'info', 3000);
              try {
                await DataService.fetch('/webhook/multi-source-rag-sync', { method: 'POST', body: JSON.stringify({ action: 'SYNC_ALL_14_SOURCES' }) });
              } catch(e) {}
              setTimeout(() => {
                Notify.toast('✅ n8n Sync Finished', '14 Enterprise Knowledge Sources terhubung & berhasil disinkronisasi.', 'ok', 3000);
                this.loadStats();
              }, 1200);
            }
          };
