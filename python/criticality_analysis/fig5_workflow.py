from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from .avalanches import PowerLawFit, avalanche_table, fit_power_law
from .io import find_output_file, load_rate, read_seed
from .seeds import write_seed


MEMORY_FIELDS = (
    "topo",
    "S",
    "Z",
    "P",
    "G",
    "K",
    "sort",
    "swap",
    "range",
    "f",
)


@dataclass(frozen=True)
class FitTargets:
    alpha: float
    beta: float


ROUND1_E0_VALUES = [6.75, 6.80, 6.85, 6.90, 6.95]


def _format_component(value: str | float | int) -> str:
    text = str(value)
    return text.replace(".", "p")


def memory_signature(seed_values: Mapping[str, str]) -> dict[str, str]:
    return {field: str(seed_values.get(field, "")) for field in MEMORY_FIELDS}


def connection_cache_name(seed_values: Mapping[str, str]) -> str:
    return "-".join(
        [
            _format_component(seed_values["S"]),
            _format_component(seed_values["Z"]),
            _format_component(seed_values["G"]),
            _format_component(seed_values["K"]),
            _format_component(seed_values["P"]),
            _format_component(seed_values["sort"]),
            _format_component(seed_values["swap"]),
            _format_component(seed_values["range"]),
            str(seed_values["topo"]),
        ]
    )


def connection_cache_filename(seed_values: Mapping[str, str]) -> str:
    return f"CONNESSIONI5-{connection_cache_name(seed_values)}"


def build_jij_metadata(cache_name: str, seed_values: Mapping[str, str], connection_file: Path) -> dict[str, object]:
    return {
        "cache_name": cache_name,
        "connection_file": str(connection_file),
        "connection_basename": connection_file.name,
        "memory_signature": memory_signature(seed_values),
    }


def validate_jij_metadata(seed_values: Mapping[str, str], metadata: Mapping[str, object]) -> None:
    signature = memory_signature(seed_values)
    stored = metadata.get("memory_signature", {})
    for field, value in signature.items():
        if str(stored.get(field, "")) != value:
            raise ValueError(f"Cached Jij metadata mismatch for {field}: expected {value}, got {stored.get(field, '')}")


