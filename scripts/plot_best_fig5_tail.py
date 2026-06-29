from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT / "results" / "tables" / "canonical_round1_20260608_summary"
FIG_DIR = PROJECT / "results" / "figures" / "canonical_round1_20260608_summary" / "best_e0_tail"
BEST_LABEL = "E0=6.950, I0=1.1"
FIT_MODE = "fixed_xmin_paper_like"


def _positive(series: pd.Series) -> np.ndarray:
    values = series.to_numpy(dtype=float)
    return values[np.isfinite(values) & (values > 0)]


def _log_density(values: np.ndarray, bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
    edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins + 1)
    counts, edges = np.histogram(values, bins=edges, density=True)
    centers = np.sqrt(edges[:-1] * edges[1:])
    valid = counts > 0
    return centers[valid], counts[valid]


def _powerlaw_reference(
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
    xs = np.logspace(np.log10(xmin), np.log10(xmax), 120)
    ys = anchor_y * (xs / anchor_x) ** (-exponent)
    return xs, ys


def _panel_distribution(ax, frame: pd.DataFrame, fits: pd.DataFrame, value: str, xlabel: str, ylabel: str, fit_name: str) -> None:
    data = _positive(frame[value])
    x, y = _log_density(data)
    fit = fits[
        (fits["label"] == BEST_LABEL)
        & (fits["quantity"] == value)
        & (fits["fit_mode"] == FIT_MODE)
    ].iloc[0]
    exponent = float(fit["alpha"])
    xmin = float(fit["xmin"])
    xmax = float(data.max())
    ref_x, ref_y = _powerlaw_reference(x, y, exponent=exponent, xmin=xmin, xmax=xmax)

    ax.plot(x, y, "-o", color="#6DA43A", linewidth=1.25, markersize=3.2, label=BEST_LABEL.replace(".950", ".95"))
    ax.plot(ref_x, ref_y, "k--", linewidth=1.0, label=rf"${fit_name}={exponent:.2f}$")
    ax.axvspan(xmin, xmax, color="#6DA43A", alpha=0.08, linewidth=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(frameon=True, fontsize=8, loc="best")
    ax.spines[["top", "right"]].set_visible(False)


def _panel_size_duration(ax, frame: pd.DataFrame) -> None:
    data = frame[["duration_ms", "size"]].dropna()
    data = data[(data["duration_ms"] > 0) & (data["size"] > 0)]
    t = data["duration_ms"].to_numpy(dtype=float)
    s = data["size"].to_numpy(dtype=float)
    edges = np.logspace(np.log10(t.min()), np.log10(t.max()), 18)
    centers: list[float] = []
    mean_s: list[float] = []
    p25: list[float] = []
    p75: list[float] = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (t >= left) & (t < right)
        if right == edges[-1]:
            mask = (t >= left) & (t <= right)
        if mask.sum() < 3:
            continue
        centers.append(float(np.sqrt(left * right)))
        mean_s.append(float(np.mean(s[mask])))
        p25.append(float(np.percentile(s[mask], 25)))
        p75.append(float(np.percentile(s[mask], 75)))

    centers_arr = np.asarray(centers)
    mean_arr = np.asarray(mean_s)
    p25_arr = np.asarray(p25)
    p75_arr = np.asarray(p75)
    ax.fill_between(centers_arr, p25_arr, p75_arr, color="#6DA43A", alpha=0.18, linewidth=0, label="IQR")
    ax.plot(centers_arr, mean_arr, "-o", color="#285C2E", linewidth=1.35, markersize=3.2, label=r"$\langle S\rangle(T)$")
    ax.scatter(t, s, s=4, color="#6DA43A", alpha=0.08, rasterized=True)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("T")
    ax.set_ylabel("S")
    ax.legend(frameon=True, fontsize=8, loc="best")
    ax.spines[["top", "right"]].set_visible(False)


def main() -> None:
    raw = pd.read_csv(TABLE_DIR / "fig5_raw_avalanches.csv")
    fits = pd.read_csv(TABLE_DIR / "fig5_fit_results.csv")
    frame = raw[raw["label"] == BEST_LABEL].copy()
    if frame.empty:
        raise RuntimeError(f"No avalanches found for {BEST_LABEL}")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(
        {
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
        }
    ):
        fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.0), dpi=220)
        _panel_distribution(axes[0], frame, fits, "size", "S", "P(S)", r"\alpha")
        _panel_distribution(axes[1], frame, fits, "duration_ms", "T", "P(T)", r"\beta")
        _panel_size_duration(axes[2], frame)
        for panel, ax in zip(["(a)", "(b)", "(c)"], axes, strict=True):
            ax.text(-0.14, 1.05, panel, transform=ax.transAxes, fontsize=10, fontweight="bold")
        fig.suptitle(f"{BEST_LABEL}: tail distributions from 5 pooled seeds", y=1.02, fontsize=10)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "best_e0_tail_triptych.png", bbox_inches="tight")
        fig.savefig(FIG_DIR / "best_e0_tail_triptych.svg", bbox_inches="tight")

        single_specs = [
            ("best_e0_ps_vs_s", lambda ax: _panel_distribution(ax, frame, fits, "size", "S", "P(S)", r"\alpha")),
            ("best_e0_pt_vs_t", lambda ax: _panel_distribution(ax, frame, fits, "duration_ms", "T", "P(T)", r"\beta")),
            ("best_e0_s_vs_t", lambda ax: _panel_size_duration(ax, frame)),
        ]
        for name, draw in single_specs:
            single, ax = plt.subplots(figsize=(4.2, 3.2), dpi=220)
            draw(ax)
            single.tight_layout()
            single.savefig(FIG_DIR / f"{name}.png", bbox_inches="tight")
            single.savefig(FIG_DIR / f"{name}.svg", bbox_inches="tight")
            plt.close(single)
        plt.close(fig)

    summary = {
        "label": BEST_LABEL,
        "avalanche_count": int(len(frame)),
        "size_min": float(frame["size"].min()),
        "size_max": float(frame["size"].max()),
        "duration_min_ms": float(frame["duration_ms"].min()),
        "duration_max_ms": float(frame["duration_ms"].max()),
    }
    pd.DataFrame([summary]).to_csv(FIG_DIR / "best_e0_tail_summary.csv", index=False)
    print(FIG_DIR)
    print(summary)


if __name__ == "__main__":
    main()
