; Inno Setup script for GenomeWorkbench.
; Builds a user-local installer (no admin rights required) from the
; PyInstaller onedir output at dist\GenomeWorkbench.
;
; Build with: iscc installer\genome_workbench.iss
; (requires Inno Setup 6, https://jrsoftware.org/isinfo.php - not bundled
; with this repository; install it separately before running iscc.)
;
; Compiled and verified on the development machine: silent install
; (/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LANG=english) placed the app
; under %LOCALAPPDATA%\Programs\GenomeWorkbench with no admin prompt
; (PrivilegesRequired=lowest working as intended), --self-test/--smoke-test
; passed from the installed location, the Start Menu shortcut was created,
; and silent uninstall removed both cleanly. Not yet verified on a fully
; separate clean Windows user account/VM — see docs/RELEASE_TEST_REPORT.md.
;
; Note: with two [Languages] entries registered, /VERYSILENT alone still
; shows the language-picker dialog and blocks; pass /LANG=english (or
; /LANG=korean) for unattended installs.

#define MyAppName "GenomeWorkbench"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "GenomeWorkbench Project"
#define MyAppExeName "GenomeWorkbench.exe"
#define MyAppAssocExt ".gwbproj"

[Setup]
AppId={{B6C1B9C1-5B7E-4B7A-9B4E-1D6A9B7B5C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; User-local install: no admin privileges required (spec 22.3).
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=GenomeWorkbench-{#MyAppVersion}-win-x64-setup
OutputDir=..\release
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; No code-signing certificate is available (docs/LICENSING.md) — this build
; is unsigned. Windows Defender/SmartScreen may warn; document this for
; users rather than pretend otherwise (docs/PRODUCT_SPEC.md 22.3).

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate .gwbproj project files with {#MyAppName}"; GroupDescription: "File associations:"

[Files]
; Onedir PyInstaller output: everything under dist\GenomeWorkbench\*
Source: "..\dist\GenomeWorkbench\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; File association only created if the user opts in (Tasks: fileassoc).
Root: HKCU; Subkey: "Software\Classes\{#MyAppAssocExt}"; ValueType: string; ValueName: ""; ValueData: "GenomeWorkbenchProject"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\GenomeWorkbenchProject"; ValueType: string; ValueName: ""; ValueData: "GenomeWorkbench Project"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\GenomeWorkbenchProject\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\GenomeWorkbenchProject\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only remove what the installer itself placed under {app}. Never touch
; user project files (.gwbproj, anywhere on disk) or external BLAST
; databases (spec 18.1: uninstall must not delete user data).
