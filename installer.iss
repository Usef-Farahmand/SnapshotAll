; The version is passed in at build time:  ISCC /DMyAppVersion=1.4.37 installer.iss
; (tools/set_version.py decides it, so the installer matches the app header and the release name).
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-unversioned"
#endif

[Setup]
AppName=SnapshotAll
AppVersion={#MyAppVersion}
AppVerName=SnapshotAll {#MyAppVersion}
AppPublisher=Usef Farahmand
AppPublisherURL=https://www.useffarahmand.com/
AppSupportURL=https://github.com/Usef-Farahmand/SnapshotAll/issues
DefaultDirName={autopf}\SnapshotAll
DefaultGroupName=SnapshotAll
OutputDir=Output
OutputBaseFilename=SnapshotAll_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\SnapshotAll.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "dist\SnapshotAll\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SnapshotAll"; Filename: "{app}\SnapshotAll.exe"
Name: "{autodesktop}\SnapshotAll"; Filename: "{app}\SnapshotAll.exe"

[Run]
Filename: "{app}\SnapshotAll.exe"; Description: "Launch SnapshotAll"; Flags: nowait postinstall skipifsilent
