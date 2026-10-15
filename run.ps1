param(
    [ValidateSet('dev', 'build', 'test', 'ingest', 'verify')]
    [string]$Action = 'dev'
)

$nodeRoot = Join-Path $env:LOCALAPPDATA 'Programs\nodejs'
$pythonRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
$npmTool = Join-Path $nodeRoot 'npm.cmd'
if (-not (Test-Path -LiteralPath $npmTool)) { $npmTool = (Get-Command npm.cmd -ErrorAction Stop).Source }

$pythonTool = $env:REGATTA_PYTHON
if ([string]::IsNullOrWhiteSpace($pythonTool)) { $pythonTool = Join-Path $pythonRoot 'python.exe' }
if ($Action -in @('ingest', 'verify') -and -not (Test-Path -LiteralPath $pythonTool)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { $pythonTool = $pythonCommand.Source }
    else { throw 'Python was not found. Set REGATTA_PYTHON to a Python executable before ingest or verify.' }
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
        'verify' {
            Invoke-Checked -File $npmTool -Arguments @('test')
            Invoke-Checked -File $npmTool -Arguments @('run', 'build')
            Invoke-Checked -File $pythonTool -Arguments @('-m', 'unittest', 'discover', '-s', 'tests/unit', '-p', 'test_*.py')
            Invoke-Checked -File $pythonTool -Arguments @('tests/e2e/test_runner.py', '--tier', 'all')
            Invoke-Checked -File $pythonTool -Arguments @('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'tier5_*.py')
        }
    }
} finally {
    Pop-Location
}
