# Extended Criticality Modular Model

Refactored project for the modular large-scale LIF model described in Angiolelli et al.,
*Physical Review Research* 7, 043153 (2025).

The scientific core is still the original C/C++ model: modular pattern construction,
STDP-derived asymmetric connectivity, event-driven LIF dynamics, overlap, rate, Fano,
and spike outputs are preserved. The refactor separates the simulator from Python
analysis notebooks.

## Layout

- `src/model`: LIF and network model code.
- `src/utils`: shared C/C++ utility code from the original project.
- `src/data`: embedded tractography/DKT constants.
- `apps/simulate`: simulator entry point.
- `configs`: reproducible `SEED` files, including Fig.5 settings.
- `python/criticality_analysis`: Python readers, runners, avalanche analysis, plotting.
- `notebooks`: Jupyter figure reproduction workflows.
- `legacy/original`: untouched source snapshot from the cloned repository.
- `docs`: refactor, environment, and figure reproduction notes.

## Build

On Windows, use MSYS2/MinGW UCRT64 as documented in `docs/ENVIRONMENT.md`.

```powershell
cmake -S . -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

Run a quick smoke test:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_config.ps1 configs/experiments/smoke.seed smoke
```

## Python Analysis

```powershell
pip install -r requirements.txt
pip install -e .
jupyter notebook notebooks/02_reproduce_synthetic_experiments.ipynb
```

Use `02_reproduce_synthetic_experiments.ipynb` for the full synthetic-data
workflow: run or read core experiments first, then derive Fig.2 hysteresis,
Fig.3/Fig.4 parameter maps and examples, and Fig.5 avalanche size/duration
distributions using the `powerlaw` package. The older
`01_reproduce_synthetic_figures.ipynb` is a smaller Fig.5-focused workflow.
