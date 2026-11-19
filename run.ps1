param(
    [ValidateSet('dev', 'build', 'test', 'ingest', 'environment', 'analytics', 'research', 'verify')]
    [string]$Action = 'dev'
)

$nodeRoot = Join-Path $env:LOCALAPPDATA 'Programs\nodejs'
if ((Test-Path -LiteralPath $nodeRoot) -and -not (($env:PATH -split ';') -contains $nodeRoot)) {
    $env:PATH = "$nodeRoot;$env:PATH"
}
$pythonRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
$npmTool = Join-Path $nodeRoot 'npm.cmd'
if (-not (Test-Path -LiteralPath $npmTool)) { $npmTool = (Get-Command npm.cmd -ErrorAction Stop).Source }

$pythonTool = $env:REGATTA_PYTHON
if ([string]::IsNullOrWhiteSpace($pythonTool) -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))) {
    $pythonTool = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
}
if ([string]::IsNullOrWhiteSpace($pythonTool)) { $pythonTool = Join-Path $pythonRoot 'python.exe' }
if ($Action -in @('ingest', 'environment', 'analytics', 'research', 'verify') -and -not (Test-Path -LiteralPath $pythonTool)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { $pythonTool = $pythonCommand.Source }
    else { throw 'Python was not found. Set REGATTA_PYTHON to a Python executable before ingest, environment, analytics or verify.' }
}

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File exited with code $LASTEXITCODE" }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    switch ($Action) {
        'dev' { Invoke-Checked -File $npmTool -Arguments @('run', 'dev') }
        'build' { Invoke-Checked -File $npmTool -Arguments @('run', 'build') }
        'test' { Invoke-Checked -File $npmTool -Arguments @('test') }
        'ingest' { Invoke-Checked -File $pythonTool -Arguments @('pipeline/run_pipeline.py') }
        'environment' { Invoke-Checked -File $pythonTool -Arguments @('-m', 'pipeline.environment', 'export') }
        'analytics' { Invoke-Checked -File $pythonTool -Arguments @('scripts/refresh_team_analytics.py') }
        'research' { Invoke-Checked -File $pythonTool -Arguments @('scripts/refresh_ac38_research.py', '--extract') }
        'verify' { Invoke-Checked -File $pythonTool -Arguments @('scripts/verify.py', '--with-format') }
    }
} finally {
    Pop-Location
}
