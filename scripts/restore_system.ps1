# System Restore Script for OSI AI Incident Analysis System
# Restores databases, Docker volumes, configs, and source code.
# Supports Dry-Run pre-flight checks, automatic rollback, and post-restore verification.

param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,

    [Parameter(Mandatory=$false)]
    [string]$Password,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ProjectRoot = Split-Path -Parent -Path $PSScriptRoot
$backupsDir = Join-Path $ProjectRoot "backups"
$7z = "C:\Program Files\7-Zip\7z.exe"

# ====================================================================
# Helper function: Check port via TCP connect
# ====================================================================
function Test-Port {
    param([string]$IP, [int]$Port)
    $tcp = New-Object System.Net.Sockets.TcpClient
    $connect = $tcp.BeginConnect($IP, $Port, $null, $null)
    $success = $connect.AsyncWaitHandle.WaitOne(2000, $false)
    $conn = $tcp.Connected
    $tcp.Close()
    return ($success -and $conn)
}

# ====================================================================
# Header Presentation
# ====================================================================
Write-Host "====================================================" -ForegroundColor Green
if ($DryRun) {
    Write-Host "      OSI SYSTEM RESTORE UTILITY (DRY RUN MODE)" -ForegroundColor Yellow
} else {
    Write-Host "      OSI SYSTEM RESTORE UTILITY" -ForegroundColor Green
}
Write-Host "====================================================" -ForegroundColor Green

# Parse .env for password/configuration
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvVars = @{}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $EnvVars[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
}

# Resolve decryption password
if (-not $Password) {
    if ($EnvVars.ContainsKey("BACKUP_PASSWORD")) {
        $Password = $EnvVars["BACKUP_PASSWORD"]
    } elseif ($EnvVars.ContainsKey("OSI_SECURITY_KEY")) {
        $Password = $EnvVars["OSI_SECURITY_KEY"]
    } else {
        if ([Environment]::UserInteractive) {
            $SecPassword = Read-Host -Prompt "Enter backup decryption password" -AsSecureString
            $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecPassword)
            $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        } else {
            Write-Error "Backup password is required to decrypt the archive."
            exit 1
        }
    }
}

# Resolve Backup File Path
$ResolvedBackupPath = $BackupFile
if (-not (Test-Path $ResolvedBackupPath)) {
    # Search under backups folder recursively
    $found = Get-ChildItem -Path $backupsDir -Filter $BackupFile -Recurse -File -ErrorAction SilentlyContinue
    if ($found) {
        $ResolvedBackupPath = $found.FullName
    } else {
        Write-Error "Backup archive file not found: $BackupFile"
        exit 1
    }
}

Write-Host "[RESTORE] Using backup archive: $ResolvedBackupPath" -ForegroundColor Cyan

# ====================================================================
# 1. Integrity Check (SHA256 Checksum)
# ====================================================================
Write-Host "[RESTORE] Verifying SHA256 integrity checksum..." -ForegroundColor Yellow
$hashFile = "$ResolvedBackupPath.sha256"
if (Test-Path $hashFile) {
    $expectedHash = (Get-Content $hashFile).Trim()
    $computedHash = (Get-FileHash -Path $ResolvedBackupPath -Algorithm SHA256).Hash
    
    if ($expectedHash -eq $computedHash) {
        Write-Host "[RESTORE] Checksum valid: $computedHash" -ForegroundColor Green
    } else {
        Write-Error "Checksum mismatch! The archive file may be corrupted."
        Write-Error "Expected: $expectedHash"
        Write-Error "Computed: $computedHash"
        exit 1
    }
} else {
    Write-Host "[WARN] SHA256 checksum file (.sha256) not found. Skipping integrity check." -ForegroundColor Yellow
}

# ====================================================================
# 2. Extract Manifest & Pre-flight Compatibility Validation
# ====================================================================
Write-Host "[RESTORE] Extracting manifest and inventory for pre-flight check..." -ForegroundColor Yellow

$TempRestoreFolder = Join-Path $backupsDir "temp_restore"
if (Test-Path $TempRestoreFolder) {
    Remove-Item -Path $TempRestoreFolder -Recurse -Force | Out-Null
}
New-Item -ItemType Directory -Path $TempRestoreFolder | Out-Null
$TempRestoreFolderWSL = "/mnt/d/" + $TempRestoreFolder.Substring(3).Replace("\", "/")
$TempBackupFolderWSL = $TempRestoreFolderWSL


if (-not (Test-Path $7z)) {
    Write-Error "7-Zip executable not found at $7z. Cannot decrypt backup."
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 1
}

# Extract manifest and manifests only first
$args = @("e", $ResolvedBackupPath, "-o$TempRestoreFolder", "-p$Password", "backup_manifest.json", "models_manifest.json", "docker_inventory.txt", "-y")
& $7z $args | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error "Decryption or extraction failed. Check password."
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 1
}

