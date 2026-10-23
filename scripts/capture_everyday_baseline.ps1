# M2.2 baseline capture on the owner's laptop (owner rule, 14 Oct 2026).
# Needs at least 3.5 GB free. Starts only the staging database container,
# runs the capture on the host with one model loaded at a time, then stops
# the container. Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File scripts\capture_everyday_baseline.ps1 -Python <python with openvino>
param(
    [string]$Python = "python",
    [double]$MinFreeGB = 3.5,
    [double]$AbortFreeGB = 1.0,
    [int]$HealthTimeoutSeconds = 120
)
$ErrorActionPreference = "Continue"  # native docker output on stderr must not throw in Windows PowerShell 5.1; exit codes are checked instead
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-FreeGB { [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2) }

$free = Get-FreeGB
if ($free -lt $MinFreeGB) {
    Write-Host "Not started: $free GB free, at least $MinFreeGB GB is needed. Close other apps and try again."
    exit 2
}
if (-not (Test-Path "eval\everyday_evaluation.py")) {
    Write-Host "Not started: eval\everyday_evaluation.py is missing. Run this from a checkout that has the M2.2 evaluator (PR #16)."
    exit 3
}
Write-Host "$free GB free. Starting the staging database container only."

$code = 1
try {
    docker compose up -d --no-deps db | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker compose could not start the database (is Docker Desktop running?)" }
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    do {
        Start-Sleep -Seconds 2
        $health = docker inspect -f "{{.State.Health.Status}}" setu-db 2>$null
    } until ($health -eq "healthy" -or (Get-Date) -gt $deadline)
    if ($health -ne "healthy") { throw "the database was not healthy after $HealthTimeoutSeconds s (status: $health)" }
    Write-Host "Database healthy. Capturing (models load one at a time)..."

    $env:LOCAL_INFERENCE_BACKEND = "openvino"
    $env:OPENVINO_MODEL_DIR = Join-Path $root "models\openvino"
    $env:SETU_MIN_FREE_GB = "$MinFreeGB"
    $env:SETU_ABORT_FREE_GB = "$AbortFreeGB"
    & $Python scripts\capture_guard.py
    $code = $LASTEXITCODE
}
catch {
    Write-Host "Stopped: $($_.Exception.Message)"
    $code = 1
}
finally {
    docker compose stop db 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "Database container stopped." } else { Write-Host "Could not stop the database container; check Docker Desktop." }
}

if ($code -eq 0) {
    $saved = Get-Content "eval\everyday_retrieval.json" -Raw -Encoding utf8 | ConvertFrom-Json
    $cases = @($saved.results.PSObject.Properties).Count
    Write-Host "RESULT ok: $cases cases saved to eval\everyday_retrieval.json at $($saved.captured.at) from $($saved.captured.database) ($($saved.captured.documents) documents, $($saved.captured.chunks) chunks). Free now: $(Get-FreeGB) GB."
} else {
    Write-Host "RESULT failed (exit $code). eval\everyday_retrieval.json was not changed by this run."
}
exit $code
