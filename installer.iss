; Inno Setup Script for MeshyDownloader
; Publisher: IamOumarIbrahim

[Setup]
AppName=MeshyDownloader
AppVersion=1.0
AppPublisher=IamOumarIbrahim
AppPublisherURL=https://github.com/IamOumarIbrahim
DefaultDirName={userappdata}\MeshyDownloader
DefaultGroupName=MeshyDownloader
OutputDir=.
OutputBaseFilename=MeshyDownloader_setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no

[Files]
Source: "MeshyDownloader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MeshyDownloader"; Filename: "{app}\MeshyDownloader.exe"
Name: "{userdesktop}\MeshyDownloader"; Filename: "{app}\MeshyDownloader.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\MeshyDownloader.exe"; Description: "Launch MeshyDownloader"; Flags: postinstall nowait postinstall skipifsilent
