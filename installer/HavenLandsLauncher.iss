; Установщик Haven Lands Launcher (Inno Setup 6).
; Компиляция: build_win.bat делает это сам, либо вручную:
;   ISCC.exe /DMyAppVersion=1.0.0 installer\HavenLandsLauncher.iss
; Результат: dist\Haven-Lands-Launcher-Setup-<версия>.exe

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "Haven Lands Launcher"
#define MyAppPublisher "Haven Lands"
#define MyAppExeName "Haven Lands Launcher.exe"
#define BuildDir "..\dist\Haven Lands Launcher"

[Setup]
; AppId не менять никогда: по нему Windows понимает, что это обновление, а не новая программа
AppId={{BC7FECC5-7269-47DA-B6AD-F687702DAE2A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Без прав администратора: ставится для текущего пользователя, окно UAC не появляется.
; В начале установки можно выбрать «для всех пользователей».
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Haven-Lands-Launcher-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
WizardImageFile=..\assets\wizard_164.bmp,..\assets\wizard_246.bmp,..\assets\wizard_328.bmp
WizardSmallImageFile=..\assets\wizard_small_55.bmp,..\assets\wizard_small_83.bmp,..\assets\wizard_small_110.bmp
Compression=lzma2/ultra64
SolidCompression=yes
; Если лаунчер открыт при обновлении — установщик сам предложит его закрыть и запустит снова
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
