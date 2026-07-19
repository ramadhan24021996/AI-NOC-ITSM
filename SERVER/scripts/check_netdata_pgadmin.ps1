# Diagnostic script for Netdata and PostgreSQL/pgAdmin (PowerShell)
# Usage: Run as Administrator/with sufficient privileges.

Write-Output "=== Check listening ports (19999 for Netdata, 5432 for Postgres) ==="
netstat -ano | Select-String ":19999|:5432" | ForEach-Object { $_.Line }

Write-Output "`n=== Test Netdata HTTP API ==="
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:19999/api/v1/version" -UseBasicParsing -TimeoutSec 5
    Write-Output "HTTP Status: $($resp.StatusCode)"
    Write-Output $resp.Content
} catch {
    Write-Output "Netdata API request failed: $_"
}

Write-Output "`n=== Check Netdata process/service ==="
try {
    Get-Service -Name netdata -ErrorAction SilentlyContinue | Format-List -Property Name,Status,DisplayName
} catch {}
Get-Process -Name netdata -ErrorAction SilentlyContinue | Format-Table Id,ProcessName,CPU,WS -AutoSize

Write-Output "`n=== Docker containers named netdata/pgadmin ==="
try { docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Ports}}" | Select-String -Pattern "netdata|pgadmin|postgres" } catch {}

Write-Output "`n=== Firewall (Windows) - list inbound rules (summary) ==="
try { Get-NetFirewallRule -Direction Inbound | Select-Object -First 30 | Format-Table Name,DisplayName,Enabled } catch {}

Write-Output "`n=== PostgreSQL local connection test (psql) ==="
try {
    psql --version > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        psql -h localhost -U postgres -p 5432 -c "\l" 2>&1 | ForEach-Object { $_ }
    } else { Write-Output "psql not found or not in PATH" }
} catch { Write-Output "psql test failed: $_" }

Write-Output "`n=== Collect common Postgres config file locations (first 200 lines if exist) ==="
$paths = @("C:\Program Files\PostgreSQL\*", "C:\ProgramData\postgresql\*", "/etc/postgresql/*/main/pg_hba.conf", "/var/lib/pgsql/data/pg_hba.conf")
foreach ($p in $paths) {
    try {
        Get-ChildItem -Path $p -ErrorAction Stop | Where-Object { $_.Name -match "pg_hba.conf|postgresql.conf" } | ForEach-Object {
            Write-Output "`n--- $($_.FullName) ---"
            Get-Content -Path $_.FullName -TotalCount 200 | ForEach-Object { $_ }
        }
    } catch {}
}

Write-Output "`n=== End of PowerShell diagnostic ==="
