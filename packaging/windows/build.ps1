# Build a portable Windows folder: dist/WebDelta/ and dist/WebDelta-windows-x64.zip
# Run on Windows. Needs Node.js (frontend) and Python 3.12 on PATH (PyInstaller only).
# End users do not need either. Does not run on macOS/Linux.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Stage = Join-Path $RepoRoot "dist\WebDelta"
$PyVersion = "3.12.7"
$EmbedZip = "python-$PyVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PyVersion/$EmbedZip"

function Reset-NativeExit {
    $global:LASTEXITCODE = 0
}

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy $Source $Destination /E /NFL /NDL /NJH /NJS /XD __pycache__ .venv .git node_modules .next out /XF *.pyc .env .env.local
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed ($LASTEXITCODE): $Source -> $Destination"
    }
    Reset-NativeExit
}

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Нужна команда на машине сборки: $Name"
    }
}

Require-Command node
Require-Command npm
Require-Command python

Write-Host "Репозиторий: $RepoRoot"
if (Test-Path $Stage) {
    Remove-Item -Recurse -Force $Stage
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$Runtime = Join-Path $Stage "runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

$ZipPath = Join-Path $env:TEMP $EmbedZip
Write-Host "Скачиваю Python $PyVersion embeddable..."
Invoke-WebRequest -Uri $EmbedUrl -OutFile $ZipPath
Expand-Archive -Path $ZipPath -DestinationPath $Runtime -Force

$Pth = Get-ChildItem -Path $Runtime -Filter "python*._pth" | Select-Object -First 1
if (-not $Pth) {
    throw "python._pth не найден в $Runtime"
}
$PthLines = @(Get-Content $Pth.FullName | Where-Object { $_ -notmatch 'import site' })
$PthLines += @("Lib\site-packages", "import site")
Set-Content -Path $Pth.FullName -Value $PthLines -Encoding ascii

$GetPip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
$RuntimePython = Join-Path $Runtime "python.exe"
Write-Host "Ставлю pip и зависимости..."
& $RuntimePython $GetPip
if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed ($LASTEXITCODE)" }
& $RuntimePython -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed ($LASTEXITCODE)" }
& $RuntimePython -m pip install -r (Join-Path $RepoRoot "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "requirements install failed ($LASTEXITCODE)" }
& $RuntimePython -m pip install "setuptools>=68" wheel
if ($LASTEXITCODE -ne 0) { throw "setuptools install failed ($LASTEXITCODE)" }
& $RuntimePython -m pip install --no-build-isolation (Join-Path $RepoRoot "packages\filediff_llm")
if ($LASTEXITCODE -ne 0) { throw "filediff_llm install failed ($LASTEXITCODE)" }

$Browsers = Join-Path $Stage ".playwright-browsers"
New-Item -ItemType Directory -Force -Path $Browsers | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = $Browsers
Write-Host "Скачиваю Chromium для Playwright..."
& $RuntimePython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "playwright install failed ($LASTEXITCODE)" }

Write-Host "Собираю статику Next..."
Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed ($LASTEXITCODE)" }
    $env:WEBDELTA_STATIC_EXPORT = "1"
    $env:NEXT_PUBLIC_API_URL = "same-origin"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed ($LASTEXITCODE)" }
}
finally {
    Pop-Location
}

Copy-Tree (Join-Path $RepoRoot "backend") (Join-Path $Stage "backend")
Copy-Tree (Join-Path $RepoRoot "packages") (Join-Path $Stage "packages")
Copy-Tree (Join-Path $RepoRoot "frontend\out") (Join-Path $Stage "frontend\out")

$EnvExample = Join-Path $ScriptDir "portable.env.example"
Copy-Item $EnvExample (Join-Path $Stage ".env.example")
Copy-Item $EnvExample (Join-Path $Stage ".env")
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "results") | Out-Null

Write-Host "Собираю WebDelta.exe..."
& python -m pip install "pyinstaller==6.11.1"
if ($LASTEXITCODE -ne 0) { throw "pyinstaller install failed ($LASTEXITCODE)" }
$Work = Join-Path $RepoRoot "dist\pyinstaller-work"
$Spec = Join-Path $RepoRoot "dist\pyinstaller-spec"
& python -m PyInstaller --noconfirm --clean --onefile --console --name WebDelta `
    --distpath $Stage `
    --workpath $Work `
    --specpath $Spec `
    (Join-Path $ScriptDir "launcher.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

$ZipOut = Join-Path $RepoRoot "dist\WebDelta-windows-x64.zip"
if (Test-Path $ZipOut) {
    Remove-Item -Force $ZipOut
}
Write-Host "Упаковываю $ZipOut"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($Stage, $ZipOut)
Write-Host "Готово: $Stage"
Write-Host "Архив: $ZipOut"
