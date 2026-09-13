[CmdletBinding()]
param(
    [ValidateSet("cu121", "cu128")]
    [string]$TorchCuda = "cu128"
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
if ($TorchCuda -eq "cu128") {
    # Do not use --no-deps here: CUDA 12.8 needs its matching NVIDIA runtime wheels.
    & $pythonExe -m pip install --force-reinstall --index-url "https://download.pytorch.org/whl/cu128" "torch==2.7.0+cu128" "torchvision==0.22.0+cu128"
} else {
    & $pythonExe -m pip install --force-reinstall --index-url "https://download.pytorch.org/whl/cu121" "torch==2.3.1+cu121" "torchvision==0.18.1+cu121"
}

Write-Host "Verifying runtime dependencies, Python, NumPy and CUDA..."
& $pythonExe -c "import fastapi, PIL, torch, trimesh, uvicorn; print('FastAPI:', fastapi.__version__); print('Pillow:', PIL.__version__); print('Trimesh:', trimesh.__version__); print('NumPy:', __import__('numpy').__version__); print('Torch:', torch.__version__); print('CUDA:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not detected'); print('Supported GPU architectures:', torch.cuda.get_arch_list() if torch.cuda.is_available() else 'n/a')"
Write-Host "Setup complete. Start the service with: .\start_scene_ai.ps1"
