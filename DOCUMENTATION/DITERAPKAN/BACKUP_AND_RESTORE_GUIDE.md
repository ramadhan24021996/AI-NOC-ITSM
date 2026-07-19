# Walkthrough: Complete System Backup & Restore Guide

This guide documents the usage, design, and structure of the backup and restore modules implemented for the OSI AI Incident Analysis System.

---

## 📂 Backup Directory Layout

The backup process creates an encrypted zip package (AES-256) inside the `backups/` folder. The internal directory layout of the archive is structured as follows:

```
system_backup_YYYYMMDD_HHMMSS.zip
├── backup_manifest.json          # Environment & version metadata
├── docker_inventory.txt          # Active container state inventory
├── models_manifest.json          # Metadata of AI models (actual weights excluded)
│
├── postgres/
│   └── database.dump             # Custom format dump (pg_dump -Fc)
│
├── redis/
│   └── dump.rdb                  # Redis DB snapshot
│
├── docker/
│   ├── docker-compose.yml        # Docker compose configuration
│   ├── Dockerfile                # Portal Dockerfile
│   └── volumes/                  # Named volume tarballs (short-mapped)
│       ├── postgres_data.tar.gz
│       ├── redis_data.tar.gz
│       └── n8n_data_vol.tar.gz
│
├── config/
│   ├── .env                      # environment configurations
│   ├── ai_config.json
│   └── remote_settings.json
│
├── source/
│   ├── backend/                  # SERVER/ source code (Go backend + utilities)
│   ├── frontend/                 # portal/ source code (Dashboard interface)
│   ├── scripts/                  # scripts/ folder contents
│   ├── go.mod                    # Root module files
│   ├── package.json              # Portal package dependency mapping
│   └── requirements.txt          # Python dependency mapping
│
└── logs/                         # Project logs directories
```

---

## 🛠️ Usage Instructions

### 1. Perform a Backup
To run a complete system backup, run the following in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup_system.ps1
```
*Note: If no `-Password` is specified, it will look for `BACKUP_PASSWORD` or `OSI_SECURITY_KEY` in `.env`. If not found, it prompts for a password securely in the terminal.*

To specify a custom name and target the root `backups/` folder:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup_system.ps1 -BackupName "system_backup_20260623_183000.zip"
```

### 2. Schedule Daily Backups (02:00)
Run this command from an **Administrator PowerShell** session to register a Windows Task Scheduler task named `OSI_System_Backup`:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup_system.ps1 -Schedule
```

### 3. Validate a Backup Archive (Dry-Run Mode)
To check if a backup archive is valid, has matching SHA256 hashes, decrypts correctly, and is compatible with the current host without altering any files:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_system.ps1 -BackupFile system_backup_20260623_183000.zip -DryRun
```

### 4. Restore the Complete System
To restore files, databases, and Docker volumes from a backup:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_system.ps1 -BackupFile system_backup_20260623_183000.zip
```
> [!IMPORTANT]
> The restore script automatically creates a **rollback snapshot** of the system's live state before starting the recovery. If any step fails (e.g. database loading error or service port checks failing), the script triggers an automatic rollback to leave your system fully operational.

---

## ✅ Verification and Testing Results

1. **Backup Script Execution**:
   - Tested running `backup_system.ps1` with the password `SuperSecureP@ss123` and custom name `system_backup_20260623_183000.zip`.
   - Verified that the Postgres container was successfully dumped.
   - Verified that Redis was forced to write memory snapshot (`SAVE`) and copied.
   - Verified that the named volumes `postgres_data`, `redis_data`, and `n8n_data_vol` were tar-archived inside WSL using a `busybox` container.
   - Verified that the files were compressed and encrypted with 7-Zip (`C:\Program Files\7-Zip\7z.exe`).
   - Verified that the SHA256 hash was generated.
   - Verified that the backup rotation cleaned up old/empty subdirectories.
2. **Restore Validation (Dry-Run)**:
   - Executed `restore_system.ps1 -BackupFile system_backup_20260623_183000.zip -DryRun`.
   - The script successfully verified the SHA256 checksum.
   - Extracted and read `backup_manifest.json` correctly.
   - Validated OS/host details, verified free space, checked WSL/Docker readiness, and released resources cleanly.
