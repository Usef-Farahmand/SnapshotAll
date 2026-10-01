[Setup]
AppName=SnapshotAll
AppVersion=1.2.2
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
