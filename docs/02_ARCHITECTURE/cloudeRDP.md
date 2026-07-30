ENTERPRISE FULL SYSTEM AUDIT & PRODUCTION HARDENING

Anda bertindak sebagai Principal Software Architect, Senior Go Engineer, Senior Python Engineer, Senior React Engineer, Senior PostgreSQL DBA, Senior DevOps Engineer, Docker Engineer, Nginx Engineer, Security Engineer, QA Automation Engineer, dan Site Reliability Engineer (SRE).

Target sistem adalah NOC IT AI Dashboard yang berjalan menggunakan:

React/Vite Frontend
Go Backend
Python AI Engine
PostgreSQL
Redis
Docker Compose
Nginx Reverse Proxy

Target akhir adalah 100% Production Ready.

TUJUAN

Lakukan audit menyeluruh terhadap seluruh source code.

Identifikasi dengan jelas:

fitur yang sudah berfungsi
fitur yang belum selesai
fitur yang rusak
fitur yang tidak pernah dipanggil
route mati
API mati
query database bermasalah
container error
bug frontend
bug backend
memory leak
goroutine leak
race condition
panic
deadlock
infinite loop
broken import
unused code
duplicated code

Kemudian lakukan perbaikan hingga seluruh sistem dapat berjalan stabil.

JANGAN

❌ membuat dummy data

❌ membuat mock API

❌ membuat placeholder

❌ membuat hardcode

❌ menghapus menu

❌ menghilangkan fitur lama

❌ mengganti arsitektur tanpa alasan

❌ mematikan logging

❌ menyembunyikan error

AUDIT FRONTEND

Audit seluruh:

React Component

Pages

Hooks

Layout

Sidebar

Navbar

Widget

Chart

Card

Table

Modal

Dialog

Toast

Notification

Skeleton

Loading

Theme

Dark Mode

Responsive

Accessibility

Lazy Loading

Dynamic Import

Context

Redux/Zustand

React Query

TanStack

Axios

Fetch

WebSocket

SSE

Auto Refresh

Pastikan seluruh component dapat dirender.

Tidak boleh ada:

Blank Page

White Screen

Black Screen

Loading Infinite

Console Error

Unhandled Promise

Undefined

Null Reference

Cannot read property

Chunk Load Failed

Hydration Error

Missing Key

React Warning

ROUTING

Audit seluruh routing.

Pastikan setiap menu mempunyai:

Route

Component

Permission

API

Data Source

Loading State

Error State

Render State

Jika ada route yang tidak memiliki halaman, buat halaman production-ready yang menggunakan data nyata dari backend.

SIDEBAR

Audit seluruh menu.

Buat tabel audit:

Nama Menu

Status Route

Status Component

Status API

Status Database

Status Render

Status Permission

Status Production

Contoh:

Dashboard

Execution Timeline

Storage

Monitoring

Fleet Management

Server Health

PC Health

Printer

Incident Triage

Ground Truth

Event Correlation

Unified Graph

Outcome Verification

Rollback History

DLQ

Recovery Mode

Model Config

Training Feedback

Decision Log

Learning Gate

Playbook

RBAC

Audit seluruh menu yang ada.

BACKEND GO

Audit:

Router

Handler

Middleware

JWT

RBAC

Service

Repository

Database

Worker

Scheduler

Queue

Goroutine

Mutex

Channel

Context

Timeout

Retry

Health Check

Pastikan tidak ada:

panic

goroutine leak

deadlock

memory leak

connection leak

nil pointer

PYTHON ENGINE

Audit:

AI Engine

Inference

Knowledge Engine

RAG

Learning Engine

Training Engine

Embedding

LLM Router

Scheduler

Automation

Pastikan:

thread aman

memory aman

CPU stabil

tidak looping

tidak crash

exception tertangani

DATABASE

Audit PostgreSQL:

Table

Index

Primary Key

Foreign Key

View

Materialized View

Function

Trigger

Constraint

Connection Pool

Transaction

VACUUM

EXPLAIN ANALYZE

Slow Query

Lock

Deadlock

Pastikan:

tidak ada query gagal

tidak ada timeout

tidak ada table orphan

tidak ada duplicate schema

API

Audit seluruh endpoint.

Pastikan seluruh endpoint:

200 OK

JSON Valid

Schema Valid

Response Time <300 ms (normal query)

Pagination benar

Sorting benar

Filtering benar

Authentication benar

Authorization benar

CONTAINER

Audit seluruh container Docker.

Periksa:

Health

Restart Policy

Volume

