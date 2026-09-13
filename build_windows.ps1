<#
.SYNOPSIS
    Builds the portable "YT Downloader" release for Windows.

.DESCRIPTION
    Produces the final layout under Release\:

        Release\YT Downloader.exe              native outer launcher (.NET 4.8)
        Release\YT Downloader\YTDownloaderCore.exe  PyInstaller onedir core
        Release\YT Downloader\_internal\           Python payload
        Release\YT Downloader\bin\                 yt-dlp, ffmpeg, ffprobe, node
        Release\YT Downloader\assets\              icon + fonts

    Pipeline: run tests -> generate icon -> publish launcher -> PyInstaller
    core -> assemble resources next to the core exe -> validate the bundle
    (selftest exit code + bundled binaries) -> summary.

.PARAMETER SkipTests
    Skips the pytest run.

.PARAMETER BuildWork
    Keeps the intermediate PyInstaller dist\ directory instead of removing it.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$BuildWork
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = $PSScriptRoot
$IconScript = Join-Path $Root "build_assets\make_icon.py"
$SpecFile   = Join-Path $Root "ytdownloader.spec"
$LauncherProj = Join-Path $Root "build_assets\launcher\YTDownloader.Launcher.csproj"
$LaunchOut  = Join-Path $Root "build_assets\build\launcher"
$DistCore   = Join-Path $Root "dist\YTDownloaderCore"
$DistDir    = Join-Path $Root "dist"
$Release    = Join-Path $Root "Release"
$AppDir     = Join-Path $Release "YT Downloader"
$BinExes    = @("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe", "node.exe")

function Stop-LockedProcesses {
    param([string]$TargetDir)
    if (-not (Test-Path $TargetDir)) { return }
    $procs = Get-Process "YT Downloader", "YTDownloaderCore", "yt-dlp", "ffmpeg", "ffprobe", "node" -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        try {
            $pPath = $proc.Path
            if ($pPath -and $pPath.StartsWith($TargetDir, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Host "  Stopping process locking build folder: $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor Yellow
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # Ignore access errors for processes owned by other users
        }
    }
    Start-Sleep -Milliseconds 250
}

function Safe-RemoveDirectory {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Stop-LockedProcesses -TargetDir $Path
    for ($i = 1; $i -le 3; $i++) {
        try {
            Remove-Item $Path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($i -eq 3) {
                throw "Could not clean directory '$Path' (file is locked or in use by another process).`nError: $($_.Exception.Message)"
            }
            Write-Host "  Retrying directory cleanup ($i/3): $Path..." -ForegroundColor Yellow
            Start-Sleep -Milliseconds 600
            Stop-LockedProcesses -TargetDir $Path
        }
    }
}

function Check-Prerequisites {
    Write-Host "==> Checking build prerequisites..." -ForegroundColor Cyan

    # 1. dotnet CLI
    $dotnet = Get-Command "dotnet" -ErrorAction SilentlyContinue
    if (-not $dotnet) {
        throw "Prerequisite missing: .NET SDK ('dotnet' CLI) is required to build the launcher. Please install .NET SDK or Visual Studio Build Tools."
    }

    # 2. Python & packages
    $py = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Prerequisite missing: Python is not available in PATH."
    }

    & python -c "import PyInstaller, PIL, customtkinter" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Prerequisite missing: Required Python packages (PyInstaller, pillow, customtkinter) are not installed in the active environment."
    }

    # 3. Binaries under bin/
    foreach ($exe in $BinExes) {
        $p = Join-Path $Root "bin\$exe"
        if (-not (Test-Path $p)) {
            throw "Prerequisite missing: Bundled binary not found: $p`nPlease place yt-dlp.exe, ffmpeg.exe, ffprobe.exe, and node.exe in the bin/ directory before building."
        }
    }

    Write-Host "  [ok] .NET SDK available"
    Write-Host "  [ok] Python & build packages available"
    Write-Host "  [ok] All required binaries found in bin\"
}

function Invoke-Step {
    param([string]$Title, [scriptblock]$Body)
    Write-Host "`n==> $Title" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Body
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Step failed with exit code ${LASTEXITCODE}: $Title"
    }
}

