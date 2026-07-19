import os
import sys
import subprocess
import shutil
from datetime import datetime

# Define paths
SOURCE_DIR = r"D:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS"
BACKUP_ROOT = r"D:\BACKUP"

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_cmd(cmd, check=True, shell=False, capture_output=False):
    """Runs a command and returns the completed process."""
    try:
        res = subprocess.run(cmd, check=check, shell=shell, capture_output=capture_output, text=True)
        return res
    except subprocess.CalledProcessError as e:
        log(f"Error executing command: {cmd}")
        if e.stdout:
            log(f"Stdout: {e.stdout}")
        if e.stderr:
            log(f"Stderr: {e.stderr}")
        raise e

def check_wsl_docker_running():
    log("Checking if Docker daemon is running in WSL Ubuntu...")
    # Run docker info to verify daemon status
    res = subprocess.run(["wsl", "-d", "Ubuntu", "docker", "info"], capture_output=True)
    if res.returncode == 0:
        log("Docker daemon is already running.")
        return True
    
    log("Docker daemon is not running. Attempting to start Docker daemon in WSL Ubuntu...")
    # Attempt to start docker using systemctl or service
    run_cmd(["wsl", "-d", "Ubuntu", "service", "docker", "start"])
    
    # Wait and verify
    import time
    for i in range(5):
        time.sleep(2)
        res = subprocess.run(["wsl", "-d", "Ubuntu", "docker", "info"], capture_output=True)
        if res.returncode == 0:
            log("Docker daemon started successfully.")
            return True
        log(f"Waiting for Docker daemon... ({i+1}/5)")
        
    log("Failed to verify Docker daemon running.")
    return False

def ensure_postgres_running():
    log("Ensuring PostgreSQL database container is running...")
    # Check if osi-postgres is running
    res = subprocess.run(["wsl", "-d", "Ubuntu", "docker", "ps", "--filter", "name=osi-postgres", "--format", "{{.Names}}"], capture_output=True, text=True)
    if "osi-postgres" in res.stdout:
        log("PostgreSQL container (osi-postgres) is running.")
        return True
        
    log("PostgreSQL container is not running. Starting Postgres container using docker-compose...")
    # Run docker compose up -d postgres
    wsl_project_path = "/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS"
    run_cmd(["wsl", "-d", "Ubuntu", "sh", "-c", f"cd '{wsl_project_path}' && docker compose up -d postgres"])
    
    # Wait for postgres to be ready
    import time
    log("Waiting for PostgreSQL database to be ready (healthcheck)...")
    for i in range(10):
        time.sleep(2)
        res = subprocess.run(["wsl", "-d", "Ubuntu", "docker", "exec", "osi-postgres", "pg_isready", "-U", "postgres", "-d", "osi_system"], capture_output=True)
        if res.returncode == 0:
            log("PostgreSQL database is ready to accept connections.")
            return True
        log(f"Waiting for Postgres... ({i+1}/10)")
        
    log("PostgreSQL database did not start or is not ready.")
    return False

def perform_db_backup(backup_db_path):
    log("Starting database backup...")
    try:
        # Run pg_dump and redirect stdout to database backup file
        with open(backup_db_path, "w", encoding="utf-8") as f:
            # We use subprocess.run with stdout bound to the file object
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "docker", "exec", "-i", "osi-postgres", "pg_dump", "-U", "postgres", "-d", "osi_system"],
                stdout=f,
                stderr=subprocess.PIPE,
                check=True
            )
        file_size_mb = os.path.getsize(backup_db_path) / (1024 * 1024)
        log(f"Database backup completed successfully. File size: {file_size_mb:.2f} MB")
        return True
    except Exception as e:
        log(f"Failed to dump database: {e}")
        return False

def perform_docker_volumes_backup(backup_volumes_path):
    log("Starting Docker volumes backup...")
    # Convert target path to WSL format: D:\BACKUP\... -> /mnt/d/BACKUP/...
    wsl_backup_path = backup_volumes_path.replace("D:", "/mnt/d").replace("\\", "/")
    
    # We will compress the contents of /var/lib/docker/volumes into the target tar.gz
    # Note that tar requires root, but WSL default user here is root.
    try:
        # Run tar inside WSL
        # We exclude metadata and temporary files if any, but backing up the whole directory is safest.
        tar_cmd = ["wsl", "-d", "Ubuntu", "tar", "-czf", wsl_backup_path, "-C", "/var/lib/docker/volumes", "."]
        run_cmd(tar_cmd)
        file_size_mb = os.path.getsize(backup_volumes_path) / (1024 * 1024)
        log(f"Docker volumes backup completed successfully. File size: {file_size_mb:.2f} MB")
        return True
    except Exception as e:
        log(f"Failed to backup Docker volumes: {e}")
        return False

