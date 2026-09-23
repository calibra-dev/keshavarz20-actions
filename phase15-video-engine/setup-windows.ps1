Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "K20 Phase15 Windows setup"

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $name"
  }
}

Require-Command "python"
Require-Command "git"
Require-Command "nvidia-smi"

if (-not (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)) {
  if (Get-Command "winget" -ErrorAction SilentlyContinue) {
    Write-Host "Installing FFmpeg with winget..."
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  } else {
    throw "FFmpeg is missing and winget is unavailable. Install FFmpeg, then rerun this script."
  }
}

python -m pip install --upgrade pip
python -m pip install -r "$PSScriptRoot\requirements.txt"

Write-Host ""
Write-Host "GPU summary:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

Write-Host ""
Write-Host "Running engine health check..."
python "$PSScriptRoot\k20_video_engine.py" health

Write-Host ""
Write-Host "Setup finished. Configure the GitHub runner labels: k20-video,gpu"
