#define AppName "VIBE CODE QA MASTER"
#define AppVersion "0.9.0-rc1"
#define AppExe "VibeQAMaster.exe"

[Setup]
AppId={{A8661186-8D1F-4E3E-9E3B-EBFD096A7073}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\VibeCodeQAMaster
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=VibeCodeQAMaster-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#AppExe}

[Files]
Source: "..\dist\VibeQAMaster\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 작업"

[Run]
Filename: "{app}\{#AppExe}"; Description: "설치 후 실행"; Flags: nowait postinstall skipifsilent

