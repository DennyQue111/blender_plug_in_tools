[CmdletBinding()]
param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$vggtSource = Join-Path $projectRoot "vendor\vggt\vggt\models\vggt.py"

if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment not found. Run .\setup_scene_ai.ps1 first."
}
if (-not (Test-Path $vggtSource)) {
    throw "VGGT source not found. Run .\setup_scene_ai.ps1 first."
}

Set-Location $projectRoot
& $pythonExe ".\scene_ai_service\run_service.py" --port $Port