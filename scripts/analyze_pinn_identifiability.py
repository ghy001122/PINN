"""Audit terminal-observation identifiability for the frozen GT v1.1 benchmark.

The analysis is descriptive. It reads the frozen synthetic triangle benchmark,
computes correlations between terminal signals and hidden fields, and writes
lightweight tables plus reproducible figures.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np


DEFAULT_INPUT = Path("data/processed/gt_v1_acceptance/gt_triangle.npz")
DEFAULT_TABLE_DIR = Path("outputs/tables")
DEFAULT_FIGURE_DIR = Path("outputs/figures/pinn_identifiability")


def _as_float(value: np.floating | float) -> float | None:
    if np.isfinite(value):
        return float(value)
    return None


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float).reshape(-1)
    b = np.asarray(b, dtype=float).reshape(-1)
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < 3:
        return float("nan")
    a = a[mask]
    b = b[mask]
    if float(np.std(a)) < 1.0e-15 or float(np.std(b)) < 1.0e-15:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _lagged_corr(reference: np.ndarray, signal: np.ndarray, max_lag: int) -> list[dict[str, float | int | None]]:
    rows: list[dict[str, float | int | None]] = []
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            ref = reference[:lag]
            sig = signal[-lag:]
        elif lag > 0:
            ref = reference[lag:]
            sig = signal[:-lag]
        else:
            ref = reference
            sig = signal
        rows.append({"lag_steps": lag, "correlation": _as_float(_pearson(ref, sig))})
    return rows


def _best_lag(rows: Iterable[dict[str, float | int | None]]) -> dict[str, float | int | None]:
    finite_rows = [row for row in rows if row["correlation"] is not None]
    if not finite_rows:
        return {"lag_steps": None, "correlation": None}
    return max(finite_rows, key=lambda row: abs(float(row["correlation"])))


def _corr_matrix(series: dict[str, np.ndarray]) -> tuple[list[str], np.ndarray]:
    labels = list(series)
    mat = np.empty((len(labels), len(labels)), dtype=float)
    for i, left in enumerate(labels):
        for j, right in enumerate(labels):
            mat[i, j] = _pearson(series[left], series[right])
    return labels, mat


def _plot_heatmap(labels: list[str], mat: np.ndarray, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    image = ax.imshow(mat, vmin=-1.0, vmax=1.0, cmap="coolwarm")
    ax.set_xticks(np.arange(len(labels)), labels=labels, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(labels)), labels=labels)
    ax.set_title("Terminal and hidden-field correlation")
    for i in range(len(labels)):
        for j in range(len(labels)):
            value = mat[i, j]
            text = "nan" if not np.isfinite(value) else f"{value:.2f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, label="Pearson r")
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def _plot_spatial_sensitivity(x: np.ndarray, profiles: dict[str, np.ndarray], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    x_nm = x * 1.0e9
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, values in profiles.items():
        ax.plot(x_nm, values, marker="o", linewidth=1.4, markersize=3, label=name)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("x (nm)")
    ax.set_ylabel("Pearson r with G(t)")
    ax.set_title("Spatial sensitivity profile")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def _plot_lag_correlation(lag_rows: dict[str, list[dict[str, float | int | None]]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, rows in lag_rows.items():
        lags = np.array([int(row["lag_steps"]) for row in rows], dtype=int)
        corr = np.array(
            [np.nan if row["correlation"] is None else float(row["correlation"]) for row in rows],
            dtype=float,
        )
        ax.plot(lags, corr, marker="o", linewidth=1.3, markersize=3, label=name)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("lag steps; positive means terminal signal leads hidden series")
    ax.set_ylabel("Pearson r")
    ax.set_title("Lag correlation with G(t)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def _write_correlation_csv(
    output: Path,
    terminal_correlations: dict[str, dict[str, float | None]],
    hidden_correlations: dict[str, float | None],
    spatial_profiles: dict[str, list[dict[str, float | None]]],
    lag_rows: dict[str, list[dict[str, float | int | None]]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "left", "right", "x_index", "x_m", "lag_steps", "correlation"],
        )
        writer.writeheader()
        for terminal, values in terminal_correlations.items():
            for field, corr in values.items():
                writer.writerow(
                    {
                        "category": "terminal_to_field",
                        "left": terminal,
                        "right": field,
                        "x_index": "",
                        "x_m": "",
                        "lag_steps": "",
                        "correlation": corr,
                    }
                )
        for pair, corr in hidden_correlations.items():
            left, right = pair.split("__")
            writer.writerow(
                {
                    "category": "hidden_to_hidden",
                    "left": left,
                    "right": right,
                    "x_index": "",
                    "x_m": "",
                    "lag_steps": "",
                    "correlation": corr,
                }
            )
        for field, rows in spatial_profiles.items():
            for idx, row in enumerate(rows):
                writer.writerow(
                    {
                        "category": "spatial_sensitivity_to_G",
                        "left": "G",
                        "right": field,
                        "x_index": idx,
                        "x_m": row["x_m"],
                        "lag_steps": "",
                        "correlation": row["correlation"],
                    }
                )
        for field, rows in lag_rows.items():
            for row in rows:
                writer.writerow(
                    {
                        "category": "lag_correlation_to_G",
                        "left": "G",
                        "right": field,
                        "x_index": "",
                        "x_m": "",
                        "lag_steps": row["lag_steps"],
                        "correlation": row["correlation"],
                    }
                )


def analyze(input_path: Path, table_dir: Path, figure_dir: Path, max_lag: int) -> dict[str, object]:
    with np.load(input_path) as data:
        keys = list(data.files)
        x = data["x"].astype(float)
        t = data["t"].astype(float)
        voltage = data["V"].astype(float)
        current = data["I"].astype(float)
        conductance = data["G"].astype(float)
        c_v = data["c_v"].astype(float)
        temperature = data["T"].astype(float)
        m = data["m"].astype(float)
        sigma = data["sigma"].astype(float)

    delta_t = temperature - temperature[0:1, :]
    delta_c_v = c_v - c_v[0:1, :]

    field_series = {
        "mean_delta_T": np.mean(delta_t, axis=1),
        "max_delta_T": np.max(delta_t, axis=1),
        "mean_delta_c_v": np.mean(delta_c_v, axis=1),
        "max_abs_delta_c_v": np.max(np.abs(delta_c_v), axis=1),
        "mean_m": np.mean(m, axis=1),
        "mean_sigma": np.mean(sigma, axis=1),
    }
    terminal_series = {
        "V": voltage,
        "I": current,
        "G": conductance,
    }

    terminal_correlations = {
        terminal: {field: _as_float(_pearson(values, field_values)) for field, field_values in field_series.items()}
        for terminal, values in terminal_series.items()
    }
    hidden_correlations = {
        "delta_T__sigma": _as_float(_pearson(delta_t, sigma)),
        "c_v__sigma": _as_float(_pearson(c_v, sigma)),
        "delta_c_v__sigma": _as_float(_pearson(delta_c_v, sigma)),
        "m__sigma": _as_float(_pearson(m, sigma)),
        "delta_T__m": _as_float(_pearson(delta_t, m)),
        "c_v__m": _as_float(_pearson(c_v, m)),
    }

    max_lag = min(max_lag, max(1, len(t) // 4))
    lag_rows = {
        field: _lagged_corr(conductance, values, max_lag)
        for field, values in {
            "mean_delta_T": field_series["mean_delta_T"],
            "mean_delta_c_v": field_series["mean_delta_c_v"],
            "mean_m": field_series["mean_m"],
            "mean_sigma": field_series["mean_sigma"],
        }.items()
    }
    best_lag = {field: _best_lag(rows) for field, rows in lag_rows.items()}

    spatial_arrays = {
        "delta_T": np.array([_pearson(conductance, delta_t[:, i]) for i in range(len(x))], dtype=float),
        "delta_c_v": np.array([_pearson(conductance, delta_c_v[:, i]) for i in range(len(x))], dtype=float),
        "m": np.array([_pearson(conductance, m[:, i]) for i in range(len(x))], dtype=float),
        "sigma": np.array([_pearson(conductance, sigma[:, i]) for i in range(len(x))], dtype=float),
    }
    spatial_profiles = {
        field: [
            {"x_m": float(x_i), "correlation": _as_float(corr)}
            for x_i, corr in zip(x, values, strict=True)
        ]
        for field, values in spatial_arrays.items()
    }
    peak_spatial_sensitivity = {
        field: {
            "x_m": float(x[int(np.nanargmax(np.abs(values)))]),
            "correlation": _as_float(values[int(np.nanargmax(np.abs(values)))]),
        }
        for field, values in spatial_arrays.items()
    }

    heatmap_series = {**terminal_series, **field_series}
    heatmap_labels, heatmap_matrix = _corr_matrix(heatmap_series)
    heatmap_path = figure_dir / "correlation_heatmap.png"
    spatial_path = figure_dir / "spatial_sensitivity.png"
    lag_path = figure_dir / "lag_correlation.png"
    _plot_heatmap(heatmap_labels, heatmap_matrix, heatmap_path)
    _plot_spatial_sensitivity(x, spatial_arrays, spatial_path)
    _plot_lag_correlation(lag_rows, lag_path)

    csv_path = table_dir / "pinn_identifiability_correlation.csv"
    _write_correlation_csv(csv_path, terminal_correlations, hidden_correlations, spatial_profiles, lag_rows)

    summary = {
        "benchmark": "Frozen Ground Truth v1.1 triangle synthetic numerical digital-twin benchmark.",
        "input_path": str(input_path),
        "npz_keys": keys,
        "n_time": int(len(t)),
        "n_x": int(len(x)),
        "terminal_to_field_correlations": terminal_correlations,
        "hidden_field_correlations": hidden_correlations,
        "best_lag_correlation_to_G": best_lag,
        "peak_spatial_sensitivity_to_G": peak_spatial_sensitivity,
        "field_dynamic_ranges": {
            "delta_T": {
                "min": float(np.min(delta_t)),
                "max": float(np.max(delta_t)),
                "time_mean_std": float(np.std(field_series["mean_delta_T"])),
            },
            "delta_c_v": {
                "min": float(np.min(delta_c_v)),
                "max": float(np.max(delta_c_v)),
                "time_mean_std": float(np.std(field_series["mean_delta_c_v"])),
            },
            "m": {
                "min": float(np.min(m)),
                "max": float(np.max(m)),
                "time_mean_std": float(np.std(field_series["mean_m"])),
            },
            "sigma": {
                "min": float(np.min(sigma)),
                "max": float(np.max(sigma)),
                "time_mean_std": float(np.std(field_series["mean_sigma"])),
            },
            "G": {
                "min": float(np.min(conductance)),
                "max": float(np.max(conductance)),
                "std": float(np.std(conductance)),
            },
            "I": {
                "min": float(np.min(current)),
                "max": float(np.max(current)),
                "std": float(np.std(current)),
            },
        },
        "interpretation": {
            "delta_T_identifiability": (
                "Weak from terminal signals alone. Mean and max delta_T are highly correlated with G, "
                "but their time series are also highly correlated with sigma and m, so the inverse problem "
                "is not unique without field anchors or additional thermal observations."
            ),
            "c_v_identifiability": (
                "Weakest among the audited hidden fields. delta_c_v changes slowly and has strong spatial "
                "structure, but terminal G only constrains an integrated conductance."
            ),
            "sigma_driver": (
                "Sigma is more directly aligned with m than with delta_c_v in this frozen benchmark."
            ),
            "v1_1_delta_T_reason": (
                "v1.1 did not significantly improve delta_T because the terminal port loss is sensitive "
                "to the integrated conductance, while multiple hidden-field combinations can yield similar "
                "G(t). The heat residual is approximate and does not add an independent thermal measurement."
            ),
            "next_step": (
                "Prioritize observability and narrative discipline: add or simulate auxiliary thermal/spatial "
                "observations for future inverse studies, keep current port-only results as an identifiability "
                "audit, and avoid claiming unique hidden-field recovery from terminal data alone."
            ),
        },
        "outputs": {
            "summary_json": str(table_dir / "pinn_identifiability_summary.json"),
            "correlation_csv": str(csv_path),
            "correlation_heatmap": str(heatmap_path),
            "spatial_sensitivity": str(spatial_path),
            "lag_correlation": str(lag_path),
        },
        "note": "This is a synthetic numerical digital-twin identifiability audit, not an experimental analysis.",
    }
    summary_path = table_dir / "pinn_identifiability_summary.json"
    table_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--max-lag", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze(args.input, args.table_dir, args.figure_dir, args.max_lag)
    print(json.dumps(summary["outputs"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
