# Creates a desktop shortcut for the built EXE (dist\DotaBetTracker\DotaBetTracker.exe)
# or, if the EXE is not built yet, for run.bat with the project icon.
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root "dist\DotaBetTracker\DotaBetTracker.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desktop "Dota Bet Tracker.lnk"))
if (Test-Path $exe) {
  $lnk.TargetPath = $exe
  $lnk.WorkingDirectory = Split-Path $exe
  $lnk.IconLocation = $exe
} else {
  $lnk.TargetPath = Join-Path $root "run.bat"
  $lnk.WorkingDirectory = $root
  $lnk.WindowStyle = 7
  $lnk.IconLocation = (Join-Path $root "assets\icon.ico")
}
$lnk.Save()
Write-Host "Shortcut created on the desktop: Dota Bet Tracker"
