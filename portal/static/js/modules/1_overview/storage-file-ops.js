/* storage-file-ops.js
 * Module: StorageFileOps — AI File Read/Edit/Download/Validate.
 * Extracted from o-nav-router.js (lines 226-313) — Phase 5.5 Atomic Design refactor.
 *
 * Layer: Modules > 1_overview
 * Depends on: DataService (service), Notify (molecule), Modal (molecule)
 */
(function () {
  'use strict';

var StorageFileOps = {
  _currentFile: null,

  async open(name) {
    const modal = document.getElementById('modal-ai-file-editor');
    const contentEl = document.getElementById('modal-ai-file-content');
    const nameEl = document.getElementById('modal-ai-file-name');
    const sizeEl = document.getElementById('modal-ai-file-size');
    const modEl = document.getElementById('modal-ai-file-mod');
    const resultEl = document.getElementById('modal-ai-file-result');
    if (!modal) return;

    if (nameEl) nameEl.textContent = name;
    if (contentEl) contentEl.value = 'Loading...';
    if (resultEl) resultEl.textContent = '';
    modal.style.display = 'flex';
    this._currentFile = name;

    try {
      const data = await DataService.fetch('/api/ai_file/read?name=' + encodeURIComponent(name));
      if (!data) { if (contentEl) contentEl.value = '// Error: cannot read file'; return; }
      if (contentEl) contentEl.value = data.content || '';
      if (sizeEl) sizeEl.textContent = (data.size > 1024 ? (data.size / 1024).toFixed(1) + 'KB' : data.size + 'B');
      if (modEl && data.mod_time) modEl.textContent = 'Modified: ' + data.mod_time.replace('T', ' ').slice(0, 19);
    } catch (e) {
      if (contentEl) contentEl.value = '// Error: ' + e.message;
    }
  },

  async save() {
    if (!this._currentFile) return;
    const contentEl = document.getElementById('modal-ai-file-content');
    const resultEl = document.getElementById('modal-ai-file-result');
    if (!contentEl) return;

    if (resultEl) resultEl.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:6px"></i>Saving...';
    try {
      const resp = await DataService.fetch('/api/ai_file/save', {
        method: 'POST',
        body: JSON.stringify({ name: this._currentFile, content: contentEl.value })
      });
      if (resp && resp.success) {
        if (resultEl) resultEl.innerHTML = '<span style="color:var(--green2)">✅ ' + (resp.message || 'Saved') + '</span>';
        Notify.toast('✅ Saved', this._currentFile + ' berhasil disimpan', 'ok', 2000);
        if (Panels.storage) Panels.storage.load();
      } else {
        if (resultEl) resultEl.innerHTML = '<span style="color:var(--red)">❌ ' + (resp && resp.error ? resp.error : 'Save failed') + '</span>';
      }
    } catch (e) {
      if (resultEl) resultEl.innerHTML = '<span style="color:var(--red)">❌ ' + e.message + '</span>';
    }
  },

  download(name) {
    const token = sessionStorage.getItem('noc_jwt_token') || '';
    const a = document.createElement('a');
    a.href = '/api/ai_file/download?name=' + encodeURIComponent(name) + '&_t=' + Date.now();
    a.download = name;
    // Programmatic download with auth header is not possible via <a> tag;
    // Use fetch + blob approach instead:
    fetch(a.href, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        a.href = url;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
      })
      .catch(e => Notify.toast('❌ Download', e.message, 'error', 2500));
  },

  async validateFile(name) {
    Notify.toast('🔍 Validating', 'Memeriksa ' + name + '...', 'info', 1500);
    try {
      const data = await DataService.fetch('/api/ai_file/validate?name=' + encodeURIComponent(name));
      if (!data) { Notify.toast('❌ Validate', 'Gagal terhubung ke server', 'error', 3000); return; }
      const icon = data.valid ? '✅' : '❌';
      Notify.toast(icon + ' Validation', name + ': ' + data.message, data.valid ? 'ok' : 'error', 3500);
    } catch (e) {
      Notify.toast('❌ Validate', e.message, 'error', 3000);
    }
  },

  async validate() {
    if (this._currentFile) await this.validateFile(this._currentFile);
  }
};

  window.StorageFileOps = StorageFileOps;
  window.Modules = window.Modules || {};
  window.Modules["1_overview"] = window.Modules["1_overview"] || {};
  window.Modules["1_overview"]["storage-file-ops"] = StorageFileOps;
  window.Modules.StorageFileOps = StorageFileOps;
})();
