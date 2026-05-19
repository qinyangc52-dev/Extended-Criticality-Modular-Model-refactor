from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io import find_output_file, find_start_file, load_medie, load_q, load_spikes, load_start


def neuron_modules(start_frame: pd.DataFrame) -> np.ndarray:
    rows = start_frame[start_frame["n_neurons"] > 0]
    n_total = int((rows["start"] + rows["n_neurons"]).max())
    modules = np.full(n_total, -1, dtype=int)
    for _, row in rows.iterrows():
        start = int(row["start"])
        stop = start + int(row["n_neurons"])
        modules[start:stop] = int(row["site"]) - 1
    return modules


def module_isi_cv(spikes: pd.DataFrame, start_frame: pd.DataFrame) -> float:
    modules = neuron_modules(start_frame)
    valid = spikes["neuron"].to_numpy(dtype=int) < len(modules)
    spike_times = spikes.loc[valid, "time_ms"].to_numpy(dtype=float)
    spike_modules = modules[spikes.loc[valid, "neuron"].to_numpy(dtype=int)]
    cvs: list[float] = []
    for module in np.unique(spike_modules[spike_modules >= 0]):
        times = np.sort(spike_times[spike_modules == module])
        if len(times) < 3:
            continue
        intervals = np.diff(times)
        mean = intervals.mean()
        if mean > 0:
            cvs.append(float(intervals.std(ddof=0) / mean))
    return float(np.mean(cvs)) if cvs else np.nan


def flexibility(q_frame: pd.DataFrame, threshold: float = 0.8) -> int:
    q_columns = [column for column in q_frame.columns if str(column).startswith("q_")]
    count = 0
    for column in q_columns:
        if (q_frame[column] > threshold).any():
            count += 1
    return count


def summarize_run(run_dir: str | Path, name: str | None = None, pout: int = 20) -> dict[str, float]:
    run_dir = Path(run_dir)
    name = name or run_dir.name
    medie = load_medie(find_output_file(run_dir, "medie3", name))
    q_frame = load_q(find_output_file(run_dir, "q3", name), pout=pout)
    spikes = load_spikes(find_output_file(run_dir, "spikes3", name), pout=pout)
    start = load_start(find_start_file(run_dir))
    last_half = medie[medie["time_ms"] >= medie["time_ms"].max() / 2]
    return {
        "run": name,
        "sigma": float(medie["sigma"].iloc[-1]),
        "delta": float(medie["delta"].iloc[-1]),
        "rate_mean": float(last_half["rate_hz"].mean()),
        "fano_mean": float(last_half["fano"].mean()),
        "fano_max": float(last_half["fano"].max()),
        "cv_count_mean": float(last_half["cv"].mean()),
        "q_mean": float(q_frame["q_max"].mean()),
        "q_var_mean": float(q_frame["q_var"].mean()),
        "q_max": float(q_frame["q_max"].max()),
        "flexibility_n0": float(flexibility(q_frame)),
        "module_isi_cv": module_isi_cv(spikes, start),
    }

