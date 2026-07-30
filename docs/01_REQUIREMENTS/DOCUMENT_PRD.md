OBJECTIVE

Lakukan dokumentasi menyeluruh (Enterprise Architecture Documentation) terhadap seluruh sistem AIOps/NOC yang telah dibangun.

Dokumentasi HARUS dibuat secara otomatis berdasarkan source code, konfigurasi, runtime, Docker Compose, database schema, service yang berjalan, agent, dashboard, AI Engine, telemetry pipeline, serta seluruh implementasi nyata yang ada di repository.

JANGAN membuat dokumentasi berdasarkan asumsi.

JANGAN membuat mock.

JANGAN membuat placeholder.

JANGAN membuat dummy.

JANGAN membuat simulasi.

Semua isi dokumentasi HARUS berasal dari implementasi yang benar-benar ada.

===========================================================
OUTPUT
===========================================================

Seluruh dokumentasi disimpan di folder

incident-analysis/

dengan struktur yang rapi.

Jika folder belum ada maka buat otomatis.

===========================================================
STRUKTUR FOLDER
===========================================================

incident-analysis/

│

├── README.md

├── EXECUTIVE_SUMMARY.md

├── SYSTEM_OVERVIEW.md

├── FULL_ARCHITECTURE.md

├── ARCHITECTURE_DECISION_RECORD.md

├── COMPONENT_INVENTORY.md

├── AGENT_DOCUMENTATION.md

├── SERVER_DOCUMENTATION.md

├── DASHBOARD_DOCUMENTATION.md

├── CHAT_SYSTEM_DOCUMENTATION.md

├── TELEMETRY_DOCUMENTATION.md

├── NETDATA_DOCUMENTATION.md

├── AI_ENGINE_DOCUMENTATION.md

├── RAG_DOCUMENTATION.md

├── RCA_ENGINE_DOCUMENTATION.md

├── INCIDENT_ENGINE_DOCUMENTATION.md

├── WATCHDOG_DOCUMENTATION.md

├── POLICY_ENGINE_DOCUMENTATION.md

├── SECURITY_DOCUMENTATION.md

├── DATABASE_DOCUMENTATION.md

├── API_DOCUMENTATION.md

├── EVENT_PIPELINE.md

├── OBSERVABILITY.md

├── DEPLOYMENT.md

├── RBAC.md

├── TELEGRAM.md

├── PERFORMANCE.md

├── BACKUP_AND_RECOVERY.md

├── KNOWN_LIMITATION.md

├── CHANGELOG.md

├── AUDIT_CHECKLIST.md

├── TROUBLESHOOTING.md

│

├── architecture/

│ ├── architecture_overview.md

│ ├── agent_flow.md

│ ├── telemetry_flow.md

│ ├── ai_flow.md

│ ├── dashboard_flow.md

│ ├── chat_flow.md

│ ├── ingestion_flow.md

│ ├── rca_flow.md

│ ├── remediation_flow.md

│ ├── authentication_flow.md

│ ├── network_flow.md

│ ├── database_flow.md

│ ├── deployment_flow.md

│ ├── startup_sequence.md

│ ├── shutdown_sequence.md

│ ├── sequence_diagram.md

│ ├── dependency_graph.md

│ ├── topology.md

│ ├── data_flow.md

│ └── system_context.md

│

├── flowchart/

│ ├── architecture.mmd

│ ├── telemetry.mmd

│ ├── incident.mmd

│ ├── ai_reasoning.mmd

│ ├── watchdog.mmd

│ ├── browser_agent.mmd

│ ├── dashboard.mmd

│ ├── live_chat.mmd

│ ├── authentication.mmd

│ ├── rca_engine.mmd

│ ├── event_pipeline.mmd

│ ├── deployment.mmd

│ ├── recovery.mmd

│ └── topology.mmd

│

├── diagrams/

│ ├── architecture.drawio

│ ├── deployment.drawio

│ ├── topology.drawio

│ ├── telemetry.drawio

│ ├── dashboard.drawio

│ ├── ai.drawio

│ └── incident.drawio

│

└── assets/

