<#
.SYNOPSIS
  skills-router 安装脚本（Windows PowerShell / PowerShell 7）

.DESCRIPTION
  从 GitHub Releases 下载 skills-router 发布包，安装到执行指令的目录（默认当前目录）。
  需要 Windows 10 1803+ / Windows 11（自带 tar.exe 与 curl.exe），或已安装 Git for Windows。

.PARAMETER Version
  要安装的版本 tag，如 "v1.2.3"。默认 "latest" 安装最新版。

.PARAMETER Destination
  安装目标目录，默认是执行脚本时所在的目录。

.PARAMETER Repo
  GitHub 仓库 "owner/repo"。默认读取环境变量 SKILLS_ROUTER_REPO；未设置时为 eavelabs-community/skills-router。

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Version v1.2.3
  .\install.ps1 -Destination D:\MyProject
  $env:SKILLS_ROUTER_REPO = "eavelabs-community/skills-router"; .\install.ps1
#>
param(
  [string]$Version = "latest",
  [string]$Destination = (Get-Location).Path,
  [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) { $Repo = $env:SKILLS_ROUTER_REPO }
if (-not $Repo) { $Repo = "eavelabs-community/skills-router" }
if ($env:SKILLS_ROUTER_VERSION) { $Version = $env:SKILLS_ROUTER_VERSION }
if ($env:SKILLS_ROUTER_DEST) { $Destination = $env:SKILLS_ROUTER_DEST }

$Asset = "skills-router.tar.gz"
if ($Version -match "^v[0-9]") {
  $Url = "https://github.com/$Repo/releases/download/$Version/$Asset"
} else {
  $Url = "https://github.com/$Repo/releases/latest/download/$Asset"
}

if (-not (Test-Path $Destination)) {
  Write-Error "destination directory does not exist: $Destination"
  exit 1
}
if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
  Write-Error "tar.exe not found. Requires Windows 10 1803+ / Windows 11, or Git for Windows."
  exit 1
}

Write-Host "==> Downloading skills-router ($Version)"
Write-Host "    $Url"

$TempDir = Join-Path $env:TEMP ("skills-router-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDir | Out-Null
$Archive = Join-Path $TempDir $Asset

try {
  if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    curl.exe -fsSL $Url -o $Archive
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Archive)) { throw "curl download failed" }
  } else {
    Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing
  }
} catch {
  Write-Error "download failed: $_"
  Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
  exit 1
}

Write-Host "==> Extracting..."
tar -xzf $Archive -C $TempDir

if (-not (Test-Path (Join-Path $TempDir ".skills-router"))) {
  Write-Error "archive does not contain .skills-router"
  Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
  exit 1
}

Write-Host "==> Installing to $Destination"
$Existing = Join-Path $Destination ".skills-router"
if (Test-Path $Existing) {
  Write-Host "    backing up existing .skills-router -> .skills-router.bak"
  $Backup = Join-Path $Destination ".skills-router.bak"
  Remove-Item $Backup -Recurse -Force -ErrorAction SilentlyContinue
  Move-Item $Existing $Backup
}
Copy-Item (Join-Path $TempDir ".skills-router") $Destination -Recurse -Force

$Readme = Join-Path $TempDir "README.md"
if (Test-Path $Readme) {
  Copy-Item $Readme (Join-Path $Destination "README.skills-router.md") -Force
}

Write-Host "==> Generating platform entries (init.py)"
Push-Location $Destination
try {
  if (Get-Command python -ErrorAction SilentlyContinue) {
    python .skills-router/init.py
  } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    python3 .skills-router/init.py
  } else {
    Write-Warning "python not found; run 'python .skills-router/init.py' manually after installing Python."
  }
} catch {
  Write-Warning "init.py failed: $_  (you can run it later: python .skills-router/init.py)"
} finally {
  Pop-Location
}

Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==> Done."
Write-Host "    skills-router installed at: $(Join-Path $Destination '.skills-router')"
Write-Host "    Next steps:"
Write-Host "      python .skills-router/scripts/skills_router.py refresh"
Write-Host "      python .skills-router/scripts/skills_router.py search `"markdown`""
