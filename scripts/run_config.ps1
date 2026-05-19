param(
    [Parameter(Mandatory = $true)][string]$SeedFile,
    [Parameter(Mandatory = $false)][string]$RunName = "",
    [switch]$LiveLog
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$MsysUcrtBin = "C:\msys64\ucrt64\bin"
if ((Test-Path $MsysUcrtBin) -and ($env:PATH -notlike "*$MsysUcrtBin*")) {
    $env:PATH = "$MsysUcrtBin;$env:PATH"
}
$Executable = Join-Path $ProjectRoot "build\criticality_sim.exe"
if (-not (Test-Path $Executable)) {
    $Executable = Join-Path $ProjectRoot "build\criticality_sim"
}
if (-not (Test-Path $Executable)) {
    throw "Simulator executable not found. Build it first with: cmake --build build --config Release"
}

$SeedPath = Resolve-Path (Join-Path $ProjectRoot $SeedFile)
if ($RunName -eq "") {
    $RunName = [IO.Path]::GetFileNameWithoutExtension($SeedPath)
}
$RunDir = Join-Path $ProjectRoot "results\runs\$RunName"
New-Item -ItemType Directory -Force $RunDir | Out-Null
Copy-Item -Force $SeedPath (Join-Path $RunDir "SEED")

function Assert-LogWritable {
    param([string]$Path)
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $stream.Close()
    } catch {
        throw "Log file is locked: $Path. The experiment '$RunName' is probably still running in another terminal. Wait for it to finish, or stop the old criticality_sim process before rerunning this experiment."
    }
}

Push-Location $RunDir
try {
    $stdout = Join-Path $RunDir "stdout.log"
    $stderr = Join-Path $RunDir "stderr.log"
    $runLog = Join-Path $RunDir "run.log"
    Assert-LogWritable $stdout
    Assert-LogWritable $stderr
    Assert-LogWritable $runLog
    if ($LiveLog) {
        Set-Content -Path $stderr -Value ""
        $cmd = "`"$Executable`" 2>&1"
        & cmd.exe /d /c $cmd | Tee-Object -FilePath $runLog
        $exitCode = $LASTEXITCODE
        Copy-Item -Force $runLog $stdout
        if ($exitCode -ne 0) {
            throw "Simulation failed with exit code $exitCode. See $runLog"
        }
    } else {
        $proc = Start-Process -FilePath $Executable -WorkingDirectory $RunDir -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru -NoNewWindow
        Get-Content $stdout, $stderr -ErrorAction SilentlyContinue | Set-Content $runLog
        if ($proc.ExitCode -ne 0) {
            throw "Simulation failed with exit code $($proc.ExitCode). See $runLog"
        }
    }
} finally {
    Pop-Location
}
Write-Host "Simulation completed: $RunDir"
