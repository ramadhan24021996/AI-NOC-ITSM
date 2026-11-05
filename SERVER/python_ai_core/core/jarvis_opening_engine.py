import random
import logging
from datetime import datetime, time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class JarvisOpeningEngine:
    """
    Dynamic Conversation Opening Engine for Jarvis:
    Constructs context-aware, non-repetitive opening greetings built from 5 dynamic layers:
    1. Greeting (Time-of-day & Day-of-week aware)
    2. Context Detector (Days since last session, ongoing investigation)
    3. System Status (Normal operational status vs Active Incident Alerts)
    4. Priority Event Alert (Highlighting specific critical devices/flags)
    5. Personalized Closing (Context-sensitive call-to-action variants)
    """

    TIME_GREETINGS = {
        "pagi": [
            "Selamat pagi{title}.",
            "Selamat pagi{title}. Sistem NOC terpantau aktif.",
            "Selamat pagi{title}. Memulai sesi pemantauan hari ini.",
            "Selamat pagi{title}. Siap mengawal operasional jaringan."
        ],
        "siang": [
            "Selamat siang{title}.",
            "Selamat siang{title}. Pemantauan sistem tetap berjalan.",
            "Selamat siang{title}. Seluruh layanan terpantau aktif.",
            "Selamat siang{title}. Sistem beroperasi dalam kondisi optimal."
        ],
        "sore": [
            "Selamat sore{title}.",
            "Selamat sore{title}. Memasuki pemantauan periode sore.",
            "Selamat sore{title}. Sistem operasional terpantau stabil.",
            "Selamat sore{title}. Seluruh node jaringan terpantau aman."
        ],
        "malam": [
            "Selamat malam{title}.",
            "Selamat malam{title}. Sistem pemantauan otomatis 24/7 aktif melayani.",
            "Selamat malam{title}. Sesi analisis operasional aktif.",
            "Selamat malam{title}. Mengawal operasional shift malam."
        ]
    }

    WELCOME_BACK_GREETINGS = [
        "Selamat datang kembali{title}.",
        "Senang bertemu Anda kembali{title}.",
        "Selamat datang kembali{title}. Sesi Anda telah terhubung.",
        "Selamat datang kembali di pusat kendali AI NOC{title}."
    ]

    WEEKEND_GREETINGS = [
        "Selamat akhir pekan{title}.",
        "Selamat akhir pekan{title}. Pemantauan otomatis tetap aktif 24/7.",
        "Selamat akhir pekan{title}. Seluruh sistem terpantau stabil."
    ]

    STATUS_NORMAL = [
        "Semua sistem beroperasi normal.",
        "Tidak ada insiden kritis yang memerlukan perhatian saat ini.",
        "Monitoring telemetri menunjukkan kondisi jaringan yang sangat stabil.",
        "Seluruh node dan service NOC berjalan optimal.",
        "Pemeriksaan kesehatan sistem selesai. Tidak ada anomali terdeteksi.",
        "Infrastruktur jaringan berada dalam batas batas latensi ideal.",
        "Status seluruh perangkat terpantau aman dan terkendali."
    ]

    STATUS_INCIDENTS_CRITICAL = [
        "Saya mendeteksi {count} insiden aktif dengan tingkat keparahan {severity}.",
        "Perhatian: Terdapat {count} anomali kritis yang memerlukan perhatian segera.",
        "Sistem mencatat {count} gangguan aktif pada infrastruktur.",
        "Peringatan: Terdapat insiden tingkat {severity} yang mempengaruhi operasional node."
    ]

    STATUS_LONG_ABSENCE = [
        "Sudah beberapa waktu sejak sesi terakhir Anda. Saya telah menyinkronkan data telemetri terbaru.",
        "Selamat datang kembali setelah beberapa hari. Seluruh log insiden telah diperbarui.",
        "Data telemetri terbaru telah berhasil disinkronkan ke dalam repositori pengetahuan."
    ]

    STATUS_ONGOING_WORK = [
        "Kita masih memiliki investigasi terbuka pada {target} yang belum ditutup.",
        "Perhatian: Terdapat investigasi aktif pada {target} yang sedang berjalan.",
        "Sesi sebelumnya mencatat pekerjaan analisis pada {target}."
    ]

    STATUS_SYSTEM_BUSY = [
        "Saat ini terdapat peningkatan aktivitas pemantauan pada jaringan.",
        "Sistem sedang memproses beban telemetri yang cukup tinggi. Memprioritaskan insiden utama.",
        "Aktivitas jaringan meningkat. AI Orchestrator memfokuskan sumber daya pada node kritis."
    ]

    CLOSINGS_NORMAL = [
        "Ada yang ingin Anda analisis saat ini?",
        "Apakah ada komponen tertentu yang ingin Anda periksa?",
        "Silakan berikan perintah atau query analisis.",
        "Saya siap membantu pemeriksaan sistem Anda.",
        "Bagaimana saya dapat membantu operasional NOC Anda saat ini?",
        "Apakah Anda ingin saya menjalankan diagnosa telemetri?",
        "Silakan instruksikan tindakan selanjutnya.",
        "Sistem siap menerima query atau instruksi eksekusi."
    ]

    CLOSINGS_INCIDENT = [
        "Apakah Anda ingin meninjau ringkasan dan rekomendasi mitigasi sekarang?",
        "Apakah kita akan melanjutkan investigasi pada insiden ini?",
        "Apakah Anda ingin saya menjalankan Playbook remediasi otomatis?",
        "Apakah Anda ingin meninjau analisis 5 Whys untuk masalah ini?",
        "Silakan tentukan apakah Anda ingin mengeksekusi tindakan HITL."
    ]

    def _determine_time_key(self, dt: datetime) -> str:
        hour = dt.hour
        if 5 <= hour < 11:
            return "pagi"
        elif 11 <= hour < 15:
            return "siang"
        elif 15 <= hour < 18:
            return "sore"
        else:
            return "malam"

    def generate_opening(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Dynamically constructs a context-aware greeting by picking variations from 5 layers.
        """
        if context is None:
            context = {}

        now = context.get("current_time") or datetime.now()
        time_key = self._determine_time_key(now)
        is_weekend = now.weekday() >= 5
        days_absent = float(context.get("days_since_last_session", 0))
        ongoing_target = context.get("ongoing_investigation")
        incidents = context.get("active_incidents", [])
        is_busy = bool(context.get("system_busy", False))

        parts = []

        # Format title (misal: " Pak Rama" atau ", Pak")
        op_name = context.get("operator_name", "").strip()
        if op_name:
            if not op_name.lower().startswith(("pak", "ibu", "engineer", "manager")):
                title_str = f", Pak {op_name}"
            else:
                title_str = f", {op_name}"
        else:
            title_str = ""

        # Layer 1: Greeting
        if days_absent > 1.5:
            template = random.choice(self.WELCOME_BACK_GREETINGS)
        elif is_weekend and random.random() < 0.5:
            template = random.choice(self.WEEKEND_GREETINGS)
        else:
            template = random.choice(self.TIME_GREETINGS[time_key])

        parts.append(template.format(title=title_str))

        # Layer 2 & 3: Context / System Status
        if incidents:
            count = len(incidents)
            max_sev = context.get("max_severity") or "HIGH"
            template = random.choice(self.STATUS_INCIDENTS_CRITICAL)
            parts.append(template.format(count=count, severity=max_sev))

            # Layer 4: Specific Event Alert if device specified
            first_dev = incidents[0].get("device_name") if isinstance(incidents[0], dict) else None
            first_flag = incidents[0].get("flag") if isinstance(incidents[0], dict) else None
            if first_dev and first_flag:
                parts.append(f"Terdeteksi indikasi {first_flag} pada perangkat {first_dev}.")

        elif ongoing_target:
            template = random.choice(self.STATUS_ONGOING_WORK)
            parts.append(template.format(target=ongoing_target))

        elif days_absent > 1.5:
            parts.append(random.choice(self.STATUS_LONG_ABSENCE))

        elif is_busy:
            parts.append(random.choice(self.STATUS_SYSTEM_BUSY))

        else:
            parts.append(random.choice(self.STATUS_NORMAL))

        # Layer 5: Closing Call to Action
        if incidents or ongoing_target:
            parts.append(random.choice(self.CLOSINGS_INCIDENT))
        else:
            parts.append(random.choice(self.CLOSINGS_NORMAL))

        return " ".join(parts)
