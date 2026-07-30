@echo off
title Installer OSI AI Agent - Windows Client
color 0A
echo ===================================================
echo   INSTALLER OSI AI AGENT - WINDOWS CLIENT
echo ===================================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    color 0C
    echo [ERROR] Perintah ini harus dijalankan sebagai Administrator!
    echo Silakan klik kanan pada INSTALL_AGENT.bat dan pilih 'Run as Administrator'.
    echo.
    pause
    exit /b 1
)

set DEFAULT_IP=10.20.0.154
echo ---------------------------------------------------
set /p TARGET_IP="Masukkan IP Server NOC [Default: %DEFAULT_IP%]: "
if "%TARGET_IP%"=="" set TARGET_IP=%DEFAULT_IP%
echo [INFO] IP Server Tujuan: %TARGET_IP%
echo ---------------------------------------------------
echo.

echo ---------------------------------------------------
set /p EXT_ID="Masukkan Chrome Extension ID (kosongkan jika belum ada): "
echo ---------------------------------------------------
echo.

echo [1/5] Menghentikan service & proses agen lama...
sc stop OSIAgent >nul 2>&1
taskkill /F /IM agent.exe >nul 2>&1
taskkill /F /IM agent_tray.exe >nul 2>&1
timeout /t 2 /nobreak >nul

set CONFIG_DIR=C:\ProgramData\Company\PC Health Agent\config
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
echo %TARGET_IP%> "%CONFIG_DIR%\server_ip.txt"

set OSI_AGENT_DIR=C:\ProgramData\OSI-Agent
if not exist "%OSI_AGENT_DIR%" mkdir "%OSI_AGENT_DIR%"
if not "%EXT_ID%"=="" (
    echo %EXT_ID%> "%OSI_AGENT_DIR%\ext_id.txt"
    echo [INFO] Extension ID disimpan: %EXT_ID%
) else (
    echo [INFO] Extension ID dilewati. Isi manual di: %OSI_AGENT_DIR%\ext_id.txt
)

set INSTALL_DIR=C:\Program Files\OSI-Agent
echo [2/5] Membuat direktori instalasi %INSTALL_DIR%...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [3/5] Menyalin file executable agen terbaru...
copy /Y "%~dp0agent.exe" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0agent_tray.exe" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0agent.ico" "%INSTALL_DIR%\" >nul
if exist "%~dp0updater.exe" copy /Y "%~dp0updater.exe" "%INSTALL_DIR%\" >nul

echo [4/5] Mendaftarkan Windows Service (OSIAgent)...
sc delete OSIAgent >nul 2>&1
sc create OSIAgent binPath= "\"%INSTALL_DIR%\agent.exe\"" start= auto DisplayName= "OSI AI Incident Analysis Agent"
sc description OSIAgent "Service pemantau otomatis & agen AI pendeteksi insiden sistem."
sc start OSIAgent

echo [5/5] Mengaktifkan System Tray App Autostart...
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "OSIAgentTray" /t REG_SZ /d "\"%INSTALL_DIR%\agent_tray.exe\"" /f >nul

start "" "%INSTALL_DIR%\agent_tray.exe"

echo.
echo ===================================================
echo [SUCCESS] Agen Windows OSI AI Berhasil Terinstall!
echo Terhubung ke IP Server: %TARGET_IP%
echo Status Service: Running (Auto-Start)
if not "%EXT_ID%"=="" (
    echo Extension ID: %EXT_ID% [TERDAFTAR]
    echo Browser Chrome/Edge akan otomatis instal ekstensi saat startup.
) else (
    echo Extension ID: [BELUM DIISI] - Isi di %OSI_AGENT_DIR%\ext_id.txt
)
echo ===================================================
pause
