# Dev setup on a new Windows machine: .venv with the project's packages (no admin rights needed).
#   powershell -ExecutionPolicy Bypass -File tools\setup_dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = $null
foreach ($c in @("py -3.10", "py -3", "python")) {
    try { $v = & cmd /c "$c --version" 2>$null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch {}
}
if (-not $py) { Write-Host "Python 3.10+ not found: install it from python.org (per-user, 64-bit), then run this again."; exit 1 }
Write-Host "Python: $py"
if (-not (Test-Path ".venv")) { & cmd /c "$py -m venv .venv" }
& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\python -m pip install -r requirements.txt
& .\.venv\Scripts\python -c "import psutil, PIL, numpy; print('ok: psutil, pillow, numpy')"
Write-Host "Done. Run the launcher from source: .venv\Scripts\python launcher\main.py"
