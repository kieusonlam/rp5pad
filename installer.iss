; RP5 Pad for Windows. Built by make_installer.py, which passes Version, DriverMsi and the output folder.
; Normal install: one UAC prompt, Program Files, the ViGEmBus driver if missing, a firewall rule for WiFi.
; With /CURRENTUSER: no admin, no driver, no firewall rule (used to test the installer on a machine that already has the driver).

[Setup]
AppId={{7B6E2C14-52A1-4E0B-9C3D-6A1F0E8D2B57}
AppName=RP5 Pad
AppVersion={#Version}
AppPublisher=kieusonlam
VersionInfoVersion={#Version}
DefaultDirName={autopf}\RP5 Pad
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=RP5Pad-Setup-{#Version}
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\RP5Pad.exe
UninstallDisplayName=RP5 Pad
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"

[Files]
Source: "build\pyi\dist\RP5Pad\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "{#DriverMsi}"; DestDir: "{tmp}"; DestName: "ViGEmBusSetup_x64.msi"; Flags: deleteafterinstall; Check: NeedDriver

[Icons]
Name: "{autoprograms}\RP5 Pad"; Filename: "{app}\RP5Pad.exe"
Name: "{autodesktop}\RP5 Pad"; Filename: "{app}\RP5Pad.exe"; Tasks: desktopicon

[Registry]
; Start with Windows is set from the tray menu; remove it with the app
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "RP5 Pad"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\ViGEmBusSetup_x64.msi"" /qb /norestart"; StatusMsg: "Installing the virtual controller driver (ViGEmBus)..."; Check: NeedDriver
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""RP5 Pad"""; Flags: runhidden; Check: IsAdminInstallMode
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""RP5 Pad"" dir=in action=allow program=""{app}\RP5Pad.exe"" enable=yes"; StatusMsg: "Allowing WiFi connections..."; Flags: runhidden; Check: IsAdminInstallMode
Filename: "{app}\RP5Pad.exe"; Description: "Start RP5 Pad"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/f /im RP5Pad.exe"; Flags: runhidden; RunOnceId: "StopApp"
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""RP5 Pad"""; Flags: runhidden; RunOnceId: "Firewall"; Check: IsAdminInstallMode

[Code]
function NeedDriver: Boolean;
begin
  Result := IsAdminInstallMode and not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ViGEmBus');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Exec('taskkill.exe', '/f /im RP5Pad.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);   { upgrading over a running copy }
  Result := '';
end;
