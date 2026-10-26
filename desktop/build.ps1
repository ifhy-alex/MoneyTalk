# Construye la app de escritorio de Windows.
#   powershell -ExecutionPolicy Bypass -File desktop\build.ps1
# Resultado:
#   dist\MoneyTalk\MoneyTalk.exe        (la app, con su carpeta _internal)
#   dist\MoneyTalk-windows.zip          (para compartir: descomprimir y abrir MoneyTalk.exe)
#   dist\MoneyTalk-Setup.exe            (instalador, solo si Inno Setup 6 está instalado)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> Frontend"
Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci falló" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build falló" }
Pop-Location

Write-Host "==> Backend + PyInstaller"
Push-Location backend
uv sync --frozen --group desktop
if ($LASTEXITCODE -ne 0) { throw "uv sync falló" }
uv run --group desktop pyinstaller ..\desktop\MoneyTalk.spec --noconfirm --clean `
    --distpath ..\dist --workpath ..\build\pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }
Pop-Location

Write-Host "==> Zip"
$zip = Join-Path $root "dist\MoneyTalk-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "dist\MoneyTalk") -DestinationPath $zip

$iscc = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($iscc) {
    Write-Host "==> Instalador (Inno Setup)"
    & $iscc (Join-Path $root "desktop\installer.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló" }
} else {
    Write-Host "Inno Setup no está instalado: se omite el instalador (el zip funciona igual)."
}
Write-Host "Listo: $root\dist"
