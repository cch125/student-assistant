$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating Python virtual environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } else {
        & python -m venv .venv
    }
}

Write-Host "Installing/updating Python requirements..."
& $VenvPython -m pip install --disable-pip-version-check -r requirements.txt

$Port = if ($env:ASSISTANT_PORT) { $env:ASSISTANT_PORT } else { "8090" }
Write-Host "Starting FastAPI student assistant at http://127.0.0.1:$Port"
& $VenvPython -m uvicorn app_fastapi:app --host 127.0.0.1 --port $Port