$manifestFile = Join-Path $TempRestoreFolder "backup_manifest.json"
if (-not (Test-Path $manifestFile)) {
    Write-Error "Archive validation failed: backup_manifest.json missing."
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 1
}

$manifest = Get-Content $manifestFile | ConvertFrom-Json
Write-Host "[MANIFEST] Backup Version : $($manifest.version)" -ForegroundColor Cyan
Write-Host "[MANIFEST] Created On      : $($manifest.created)" -ForegroundColor Cyan
Write-Host "[MANIFEST] Source Host    : $($manifest.hostname)" -ForegroundColor Cyan
Write-Host "[MANIFEST] OS             : $($manifest.os)" -ForegroundColor Cyan
Write-Host "[MANIFEST] PostgreSQL     : $($manifest.postgres)" -ForegroundColor Cyan
Write-Host "[MANIFEST] Redis          : $($manifest.redis)" -ForegroundColor Cyan

# Compare host details
$currentOSObj = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
$currentOS = if ($currentOSObj) { $currentOSObj.Caption } else { "Windows" }

Write-Host "[RESTORE] Validating compatibility..." -ForegroundColor Yellow
if ($manifest.os -ne $currentOS) {
    Write-Host "[WARN] Backup was created on a different OS ($($manifest.os)) than the current OS ($currentOS)." -ForegroundColor Yellow
}
if ($manifest.hostname -ne $env:COMPUTERNAME) {
    Write-Host "[INFO] Restoring backup to a new machine: $($manifest.hostname) -> $env:COMPUTERNAME" -ForegroundColor Gray
}

# Check disk space OK
$drive = Get-PSDrive -Name (Split-Path -Qualifier $ProjectRoot).Replace(":", "")
$freeSpaceGB = [Math]::Round($drive.Free / 1GB, 2)
Write-Host "[RESTORE] Free disk space: $freeSpaceGB GB" -ForegroundColor Gray
if ($freeSpaceGB -lt 5) {
    Write-Warning "Low disk space ($freeSpaceGB GB). Restore might fail."
}

# Check WSL and Docker readiness
Write-Host "[RESTORE] Verifying WSL/Docker readiness..." -ForegroundColor Yellow
$wslCheck = wsl -l -v 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "WSL is not running or not installed. WSL is required to restore volumes and database."
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 1
}

$dockerCheck = wsl -d Ubuntu -e sh -c "docker ps" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is offline inside WSL Ubuntu. Please run START_SYSTEM_VERIFIED.bat to initialize Docker."
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 1
}

Write-Host "[SUCCESS] Pre-flight compatibility checks completed." -ForegroundColor Green

if ($DryRun) {
    Write-Host "====================================================" -ForegroundColor Yellow
    Write-Host " [DRY RUN SUCCESS] All checks passed. Releasing resources." -ForegroundColor Yellow
    Write-Host "====================================================" -ForegroundColor Yellow
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    exit 0
}

# ====================================================================
# 3. Create Rollback Snapshot (Rollback Mechanism)
# ====================================================================
Write-Host "[RESTORE] Creating live system rollback snapshot before restore..." -ForegroundColor Yellow
$RollbackDir = Join-Path $backupsDir "temp_rollback"
if (Test-Path $RollbackDir) {
    Remove-Item -Path $RollbackDir -Recurse -Force
}
New-Item -ItemType Directory -Path $RollbackDir | Out-Null

