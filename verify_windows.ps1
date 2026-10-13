$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\Script2Gif\Script2Gif.exe"

if (-not (Test-Path $exe)) {
    throw "Executable not found: $exe"
}

$process = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 5
$process.Refresh()

if ($process.HasExited) {
    throw "Script2Gif exited during startup with code $($process.ExitCode)"
}

Stop-Process -Id $process.Id
Write-Host "Script2Gif startup smoke test passed."
