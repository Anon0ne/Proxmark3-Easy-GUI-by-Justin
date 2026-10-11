param([switch]$NoShortcut)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Program $Arguments" }
}
function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe')
    )
    $installed = Get-Command python -ErrorAction SilentlyContinue
    if ($installed) { $candidates += $installed.Source }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

try {
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Python 3.10+ and winget are missing. Install Python from https://www.python.org/downloads/windows/ and rerun.'
        }
        Write-Host 'Installing Python 3.12 for the current user…'
        Invoke-Checked 'winget' @('install','--id','Python.Python.3.12','--exact','--scope','user','--accept-package-agreements','--accept-source-agreements')
        $pythonExe = Find-Python
        if (-not $pythonExe) { throw 'Python installation did not produce a usable interpreter. Reopen PowerShell and rerun.' }
    }
    Invoke-Checked $pythonExe @('-m','venv','.venv')
    $buildPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    Invoke-Checked $buildPython @('-m','pip','install','--no-cache-dir','-r','requirements.txt')
    Invoke-Checked $buildPython @('-m','unittest','discover','-s','tests','-v')
    Invoke-Checked $buildPython @('build_exe.py')
    $target = Join-Path $PSScriptRoot 'dist\Proxmark3Suite.exe'
    if (-not (Test-Path -LiteralPath $target)) { throw 'EXE artifact missing after build.' }
    if (-not $NoShortcut) {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Proxmark3 Engineering Suite.lnk'))
        $shortcut.TargetPath = $target
        $shortcut.WorkingDirectory = $PSScriptRoot
        $shortcut.Description = 'Proxmark3 Easy GUI - by Justin 0.3b'
        $shortcut.Save()
    }
    Write-Host "Build complete: $target"
    Write-Host 'Connect and verify hardware compatibility before using card commands.'
} catch {
    Write-Error $_
    exit 1
}
