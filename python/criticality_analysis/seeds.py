from __future__ import annotations

from pathlib import Path

from .io import read_seed


def write_seed(base_seed: str | Path, output: str | Path, **updates: object) -> Path:
    """Write a SEED file using the original key=value format."""
    values = read_seed(base_seed)
    for key, value in updates.items():
        values[key] = str(value)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def make_parameter_sweep(
    base_seed: str | Path,
    output_dir: str | Path,
    e0_values: list[float],
    i0_values: list[float],
    prefix: str = "sweep",
    **common_updates: object,
) -> dict[str, Path]:
    """Create SEED files for an E0/I0 grid."""
    output_dir = Path(output_dir)
    configs: dict[str, Path] = {}
    for i0 in i0_values:
        for e0 in e0_values:
            name = f"{prefix}_e{e0:g}_i{i0:g}".replace(".", "p")
            path = output_dir / f"{name}.seed"
            updates = {
                "name": name,
                "sigma": e0,
                "delta": i0,
                **common_updates,
            }
            configs[name] = write_seed(base_seed, path, **updates)
    return configs

