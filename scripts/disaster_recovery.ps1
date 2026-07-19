# Disaster Recovery Script for OSI AI Incident Analysis System
# Supports Backup and Restore operations for PostgreSQL, Redis, and configuration files

param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("backup", "restore")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [string]$BackupFile
)

$ProjectRoot = Split-Path -Parent -Path $PSScriptRoot
$BackupDir = Join-Path $ProjectRoot "backup_data"
$EnvFile = Join-Path $ProjectRoot ".env"

# Load environment variables from .env
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        [System.Environment]::SetEnvironmentVariable($name, $value)
    }
}

$DB_NAME = [System.Environment]::GetEnvironmentVariable("DB_NAME")
if (-not $DB_NAME) { $DB_NAME = "osi_system" }
$DB_USER = "postgres"
$DB_PASS = "postgres"

function Show-Header {
    Write-Host "====================================================" -ForegroundColor Green
    Write-Host "   OSI AI SYSTEM DISASTER RECOVERY UTILITY" -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Green
}

function Perform-Backup {
    Show-Header
    Write-Host "[DR] Initiating system backup..." -ForegroundColor Cyan
    
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }
    
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $TempBackupFolder = Join-Path $BackupDir "temp_$Timestamp"
    New-Item -ItemType Directory -Path $TempBackupFolder | Out-Null
    
    # 1. Backup PostgreSQL
    Write-Host "[DR] Backing up PostgreSQL database..." -ForegroundColor Yellow
    $SqlBackup = Join-Path $TempBackupFolder "db_backup.sql"
    
    # Try Docker backup first
    $dockerCheck = docker ps --filter "name=osi-postgres" --format "{{.Names}}"
    if ($dockerCheck -eq "osi-postgres") {
        Write-Host "[DR] PostgreSQL detected in Docker container 'osi-postgres'. Using docker pg_dump..." -ForegroundColor Gray
        docker exec -t osi-postgres pg_dump -U postgres $DB_NAME > $SqlBackup
    } else {
        # Local postgres fallback
        $pgDumpPath = "pg_dump"
        try {
            $env:PGPASSWORD = $DB_PASS
            & $pgDumpPath -U $DB_USER -h localhost -d $DB_NAME -f $SqlBackup
        } catch {
            Write-Host "[ERROR] pg_dump failed. Make sure pg_dump is in your PATH." -ForegroundColor Red
        }
    }
    
    # 2. Backup Redis Snapshot
    Write-Host "[DR] Backing up Redis snapshot..." -ForegroundColor Yellow
    $RedisBackup = Join-Path $TempBackupFolder "dump.rdb"
    
    $redisDockerCheck = docker ps --filter "name=osi-redis" --format "{{.Names}}"
    if ($redisDockerCheck -eq "osi-redis") {
        docker cp osi-redis:/data/dump.rdb $RedisBackup
    } else {
        # Local redis dump fallback
        $localRedisDump = "C:\Redis\dump.rdb"
        if (Test-Path $localRedisDump) {
            Copy-Item -Path $localRedisDump -Destination $RedisBackup -Force
        } else {
            Write-Host "[WARN] Local dump.rdb not found in C:\Redis." -ForegroundColor DarkYellow
        }
    }
    
    # 3. Backup Config Files
    Write-Host "[DR] Backing up configurations..." -ForegroundColor Yellow
    $ConfigBackupDir = Join-Path $TempBackupFolder "config"
    New-Item -ItemType Directory -Path $ConfigBackupDir | Out-Null
    
    $ConfigsToBackup = @(
        (Join-Path $ProjectRoot "portal\remote_settings.json"),
        (Join-Path $ProjectRoot "server\01_CORE_SERVER\ai_config.json"),
        (Join-Path $ProjectRoot ".env")
    )
    
    foreach ($file in $ConfigsToBackup) {
        if (Test-Path $file) {
            Copy-Item -Path $file -Destination $ConfigBackupDir -Force
        }
    }
    
    # 4. Zip the backup archive
    $ZipPath = Join-Path $BackupDir "osi_backup_$Timestamp.zip"
    Write-Host "[DR] Compressing backup archive to $ZipPath..." -ForegroundColor Yellow
    Compress-Archive -Path "$TempBackupFolder\*" -DestinationPath $ZipPath -Force
    
    # Cleanup temp folder
    Remove-Item -Path $TempBackupFolder -Recurse -Force
    
    Write-Host "[SUCCESS] Backup completed successfully: $ZipPath" -ForegroundColor Green
}

