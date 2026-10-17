"""
SERVER.jarvis.agentic.tool_registry — JARVIS Tool Registry
===========================================================
Mendaftarkan semua tool JARVIS sebagai JSON Schema (format Gemini Function Calling).

FILOSOFI HYBRID DISPATCH:
  Tool di sini adalah WRAPPER ke semua handler yang sudah ada:
    - _handle_query()       → get_live_incidents, get_host_metrics, dll
    - _handle_action()      → execute_remediation
    - _handle_chat()        → answer_directly
    - browser_control       → open_dashboard_panel
    - noc_bridge._get()     → get_network_topology, get_system_health
    - RAG service           → search_knowledge

  Hardcoded regex/rules di setiap handler TETAP BERJALAN — mereka menjadi
  backend yang dipanggil oleh tool ini. LLM hanya memutuskan TOOL mana yang
  paling tepat untuk query user.

Zero deletion. Zero regression.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.agentic.tool_registry")


# ─────────────────────────────────────────────────────────────────────────────
# TOOL SCHEMA DEFINITIONS (Gemini Function Calling Format)
# ─────────────────────────────────────────────────────────────────────────────

JARVIS_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_live_incidents",
        "description": (
            "Ambil data insiden real-time dari database NOC. "
            "Gunakan ini ketika operator bertanya tentang insiden, alert, tiket, anomali sistem, "
            "atau status masalah yang sedang terjadi. "
            "Contoh trigger: 'cek insiden', 'ada alert apa', 'berapa tiket open', 'insiden critical hari ini'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter status insiden: OPEN, CLOSED, IN_PROGRESS, atau ALL",
                    "enum": ["OPEN", "CLOSED", "IN_PROGRESS", "ALL"],
                    "default": "OPEN"
                },
                "severity": {
                    "type": "string",
                    "description": "Filter severity: CRITICAL, HIGH, MEDIUM, LOW, atau ALL",
                    "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "ALL"],
                    "default": "ALL"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal insiden yang ditampilkan (1-50)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "get_host_metrics",
        "description": (
            "Ambil metrik host real-time: CPU, RAM, Disk, Network dari device tertentu atau host server. "
            "Gunakan ketika operator menanyakan performa server, resource usage, atau kesehatan device. "
            "Contoh trigger: 'cek cpu kasir-3', 'berapa ram server-01', 'disk usage gudang', 'display metrics', 'cek resource'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Nama device atau hostname (contoh: KASIR-3, SERVER-01, PC-GUDANG). Kosongkan untuk host JARVIS sendiri."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_printer_status",
        "description": (
            "Cek status printer dan print queue dari device atau lokasi tertentu. "
            "Gunakan ketika ada keluhan atau pertanyaan terkait printer, cetak, spooler, atau queue. "
            "Contoh trigger: 'status printer gudang', 'cek print queue kasir', 'printer bermasalah', 'print spooler'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Nama device atau lokasi printer. Kosongkan untuk semua printer."
                }
            },
            "required": []
        }
    },
    {
        "name": "execute_remediation",
        "description": (
            "Eksekusi aksi remediasi atau perbaikan sistem. "
            "WAJIB digunakan ketika operator memerintahkan aksi operasional seperti restart, flush, kill, clear. "
            "Semua aksi melewati Action Catalog Validator dan HITL safety gate. "
            "Contoh trigger: 'restart spooler kasir-3', 'flush dns', 'kill process', 'clear print queue', 'restart service'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_name": {
                    "type": "string",
                    "description": (
                        "Nama aksi dari katalog: RESTART_PRINT_SPOOLER, FLUSH_DNS, CLEAR_PRINT_QUEUE, "
                        "RESTART_NETWORK_ADAPTER, KILL_PROCESS, RECYCLE_APP_POOL, RESTART_SERVICE, "
                        "ESCALATE_TO_HUMAN, SEND_TELEGRAM_ALERT, atau aksi lain dari 146+ catalog."
                    )
                },
                "device_name": {
                    "type": "string",
                    "description": "Nama device target aksi remediasi (contoh: KASIR-3, SERVER-01)"
                },
                "incident_id": {
                    "type": "string",
                    "description": "ID insiden yang terkait (contoh: INC-1895885). Opsional."
                }
            },
            "required": ["action_name", "device_name"]
        }
    },
    {
        "name": "search_knowledge",
        "description": (
            "Cari SOP, playbook, dokumentasi teknis, atau knowledge base di RAG. "
            "Gunakan ketika operator bertanya tentang prosedur, langkah penanganan, atau penjelasan teknis. "
            "Contoh trigger: 'SOP untuk printer error', 'playbook L3 eskalasi', 'cara handle dns failure', "
            "'dokumentasi restart spooler', 'jelaskan apa itu print spooler'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pertanyaan atau topik yang ingin dicari di knowledge base"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "open_dashboard_panel",
        "description": (
            "Navigasi dan buka panel/menu tertentu di dashboard NOC secara otomatis. "
            "Gunakan ketika operator meminta untuk membuka, menampilkan, atau navigasi ke bagian dashboard. "
            "Contoh trigger: 'buka panel network', 'tampilkan AI governance', 'buka tab printer', "
            "'navigasi ke incident management', 'tampilkan pchealth'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "panel_id": {
                    "type": "string",
                    "description": (
                        "ID panel dashboard: overview, pchealth, network, printer, rca, "
                        "incidents, ai-governance, fleet, training, postmortem, jarvis-voice"
                    )
                }
            },
            "required": ["panel_id"]
        }
    },
    {
        "name": "get_system_health",
        "description": (
            "Cek health status semua service dan komponen sistem (Go API, Python AI, Redis, NATS, PostgreSQL, Docker containers). "
            "Gunakan ketika operator bertanya tentang status keseluruhan sistem. "
            "Contoh trigger: 'cek health system', 'status semua service', 'apakah semua berjalan normal', 'system status'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_network_topology",
        "description": (
            "Ambil informasi topologi jaringan, koneksi device, dan status network. "
            "Gunakan ketika operator bertanya tentang jaringan, koneksi antar device, atau infrastruktur network. "
            "Contoh trigger: 'topologi jaringan', 'cek koneksi network', 'device terhubung ke apa', "
            "'status network', 'infrastructure map'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "answer_directly",
        "description": (
            "Jawab pertanyaan langsung tanpa perlu memanggil tool atau data live. "
            "Gunakan untuk: sapaan, pertanyaan umum, identitas JARVIS, penjelasan fitur, "
            "atau ketika pertanyaan tidak memerlukan data real-time. "
            "Contoh trigger: 'siapa kamu', 'halo jarvis', 'kamu bisa apa', 'jelaskan fungsi training feedback'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "Teks jawaban langsung yang akan diberikan kepada operator"
                }
            },
            "required": ["answer"]
        }
    },
    {
        "name": "assign_field_engineer",
        "description": (
            "Tugaskan field engineer ke insiden via Telegram. "
            "Gunakan ketika operator meminta penugasan teknisi lapangan. "
            "Contoh trigger: 'tugaskan Budi ke INC-001', 'kirim teknisi ke kasir-3', 'dispatch engineer gudang'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "ID insiden yang ditugaskan (contoh: INC-1895885)"
                },
                "engineer_name": {
                    "type": "string",
                    "description": "Nama teknisi yang ditugaskan"
                },
                "location": {
                    "type": "string",
                    "description": "Lokasi/device yang perlu dikunjungi"
                }
            },
            "required": ["incident_id"]
        }
    },
]


class JarvisToolRegistry:
    """
    Registry yang menyimpan dan menyediakan schema semua tool JARVIS
    dalam format yang kompatibel dengan Gemini Function Calling API.
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {
            t["name"]: t for t in JARVIS_TOOLS
        }
        logger.info(
            "[JarvisToolRegistry] Initialized with %d tools: %s",
            len(self._tools),
            list(self._tools.keys())
        )

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Kembalikan semua tool schema untuk dikirim ke Gemini API."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Ambil satu tool schema berdasarkan nama."""
        return self._tools.get(name)

    def get_tool_names(self) -> List[str]:
        """Daftar nama semua tool yang terdaftar."""
        return list(self._tools.keys())

    def get_gemini_tool_config(self) -> Dict[str, Any]:
        """
        Format tool config untuk Gemini API (google.genai format).
        Sesuai dokumentasi: tools=[{"function_declarations": [...]}]
        """
        return {
            "tools": [
                {
                    "function_declarations": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["parameters"]
                        }
                        for t in self._tools.values()
                    ]
                }
            ],
            "tool_config": {
                "function_calling_config": {
                    "mode": "AUTO"   # LLM bebas memilih tool atau menjawab langsung
                }
            }
        }
