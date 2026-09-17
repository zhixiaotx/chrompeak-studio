; Inno Setup script — produces an installer for the built executable.
; Compile with ISCC after running:  python desktop/build_desktop.py
[Setup]
AppName=ChromaPeak Studio
AppVersion=0.1.0
DefaultDirName={pf}\ChromaPeakStudio
DefaultGroupName=ChromaPeak Studio
OutputDir=installer
OutputBaseFilename=ChromaPeakStudio_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Files]
; dist layout produced by PyInstaller --onedir
Source: "dist\ChromaPeakStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ChromaPeak Studio"; Filename: "{app}\ChromaPeakStudio.exe"
Name: "{commondesktop}\ChromaPeak Studio"; Filename: "{app}\ChromaPeakStudio.exe"

[Run]
Filename: "{app}\ChromaPeakStudio.exe"; Description: "启动 ChromaPeak Studio"; Flags: nowait postinstall skipifsilent
