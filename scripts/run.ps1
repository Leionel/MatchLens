param([switch]$SkipBuild, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    uv sync --project services/api
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency sync failed' }
    if (-not $SkipBuild) {
        npm --prefix apps/web ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency install failed' }
        npm --prefix apps/web run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    }
    Push-Location services/api
    try { ./.venv/Scripts/python.exe -m uvicorn matchlens.main:app --host 127.0.0.1 --port $Port --workers 1 }
    finally { Pop-Location }
} finally { Pop-Location }
