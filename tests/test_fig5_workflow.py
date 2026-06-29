from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from criticality_analysis.fig5_workflow import (
    ROUND1_E0_VALUES,
    FitTargets,
    analyze_avalanche_groups,
    build_jij_metadata,
    build_campaign_manifest,
    build_refinement_e0_values,
    build_seed_series,
    connection_cache_name,
    connection_cache_filename,
    detect_best_sigma,
    load_jij_metadata,
    manifest_run_dirs,
    memory_signature,
    parse_run_spec,
    pooled_groups_from_manifest,
    pool_avalanche_groups,
    prepare_learning_seed,
    prepare_reuse_seed,
    read_seed,
    resolve_fit_label,
    run_prepared_simulation,
    save_jij_metadata,
    summarize_campaign,
    summarize_runtime_table,
    materialize_cached_jij,
    validate_jij_metadata,
)
from criticality_analysis.plotting import plot_avalanche_st_line


def _seed_values(**overrides: str) -> dict[str, str]:
    values = {
        "topo": "tract1",
        "S": "66",
        "Z": "200",
        "G": "12",
        "K": "100",
        "P": "20",
        "sort": "0",
        "swap": "1",
        "range": "400",
        "f": "8",
        "seed": "1256874",
        "seed3": "0",
        "sigma": "6.9",
        "delta": "1.1",
        "bin": "5",
        "flush": "5",
        "tmax": "20000",
        "rho": "1",
        "alpha": "0.5",
    }
    values.update(overrides)
    return values


def test_memory_signature_ignores_dynamics_fields() -> None:
    base = _seed_values()
    varied = _seed_values(sigma="7.2", delta="1.1", bin="10", tmax="40000", rho="2", alpha="0.8")
    assert memory_signature(base) == memory_signature(varied)


def test_memory_signature_ignores_runtime_seeds() -> None:
    base = _seed_values()
    varied = _seed_values(seed="42", seed3="99")
    assert memory_signature(base) == memory_signature(varied)


def test_validate_jij_metadata_rejects_memory_mismatch() -> None:
    seed = _seed_values()
    metadata = build_jij_metadata("canonical", seed, Path("cache/CONNESSIONI5-demo"))
    validate_jij_metadata(seed, metadata)

    with pytest.raises(ValueError, match="topo"):
        validate_jij_metadata(_seed_values(topo="random"), metadata)


def test_connection_cache_name_changes_with_memory_shape() -> None:
    base = connection_cache_name(_seed_values())
    changed = connection_cache_name(_seed_values(G="14"))
    assert base != changed


def test_analyze_avalanche_groups_outputs_requested_modes() -> None:
    avalanches = {
        "run_a": pd.DataFrame(
            {
                "size": [20, 30, 45, 60, 90, 140, 210, 320, 480, 720],
                "duration_ms": [10, 15, 20, 25, 30, 40, 50, 65, 80, 100],
            }
        ),
        "run_b": pd.DataFrame(
            {
                "size": [22, 35, 50, 75, 100, 160, 230, 360, 520, 760],
                "duration_ms": [10, 15, 20, 25, 35, 45, 55, 70, 90, 110],
            }
        ),
    }
    outputs = analyze_avalanche_groups(
        avalanches,
        fit_targets=FitTargets(alpha=1.61, beta=1.93),
        fixed_xmins={"size": 45.0, "duration_ms": 20.0},
        grid_xmins={
            "size": [30.0, 45.0, 60.0],
            "duration_ms": [15.0, 20.0, 25.0],
        },
    )

    modes = set(outputs["fit_results"]["fit_mode"])
    assert {"auto_xmin", "fixed_xmin_paper_like", "grid_search_xmin"} <= modes
    assert {"abs_distance_to_alpha_target", "abs_distance_to_beta_target"} <= set(outputs["target_summary"].columns)
    assert not outputs["sensitivity"].empty


def test_plot_avalanche_st_line_writes_output(tmp_path: Path) -> None:
    avalanches = {
        "E0=6.8, I0=1.1": pd.DataFrame(
            {
                "size": [20, 40, 80, 160],
                "duration_ms": [10, 20, 40, 80],
            }
        )
    }
    output = tmp_path / "fig5_st_line.png"
    plot_avalanche_st_line(avalanches, output=output)
    assert output.exists()


def test_pool_avalanche_groups_adds_pooled_label() -> None:
    avalanches = {
        "seed_1": pd.DataFrame({"size": [10, 20], "duration_ms": [5, 10]}),
        "seed_2": pd.DataFrame({"size": [30], "duration_ms": [15]}),
    }
    pooled = pool_avalanche_groups(avalanches, "pooled")
    assert "pooled" in pooled
    assert len(pooled["pooled"]) == 3


def test_parse_run_spec_splits_on_last_equals() -> None:
    label, run_ref = parse_run_spec("E0=6.9, I0=1.1=C:/tmp/run_dir")
    assert label == "E0=6.9, I0=1.1"
    assert run_ref == "C:/tmp/run_dir"


def test_resolve_fit_label_prefers_explicit_target_or_e69() -> None:
    labels = ["E0=5.7, I0=1.1", "E0=6.9, I0=1.1", "pooled"]
    assert resolve_fit_label(labels, "") == "E0=6.9, I0=1.1"
    assert resolve_fit_label(["E0=5.7, I0=1.1", "E0=6.9, I0=1.1"], "") == "E0=6.9, I0=1.1"
    assert resolve_fit_label(labels, "E0=6.9, I0=1.1") == "E0=6.9, I0=1.1"


