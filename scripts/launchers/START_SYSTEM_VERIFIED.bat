@echo off
setlocal EnableExtensions DisableDelayedExpansion
title OSI AI NOC SYSTEM - STARTER
color 0B
:: Paksa working directory ke folder script, bukan Google Drive
cd /d "%~dp0"

echo ====================================================================
echo           OSI AI NOC INCIDENT ANALYSIS SYSTEM (HYBRID STACK)
echo ====================================================================
echo.
echo  [+] Menginisialisasi Jaringan dan Layanan Docker WSL 2...
echo.

:: ===========================================================
:: 1. Deteksi IP LAN (PowerShell - tanpa hardcode)
:: ===========================================================
echo  [+] Mendeteksi IP LAN aktif...
for /f "delims=" %%A in ('powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' -and $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*'} | Select-Object -ExpandProperty IPAddress -First 1); if([string]::IsNullOrEmpty($ip)){$ip='127.0.0.1'}; Write-Output $ip"') do set LAN_IP=%%A
if "%LAN_IP%"=="" set LAN_IP=127.0.0.1
echo  [OK] IP LAN Terdeteksi: %LAN_IP%
echo.

:: ===========================================================
:: 2. Start Docker di WSL Ubuntu
::    2>nul pada perintah wsl menekan warning "Failed to translate"
::    yang muncul karena terminal berasal dari Google Drive path
:: ===========================================================
echo  [+] Memulai Docker Daemon di WSL Ubuntu...

set WSL_OK=0
set WSL_RETRY=0

:WSL_RETRY_LOOP
wsl -d Ubuntu --cd /tmp -e sh -c "sudo systemctl start docker > /dev/null 2>&1; sleep 2; docker info > /dev/null 2>&1" 2>nul
if %errorlevel%==0 (
    set WSL_OK=1
    goto WSL_DONE
)
set /a WSL_RETRY+=1
if %WSL_RETRY% LSS 3 (
    echo  [!] Docker belum siap, retry %WSL_RETRY%/3 dalam 5 detik...
    ping 127.0.0.1 -n 6 >nul
    goto WSL_RETRY_LOOP
)

:WSL_DONE
if "%WSL_OK%"=="0" (
    color 0E
    echo  [WARNING] Docker Daemon tidak merespons. Lanjut mencoba docker compose...
    echo.
) else (
    echo  [OK] Docker Daemon WSL Ubuntu aktif.
    echo.
)

:: ===========================================================
:: 3. Docker Compose up
::    Catatan: docker compose output muncul di stdout WSL
::    2>nul menekan warning "Failed to translate" dari WSL stderr
:: ===========================================================
echo  [+] Meluncurkan Stack Server (Docker Compose)...
wsl -d Ubuntu --cd /tmp -e sh -c "cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS' && docker compose up -d 2>&1" 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  [ERROR] Gagal menjalankan docker compose up.
    echo  Cek manual: buka WSL Ubuntu lalu ketik:
    echo    cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS'
    echo    docker compose up -d
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker Compose stack diluncurkan.
echo.

:: ===========================================================
:: 4. Konfigurasi PortProxy
::    PENTING: Docker WSL2 ports diakses via 127.0.0.1 dari Windows
::    (WSL2 loopback mirroring) - BUKAN via WSL IP langsung
::    WSL IP (172.x.x.x) hanya untuk service di dalam WSL host,
::    bukan container Docker.
:: ===========================================================
echo  [+] Mengkonfigurasi PortProxy: LAN %LAN_IP% ^-^> localhost Docker...
powershell -NoProfile -Command "Start-Process cmd -Verb RunAs -Wait -ArgumentList '/c netsh interface portproxy reset 2>nul & netsh advfirewall firewall delete rule name=OSI-NOC-ALL 2>nul & netsh advfirewall firewall add rule name=OSI-NOC-ALL dir=in action=allow protocol=TCP localport=8099,9443,18800,9998,44600'" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' and CommandLine like '%%port_forward.py%%'\" | Invoke-CimMethod -MethodName Terminate" >nul 2>&1
start "OSI_NOC_PROXY" /B python.exe scripts\port_forward.py %LAN_IP%
echo  [OK] PortProxy diaktifkan di IP %LAN_IP%.
echo.

:: ===========================================================
:: 5. FTP Collector (native Windows)
:: ===========================================================
echo  [+] Memeriksa FTP Collector...
netstat -ano 2>nul | findstr ":18800 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo  [OK] FTP Collector sudah aktif di Port 18800
) else (
    if exist "%~dp0release_binaries\windows_amd64\agent_collector.exe" (
        start "FTP_COLLECTOR" /D "%~dp0" cmd /k "title FTP-COLLECTOR && release_binaries\windows_amd64\agent_collector.exe"
        echo  [OK] FTP Collector diluncurkan.
    ) else (
        echo  [SKIP] agent_collector.exe tidak ditemukan.
    )
)
echo.

:: ===========================================================
:: 6. Launcher Service (Port 44600)
:: ===========================================================
echo  [+] Memeriksa Launcher Service (Port 44600)...
netstat -ano 2>nul | findstr ":44600 " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo  [OK] Launcher Service sudah aktif di Port 44600
) else (
    if exist "%~dp0release_binaries\windows_amd64\launcher.exe" (
        start "LOCAL_LAUNCHER" /D "%~dp0release_binaries\windows_amd64" cmd /k "title LOCAL-LAUNCHER && launcher.exe"
        echo  [OK] Launcher Service diluncurkan.
    ) else (
        echo  [SKIP] launcher.exe tidak ditemukan.
    )
)
echo.

