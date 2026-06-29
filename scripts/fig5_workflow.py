from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

import pandas as pd

from criticality_analysis import (
    ROUND1_E0_VALUES,
    FitTargets,
    analyze_avalanche_groups,
    build_jij_metadata,
    build_campaign_manifest,
    build_refinement_e0_values,
    build_seed_series,
    connection_cache_filename,
    detect_best_sigma,
    load_avalanches_from_runs,
    load_jij_metadata,
    load_manifest,
    load_run_timings,
    manifest_run_dirs,
    materialize_cached_jij,
    parse_run_spec,
    pooled_groups_from_manifest,
    prepare_learning_seed,
    prepare_reuse_seed,
    read_seed,
    resolve_fit_label,
    run_prepared_simulation,
    save_jij_metadata,
    save_manifest,
    save_runtime_record,
    summarize_runtime_table,
    summarize_campaign,
    validate_jij_metadata,
)
from criticality_analysis.plotting import (
    plot_avalanche_distribution,
    plot_avalanche_st_line,
    plot_fig5_paper_style,
)


PROJECT = Path(__file__).resolve().parents[1]
RUN_ROOT = PROJECT / "results" / "runs"
FIG_DIR = PROJECT / "results" / "figures"
TABLE_DIR = PROJECT / "results" / "tables"
CACHE_ROOT = PROJECT / "results" / "jij_cache"
EXECUTABLE = PROJECT / "build" / ("criticality_sim.exe" if (PROJECT / "build" / "criticality_sim.exe").exists() else "criticality_sim")


class _Fit:
    def __init__(self, row):
        self.alpha = float(row["alpha"])
        self.xmin = float(row["xmin"])


def _select_fit_rows(fit_results, fit_label: str, fit_mode: str):
    size_fit_row = fit_results[
        (fit_results["label"] == fit_label)
        & (fit_results["quantity"] == "size")
        & (fit_results["fit_mode"] == fit_mode)
    ].iloc[0]
    duration_fit_row = fit_results[
        (fit_results["label"] == fit_label)
        & (fit_results["quantity"] == "duration_ms")
        & (fit_results["fit_mode"] == fit_mode)
    ].iloc[0]
    return _Fit(size_fit_row), _Fit(duration_fit_row)


def _start_timer() -> tuple[datetime, float]:
    return datetime.now(timezone.utc), time.perf_counter()


