; Installer script for Inno Setup 6 (free): https://jrsoftware.org/isinfo.php
; Build: first run build_exe.bat (it also updates app_version.iss from version.py),
; then open this file in Inno Setup and press Compile (F9).
; Result: installer\Output\DotaBetTracker-Setup-<version>.exe
; Installs per-user (no admin rights needed) so in-app updates can replace files.
; User data lives in %APPDATA%\DotaBets and is NEVER touched by install, update or uninstall.
#define AppName "Dota Bet Tracker"
; Version comes from version.py: build_exe.bat writes it into app_version.iss automatically.
#include "app_version.iss"
#define ExeName "DotaBetTracker.exe"

[Setup]
AppId={{B7C1E0A4-5D2F-4C61-9E3B-0A7D3B1F6C42}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\DotaBetTracker
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=DotaBetTracker-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "..\dist\DotaBetTracker\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
