from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT / "results" / "tables" / "canonical_round1_20260608_summary"
FIG_DIR = PROJECT / "results" / "figures" / "canonical_round1_20260608_summary" / "individual_seed_ps_pt_k"
FIT_MODE = "fixed_xmin_paper_like"


def parse_label(label: str) -> tuple[float, int]:
    e_match = re.search(r"E0=([0-9.]+)", label)
    seed_match = re.search(r"seed=([0-9]+)", label)
    if not e_match or not seed_match:
        raise ValueError(f"Cannot parse label: {label}")
    return float(e_match.group(1)), int(seed_match.group(1))


def positive(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    return array[np.isfinite(array) & (array > 0)]


def log_density(values: np.ndarray, bins: int = 26) -> tuple[np.ndarray, np.ndarray]:
    edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins + 1)
    counts, edges = np.histogram(values, bins=edges, density=True)
    centers = np.sqrt(edges[:-1] * edges[1:])
    keep = counts > 0
    return centers[keep], counts[keep]


def reference_line(
    x: np.ndarray,
    y: np.ndarray,
    *,
    exponent: float,
    xmin: float,
    xmax: float,
) -> tuple[np.ndarray, np.ndarray]:
    tail = (x >= xmin) & (x <= xmax)
    if tail.any():
        anchor_x = float(np.median(x[tail]))
        anchor_y = float(np.median(y[tail]))
    else:
        anchor_x = float(x[-1])
        anchor_y = float(y[-1])
    xs = np.logspace(np.log10(xmin), np.log10(xmax), 100)
    ys = anchor_y * (xs / anchor_x) ** (-exponent)
    return xs, ys


def selected_fit_rows(fits: pd.DataFrame) -> pd.DataFrame:
    selected = fits[fits["fit_mode"].eq(FIT_MODE)].copy()
    selected = selected[selected["label"].str.contains("seed=", regex=False)].copy()
    rows: list[dict[str, float | int | str]] = []
    for label, group in selected.groupby("label", sort=False):
        e0, seed = parse_label(label)
        size = group[group["quantity"].eq("size")].iloc[0]
        duration = group[group["quantity"].eq("duration_ms")].iloc[0]
        tau_s = float(size["alpha"])
        tau_t = float(duration["alpha"])
        rows.append(
            {
                "label": label,
                "E0": e0,
                "seed": seed,
                "tau_S": tau_s,
                "tau_T": tau_t,
                "kappa": (tau_t - 1.0) / (tau_s - 1.0),
                "size_xmin": float(size["xmin"]),
                "duration_xmin": float(duration["xmin"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["E0", "seed"]).reset_index(drop=True)


def draw_distribution(
    ax,
    values: np.ndarray,
    *,
    exponent: float,
    xmin: float,
    xlabel: str,
    ylabel: str,
    exponent_label: str,
    color: str,
) -> None:
    x, y = log_density(values)
    xmax = float(values.max())
    ref_x, ref_y = reference_line(x, y, exponent=exponent, xmin=xmin, xmax=xmax)
    ax.plot(x, y, "-o", color=color, linewidth=1.2, markersize=3.0)
    ax.plot(ref_x, ref_y, "k--", linewidth=1.0, label=rf"${exponent_label}={exponent:.2f}$")
    ax.axvspan(xmin, xmax, color=color, alpha=0.08, linewidth=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(frameon=True, fontsize=8, loc="best")
    ax.spines[["top", "right"]].set_visible(False)


def draw_size_duration(ax, frame: pd.DataFrame, *, kappa: float) -> None:
    data = frame[["duration_ms", "size"]].dropna()
    data = data[(data["duration_ms"] > 0) & (data["size"] > 0)]
    t = data["duration_ms"].to_numpy(dtype=float)
    s = data["size"].to_numpy(dtype=float)

    ax.scatter(t, s, s=5, color="#6DA43A", alpha=0.12, linewidths=0, rasterized=True)

    edges = np.logspace(np.log10(t.min()), np.log10(t.max()), 16)
    centers: list[float] = []
    means: list[float] = []
    p25: list[float] = []
    p75: list[float] = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (t >= left) & (t < right)
        if right == edges[-1]:
            mask = (t >= left) & (t <= right)
        if mask.sum() < 3:
            continue
        centers.append(float(np.sqrt(left * right)))
        means.append(float(np.mean(s[mask])))
        p25.append(float(np.percentile(s[mask], 25)))
        p75.append(float(np.percentile(s[mask], 75)))

    if centers:
        centers_array = np.asarray(centers)
        ax.fill_between(centers_array, p25, p75, color="#6DA43A", alpha=0.16, linewidth=0)
        ax.plot(centers_array, means, "-o", color="#285C2E", linewidth=1.15, markersize=2.8, label=r"$\langle S\rangle(T)$")

    ax.text(
        0.05,
        0.94,
        rf"$\kappa={kappa:.2f}$",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "0.75", "alpha": 0.85},
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("T")
    ax.set_ylabel("S")
    ax.legend(frameon=True, fontsize=7, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)


def plot_one_seed(raw: pd.DataFrame, row: pd.Series) -> Path:
    label = str(row["label"])
    e0 = float(row["E0"])
    seed = int(row["seed"])
    frame = raw[raw["label"].eq(label)].copy()
    if frame.empty:
        raise RuntimeError(f"No avalanche rows for {label}")

    sizes = positive(frame["size"])
    durations = positive(frame["duration_ms"])
    color = "#5C8F34"
    e_dir = FIG_DIR / f"e0_{e0:.2f}".replace(".", "p")
    e_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.1), dpi=220)
    draw_distribution(
        axes[0],
        sizes,
        exponent=float(row["tau_S"]),
        xmin=float(row["size_xmin"]),
        xlabel="S",
        ylabel="P(S)",
        exponent_label=r"\tau_S",
        color=color,
    )
    draw_distribution(
        axes[1],
        durations,
        exponent=float(row["tau_T"]),
        xmin=float(row["duration_xmin"]),
        xlabel="T",
        ylabel="P(T)",
        exponent_label=r"\tau_T",
        color="#2F6FBB",
    )

    draw_size_duration(axes[2], frame, kappa=float(row["kappa"]))

    for panel, ax in zip(["(a)", "(b)", "(c)"], axes, strict=True):
        ax.text(-0.12, 1.05, panel, transform=ax.transAxes, fontsize=10, fontweight="bold")
    fig.suptitle(f"E0={e0:.2f}, I0=1.1, seed={seed}: individual avalanche distributions", y=1.04, fontsize=10)
    fig.tight_layout()

    e_tag = f"e0_{e0:.2f}".replace(".", "p")
    output = e_dir / f"{e_tag}_seed{seed:02d}_ps_pt_k.png"
    fig.savefig(output, bbox_inches="tight")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return output


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(TABLE_DIR / "fig5_raw_avalanches.csv")
    fits = pd.read_csv(TABLE_DIR / "fig5_fit_results.csv")
    summary = selected_fit_rows(fits)
    counts = raw[raw["label"].str.contains("seed=", regex=False)].groupby("label").size().rename("avalanche_count")
    summary = summary.merge(counts, left_on="label", right_index=True, how="left")
    summary.to_csv(FIG_DIR / "individual_seed_tau_kappa_summary.csv", index=False)
    outputs = [plot_one_seed(raw, row) for _, row in summary.iterrows()]
    print(FIG_DIR)
    print(f"generated={len(outputs)}")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
