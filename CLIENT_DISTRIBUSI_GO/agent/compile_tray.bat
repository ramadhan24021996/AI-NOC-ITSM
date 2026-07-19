@echo off
echo ==================================================
echo  Compiling C# System Tray Application...
echo ==================================================
set CSC_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC_PATH%" (
    echo [ERROR] csc.exe not found at %CSC_PATH%
    exit /b 1
)
"%CSC_PATH%" /target:winexe /out:agent_tray.exe /win32icon:agent.ico /r:System.Web.Extensions.dll /r:System.Management.dll tray.cs ChatForm.cs
if %errorlevel% neq 0 (
    echo [ERROR] Compilation failed.
    exit /b %errorlevel%
)
echo [SUCCESS] Compiled agent_tray.exe successfully!
exit /b 0
