$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root
$host.UI.RawUI.WindowTitle = "SolarScope Full-Stack Application"
python dev.py
