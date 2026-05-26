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
    stage: str
    run_name: str
    e0: float
    i0: float
    seed_path: Path
    run_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locate Fig.3 critical lines with coarse-to-refined E0/I0 searches.")
    parser.add_argument("--config", default="configs/fig3_critical_search.json", help="JSON configuration path.")
    parser.add_argument("--workers", type=int, default=None, help="Parallel simulation workers.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned coarse search and exit.")
    parser.add_argument("--summarize-only", action="store_true", help="Summarize an existing run root without simulations.")
    parser.add_argument("--run-id", default=None, help="Optional subdirectory under run_root/generated_config_dir/log_dir.")
    parser.add_argument("--limit-i0", type=int, default=None, help="Limit I0 rows for validation runs.")
    parser.add_argument("--timeout", type=int, default=None, help="Per-simulation timeout in seconds.")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = resolve_path(path)
    with config_path.open("r", encoding="utf-8-sig") as stream:
        config = json.load(stream)
    config["_config_path"] = str(config_path)
    return config


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def scoped_path(config: dict[str, Any], key: str, run_id: str | None) -> Path:
    base = resolve_path(config[key])
    return base / run_id if run_id else base


def os_cpu_count() -> int | None:
    try:
        import os

        return os.cpu_count()
    except Exception:  # noqa: BLE001
        return None


def frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    n_steps = int(round((stop - start) / step))
    for index in range(n_steps + 1):
        values.append(round(start + index * step, 10))
    return values


