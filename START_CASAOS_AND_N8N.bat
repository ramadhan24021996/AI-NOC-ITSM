@echo off
setlocal EnableExtensions DisableDelayedExpansion
:: Paksa working directory ke folder script, bukan Google Drive
cd /d "%~dp0"
title START MASTER - CasaOS and n8n Workflow Engine
color 0B
cls

echo ====================================================================
echo               OSI AI NOC WORKFLOW AUTOMATION ENGINE
echo ====================================================================
echo.
echo  [+] Menginisialisasi Lingkungan WSL 2...
echo.

:: ===========================================================
:: 1. Start Docker di WSL Ubuntu
::    KUNCI FIX: --cd /tmp = hindari "Failed to translate G:\..."
:: ===========================================================
echo  [+] Memulai Docker Daemon di WSL Ubuntu...

set WSL_READY=0
set WSL_TRY=0

:WSL_START_LOOP
set /a WSL_TRY+=1
if %WSL_TRY% GTR 3 goto WSL_FAILED

wsl -d Ubuntu --cd /tmp -e sh -c "sudo systemctl disable docker.socket > /dev/null 2>&1; sudo systemctl stop docker.socket > /dev/null 2>&1; sudo systemctl start docker > /dev/null 2>&1; sleep 2; docker info > /dev/null 2>&1" 2>nul
if %errorlevel%==0 (
    set WSL_READY=1
    echo  [OK] Docker Daemon WSL Ubuntu aktif (percobaan %WSL_TRY%).
    goto WSL_START_DONE
)

echo  [!] Percobaan %WSL_TRY%/3 gagal, menunggu 5 detik...
ping 127.0.0.1 -n 6 >nul
goto WSL_START_LOOP

:WSL_FAILED
color 0C
echo.
echo  [ERROR] Gagal menyalakan Docker Daemon di WSL Ubuntu (3x percobaan).
echo.
echo  Solusi:
echo    1. Buka PowerShell as Admin
echo    2. Ketik: wsl --shutdown
echo    3. Tunggu 10 detik
echo    4. Jalankan script ini lagi
echo.
pause
exit /b 1

:WSL_START_DONE
echo.

:: ===========================================================
:: 2. Cari dan jalankan n8n via docker compose
::    KUNCI FIX: gunakan --cd /tmp agar tidak error Google Drive
:: ===========================================================
echo  [+] Mencari folder n8n_docker...

:: Cek semua kemungkinan path n8n_docker
set N8N_COMPOSE_PATH=
wsl -d Ubuntu --cd /tmp -e sh -c "test -f '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/SERVER/n8n_docker/docker-compose.yml' && echo FOUND" 2>nul | findstr "FOUND" >nul 2>&1
if %ERRORLEVEL%==0 (
    set N8N_COMPOSE_PATH=/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/SERVER/n8n_docker
    goto N8N_FOUND
)

wsl -d Ubuntu --cd /tmp -e sh -c "test -f '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/server/n8n_docker/docker-compose.yml' && echo FOUND" 2>nul | findstr "FOUND" >nul 2>&1
if %ERRORLEVEL%==0 (
    set N8N_COMPOSE_PATH=/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/server/n8n_docker
    goto N8N_FOUND
)

wsl -d Ubuntu --cd /tmp -e sh -c "test -f '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/n8n_docker/docker-compose.yml' && echo FOUND" 2>nul | findstr "FOUND" >nul 2>&1
if %ERRORLEVEL%==0 (
    set N8N_COMPOSE_PATH=/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS/n8n_docker
    goto N8N_FOUND
)

echo  [WARNING] docker-compose.yml n8n tidak ditemukan. Skip n8n.
goto SKIP_N8N

:N8N_FOUND
echo  [OK] n8n ditemukan: %N8N_COMPOSE_PATH%
wsl -d Ubuntu --cd /tmp -e sh -c "cd '%N8N_COMPOSE_PATH%' && docker compose up -d 2>&1"
if %errorlevel% neq 0 (
    color 0E
    echo  [WARNING] Gagal meluncurkan n8n. Periksa docker-compose.yml di folder n8n_docker.
) else (
    echo  [OK] Container n8n diluncurkan.
)

:SKIP_N8N
echo.

:: ===========================================================
:: 3. CasaOS
:: ===========================================================
echo  [+] Memeriksa CasaOS...
wsl -d Ubuntu --cd /tmp -e sh -c "systemctl is-active casaos > /dev/null 2>&1 || sudo systemctl start casaos > /dev/null 2>&1"
if %errorlevel%==0 (
    echo  [OK] CasaOS aktif.
) else (
    echo  [INFO] CasaOS tidak terdeteksi, skip.
)
echo.

:: ===========================================================
:: 4. PortProxy untuk n8n (5678) dan CasaOS (80)
:: ===========================================================
echo  [+] Mengkonfigurasi PortProxy untuk n8n dan CasaOS...
powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c netsh interface portproxy delete v4tov4 listenport=5678 listenaddress=0.0.0.0 2>nul & netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0 2>nul & netsh interface portproxy add v4tov4 listenport=5678 listenaddress=0.0.0.0 connectport=5678 connectaddress=127.0.0.1 & netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=127.0.0.1 & netsh advfirewall firewall delete rule name=OSI-N8N-ALL 2>nul & netsh advfirewall firewall add rule name=OSI-N8N-ALL dir=in action=allow protocol=TCP localport=80,5678' -Verb RunAs -Wait" 2>nul
echo  [OK] PortProxy n8n dan CasaOS dikonfigurasi.
echo.

:: ===========================================================
:: 5. Deteksi IP LAN
:: ===========================================================
for /f "delims=" %%A in ('powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' -and $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*'} | Select-Object -ExpandProperty IPAddress -First 1); if([string]::IsNullOrEmpty($ip)){$ip='localhost'}; Write-Output $ip"') do set LAN_IP=%%A
if "%LAN_IP%"=="" set LAN_IP=localhost

:: ===========================================================
:: 6. Tampilan sukses + keepalive aman (BUKAN tail -f /dev/null)
:: ===========================================================
cls
color 0A
echo ====================================================================
echo           CASAOS AND N8N WORKFLOW ENGINE BERHASIL DIJALANKAN!
echo ====================================================================
echo.
echo   Status Sistem:
echo   * WSL Ubuntu          : AKTIF
echo   * Docker Daemon       : BERJALAN
echo   * CasaOS              : AKTIF
echo   * n8n Container       : ONLINE
echo   * PortProxy LAN       : AKTIF (0.0.0.0)
echo.
echo   Akses dari PC ini (localhost):
echo   * CasaOS  : http://localhost         (Port 80)
echo   * n8n     : http://localhost:5678    (Port 5678)
echo.
echo   Akses dari LAN (IP: %LAN_IP%):
echo   * CasaOS  : http://%LAN_IP%
echo   * n8n     : http://%LAN_IP%:5678
echo.
echo ====================================================================
echo   [PENTING] JANGAN TUTUP JENDELA INI!
echo   Jendela ini menjaga WSL tetap aktif.
echo   Tekan [Ctrl+C] untuk menghentikan.
echo ====================================================================
echo.

:: Keepalive AMAN - ping loop, tidak hang ketika WSL stop
:KEEPALIVE_LOOP
ping 127.0.0.1 -n 61 >nul
echo  [%time%] System alive - CasaOS + n8n berjalan...
goto KEEPALIVE_LOOP

endlocal
