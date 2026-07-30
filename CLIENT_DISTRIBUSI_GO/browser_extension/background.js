/**
 * OSI Agent - Browser Extension Background Service Worker
 * =========================================================
 * Prinsip Kerja:
 *   1. Mendengarkan event pergantian tab & URL (chrome.tabs.onActivated, onUpdated)
 *   2. Menghitung durasi aktif per tab (Active Time Tracking)
 *   3. Mengirim payload JSON ke http://127.0.0.1:10001/ext-telemetry (Local Agent Go)
 *   4. Agent Go yang akan meneruskan data ke Master Server (IP Server mengikuti config agent)
 *
 * Komunikasi:
 *   Ekstensi --> 127.0.0.1:10001 (Local Agent) --> [IP_MASTER_SERVER]:80 (Dashboard)
 */

const LOCAL_AGENT_URL = "http://127.0.0.1:10001/ext-telemetry";
const FLUSH_INTERVAL_MS = 10000; // Kirim ke agent setiap 10 detik
const IDLE_THRESHOLD_SEC = 60;   // User dianggap idle setelah 60 detik tidak ada aktivitas

// ── State Tracking ─────────────────────────────────────────────────────────

let activeTabInfo = {
  tabId: null,
  url: "",
  title: "",
  domain: "",
  startTime: Date.now(),
};

let pendingEvents = [];
let pcName = "UNKNOWN-HOST";

// ── Utility ─────────────────────────────────────────────────────────────────

/**
 * Mengekstrak domain dari URL penuh.
 * Contoh: "https://google.com/search?q=test" => "google.com"
 */
function extractDomain(url) {
  try {
    if (!url || url.startsWith("chrome://") || url.startsWith("chrome-extension://") || url.startsWith("about:")) {
      return "";
    }
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

/**
 * Finalisasi event tab yang sebelumnya aktif & simpan ke antrian.
 * Hitung durasi aktif sebenarnya.
 */
function finalizeCurrentTab() {
  if (!activeTabInfo.tabId || !activeTabInfo.domain) return;

  const durationSec = Math.round((Date.now() - activeTabInfo.startTime) / 1000);
  if (durationSec < 1) return; // Abaikan kunjungan terlalu singkat

  pendingEvents.push({
    type: "web_activity",
    browser: detectBrowser(),
    url: activeTabInfo.url,
    domain: activeTabInfo.domain,
    tab_title: activeTabInfo.title,
    active_time_sec: durationSec,
    tab_state: "completed",
    timestamp: Math.floor(activeTabInfo.startTime / 1000),
    pc_name: pcName,
    source: "browser_extension",
  });
}

/**
 * Deteksi nama browser dari User-Agent.
 */
function detectBrowser() {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("edg/")) return "edge";
  if (ua.includes("opr/") || ua.includes("opera")) return "opera";
  if (ua.includes("brave")) return "brave";
  if (ua.includes("chrome")) return "chrome";
  if (ua.includes("firefox")) return "firefox";
  return "unknown";
}

/**
 * Kirim antrian event ke Local Agent (127.0.0.1:10001)
 */
async function flushToLocalAgent() {
  if (pendingEvents.length === 0) return;

  const eventsToSend = [...pendingEvents];
  pendingEvents = [];

  try {
    await fetch(LOCAL_AGENT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: eventsToSend }),
    });
    console.log(`[OSI-EXT] Flushed ${eventsToSend.length} event(s) to local agent.`);
  } catch (err) {
    // Jika agent offline, kembalikan events ke antrian agar tidak hilang
    pendingEvents = eventsToSend.concat(pendingEvents).slice(0, 200); // batas 200 event
    console.warn("[OSI-EXT] Local agent tidak tersedia, event di-buffer:", err.message);
  }
}

/**
 * Update info tab aktif saat ini.
 */
async function updateActiveTab(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    const domain = extractDomain(tab.url || "");

    finalizeCurrentTab();

    activeTabInfo = {
      tabId: tabId,
      url: tab.url || "",
      title: tab.title || "",
      domain: domain,
      startTime: Date.now(),
    };
  } catch {
    // Tab mungkin sudah tutup
    finalizeCurrentTab();
    activeTabInfo = { tabId: null, url: "", title: "", domain: "", startTime: Date.now() };
  }
}

// ── Event Listeners ──────────────────────────────────────────────────────────

// Event: User berganti tab
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  await updateActiveTab(activeInfo.tabId);
});

// Event: URL di tab aktif berubah (navigasi ke halaman baru)
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.active) {
    await updateActiveTab(tabId);
  }
});

// Event: Tab ditutup
chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeTabInfo.tabId) {
    finalizeCurrentTab();
    activeTabInfo = { tabId: null, url: "", title: "", domain: "", startTime: Date.now() };
  }
});

// Event: Status idle user berubah
chrome.idle.setDetectionInterval(IDLE_THRESHOLD_SEC);
chrome.idle.onStateChanged.addListener((newState) => {
  if (newState === "idle" || newState === "locked") {
    // User pergi dari komputer - finalisasi tab aktif
    finalizeCurrentTab();
    activeTabInfo.startTime = Date.now(); // Reset timer
  } else if (newState === "active") {
    // User kembali aktif - reset waktu mulai
    activeTabInfo.startTime = Date.now();
  }
});

// ── Periodic Flush ───────────────────────────────────────────────────────────

// Flush event ke local agent secara periodik
setInterval(async () => {
  // Tambahkan snapshot tab aktif saat ini ke antrian sebelum flush
  if (activeTabInfo.tabId && activeTabInfo.domain) {
    const currentDurationSec = Math.round((Date.now() - activeTabInfo.startTime) / 1000);
    if (currentDurationSec >= 5) {
      pendingEvents.push({
        type: "web_activity",
        browser: detectBrowser(),
        url: activeTabInfo.url,
        domain: activeTabInfo.domain,
        tab_title: activeTabInfo.title,
        active_time_sec: currentDurationSec,
        tab_state: "active",
        timestamp: Math.floor(Date.now() / 1000),
        pc_name: pcName,
        source: "browser_extension",
      });
      // Reset startTime agar durasi tidak double-count
      activeTabInfo.startTime = Date.now();
    }
  }

  await flushToLocalAgent();
}, FLUSH_INTERVAL_MS);

// ── Startup ──────────────────────────────────────────────────────────────────

// Inisialisasi: ambil tab yang sedang aktif saat extension di-load
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs && tabs.length > 0) {
    updateActiveTab(tabs[0].id);
  }
});

console.log("[OSI-EXT] OSI Agent Browser Extension started. Reporting to:", LOCAL_AGENT_URL);
