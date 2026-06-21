"""Analyze Ground Truth v1 outputs and write compact metrics JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.utils.io import ensure_dir, write_json


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Analyze Ground Truth v1 npz outputs.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, default=Path("outputs/tables/gt_v1_metrics"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--voltage-threshold-frac", type=float, default=0.05)
    return parser


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    """Load an npz archive into memory."""

    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _params_from_data(data: dict[str, np.ndarray]) -> dict[str, Any]:
    """Parse JSON-serialized parameter metadata from a Ground Truth npz."""

    raw = data.get("params_json")
    if raw is None:
        return {}
    text = str(raw.item() if hasattr(raw, "item") else raw)
    return json.loads(text)


def compute_metrics(data: dict[str, np.ndarray], voltage_threshold_frac: float = 0.05) -> dict[str, float]:
    """Compute quantitative acceptance metrics from a Ground Truth result."""

    voltage = np.asarray(data["V"], dtype=float)
    current = np.asarray(data["I"], dtype=float)
    conductance = np.asarray(data["G"], dtype=float)
    temperature = np.asarray(data["T"], dtype=float)
    defect = np.asarray(data["c_v"], dtype=float)
    m_state = np.asarray(data["m"], dtype=float)
    sigma = np.asarray(data["sigma"], dtype=float)
    params = _params_from_data(data)

    v_threshold = voltage_threshold_frac * max(float(np.max(np.abs(voltage))), 1.0e-30)
    active = np.abs(voltage) > v_threshold
    active_conductance = conductance[active]
    active_conductance = active_conductance[np.isfinite(active_conductance)]
    positive_g = active_conductance[active_conductance > 0.0]
    g_values = positive_g if positive_g.size else active_conductance

    if g_values.size:
        g_min = float(np.min(g_values))
        g_max = float(np.max(g_values))
    else:
        g_min = float(np.min(conductance))
        g_max = float(np.max(conductance))
    g_ratio = float(g_max / max(g_min, 1.0e-30))

    t0 = float(params.get("T0", temperature[0].mean()))
    return {
        "I_min": float(np.min(current)),
        "I_max": float(np.max(current)),
        "G_min": g_min,
        "G_max": g_max,
        "G_ratio": g_ratio,
        "max_delta_T": float(np.max(temperature - t0)),
        "max_abs_delta_c_v": float(np.max(np.abs(defect - defect[0:1, :]))),
        "max_abs_delta_m": float(np.max(np.abs(m_state - m_state[0:1, :]))),
        "sigma_min": float(np.min(sigma)),
        "sigma_max": float(np.max(sigma)),
        "approximate_iv_loop_area": float(abs(np.trapz(current, voltage))),
    }


def main() -> None:
    """CLI entrypoint."""

    args = build_parser().parse_args()
    data = _load_npz(args.input)
    metrics = compute_metrics(data, voltage_threshold_frac=args.voltage_threshold_frac)
    output_path = args.output
    if output_path is None:
        outdir = ensure_dir(args.outdir)
        output_path = outdir / f"{args.input.stem}_metrics.json"
    write_json(output_path, metrics)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    print(f"Saved metrics: {output_path}")


if __name__ == "__main__":
    main()