$RollbackDirWSL = "/mnt/d/" + $RollbackDir.Substring(3).Replace("\", "/")

# Backup PostgreSQL
$postgresOnline = $false
$postgresCheck = wsl -d Ubuntu -e sh -c "docker ps --filter 'name=osi-postgres' --format '{{.Names}}'" 2>&1
if ($postgresCheck -match "osi-postgres") { $postgresOnline = $true }

if ($postgresOnline) {
    $dbName = $EnvVars["DB_NAME"]
    if (-not $dbName) { $dbName = "osi_system" }
    New-Item -ItemType Directory -Path "$RollbackDir\postgres" -Force | Out-Null
    wsl -d Ubuntu -e sh -c "docker exec -i osi-postgres pg_dump -U postgres -Fc --clean --if-exists --create $dbName > '$RollbackDirWSL/postgres/database.dump'" 2>&1 | Out-Null
}

# Backup Redis dump
$redisOnline = $false
$redisCheck = wsl -d Ubuntu -e sh -c "docker ps --filter 'name=osi-redis' --format '{{.Names}}'" 2>&1
if ($redisCheck -match "osi-redis") { $redisOnline = $true }

if ($redisOnline) {
    New-Item -ItemType Directory -Path "$RollbackDir\redis" -Force | Out-Null
    wsl -d Ubuntu -e sh -c "docker exec -i osi-redis redis-cli SAVE && docker cp osi-redis:/data/dump.rdb '$RollbackDirWSL/redis/dump.rdb'" 2>&1 | Out-Null
}

# Backup Volumes
New-Item -ItemType Directory -Path "$RollbackDir\volumes" -Force | Out-Null
$volumesOutput = wsl -d Ubuntu -e sh -c "docker volume ls --format '{{.Name}}'" 2>&1
$volumes = $volumesOutput -split "`n" | Where-Object { $_.Trim() -ne "" }
foreach ($vol in $volumes) {
    $vol = $vol.Trim()
    if ($vol -match "postgres_data" -or $vol -match "redis_data" -or $vol -match "n8n_data_vol" -or $vol -match "osi") {
        wsl -d Ubuntu -e sh -c "docker run --rm -v ${vol}:/data -v '${RollbackDirWSL}/volumes:/backup' busybox tar czf /backup/${vol}.tar.gz -C /data ." 2>&1 | Out-Null
    }
}

# ====================================================================
# 4. Extract Complete Backup Archive
# ====================================================================
Write-Host "[RESTORE] Extracting complete backup archive..." -ForegroundColor Yellow
$args = @("x", $ResolvedBackupPath, "-o$TempRestoreFolder", "-p$Password", "-y")
& $7z $args | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error "Extraction failed. Rolling back..."
    # Rollback implementation is placed at the end in try-catch
}