function Perform-Restore {
    Show-Header
    if (-not $BackupFile) {
        Write-Host "[ERROR] Please specify -BackupFile parameter to restore." -ForegroundColor Red
        return
    }
    
    if (-not (Test-Path $BackupFile)) {
        # Check inside backup_data folder
        $AltPath = Join-Path $BackupDir $BackupFile
        if (Test-Path $AltPath) {
            $BackupFile = $AltPath
        } else {
            Write-Host "[ERROR] Backup archive not found: $BackupFile" -ForegroundColor Red
            return
        }
    }
    
    Write-Host "[DR] Restoring system from: $BackupFile" -ForegroundColor Cyan
    
    $TempRestoreFolder = Join-Path $BackupDir "temp_restore"
    if (Test-Path $TempRestoreFolder) {
        Remove-Item -Path $TempRestoreFolder -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TempRestoreFolder | Out-Null
    
    Write-Host "[DR] Extracting archive..." -ForegroundColor Yellow
    Expand-Archive -Path $BackupFile -DestinationPath $TempRestoreFolder -Force
    
    # 1. Restore PostgreSQL
    $SqlBackup = Join-Path $TempRestoreFolder "db_backup.sql"
    if (Test-Path $SqlBackup) {
        Write-Host "[DR] Restoring PostgreSQL database..." -ForegroundColor Yellow
        $dockerCheck = docker ps --filter "name=osi-postgres" --format "{{.Names}}"
        if ($dockerCheck -eq "osi-postgres") {
            # Drop/recreate DB for clean import
            docker exec -t osi-postgres dropdb -U postgres --if-exists $DB_NAME
            docker exec -t osi-postgres createdb -U postgres $DB_NAME
            docker exec -i osi-postgres psql -U postgres -d $DB_NAME < $SqlBackup
        } else {
            # Local restore
            $env:PGPASSWORD = $DB_PASS
            try {
                & dropdb -U $DB_USER -h localhost --if-exists $DB_NAME
                & createdb -U $DB_USER -h localhost $DB_NAME
                & psql -U $DB_USER -h localhost -d $DB_NAME -f $SqlBackup
            } catch {
                Write-Host "[ERROR] Local database restore failed. Make sure psql CLI tools are in PATH." -ForegroundColor Red
            }
        }
    }
    
    # 2. Restore Redis Snapshot
    $RedisBackup = Join-Path $TempRestoreFolder "dump.rdb"
    if (Test-Path $RedisBackup) {
        Write-Host "[DR] Restoring Redis snapshot..." -ForegroundColor Yellow
        $redisDockerCheck = docker ps --filter "name=osi-redis" --format "{{.Names}}"
        if ($redisDockerCheck -eq "osi-redis") {
            docker cp $RedisBackup osi-redis:/data/dump.rdb
            docker restart osi-redis
        } else {
            $localRedisDump = "C:\Redis\dump.rdb"
            if (Test-Path (Split-Path $localRedisDump)) {
                # Stop local redis service if running
                Stop-Service -Name "redis" -ErrorAction SilentlyContinue
                Copy-Item -Path $RedisBackup -Destination $localRedisDump -Force
                Start-Service -Name "redis" -ErrorAction SilentlyContinue
            }
        }
    }
    
    # 3. Restore Config Files
    Write-Host "[DR] Restoring configurations..." -ForegroundColor Yellow
    $ConfigBackupDir = Join-Path $TempRestoreFolder "config"
    if (Test-Path $ConfigBackupDir) {
        Copy-Item -Path (Join-Path $ConfigBackupDir "remote_settings.json") -Destination (Join-Path $ProjectRoot "portal\remote_settings.json") -Force -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $ConfigBackupDir "ai_config.json") -Destination (Join-Path $ProjectRoot "server\01_CORE_SERVER\ai_config.json") -Force -ErrorAction SilentlyContinue
        Copy-Item -Path (Join-Path $ConfigBackupDir ".env") -Destination (Join-Path $ProjectRoot ".env") -Force -ErrorAction SilentlyContinue
    }
    
    # Cleanup temp folder
    Remove-Item -Path $TempRestoreFolder -Recurse -Force
    
    Write-Host "[SUCCESS] Disaster recovery restore completed successfully!" -ForegroundColor Green
}

if ($Action -eq "backup") {
    Perform-Backup
} elseif ($Action -eq "restore") {
    Perform-Restore
}
