MISSION:
Perform a COMPLETE FORENSIC AUDIT of the entire "incident-analysis" project.

THIS IS NOT A CODE REVIEW.

THIS IS NOT A FILE REVIEW.

THIS IS A COMPLETE SYSTEM ARCHITECTURE AUDIT.

The objective is to understand the ENTIRE SYSTEM exactly as it currently exists.

You MUST inspect EVERYTHING.

NEVER skip files because they look small.

NEVER skip folders because they look unused.

NEVER assume.

NEVER summarize without evidence.

NEVER stop until the entire repository has been traversed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY REPOSITORY COVERAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recursively inspect every folder including but not limited to:

SERVER/

CLIENT_DISTRIBUSI_GO/

portal/

docker/

config/

docs/

scripts/

database/

postgres/

nginx/

n8n/

backup/

archive/

artifacts/

knowledge/

RAG/

GraphRAG/

tests/

workflows/

telemetry/

templates/

static/

python_ai_core/

ALL subdirectories

ALL hidden folders

ALL build scripts

ALL migrations

ALL YAML

ALL Dockerfiles

ALL Compose files

ALL JSON

ALL TOML

ALL ENV

ALL GO

ALL PYTHON

ALL HTML

ALL CSS

ALL JS

ALL SQL

ALL Markdown

ALL protobuf

ALL shell scripts

ALL PowerShell

ALL batch

ALL binaries metadata

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY CROSS ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Do NOT inspect files independently.

Build the complete dependency graph.

Determine:

Who calls whom

Who imports whom

Who generates data

Who consumes data

Who owns state

Who owns cache

Who owns memory

Who owns configuration

Who owns persistence

Who owns orchestration

Who owns scheduling

Who owns execution

Who owns rollback

Who owns learning

Who owns RAG

Who owns GraphRAG

Who owns telemetry

Who owns dashboard

Who owns websocket

Who owns REST API

Who owns database

Who owns NATS

Who owns Redis

Who owns PostgreSQL

Who owns authentication

Who owns authorization

Who owns RBAC

Who owns HITL

Who owns sandbox

Who owns remediation

Who owns execution pipeline

Who owns verification

Who owns rollback

Who owns learning feedback

Who owns vector database

Who owns knowledge ingestion

Who owns embeddings

Who owns model registry

Who owns plugin registry

Who owns capability registry

Who owns agent registry

Who owns tool registry

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRACE EVERY DATA FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For every component determine:

Input

Output

Events

Dependencies

Thread ownership

Concurrency

Shared memory

Channels

Queues

Locks

Database writes

Database reads

API calls

WebSocket events

NATS subjects

Redis usage

Filesystem usage

Temporary files

Caching

Configuration loading

Plugin loading

Dynamic imports

Reflection

AI calls

LLM calls

Embedding calls

RAG retrieval

Graph traversal

Learning updates

Dashboard rendering

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUILD COMPLETE SYSTEM MAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Produce complete diagrams internally for:

Folder hierarchy

Module hierarchy

Package hierarchy

Dependency graph

Execution graph

Data flow graph

Knowledge flow graph

GraphRAG flow

Telemetry flow

Learning flow

Remediation flow

Approval flow

Rollback flow

Agent communication graph

Dashboard rendering graph

API routing graph

Go backend graph

Python backend graph

Frontend graph

Database schema graph

Docker communication graph

Container dependency graph

Network topology

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTIFY EVERYTHING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Detect:

Dead code

Duplicate modules

Unused functions

Unused endpoints

Unused APIs

Unused database tables

Unused migrations

Unused JS

Unused CSS

Unused templates

Unused imports

Unused packages

Circular dependency

Race conditions

Memory leaks

Potential deadlocks

Security issues

Missing validation

RBAC bypass

Missing HITL

Direct execution paths

Bypass of sandbox

Bypass of rollback

Bypass of audit trail

Missing logging

Missing metrics

Missing monitoring

Missing retries

Missing timeout

Missing rollback

Missing verification

Missing ownership

Missing abstraction

Missing interfaces

Large files requiring modularization

High coupling

Low cohesion

Technical debt

Architecture smells

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAPHRAG AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify every interaction between:

Knowledge Store

Vector Store

Graph Store

Embedding Engine

Knowledge Aggregator

KEDB

Runbook

SOP

Learning Engine

Feedback Loop

RAG Router

Prompt Builder

LLM Core

Graph Traversal

Evidence Engine

Ranking Engine

Confidence Engine

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MULTI AGENT AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify every specialist agent.

Architect Agent

Developer Agent

Learning Agent

Network Agent

OS Agent

Printer Agent

Security Agent

Storage Agent

Database Agent

Browser Agent

Cloud Agent

Identity Agent

Virtualization Agent

Application Agent

Verify:

Responsibilities

Communication

Isolation

Memory ownership

Capability ownership

Tool ownership

Planning ownership

Execution ownership

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ZERO TRUST AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify every execution path.

No command may execute without:

Risk Analysis

Action Matrix

Sandbox

Policy Engine

Verification

Rollback

Audit Trail

HITL

Digital Signature

Evidence

If any path bypasses these controls,

report it as CRITICAL.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DASHBOARD AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify every dashboard panel.

Trace:

Backend endpoint

WebSocket

REST API

Database query

Graph source

Knowledge source

Telemetry source

Rendering pipeline

JavaScript controller

HTML template

CSS

Events

If any panel is disconnected,

report it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Produce a COMPLETE ENTERPRISE AUDIT REPORT.

Do NOT stop after finding one issue.

Continue until the ENTIRE repository has been audited.

Report:

System Overview

Architecture Overview

Dependency Graph

Data Flow

Execution Flow

Knowledge Flow

Module Inventory

Component Inventory

Unused Components

Security Findings

Performance Findings

Concurrency Findings

Database Findings

Frontend Findings

Backend Findings

Go Findings

Python Findings

GraphRAG Findings

Multi-Agent Findings

Zero Trust Findings

Dashboard Findings

Production Readiness

Architecture Score

Security Score

Reliability Score

Maintainability Score

Scalability Score

Technical Debt Score

Risk Score

Critical Findings

Recommended Refactoring Roadmap

Evidence for every finding.

Never guess.

Never hallucinate.

Every conclusion must reference actual source code.

Continue auditing until every reachable file has been analyzed.

DO NOT FINISH EARLY.

ZERO FILES LEFT BEHIND.
Tambahan agar audit benar-benar mendalam

Untuk proyek sebesar incident-analysis, saya juga menyarankan menambahkan aturan berikut di akhir prompt:

Recursive Deep Scan: ulangi audit hingga tidak ditemukan file, modul, endpoint, dependency, atau relasi baru pada iterasi berikutnya (fixed-point analysis).
Evidence Required: setiap temuan wajib menyebutkan file, fungsi/kelas, dan alur pemanggil (caller → callee). Jangan membuat kesimpulan tanpa bukti dari kode.
Cross-Reference Validation: cocokkan hasil analisis frontend, backend Go, Python AI Core, database, Docker, dan konfigurasi. Laporkan bila ada ketidaksesuaian.
Production Gap Matrix: hasil akhir harus berupa matriks Implemented, Partially Implemented, Missing, Dead Code, dan Needs Refactoring untuk setiap modul dan capability yang telah direncanakan.
No Assumptions: bila sebuah komponen tidak dapat diverifikasi dari kode yang ada, tandai sebagai UNVERIFIED daripada mengasumsikan perilakunya.