def perform_codebase_backup(backup_codebase_dir):
    log("Starting codebase backup...")
    # Excludes list
    excludes = {".git", "node_modules", "backups", "archive"}
    
    copied_count = 0
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Prune directories we don't want to copy
            dirs[:] = [d for d in dirs if d not in excludes]
            
            # Create corresponding directory structure in backup
            rel_path = os.path.relpath(root, SOURCE_DIR)
            if rel_path == ".":
                target_root = backup_codebase_dir
            else:
                target_root = os.path.join(backup_codebase_dir, rel_path)
                
            os.makedirs(target_root, exist_ok=True)
            
            for file in files:
                # Skip large archive files that might be in the root if we want to save space
                # But since we have space, we will copy everything unless it's a huge zip that is already a backup.
                if file.endswith(".zip") and "MIGRATION" in file:
                    # Let's copy it as it is part of the system, but skip backups or temporary files
                    _ = None
                
                src_file = os.path.join(root, file)
                dest_file = os.path.join(target_root, file)
                
                shutil.copy2(src_file, dest_file)
                copied_count += 1
                total_size += os.path.getsize(src_file)
                
        total_size_mb = total_size / (1024 * 1024)
        log(f"Codebase backup completed successfully. Copied {copied_count} files. Total size: {total_size_mb:.2f} MB")
        return True
    except Exception as e:
        log(f"Failed to backup codebase: {e}")
        return False

def main():
    log("=== STARTING FULL SYSTEM BACKUP ===")
    
    # Create backup target folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(BACKUP_ROOT, f"Backup_{timestamp}")
    
    try:
        os.makedirs(backup_folder, exist_ok=True)
    except Exception as e:
        log(f"CRITICAL: Failed to create backup directory {backup_folder}: {e}")
        sys.exit(1)
        
    log(f"Backup Destination: {backup_folder}")
    
    # Prepare directories
    db_backup_dir = os.path.join(backup_folder, "database")
    docker_backup_dir = os.path.join(backup_folder, "docker")
    codebase_backup_dir = os.path.join(backup_folder, "codebase")
    
    os.makedirs(db_backup_dir, exist_ok=True)
    os.makedirs(docker_backup_dir, exist_ok=True)
    os.makedirs(codebase_backup_dir, exist_ok=True)
    
    db_backup_file = os.path.join(db_backup_dir, "osi_system_backup.sql")
    volumes_backup_file = os.path.join(docker_backup_dir, "docker_volumes_backup.tar.gz")
    
    # Step 1: Ensure Docker daemon is running
    docker_ok = check_wsl_docker_running()
    
    # Step 2: Backup DB if docker is running
    db_ok = False
    if docker_ok:
        if ensure_postgres_running():
            db_ok = perform_db_backup(db_backup_file)
        else:
            log("Skipping database dump because PostgreSQL container is not running.")
    else:
        log("Skipping database dump because Docker daemon is not running.")
        
    # Step 3: Backup Docker Volumes if docker daemon is running
    docker_vol_ok = False
    if docker_ok:
        docker_vol_ok = perform_docker_volumes_backup(volumes_backup_file)
    else:
        log("Skipping Docker volumes backup because Docker daemon is not running.")
        
    # Step 4: Backup codebase files
    codebase_ok = perform_codebase_backup(codebase_backup_dir)
    
    # Step 5: Write backup summary
    summary_path = os.path.join(backup_folder, "backup_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=== BACKUP SUMMARY ===\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Backup Folder: {backup_folder}\n\n")
        f.write(f"1. Database Backup: {'SUCCESS' if db_ok else 'FAILED/SKIPPED'}\n")
        if db_ok:
            f.write(f"   Database Dump File: {db_backup_file} ({os.path.getsize(db_backup_file)/(1024*1024):.2f} MB)\n")
        f.write(f"2. Docker Volumes Backup: {'SUCCESS' if docker_vol_ok else 'FAILED/SKIPPED'}\n")
        if docker_vol_ok:
            f.write(f"   Volumes Tarball: {volumes_backup_file} ({os.path.getsize(volumes_backup_file)/(1024*1024):.2f} MB)\n")
        f.write(f"3. Codebase Backup: {'SUCCESS' if codebase_ok else 'FAILED/SKIPPED'}\n")
        if codebase_ok:
            # calculate total files in codebase dir
            files_count = sum([len(files) for r, d, files in os.walk(codebase_backup_dir)])
            f.write(f"   Codebase Folder: {codebase_backup_dir} ({files_count} files)\n")
            
    log("=== BACKUP SUMMARY ===")
    log(f"Summary written to {summary_path}")
    log(f"Database: {'SUCCESS' if db_ok else 'FAILED/SKIPPED'}")
    log(f"Docker Volumes: {'SUCCESS' if docker_vol_ok else 'FAILED/SKIPPED'}")
    log(f"Codebase: {'SUCCESS' if codebase_ok else 'FAILED/SKIPPED'}")
    
    if db_ok and docker_vol_ok and codebase_ok:
        log("FULL SYSTEM BACKUP COMPLETED SUCCESSFULLY!")
    else:
        log("BACKUP COMPLETED WITH ERRORS/WARNINGS. Please review the logs.")

if __name__ == "__main__":
    main()