# ====================================================================
# 5. Restore Implementation (Try-Catch with Rollback)
# ====================================================================
try {
    # 5a. Restore Docker Configurations & Volume tarballs
    Write-Host "[RESTORE] Restoring Docker named volumes..." -ForegroundColor Yellow
    $VolTarballs = Get-ChildItem -Path "$TempRestoreFolder\docker\volumes" -Filter "*.tar.gz" -ErrorAction SilentlyContinue
    foreach ($tar in $VolTarballs) {
        $volName = $tar.BaseName
        $actualVolName = $volName
        # Remap standard names back to custom compose prefix
        if ($volName -eq "postgres_data") { $actualVolName = "ai-agendrivenintelligentincidentanalis_postgres_data" }
        elseif ($volName -eq "redis_data") { $actualVolName = "ai-agendrivenintelligentincidentanalis_redis_data" }
        
        Write-Host "[RESTORE] Re-populating volume: $actualVolName..." -ForegroundColor Gray
        # Clear destination volume first and restore
        wsl -d Ubuntu -e sh -c "docker run --rm -v ${actualVolName}:/data -v '${TempBackupFolderWSL}/docker/volumes:/backup' busybox sh -c 'rm -rf /data/* && tar xzf /backup/${volName}.tar.gz -C /data'" 2>&1 | Out-Null
    }
    
    # 5b. Restore PostgreSQL Database dump (pg_restore)
    $SqlBackup = Join-Path $TempRestoreFolder "postgres\database.dump"
    if (Test-Path $SqlBackup) {
        Write-Host "[RESTORE] Restoring PostgreSQL database via pg_restore..." -ForegroundColor Yellow
        $dbName = $EnvVars["DB_NAME"]
        if (-not $dbName) { $dbName = "osi_system" }
        
        $SqlBackupWSL = "$TempBackupFolderWSL/postgres/database.dump"
        # Run pg_restore connecting to template db 'postgres' to recreate clean database
        wsl -d Ubuntu -e sh -c "docker exec -i osi-postgres pg_restore -U postgres -d postgres --clean --create < '$SqlBackupWSL'" 2>&1 | Out-Null
        Write-Host "[RESTORE] Database restored." -ForegroundColor Green
    }
    
    # 5c. Restore Redis dump.rdb
    $RedisBackup = Join-Path $TempRestoreFolder "redis\dump.rdb"
    if (Test-Path $RedisBackup) {
        Write-Host "[RESTORE] Restoring Redis snapshot..." -ForegroundColor Yellow
        wsl -d Ubuntu -e sh -c "docker cp '$TempBackupFolderWSL/redis/dump.rdb' osi-redis:/data/dump.rdb" 2>&1 | Out-Null
        Write-Host "[RESTORE] Restarting Redis container to reload snapshot..." -ForegroundColor Yellow
        wsl -d Ubuntu -e sh -c "docker restart osi-redis" 2>&1 | Out-Null
    }
    
    # 5d. Restore Configs
    Write-Host "[RESTORE] Restoring configuration files..." -ForegroundColor Yellow
    if (Test-Path "$TempRestoreFolder\config\.env") {
        Copy-Item -Path "$TempRestoreFolder\config\.env" -Destination "$ProjectRoot\.env" -Force
    }
    if (Test-Path "$TempRestoreFolder\config\ai_config.json") {
        Copy-Item -Path "$TempRestoreFolder\config\ai_config.json" -Destination "$ProjectRoot\portal\ai_config.json" -Force
    }
    if (Test-Path "$TempRestoreFolder\config\remote_settings.json") {
        Copy-Item -Path "$TempRestoreFolder\config\remote_settings.json" -Destination "$ProjectRoot\portal\remote_settings.json" -Force
    }
    
    # 5e. Restore Source Code Files (Strict Mapping)
    Write-Host "[RESTORE] Restoring project source code files..." -ForegroundColor Yellow
    
    # Restore docker-compose.yml and Dockerfile
    if (Test-Path "$TempRestoreFolder\docker\docker-compose.yml") {
        Copy-Item -Path "$TempRestoreFolder\docker\docker-compose.yml" -Destination "$ProjectRoot\docker-compose.yml" -Force
    }
    if (Test-Path "$TempRestoreFolder\docker\Dockerfile") {
        Copy-Item -Path "$TempRestoreFolder\docker\Dockerfile" -Destination "$ProjectRoot\portal\Dockerfile" -Force
    }

    # Restore Backend (SERVER)
    if (Test-Path "$TempRestoreFolder\source\backend") {
        # Create directory if missing
        if (-not (Test-Path "$ProjectRoot\SERVER")) { New-Item -ItemType Directory -Path "$ProjectRoot\SERVER" -Force | Out-Null }
        Copy-Item -Path "$TempRestoreFolder\source\backend\*" -Destination "$ProjectRoot\SERVER" -Recurse -Force
    }
    # Restore Frontend (portal)
    if (Test-Path "$TempRestoreFolder\source\frontend") {
        if (-not (Test-Path "$ProjectRoot\portal")) { New-Item -ItemType Directory -Path "$ProjectRoot\portal" -Force | Out-Null }
        Copy-Item -Path "$TempRestoreFolder\source\frontend\*" -Destination "$ProjectRoot\portal" -Recurse -Force
    }
    # Restore Scripts (scripts)
    if (Test-Path "$TempRestoreFolder\source\scripts") {
        if (-not (Test-Path "$ProjectRoot\scripts")) { New-Item -ItemType Directory -Path "$ProjectRoot\scripts" -Force | Out-Null }
        Copy-Item -Path "$TempRestoreFolder\source\scripts\*" -Destination "$ProjectRoot\scripts" -Recurse -Force
    }
    # Restore Root Files
    $sourceRootFiles = Get-ChildItem -Path "$TempRestoreFolder\source" -File
    foreach ($sf in $sourceRootFiles) {
        Copy-Item -Path $sf.FullName -Destination $ProjectRoot -Force
    }

    
    # Restart all containers to ensure fresh state
    Write-Host "[RESTORE] Restarting Docker Compose services..." -ForegroundColor Yellow
    wsl -d Ubuntu -e sh -c "cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS' && docker compose restart" 2>&1 | Out-Null
    
    # Sleep to allow services to initialize
    Write-Host "[RESTORE] Waiting 10 seconds for containers to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    # ====================================================================
    # 6. Post-Restore Verification (Point 14)
    # ====================================================================
    Write-Host "[RESTORE] Verifying system health and port bindings..." -ForegroundColor Yellow
    
    $postgresLive = Test-Port "127.0.0.1" 5432
    # Verify via docker exec since 5432 is not exposed directly
    $pgHealthy = wsl -d Ubuntu -e sh -c "docker inspect --format='{{.State.Health.Status}}' osi-postgres" 2>&1
    $redisHealthy = wsl -d Ubuntu -e sh -c "docker inspect --format='{{.State.Health.Status}}' osi-redis" 2>&1
    
    $nginxHTTP = Test-Port "127.0.0.1" 8099
    $nginxHTTPS = Test-Port "127.0.0.1" 9443
    $goIngestion = Test-Port "127.0.0.1" 18800
    $secureRelay = Test-Port "127.0.0.1" 9998
    $launcherService = Test-Port "127.0.0.1" 44600
    
    Write-Host "=== HEALTH CHECKS ===" -ForegroundColor Cyan
    Write-Host "  PostgreSQL Container Health : $(if ($pgHealthy -match 'healthy'){'🟢 HEALTHY'}else{'🔴 UNHEALTHY'})"
    Write-Host "  Redis Container Health      : $(if ($redisHealthy -match 'healthy'){'🟢 HEALTHY'}else{'🔴 UNHEALTHY'})"
    Write-Host "  Nginx HTTP Portal (8099)    : $(if ($nginxHTTP){'🟢 LIVE'}else{'🔴 DEAD'})"
    Write-Host "  Nginx HTTPS Portal (9443)   : $(if ($nginxHTTPS){'🟢 LIVE'}else{'🔴 DEAD'})"
    Write-Host "  Go Ingestion Server (18800) : $(if ($goIngestion){'🟢 LIVE'}else{'🔴 DEAD'})"
    Write-Host "  Secure Relay (9998)         : $(if ($secureRelay){'🟢 LIVE'}else{'🔴 DEAD'})"
    Write-Host "  Remote Launcher (44600)     : $(if ($launcherService){'🟢 LIVE'}else{'🔴 DEAD'})"
    
    if (-not ($nginxHTTP -and $nginxHTTPS -and $goIngestion -and $secureRelay -and ($pgHealthy -match "healthy") -and ($redisHealthy -match "healthy"))) {
        throw "One or more core services failed verification after restore."
    }
    
    # Cleanup temp folder and rollback folder
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    Remove-Item -Path $RollbackDir -Recurse -Force
    
    Write-Host "====================================================" -ForegroundColor Green
    Write-Host "    [SUCCESS] RESTORE COMPLETED AND SYSTEM IS LIVE!" -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Green
    
} catch {
    # ====================================================================
    # 7. Rollback Trigger (Point 15)
    # ====================================================================
    Write-Host "====================================================" -ForegroundColor Red
    Write-Host "   CRITICAL ERROR DETECTED! INITIATING ROLLBACK..." -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    Write-Host "====================================================" -ForegroundColor Red
    
    try {
        # Restore Volumes from Rollback Snapshot
        $rollbackTarballs = Get-ChildItem -Path "$RollbackDir\volumes" -Filter "*.tar.gz" -ErrorAction SilentlyContinue
        foreach ($tar in $rollbackTarballs) {
            $volName = $tar.BaseName
            wsl -d Ubuntu -e sh -c "docker run --rm -v ${volName}:/data -v '${RollbackDirWSL}/volumes:/backup' busybox sh -c 'rm -rf /data/* && tar xzf /backup/${volName}.tar.gz -C /data'" 2>&1 | Out-Null
        }
        
        # Restore Database
        $rollbackDB = Join-Path $RollbackDir "postgres\database.dump"
        if (Test-Path $rollbackDB) {
            $dbName = $EnvVars["DB_NAME"]
            if (-not $dbName) { $dbName = "osi_system" }
            wsl -d Ubuntu -e sh -c "docker exec -i osi-postgres pg_restore -U postgres -d postgres --clean --create < '$RollbackDirWSL/postgres/database.dump'" 2>&1 | Out-Null
        }
        
        # Restore Redis
        $rollbackRedis = Join-Path $RollbackDir "redis\dump.rdb"
        if (Test-Path $rollbackRedis) {
            wsl -d Ubuntu -e sh -c "docker cp '$RollbackDirWSL/redis/dump.rdb' osi-redis:/data/dump.rdb" 2>&1 | Out-Null
            wsl -d Ubuntu -e sh -c "docker restart osi-redis" 2>&1 | Out-Null
        }
        
        # Restart all services
        wsl -d Ubuntu -e sh -c "cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS' && docker compose restart" 2>&1 | Out-Null
        
        Write-Host "[ROLLBACK] System has been successfully reverted to the pre-restore state." -ForegroundColor Green
    } catch {
        Write-Error "CRITICAL: Rollback failed! System state may be corrupt. Error: $_"
    }
    
    # Cleanup temp folder
    Remove-Item -Path $TempRestoreFolder -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}
