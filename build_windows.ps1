<#
.SYNOPSIS
    Builds the portable "YT Downloader" release for Windows.

.DESCRIPTION
    Freezes app.py straight into the release executable with PyInstaller -- there
    is no outer launcher and no .NET step. The final layout under Release\ is:

        Release\YT Downloader.exe     PyInstaller onedir executable (app.py)
        Release\_internal\            frozen Python run-time, libraries, base_library.zip
        Release\bin\                  yt-dlp, ffmpeg, ffprobe, node
        Release\assets\               icon + fonts

    bin\ and assets\ deliberately stay *beside* the executable instead of inside
    _internal\, because utils.paths.app_root() resolves them from the executable's
    own directory. That keeps the folder relocatable as a unit.

    Pipeline: stop locked processes -> prerequisites -> tests -> icon ->
    PyInstaller -> assemble Release\ -> validate layout -> packaged self-test
    from an arbitrary CWD -> bundled binary smoke tests -> summary.

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
$DistDir    = Join-Path $Root "dist"
$StageDir   = Join-Path $DistDir "YT Downloader"
$WorkDir    = Join-Path $Root "build\pyinstaller"
$Release    = Join-Path $Root "Release"
$AppExe     = Join-Path $Release "YT Downloader.exe"
$IconFile   = Join-Path $Root "build_assets\build\logo.ico"
$BinExes    = @("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe", "node.exe")

# Directory names that must end up as siblings of the executable, not inside
# _internal\ -- utils.paths resolves bin/ and assets/ from app_root().
$ResourceDirs = @("bin", "assets")
$Forbidden    = @("YT Downloader", "YTDownloaderCore.exe", "YT Downloader.exe.config")

function Stop-LockedProcesses {
    param([string]$TargetDir)
    if (-not (Test-Path $TargetDir)) { return }
    $procs = Get-Process "YT Downloader", "yt-dlp", "ffmpeg", "ffprobe", "node" -ErrorAction SilentlyContinue
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
            try {
                Get-ChildItem -LiteralPath $Path -Force | Remove-Item -Recurse -Force -ErrorAction Stop
                return
            } catch {
                # Fall through to retry
            }
            if ($i -eq 3) {
                throw "Could not clean directory '$Path' (file is locked or in use by another process).`nError: $($_.Exception.Message)"
            }
            Write-Host "  Retrying directory cleanup ($i/3): $Path..." -ForegroundColor Yellow
            Start-Sleep -Milliseconds 600
            Stop-LockedProcesses -TargetDir $Path
        }
    }
}

function Assert-Exists {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Package validation failed: $Label is missing -> $Path"
    }
}

function Check-Prerequisites {
    Write-Host "==> Checking build prerequisites..." -ForegroundColor Cyan

    $py = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Prerequisite missing: Python is not available in PATH."
    }

    & python -c "import PyInstaller, PIL, customtkinter" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Prerequisite missing: Required Python packages (PyInstaller, pillow, customtkinter) are not installed in the active environment."
    }

    foreach ($exe in $BinExes) {
        $p = Join-Path $Root "bin\$exe"
        if (-not (Test-Path -LiteralPath $p)) {
            throw "Prerequisite missing: Bundled binary not found: $p`nPlease place yt-dlp.exe, ffmpeg.exe, ffprobe.exe, and node.exe in the bin/ directory before building."
        }
    }

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

function Copy-FrozenBundle {
    # PyInstaller writes dist\YT Downloader\{YT Downloader.exe,_internal\}.
    # Flatten one level up so Release\ is the bundle root and no nested
    # "YT Downloader" application directory survives the assembly.
    Get-ChildItem -LiteralPath $StageDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Release -Recurse -Force
    }
}

function Copy-ApplicationResources {
    # bin/ and assets/ stay beside the executable, never inside _internal.
    $binTarget = Join-Path $Release "bin"
    $assetsTarget = Join-Path $Release "assets"
    New-Item -ItemType Directory -Force -Path $binTarget, $assetsTarget | Out-Null

    foreach ($exe in $BinExes) {
        Copy-Item -LiteralPath (Join-Path $Root "bin\$exe") -Destination (Join-Path $binTarget $exe) -Force
    }

    $fonts = Join-Path $Root "assets\fonts"
    if (Test-Path -LiteralPath $fonts) {
        Copy-Item -LiteralPath $fonts -Destination (Join-Path $assetsTarget "fonts") -Recurse -Force
    }

    Assert-Exists -Path $IconFile -Label "generated application icon"
    Copy-Item -LiteralPath $IconFile -Destination (Join-Path $assetsTarget "logo.ico") -Force
}

function Assert-RequiredPackageFiles {
    Assert-Exists -Path $AppExe -Label "application executable"
    Assert-Exists -Path (Join-Path $Release "_internal") -Label "frozen Python runtime"
    Assert-Exists -Path (Join-Path $Release "_internal\base_library.zip") -Label "frozen base_library.zip"
    Assert-Exists -Path (Join-Path $Release "assets\logo.ico") -Label "application icon"

    foreach ($exe in $BinExes) {
        Assert-Exists -Path (Join-Path $Release "bin\$exe") -Label "bundled binary bin\$exe"
    }
}

