"""Plot v1 synthetic Ground Truth outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.utils.io import ensure_dir
from pinnpcm.visualization.plots import save_figure


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Plot synthetic Ground Truth v1 data.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--protocol", choices=["auto", "triangle", "ltp_ltd"], default="auto")
    return parser


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    """Load an npz archive into memory."""

    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _plot_map(
    t: np.ndarray,
    x: np.ndarray,
    values: np.ndarray,
    title: str,
    cbar_label: str,
    path: Path,
) -> None:
    """Save a time-space map."""

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    mesh = ax.pcolormesh(t * 1e3, x * 1e9, values.T, shading="auto")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label(cbar_label)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("x (nm)")
    ax.set_title(title)
    save_figure(fig, path)


def _params_from_data(data: dict[str, np.ndarray]) -> dict[str, float]:
    """Parse JSON-serialized parameter metadata from a Ground Truth npz."""

    if "params_json" not in data:
        return {}
    raw = data["params_json"]
    text = str(raw.item() if hasattr(raw, "item") else raw)
    return json.loads(text)


def _infer_protocol(input_path: Path, requested: str) -> str:
    """Infer the voltage protocol from CLI input when possible."""

    if requested != "auto":
        return requested
    return "ltp_ltd" if "ltp_ltd" in input_path.stem else "triangle"


def _pulse_conductance(voltage: np.ndarray, conductance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return pulse indices and per-pulse conductance values for pulse trains."""

    threshold = 0.1 * max(float(np.max(np.abs(voltage))), 1.0e-30)
    active = np.abs(voltage) > threshold
    starts: list[int] = []
    ends: list[int] = []
    in_segment = False
    start = 0

    for idx, is_active in enumerate(active):
        if is_active and not in_segment:
            start = idx
            in_segment = True
        elif not is_active and in_segment:
            starts.append(start)
            ends.append(idx)
            in_segment = False
    if in_segment:
        starts.append(start)
        ends.append(active.size)

    pulse_g = []
    for start_idx, end_idx in zip(starts, ends):
        segment_g = conductance[start_idx:end_idx]
        if segment_g.size:
            pulse_g.append(float(np.mean(segment_g)))

    pulse_index = np.arange(1, len(pulse_g) + 1, dtype=int)
    return pulse_index, np.asarray(pulse_g, dtype=float)


def main() -> None:
    """CLI entrypoint."""

    args = build_parser().parse_args()
    outdir = ensure_dir(args.outdir)
    data = _load_npz(args.input)
    params = _params_from_data(data)
    protocol = _infer_protocol(args.input, args.protocol)

    x = data["x"]
    t = data["t"]
    voltage = data["V"]
    current = data["I"]
    conductance = data["G"]
    delta_defect = data["c_v"] - data["c_v"][0:1, :]
    delta_temperature = data["T"] - float(params.get("T0", data["T"][0].mean()))
    delta_m = data["m"] - data["m"][0:1, :]

    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    ax.plot(voltage, current * 1e9, linewidth=1.8)
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (nA)")
    ax.set_title("Synthetic I-V Curve")
    save_figure(fig, outdir / "iv_curve.png")

    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    ax.plot(t * 1e3, conductance * 1e9, linewidth=1.8)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Conductance (nS)")
    ax.set_title("Synthetic Conductance vs Time")
    save_figure(fig, outdir / "g_vs_time.png")

    _plot_map(t, x, data["T"], "Temperature Field", "Temperature (K)", outdir / "temperature_map.png")
    _plot_map(t, x, data["c_v"], "Effective Defect State", "c_v (dimensionless)", outdir / "defect_map.png")
    _plot_map(t, x, data["m"], "Effective Conductive-State Fraction", "m (dimensionless)", outdir / "m_state_map.png")
    _plot_map(t, x, data["sigma"], "Conductivity Field", "Conductivity (S/m)", outdir / "sigma_map.png")
    _plot_map(t, x, delta_defect, "Defect-State Change", "Delta c_v (dimensionless)", outdir / "delta_defect_map.png")
    _plot_map(t, x, delta_temperature, "Temperature Rise", "Delta T (K)", outdir / "delta_temperature_map.png")
    _plot_map(t, x, delta_m, "Conductive-State Change", "Delta m (dimensionless)", outdir / "delta_m_map.png")

    fig, ax_v = plt.subplots(figsize=(6.0, 4.0))
    ax_i = ax_v.twinx()
    ax_v.plot(t * 1e3, voltage, color="tab:blue", linewidth=1.8, label="Voltage")
    ax_i.plot(t * 1e3, current * 1e9, color="tab:red", linewidth=1.4, label="Current")
    ax_v.set_xlabel("Time (ms)")
    ax_v.set_ylabel("Voltage (V)", color="tab:blue")
    ax_i.set_ylabel("Current (nA)", color="tab:red")
    ax_v.tick_params(axis="y", labelcolor="tab:blue")
    ax_i.tick_params(axis="y", labelcolor="tab:red")
    ax_v.set_title("Voltage and Current vs Time")
    fig.tight_layout()
    save_figure(fig, outdir / "voltage_current_time.png")

    if protocol == "ltp_ltd":
        pulse_index, pulse_g = _pulse_conductance(voltage, conductance)
        if pulse_g.size:
            g0 = pulse_g[0] if abs(pulse_g[0]) > 1.0e-30 else 1.0
            fig, ax = plt.subplots(figsize=(5.4, 3.8))
            ax.plot(pulse_index, pulse_g / g0, marker="o", linewidth=1.8)
            ax.set_xlabel("Pulse index")
            ax.set_ylabel("G / G0 (dimensionless)")
            ax.set_title("Normalized Conductance vs Pulse Index")
            ax.grid(True, alpha=0.25)
            save_figure(fig, outdir / "normalized_g_vs_pulse.png")

    print(f"Saved figures to: {outdir}")


if __name__ == "__main__":
    main()
