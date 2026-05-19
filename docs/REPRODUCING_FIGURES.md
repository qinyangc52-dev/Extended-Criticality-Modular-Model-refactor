# Reproducing Synthetic Figures

## Scope

The notebook reproduces figures that can be generated from the synthetic C/C++
model outputs. Empirical MEG figures require the original MEG/source data, which
are not included in this repository.

## Fig.5

Fig.5 uses synthetic neuronal avalanches:

- Module firing rates are computed from simulator `rate3-*.dat` output.
- The Fig.5 configs set `bin=5`, so rate rows are 5 ms windows.
- An avalanche is a continuous interval with at least one module rate greater than zero.
- Size is the integral of summed module rates over the avalanche.
- Duration is the number of active 5 ms bins multiplied by 5 ms.
- The notebook fits power laws using the `powerlaw` Python package and reports
  alpha/beta, KS distance, likelihood ratio `R`, and `p`.

Run the three Fig.5 simulations:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_config.ps1 configs/experiments/stationary_e57_i11_bin5.seed stationary_e57_i11_bin5
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_config.ps1 configs/experiments/stationary_e68_i11_bin5.seed stationary_e68_i11_bin5
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_config.ps1 configs/experiments/stationary_e69_i11_bin5.seed stationary_e69_i11_bin5
```

Then run `notebooks/02_reproduce_synthetic_experiments.ipynb`.

## Fig.2-Fig.4

`02_reproduce_synthetic_experiments.ipynb` also includes:

- Fig.2-style hysteresis curves from `hysteresis_i03.seed`,
  `hysteresis_i08.seed`, and `hysteresis_i11.seed`.
- Fig.3/Fig.4 parameter-space maps generated from an editable E0/I0 grid.
- Fig.4 example panels using `stationary_e57_i11_bin1.seed`,
  `stationary_e68_i11_bin1.seed`, and `stationary_e69_i11_bin1.seed`:
  raster, module-rate heatmap, and overlap time series.

The naming is experiment-first: simulation outputs under `results/runs/` are
primary results, and figures are derived products.

The notebook can generate sweep `SEED` files under `results/generated_configs/`.
Dense publication-quality parameter maps require many long C/C++ simulations;
start with the default grid, then increase `E0_VALUES` and `I0_VALUES` if more
resolution is needed.

## Notes

The paper's reported exponents depend on simulation length, random seed, fitting
range, and available avalanche counts. The notebook reports the fitted values
from the generated outputs and saves figures to `results/figures/`.
