from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from criticality_analysis.io import find_output_file, load_medie, load_q, read_seed
from criticality_analysis.seeds import write_seed


@dataclass(frozen=True)
class Task:
    run_name: str
    e0: float
    i0: float
    seed_path: Path
    run_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and summarize the Fig.3 E0/I0 parameter-space workflow.")
    parser.add_argument("--config", default="configs/fig3_full_grid.json", help="JSON configuration path.")
    parser.add_argument("--workers", type=int, default=None, help="Parallel simulation workers.")
    parser.add_argument("--resume", action="store_true", help="Skip runs with complete q3/medie3 outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned tasks without writing seeds or running simulations.")
    parser.add_argument("--generate-only", action="store_true", help="Generate SEED files, then stop.")
    parser.add_argument("--summarize-only", action="store_true", help="Do not run simulations; only summarize existing outputs.")
    parser.add_argument("--limit", type=int, default=None, help="Limit task count for validation.")
    parser.add_argument("--timeout", type=int, default=None, help="Per-simulation timeout in seconds.")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = resolve_path(path)
    with config_path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    config["_config_path"] = str(config_path)
    return config


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    n_steps = int(round((stop - start) / step))
    for index in range(n_steps + 1):
        value = start + index * step
        values.append(round(value, 10))
    return values


def fmt_float(value: float) -> str:
    text = f"{value:g}".replace("-", "m").replace(".", "p")
    return text


def build_tasks(config: dict[str, Any]) -> list[Task]:
    e0_values = frange(**config["e0"])
    i0_values = frange(**config["i0"])
    seed_dir = resolve_path(config["generated_config_dir"])
    run_root = resolve_path(config["run_root"])
    prefix = config["name"]
    tasks: list[Task] = []
    for i0 in i0_values:
        for e0 in e0_values:
            run_name = f"{prefix}_e{fmt_float(e0)}_i{fmt_float(i0)}"
            tasks.append(
                Task(
                    run_name=run_name,
                    e0=e0,
                    i0=i0,
                    seed_path=seed_dir / f"{run_name}.seed",
                    run_dir=run_root / run_name,
                )
            )
    return tasks


