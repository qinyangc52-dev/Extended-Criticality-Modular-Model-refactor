# Refactoring Notes

## What Changed

- The original flat source tree was split into model, utility, data, and app layers.
- The simulator now builds through CMake as `criticality_sim`.
- Python analysis code was added for output loading, isolated runs, avalanche extraction, and plotting.
- Jupyter notebooks were added for synthetic figure reproduction.
- Reproducible experiment `SEED` configurations were added under `configs/experiments/`.
- VSCode task and extension recommendations were added.

## What Did Not Change

- The LIF event-driven dynamics are unchanged.
- The STDP learning rule and embedded tractography matrix are unchanged.
- The original `SEED` key-value format is unchanged.
- Output file semantics remain compatible with the original program.
- The original code snapshot is preserved in `legacy/original`.

## Source Mapping

- Original `main.c` -> `apps/simulate/main.c`.
- Original `network.c` -> `src/model/network.c`.
- Original `neuroni.c` -> `src/model/neuroni.c`.
- Original `tract1.c` -> `src/data/tract1.c`.
- Original helper files -> `src/utils/`.

The only intentional simulator entry-point adjustment is passing `argc/argv` into
`pvm_init`, which improves command-line compatibility and does not change the model.
