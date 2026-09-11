[CmdletBinding()]
param(
    [ValidateSet("cu121")]
    [string]$TorchCuda = "cu121"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$vggtRepo = Join-Path $projectRoot "vendor\vggt"
$constraints = Join-Path $projectRoot "scene_ai_service\constraints-windows.txt"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher 'py' was not found. Install Python 3.10 x64, then run this script again."
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating Python 3.10 virtual environment..."
    & py -3.10 -m venv (Join-Path $projectRoot ".venv")
}

if (-not (Test-Path (Join-Path $vggtRepo ".git"))) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git was not found. Install Git, then run this script again."
    }
    New-Item -ItemType Directory -Force (Split-Path $vggtRepo) | Out-Null
    Write-Host "Cloning VGGT..."
    & git clone https://github.com/facebookresearch/vggt.git $vggtRepo
}

Write-Host "Installing pinned scene-AI dependencies..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $vggtRepo "requirements.txt") -r (Join-Path $projectRoot "scene_ai_service\requirements.txt") -c $constraints
& $pythonExe -m pip install --force-reinstall --no-deps --index-url "https://download.pytorch.org/whl/$TorchCuda" "torch==2.3.1+$TorchCuda" "torchvision==0.18.1+$TorchCuda"

Write-Host "Verifying Python, NumPy and CUDA..."
& $pythonExe -c "import numpy, torch; print('NumPy:', numpy.__version__); print('Torch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not detected')"
Write-Host "Setup complete. Start the service with: .\start_scene_ai.ps1"