def test_analyze_avalanche_groups_skips_invalid_grid_candidates() -> None:
    avalanches = {
        "run_a": pd.DataFrame(
            {
                "size": [20, 40, 80, 160],
                "duration_ms": [10, 20, 40, 80],
            }
        )
    }
    outputs = analyze_avalanche_groups(
        avalanches,
        fit_targets=FitTargets(alpha=1.61, beta=1.93),
        fixed_xmins={"size": 40.0, "duration_ms": 20.0},
        grid_xmins={"size": [40.0, 10000.0], "duration_ms": [20.0, 10000.0]},
    )
    assert "grid_search_xmin" in set(outputs["fit_results"]["fit_mode"])


def test_build_seed_series_and_round1_defaults() -> None:
    assert ROUND1_E0_VALUES == [6.75, 6.80, 6.85, 6.90, 6.95]
    assert build_seed_series(10, 3, 2) == [10, 12, 14]


def test_build_campaign_manifest_and_run_dirs(tmp_path: Path) -> None:
    manifest = build_campaign_manifest(
        "round1",
        [6.8, 6.9],
        [101, 102],
        delta=1.1,
        bin_ms=5.0,
        flush=5,
        tmax_ms=20000.0,
        rho=1.0,
        alpha=0.5,
    )
    assert len(manifest) == 4
    assert set(manifest["group_label"]) == {"E0=6.800, I0=1.1", "E0=6.900, I0=1.1"}
    run_dirs = manifest_run_dirs(manifest, tmp_path / "runs")
    assert str(next(iter(run_dirs.values()))).startswith(str(tmp_path / "runs"))


def test_pooled_groups_from_manifest_and_campaign_summary() -> None:
    manifest = build_campaign_manifest(
        "round1",
        [6.8, 6.9],
        [201, 202],
        delta=1.1,
        bin_ms=5.0,
        flush=5,
        tmax_ms=20000.0,
        rho=1.0,
        alpha=0.5,
    )
    avalanches = {
        str(row["label"]): pd.DataFrame(
            {
                "size": [20, 30, 45, 70, 110, 170, 250, 360],
                "duration_ms": [10, 15, 20, 30, 40, 55, 75, 95],
            }
        )
        for _, row in manifest.iterrows()
    }
    pooled = pooled_groups_from_manifest(avalanches, manifest)
    assert set(pooled) == {"E0=6.800, I0=1.1", "E0=6.900, I0=1.1"}
    single_outputs = analyze_avalanche_groups(
        avalanches,
        fit_targets=FitTargets(alpha=1.61, beta=1.93),
        fixed_xmins={"size": 45.0, "duration_ms": 20.0},
        grid_xmins={"size": [30.0, 45.0], "duration_ms": [15.0, 20.0]},
    )
    pooled_outputs = analyze_avalanche_groups(
        pooled,
        fit_targets=FitTargets(alpha=1.61, beta=1.93),
        fixed_xmins={"size": 45.0, "duration_ms": 20.0},
        grid_xmins={"size": [30.0, 45.0], "duration_ms": [15.0, 20.0]},
    )
    fit_results = pd.concat([single_outputs["fit_results"], pooled_outputs["fit_results"]], ignore_index=True)
    summary = summarize_campaign(
        fit_results,
        manifest,
        fit_mode="fixed_xmin_paper_like",
        fit_targets=FitTargets(alpha=1.61, beta=1.93),
    )
    assert {"score", "single_seed_alpha_std", "single_seed_beta_std"} <= set(summary.columns)
    assert detect_best_sigma(summary) in {6.8, 6.9}


def test_build_refinement_e0_values() -> None:
    assert build_refinement_e0_values(6.85) == [6.8, 6.825, 6.85, 6.875, 6.9]


def test_summarize_runtime_table() -> None:
    timings = pd.DataFrame(
        {
            "label": ["a", "a", "b"],
            "runtime_seconds": [10.0, 20.0, 5.0],
        }
    )
    summary = summarize_runtime_table(timings)
    assert {"runtime_seconds_total", "runtime_seconds_mean", "runtime_seconds_min", "runtime_seconds_max"} <= set(summary.columns)
    assert float(summary.loc[summary["label"] == "a", "runtime_seconds_total"].iloc[0]) == 30.0


def test_smoke_jij_can_be_learned_and_reused(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[1]
    executable = project / "build" / "criticality_sim.exe"
    if not executable.exists():
        pytest.skip("simulator executable not built")

    base_seed = project / "configs" / "experiments" / "smoke.seed"
    cache_dir = tmp_path / "cache"
    learn_seed = prepare_learning_seed(base_seed, tmp_path / "learn.seed", cache_dir, "smoke_cache")
    run_prepared_simulation(executable, learn_seed, tmp_path / "learn_runs", "smoke_cache", timeout=30)
    seed_values = read_seed(learn_seed)
    metadata_path = save_jij_metadata(
        build_jij_metadata("smoke_cache", seed_values, cache_dir / connection_cache_filename(seed_values)),
        cache_dir / "metadata.json",
    )

    reuse_seed = prepare_reuse_seed(
        base_seed,
        tmp_path / "reuse.seed",
        "smoke_reuse",
        sigma=6.9,
        delta=1.1,
        bin_ms=1,
        flush=5,
        tmax_ms=50,
    )
    reuse_values = read_seed(reuse_seed)
    metadata = load_jij_metadata(metadata_path)
    validate_jij_metadata(reuse_values, metadata)
    run_dir = (tmp_path / "runs" / "smoke_reuse").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    materialize_cached_jij(metadata, run_dir, reuse_values)
    completed = run_prepared_simulation(executable, reuse_seed, tmp_path / "runs", "smoke_reuse", timeout=30)
    assert (completed / "output").exists()
    assert (completed / "timing.json").exists()