def executable_path(config: dict[str, Any]) -> Path:
    configured = resolve_path(config["executable"])
    candidates = [configured]
    if configured.suffix == "":
        candidates.append(configured.with_suffix(".exe"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return configured


def expected_outputs(task: Task) -> tuple[Path, Path]:
    output_dir = task.run_dir / "output"
    return output_dir / f"q3-{task.run_name}.dat", output_dir / f"medie3-{task.run_name}.dat"


def has_complete_outputs(task: Task) -> bool:
    q_file, medie_file = expected_outputs(task)
    return q_file.exists() and q_file.stat().st_size > 0 and medie_file.exists() and medie_file.stat().st_size > 0


def generate_seed(config: dict[str, Any], task: Task) -> None:
    updates = {
        **config["seed_updates"],
        "name": task.run_name,
        "sigma": task.e0,
        "delta": task.i0,
    }
    write_seed(resolve_path(config["base_seed"]), task.seed_path, **updates)


def generate_seeds(config: dict[str, Any], tasks: list[Task]) -> None:
    for task in tasks:
        generate_seed(config, task)


def run_one(task_data: dict[str, str | int | None]) -> tuple[str, int, str]:
    task = Task(
        run_name=str(task_data["run_name"]),
        e0=float(task_data["e0"]),
        i0=float(task_data["i0"]),
        seed_path=Path(str(task_data["seed_path"])),
        run_dir=Path(str(task_data["run_dir"])),
    )
    executable = Path(str(task_data["executable"]))
    timeout = task_data.get("timeout")
    task.run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(task.seed_path, task.run_dir / "SEED")
    output_dir = task.run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    stdout_file = task.run_dir / "stdout.log"
    stderr_file = task.run_dir / "stderr.log"
    run_log = task.run_dir / "run.log"
    try:
        completed = subprocess.run(
            [str(executable)],
            cwd=task.run_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=None if timeout is None else int(timeout),
            check=False,
        )
        stdout_file.write_text(completed.stdout, encoding="utf-8", errors="replace")
        stderr_file.write_text(completed.stderr, encoding="utf-8", errors="replace")
        run_log.write_text(
            f"started={started}\nfinished={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"exit_code={completed.returncode}\n\n[stdout]\n{completed.stdout}\n\n[stderr]\n{completed.stderr}\n",
            encoding="utf-8",
            errors="replace",
        )
        return task.run_name, int(completed.returncode), "" if completed.returncode == 0 else str(run_log)
    except Exception as exc:  # noqa: BLE001 - batch runner must capture failures.
        run_log.write_text(
            f"started={started}\nfinished={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"exception={exc!r}\n",
            encoding="utf-8",
            errors="replace",
        )
        return task.run_name, 1, repr(exc)


def run_tasks(config: dict[str, Any], tasks: list[Task], workers: int, resume: bool, timeout: int | None) -> None:
    log_dir = resolve_path(config["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "fig3_full_pipeline.log"
    executable = executable_path(config)
    if not executable.exists():
        raise FileNotFoundError(f"Simulator executable not found: {executable}")

    pending = [task for task in tasks if not (resume and has_complete_outputs(task))]
    append_log(log_path, f"planned={len(tasks)} pending={len(pending)} workers={workers} executable={executable}")
    if not pending:
        append_log(log_path, "No pending simulations.")
        return

    payloads = [
        {
            "run_name": task.run_name,
            "e0": task.e0,
            "i0": task.i0,
            "seed_path": str(task.seed_path),
            "run_dir": str(task.run_dir),
            "executable": str(executable),
            "timeout": timeout,
        }
        for task in pending
    ]
    done = 0
    failed = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, payload) for payload in payloads]
        for future in as_completed(futures):
            run_name, exit_code, message = future.result()
            done += 1
            if exit_code != 0:
                failed += 1
            append_log(log_path, f"{done}/{len(pending)} {run_name} exit={exit_code} {message}")
    append_log(log_path, f"finished pending={len(pending)} failed={failed}")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def summarize_task(config: dict[str, Any], task: Task) -> dict[str, Any]:
    seed_values = read_seed(task.seed_path) if task.seed_path.exists() else {}
    row: dict[str, Any] = {
        "run_name": task.run_name,
        "E0": task.e0,
        "I0": task.i0,
        "seed": seed_values.get("seed", config["seed_updates"].get("seed")),
        "bin_ms": float(seed_values.get("bin", config["seed_updates"].get("bin", np.nan))),
        "tmax_ms": float(seed_values.get("tmax", config["seed_updates"].get("tmax", np.nan))),
        "Q_mean": np.nan,
        "chi_Q": np.nan,
        "Q_max": np.nan,
        "rate_mean": np.nan,
        "fano_mean": np.nan,
        "cv_count_mean": np.nan,
        "flexibility_n0": np.nan,
        "status": "missing",
        "output_dir": str(task.run_dir / "output"),
    }
    try:
        if not has_complete_outputs(task):
            return row
        analysis = config.get("analysis", {})
        pout = int(analysis.get("pout", 20))
        last_fraction = float(analysis.get("last_fraction", 0.5))
        threshold = float(analysis.get("replay_threshold", 0.8))
        medie = load_medie(find_output_file(task.run_dir, "medie3", task.run_name))
        q_frame = load_q(find_output_file(task.run_dir, "q3", task.run_name), pout=pout)
        medie_last = last_fraction_frame(medie, "time_ms", last_fraction)
        q_last = last_fraction_frame(q_frame, "t_end", last_fraction)
        q_columns = [column for column in q_last.columns if str(column).startswith("q_")]
        row.update(
            {
                "Q_mean": float(q_last["q_max"].mean()),
                "chi_Q": float(q_last["q_var"].mean()),
                "Q_max": float(q_last["q_max"].max()),
                "rate_mean": float(medie_last["rate_hz"].mean()),
                "fano_mean": float(medie_last["fano"].mean()),
                "cv_count_mean": float(medie_last["cv"].mean()),
                "flexibility_n0": int(sum((q_last[column] > threshold).any() for column in q_columns)),
                "status": "ok",
            }
        )
    except Exception as exc:  # noqa: BLE001 - summary table should retain failures.
        row["status"] = f"error: {exc}"
    return row


def last_fraction_frame(frame: pd.DataFrame, time_column: str, last_fraction: float) -> pd.DataFrame:
    if frame.empty or time_column not in frame:
        return frame
    max_time = float(frame[time_column].max())
    cutoff = max_time * (1.0 - last_fraction)
    return frame[frame[time_column] >= cutoff]


def summarize(config: dict[str, Any], tasks: list[Task]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    table_dir = resolve_path(config["table_dir"])
    table_dir.mkdir(parents=True, exist_ok=True)
    rows = [summarize_task(config, task) for task in tasks]
    summary = pd.DataFrame(rows)
    summary.to_csv(table_dir / "fig3_parameter_space_summary.csv", index=False)
    missing = summary[summary["status"] != "ok"].copy()
    missing.to_csv(table_dir / "fig3_missing_or_failed_runs.csv", index=False)
    ok = summary[summary["status"] == "ok"].copy()
    critical = chi_peak_line(ok)
    transition = q_gradient_line(ok)
    critical.to_csv(table_dir / "fig3_critical_line_chiQ_peak.csv", index=False)
    transition.to_csv(table_dir / "fig3_transition_line_Q_gradient.csv", index=False)
    return summary, critical, transition


def chi_peak_line(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if summary.empty:
        return pd.DataFrame(rows)
    for i0, group in summary.groupby("I0"):
        group = group.sort_values("E0").reset_index(drop=True)
        if group.empty or group["chi_Q"].isna().all():
            continue
        peak_idx = int(group["chi_Q"].astype(float).idxmax())
        peak = group.loc[peak_idx]
        e_interp, flag = parabolic_peak(group["E0"].to_numpy(float), group["chi_Q"].to_numpy(float), peak_idx)
        rows.append(
            {
                "I0": float(i0),
                "E0_peak_grid": float(peak["E0"]),
                "E0_peak_interp": e_interp,
                "chi_Q_peak": float(peak["chi_Q"]),
                "Q_at_peak": float(peak["Q_mean"]),
                "rate_at_peak": float(peak["rate_mean"]),
                "fano_at_peak": float(peak["fano_mean"]),
                "flexibility_at_peak": float(peak["flexibility_n0"]),
                "run_name": peak["run_name"],
                "confidence_flag": flag,
            }
        )
    return pd.DataFrame(rows)


def q_gradient_line(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if summary.empty:
        return pd.DataFrame(rows)
    for i0, group in summary.groupby("I0"):
        group = group.sort_values("E0").reset_index(drop=True)
        if len(group) < 2 or group["Q_mean"].isna().all():
            continue
        e0 = group["E0"].to_numpy(float)
        q = group["Q_mean"].to_numpy(float)
        gradient = np.gradient(q, e0)
        if np.all(~np.isfinite(gradient)):
            continue
        finite_gradient = np.where(np.isfinite(gradient), gradient, -np.inf)
        grad_idx = int(np.argmax(finite_gradient))
        e_interp, flag = parabolic_peak(e0, finite_gradient, grad_idx)
        before_idx = max(0, grad_idx - 1)
        after_idx = min(len(group) - 1, grad_idx + 1)
        near = group.loc[grad_idx]
        rows.append(
            {
                "I0": float(i0),
                "E0_transition_grid": float(near["E0"]),
                "E0_transition_interp": e_interp,
                "max_dQ_dE0": float(finite_gradient[grad_idx]),
                "Q_before": float(group.loc[before_idx, "Q_mean"]),
                "Q_after": float(group.loc[after_idx, "Q_mean"]),
                "chi_Q_near_transition": float(near["chi_Q"]),
                "rate_near_transition": float(near["rate_mean"]),
                "run_name": near["run_name"],
                "confidence_flag": flag,
            }
        )
    return pd.DataFrame(rows)


def parabolic_peak(x: np.ndarray, y: np.ndarray, index: int) -> tuple[float, str]:
    if index <= 0 or index >= len(x) - 1:
        return float(x[index]), "edge_peak_no_interp"
    x3 = x[index - 1 : index + 2]
    y3 = y[index - 1 : index + 2]
    if not np.all(np.isfinite(x3)) or not np.all(np.isfinite(y3)):
        return float(x[index]), "nonfinite_no_interp"
    try:
        a, b, _ = np.polyfit(x3, y3, deg=2)
        if a >= 0:
            return float(x[index]), "not_concave_no_interp"
        peak = -b / (2 * a)
        if peak < x3.min() or peak > x3.max():
            return float(x[index]), "interp_outside_no_interp"
        return float(peak), "interpolated"
    except Exception:  # noqa: BLE001
        return float(x[index]), "interp_failed"


def plot_all(config: dict[str, Any], summary: pd.DataFrame, critical: pd.DataFrame, transition: pd.DataFrame) -> None:
    ok = summary[summary["status"] == "ok"].copy()
    figure_dir = resolve_path(config["figure_dir"])
    figure_dir.mkdir(parents=True, exist_ok=True)
    if ok.empty:
        return
    plot_heatmap(
        ok,
        metric="Q_mean",
        title="Order parameter",
        colorbar_label="Q",
        output=figure_dir / "fig3_order_parameter_Q_full.png",
        critical=critical,
        transition=transition,
        log_color=False,
    )
    plot_heatmap(
        ok,
        metric="chi_Q",
        title="Order parameter fluctuations",
        colorbar_label="chi_Q",
        output=figure_dir / "fig3_order_parameter_fluctuations_chiQ_full.png",
        critical=critical,
        transition=transition,
        log_color=True,
    )
    plot_combined(ok, critical, transition, figure_dir / "fig3_parameter_space_full.png")


def plot_heatmap(
    summary: pd.DataFrame,
    metric: str,
    title: str,
    colorbar_label: str,
    output: Path,
    critical: pd.DataFrame,
    transition: pd.DataFrame,
    log_color: bool,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    pivot = pivot_metric(summary, metric)
    values = pivot.to_numpy(float)
    fig, ax = plt.subplots(figsize=(5.2, 4.0), dpi=220)
    extent = [pivot.columns.min(), pivot.columns.max(), pivot.index.min(), pivot.index.max()]
    norm = None
    if log_color:
        positive = values[np.isfinite(values) & (values > 0)]
        if positive.size:
            norm = LogNorm(vmin=max(positive.min(), 1e-6), vmax=positive.max())
    image = ax.imshow(values, origin="lower", aspect="auto", extent=extent, interpolation="nearest", norm=norm)
    overlay_lines(ax, critical, transition)
    ax.set_xlabel("E0")
    ax.set_ylabel("I0")
    ax.set_title(title)
    fig.colorbar(image, ax=ax, label=colorbar_label)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_combined(summary: pd.DataFrame, critical: pd.DataFrame, transition: pd.DataFrame, output: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=220)
    for ax, metric, title, label, log_color in [
        (axes[0], "Q_mean", "Order parameter", "Q", False),
        (axes[1], "chi_Q", "Order parameter fluctuations", "chi_Q", True),
    ]:
        pivot = pivot_metric(summary, metric)
        values = pivot.to_numpy(float)
        extent = [pivot.columns.min(), pivot.columns.max(), pivot.index.min(), pivot.index.max()]
        norm = None
        if log_color:
            positive = values[np.isfinite(values) & (values > 0)]
            if positive.size:
                norm = LogNorm(vmin=max(positive.min(), 1e-6), vmax=positive.max())
        image = ax.imshow(values, origin="lower", aspect="auto", extent=extent, interpolation="nearest", norm=norm)
        overlay_lines(ax, critical, transition)
        ax.set_xlabel("E0")
        ax.set_ylabel("I0")
        ax.set_title(title)
        fig.colorbar(image, ax=ax, label=label)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def pivot_metric(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    return summary.pivot_table(index="I0", columns="E0", values=metric, aggfunc="mean").sort_index().sort_index(axis=1)


def overlay_lines(ax: Any, critical: pd.DataFrame, transition: pd.DataFrame) -> None:
    if not critical.empty:
        ax.plot(critical["E0_peak_interp"], critical["I0"], color="black", linewidth=1.6, marker="o", markersize=2.2, label="chi_Q peak")
    if not transition.empty:
        ax.plot(
            transition["E0_transition_interp"],
            transition["I0"],
            color="white",
            linewidth=1.1,
            linestyle="--",
            marker=".",
            markersize=2.0,
            label="max dQ/dE0",
        )
    ax.legend(frameon=True, fontsize=6, loc="best")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    tasks = build_tasks(config)
    if args.limit is not None:
        tasks = tasks[: args.limit]
    workers = args.workers or min(4, max(1, (os_cpu_count() or 1)))

    if args.dry_run:
        print(f"config={config['_config_path']}")
        print(f"tasks={len(tasks)}")
        print(f"workers={workers}")
        if tasks:
            print(f"first={tasks[0]}")
            print(f"last={tasks[-1]}")
        return

    generate_seeds(config, tasks)
    if args.generate_only:
        print(f"Generated {len(tasks)} seed files in {resolve_path(config['generated_config_dir'])}")
        return

    if not args.summarize_only:
        run_tasks(config, tasks, workers=workers, resume=args.resume, timeout=args.timeout)

    summary, critical, transition = summarize(config, tasks)
    plot_all(config, summary, critical, transition)
    print(f"Summary rows: {len(summary)}")
    print(f"Critical line rows: {len(critical)}")
    print(f"Transition line rows: {len(transition)}")
    print(f"Tables: {resolve_path(config['table_dir'])}")
    print(f"Figures: {resolve_path(config['figure_dir'])}")


def os_cpu_count() -> int | None:
    try:
        import os

        return os.cpu_count()
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    main()
