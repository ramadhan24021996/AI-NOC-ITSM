/* utils.service.js
 * Pure utility helpers — no DOM framework dependency, no service dependency.
 * Extracted from data.service.js (lines 6520-6698) — Phase 5.1 Atomic Design refactor.
 *
 * Layer: Services (lowest level)
 * Depends on: CFG (global config object from t-config-globals.js)
 */
(function () {
  'use strict';

  /* ==================================================
     SITE / IP HELPERS
  ================================================== */
  function getSite(ip) {
    if (!ip) return 'Unknown';
    const gw = ip.split('.').slice(0, 3).join('.') + '.1';
    return CFG.GATEWAY_TO_SITE[gw] || CFG.GATEWAY_TO_SITE[ip] || ip.split('.').slice(0, 3).join('.') + '.*';
  }

  /* ==================================================
     TIME HELPERS
  ================================================== */
  function timeSince(ts) {
    if (!ts) return '—';
    const secs = Math.max(0, Math.floor((Date.now() - new Date(ts).getTime()) / 1000));
    if (secs < 60) return secs + 's lalu';
    if (secs < 3600) return Math.floor(secs / 60) + 'm lalu';
    if (secs < 86400) return Math.floor(secs / 3600) + 'j lalu';
    return Math.floor(secs / 86400) + 'h lalu';
  }

  /* ==================================================
     STATUS TAG RENDERER
  ================================================== */
  function statusTag(s) {
    if (!s) return '<span class="tag tag-gray">—</span>';
    const u = (s || '').toUpperCase();
    if (u === 'ONLINE' || u === 'OK') return '<span class="tag tag-green">● Online</span>';
    if (u === 'OFFLINE') return '<span class="tag tag-red">● Offline</span>';
    if (u === 'FAULTY' || u === 'DEGRADED' || u === 'WARNING') return '<span class="tag tag-orange">● Degraded</span>';
    return '<span class="tag tag-gray">' + s + '</span>';
  }

  /* ================================================================
     HUMAN-READABLE TRANSLATOR ENGINE
     Mengubah semua data mentah menjadi Bahasa Indonesia yang mudah dipahami.
     Tidak ada raw flag, raw log, atau kode teknis yang boleh tampil ke klien.
  ================================================================= */
  const _flagMap = {
    'PRINTER_QUEUE_ALERT': '🖨️ Antrean cetak menumpuk',
    'SPOOLER_HANG': '🖨️ Layanan cetak tidak merespons',
    'SPOOLER_ALERT': '🖨️ Layanan cetak terganggu',
    'OFFLINE': '🔴 Perangkat tidak dapat dihubungi',
    'NETWORK_DOWN': '🔌 Koneksi jaringan terputus',
    'NETWORK_LOSS': '🔌 Packet loss jaringan terdeteksi',
    'HIGH_LATENCY': '⏱️ Respon jaringan sangat lambat',
    'LATENCY_ALERT': '⏱️ Respon jaringan lambat',
    'DISK_FULL': '💾 Kapasitas disk hampir penuh',
    'DISK_ALERT': '💾 Peringatan penggunaan disk tinggi',
    'CPU_HIGH': '🔥 Beban prosesor sangat tinggi',
    'CPU_ALERT': '🔥 Penggunaan CPU melebihi batas normal',
    'MEMORY_HIGH': '🧠 Penggunaan memori sangat tinggi',
    'MEMORY_ALERT': '🧠 Penggunaan memori melebihi batas normal',
    'AGENT_OFFLINE': '📡 Agen monitoring tidak aktif',
    'AGENT_ALERT': '📡 Agen monitoring membutuhkan perhatian',
    'DB_DEADLOCK': '🗄️ Basis data mengalami antrean terhenti',
    'DB_HIGH_CONN': '🗄️ Koneksi basis data mendekati batas maksimum',
    'GATEWAY_TIMEOUT': '🌐 Portal/Gateway tidak merespons tepat waktu',
    'HTTP_ERROR': '🌐 Layanan web mengalami gangguan',
    'CRITICAL': '🚨 Insiden kritis — perlu tindakan segera',
    'HIGH': '⚠️ Insiden prioritas tinggi',
    'MEDIUM': '🟡 Insiden prioritas sedang',
    'LOW': '🟢 Insiden prioritas rendah',
    'DEGRADED': '⚠️ Kinerja perangkat menurun',
    'QUEUE_ALERT': '📋 Antrean proses menumpuk',
    'CONNECTION_REFUSED': '🔒 Koneksi ditolak oleh server tujuan',
    'TIMEOUT': '⏰ Waktu koneksi habis tanpa respon',
    'PACKET_LOSS': '📶 Terjadi kehilangan paket data jaringan',
    'SERVICE_DOWN': '⛔ Layanan sistem terhenti',
    'AUTH_FAIL': '🔑 Autentikasi gagal berulang kali',
    'RESOLVED': '✅ Insiden telah diselesaikan',
    'ESCALATED': '📣 Diteruskan ke tim senior',
    'ACTIVE': '🔴 Sedang berlangsung',
    'WATCHDOG_ALERT': '🛡️ Pemantauan Otomatis: Layanan mengalami pemulihan mandiri',
    'WATCHDOG_TRIGGER': '🛡️ Pemicu Pemantauan Sistem',
    'WATCHDOG_FAILED': '🚨 Pemantauan Otomatis: Layanan gagal dipulihkan',
    'PROCESS_CRASH': '💥 Proses aplikasi terhenti mendadak',
    'SOCKET_HANGUP': '🔌 Sambungan jaringan terputus mendadak',
    'DNS_FAILURE': '🌐 Resolusi nama domain (DNS) mengalami kegagalan',
    'UNKNOWN': '❓ Kondisi sistem belum teridentifikasi'
  };

  const _rootCauseMap = {
    'WATCHDOG': 'Layanan pemantau otomatis mendeteksi modul tidak merespons dan melakukan inisialisasi ulang mandiri.',
    'SPOOLER': 'Antrean dokumen menumpuk menyebabkan proses spooler kehabisan memori kerja.',
    'PRINTER': 'Layanan cetak tidak dapat memproses antrean — kemungkinan driver atau memori spooler tersumbat.',
    'NETWORK': 'Koneksi antara perangkat dan switch/router mengalami gangguan.',
    'LATENCY': 'Respons jaringan melambat akibat kemacetan lalu lintas data atau beban server tinggi.',
    'DISK': 'Partisi disk mendekati kapasitas penuh sehingga sistem tidak dapat menulis file baru.',
    'CPU': 'Prosesor kelebihan beban akibat proses yang berjalan tidak normal atau lonjakan aktivitas.',
    'MEMORY': 'Memori fisik habis dipakai — kemungkinan ada proses bocor memori (memory leak).',
    'AGENT': 'Agen monitoring kehilangan koneksi ke server pusat.',
    'DB': 'Basis data mengalami antrean transaksi terhenti (deadlock) atau koneksi mencapai batas maksimum.',
    'GATEWAY': 'Server gateway tidak merespons dalam batas waktu yang ditentukan.',
    'OFFLINE': 'Perangkat tidak dapat dihubungi — kemungkinan mati, kabel terputus, atau IP berubah.',
    'DEFAULT': 'Sistem mendeteksi anomali pada pola kinerja perangkat yang melebihi ambang batas normal.'
  };

  /**
   * Mengubah flag teknis menjadi label Bahasa Indonesia ringkas.
   */
  function humanFlag(flag) {
    if (!flag) return '❓ Status tidak diketahui';
    const f = (flag || '').toUpperCase().replace(/_/g, '_');
    for (const [k, v] of Object.entries(_flagMap)) {
      if (f.includes(k)) return v;
    }
    return '⚠️ ' + (flag || '').replace(/_/g, ' ').toLowerCase()
      .replace(/\b\w/g, c => c.toUpperCase());
  }

  /**
   * Mengubah string evidence / log teknis menjadi kalimat Bahasa Indonesia.
   */
  function humanEvidence(evidence, flag) {
    if (!evidence || evidence === '—' || evidence === '-') return 'Tidak ada detail tambahan.';
    const e = (evidence || '').toLowerCase();
    const f = (flag || '').toUpperCase();

    if (f.includes('SPOOLER') || f.includes('PRINTER') || e.includes('spooler') || e.includes('printer'))
      return 'Layanan cetak mengalami hambatan saat memproses antrean dokumen.';
    if (e.includes('deadlock') || e.includes('lock'))
      return 'Basis data mengalami kondisi saling tunggu (deadlock) antar proses transaksi.';
    if (e.includes('timeout') || e.includes('504') || e.includes('503'))
      return 'Server tidak merespons dalam batas waktu yang ditentukan sistem.';
    if (e.includes('packet loss') || e.includes('loss'))
      return 'Sebagian paket data hilang saat dikirimkan melalui jaringan.';
    if (e.includes('connection refused') || e.includes('refused'))
      return 'Server tujuan menolak koneksi — layanan mungkin tidak berjalan.';
    if (e.includes('cpu') || e.includes('processor'))
      return 'Penggunaan prosesor melebihi ambang batas normal secara konsisten.';
    if (e.includes('disk') || e.includes('storage'))
      return 'Kapasitas penyimpanan mendekati penuh, sistem tidak dapat menulis data baru.';
    if (e.includes('memory') || e.includes('ram') || e.includes('oom'))
      return 'Memori sistem hampir habis — ada proses yang mengkonsumsi terlalu banyak memori.';
    if (e.includes('offline') || e.includes('unreachable') || e.includes('down'))
      return 'Perangkat tidak dapat dihubungi melalui jaringan.';
    if (e.includes('latency') || e.includes('ms') || e.includes('slow'))
      return 'Respon jaringan jauh lebih lambat dari kondisi normal.';

    // Generic fallback: truncate & clean the raw string
    const cleaned = evidence.replace(/[<>{}[\]]/g, '').substring(0, 100);
    return 'Sistem mendeteksi: ' + cleaned + (evidence.length > 100 ? '...' : '');
  }

  /**
   * Mengubah status teknis menjadi label Bahasa Indonesia.
   */
  function humanStatus(status) {
    const map = {
      'ACTIVE': '🔴 Sedang berlangsung',
      'RESOLVED': '✅ Telah diselesaikan',
      'ESCALATED': '📣 Diteruskan ke tim senior',
      'PENDING': '⏳ Menunggu penanganan',
      'SOLVED VERIFIED': '✅ Terselesaikan & diverifikasi',
      'INVESTIGATING': '🔍 Sedang diselidiki',
      'ACKNOWLEDGED': '👁️ Sudah diperhatikan'
    };
    return map[(status || '').toUpperCase()] || ('⚪ ' + (status || 'Tidak diketahui'));
  }

  /**
   * Menentukan akar masalah dalam Bahasa Indonesia berdasarkan flag & evidence.
   */
  function humanRootCause(flag, evidence) {
    const f = (flag || '').toUpperCase();
    const e = (evidence || '').toLowerCase();
    for (const [k, v] of Object.entries(_rootCauseMap)) {
      if (f.includes(k) || e.includes(k.toLowerCase())) return v;
    }
    return _rootCauseMap['DEFAULT'];
  }

  /* ==================================================
     SEVERITY & DEVICE ICON HELPERS
  ================================================== */
  function sevTag(flag) {
    const f = (flag || '').toUpperCase();
    if (f.includes('OFFLINE') || f.includes('CRITICAL') || f.includes('DOWN')) return '<span class="sev-crit">KRITIS</span>';
    if (f.includes('HIGH') || f.includes('ALERT') || f.includes('QUEUE')) return '<span class="sev-high">TINGGI</span>';
    if (f.includes('DEGRADED') || f.includes('LATENCY') || f.includes('AGENT') || f.includes('LOSS')) return '<span class="sev-med">SEDANG</span>';
    return '<span class="sev-low">RENDAH</span>';
  }

  function getDeviceIcon(layer) {
    return ({
      1: '<i class="fa-solid fa-desktop" style="margin-right:6px;color:var(--blue2)"></i>',
      2: '<i class="fa-solid fa-print" style="margin-right:6px;color:var(--green2)"></i>',
      3: '<i class="fa-solid fa-network-wired" style="margin-right:6px;color:var(--cyan2)"></i>',
      4: '<i class="fa-solid fa-plug" style="margin-right:6px;color:var(--orange2)"></i>',
      5: '<i class="fa-solid fa-link" style="margin-right:6px;color:var(--purple2)"></i>',
      6: '<i class="fa-solid fa-chart-line" style="margin-right:6px;color:var(--blue2)"></i>',
      7: '<i class="fa-solid fa-robot" style="margin-right:6px;color:var(--pink2)"></i>'
    })[layer] || '<i class="fa-solid fa-desktop" style="margin-right:6px"></i>';
  }

  /* ==================================================
     DOM MICRO-HELPERS
  ================================================== */
  function pct(n, max) { return max > 0 ? Math.round(n / max * 100) : 0; }
  function setEl(id, val) { var e = document.getElementById(id); if (e) e.textContent = val; }
  function htmlEl(id, val) { var e = document.getElementById(id); if (e) e.innerHTML = val; }
  function isPanelActive(id) { var e = document.getElementById('p-' + id); return e ? e.classList.contains('active') : false; }
  function updateLastRefresh() { var _el = document.getElementById('bdg-monitoring'); if (_el) _el.textContent = 'Live'; }
  function pbColor(val) { return val >= 80 ? 'pb-red' : val >= 60 ? 'pb-orange' : 'pb-green'; }

  /* ==================================================
     GLOBAL REGISTRATION
  ================================================== */
  window.getSite = getSite;
  window.timeSince = timeSince;
  window.statusTag = statusTag;
  window.humanFlag = humanFlag;
  window.humanEvidence = humanEvidence;
  window.humanStatus = humanStatus;
  window.humanRootCause = humanRootCause;
  window.sevTag = sevTag;
  window.getDeviceIcon = getDeviceIcon;
  window.pct = pct;
  window.setEl = setEl;
  window.htmlEl = htmlEl;
  window.isPanelActive = isPanelActive;
  window.updateLastRefresh = updateLastRefresh;
  window.pbColor = pbColor;

  /* Namespace registration */
  window.Services = window.Services || {};
  window.Services.Utils = {
    getSite: getSite,
    timeSince: timeSince,
    statusTag: statusTag,
    humanFlag: humanFlag,
    humanEvidence: humanEvidence,
    humanStatus: humanStatus,
    humanRootCause: humanRootCause,
    sevTag: sevTag,
    getDeviceIcon: getDeviceIcon,
    pct: pct,
    setEl: setEl,
    htmlEl: htmlEl,
    isPanelActive: isPanelActive,
    updateLastRefresh: updateLastRefresh,
    pbColor: pbColor
  };
  window.Utils = window.Services.Utils;
})();
