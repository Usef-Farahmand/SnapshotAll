[Setup]
AppName=SnapshotAll
AppVersion=1.0
AppPublisher=Usef Farahmand
DefaultDirName={autopf}\SnapshotAll
DefaultGroupName=SnapshotAll
OutputDir=Output
OutputBaseFilename=SnapshotAll_Setup
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