def save_jij_metadata(metadata: Mapping[str, object], output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def load_jij_metadata(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prepare_learning_seed(base_seed: str | Path, output_seed: str | Path, cache_dir: str | Path, cache_name: str) -> Path:
    return write_seed(
        base_seed,
        output_seed,
        name=cache_name,
        tmpdir=str(Path(cache_dir).as_posix()),
        file=6,
    )


def prepare_reuse_seed(
    base_seed: str | Path,
    output_seed: str | Path,
    run_name: str,
    *,
    sigma: float | None = None,
    delta: float | None = None,
    bin_ms: float | None = None,
    flush: int | None = None,
    tmax_ms: float | None = None,
    rho: float | None = None,
    alpha: float | None = None,
    seed: int | None = None,
    seed3: int | None = None,
) -> Path:
    updates: dict[str, object] = {
        "name": run_name,
        "tmpdir": "output",
        "file": 1,
    }
    if sigma is not None:
        updates["sigma"] = sigma
    if delta is not None:
        updates["delta"] = delta
    if bin_ms is not None:
        updates["bin"] = bin_ms
    if flush is not None:
        updates["flush"] = flush
    if tmax_ms is not None:
        updates["tmax"] = tmax_ms
    if rho is not None:
        updates["rho"] = rho
    if alpha is not None:
        updates["alpha"] = alpha
    if seed is not None:
        updates["seed"] = seed
    if seed3 is not None:
        updates["seed3"] = seed3
    return write_seed(base_seed, output_seed, **updates)


def materialize_cached_jij(metadata: Mapping[str, object], run_dir: str | Path, seed_values: Mapping[str, str]) -> Path:
    run_dir = Path(run_dir)
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    src = Path(str(metadata["connection_file"]))
    if not src.exists():
        raise FileNotFoundError(f"Cached Jij file not found: {src}")
    dest = output_dir / connection_cache_filename(seed_values)
    shutil.copy2(src, dest)
    return dest


def _simulator_env() -> dict[str, str]:
    env = os.environ.copy()
    msys_bin = r"C:\msys64\ucrt64\bin"
    if Path(msys_bin).exists() and msys_bin not in env.get("PATH", ""):
        env["PATH"] = f"{msys_bin};{env.get('PATH', '')}"
    return env


def run_prepared_simulation(
    executable: str | Path,
    seed_file: str | Path,
    run_root: str | Path,
    run_name: str,
    timeout: int | None = None,
) -> Path:
    executable = Path(executable).resolve()
    if not executable.exists():
        raise FileNotFoundError(f"Simulator executable not found: {executable}")
    seed_file = Path(seed_file).resolve()
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    run_dir = Path(run_root).resolve() / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_file, run_dir / "SEED")
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()

    completed = subprocess.run(
        [str(executable)],
        cwd=run_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        env=_simulator_env(),
    )
    finished_at = datetime.now(timezone.utc)
    runtime_seconds = time.perf_counter() - started_perf
    (run_dir / "run.log").write_text(completed.stdout, encoding="utf-8", errors="replace")
    save_runtime_record(
        {
            "run_name": run_name,
            "seed_file": str(seed_file),
            "executable": str(executable),
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": finished_at.isoformat(),
            "runtime_seconds": runtime_seconds,
            "exit_code": completed.returncode,
        },
        run_dir / "timing.json",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Simulation failed with exit code {completed.returncode}; see {run_dir / 'run.log'}")
    return run_dir


def save_runtime_record(record: Mapping[str, object], output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(record), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def load_runtime_record(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_run_timings(run_dirs: Mapping[str, str | Path]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, run_dir in run_dirs.items():
        timing_path = Path(run_dir) / "timing.json"
        if not timing_path.exists():
            continue
        row = load_runtime_record(timing_path)
        row["label"] = label
        row["run_dir"] = str(Path(run_dir))
        rows.append(row)
    return pd.DataFrame(rows)


def fit_modes_for_series(
    values: pd.Series,
    quantity: str,
    label: str,
    fit_targets: FitTargets,
    *,
    fixed_xmin: float | None = None,
    grid_xmins: list[float] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    target = fit_targets.alpha if quantity == "size" else fit_targets.beta
    selected: list[dict[str, object]] = []
    sensitivity: list[dict[str, object]] = []

    auto_fit = fit_power_law(values)
    selected.append(_fit_row(label, quantity, "auto_xmin", auto_fit, target))

    if fixed_xmin is not None:
        fixed_fit = fit_power_law(values, xmin=fixed_xmin)
        selected.append(_fit_row(label, quantity, "fixed_xmin_paper_like", fixed_fit, target))

    if grid_xmins:
        candidates: list[dict[str, object]] = []
        for candidate in grid_xmins:
            fit = _safe_fit_power_law(values, xmin=candidate)
            if fit is None:
                continue
            row = _fit_row(label, quantity, "grid_search_candidate", fit, target)
            row["candidate_xmin"] = candidate
            sensitivity.append(row)
            candidates.append(row)
        if candidates:
            best = min(candidates, key=lambda item: float(item["abs_distance_to_target"]))
            chosen = dict(best)
            chosen["fit_mode"] = "grid_search_xmin"
            selected.append(chosen)
    return selected, sensitivity


def _fit_row(label: str, quantity: str, fit_mode: str, fit: PowerLawFit, target: float) -> dict[str, object]:
    return {
        "label": label,
        "quantity": quantity,
        "fit_mode": fit_mode,
        "alpha": fit.alpha,
        "sigma": fit.sigma,
        "xmin": fit.xmin,
        "xmax": fit.xmax,
        "ks_distance": fit.ks_distance,
        "likelihood_ratio": fit.likelihood_ratio,
        "p_value": fit.p_value,
        "abs_distance_to_target": abs(fit.alpha - target),
    }


def summarize_target_distances(fit_results: pd.DataFrame, fit_targets: FitTargets) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (label, fit_mode), frame in fit_results.groupby(["label", "fit_mode"], dropna=False):
        size_row = frame[frame["quantity"] == "size"]
        duration_row = frame[frame["quantity"] == "duration_ms"]
        if size_row.empty or duration_row.empty:
            continue
        rows.append(
            {
                "label": label,
                "fit_mode": fit_mode,
                "alpha": float(size_row.iloc[0]["alpha"]),
                "beta": float(duration_row.iloc[0]["alpha"]),
                "abs_distance_to_alpha_target": abs(float(size_row.iloc[0]["alpha"]) - fit_targets.alpha),
                "abs_distance_to_beta_target": abs(float(duration_row.iloc[0]["alpha"]) - fit_targets.beta),
                "score": abs(float(size_row.iloc[0]["alpha"]) - fit_targets.alpha)
                + abs(float(duration_row.iloc[0]["alpha"]) - fit_targets.beta),
            }
        )
    return pd.DataFrame(rows)


def analyze_avalanche_groups(
    avalanches_by_label: Mapping[str, pd.DataFrame],
    *,
    fit_targets: FitTargets,
    fixed_xmins: Mapping[str, float] | None = None,
    grid_xmins: Mapping[str, list[float]] | None = None,
) -> dict[str, pd.DataFrame]:
    fixed_xmins = dict(fixed_xmins or {})
    grid_xmins = {key: list(value) for key, value in (grid_xmins or {}).items()}

    fit_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    raw_rows: list[pd.DataFrame] = []
    for label, avalanches in avalanches_by_label.items():
        frame = avalanches.copy()
        frame.insert(0, "label", label)
        raw_rows.append(frame)
        for quantity in ("size", "duration_ms"):
            selected, sensitivity = fit_modes_for_series(
                frame[quantity],
                quantity,
                label,
                fit_targets,
                fixed_xmin=fixed_xmins.get(quantity),
                grid_xmins=grid_xmins.get(quantity),
            )
            fit_rows.extend(selected)
            sensitivity_rows.extend(sensitivity)

    fit_results = pd.DataFrame(fit_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    target_summary = summarize_target_distances(fit_results, fit_targets)
    raw_avalanches = pd.concat(raw_rows, ignore_index=True) if raw_rows else pd.DataFrame()
    return {
        "raw_avalanches": raw_avalanches,
        "fit_results": fit_results,
        "sensitivity": sensitivity,
        "target_summary": target_summary,
    }


def load_avalanches_from_runs(run_dirs: Mapping[str, str | Path]) -> dict[str, pd.DataFrame]:
    avalanches: dict[str, pd.DataFrame] = {}
    for label, run_dir in run_dirs.items():
        run_dir = Path(run_dir)
        rate = load_rate(find_output_file(run_dir, "rate3", run_dir.name))
        avalanches[label] = avalanche_table(rate)
    return avalanches


def pool_avalanche_groups(
    avalanches_by_label: Mapping[str, pd.DataFrame],
    pooled_label: str = "pooled",
) -> dict[str, pd.DataFrame]:
    pooled = {label: frame.copy() for label, frame in avalanches_by_label.items()}
    if not pooled:
        return pooled
    pooled[pooled_label] = pd.concat([frame.copy() for frame in avalanches_by_label.values()], ignore_index=True)
    return pooled


def parse_run_spec(value: str) -> tuple[str, str]:
    label, run_ref = value.rsplit("=", 1)
    return label, run_ref


def resolve_fit_label(labels: list[str], requested_label: str) -> str:
    if requested_label:
        return requested_label
    if "E0=6.9, I0=1.1" in labels:
        return "E0=6.9, I0=1.1"
    return labels[0]


def canonical_e0_label(e0: float, delta: float = 1.1) -> str:
    return f"E0={e0:.3f}, I0={delta:.1f}"


def campaign_run_name(prefix: str, e0: float, seed_index: int) -> str:
    return f"{prefix}_e{e0:.3f}_seed{seed_index:02d}".replace(".", "p")


def build_campaign_manifest(
    prefix: str,
    e0_values: list[float],
    seed_values: list[int],
    *,
    delta: float,
    bin_ms: float,
    flush: int,
    tmax_ms: float,
    rho: float,
    alpha: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for e0 in e0_values:
        group_label = canonical_e0_label(e0, delta)
        for idx, seed_value in enumerate(seed_values, start=1):
            rows.append(
                {
                    "run_name": campaign_run_name(prefix, e0, idx),
                    "label": f"{group_label}, seed={idx}",
                    "group_label": group_label,
                    "sigma": e0,
                    "delta": delta,
                    "seed": seed_value,
                    "seed_index": idx,
                    "bin_ms": bin_ms,
                    "flush": flush,
                    "tmax_ms": tmax_ms,
                    "rho": rho,
                    "alpha": alpha,
                }
            )
    return pd.DataFrame(rows)


def build_seed_series(seed_start: int, count: int, step: int = 1) -> list[int]:
    return [seed_start + index * step for index in range(count)]


def build_refinement_e0_values(center: float, step: float = 0.025, radius: int = 2) -> list[float]:
    return [round(center + step * offset, 3) for offset in range(-radius, radius + 1)]


def save_manifest(manifest: pd.DataFrame, output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(output, index=False)
    return output


def load_manifest(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def manifest_run_dirs(manifest: pd.DataFrame, run_root: str | Path) -> dict[str, Path]:
    base = Path(run_root)
    return {str(row["label"]): base / str(row["run_name"]) for _, row in manifest.iterrows()}


def pooled_groups_from_manifest(
    avalanches_by_label: Mapping[str, pd.DataFrame],
    manifest: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    grouped: dict[str, list[pd.DataFrame]] = {}
    label_to_group = dict(zip(manifest["label"], manifest["group_label"], strict=False))
    for label, frame in avalanches_by_label.items():
        group_label = str(label_to_group[label])
        grouped.setdefault(group_label, []).append(frame.copy())
    return {group_label: pd.concat(frames, ignore_index=True) for group_label, frames in grouped.items()}


def summarize_campaign(
    fit_results: pd.DataFrame,
    manifest: pd.DataFrame,
    *,
    fit_mode: str,
    fit_targets: FitTargets,
    timings: pd.DataFrame | None = None,
) -> pd.DataFrame:
    timings = timings if timings is not None else pd.DataFrame()
    selected = fit_results[fit_results["fit_mode"] == fit_mode].copy()
    pooled_rows = selected[selected["label"].isin(set(manifest["group_label"]))].copy()
    seed_rows = selected[selected["label"].isin(set(manifest["label"]))].copy()
    rows: list[dict[str, object]] = []
    for group_label in manifest["group_label"].drop_duplicates():
        pooled_frame = pooled_rows[pooled_rows["label"] == group_label]
        if pooled_frame.empty:
            continue
        size_row = pooled_frame[pooled_frame["quantity"] == "size"].iloc[0]
        duration_row = pooled_frame[pooled_frame["quantity"] == "duration_ms"].iloc[0]
        seed_frame = seed_rows[seed_rows["label"].isin(set(manifest.loc[manifest["group_label"] == group_label, "label"]))]
        size_seed = seed_frame[seed_frame["quantity"] == "size"]["alpha"].astype(float)
        duration_seed = seed_frame[seed_frame["quantity"] == "duration_ms"]["alpha"].astype(float)
        run_slice = manifest[manifest["group_label"] == group_label]
        timing_slice = timings[timings["label"].isin(set(run_slice["label"]))] if not timings.empty else pd.DataFrame()
        rows.append(
            {
                "label": group_label,
                "sigma": float(run_slice.iloc[0]["sigma"]),
                "delta": float(run_slice.iloc[0]["delta"]),
                "seed_count": int(run_slice["seed_index"].nunique()),
                "tmax_ms": float(run_slice["tmax_ms"].max()),
                "pooled_alpha": float(size_row["alpha"]),
                "pooled_beta": float(duration_row["alpha"]),
                "alpha_target_distance": abs(float(size_row["alpha"]) - fit_targets.alpha),
                "beta_target_distance": abs(float(duration_row["alpha"]) - fit_targets.beta),
                "score": abs(float(size_row["alpha"]) - fit_targets.alpha) + abs(float(duration_row["alpha"]) - fit_targets.beta),
                "single_seed_alpha_mean": float(size_seed.mean()),
                "single_seed_alpha_std": float(size_seed.std(ddof=0)) if not size_seed.empty else 0.0,
                "single_seed_beta_mean": float(duration_seed.mean()),
                "single_seed_beta_std": float(duration_seed.std(ddof=0)) if not duration_seed.empty else 0.0,
                "runtime_seconds_total": float(timing_slice["runtime_seconds"].astype(float).sum()) if not timing_slice.empty else 0.0,
                "runtime_seconds_mean": float(timing_slice["runtime_seconds"].astype(float).mean()) if not timing_slice.empty else 0.0,
            }
        )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(["score", "single_seed_alpha_std", "single_seed_beta_std", "sigma"], ignore_index=True)


def detect_best_sigma(summary: pd.DataFrame) -> float:
    if summary.empty:
        raise ValueError("Campaign summary is empty; cannot select best sigma.")
    return float(summary.iloc[0]["sigma"])


def parse_sigma_from_label(label: str) -> float | None:
    match = re.search(r"E0=([0-9.]+)", label)
    if not match:
        return None
    return float(match.group(1))


def summarize_runtime_table(timings: pd.DataFrame) -> pd.DataFrame:
    if timings.empty:
        return pd.DataFrame(
            columns=[
                "label",
                "run_count",
                "runtime_seconds_total",
                "runtime_seconds_mean",
                "runtime_seconds_min",
                "runtime_seconds_max",
            ]
        )
    frame = timings.copy()
    frame["runtime_seconds"] = frame["runtime_seconds"].astype(float)
    grouped = (
        frame.groupby("label", dropna=False)["runtime_seconds"]
        .agg(["count", "sum", "mean", "min", "max"])
        .reset_index()
        .rename(
            columns={
                "count": "run_count",
                "sum": "runtime_seconds_total",
                "mean": "runtime_seconds_mean",
                "min": "runtime_seconds_min",
                "max": "runtime_seconds_max",
            }
        )
    )
    return grouped


def _safe_fit_power_law(values: pd.Series, xmin: float) -> PowerLawFit | None:
    data = values.to_numpy(dtype=float)
    data = data[pd.notna(data)]
    if not (data > 0).any() or (data >= xmin).sum() < 2:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return fit_power_law(values, xmin=xmin)
        except ValueError:
            return None
