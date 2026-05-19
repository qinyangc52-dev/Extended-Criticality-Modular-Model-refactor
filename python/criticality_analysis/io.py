from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_seed(path: str | Path) -> dict[str, str]:
    """Read the original SEED key=value format without changing its semantics."""
    values: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("%", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def find_output_file(run_dir: str | Path, prefix: str, name: str | None = None) -> Path:
    run_dir = Path(run_dir)
    output_dir = run_dir / "output"
    if name:
        candidate = output_dir / f"{prefix}-{name}.dat"
        if candidate.exists():
            return candidate
    matches = sorted(output_dir.glob(f"{prefix}-*.dat"))
    if not matches:
        raise FileNotFoundError(f"No {prefix}-*.dat file found in {output_dir}")
    return matches[0]


def load_rate(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    frame = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
    frame = frame.rename(columns={0: "time_ms"})
    for column in frame.columns[1:]:
        frame = frame.rename(columns={column: f"module_{column - 1:02d}"})
    return frame


def load_spikes(path: str | Path, pout: int = 3) -> pd.DataFrame:
    names = ["time_ms", "flag", "neuron"] + [f"posix_{idx}" for idx in range(pout)]
    frame = pd.read_csv(path, sep=r"\s+", header=None, names=names, engine="python")
    return frame


def load_medie(path: str | Path) -> pd.DataFrame:
    names = ["sigma", "delta", "alpha", "time_ms", "rate_hz", "variance", "cv", "fano"]
    return pd.read_csv(path, sep=r"\s+", header=None, names=names, engine="python")


def load_q(path: str | Path, pout: int = 3) -> pd.DataFrame:
    base = [
        "sigma",
        "delta",
        "alpha",
        "t_start",
        "t_end",
        "n_spikes",
        "best_pattern",
        "q_max",
        "q_var",
    ]
    extra: list[str] = []
    for idx in range(pout):
        extra.extend([f"window_{idx}", f"q_{idx}"])
    return pd.read_csv(path, sep=r"\s+", header=None, names=base + extra, engine="python")


def load_start(path: str | Path) -> pd.DataFrame:
    names = ["site", "n_neurons", "start", "k_pattern"]
    return pd.read_csv(path, sep=r"\s+", header=None, names=names, engine="python")


def find_start_file(run_dir: str | Path, topo: str = "tract1") -> Path:
    output_dir = Path(run_dir) / "output"
    candidate = output_dir / f"start-{topo}.txt"
    if candidate.exists():
        return candidate
    matches = sorted(output_dir.glob("start-*.txt"))
    if not matches:
        raise FileNotFoundError(f"No start-*.txt file found in {output_dir}")
    return matches[0]
