; Inno Setup script (starter). Adjust paths if needed.
[Setup]
AppName=UI Bridge
AppVersion=1.0.0
DefaultDirName={pf}\UIBridge
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=UIBridge-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\UIBridge\UIBridge.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\UI Bridge"; Filename: "{app}\UIBridge.exe"
