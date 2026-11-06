; K78 RGB kurulum programı (Inno Setup 6/7)
; Derleme: build.ps1  (önce PyInstaller ile dist\K78RGB üretilir)

#define AppName "K78 RGB"
#define AppVersion "1.0.0"
#define AppExe "K78RGB.exe"
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
#define RunName "K78Isik"

[Setup]
AppId={{3FF9B63C-6E09-4D6C-9F5E-628C6F735E7C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=atorata
AppPublisherURL=https://github.com/atorata/thunderobot-k78-rgb-control
AppSupportURL=https://github.com/atorata/thunderobot-k78-rgb-control/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Yönetici izni gerekmez: kullanıcının kendi Programs klasörüne kurulur
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
InfoBeforeFile=before_install.txt
SetupIconFile=..\assets\k78.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir=..\release
OutputBaseFilename=K78RGB-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} kurulumu

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.AutoStart=Windows açılışında başlat (tepside)
english.AutoStart=Start with Windows (in the tray)
turkish.Launch=K78 RGB'yi başlat
english.Launch=Launch K78 RGB

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutoStart}"; Flags: unchecked

[Files]
Source: "..\dist\K78RGB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Uygulamanın kendi "Windows açılışında başlat" ayarıyla aynı değer
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunName}"; ValueData: """{app}\{#AppExe}"" --tray"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopK78RGB"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure StopRunningApp();
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM {#AppExe} /F', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Uygulama içinden açılmış olsa da otomatik başlatma kaydını temizle }
    RegDeleteValue(HKEY_CURRENT_USER, '{#RunKey}', '{#RunName}');
    { Kullanıcı profilleri (%APPDATA%\K78RGB) bilerek silinmez }
  end;
end;
