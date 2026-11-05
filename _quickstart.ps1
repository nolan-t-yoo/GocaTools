#Requires -Version 5.1
<#
.SYNOPSIS
    Install Python if it is missing, then start GocaTools.

.DESCRIPTION
    Looks for Python 3.9 or newer with tkinter available. When none is found this installs a
    per-user copy of Python 3.12 - with winget when it is available, otherwise with the official
    python.org installer, checked against a pinned SHA-256 - and then hands over to launch.bat,
    which creates the virtual environment, installs the two dependencies and opens the UI.

    No administrator rights are needed. Run it by right-clicking this file and choosing
    "Run with PowerShell", or from a terminal:

        powershell -ExecutionPolicy Bypass -File .\_quickstart.ps1

.PARAMETER NoLaunch
    Set Python up but do not start the UI.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\_quickstart.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\_quickstart.ps1 -NoLaunch
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$NoLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PythonVersion = '3.12.10'
$WingetId = 'Python.Python.3.12'
$MinVersion = [version]'3.9'

# SHA-256 of the official python.org installers for $PythonVersion.
$InstallerHashes = @{
    'amd64' = '67B5635E80EA51072B87941312D00EC8927C4DB9BA18938F7AD2D27B328B95FB'
    'arm64' = '377AC8FD478987940088E879441E702A71B53164D2A1E6F1D51FF77A7E470258'
    'x86'   = 'FDFE385B94F5B8785A0226A886979527FD26EB65DEFDBF29992FD22CC4B0E31E'
}

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$launchBat = Join-Path $scriptDir 'launch.bat'

# Plain functions have no $PSCmdlet of their own, so keep the script's for ShouldProcess.
$Cmdlet = $PSCmdlet

# ── output helpers ───────────────────────────────────────────────────────────
function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "    $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    ! $Message" -ForegroundColor Yellow
}

function Stop-Quickstart {
    param([string]$Message)
    Write-Host ''
    Write-Host "Quickstart could not finish: $Message" -ForegroundColor Red
    exit 1
}

# ── Python detection ─────────────────────────────────────────────────────────
function Test-UsablePython {
    param([string]$Exe)

    if (-not $Exe) { return $false }
    if ($Exe -like '*\WindowsApps\*') { return $false }  # Microsoft Store stub, not a real install
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }

    & $Exe -c 'import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-PythonCandidates {
    $found = New-Object System.Collections.Generic.List[string]

    foreach ($name in 'python', 'python3') {
        $command = Get-Command -Name $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source) { $found.Add($command.Source) }
    }

    if (Get-Command -Name 'py.exe' -ErrorAction SilentlyContinue) {
        $exe = & py.exe -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { $found.Add($exe.Trim()) }
    }

    # Per-user and machine-wide installs made by the python.org installer.
    $globs = @()
    if ($env:LOCALAPPDATA) { $globs += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe') }
    if ($env:ProgramFiles) { $globs += (Join-Path $env:ProgramFiles 'Python3*\python.exe') }
    foreach ($glob in $globs) {
        Get-ChildItem -Path $glob -ErrorAction SilentlyContinue |
            ForEach-Object { $found.Add($_.FullName) }
    }

    # Last resort: whatever the installer recorded in the registry.
    foreach ($root in 'HKLM:\SOFTWARE\Python\PythonCore', 'HKCU:\SOFTWARE\Python\PythonCore') {
        if (-not (Test-Path -Path $root)) { continue }
        foreach ($key in Get-ChildItem -Path $root -ErrorAction SilentlyContinue) {
            $installKey = Join-Path $key.PSPath 'InstallPath'
            $item = Get-Item -Path $installKey -ErrorAction SilentlyContinue
            if (-not $item) { continue }
            $exe = $item.GetValue('ExecutablePath')
            if (-not $exe) {
                $directory = $item.GetValue('')
                if ($directory) { $exe = Join-Path $directory 'python.exe' }
            }
            if ($exe) { $found.Add($exe) }
        }
    }

    return $found | Select-Object -Unique
}

function Find-UsablePython {
    foreach ($candidate in Get-PythonCandidates) {
        if (Test-UsablePython -Exe $candidate) { return $candidate }
    }
    return $null
}

