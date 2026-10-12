param(
    [string]$Executable = "$PSScriptRoot\dist\FastAPI-Service.exe",
    [int]$Port = 18092
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Executable)) {
    throw "Executable not found: $Executable. Run build_windows.bat first."
}

$process = Start-Process `
    -FilePath $Executable `
    -ArgumentList @("--headless", "--no-browser", "--port", $Port) `
    -PassThru

try {
    $health = $null
    $deadline = (Get-Date).AddSeconds(30)

    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) {
            throw "Executable exited before the service became ready. Exit code: $($process.ExitCode)"
        }

        try {
            $health = Invoke-RestMethod `
                -Uri "http://127.0.0.1:$Port/health" `
                -TimeoutSec 2
            break
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if ($null -eq $health -or $health.status -ne "ok") {
        throw "Health check failed or timed out."
    }

    $ping = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$Port/api/v1/examples/ping" `
        -TimeoutSec 5

    if ($ping.message -ne "pong") {
        throw "Ping check returned an unexpected response."
    }

    Write-Host "[PASS] Executable started successfully." -ForegroundColor Green
    Write-Host "[PASS] /health returned status=ok." -ForegroundColor Green
    Write-Host "[PASS] /api/v1/examples/ping returned pong." -ForegroundColor Green
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit()
    }
    Write-Host "Smoke-test process stopped."
}
