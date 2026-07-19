; Inno Setup Script for OSI AI PC Health Agent
; Installs agent.exe (service), agent_tray.exe (tray), updater.exe and agent.ico.
; Prompts for Server IP and registers Windows Service with Recovery settings.

[Setup]
AppName=OSI AI Agent
AppVersion=2.0.0
AppPublisher=OSI AI Team
DefaultDirName={commonpf}\Company\PC Health Agent
DefaultGroupName=OSI AI Agent
DisableProgramGroupPage=yes
OutputDir=..\05_SIAP_DISTRIBUSI
OutputBaseFilename=PC_HEALTH_AGENT_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=..\agent\agent.ico
UninstallDisplayIcon={app}\agent_tray.exe

[Dirs]
Name: "{commonappdata}\Company\PC Health Agent"; Permissions: users-full
Name: "{commonappdata}\Company\PC Health Agent\config"; Permissions: users-full
Name: "{commonappdata}\Company\PC Health Agent\logs"; Permissions: users-full
Name: "{commonappdata}\Company\PC Health Agent\cache"; Permissions: users-full
Name: "{commonappdata}\Company\PC Health Agent\telemetry"; Permissions: users-full

[Files]
Source: "..\agent\agent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\agent\agent_tray.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\updater\updater.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\agent\agent.ico"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; Run the System Tray application automatically when users log in
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "OSIAgentTray"; ValueData: """{app}\agent_tray.exe"""; Flags: uninsdeletevalue

[Run]
; Stop and delete the service if it exists (for upgrade scenarios)
Filename: "{sys}\sc.exe"; Parameters: "stop ""OSI AI Agent"""; Flags: runhidden
Filename: "{sys}\sc.exe"; Parameters: "delete ""OSI AI Agent"""; Flags: runhidden
; Create the service (delayed automatic startup, LocalSystem account)
Filename: "{sys}\sc.exe"; Parameters: "create ""OSI AI Agent"" binPath= ""\""{app}\agent.exe\"""" start= delayed-auto displayName= ""OSI AI Incident Analysis Agent"""; Flags: runhidden
; Set service description
Filename: "{sys}\sc.exe"; Parameters: "description ""OSI AI Agent"" ""OSI AI Incident Analysis - PC Health Monitoring Agent"""; Flags: runhidden
; Set failure/recovery settings (restart after 30 seconds)
Filename: "{sys}\sc.exe"; Parameters: "failure ""OSI AI Agent"" reset= 86400 actions= restart/30000/restart/30000/restart/30000"; Flags: runhidden
; Windows Firewall rule for command server port 10000
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""OSI Agent Command Listener"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""OSI Agent Command Listener"" dir=in action=allow protocol=TCP localport=10000"; Flags: runhidden
; Start the service background runner
Filename: "{sys}\sc.exe"; Parameters: "start ""OSI AI Agent"""; Flags: runhidden
; Start the tray icon UI for the current session
Filename: "{app}\agent_tray.exe"; Flags: nowait postinstall runasoriginaluser; Description: "Start OSI Agent Tray Monitor"

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM agent_tray.exe /T"; Flags: runhidden; RunOnceId: KillTray
Filename: "{sys}\sc.exe"; Parameters: "stop ""OSI AI Agent"""; Flags: runhidden; RunOnceId: StopSvc
Filename: "{sys}\sc.exe"; Parameters: "delete ""OSI AI Agent"""; Flags: runhidden; RunOnceId: DeleteSvc
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""OSI Agent Command Listener"""; Flags: runhidden; RunOnceId: DeleteFW

[Code]
var
  ServerIPPage: TInputQueryWizardPage;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Terminate any running instances before setup
  Exec('taskkill.exe', '/F /IM agent.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM agent_tray.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure InitializeWizard;
begin
  ServerIPPage := CreateInputQueryPage(wpSelectDir,
    'Konfigurasi Server', 'Alamat IP Central Orchestrator',
    'Silakan masukkan alamat IP dari Central Orchestrator / Dashboard Server:');
  ServerIPPage.Add('IP Server:', False);
  ServerIPPage.Values[0] := '10.20.0.163';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: String;
  ServerIP: String;
  Lines: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{commonappdata}\Company\PC Health Agent\config');
    if WizardSilent and FileExists(ConfigPath + '\server_ip.txt') then
    begin
      // Preserve existing server_ip.txt if installer runs silently
    end
    else
    begin
      ServerIP := Trim(ServerIPPage.Values[0]);
      if ServerIP = '' then
        ServerIP := '10.20.0.163';
        
      ForceDirectories(ConfigPath);
      
      SetArrayLength(Lines, 1);
      Lines[0] := ServerIP;
      SaveStringsToFile(ConfigPath + '\server_ip.txt', Lines, False);
    end;
  end;
end;

procedure CurUninstallStepChanged(JustAfterAnUninstallStep: TUninstallStep);
begin
  if JustAfterAnUninstallStep = usPostUninstall then
  begin
    DelTree(ExpandConstant('{commonappdata}\Company\PC Health Agent'), True, True, True);
  end;
end;