def fmt_float(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def executable_path(config: dict[str, Any]) -> Path:
    configured = resolve_path(config["executable"])
    candidates = [configured]
    if configured.suffix == "":
        candidates.append(configured.with_suffix(".exe"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return configured


def i0_values(config: dict[str, Any], limit_i0: int | None) -> list[float]:
    values = frange(**config["i0"])
    if limit_i0 is not None:
        values = values[: max(0, limit_i0)]
    return values


def stage_seed_dir(config: dict[str, Any], run_id: str | None, stage: str) -> Path:
    return scoped_path(config, "generated_config_dir", run_id) / stage


def stage_run_dir(config: dict[str, Any], run_id: str | None, stage: str) -> Path:
    return scoped_path(config, "run_root", run_id) / stage


def build_task(config: dict[str, Any], run_id: str | None, stage: str, e0: float, i0: float) -> Task:
    prefix = config["name"]
    run_name = f"{prefix}_{stage}_e{fmt_float(e0)}_i{fmt_float(i0)}"
    return Task(
        stage=stage,
        run_name=run_name,
        e0=e0,
        i0=i0,
        seed_path=stage_seed_dir(config, run_id, stage) / f"{run_name}.seed",
        run_dir=stage_run_dir(config, run_id, stage) / run_name,
    )


def build_coarse_tasks(config: dict[str, Any], run_id: str | None, limit_i0: int | None) -> list[Task]:
    e0 = frange(**config["coarse_e0"])
    return [build_task(config, run_id, "coarse", e, i) for i in i0_values(config, limit_i0) for e in e0]


def build_refine_tasks(config: dict[str, Any], run_id: str | None, coarse_summary: pd.DataFrame) -> list[Task]:
    refine = config["refine"]
    width = float(refine["half_width"])
    step = float(refine["step"])
    e_min = float(config["coarse_e0"]["start"])
    e_max = float(config["coarse_e0"]["stop"])
    tasks: list[Task] = []
    if coarse_summary.empty:
        return tasks
    ok = coarse_summary[coarse_summary["status"] == "ok"].copy()
    for i0, group in ok.groupby("I0"):
        group = group.sort_values("E0").reset_index(drop=True)
        if group.empty or group["chi_Q"].isna().all():
            continue
        peak = float(group.loc[int(group["chi_Q"].astype(float).idxmax()), "E0"])
        start = max(e_min, round(peak - width, 10))
        stop = min(e_max, round(peak + width, 10))
        for e0 in frange(start, stop, step):
            tasks.append(build_task(config, run_id, "refine", e0, float(i0)))
    return tasks


def expected_outputs(task: Task) -> tuple[Path, Path]:
    output_dir = task.run_dir / "output"
    return output_dir / f"q3-{task.run_name}.dat", output_dir / f"medie3-{task.run_name}.dat"


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
        task.seed_path.parent.mkdir(parents=True, exist_ok=True)
        generate_seed(config, task)


def run_one(task_data: dict[str, str | int | float | None]) -> tuple[str, str, int, str]:
    task = Task(
        stage=str(task_data["stage"]),
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
    (task.run_dir / "output").mkdir(parents=True, exist_ok=True)
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
            f"stage={task.stage}\nstarted={started}\nfinished={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"exit_code={completed.returncode}\n\n[stdout]\n{completed.stdout}\n\n[stderr]\n{completed.stderr}\n",
            encoding="utf-8",
            errors="replace",
        )
        return task.stage, task.run_name, int(completed.returncode), "" if completed.returncode == 0 else str(run_log)
    except Exception as exc:  # noqa: BLE001
        run_log.write_text(
            f"stage={task.stage}\nstarted={started}\nfinished={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"exception={exc!r}\n",
            encoding="utf-8",
            errors="replace",
        )
        return task.stage, task.run_name, 1, repr(exc)


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def write_status(path: Path, status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def format_seconds(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "unknown"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


def run_tasks(
    config: dict[str, Any],
    run_id: str | None,
    stage: str,
    tasks: list[Task],
    workers: int,
    timeout: int | None,
) -> None:
    log_dir = scoped_path(config, "log_dir", run_id)
    progress_log = log_dir / "fig3_critical_progress.log"
    status_path = log_dir / "fig3_critical_status.json"
    executable = executable_path(config)
    if not executable.exists():
        raise FileNotFoundError(f"Simulator executable not found: {executable}")
    if not tasks:
        append_log(progress_log, f"stage={stage} total=0 skipped")
        return

    append_log(progress_log, f"stage={stage} total={len(tasks)} workers={workers} executable={executable}")
    payloads = [
        {
            "stage": task.stage,
            "run_name": task.run_name,
            "e0": task.e0,
            "i0": task.i0,
            "seed_path": str(task.seed_path),
            "run_dir": str(task.run_dir),
            "executable": str(executable),
            "timeout": timeout,
        }
        for task in tasks
    ]
    started = time.time()
    done = 0
    failed = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, payload) for payload in payloads]
        for future in as_completed(futures):
            task_stage, run_name, exit_code, message = future.result()
            done += 1
            failed += int(exit_code != 0)
            elapsed = time.time() - started
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(tasks) - done) / rate if rate > 0 else None
            append_log(
                progress_log,
                (
                    f"stage={task_stage} done={done}/{len(tasks)} ok={done - failed} failed={failed} "
                    f"elapsed={format_seconds(elapsed)} eta={format_seconds(eta)} current={run_name} "
                    f"exit={exit_code} {message}"
                ),
            )
            write_status(
                status_path,
                {
                    "stage": task_stage,
                    "done": done,
                    "total": len(tasks),
                    "ok": done - failed,
                    "failed": failed,
                    "elapsed_seconds": round(elapsed, 2),
                    "eta_seconds": None if eta is None else round(eta, 2),
                    "current": run_name,
                    "exit_code": exit_code,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
    append_log(progress_log, f"stage={stage} finished total={len(tasks)} failed={failed}")


def output_complete(task: Task) -> bool:
    q_file, medie_file = expected_outputs(task)
    return q_file.exists() and q_file.stat().st_size > 0 and medie_file.exists() and medie_file.stat().st_size > 0


def summarize_task(config: dict[str, Any], task: Task) -> dict[str, Any]:
    seed_values = read_seed(task.seed_path) if task.seed_path.exists() else {}
    row: dict[str, Any] = {
        "stage": task.stage,
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
        if not output_complete(task):
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
    except Exception as exc:  # noqa: BLE001
        row["status"] = f"error: {exc}"
    return row


def last_fraction_frame(frame: pd.DataFrame, time_column: str, last_fraction: float) -> pd.DataFrame:
    if frame.empty or time_column not in frame:
        return frame
    cutoff = float(frame[time_column].max()) * (1.0 - last_fraction)
    return frame[frame[time_column] >= cutoff]


def summarize_tasks(config: dict[str, Any], tasks: list[Task]) -> pd.DataFrame:
    return pd.DataFrame([summarize_task(config, task) for task in tasks])


def best_rows(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    ok = summary[summary["status"] == "ok"].copy()
    if ok.empty:
        return ok
    ok["stage_rank"] = ok["stage"].map({"coarse": 0, "refine": 1}).fillna(0)
    ok = ok.sort_values(["I0", "E0", "stage_rank"])
    return ok.drop_duplicates(["I0", "E0"], keep="last").drop(columns=["stage_rank"])


def write_tables(config: dict[str, Any], run_id: str | None, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    table_dir = scoped_path(config, "table_dir", run_id)
    table_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(table_dir / "fig3_parameter_space_summary.csv", index=False)
    missing = summary[summary["status"] != "ok"].copy()
    missing.to_csv(table_dir / "fig3_missing_or_failed_runs.csv", index=False)
    ok = best_rows(summary)
    critical = chi_peak_line(ok)
    transition = q_gradient_line(ok)
    critical.to_csv(table_dir / "fig3_critical_line_chiQ_peak.csv", index=False)
    transition.to_csv(table_dir / "fig3_transition_line_Q_gradient.csv", index=False)
    return ok, critical, transition


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
        finite_gradient = np.where(np.isfinite(gradient), gradient, -np.inf)
        if np.all(finite_gradient == -np.inf):
            continue
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
        return float(x[index]), "edge_peak"
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


def plot_all(config: dict[str, Any], run_id: str | None, summary: pd.DataFrame, critical: pd.DataFrame, transition: pd.DataFrame) -> None:
    figure_dir = scoped_path(config, "figure_dir", run_id)
    figure_dir.mkdir(parents=True, exist_ok=True)
    if summary.empty:
        return
    plot_combined(summary, critical, transition, figure_dir / "fig3_parameter_space_critical_search.png")
    plot_heatmap(
        summary,
        metric="chi_Q",
        title="Order parameter fluctuations",
        colorbar_label="chi_Q",
        output=figure_dir / "fig3_chiQ_critical_line.png",
        critical=critical,
        transition=transition,
        log_color=True,
    )


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
    fig, ax = plt.subplots(figsize=(5.4, 4.1), dpi=220)
    extent = [pivot.columns.min(), pivot.columns.max(), pivot.index.min(), pivot.index.max()]
    norm = log_norm(values) if log_color else None
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

    fig, axes = plt.subplots(1, 2, figsize=(10.7, 4.1), dpi=220)
    for ax, metric, title, label, use_log in [
        (axes[0], "Q_mean", "Order parameter", "Q", False),
        (axes[1], "chi_Q", "Order parameter fluctuations", "chi_Q", True),
    ]:
        pivot = pivot_metric(summary, metric)
        values = pivot.to_numpy(float)
        extent = [pivot.columns.min(), pivot.columns.max(), pivot.index.min(), pivot.index.max()]
        image = ax.imshow(values, origin="lower", aspect="auto", extent=extent, interpolation="nearest", norm=log_norm(values) if use_log else None)
        overlay_lines(ax, critical, transition)
        ax.set_xlabel("E0")
        ax.set_ylabel("I0")
        ax.set_title(title)
        fig.colorbar(image, ax=ax, label=label)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def log_norm(values: np.ndarray) -> Any:
    from matplotlib.colors import LogNorm

    positive = values[np.isfinite(values) & (values > 0)]
    if positive.size == 0:
        return None
    return LogNorm(vmin=max(float(positive.min()), 1e-6), vmax=float(positive.max()))


def pivot_metric(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    return summary.pivot_table(index="I0", columns="E0", values=metric, aggfunc="mean").sort_index().sort_index(axis=1)


def overlay_lines(ax: Any, critical: pd.DataFrame, transition: pd.DataFrame) -> None:
    if not critical.empty:
        ax.plot(critical["E0_peak_interp"], critical["I0"], color="black", linewidth=1.7, marker="o", markersize=2.2, label="chi_Q peak")
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


def ensure_fresh_run_root(config: dict[str, Any], run_id: str | None) -> None:
    run_root = scoped_path(config, "run_root", run_id)
    if run_root.exists():
        raise FileExistsError(
            f"Run root already exists: {run_root}. This workflow has no resume mode; "
            "choose --run-id for a new run or remove the old directory intentionally."
        )


def collect_existing_tasks(config: dict[str, Any], run_id: str | None) -> list[Task]:
    tasks: list[Task] = []
    for stage in ["coarse", "refine"]:
        seed_dir = stage_seed_dir(config, run_id, stage)
        if not seed_dir.exists():
            continue
        for seed_path in sorted(seed_dir.glob("*.seed")):
            seed_values = read_seed(seed_path)
            e0 = float(seed_values["sigma"])
            i0 = float(seed_values["delta"])
            run_name = seed_path.stem
            tasks.append(
                Task(
                    stage=stage,
                    run_name=run_name,
                    e0=e0,
                    i0=i0,
                    seed_path=seed_path,
                    run_dir=stage_run_dir(config, run_id, stage) / run_name,
                )
            )
    return tasks


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    workers = args.workers or min(4, max(1, os_cpu_count() or 1))
    coarse_tasks = build_coarse_tasks(config, args.run_id, args.limit_i0)

    if args.dry_run:
        max_refine = len(i0_values(config, args.limit_i0)) * (int(round((2 * float(config["refine"]["half_width"])) / float(config["refine"]["step"]))) + 1)
        print(f"config={config['_config_path']}")
        print(f"workers={workers}")
        print(f"coarse_tasks={len(coarse_tasks)}")
        print(f"refine_tasks_max={max_refine}")
        print(f"estimated_total_max={len(coarse_tasks) + max_refine}")
        if coarse_tasks:
            print(f"first={coarse_tasks[0]}")
            print(f"last={coarse_tasks[-1]}")
        return

    if args.summarize_only:
        tasks = collect_existing_tasks(config, args.run_id)
        summary = summarize_tasks(config, tasks)
        ok, critical, transition = write_tables(config, args.run_id, summary)
        plot_all(config, args.run_id, ok, critical, transition)
        print(f"Summary rows: {len(summary)}")
        print(f"Critical line rows: {len(critical)}")
        print(f"Transition line rows: {len(transition)}")
        return

    ensure_fresh_run_root(config, args.run_id)
    generate_seeds(config, coarse_tasks)
    run_tasks(config, args.run_id, "coarse", coarse_tasks, workers=workers, timeout=args.timeout)
    coarse_summary = summarize_tasks(config, coarse_tasks)
    refine_tasks = build_refine_tasks(config, args.run_id, coarse_summary)
    generate_seeds(config, refine_tasks)
    run_tasks(config, args.run_id, "refine", refine_tasks, workers=workers, timeout=args.timeout)

    summary = pd.concat([coarse_summary, summarize_tasks(config, refine_tasks)], ignore_index=True)
    ok, critical, transition = write_tables(config, args.run_id, summary)
    plot_all(config, args.run_id, ok, critical, transition)
    print(f"Summary rows: {len(summary)}")
    print(f"Critical line rows: {len(critical)}")
    print(f"Transition line rows: {len(transition)}")
    print(f"Tables: {scoped_path(config, 'table_dir', args.run_id)}")
    print(f"Figures: {scoped_path(config, 'figure_dir', args.run_id)}")


if __name__ == "__main__":
    main()
