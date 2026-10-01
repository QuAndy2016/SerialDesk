; SerialDesk Windows installer (U34)
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
AppPublisher=Qu Andy
AppPublisherURL=https://github.com/QuAndy2016/SerialDesk
AppSupportURL=https://github.com/QuAndy2016/SerialDesk/issues
DefaultDirName={autopf}\{#MyAppName}
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
; U163d: on uninstall, ask whether the per-user settings and logs should go too.
; They live in %APPDATA%\SerialDesk and are otherwise intentionally kept.
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
