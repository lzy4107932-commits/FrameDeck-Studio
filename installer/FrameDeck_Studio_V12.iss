#define MyAppName "FrameDeck Studio"
#define MyAppVersion "12.0.0"
#define MyAppPublisher "紫东来"
#define MyAppExeName "FrameDeck Studio V12 Stable.exe"

[Setup]
AppId={{7E9BFE77-A128-4C84-98F9-3B052E2AA120}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FrameDeck Studio
DefaultGroupName=FrameDeck Studio
OutputDir=output
OutputBaseFilename=FrameDeck-Studio-v12.0.0-Windows-x64-Setup
SetupIconFile=..\resources\icon.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FrameDeck Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FrameDeck Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 FrameDeck Studio"; Flags: nowait postinstall skipifsilent