function Assert-ResourceDirsBesideExecutable {
    # bin/, assets/ and _internal/ must be siblings of the executable: that is
    # exactly what app_root() resolves when the frozen app starts.
    $releaseRoot = (Resolve-Path -LiteralPath $Release).Path
    foreach ($dir in ($ResourceDirs + "_internal")) {
        $resolved = (Resolve-Path -LiteralPath (Join-Path $Release $dir)).Path
        if ((Split-Path $resolved -Parent) -ne $releaseRoot) {
            throw "Package validation failed: '$dir' is not a sibling of the executable -> $resolved"
        }
    }
}

function Assert-NoLauncherArtifacts {
    foreach ($stale in $Forbidden) {
        $stalePath = Join-Path $Release $stale
        if (Test-Path -LiteralPath $stalePath) {
            throw "Package validation failed: obsolete launcher artifact present -> $stalePath"
        }
    }

    $topLevelExes = @(Get-ChildItem -LiteralPath $Release -Filter "*.exe" -File)
    if ($topLevelExes.Count -ne 1 -or $topLevelExes[0].Name -ne "YT Downloader.exe") {
        $found = ($topLevelExes | ForEach-Object { $_.Name }) -join ", "
        throw "Package validation failed: Release\ must hold exactly one executable ('YT Downloader.exe'), found: $found"
    }
}

function Invoke-PackagedSelfTest {
    # The frozen app resolves bin/ and assets/ from its own directory, so run it
    # from an unrelated CWD to prove nothing depends on the working directory.
    $selftestDir = Join-Path ([System.IO.Path]::GetTempPath()) "ytdlp-desktop-selftest"
    if (-not (Test-Path -LiteralPath $selftestDir)) {
        New-Item -ItemType Directory -Force -Path $selftestDir | Out-Null
    }

    Write-Host "  CWD: $selftestDir" -NoNewline
    Push-Location $selftestDir
    $env:YTDLP_DESKTOP_SELFTEST = "1"
    try {
        $proc = Start-Process -FilePath $AppExe -PassThru -Wait
        $code = $proc.ExitCode
        if ($code -ne 0) {
            throw "Packaged self-test failed: '$AppExe' exited with code $code"
        }
    } finally {
        Remove-Item Env:YTDLP_DESKTOP_SELFTEST -ErrorAction SilentlyContinue
        Pop-Location
        Stop-LockedProcesses -TargetDir $Release
    }
    Write-Host " selftest exit=$code [ok]"
}

function Assert-BundledBinariesRun {
    # Exercise the *packaged* copies, never the source tree.
    $ytDlp = Join-Path $Release "bin\yt-dlp.exe"
    $ytDlpVersion = & $ytDlp --version
    $ytDlpCode = $LASTEXITCODE
    Write-Host "  yt-dlp: $ytDlpVersion"
    if ($ytDlpCode -ne 0) {
        throw "Packaged yt-dlp.exe --version failed with exit code $ytDlpCode"
    }

    $ffmpeg = Join-Path $Release "bin\ffmpeg.exe"
    $ffmpegBanner = & $ffmpeg -version 2>&1
    $ffmpegCode = $LASTEXITCODE
    Write-Host "  ffmpeg: $($ffmpegBanner | Select-Object -First 1)"
    if ($ffmpegCode -ne 0) {
        throw "Packaged ffmpeg.exe -version failed with exit code $ffmpegCode"
    }
}

# Stop any old running release instances before starting
Stop-LockedProcesses -TargetDir $Release

Check-Prerequisites

if (-not $SkipTests) {
    Invoke-Step "Running tests" {
        python -m pytest $Root -q
    }
}

Invoke-Step "Generating application icon" {
    python $IconScript
}

Invoke-Step "Building PyInstaller onedir application" {
    Safe-RemoveDirectory -Path $DistDir
    python -m PyInstaller --noconfirm --clean $SpecFile --distpath $DistDir --workpath $WorkDir
}

Invoke-Step "Assembling Release layout" {
    if (-not (Test-Path -LiteralPath $StageDir)) {
        throw "PyInstaller did not produce the expected onedir bundle: $StageDir"
    }
    Safe-RemoveDirectory -Path $Release
    New-Item -ItemType Directory -Force -Path $Release | Out-Null
    Copy-FrozenBundle
    Copy-ApplicationResources
}

Invoke-Step "Validating package layout" {
    Assert-RequiredPackageFiles
    Assert-ResourceDirsBesideExecutable
    Assert-NoLauncherArtifacts
    Write-Host "  [ok] $AppExe"
    Write-Host "  [ok] $Release\bin (yt-dlp, ffmpeg, ffprobe, node)"
    Write-Host "  [ok] $Release\assets (logo.ico)"
    Write-Host "  [ok] $Release\_internal (base_library.zip)"
}

Invoke-Step "Running packaged self-test from an arbitrary working directory" {
    Invoke-PackagedSelfTest
}

Invoke-Step "Smoke-testing bundled binaries from the package" {
    Assert-BundledBinariesRun
}

if (-not $BuildWork) {
    Write-Host "`n==> Cleaning intermediate build artifacts" -ForegroundColor Cyan
    Remove-Item $DistDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Release ready:" -ForegroundColor Green
Write-Host "  $Release" -ForegroundColor Green
Write-Host "  Run the app from:  $AppExe" -ForegroundColor Green
