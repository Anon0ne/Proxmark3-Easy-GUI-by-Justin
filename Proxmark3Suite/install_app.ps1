param(
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA 'Programs\Proxmark3EasyGUI'),
    [switch]$NoShortcut
)
$ErrorActionPreference = 'Stop'
try {
    $source = Join-Path $PSScriptRoot 'Proxmark3Suite.exe'
    if (-not (Test-Path -LiteralPath $source)) { throw 'Extract the entire Windows package before running Install.ps1.' }
    $destination = [IO.Path]::GetFullPath($InstallDirectory)
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $target = Join-Path $destination 'Proxmark3Suite.exe'
    if ([IO.Path]::GetFullPath($source) -ne $target) {
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
    if (-not $NoShortcut) {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Proxmark3 Engineering Suite.lnk'))
        $shortcut.TargetPath = $target
        $shortcut.WorkingDirectory = $destination
        $shortcut.Description = 'Proxmark3 Engineering Suite 0.6b beta'
        $shortcut.IconLocation = $target + ',0'
        $shortcut.Save()
    }
    Write-Host "Installed: $target"
    Write-Host 'Open the app, choose the external Iceman client in Settings, then Connect & verify.'
} catch {
    Write-Error $_
    exit 1
}
