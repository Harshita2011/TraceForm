param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "traceform"
$frontendRoot = Join-Path $projectRoot "frontend"
$runtimeRoot = Join-Path $projectRoot ".runtime"
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$pythonCommand = (Get-Command $Python).Source
$localDependencies = Join-Path $backendRoot ".runtime-deps"
if (Test-Path -LiteralPath $localDependencies) { $env:PYTHONPATH = $localDependencies }
function Start-ServiceProcess($Name, $Executable, $Arguments, $WorkingDirectory) {
    $pidFile = Join-Path $runtimeRoot "$Name.pid"
    if (Test-Path -LiteralPath $pidFile) {
        $savedProcessId = [int](Get-Content -LiteralPath $pidFile)
        if (Get-Process -Id $savedProcessId -ErrorAction SilentlyContinue) {
            Write-Host "$Name already running (PID $savedProcessId)"; return
        }
    }
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot "$Name.out.log") -RedirectStandardError (Join-Path $runtimeRoot "$Name.err.log")
    $process.Id | Set-Content -LiteralPath $pidFile
    Write-Host "$Name started (PID $($process.Id)); logs in $runtimeRoot"
}
Push-Location $backendRoot
try { & $pythonCommand -m db.migrate; if ($LASTEXITCODE -ne 0) { throw "Database migration failed." } }
finally { Pop-Location }
Start-ServiceProcess "api" $pythonCommand @("-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000") $backendRoot
Start-ServiceProcess "worker" $pythonCommand @("-m", "orchestrator.worker") $backendRoot
Start-ServiceProcess "frontend" (Get-Command cmd.exe).Source @("/c", "npm run dev") $frontendRoot
Write-Host "Open http://localhost:3000/dashboard/settings to check the provider and worker."