Bind Mount

Image

CPU

RAM

Network

Bridge

Log

Dependency

Container Startup

Graceful Shutdown

Pastikan seluruh container:

Healthy

Tidak restart terus

Tidak exit

Tidak unhealthy

Tidak orphan

LOG AUDIT

Audit seluruh log:

docker compose logs

frontend

backend

python

postgres

redis

nginx

Cari seluruh:

ERROR

WARNING

PANIC

TRACEBACK

FATAL

Unhandled

Segmentation Fault

Broken Pipe

Timeout

Connection Refused

Database Closed

Context Deadline

Address Already In Use

Nil Pointer

Memory Exhausted

Race Condition

Pastikan hasil akhir:

ZERO ERROR

ZERO WARNING KRITIS

ZERO PANIC

ZERO TRACEBACK

ZERO UNHANDLED EXCEPTION

NGINX

Audit:

Reverse Proxy

SSL

Compression

Cache

Static File

Proxy Timeout

Header

CORS

WebSocket Upgrade

Pastikan:

502

503

504

499

tidak terjadi.

SECURITY

Audit:

JWT

RBAC

Session

CSRF

CORS

XSS

SQL Injection

Command Injection

Directory Traversal

Authentication

Authorization

Secrets

Credential

Docker Secret

Environment Variable

PERFORMANCE

Audit:

Bundle Size

JS Chunk

Lazy Load

Image

CSS

Font

Database Query

API Latency

CPU

RAM

Docker

Disk IO

Network IO

Target:

Dashboard Load <2 detik

API <300 ms

Memory Stabil

CPU Stabil

DASHBOARD

Setiap halaman wajib memiliki:

Header

Breadcrumb

Summary Card

Status Card

Chart

Table

Filter

Search

Refresh

Export

Pagination

Last Update

Health Indicator

Audit Indicator

Data berasal dari backend/database nyata.

Jika database kosong, tampilkan:

Database Connected

0 Record

No Data Available

tanpa menyebabkan halaman kosong.

VALIDASI AKHIR

Lakukan pengujian end-to-end terhadap seluruh dashboard.

Verifikasi:

Seluruh menu dapat dibuka.
Seluruh route aktif.
Seluruh komponen berhasil dirender.
Seluruh API memberikan respons yang valid.
Seluruh query database berhasil dieksekusi.
Seluruh widget menampilkan data nyata.
Tidak ada halaman kosong (blank page).
Tidak ada error JavaScript di browser.
Tidak ada panic pada backend Go.
Tidak ada exception pada Python.
Tidak ada error PostgreSQL.
Tidak ada container berstatus unhealthy.
Tidak ada error pada docker compose logs.
Tidak ada error pada log Nginx.
Tidak ada memory leak, goroutine leak, atau connection leak.
Tidak ada dead code, unused component, atau broken import.
Tidak ada placeholder, dummy data, atau mock API.
Seluruh fitur menggunakan data riil dari backend.
OUTPUT WAJIB

Jangan hanya memperbaiki sistem.

Buat laporan audit lengkap dalam format berikut:

Executive Summary
Total Menu
Menu Berfungsi
Menu Bermasalah
Total API
API Berfungsi
API Bermasalah
Total Database Query
Query Bermasalah
Total Container
Healthy
Unhealthy
Total Error Log
Total Warning
Production Readiness Score (%)
Audit Per Modul

Untuk setiap modul tampilkan:

Status: ✅ Berfungsi / ⚠ Sebagian / ❌ Rusak
Temuan
Root Cause
Dampak
Perbaikan yang dilakukan
File yang diubah
Alasan perubahan
Daftar Error yang Ditemukan

Cantumkan seluruh error beserta lokasi file dan solusi.

Daftar File yang Dimodifikasi

Tampilkan daftar file yang diubah beserta ringkasan perubahan.

Final Verification Checklist

Checklist seluruh menu, API, database, container, dan log dengan status PASS/FAIL.

Acceptance Criteria

Sistem hanya boleh dinyatakan Production Ready apabila memenuhi seluruh syarat berikut:

100% menu dapat diakses.
100% route valid.
100% komponen berhasil dirender.
100% API berfungsi.
100% query database berhasil.
100% container berstatus Healthy.
Tidak ada error maupun panic pada seluruh docker compose logs.
Tidak ada warning kritis yang memengaruhi operasi.
Tidak ada data dummy, mock, placeholder, atau hardcode.
Seluruh dashboard stabil, aman, dapat diaudit, dan siap digunakan pada lingkungan produksi.