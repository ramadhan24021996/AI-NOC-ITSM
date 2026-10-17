"""
SERVER.jarvis.cognition.phonetic_corrector — Voice STT Phonetic Auto-Correction Engine
=======================================================================================
Mengoreksi kesalahan ketik/transkripsi suara dari Web Speech API (Chrome STT Bahasa Indonesia)
dan Whisper STT untuk istilah-istilah teknis NOC, nama tool, protokol jaringan, dan perintah khusus.

v2.1 (Gap #5 Fix): Expanded dengan ~45 entri baru untuk:
  - Istilah jaringan lanjutan (gateway, vlan, ssl, firewall, routing)
  - Perangkat NOC (switch, router, ups, modem, access point)
  - Angka verbal (satu→1, dua→2, tiga→3 untuk device numbering)
  - Nama site (marketing, finance, hrd, kantor pusat)
  - Status teknis (downtime, degraded, flapping, throttling)
  - Perintah remediation (recycle, force restart, kill proses)
"""
import re
from typing import Dict

# Mapping komprehensif kesalahan pengucapan (Phonetic / STT Typo Map) -> Perbaikan Baku
PHONETIC_REPLACEMENTS: Dict[str, str] = {
    # === WAKE WORDS & JARVIS NAME ===
    r"\b(jervis|jarfis|zarvis|charvis|jaspis|jarvisnya|servis|servisnya)\b": "jarvis",
    # Partial wake word — STT drops leading 'J' or 'Ja'
    r"(?:^|\s)(arvis|avis|harvis|jarbi|jarvi|jarbi|javis)(?:[,\s])": " jarvis ",

    # === BROWSER & PLATFORM ===
    r"\b(yutub|yutup|utub|youtub)\b":                       "youtube",
    r"\b(chat\s*jipiti|chat\s*gipiti|gipiti|gpt\s*ei|gpt\s*ai|gpt\s*e\s*i|gpt\s*i|ji\s*pi\s*ti|ji\s*pe\s*te|chat\s*gpt|chat\s*gpt\s*ai|jet\.ai|gepeto|gpt\.ai|gpt)\b": "chatgpt",
    r"\b(play\s*lagu|putar\s*lagu|play\s*musik|putar\s*musik)\b": "play musik",
    r"\b(favo|fav|faforit|pavorit|pavo|pevorit|favorid)\b": "favorit",
    r"\b(buka\s*teks|teks|text)\b":                         "",
    r"\b(live\s*cat|live\s*catting|lai\s*cat)\b":           "live chat",
    r"\b(live\s*lock|live\s*lok|live\s*loc|live\s*look|lai\s*log|live\s*lognya)\b": "live log",
    r"\b(open\s*menu|open)\b":                             "buka",

    # === REMOTE TOOLS & PROTOCOLS ===
    r"\b(rus\s*desk|rasdesk|rosdesk|rusdek|rust\s*desk)\b": "rustdesk",
    r"\b(vi\s*en\s*si|vensi|pi\s*en\s*si)\b":               "vnc",
    r"\b(ar\s*di\s*pi|er\s*de\s*pe|er\s*di\s*pi)\b":       "rdp",
    r"\b(es\s*es\s*ha|es\s*es\s*h)\b":                     "ssh",
    r"\b(service\s*buka\s*remote|buka\s*remote\s*akses|remote\s*akses|akses\s*remote|service\s*buka)\b": "remote",
    r"\b(pcnux|pc\s*nux|pc\s*nuk|nux|nuk|noob|nobe)\b":     "PC-MKT-NUC",

    # === HARDWARE & NOC METRICS ===
    r"\b(si\s*p\s*u|se\s*p\s*u|ce\s*p\s*u|sepuh|sepu|si\s*pi\s*u|se\s*pi\s*u)\b": "cpu",
    r"\b(rem|raem)\b":                                      "ram",
    r"\b(disik|desks)\b":                                   "disk",
    r"\b(hel|helth|heltek|helcek|helsek|halk\s*cek)\b":    "health",
    r"\b(servr|serv|servernya)\b":                          "server",
    r"\b(priter|printe)\b":                                 "printer",
    r"\b(devis|divais|devaice)\b":                         "device",
    r"\b(stat|satus|tatus)\b":                             "status",

    # === TECHNICAL NOC TERMS ===
    r"\b(spuler|sipuler|spoler|spul)\b":                   "spooler",
    r"\b(posgres|postgre|pos\s*gres)\b":                    "postgresql",
    r"\b(flas\s*dns|plas\s*dns|plas\s*d\s*en\s*es|flus\s*dns)\b": "flush dns",
    r"\b(be\s*ge\s*pe|pejei|bjei)\b":                      "bgp",
    r"\b(o\s*te\s*a|otey)\b":                              "ota",
    r"\b(fail\s*over|pelover)\b":                          "failover",
    r"\b(autit\s*log|otit\s*log)\b":                      "audit log",
    r"\b(kosal\s*graf|kausal\s*graf)\b":                   "causal graph",
    r"\b(blas\s*radius|blas\s*radios)\b":                  "blast radius",
    r"\b(sanbox|senbox|sampox|sanbok)\b":                  "sandbox",
    # criticality score — common STT corruption patterns (BUG-B fix)
    r"\b(tritikalitis|tritikal\s*itis|tri\s*tikal\s*iti|kritikaliti|kritikalitas|kritikalite|kritikal\s*iti)\b": "criticality",
    r"\b(tritikal|tri\s*tikal)\b":                         "criticality",
    # 'score' STT corruption: 'chord', 'chort', 'skore', 'skor' (BUG-B fix)
    r"\b(chord|chort|skore|scor(?!e))\b":                  "score",

    # === COMMANDS & HITL ACTIONS ===
    r"\b(restar|restat|res\s*tat|ristart)\b":               "restart",
    r"\b(apruf|aprof|apruve)\b":                            "approve",
    r"\b(rijek|rijec|rejek)\b":                             "reject",

    # === NETWORK & SITES ===
    r"\b(netwok|netwoknya|jaringan)\b":                    "jaringan",
    r"\b(mikrotik|mikro\s*tik)\b":                         "mikrotik",
    r"\b(sisco|sisko)\b":                                  "cisco",
    r"\b(kashir|kasier)\b":                                "kasir",
    r"\b(gudan)\b":                                        "gudang",

    # === STATUS & METRICS ===
    r"\b(on\s*lein|onlin|on\s*line)\b":                    "online",
    r"\b(of\s*lein|offlin|of\s*line)\b":                   "offline",
    r"\b(sistem|sistemnya)\b":                             "sistem",

    # ──────────────────────────────────────────────────────────────────────────
    # GAP #5 FIX: 45+ Entri Baru
    # ──────────────────────────────────────────────────────────────────────────

    # === ANGKA VERBAL → DIGIT (untuk device numbering) ===
    r"\b(satu)\b":                                         "1",
    r"\b(dua)\b":                                          "2",
    r"\b(tiga)\b":                                         "3",
    r"\b(empat)\b":                                        "4",
    r"\b(lima)\b":                                         "5",
    r"\b(enam)\b":                                         "6",
    r"\b(tujuh)\b":                                        "7",
    r"\b(delapan)\b":                                      "8",
    r"\b(sembilan)\b":                                     "9",
    r"\b(sepuluh)\b":                                      "10",

    # === PERANGKAT NOC TAMBAHAN ===
    r"\b(swits|swic|swich|suitc)\b":                       "switch",
    r"\b(routher|rowter|ruter|ruther)\b":                  "router",
    r"\b(yu\s*pi\s*es|u\s*pi\s*es|ups\s*nya)\b":          "ups",
    r"\b(akses\s*point|ak\s*ses\s*poin|ap\s*wifi)\b":     "access point",
    r"\b(modem|modens|modems|mo\s*dem)\b":                 "modem",
    r"\b(faierwol|fayer\s*wal|faier\s*wall)\b":           "firewall",

    # === ISTILAH JARINGAN LANJUTAN ===
    r"\b(gateway\s*timeout|geitwei\s*timeout|gaitway\s*timeout)\b": "gateway timeout",
    r"\b(http\s*lima\s*ratus\s*empat|http\s*504|eror\s*504)\b": "http 504",
    r"\b(http\s*lima\s*ratus\s*tiga|http\s*503|eror\s*503)\b": "http 503",
    r"\b(es\s*es\s*el|ssl\s*error|ssl\s*eror)\b":         "ssl",
    r"\b(vi\s*el\s*an|vilan|v\s*l\s*a\s*n)\b":            "vlan",
    r"\b(routing\s*table|rutin\s*tabel)\b":                "routing table",
    r"\b(pe\s*in\s*ge|pinge|pin\s*ge)\b":                 "ping",
    r"\b(latensi|laten\s*si)\b":                          "latency",
    r"\b(bandwit|bandwid|band\s*with)\b":                 "bandwidth",
    r"\b(throtling|throtteling|troling)\b":               "throttling",
    r"\b(koneksi|koneksinya)\b":                          "koneksi",

    # === STATUS TEKNIS ===
    r"\b(dauntime|down\s*tyme|dawntaim)\b":               "downtime",
    r"\b(degreided|degraid|degradid)\b":                  "degraded",
    r"\b(flapink|flapin|flapping\s*link)\b":              "flapping",
    r"\b(kritis|krissis)\b":                              "critical",
    r"\b(peringatan|warnink|warning)\b":                  "warning",
    r"\b(normal|normail|normil)\b":                       "normal",

    # === PERINTAH REMEDIATION TAMBAHAN ===
    r"\b(risaikel|re\s*cycle|risikle)\b":                 "recycling",
    r"\b(fors\s*restart|force\s*restar|paksa\s*restart)\b": "force restart",
    r"\b(kil\s*proses|kill\s*proses|matiin\s*proses)\b":  "kill proses",
    r"\b(klir\s*log|bersih\s*log|hapus\s*log)\b":         "clear log",
    r"\b(rolog\s*in|re\s*login|relogin)\b":               "re-login",

    # === NAMA SITE / DEPARTEMEN ===
    r"\b(marketting|marketin|markting)\b":                "marketing",
    r"\b(finans|finan|keuangan)\b":                       "finance",
    r"\b(eich\s*ar\s*di|h\s*r\s*d|heardee)\b":           "hrd",
    r"\b(kantor\s*pus|kanpus|kant\s*pusat)\b":            "kantor pusat",
    r"\b(operasional|ops|operasi)\b":                     "operasional",
    r"\b(produksi|produk\s*si)\b":                        "produksi",

    # === IDENTIFIKASI INSIDEN ===
    r"\b(in\s*si\s*dent|inseden|insiden)\b":              "incident",
    r"\b(ar\s*ka\s*a|r\s*c\s*a|risiea)\b":               "rca",
    r"\b(es\s*el\s*a|sela|s\s*l\s*a)\b":                 "sla",
    r"\b(es\s*o\s*pe|esope|s\s*o\s*p)\b":                "sop",
}


class JarvisPhoneticCorrector:
    """Mesin normalisasi fonetik untuk korpus suara Bahasa Indonesia + Istilah NOC.

    v2.1 (Gap #5 Fix): Expanded dari 50 → 95+ entri kamus fonetik.
    """

    @classmethod
    def normalize_transcript(cls, raw_transcript: str) -> str:
        """Koreksi otomatis hasil STT mentah dari Web Speech API & FasterWhisper."""
        if not raw_transcript:
            return ""

        normalized = raw_transcript.strip()

        # Replace phonetic patterns iteratively
        for pattern, replacement in PHONETIC_REPLACEMENTS.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # Clean extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def get_typo_corrections_count(cls) -> int:
        return len(PHONETIC_REPLACEMENTS)

