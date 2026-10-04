; SerialDesk Windows installer
; Built in CI with Inno Setup 6:  ISCC.exe /DMyVersion=0.6.0 installer\SerialDesk.iss
; Produces dist\SerialDesk_v<version>-win64-setup.exe from the PyInstaller onedir bundle.

#ifndef MyVersion
  #define MyVersion "0.0.0"
#endif

#define MyAppName "SerialDesk"
#define MyAppVersion MyVersion
#define MyAppExeName "SerialDesk_v" + MyVersion + ".exe"
#define SrcDir "..\dist\SerialDesk_v" + MyVersion

[Setup]
AppId={{8E4B4C8E-5B3A-4E5C-9C2E-SERIALDESK01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Qu 
AppPublisherURL=https://github.com/QuAndy2016/SerialDesk
AppSupportURL=https://github.com/QuAndy2016/SerialDesk/issues
DefaultDirName={autopf}\{#MyAppName}
; 2026-10-03: always offer the destination page - Inno's default (auto) hides it once the
; same AppId is installed, which is why the folder looked fixed on re-install.
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SerialDesk_v{#MyAppVersion}-win64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut / 创建桌面快捷方式"; GroupDescription: "Additional tasks / 附加任务:"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} / 运行 SerialDesk"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; user data (config.json / logs) lives in %APPDATA%\SerialDesk and is intentionally kept

[Code]
// 2026-10-03: pick the default log folder during setup and leave it beside the exe as
// logs_dir.txt; the app reads it when no per-user choice has been made yet.
var
  LogDirPage: TInputDirWizardPage;

procedure InitializeWizard();
begin
  LogDirPage := CreateInputDirPage(wpSelectTasks,
    'Default log folder',
    'Where should saved logs go by default?',
    'SerialDesk writes saved and auto-saved receive logs here. You can change it later in Settings.',
    False, '');
  LogDirPage.Add('Log folder:');
  LogDirPage.Values[0] := ExpandConstant('{userappdata}\SerialDesk\logs');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\logs_dir.txt'), LogDirPage.Values[0], False);
end;

// d: on uninstall, ask whether the per-user settings and logs should go too.
// They live in %APPDATA%\SerialDesk and are otherwise intentionally kept.
// (Note: inside [Code] only // and { } are comments; ';' is rejected by the Pascal compiler.)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Choice: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Choice := MsgBox('Also delete your settings and logs (config.json, logs)?'
                     + #13#10 + '同时删除配置与日志吗？',
                     mbConfirmation, MB_YESNO);
    if Choice = IDYES then
      DelTree(ExpandConstant('{userappdata}\SerialDesk'), True, True, True);
  end;
end;
