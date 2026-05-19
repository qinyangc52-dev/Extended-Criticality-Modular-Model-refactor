# Environment Setup

## Windows C/C++ Toolchain

Recommended setup for VSCode on Windows:

1. Install MSYS2:

```powershell
winget install MSYS2.MSYS2
```

2. Open the **MSYS2 UCRT64** terminal and install build tools:

```bash
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-make
```

3. Add this directory to your Windows `PATH` if VSCode PowerShell cannot find `g++`:

```text
C:\msys64\ucrt64\bin
```

4. Check the environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_environment.ps1
```

## Python

Install the analysis dependencies:

```powershell
pip install -r requirements.txt
pip install -e .
```

The notebook uses `powerlaw` to match the method described for Fig.5.

## VSCode Extensions

Install the recommended extensions shown by VSCode from `.vscode/extensions.json`:

- C/C++ (`ms-vscode.cpptools`)
- CMake Tools (`ms-vscode.cmake-tools`)
- Python (`ms-python.python`)
- Jupyter (`ms-toolsai.jupyter`)
- Makefile Tools (`ms-vscode.makefile-tools`)
- GitLens (`eamodio.gitlens`)

## VSCode Tasks

Use **Terminal -> Run Task**:

- `Check Environment`
- `Configure CMake`
- `Build Release`
- `Run Smoke Simulation`
- `Run Stationary Bin5 Experiments`
- `Run Core Synthetic Experiments`
