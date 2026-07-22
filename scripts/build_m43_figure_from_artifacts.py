"""Rebuild the M43 figure from locked CSV artifacts without PDE execution."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "outputs/tables/m43_finite_width_thermal_spreading_cases.csv"
REFERENCE = ROOT / "outputs/tables/m43_transient_green_reference.csv"
FIGURE = ROOT / "outputs/figures/m43/m43_thermal_spreading_closure.png"
SUMMARY = ROOT / "outputs/tables/m43_finite_width_thermal_spreading_summary.json"
MANIFEST = ROOT / "outputs/tables/m43_figure_postprocessing_manifest.json"
REFERENCE_CODE = ROOT / "src/pinnpcm/physics/m43_thermal_spreading_reference.py"
FORMAL_FIGURE_SHA256 = "E0A21E7EDD2ED7992C3238B4676A8BABEFE4BCDA6D65E1AEC64F9CF45015C6F4"
INTERMEDIATE_FIGURE_SHA256 = "429C6FBB4801BF9A79E890F6DC67630873C682A276573D92CAEEAF5FD6143F18"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def value(row: dict[str, str], key: str):
    raw = row.get(key, "")
    return None if raw in (None, "") else json.loads(raw)


def main() -> int:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if sha256(CASES) != summary["artifact_sha256"]["cases"]:
        raise RuntimeError("locked M43 cases CSV hash mismatch")
    if sha256(REFERENCE) != summary["artifact_sha256"]["transient_reference"]:
        raise RuntimeError("locked M43 transient-reference CSV hash mismatch")
    if sha256(REFERENCE_CODE) != summary["runtime_code_sha256"]["reference"]:
        raise RuntimeError("locked M43 independent-reference code hash mismatch")
    if summary["decision"] != "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY":
        raise RuntimeError("unexpected M43 terminal decision")

    rows = {row["case_id"]: row for row in read_csv(CASES)}
    refs = read_csv(REFERENCE)
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.2), constrained_layout=True)
    rho_line = np.linspace(1.0, 5.0, 161)
    # Plot the locked analytical curve by interpolating only for display from
    # the production formula's two endpoint values is not valid; import the
    # independent reference function, which performs no PDE forward.
    from pinnpcm.physics.m43_thermal_spreading_reference import steady_dimensionless_theta
    axes[0].plot(rho_line, [steady_dimensionless_theta(r) for r in rho_line], "k-", label="Eq. (21)")
    markers = {
        "square_steady_M1D3": (1.0, "o"),
        "square_steady_M2D3": (1.0, "s"),
        "square_steady_M3D3": (1.0, "^"),
        "square_steady_M3D2": (1.0, "D"),
        "square_steady_M3D1": (1.0, "P"),
        "rho5_steady_M2D3": (5.0, "s"),
        "rho5_steady_M3D3": (5.0, "^"),
        "rho5_steady_M3D2": (5.0, "D"),
    }
    for case_id, (rho, marker) in markers.items():
        axes[0].scatter([rho], [float(value(rows[case_id], "Theta"))], marker=marker, s=54, label=case_id.replace("_steady", ""))
    axes[0].set(xlabel=r"aspect ratio $\rho$", ylabel=r"$\Theta=k\sqrt{A_s}R_s$", title="Steady independent-reference closure")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=7, ncol=2)

    times = np.asarray([float(row["time_s"]) for row in refs])
    green = np.asarray([float(row["Z_green_fine_K_W"]) for row in refs])
    fvm_fine = np.asarray(value(rows["rho5_transient_M3D3_fine"], "Zth_K_W"), dtype=float)
    fvm_base = np.asarray(value(rows["rho5_transient_M3D3_base"], "Zth_K_W"), dtype=float)
    xz = np.asarray(value(rows["rho5_xz_M3D3_base"], "Zth_K_W"), dtype=float)
    axes[1].semilogx(times, green, "k-", label="Green reference")
    axes[1].semilogx(times, fvm_fine, "o-", label="3D FVM (fine time)")
    axes[1].semilogx(times, xz, "s--", label="x-z comparator")
    twin = axes[1].twinx()
    # Match the formal finite-width gate contract: base x-z against base 3D.
    bias = np.abs(xz - fvm_base) / np.maximum(np.abs(fvm_base), 1.0e-300)
    bias_line = twin.semilogx(
        times,
        bias,
        color="#b55d47",
        linestyle=":",
        label="finite-width bias (matched base)",
    )[0]
    twin.set_ylabel("finite-width bias")
    twin.set_ylim(bottom=0.0)
    axes[1].set(xlabel="time (s)", ylabel=r"$Z_{th}$ (K/W)", title="Transient reference, 3D, and x-z comparator")
    axes[1].grid(alpha=0.25)
    axes[1].legend(axes[1].lines + [bias_line], [line.get_label() for line in axes[1].lines] + [bias_line.get_label()], fontsize=8, loc="lower right")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=180)
    plt.close(fig)

    final_figure_sha256 = sha256(FIGURE)
    builder_sha256 = sha256(Path(__file__))
    summary["artifact_sha256"]["figure"] = final_figure_sha256
    summary["postprocessing_code_sha256"] = {"figure_builder": builder_sha256}
    summary["visualization_only_amendment"] = {
        "formal_figure_sha256": FORMAL_FIGURE_SHA256,
        "intermediate_figure_sha256": INTERMEDIATE_FIGURE_SHA256,
        "final_figure_sha256": final_figure_sha256,
        "reason": "Restore physical x coordinates and align displayed bias with the formal matched-base contract.",
        "pde_forwards": 0,
        "gate_values_changed": False,
        "cases_csv_changed": False,
        "transient_reference_csv_changed": False,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": "m43_figure_postprocessing_manifest_v1",
        "evidence_role": "visualization_only_non_voting_amendment",
        "formal_figure_sha256": FORMAL_FIGURE_SHA256,
        "intermediate_figure_sha256": INTERMEDIATE_FIGURE_SHA256,
        "final_figure_sha256": final_figure_sha256,
        "builder_sha256": builder_sha256,
        "locked_input_sha256": {
            "cases": sha256(CASES),
            "transient_reference": sha256(REFERENCE),
            "reference_code": sha256(REFERENCE_CODE),
        },
        "bias_contract": "rho5_xz_M3D3_base versus rho5_transient_M3D3_base",
        "pde_forwards": 0,
        "gate_values_changed": False,
        "cases_csv_changed": False,
        "transient_reference_csv_changed": False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
