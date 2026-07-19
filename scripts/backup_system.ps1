$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFolder = "D:\BACKUP\Backup_$timestamp"
Write-Host "=== STARTING FULL SYSTEM BACKUP ==="
Write-Host "Backup Folder: $backupFolder"

# Create directories
New-Item -ItemType Directory -Force -Path "$backupFolder\database" | Out-Null
New-Item -ItemType Directory -Force -Path "$backupFolder\docker" | Out-Null
New-Item -ItemType Directory -Force -Path "$backupFolder\codebase" | Out-Null

# 1. Start Docker Daemon in WSL
Write-Host "[+] Checking Docker daemon status in WSL Ubuntu..."
$dockerStatus = wsl -d Ubuntu -e sh -c "docker info >/dev/null 2>&1; echo `$?"
if ($dockerStatus.Trim() -ne "0") {
    Write-Host "[+] Docker daemon is not running. Starting it..."
    wsl -d Ubuntu -e sh -c "sudo service docker start"
    Start-Sleep -Seconds 5
}
Write-Host "[OK] Docker daemon is running."

# 2. Start Postgres database if not running
Write-Host "[+] Checking if PostgreSQL container (osi-postgres) is running..."
$pgStatus = wsl -d Ubuntu -e sh -c "docker ps --filter 'name=osi-postgres' --format '{{.Names}}'"
if ($pgStatus -notlike "*osi-postgres*") {
    Write-Host "[+] PostgreSQL is not running. Starting it using docker compose..."
    wsl -d Ubuntu -e sh -c "cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS' && docker compose up -d postgres"
    # Wait for postgres to be ready
    Write-Host "[+] Waiting for Postgres to accept connections..."
    for ($i = 0; $i -lt 10; $i++) {
        $ready = wsl -d Ubuntu -e sh -c "docker exec osi-postgres pg_isready -U postgres -d osi_system >/dev/null 2>&1; echo `$?"
        if ($ready.Trim() -eq "0") {
            break
        }
        Start-Sleep -Seconds 2
    }
}
Write-Host "[OK] PostgreSQL container is ready."

# 3. Dump Postgres database
Write-Host "[+] Dumping database osi_system to SQL file..."
# Redirect inside WSL to prevent PowerShell UTF-16 translation
wsl -d Ubuntu -e sh -c "docker exec -i osi-postgres pg_dump -U postgres -d osi_system > /mnt/d/BACKUP/Backup_$timestamp/database/osi_system_backup.sql"
$dbSize = (Get-Item "$backupFolder\database\osi_system_backup.sql").Length / 1MB
Write-Host "[OK] Database dump completed. Size: ($($dbSize.ToString('F2'))) MB"

# 4. Backup Docker Volumes
Write-Host "[+] Creating tarball of Docker volumes..."
wsl -d Ubuntu -e sh -c "tar -czf /mnt/d/BACKUP/Backup_$timestamp/docker/docker_volumes_backup.tar.gz -C /var/lib/docker/volumes ."
$volSize = (Get-Item "$backupFolder\docker\docker_volumes_backup.tar.gz").Length / 1MB
Write-Host "[OK] Docker volumes backup completed. Size: ($($volSize.ToString('F2'))) MB"

# 5. Backup Codebase using Robocopy
Write-Host "[+] Copying codebase to backup folder..."
robocopy "D:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS" "$backupFolder\codebase" /E /XD .git node_modules backups archive /XF backup_run.log /R:1 /W:1 | Out-Null
$filesCount = (Get-ChildItem -Path "$backupFolder\codebase" -Recurse -File).Count
Write-Host "[OK] Codebase backup completed. Copied $filesCount files."

# 6. Write summary
$summaryPath = "$backupFolder\backup_summary.txt"
$summaryText = @"
=== BACKUP SUMMARY ===
Timestamp: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Backup Folder: $backupFolder

1. Database Backup: SUCCESS
   Database Dump: $backupFolder\database\osi_system_backup.sql ($($dbSize.ToString('F2')) MB)
2. Docker Volumes Backup: SUCCESS
   Volumes Tarball: $backupFolder\docker\docker_volumes_backup.tar.gz ($($volSize.ToString('F2')) MB)
3. Codebase Backup: SUCCESS
   Codebase Folder: $backupFolder\codebase ($filesCount files)
"@
$summaryText | Out-File -FilePath $summaryPath -Encoding utf8
Write-Host "=== BACKUP COMPLETED SUCCESSFULLY ==="
Write-Host "Summary saved to $summaryPath"
