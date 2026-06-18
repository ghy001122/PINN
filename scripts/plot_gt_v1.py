"""Plot v1 synthetic Ground Truth outputs."""

from __future__ import annotations

import argparse
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


def main() -> None:
    """CLI entrypoint."""

    args = build_parser().parse_args()
    outdir = ensure_dir(args.outdir)
    data = _load_npz(args.input)

    x = data["x"]
    t = data["t"]
    voltage = data["V"]
    current = data["I"]
    conductance = data["G"]

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

    print(f"Saved figures to: {outdir}")


if __name__ == "__main__":
    main()