# Stop any old running release instances before starting
Stop-LockedProcesses -TargetDir $Release

# Fast pre-flight check
Check-Prerequisites

if (-not $SkipTests) {
    Invoke-Step "Running tests" {
        python -m pytest $Root -q
    }
}

Invoke-Step "Generating application icon" {
    python $IconScript
}

Invoke-Step "Publishing native launcher (.NET 4.8 WinExe)" {
    dotnet publish $LauncherProj -c Release -o $LaunchOut
}

Invoke-Step "Building PyInstaller onedir core" {
    python -m PyInstaller --noconfirm --clean $SpecFile --distpath $DistDir --workpath (Join-Path $Root "build\pyinstaller")
}

Invoke-Step "Assembling Release layout" {
    Safe-RemoveDirectory -Path $Release
    New-Item -ItemType Directory -Force -Path $AppDir, "$AppDir\bin", "$AppDir\assets" | Out-Null

    Copy-Item (Join-Path $DistCore "YTDownloaderCore.exe") $AppDir
    Copy-Item (Join-Path $DistCore "_internal") "$AppDir\_internal" -Recurse -Force

    foreach ($exe in $BinExes) {
        Copy-Item (Join-Path $Root "bin\$exe") "$AppDir\bin\$exe"
    }
    if (Test-Path (Join-Path $Root "assets\fonts")) {
        Copy-Item (Join-Path $Root "assets\fonts") "$AppDir\assets\fonts" -Recurse -Force
    }

    $builtIcon = Join-Path $Root "build_assets\build\logo.ico"
    if (Test-Path $builtIcon) {
        Copy-Item $builtIcon "$AppDir\assets\logo.ico"
        Copy-Item $builtIcon (Join-Path $Root "assets\logo.ico") -Force
    }

    Copy-Item (Join-Path $LaunchOut "YT Downloader.exe") $Release
    if (Test-Path (Join-Path $LaunchOut "YT Downloader.exe.config")) {
        Copy-Item (Join-Path $LaunchOut "YT Downloader.exe.config") $Release
    }
}

Invoke-Step "Validating bundle" {
    $required = @(
        "$Release\YT Downloader.exe",
        "$AppDir\YTDownloaderCore.exe",
        "$AppDir\_internal\base_library.zip",
        "$AppDir\bin\yt-dlp.exe",
        "$AppDir\bin\ffmpeg.exe",
        "$AppDir\bin\ffprobe.exe",
        "$AppDir\bin\node.exe",
        "$AppDir\assets\logo.ico"
    )
    foreach ($f in $required) {
        if (-not (Test-Path $f)) { throw "Missing required file: $f" }
        Write-Host ("  [ok] {0} ({1:N0} KB)" -f (Split-Path $f -Leaf), ((Get-Item $f).Length / 1KB))
    }

    Write-Host "  Running packaged selftest through the launcher (arbitrary CWD)..." -NoNewline
    $validateDir = Join-Path $env:TEMP "ytdlp-desktop-validate"
    New-Item -ItemType Directory -Force -Path $validateDir | Out-Null
    Push-Location $validateDir
    $env:YTDLP_DESKTOP_SELFTEST = "1"
    try {
        $p = Start-Process -FilePath "$Release\YT Downloader.exe" -PassThru -Wait
        if ($p.ExitCode -ne 0) { throw "Selftest exit code was $($p.ExitCode)" }
        Write-Host " exit=$($p.ExitCode)"
    }
    finally {
        Remove-Item Env:YTDLP_DESKTOP_SELFTEST -ErrorAction SilentlyContinue
        Pop-Location
        Stop-LockedProcesses -TargetDir $Release
    }

    Write-Host "  Binaries from the packaged bin\:" 
    & "$AppDir\bin\yt-dlp.exe" --version
    (& "$AppDir\bin\ffmpeg.exe" -version 2>&1) | Select-Object -First 1
}

if (-not $BuildWork) {
    Write-Host "`n==> Cleaning intermediate build artifacts" -ForegroundColor Cyan
    Remove-Item $DistDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Release ready:" -ForegroundColor Green
Write-Host "  $Release" -ForegroundColor Green
Write-Host "  Run the app from:  $Release\YT Downloader.exe" -ForegroundColor Green