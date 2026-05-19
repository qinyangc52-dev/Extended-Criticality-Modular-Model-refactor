from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PowerLawFit:
    alpha: float
    sigma: float
    xmin: float
    xmax: float | None
    ks_distance: float
    likelihood_ratio: float
    p_value: float


def avalanche_table(rate_frame: pd.DataFrame, rate_threshold: float = 0.0) -> pd.DataFrame:
    """Extract synthetic avalanches using the paper's module-rate definition.

    A synthetic avalanche is a continuous interval with at least one module rate
    above zero. Size is the integral of the sum of module rates over the interval.
    """
    if "time_ms" not in rate_frame:
        raise ValueError("rate_frame must contain a time_ms column")
    module_columns = [column for column in rate_frame.columns if str(column).startswith("module_")]
    if not module_columns:
        raise ValueError("rate_frame does not contain module_* columns")

    times = rate_frame["time_ms"].to_numpy(dtype=float)
    rates = rate_frame[module_columns].to_numpy(dtype=float)
    if len(times) < 2:
        return pd.DataFrame(columns=["start_ms", "end_ms", "duration_ms", "size", "peak_rate"])

    dt = float(np.median(np.diff(times)))
    total_rate = rates.sum(axis=1)
    active = np.any(rates > rate_threshold, axis=1)
    rows: list[dict[str, float]] = []
    start: int | None = None
    for idx, is_active in enumerate(active):
        if is_active and start is None:
            start = idx
        elif not is_active and start is not None:
            rows.append(_summarize_avalanche(times, total_rate, start, idx, dt))
            start = None
    if start is not None:
        rows.append(_summarize_avalanche(times, total_rate, start, len(active), dt))
    return pd.DataFrame(rows)


def _summarize_avalanche(times: np.ndarray, total_rate: np.ndarray, start: int, stop: int, dt: float) -> dict[str, float]:
    interval = total_rate[start:stop]
    return {
        "start_ms": float(times[start]),
        "end_ms": float(times[stop - 1] + dt),
        "duration_ms": float((stop - start) * dt),
        "size": float(interval.sum() * dt),
        "peak_rate": float(interval.max()),
    }


def fit_power_law(values: pd.Series | np.ndarray, xmin: float | None = None, xmax: float | None = None) -> PowerLawFit:
    """Fit a power law and compare it with an exponential distribution."""
    import powerlaw

    data = np.asarray(values, dtype=float)
    data = data[np.isfinite(data) & (data > 0)]
    if data.size < 2:
        raise ValueError("Power-law fit requires at least two positive observations")
    fit = powerlaw.Fit(data, xmin=xmin, xmax=xmax, verbose=False)
    ratio, p_value = fit.distribution_compare("power_law", "exponential")
    return PowerLawFit(
        alpha=float(fit.power_law.alpha),
        sigma=float(fit.power_law.sigma),
        xmin=float(fit.power_law.xmin),
        xmax=None if fit.power_law.xmax is None else float(fit.power_law.xmax),
        ks_distance=float(fit.power_law.D),
        likelihood_ratio=float(ratio),
        p_value=float(p_value),
    )

