[Setup]
AppId={{E94D6ACA-7E33-4A4B-83FA-1AB5FD406FB9}
AppName=Proxmark3 Engineering Suite
AppVersion=0.6b
AppPublisher=Justin
AppPublisherURL=https://github.com/Anon0ne/Proxmark3-Easy-GUI-by-Justin
DefaultDirName={localappdata}\Programs\Proxmark3EasyGUI
DefaultGroupName=Proxmark3 Engineering Suite
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=Proxmark3-Easy-GUI-0.6b-Setup
SetupIconFile=assets\app-icon.ico
UninstallDisplayIcon={app}\Proxmark3Suite.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=INSTALLATION.txt

[Files]
Source: "dist-0.6b\Proxmark3Suite.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALLATION.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\Proxmark3 Engineering Suite"; Filename: "{app}\Proxmark3Suite.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Proxmark3Suite.exe"
Name: "{group}\Proxmark3 Engineering Suite"; Filename: "{app}\Proxmark3Suite.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Proxmark3Suite.exe"; Description: "Open Proxmark3 Engineering Suite"; Flags: nowait postinstall skipifsilent