:: ===========================================================
:: 7. Tunggu container ready (12 detik)
:: ===========================================================
echo  [+] Menunggu container siap (12 detik)...
ping 127.0.0.1 -n 13 >nul
echo.

:: ===========================================================
:: 8. Verifikasi Port via TCP Connect (reliable, tanpa race condition)
::    Tidak pakai netstat karena portproxy tidak selalu muncul di netstat
::    TCP connect langsung uji apakah port bisa diakses
:: ===========================================================
echo ====================================================================
echo                 VERIFIKASI STATUS PORT OPERASIONAL
echo ====================================================================
echo.
set FAIL_COUNT=0

:: Fungsi cek TCP: PowerShell TcpClient dengan timeout 3 detik
powershell -NoProfile -Command "$ports=@(8099,9443,18800,9998); $labels=@('Nginx HTTP','Nginx HTTPS','Go Ingestion','Secure Relay'); $fail=0; for($i=0;$i -lt $ports.Count;$i++){$tcp=New-Object System.Net.Sockets.TcpClient; $r=$tcp.BeginConnect('127.0.0.1',$ports[$i],$null,$null); $ok=$r.AsyncWaitHandle.WaitOne(3000,$false); if($ok -and $tcp.Connected){Write-Host ' [OK] Port' $ports[$i] '-' $labels[$i]; $tcp.Close()}else{Write-Host ' [XX] Port' $ports[$i] '-' $labels[$i] 'MATI'; $fail++; $tcp.Close()}}; exit $fail"
set FAIL_COUNT=%ERRORLEVEL%

:: Cek launcher (opsional, tidak masuk FAIL_COUNT)
powershell -NoProfile -Command "$tcp=New-Object System.Net.Sockets.TcpClient; $r=$tcp.BeginConnect('127.0.0.1',44600,$null,$null); $ok=$r.AsyncWaitHandle.WaitOne(2000,$false); if($ok -and $tcp.Connected){Write-Host ' [OK] Port 44600 - Launcher Service'; $tcp.Close()}else{Write-Host ' [??] Port 44600 - Launcher Service (opsional)'; $tcp.Close()}" 2>nul

echo.

:: Cek dashboard actual response
echo  [+] Mengecek akses Dashboard via TCP...
powershell -NoProfile -Command "$tcp=New-Object System.Net.Sockets.TcpClient; $r=$tcp.BeginConnect('127.0.0.1',8099,$null,$null); $ok=$r.AsyncWaitHandle.WaitOne(3000,$false); if($ok -and $tcp.Connected){Write-Host ' [OK] Dashboard port 8099 - BISA DIAKSES'; $tcp.Close()}else{Write-Host ' [XX] Dashboard port 8099 - TIDAK BISA DIAKSES'}"
powershell -NoProfile -Command "$tcp=New-Object System.Net.Sockets.TcpClient; $r=$tcp.BeginConnect('127.0.0.1',9443,$null,$null); $ok=$r.AsyncWaitHandle.WaitOne(3000,$false); if($ok -and $tcp.Connected){Write-Host ' [OK] Dashboard port 9443 - BISA DIAKSES'; $tcp.Close()}else{Write-Host ' [XX] Dashboard port 9443 - TIDAK BISA DIAKSES'}"

echo.
echo  [INFO] DB Postgres dan Redis terisolasi (Zero-Trust - tidak expose langsung).
echo  [INFO] SSL warning di browser NORMAL - klik Advanced lalu Proceed.
echo.
echo --------------------------------------------------------------------

if %FAIL_COUNT%==0 (
    color 0A
    echo ====================================================================
    echo             SISTEM NOC BERHASIL DIJALANKAN!
    echo ====================================================================
    echo.
    echo   Akses Dashboard dari PC ini:
    echo   * http://localhost:8099           [HTTP - redirect ke HTTPS]
    echo   * https://localhost:9443          [HTTPS - klik Advanced, lalu Proceed]
    echo.
    echo   Akses Dashboard dari LAN [IP: %LAN_IP%]:
    echo   * http://%LAN_IP%:8099
    echo   * https://%LAN_IP%:9443
    echo.
    echo   Ingestion + Relay:
    echo   * TCP Ingestion  : %LAN_IP%:18800
    echo   * Launcher       : http://%LAN_IP%:44600/health
    echo ====================================================================
    echo.
    echo  [+] Membuka dashboard di browser...
    start "" "http://%LAN_IP%:8099"
) else (
    color 0E
    echo ====================================================================
    echo  [PERINGATAN] %FAIL_COUNT% port belum aktif.
    echo.
    echo  Troubleshoot:
    echo    1. Buka PowerShell dan jalankan:
    echo       wsl -d Ubuntu --cd /tmp -e docker ps
    echo    2. Cek log container:
    echo       wsl -d Ubuntu --cd /tmp -e docker logs osi-nginx
    echo       wsl -d Ubuntu --cd /tmp -e docker logs osi-dashboard-server
    echo    3. Restart stack jika perlu:
    echo       wsl -d Ubuntu --cd /tmp -e sh -c "cd '/mnt/d/AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS' && docker compose restart"
    echo ====================================================================
)

echo.
pause
endlocal
