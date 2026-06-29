from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT / "results" / "tables" / "canonical_round1_20260608_summary"
FIG_DIR = PROJECT / "results" / "figures" / "canonical_round1_20260608_summary" / "seed_distributions_k"
FIT_MODE = "fixed_xmin_paper_like"


def parse_label(label: str) -> tuple[float, int | None]:
    e_match = re.search(r"E0=([0-9.]+)", label)
    seed_match = re.search(r"seed=([0-9]+)", label)
    if not e_match:
        raise ValueError(f"Cannot parse E0 from label: {label}")
    e0 = float(e_match.group(1))
    seed = int(seed_match.group(1)) if seed_match else None
    return e0, seed


def positive(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    return array[np.isfinite(array) & (array > 0)]


def log_density(values: np.ndarray, bins: int = 24) -> tuple[np.ndarray, np.ndarray]:
    edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins + 1)
    counts, edges = np.histogram(values, bins=edges, density=True)
    centers = np.sqrt(edges[:-1] * edges[1:])
    valid = counts > 0
    return centers[valid], counts[valid]


def load_seed_k_table(fits: pd.DataFrame) -> pd.DataFrame:
    selected = fits[fits["fit_mode"].eq(FIT_MODE)].copy()
    selected = selected[selected["label"].str.contains("seed=", regex=False)].copy()
    rows: list[dict[str, float | int | str]] = []
    for label, group in selected.groupby("label", sort=False):
        size = group[group["quantity"].eq("size")]
        duration = group[group["quantity"].eq("duration_ms")]
        if size.empty or duration.empty:
            continue
        e0, seed = parse_label(label)
        tau_s = float(size.iloc[0]["alpha"])
        tau_t = float(duration.iloc[0]["alpha"])
        kappa = (tau_t - 1.0) / (tau_s - 1.0)
        rows.append(
            {
                "label": label,
                "E0": e0,
                "seed": int(seed),
                "tau_S": tau_s,
                "tau_T": tau_t,
                "kappa": kappa,
                "size_xmin": float(size.iloc[0]["xmin"]),
                "duration_xmin": float(duration.iloc[0]["xmin"]),
            }
        )
    table = pd.DataFrame(rows).sort_values(["E0", "seed"]).reset_index(drop=True)
    return table


def plot_for_e0(raw: pd.DataFrame, k_table: pd.DataFrame, e0: float) -> Path:
    subset = k_table[k_table["E0"].eq(e0)].copy()
    colors = plt.cm.viridis(np.linspace(0.12, 0.86, len(subset)))
    e_tag = f"e{e0:.3f}".replace(".", "p")

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.15), dpi=220)
    ax_s, ax_t, ax_k = axes

    for color, row in zip(colors, subset.itertuples(index=False), strict=True):
        frame = raw[raw["label"].eq(row.label)]
        sizes = positive(frame["size"])
        durations = positive(frame["duration_ms"])
        sx, sy = log_density(sizes)
        tx, ty = log_density(durations)
        label = f"seed {row.seed}"
        ax_s.plot(sx, sy, "-o", color=color, linewidth=1.0, markersize=2.6, label=label)
        ax_t.plot(tx, ty, "-o", color=color, linewidth=1.0, markersize=2.6, label=label)

    ax_s.set_xscale("log")
    ax_s.set_yscale("log")
    ax_s.set_xlabel("S")
    ax_s.set_ylabel("P(S)")
    ax_s.set_title("Avalanche size")
    ax_s.legend(frameon=True, fontsize=6, loc="best")

    ax_t.set_xscale("log")
    ax_t.set_yscale("log")
    ax_t.set_xlabel("T")
    ax_t.set_ylabel("P(T)")
    ax_t.set_title("Avalanche duration")
    ax_t.legend(frameon=True, fontsize=6, loc="best")

    ax_k.scatter(subset["seed"], subset["kappa"], color=colors, s=38, zorder=3)
    ax_k.plot(subset["seed"], subset["kappa"], color="#555555", linewidth=0.8, zorder=2)
    mean_k = float(subset["kappa"].mean())
    ax_k.axhline(mean_k, color="black", linestyle="--", linewidth=1.0, label=fr"mean $\kappa={mean_k:.2f}$")
    for row in subset.itertuples(index=False):
        ax_k.text(row.seed, row.kappa, f"{row.kappa:.2f}", ha="center", va="bottom", fontsize=7)
    ax_k.set_xlabel("seed")
    ax_k.set_ylabel(r"$\kappa=(\tau_T-1)/(\tau_S-1)$")
    ax_k.set_title("Scaling relation")
    ax_k.set_xticks(subset["seed"].to_list())
    ax_k.legend(frameon=True, fontsize=7, loc="best")

    for panel, ax in zip(["(a)", "(b)", "(c)"], axes, strict=True):
        ax.text(-0.13, 1.06, panel, transform=ax.transAxes, fontweight="bold", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(f"E0={e0:.2f}, I0=1.1: per-seed avalanche distributions and scaling", y=1.04, fontsize=10)
    fig.tight_layout()
    output = FIG_DIR / f"{e_tag}_per_seed_ps_pt_k.png"
    fig.savefig(output, bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return output


def plot_k_overview(k_table: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6.6, 3.6), dpi=220)
    for e0, group in k_table.groupby("E0", sort=True):
        ax.plot(group["seed"], group["kappa"], "-o", linewidth=1.1, markersize=3.4, label=f"E0={e0:.2f}")
        for row in group.itertuples(index=False):
            ax.text(row.seed, row.kappa, f"{row.kappa:.2f}", ha="center", va="bottom", fontsize=6)
    ax.set_xlabel("seed")
    ax.set_ylabel(r"$\kappa=(\tau_T-1)/(\tau_S-1)$")
    ax.set_xticks(sorted(k_table["seed"].unique()))
    ax.legend(frameon=True, fontsize=7, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    output = FIG_DIR / "kappa_by_e0_seed.png"
    fig.savefig(output, bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return output


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(TABLE_DIR / "fig5_raw_avalanches.csv")
    fits = pd.read_csv(TABLE_DIR / "fig5_fit_results.csv")
    k_table = load_seed_k_table(fits)
    k_table.to_csv(FIG_DIR / "seed_tau_kappa_summary.csv", index=False)

    outputs = [plot_for_e0(raw, k_table, e0) for e0 in sorted(k_table["E0"].unique())]
    outputs.append(plot_k_overview(k_table))
    print(FIG_DIR)
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
