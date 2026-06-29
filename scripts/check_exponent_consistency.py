from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress


PROJECT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT / "results" / "tables" / "canonical_round1_20260608_summary"
OUT_DIR = PROJECT / "results" / "tables" / "canonical_round1_20260608_summary" / "exponent_consistency"
FIT_MODE = "fixed_xmin_paper_like"


def fit_gamma_emp(
    frame: pd.DataFrame,
    *,
    t_min: float,
    bins: int = 14,
    min_count: int = 3,
) -> dict[str, float]:
    data = frame[["duration_ms", "size"]].dropna()
    data = data[(data["duration_ms"] >= t_min) & (data["size"] > 0)]
    if data.empty or data["duration_ms"].nunique() < 2:
        return {
            "gamma_emp": np.nan,
            "gamma_emp_stderr": np.nan,
            "gamma_emp_r2": np.nan,
            "gamma_fit_points": 0,
            "gamma_fit_n_avalanches": int(len(data)),
        }

    t_values = data["duration_ms"].to_numpy(dtype=float)
    s_values = data["size"].to_numpy(dtype=float)
    edges = np.logspace(np.log10(t_values.min()), np.log10(t_values.max()), bins + 1)
    x_points: list[float] = []
    y_points: list[float] = []
    counts: list[int] = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (t_values >= left) & (t_values < right)
        if right == edges[-1]:
            mask = (t_values >= left) & (t_values <= right)
        n = int(mask.sum())
        if n < min_count:
            continue
        x_points.append(float(np.sqrt(left * right)))
        y_points.append(float(np.mean(s_values[mask])))
        counts.append(n)

    if len(x_points) < 3:
        return {
            "gamma_emp": np.nan,
            "gamma_emp_stderr": np.nan,
            "gamma_emp_r2": np.nan,
            "gamma_fit_points": len(x_points),
            "gamma_fit_n_avalanches": int(sum(counts)),
        }

    fit = linregress(np.log10(x_points), np.log10(y_points))
    return {
        "gamma_emp": float(fit.slope),
        "gamma_emp_stderr": float(fit.stderr),
        "gamma_emp_r2": float(fit.rvalue**2),
        "gamma_fit_points": len(x_points),
        "gamma_fit_n_avalanches": int(sum(counts)),
    }


def fit_rows_table(fits: pd.DataFrame) -> pd.DataFrame:
    selected = fits[fits["fit_mode"].eq(FIT_MODE)].copy()
    rows: list[dict[str, object]] = []
    for label, group in selected.groupby("label", sort=False):
        size = group[group["quantity"].eq("size")]
        duration = group[group["quantity"].eq("duration_ms")]
        if size.empty or duration.empty:
            continue
        tau = float(size.iloc[0]["alpha"])
        alpha = float(duration.iloc[0]["alpha"])
        rows.append(
            {
                "label": label,
                "tau_S": tau,
                "alpha_T": alpha,
                "gamma_pred": (alpha - 1.0) / (tau - 1.0),
                "size_xmin": float(size.iloc[0]["xmin"]),
                "duration_xmin": float(duration.iloc[0]["xmin"]),
                "is_seed": "seed=" in str(label),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(TABLE_DIR / "fig5_raw_avalanches.csv")
    fits = pd.read_csv(TABLE_DIR / "fig5_fit_results.csv")
    exponent_rows = fit_rows_table(fits)

    rows: list[dict[str, object]] = []
    for row in exponent_rows.itertuples(index=False):
        frame = raw[raw["label"].eq(row.label)]
        if frame.empty:
            continue
        gamma = fit_gamma_emp(frame, t_min=float(row.duration_xmin))
        delta = gamma["gamma_emp"] - float(row.gamma_pred)
        rows.append(
            {
                "label": row.label,
                "is_seed": row.is_seed,
                "tau_S": row.tau_S,
                "alpha_T": row.alpha_T,
                "gamma_pred": row.gamma_pred,
                **gamma,
                "delta_gamma": delta,
                "abs_delta_gamma": abs(delta) if np.isfinite(delta) else np.nan,
                "relative_delta_gamma": abs(delta) / abs(row.gamma_pred) if np.isfinite(delta) and row.gamma_pred else np.nan,
                "size_xmin": row.size_xmin,
                "duration_xmin": row.duration_xmin,
                "avalanche_count_total": int(len(frame)),
            }
        )
    result = pd.DataFrame(rows)
    result.sort_values(["is_seed", "abs_delta_gamma"], ascending=[True, True]).to_csv(
        OUT_DIR / "exponent_consistency_all.csv", index=False
    )
    result[result["is_seed"]].sort_values("abs_delta_gamma").to_csv(
        OUT_DIR / "exponent_consistency_seed_ranked.csv", index=False
    )
    result[~result["is_seed"]].sort_values("abs_delta_gamma").to_csv(
        OUT_DIR / "exponent_consistency_pooled_ranked.csv", index=False
    )
    print(OUT_DIR)
    print("pooled")
    print(result[~result["is_seed"]].sort_values("abs_delta_gamma").head(10).to_string(index=False))
    print("seed")
    print(result[result["is_seed"]].sort_values("abs_delta_gamma").head(10).to_string(index=False))


if __name__ == "__main__":
    main()
