; Instalador de Windows (Inno Setup 6). Lo compila desktop\build.ps1 si encuentra ISCC.exe.
; Instala por usuario (sin pedir permisos de administrador) y crea accesos directos.
; Los datos NO viven aquí sino en %LOCALAPPDATA%\MoneyTalk, así que desinstalar o
; actualizar no borra la información.

#define AppName "MoneyTalk"
#define AppVersion "0.1.0"

[Setup]
AppId={{6F0C2E52-3B7A-4C8F-9C3E-5D2A61B0A9E1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=MoneyTalk
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=MoneyTalk-Setup
SetupIconFile=moneytalk.ico
UninstallDisplayIcon={app}\MoneyTalk.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\MoneyTalk\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\MoneyTalk.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\MoneyTalk.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MoneyTalk.exe"; Description: "Abrir MoneyTalk"; Flags: nowait postinstall skipifsilent
