# Activate venv and run the agent nicely
param([int]$Port=5025)
if (Test-Path ".\.venv\Scripts\Activate.ps1") {. .\.venv\Scripts\Activate.ps1}
$env:UIB_PORT="$Port"
uvicorn app.main:app --host 127.0.0.1 --port $env:UIB_PORT --reload
