@echo off
echo ===================================================
echo     OSI AI NOC - DEPLOYING NEW AGENT BINARIES
echo ===================================================
echo.
echo [+] Stopping Windows Service: OSI AI Agent...
net stop "OSI AI Agent"
echo.
echo [+] Killing running Tray Application...
taskkill /F /IM agent_tray.exe 2>nul
echo.
echo [+] Copying new agent.exe to Program Files...
copy /Y "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\CLIENT_DISTRIBUSI_GO\agent\agent.exe" "C:\Program Files\Company\PC Health Agent\agent.exe"
copy /Y "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\CLIENT_DISTRIBUSI_GO\agent\agent.exe" "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\release_binaries\windows_amd64\agent.exe"
echo.
echo [+] Copying new agent_tray.exe to Program Files...
copy /Y "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\CLIENT_DISTRIBUSI_GO\agent\agent_tray.exe" "C:\Program Files\Company\PC Health Agent\agent_tray.exe"
copy /Y "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\CLIENT_DISTRIBUSI_GO\agent\agent_tray.exe" "d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\release_binaries\windows_amd64\agent_tray.exe"
echo.
echo [+] Starting Windows Service: OSI AI Agent...
net start "OSI AI Agent"
echo.
echo [+] Launching new Tray Application...
start "" "C:\Program Files\Company\PC Health Agent\agent_tray.exe"
echo.
echo [SUCCESS] Binary deployment complete!
pause