def _finish_timer(started_at: datetime, started_perf: float, *, event: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    finished_at = datetime.now(timezone.utc)
    record = {
        "event": event,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "runtime_seconds": time.perf_counter() - started_perf,
    }
    if extra:
        record.update(extra)
    return record


def _write_command_timing(output: str | Path, record: dict[str, object]) -> Path:
    return save_runtime_record(record, output)


def _execute_manifest(
    manifest: pd.DataFrame,
    *,
    metadata_path: Path,
    base_seed: Path,
    timeout: int | None,
) -> pd.DataFrame:
    metadata = load_jij_metadata(metadata_path)
    generated_dir = PROJECT / "results" / "generated_configs" / "fig5_workflow" / str(manifest.iloc[0]["run_name"]).split("_seed")[0]
    timings: list[dict[str, object]] = []
    total = len(manifest)
    for index, row in enumerate(manifest.itertuples(index=False), start=1):
        prepared_seed = prepare_reuse_seed(
            base_seed,
            generated_dir / f"{row.run_name}.seed",
            str(row.run_name),
            sigma=float(row.sigma),
            delta=float(row.delta),
            bin_ms=float(row.bin_ms),
            flush=int(row.flush),
            tmax_ms=float(row.tmax_ms),
            rho=float(row.rho),
            alpha=float(row.alpha),
            seed=int(row.seed),
        )
        prepared_values = read_seed(prepared_seed)
        validate_jij_metadata(prepared_values, metadata)
        run_dir = (RUN_ROOT / str(row.run_name)).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        materialize_cached_jij(metadata, run_dir, prepared_values)
        run_prepared_simulation(EXECUTABLE, prepared_seed, RUN_ROOT, str(row.run_name), timeout=timeout)
        timing_path = run_dir / "timing.json"
        timing = pd.read_json(timing_path, typ="series").to_dict()
        timing["label"] = str(row.label)
        timing["group_label"] = str(row.group_label)
        timing["run_name"] = str(row.run_name)
        timing["progress_index"] = index
        timing["progress_total"] = total
        timings.append(timing)
        print(f"[{index}/{total}] {row.run_name}: {float(timing['runtime_seconds']):.1f}s")
    return pd.DataFrame(timings)


def cmd_learn_j(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    cache_dir = CACHE_ROOT / args.cache_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    prepared_seed = prepare_learning_seed(args.base_seed, cache_dir / f"{args.cache_name}.seed", cache_dir, args.cache_name)
    run_dir = run_prepared_simulation(EXECUTABLE, prepared_seed, CACHE_ROOT, args.cache_name, timeout=args.timeout)
    seed_values = read_seed(prepared_seed)
    connection_file = cache_dir / connection_cache_filename(seed_values)
    metadata = build_jij_metadata(args.cache_name, seed_values, connection_file)
    metadata_path = save_jij_metadata(metadata, cache_dir / "metadata.json")
    _write_command_timing(
        cache_dir / "command_timing.json",
        _finish_timer(started_at, started_perf, event="learn-j", extra={"cache_name": args.cache_name, "run_dir": str(run_dir)}),
    )
    print(run_dir)
    print(metadata_path)


def cmd_run_dynamics(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    metadata = load_jij_metadata(args.metadata)
    prepared_seed = prepare_reuse_seed(
        args.base_seed,
        PROJECT / "results" / "generated_configs" / "fig5_workflow" / f"{args.run_name}.seed",
        args.run_name,
        sigma=args.sigma,
        delta=args.delta,
        bin_ms=args.bin_ms,
        flush=args.flush,
        tmax_ms=args.tmax_ms,
        rho=args.rho,
        alpha=args.alpha,
        seed=args.seed,
        seed3=args.seed3,
    )
    seed_values = read_seed(prepared_seed)
    validate_jij_metadata(seed_values, metadata)
    run_dir = (RUN_ROOT / args.run_name).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    materialize_cached_jij(metadata, run_dir, seed_values)
    completed_dir = run_prepared_simulation(EXECUTABLE, prepared_seed, RUN_ROOT, args.run_name, timeout=args.timeout)
    _write_command_timing(
        completed_dir / "command_timing.json",
        _finish_timer(started_at, started_perf, event="run-dynamics", extra={"run_name": args.run_name}),
    )
    print(completed_dir)


def cmd_analyze(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    run_dirs = {}
    for item in args.run:
        label, run_name = parse_run_spec(item)
        candidate = Path(run_name)
        run_dirs[label] = candidate if candidate.exists() else RUN_ROOT / run_name
    avalanches = load_avalanches_from_runs(run_dirs)
    outputs = analyze_avalanche_groups(
        avalanches,
        fit_targets=FitTargets(alpha=args.target_alpha, beta=args.target_beta),
        fixed_xmins={"size": args.size_xmin, "duration_ms": args.duration_xmin},
        grid_xmins={
            "size": args.size_grid,
            "duration_ms": args.duration_grid,
        },
    )
    prefix = args.output_prefix
    table_dir = TABLE_DIR / prefix
    fig_dir = FIG_DIR / prefix
    table_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    outputs["raw_avalanches"].to_csv(table_dir / "fig5_raw_avalanches.csv", index=False)
    outputs["fit_results"].to_csv(table_dir / "fig5_fit_results.csv", index=False)
    outputs["sensitivity"].to_csv(table_dir / "fig5_xmin_sensitivity.csv", index=False)
    outputs["target_summary"].to_csv(table_dir / "fig5_target_summary.csv", index=False)

    fit_results = outputs["fit_results"]
    fit_label = resolve_fit_label(list(avalanches.keys()), args.fit_label)
    size_fit, duration_fit = _select_fit_rows(fit_results, fit_label, args.main_fit_mode)
    plot_fig5_paper_style(avalanches, size_fit, duration_fit, fig_dir / "fig5_paper_style.png")
    plot_avalanche_distribution(avalanches, "size", fit_label=fit_label, fit=size_fit, output=fig_dir / "fig5_size_distribution.png")
    plot_avalanche_distribution(avalanches, "duration_ms", fit_label=fit_label, fit=duration_fit, output=fig_dir / "fig5_duration_distribution.png")
    plot_avalanche_st_line(avalanches, output=fig_dir / "fig5_st_line.png")
    _write_command_timing(
        table_dir / "command_timing.json",
        _finish_timer(started_at, started_perf, event="analyze", extra={"output_prefix": prefix}),
    )
    print(table_dir)
    print(fig_dir)


def cmd_scan_e0(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    seed_values = build_seed_series(args.seed_start, args.seed_count, args.seed_step)
    e0_values = args.e0 if args.e0 else ROUND1_E0_VALUES
    manifest = build_campaign_manifest(
        args.prefix,
        e0_values,
        seed_values,
        delta=args.delta,
        bin_ms=args.bin_ms,
        flush=args.flush,
        tmax_ms=args.tmax_ms,
        rho=args.rho,
        alpha=args.alpha,
    )
    table_dir = TABLE_DIR / args.prefix
    table_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = save_manifest(manifest, table_dir / "scan_manifest.csv")
    timings = _execute_manifest(
        manifest,
        metadata_path=args.metadata,
        base_seed=args.base_seed,
        timeout=args.timeout,
    )
    timings.to_csv(table_dir / "scan_timings.csv", index=False)
    summarize_runtime_table(timings).to_csv(table_dir / "scan_runtime_summary.csv", index=False)
    _write_command_timing(
        table_dir / "command_timing.json",
        _finish_timer(started_at, started_perf, event="scan-e0", extra={"prefix": args.prefix, "run_count": len(manifest)}),
    )
    print(manifest_path)


def cmd_summarize_scan(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    manifest = load_manifest(args.manifest)
    run_dirs = manifest_run_dirs(manifest, RUN_ROOT)
    single_run_avalanches = load_avalanches_from_runs(run_dirs)
    pooled_avalanches = pooled_groups_from_manifest(single_run_avalanches, manifest)
    timings = load_run_timings(run_dirs)

    fit_targets = FitTargets(alpha=args.target_alpha, beta=args.target_beta)
    single_outputs = analyze_avalanche_groups(
        single_run_avalanches,
        fit_targets=fit_targets,
        fixed_xmins={"size": args.size_xmin, "duration_ms": args.duration_xmin},
        grid_xmins={"size": args.size_grid, "duration_ms": args.duration_grid},
    )
    pooled_outputs = analyze_avalanche_groups(
        pooled_avalanches,
        fit_targets=fit_targets,
        fixed_xmins={"size": args.size_xmin, "duration_ms": args.duration_xmin},
        grid_xmins={"size": args.size_grid, "duration_ms": args.duration_grid},
    )

    fit_results = pd.concat([single_outputs["fit_results"], pooled_outputs["fit_results"]], ignore_index=True)
    raw_avalanches = pd.concat([single_outputs["raw_avalanches"], pooled_outputs["raw_avalanches"]], ignore_index=True)
    sensitivity = pd.concat([single_outputs["sensitivity"], pooled_outputs["sensitivity"]], ignore_index=True)
    target_summary = pd.concat([single_outputs["target_summary"], pooled_outputs["target_summary"]], ignore_index=True)

    campaign_summary = summarize_campaign(
        fit_results,
        manifest,
        fit_mode=args.main_fit_mode,
        fit_targets=fit_targets,
        timings=timings,
    )
    table_dir = TABLE_DIR / args.output_prefix
    fig_dir = FIG_DIR / args.output_prefix
    table_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(table_dir / "scan_manifest.csv", index=False)
    raw_avalanches.to_csv(table_dir / "fig5_raw_avalanches.csv", index=False)
    fit_results.to_csv(table_dir / "fig5_fit_results.csv", index=False)
    sensitivity.to_csv(table_dir / "fig5_xmin_sensitivity.csv", index=False)
    target_summary.to_csv(table_dir / "fig5_target_summary.csv", index=False)
    campaign_summary.to_csv(table_dir / "fig5_campaign_summary.csv", index=False)
    timings.to_csv(table_dir / "scan_timings.csv", index=False)
    summarize_runtime_table(timings).to_csv(table_dir / "scan_runtime_summary.csv", index=False)

    fit_label = resolve_fit_label(list(pooled_avalanches.keys()), args.fit_label)
    size_fit, duration_fit = _select_fit_rows(pooled_outputs["fit_results"], fit_label, args.main_fit_mode)
    plot_fig5_paper_style(pooled_avalanches, size_fit, duration_fit, fig_dir / "fig5_paper_style.png")
    plot_avalanche_distribution(pooled_avalanches, "size", fit_label=fit_label, fit=size_fit, output=fig_dir / "fig5_size_distribution.png")
    plot_avalanche_distribution(pooled_avalanches, "duration_ms", fit_label=fit_label, fit=duration_fit, output=fig_dir / "fig5_duration_distribution.png")
    plot_avalanche_st_line(pooled_avalanches, output=fig_dir / "fig5_st_line.png")

    if not campaign_summary.empty:
        best_sigma = detect_best_sigma(campaign_summary)
        refine = build_refinement_e0_values(best_sigma, step=args.refine_step, radius=args.refine_radius)
        save_manifest(
            build_campaign_manifest(
                f"{args.output_prefix}_round2",
                refine,
                build_seed_series(args.seed_start, args.seed_count, args.seed_step),
                delta=args.delta,
                bin_ms=args.bin_ms,
                flush=args.flush,
                tmax_ms=args.tmax_ms,
                rho=args.rho,
                alpha=args.alpha,
            ),
            table_dir / "suggested_round2_manifest.csv",
        )
    _write_command_timing(
        table_dir / "command_timing.json",
        _finish_timer(started_at, started_perf, event="summarize-scan", extra={"output_prefix": args.output_prefix}),
    )
    print(table_dir)
    print(fig_dir)


def cmd_run_full_campaign(args: argparse.Namespace) -> None:
    started_at, started_perf = _start_timer()
    cache_dir = CACHE_ROOT / args.cache_name
    metadata_path = cache_dir / "metadata.json"
    if not metadata_path.exists():
        learn_args = argparse.Namespace(base_seed=args.learn_base_seed, cache_name=args.cache_name, timeout=args.timeout)
        cmd_learn_j(learn_args)

    round1_prefix = args.round1_prefix
    round1_scan_args = argparse.Namespace(
        metadata=metadata_path,
        base_seed=args.run_base_seed,
        prefix=round1_prefix,
        e0=[],
        seed_start=args.seed_start,
        seed_count=args.seed_count,
        seed_step=args.seed_step,
        delta=args.delta,
        bin_ms=args.bin_ms,
        flush=args.flush,
        tmax_ms=args.tmax_ms,
        rho=args.rho,
        alpha=args.alpha,
        timeout=args.timeout,
    )
    cmd_scan_e0(round1_scan_args)

    round1_manifest = TABLE_DIR / round1_prefix / "scan_manifest.csv"
    round1_summary_prefix = f"{round1_prefix}_summary"
    summarize_args = argparse.Namespace(
        manifest=round1_manifest,
        output_prefix=round1_summary_prefix,
        target_alpha=args.target_alpha,
        target_beta=args.target_beta,
        size_xmin=args.size_xmin,
        duration_xmin=args.duration_xmin,
        size_grid=args.size_grid,
        duration_grid=args.duration_grid,
        main_fit_mode=args.main_fit_mode,
        fit_label=args.fit_label,
        seed_start=args.seed_start,
        seed_count=args.seed_count,
        seed_step=args.seed_step,
        delta=args.delta,
        bin_ms=args.bin_ms,
        flush=args.flush,
        tmax_ms=args.tmax_ms,
        rho=args.rho,
        alpha=args.alpha,
        refine_step=args.refine_step,
        refine_radius=args.refine_radius,
    )
    cmd_summarize_scan(summarize_args)

    round2_manifest = TABLE_DIR / round1_summary_prefix / "suggested_round2_manifest.csv"
    round2_prefix = args.round2_prefix
    if round2_manifest.exists():
        manifest = load_manifest(round2_manifest)
        manifest["run_name"] = manifest["run_name"].astype(str).str.replace(f"{round1_summary_prefix}_round2", round2_prefix, regex=False)
        round2_dir = TABLE_DIR / round2_prefix
        round2_dir.mkdir(parents=True, exist_ok=True)
        save_manifest(manifest, round2_dir / "scan_manifest.csv")
        timings = _execute_manifest(manifest, metadata_path=metadata_path, base_seed=args.run_base_seed, timeout=args.timeout)
        timings.to_csv(round2_dir / "scan_timings.csv", index=False)
        summarize_runtime_table(timings).to_csv(round2_dir / "scan_runtime_summary.csv", index=False)
        round2_summarize_args = argparse.Namespace(
            manifest=round2_dir / "scan_manifest.csv",
            output_prefix=f"{round2_prefix}_summary",
            target_alpha=args.target_alpha,
            target_beta=args.target_beta,
            size_xmin=args.size_xmin,
            duration_xmin=args.duration_xmin,
            size_grid=args.size_grid,
            duration_grid=args.duration_grid,
            main_fit_mode=args.main_fit_mode,
            fit_label=args.fit_label,
            seed_start=args.seed_start,
            seed_count=args.seed_count,
            seed_step=args.seed_step,
            delta=args.delta,
            bin_ms=args.bin_ms,
            flush=args.flush,
            tmax_ms=args.tmax_ms,
            rho=args.rho,
            alpha=args.alpha,
            refine_step=args.refine_step,
            refine_radius=args.refine_radius,
        )
        cmd_summarize_scan(round2_summarize_args)

    campaign_dir = TABLE_DIR / args.campaign_prefix
    campaign_dir.mkdir(parents=True, exist_ok=True)
    _write_command_timing(
        campaign_dir / "campaign_timing.json",
        _finish_timer(started_at, started_perf, event="run-full-campaign", extra={"cache_name": args.cache_name}),
    )
    print(campaign_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fig.5 workflow with saved Jij reuse and multi-mode fitting.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    learn = subparsers.add_parser("learn-j")
    learn.add_argument("--base-seed", type=Path, default=PROJECT / "configs" / "experiments" / "baseline_paper.seed")
    learn.add_argument("--cache-name", required=True)
    learn.add_argument("--timeout", type=int, default=None)
    learn.set_defaults(func=cmd_learn_j)

    dyn = subparsers.add_parser("run-dynamics")
    dyn.add_argument("--metadata", type=Path, required=True)
    dyn.add_argument("--base-seed", type=Path, required=True)
    dyn.add_argument("--run-name", required=True)
    dyn.add_argument("--sigma", type=float, required=True)
    dyn.add_argument("--delta", type=float, default=1.1)
    dyn.add_argument("--bin-ms", type=float, default=5.0)
    dyn.add_argument("--flush", type=int, default=5)
    dyn.add_argument("--tmax-ms", type=float, default=20000.0)
    dyn.add_argument("--rho", type=float, default=1.0)
    dyn.add_argument("--alpha", type=float, default=0.5)
    dyn.add_argument("--seed", type=int, default=None)
    dyn.add_argument("--seed3", type=int, default=None)
    dyn.add_argument("--timeout", type=int, default=None)
    dyn.set_defaults(func=cmd_run_dynamics)

    scan = subparsers.add_parser("scan-e0")
    scan.add_argument("--metadata", type=Path, required=True)
    scan.add_argument("--base-seed", type=Path, default=PROJECT / "configs" / "experiments" / "stationary_e69_i11_bin5.seed")
    scan.add_argument("--prefix", required=True)
    scan.add_argument("--e0", nargs="+", type=float, default=[])
    scan.add_argument("--seed-start", type=int, default=1256874)
    scan.add_argument("--seed-count", type=int, default=5)
    scan.add_argument("--seed-step", type=int, default=1)
    scan.add_argument("--delta", type=float, default=1.1)
    scan.add_argument("--bin-ms", type=float, default=5.0)
    scan.add_argument("--flush", type=int, default=5)
    scan.add_argument("--tmax-ms", type=float, default=20000.0)
    scan.add_argument("--rho", type=float, default=1.0)
    scan.add_argument("--alpha", type=float, default=0.5)
    scan.add_argument("--timeout", type=int, default=None)
    scan.set_defaults(func=cmd_scan_e0)

    summarize = subparsers.add_parser("summarize-scan")
    summarize.add_argument("--manifest", type=Path, required=True)
    summarize.add_argument("--output-prefix", required=True)
    summarize.add_argument("--target-alpha", type=float, default=1.61)
    summarize.add_argument("--target-beta", type=float, default=1.93)
    summarize.add_argument("--size-xmin", type=float, default=80.0)
    summarize.add_argument("--duration-xmin", type=float, default=20.0)
    summarize.add_argument("--size-grid", nargs="+", type=float, default=[80.0, 100.0, 120.0, 140.0, 180.0])
    summarize.add_argument("--duration-grid", nargs="+", type=float, default=[20.0, 30.0, 40.0, 45.0, 60.0])
    summarize.add_argument("--main-fit-mode", default="fixed_xmin_paper_like")
    summarize.add_argument("--fit-label", default="")
    summarize.add_argument("--seed-start", type=int, default=1256874)
    summarize.add_argument("--seed-count", type=int, default=5)
    summarize.add_argument("--seed-step", type=int, default=1)
    summarize.add_argument("--delta", type=float, default=1.1)
    summarize.add_argument("--bin-ms", type=float, default=5.0)
    summarize.add_argument("--flush", type=int, default=5)
    summarize.add_argument("--tmax-ms", type=float, default=20000.0)
    summarize.add_argument("--rho", type=float, default=1.0)
    summarize.add_argument("--alpha", type=float, default=0.5)
    summarize.add_argument("--refine-step", type=float, default=0.025)
    summarize.add_argument("--refine-radius", type=int, default=2)
    summarize.set_defaults(func=cmd_summarize_scan)

    full = subparsers.add_parser("run-full-campaign")
    full.add_argument("--cache-name", default="canonical_jij_paper_seed1256874")
    full.add_argument("--campaign-prefix", default="canonical_fig5_campaign")
    full.add_argument("--round1-prefix", default="round1_e0_scan")
    full.add_argument("--round2-prefix", default="round2_e0_scan")
    full.add_argument("--learn-base-seed", type=Path, default=PROJECT / "configs" / "experiments" / "baseline_paper.seed")
    full.add_argument("--run-base-seed", type=Path, default=PROJECT / "configs" / "experiments" / "stationary_e69_i11_bin5.seed")
    full.add_argument("--seed-start", type=int, default=1256874)
    full.add_argument("--seed-count", type=int, default=5)
    full.add_argument("--seed-step", type=int, default=1)
    full.add_argument("--delta", type=float, default=1.1)
    full.add_argument("--bin-ms", type=float, default=5.0)
    full.add_argument("--flush", type=int, default=5)
    full.add_argument("--tmax-ms", type=float, default=20000.0)
    full.add_argument("--rho", type=float, default=1.0)
    full.add_argument("--alpha", type=float, default=0.5)
    full.add_argument("--target-alpha", type=float, default=1.61)
    full.add_argument("--target-beta", type=float, default=1.93)
    full.add_argument("--size-xmin", type=float, default=80.0)
    full.add_argument("--duration-xmin", type=float, default=20.0)
    full.add_argument("--size-grid", nargs="+", type=float, default=[80.0, 100.0, 120.0, 140.0, 180.0])
    full.add_argument("--duration-grid", nargs="+", type=float, default=[20.0, 30.0, 40.0, 45.0, 60.0])
    full.add_argument("--main-fit-mode", default="fixed_xmin_paper_like")
    full.add_argument("--fit-label", default="")
    full.add_argument("--refine-step", type=float, default=0.025)
    full.add_argument("--refine-radius", type=int, default=2)
    full.add_argument("--timeout", type=int, default=None)
    full.set_defaults(func=cmd_run_full_campaign)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--run", action="append", required=True, help="label=run_name")
    analyze.add_argument("--output-prefix", required=True)
    analyze.add_argument("--target-alpha", type=float, default=1.61)
    analyze.add_argument("--target-beta", type=float, default=1.93)
    analyze.add_argument("--size-xmin", type=float, default=80.0)
    analyze.add_argument("--duration-xmin", type=float, default=20.0)
    analyze.add_argument("--size-grid", nargs="+", type=float, default=[80.0, 100.0, 120.0, 140.0, 180.0])
    analyze.add_argument("--duration-grid", nargs="+", type=float, default=[20.0, 30.0, 40.0, 45.0, 60.0])
    analyze.add_argument("--main-fit-mode", default="fixed_xmin_paper_like")
    analyze.add_argument("--fit-label", default="")
    analyze.set_defaults(func=cmd_analyze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
