#define AppName "VideoManage"
#define AppVersion "0.1.0"
#define AppPublisher "ANVideoManage"
#define AppExeName "start_windows.bat"

[Setup]
AppId={{8A5F5AA7-E3D4-45F9-A1FA-1D3E0A6B5C92}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\release
OutputBaseFilename=VideoManageSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\zlm\MediaServer.exe

[Files]
Source: "..\release\installer-staging\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\backend\data"
Name: "{app}\zlm\www\record"
Name: "{app}\zlm\www\hls"
Name: "{app}\zlm\www\snap"

[Icons]
Name: "{autodesktop}\VideoManage"; Filename: "{cmd}"; Parameters: "/c ""{app}\start_windows.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\zlm\MediaServer.exe"
Name: "{group}\VideoManage"; Filename: "{cmd}"; Parameters: "/c ""{app}\start_windows.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\zlm\MediaServer.exe"
Name: "{group}\卸载 VideoManage"; Filename: "{uninstallexe}"

[Run]
Filename: "{cmd}"; Parameters: "/c ""{app}\start_windows.bat"""; WorkingDir: "{app}"; Description: "启动 VideoManage"; Flags: nowait postinstall skipifsilent
