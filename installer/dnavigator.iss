; Inno Setup script for DNAvigator (formerly GenomeWorkbench -- renamed for
; distinctiveness/searchability, see docs/DECISIONS.md).
; Builds a user-local installer (no admin rights required) from the
; PyInstaller onedir output at dist\DNAvigator.
;
; Build with: iscc installer\dnavigator.iss
; (requires Inno Setup 6, https://jrsoftware.org/isinfo.php - not bundled
; with this repository; install it separately before running iscc.)
;
; Compiled and verified on the development machine: silent install
; (/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LANG=english) placed the app
; under %LOCALAPPDATA%\Programs\DNAvigator with no admin prompt
; (PrivilegesRequired=lowest working as intended), --self-test/--smoke-test
; passed from the installed location, the Start Menu shortcut was created,
; and silent uninstall removed both cleanly. Also verified on GitHub Actions'
; clean windows-latest runner (windows-release.yml) — see docs/RELEASE_TEST_REPORT.md.
;
; Note: with two [Languages] entries registered, /VERYSILENT alone still
; shows the language-picker dialog and blocks; pass /LANG=english (or
; /LANG=korean) for unattended installs.

#define MyAppName "DNAvigator"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "DNAvigator Project"
#define MyAppExeName "DNAvigator.exe"
#define MyAppAssocExt ".gwbproj"

[Setup]
AppId={{4B71C72A-8BC3-45F6-9FB8-ABE84745354F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; User-local install: no admin privileges required (spec 22.3).
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=DNAvigator-{#MyAppVersion}-win-x64-setup
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
; Onedir PyInstaller output: everything under dist\DNAvigator\*
Source: "..\dist\DNAvigator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; File association only created if the user opts in (Tasks: fileassoc).
; Project file extension (.gwbproj) is unchanged from the GenomeWorkbench
; name -- it's internal plumbing invisible to the rename's actual goal
; (searchability of the app name), and changing it has no upside.
Root: HKCU; Subkey: "Software\Classes\{#MyAppAssocExt}"; ValueType: string; ValueName: ""; ValueData: "DNAvigatorProject"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\DNAvigatorProject"; ValueType: string; ValueName: ""; ValueData: "DNAvigator Project"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\DNAvigatorProject\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\DNAvigatorProject\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only remove what the installer itself placed under {app}. Never touch
; user project files (.gwbproj, anywhere on disk) or external BLAST
; databases (spec 18.1: uninstall must not delete user data).
