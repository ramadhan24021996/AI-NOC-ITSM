// Popup script - Memeriksa status koneksi ke local agent dan menampilkan info tab aktif
const badge = document.getElementById("statusBadge");
const domainEl = document.getElementById("domain");

// Cek apakah local agent Go sedang berjalan
fetch("http://127.0.0.1:10001/health", { method: "GET", signal: AbortSignal.timeout(2000) })
  .then(r => {
    badge.textContent = r.ok ? "ONLINE ✓" : "Agent Error";
    badge.className = "badge " + (r.ok ? "online" : "offline");
  })
  .catch(() => {
    badge.textContent = "OFFLINE";
    badge.className = "badge offline";
  });

// Tampilkan domain tab aktif
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs && tabs[0] && tabs[0].url) {
    try {
      domainEl.textContent = new URL(tabs[0].url).hostname || "-";
    } catch {
      domainEl.textContent = "-";
    }
  }
});
