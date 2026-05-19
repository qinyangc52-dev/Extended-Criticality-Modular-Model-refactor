from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_avalanche_distribution(
    avalanches_by_label: dict[str, pd.DataFrame],
    value: str,
    fit_label: str | None = None,
    fit=None,
    output: str | Path | None = None,
):
    fig, ax = plt.subplots(figsize=(4.2, 3.2), dpi=160)
    for label, frame in avalanches_by_label.items():
        data = frame[value].to_numpy(dtype=float)
        data = data[np.isfinite(data) & (data > 0)]
        if data.size == 0:
            continue
        bins = np.logspace(np.log10(data.min()), np.log10(data.max()), 30)
        counts, edges = np.histogram(data, bins=bins, density=True)
        centers = np.sqrt(edges[:-1] * edges[1:])
        valid = counts > 0
        ax.plot(centers[valid], counts[valid], marker="o", linewidth=1.2, markersize=3, label=label)

    if fit is not None and fit_label is not None and fit_label in avalanches_by_label:
        data = avalanches_by_label[fit_label][value].to_numpy(dtype=float)
        data = data[np.isfinite(data) & (data > 0)]
        xs = np.logspace(np.log10(max(fit.xmin, data.min())), np.log10(data.max()), 80)
        ys = xs ** (-fit.alpha)
        ys *= 0.8 * ax.get_ylim()[1] / ys.max()
        ax.plot(xs, ys, "--", color="black", linewidth=1.2, label=f"power law alpha={fit.alpha:.2f}")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Avalanche size" if value == "size" else "Avalanche duration (ms)")
    ax.set_ylabel("Probability density")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, ax


def plot_hysteresis(medie_frame: pd.DataFrame, output: str | Path | None = None):
    fig, axes = plt.subplots(3, 1, figsize=(4.8, 6.0), dpi=160, sharex=True)
    axes[0].plot(medie_frame["sigma"], medie_frame["rate_hz"], linewidth=1.1)
    axes[0].set_ylabel("rate (Hz/neuron)")
    axes[1].plot(medie_frame["sigma"], medie_frame["q_max"] if "q_max" in medie_frame else medie_frame["fano"], linewidth=1.1)
    axes[1].set_ylabel("order / Fano")
    axes[2].plot(medie_frame["sigma"], medie_frame["fano"], linewidth=1.1)
    axes[2].set_ylabel("Fano")
    axes[2].set_xlabel("E0 / sigma")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, axes


def plot_metric_heatmap(summary: pd.DataFrame, metric: str, output: str | Path | None = None):
    pivot = summary.pivot_table(index="delta", columns="sigma", values=metric, aggfunc="mean").sort_index()
    fig, ax = plt.subplots(figsize=(4.2, 3.4), dpi=160)
    image = ax.imshow(pivot.to_numpy(), origin="lower", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{value:g}" for value in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{value:g}" for value in pivot.index])
    ax.set_xlabel("E0 / sigma")
    ax.set_ylabel("I0 / delta")
    ax.set_title(metric)
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, ax


def plot_raster(spikes: pd.DataFrame, max_spikes: int = 60000, output: str | Path | None = None):
    frame = spikes.iloc[:max_spikes]
    fig, ax = plt.subplots(figsize=(7, 3), dpi=160)
    ax.scatter(frame["time_ms"], frame["neuron"], s=0.35, color="black")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("neuron")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, ax


def plot_module_rate(rate: pd.DataFrame, output: str | Path | None = None):
    module_cols = [column for column in rate.columns if str(column).startswith("module_")]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=160)
    image = ax.imshow(rate[module_cols].T, origin="lower", aspect="auto", interpolation="nearest")
    ax.set_xlabel("time bin")
    ax.set_ylabel("module")
    fig.colorbar(image, ax=ax, label="rate")
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, ax


def plot_overlap(q_frame: pd.DataFrame, output: str | Path | None = None):
    q_cols = [column for column in q_frame.columns if str(column).startswith("q_")]
    fig, ax = plt.subplots(figsize=(7, 3), dpi=160)
    for column in q_cols[:8]:
        ax.plot(q_frame["t_end"], q_frame[column], linewidth=0.9, alpha=0.8)
    ax.plot(q_frame["t_end"], q_frame["q_max"], color="black", linewidth=1.1, label="q max")
    ax.axhline(0.8, color="black", linestyle="--", linewidth=0.9)
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("overlap")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    return fig, ax
