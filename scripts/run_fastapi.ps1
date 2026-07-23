$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$Python = "python"
$Port = if ($env:ASSISTANT_PORT) { $env:ASSISTANT_PORT } else { "8090" }

Write-Host "Installing Python requirements..."
& $Python -m pip install -r requirements.txt

Write-Host "Starting FastAPI student assistant at http://127.0.0.1:$Port"
& $Python -m uvicorn app_fastapi:app --host 127.0.0.1 --port $Port

