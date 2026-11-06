# K78 RGB derleme: uygulama .exe'si (PyInstaller) + kurulum programı (Inno Setup)
# Kullanım:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# 1) Derleme ortamı (repoya girmez)
$py = Join-Path $root ".build-venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv .build-venv
    & $py -m pip install --quiet --upgrade pip
}
& $py -m pip install --quiet pyinstaller

# 2) Simge
if (-not (Test-Path "$root\assets\k78.ico")) { & $py "$root\tools\make_icon.py" }

# 3) Uygulama (.exe, onedir)
& $py -m PyInstaller --noconfirm --clean --windowed --onedir --name K78RGB `
    --icon "$root\assets\k78.ico" --version-file "$root\installer\version_info.txt" `
    --distpath "$root\dist" --workpath "$root\build" --specpath "$root\build" "$root\k78gui.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız" }

# 4) Kurulum programı
$iscc = @(
    "$env:USERPROFILE\tools\InnoSetup7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Warning "Inno Setup (ISCC.exe) bulunamadı; yalnızca dist\K78RGB üretildi. https://jrsoftware.org/isinfo.php"
    exit 0
}
& $iscc "$root\installer\k78rgb.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız" }
Get-ChildItem "$root\release\*.exe" | ForEach-Object {
    "{0}  {1:N1} MB  SHA256 {2}" -f $_.Name, ($_.Length / 1MB), (Get-FileHash $_.FullName -Algorithm SHA256).Hash
}