function Get-PythonArch {
    $machine = $env:PROCESSOR_ARCHITEW6432
    if (-not $machine) { $machine = $env:PROCESSOR_ARCHITECTURE }

    switch ($machine) {
        'ARM64' { return 'arm64' }
        'AMD64' { return 'amd64' }
        default { return 'x86' }
    }
}

# ── installation ─────────────────────────────────────────────────────────────
function Update-SessionPath {
    # A fresh install only updates the stored PATH, not this shell's copy.
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ';'
}

function Install-PythonWithWinget {
    if (-not (Get-Command -Name 'winget.exe' -ErrorAction SilentlyContinue)) { return $false }

    Write-Step "Installing Python $PythonVersion with winget"
    & winget.exe install --id $WingetId --exact --source winget --scope user --silent `
        --accept-package-agreements --accept-source-agreements --disable-interactivity

    # 0 = installed, -1978335189 = already installed.
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
        Write-Info 'winget finished.'
        return $true
    }

    Write-Warn "winget exited with code $LASTEXITCODE; trying the python.org installer instead."
    return $false
}

function Install-PythonFromPythonOrg {
    $arch = Get-PythonArch
    $fileName = switch ($arch) {
        'amd64' { "python-$PythonVersion-amd64.exe" }
        'arm64' { "python-$PythonVersion-arm64.exe" }
        default { "python-$PythonVersion.exe" }
    }
    $url = "https://www.python.org/ftp/python/$PythonVersion/$fileName"
    $installer = Join-Path $env:TEMP $fileName

    Write-Step "Downloading Python $PythonVersion ($arch)"
    Write-Info $url
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch {
        # Older hosts already default to a usable protocol.
    }
    try {
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    } catch {
        Stop-Quickstart "could not download the installer.`n    $($_.Exception.Message)`n    Install Python manually from https://www.python.org/downloads/ and run launch.bat."
    }

    $expected = $InstallerHashes[$arch]
    $actual = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
    if ($actual -ne $expected) {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
        Stop-Quickstart "the downloaded installer did not match its expected SHA-256.`n    expected $expected`n    actual   $actual"
    }
    Write-Info 'SHA-256 verified.'

    Write-Step "Installing Python $PythonVersion for the current user"
    $arguments = '/quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 ' +
        'Include_launcher=1 Include_tcltk=1 Include_test=0 Include_doc=0 Shortcuts=1'
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue

    if ($process.ExitCode -ne 0) {
        Stop-Quickstart "the Python installer exited with code $($process.ExitCode). Try https://www.python.org/downloads/ instead."
    }
    Write-Info 'Python installed.'
}

# ── main ─────────────────────────────────────────────────────────────────────
function Invoke-Quickstart {
    Write-Host ''
    Write-Host 'GocaTools quickstart' -ForegroundColor Cyan
    Write-Host '--------------------'

    if (-not (Test-Path -LiteralPath $launchBat)) {
        Stop-Quickstart "launch.bat was not found next to this script ($scriptDir)."
    }

    $python = Find-UsablePython

    if ($python) {
        Write-Step "Using Python: $python"
    } else {
        if (Get-PythonCandidates) {
            Write-Warn 'A Python install was found but it is older than 3.9 or has no tkinter.'
        }
        Write-Step "Python $MinVersion or newer was not found - installing it now"
        Write-Info 'No administrator rights are needed; this installs for the current user only.'

        if ($WhatIfPreference) {
            Write-Info "Would install Python $PythonVersion (winget or python.org), then run launch.bat."
            return
        }

        if (-not (Install-PythonWithWinget)) {
            Install-PythonFromPythonOrg
        }

        Update-SessionPath
        $python = Find-UsablePython
        if (-not $python) {
            Stop-Quickstart 'Python was installed but this shell cannot see it yet. Close this window, open a new one and run _quickstart.ps1 again.'
        }
        Write-Step "Using Python: $python"
    }

    if ($NoLaunch) {
        Write-Step 'Ready. Skipping the launch because -NoLaunch was given.'
        return
    }

    Write-Step 'Starting GocaTools'
    if (-not $Cmdlet.ShouldProcess('GocaTools', 'Start')) { return }

    & $launchBat
    exit $LASTEXITCODE
}

Invoke-Quickstart
