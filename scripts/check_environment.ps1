Write-Host "Checking C/C++ and Python environment..."

$ucrt = "C:\msys64\ucrt64\bin"
if (Test-Path $ucrt) {
    $env:PATH = "$ucrt;$env:PATH"
}

$commands = @("g++", "cmake", "python")
foreach ($cmd in $commands) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "[OK] $cmd -> $($found.Source)"
    } else {
        Write-Host "[MISSING] $cmd"
    }
}

@'
import importlib
for name in ["numpy", "pandas", "matplotlib", "jupyter", "nbformat", "powerlaw"]:
    try:
        mod = importlib.import_module(name)
        print(f"[OK] python package {name}: {getattr(mod, '__version__', 'installed')}")
    except Exception as exc:
        print(f"[MISSING] python package {name}: {exc}")
'@ | python -

Write-Host ""
Write-Host "If g++ or cmake is missing, install MSYS2 and the UCRT64 packages documented in docs/ENVIRONMENT.md."