===========================================================
DOKUMENTASI AGENT
===========================================================

Dokumentasikan seluruh agent.

Windows Agent

Linux Agent

Watchdog Agent

Telemetry Agent

Browser Agent

AI Agent

Health Agent

Scheduler Agent

Collector Agent

Netdata Agent

Remote Agent

Notification Agent

Remediation Agent

Untuk setiap agent tampilkan:

Tujuan

Lokasi source code

Dependency

Flow kerja

Library

Config

Port

Thread

Loop

Heartbeat

Recovery

Restart

Failure Mode

Input

Output

API

Telemetry

Log

===========================================================
NETDATA
===========================================================

Dokumentasikan:

Child

Parent

Streaming

Metrics

Alarm

Health

Exporter

Collector

Pipeline

===========================================================
TELEMETRY
===========================================================

Dokumentasikan:

Browser

CPU

RAM

Disk

Network

Temperature

Event Log

Application Log

System Log

Browser Telemetry

Console Error

Crash

URL

Timeline

Pipeline

===========================================================
SERVER
===========================================================

Dashboard Server

Ingestion Server

AI Server

Scheduler

NATS

Redis

PostgreSQL

Nginx

Telegram

Semua service.

===========================================================
DASHBOARD
===========================================================

Dokumentasikan seluruh menu.

Overview

Incident

Monitoring

Fleet

Browser Crash

Live Chat

RCA

AI Insight

RBAC

Policy

Settings

Audit

Semua submenu.

Jelaskan:

Tujuan

API

Data Source

Refresh

Filter

Search

Role

===========================================================
CHAT LIVE
===========================================================

Dokumentasikan:

Flow

Room

Message

AI Chat

Notification

History

Attachment

Role

===========================================================
DATABASE
===========================================================

Dokumentasikan:

Seluruh tabel

Seluruh relasi

Index

JSONB

Trigger

View

Function

===========================================================
API
===========================================================

Dokumentasikan seluruh endpoint.

Request

Response

Authentication

Role

Input

Output

Validation

===========================================================
AI ENGINE
===========================================================

Dokumentasikan:

Pipeline

Consensus

Critic

Policy

Evidence

RAG

Knowledge

Prediction

Root Cause

Recommendation

Hallucination Guard

Evidence Score

Causal Graph

===========================================================
EVENT PIPELINE
===========================================================

Browser

↓

Agent

↓

Collector

↓

Telemetry

↓

NATS

↓

Ingestion

↓

Validation

↓

Database

↓

AI

↓

Dashboard

↓

Notification

↓

Operator

===========================================================
FLOWCHART
===========================================================

Generate Mermaid lengkap.

Flow harus dapat dirender.

Architecture

Sequence

Flow

Topology

Dependency

Deployment

Startup

Shutdown

Authentication

AI

Incident

RCA

===========================================================
FLOW HARUS MENJELASKAN

Windows Agent

↓

Telemetry

↓

Watchdog

↓

Ingestion

↓

NATS

↓

AI

↓

Database

↓

Dashboard

↓

Operator

↓

Remediation

↓

Recovery

===========================================================
DEPENDENCY GRAPH
===========================================================

Bangun graph dependency seluruh sistem.

===========================================================
SYSTEM CONTEXT
===========================================================

Buat Context Diagram.

===========================================================
DEPLOYMENT
===========================================================

Dokumentasikan:

Docker

Container

Port

Volume

Network

Restart

Healthcheck

===========================================================
AUDIT
===========================================================

Setiap file harus berisi:

Tujuan

Komponen

Flow

Dependency

Known Issue

Risk

Recommendation

===========================================================
EXECUTIVE SUMMARY
===========================================================

Buat ringkasan untuk presentasi kepada:

Management

Auditor

Engineer

Developer

===========================================================
OUTPUT AKHIR
===========================================================

Hasil akhir berupa dokumentasi Enterprise yang lengkap, konsisten, mudah dibaca, siap dipresentasikan, mudah diaudit, mudah dipelihara, serta menggambarkan keseluruhan arsitektur dan alur kerja sistem secara end-to-end berdasarkan implementasi nyata yang terdapat di repository.