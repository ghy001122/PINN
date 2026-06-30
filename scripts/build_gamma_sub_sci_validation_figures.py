"""Build figure-ready plots for the gamma_sub SCI validation pack."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIGURE_DIR = Path("outputs/figures/gamma_sub_sci_validation")
DEFAULT_REPORT = Path("docs/codex_reports/gamma_sub_multi_protocol_and_profile_likelihood_validation_report.md")


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(_resolve(path).read_text(encoding="utf-8"))


def _read_csv(path: str | Path) -> list[dict[str, Any]]:
    with _resolve(path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return "unavailable"


def _bar_multi_protocol(rows: list[dict[str, Any]], path: Path) -> None:
    protocols = sorted({row["protocol"] for row in rows})
    means = [np.mean([float(row["relative_error"]) for row in rows if row["protocol"] == p]) for p in protocols]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(protocols, means, color="#4c78a8")
    ax.set_ylabel("mean relative gamma error")
    ax.set_title("Multi-protocol gamma_sub recoverability")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _profile_landscape(rows: list[dict[str, Any]], path: Path) -> None:
    gammas = sorted({float(row["gamma_sub"]) for row in rows})
    offsets = sorted({float(row["T_sw_offset_K"]) for row in rows})
    lookup = {(float(row["gamma_sub"]), float(row["T_sw_offset_K"])): float(row["objective"]) for row in rows}
    z = np.asarray([[lookup[(g, o)] for g in gammas] for o in offsets], dtype=float)
    fig, ax = plt.subplots(figsize=(7, 4.8))
    im = ax.imshow(z, aspect="auto", origin="lower", extent=[min(gammas), max(gammas), min(offsets), max(offsets)], cmap="viridis")
    ax.set_xscale("log")
    ax.set_xlabel("gamma_sub")
    ax.set_ylabel("T_sw offset (K)")
    ax.set_title("Port objective landscape")
    fig.colorbar(im, ax=ax, label="objective")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _profile_ridge(rows: list[dict[str, Any]], path: Path) -> None:
    prof = [row for row in rows if row["profile_type"] == "min_over_T_sw_for_gamma"]
    gammas = [float(row["fixed_value"]) for row in prof]
    offsets = [float(row["profiled_value"]) for row in prof]
    objs = [float(row["min_objective"]) for row in prof]
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(gammas, offsets, marker="o", color="#f58518", label="profiled T_sw offset")
    ax1.set_xscale("log")
    ax1.set_xlabel("gamma_sub")
    ax1.set_ylabel("best T_sw offset (K)")
    ax2 = ax1.twinx()
    ax2.plot(gammas, objs, marker="s", color="#54a24b", label="profile objective")
    ax2.set_ylabel("min objective")
    ax1.set_title("Profile-likelihood ridge")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _joint_boundary(rows: list[dict[str, Any]], path: Path) -> None:
    names = [row["case_name"] for row in rows]
    errors = [float(row["relative_error"]) for row in rows]
    ambiguity = [float(row["ambiguity_score"]) for row in rows]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - 0.18, errors, width=0.36, label="gamma relative error", color="#4c78a8")
    ax.bar(x + 0.18, ambiguity, width=0.36, label="ambiguity score", color="#e45756")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylabel("score")
    ax.set_title("Joint inversion boundary")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _protocol_design(rows: list[dict[str, Any]], path: Path) -> None:
    x = [abs(float(row["sensitivity_angle_or_cosine"])) for row in rows]
    y = [float(row["distinguishability_score"]) for row in rows]
    labels = [row["protocol_name"] for row in rows]
    colors = ["#54a24b" if row["recommended_for_gamma_sub_inversion"] == "True" else "#4c78a8" for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.scatter(x, y, s=70, c=colors)
    for xi, yi, label in zip(x, y, labels):
        ax.annotate(label, (xi, yi), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("abs cosine(gamma_sub sensitivity, T_sw sensitivity)")
    ax.set_ylabel("distinguishability score")
    ax.set_title("Protocol observability design preflight")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _write_report(path: Path, summaries: dict[str, Any]) -> None:
    branch = _git_value(["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _git_value(["rev-parse", "HEAD"])
    multi = summaries["multi"]
    profile = summaries["profile"]
    joint = summaries["joint"]
    design = summaries["design"]
    lines = [
        "# Gamma_Sub Multi-Protocol And Profile-Likelihood Validation Report",
        "",
        "All results are synthetic numerical digital-twin benchmark evidence. They are not experimental measurements, not full three-dimensional device simulations, and not sparse-port full hidden-field recovery.",
        "",
        "## Repository",
        "",
        f"- branch: `{branch}`",
        f"- commit hash at report generation: `{commit}`",
        "",
        "## Changed Files",
        "",
        "- `configs/gamma_sub_multi_protocol_recoverability.yaml`",
        "- `configs/gamma_sub_tsw_profile_likelihood.yaml`",
        "- `configs/gamma_sub_joint_inversion_boundary.yaml`",
        "- `configs/gamma_sub_protocol_observability_design.yaml`",
        "- `scripts/gamma_sub_validation_common.py`",
        "- `scripts/audit_gamma_sub_multi_protocol_recoverability.py`",
        "- `scripts/audit_gamma_sub_tsw_profile_likelihood.py`",
        "- `scripts/audit_gamma_sub_joint_inversion_boundary.py`",
        "- `scripts/audit_gamma_sub_protocol_observability_design.py`",
        "- `scripts/build_gamma_sub_sci_validation_figures.py`",
        "- `tests/test_gamma_sub_multi_protocol_recoverability.py`",
        "- `tests/test_gamma_sub_tsw_profile_likelihood.py`",
        "- `tests/test_gamma_sub_joint_inversion_boundary.py`",
        "- `tests/test_gamma_sub_protocol_observability_design.py`",
        "- lightweight JSON/CSV evidence under `outputs/tables/`",
        "- project state, registry, and paper-evidence Markdown files",
        "",
        "## Experiment Design",
        "",
        "1. Multi-protocol recoverability compares triangle, LTP/LTD, derived multi-amplitude synthetic, and mixed objectives under nominal, wide `T_sw` mismatch, and narrowed-prior scenarios.",
        "2. Profile likelihood scans the `gamma_sub` by `T_sw` port-objective landscape and extracts ridge/coupling diagnostics.",
        "3. Joint inversion boundary releases nuisance parameters in lightweight candidate grids to show where conditional `gamma_sub` recovery becomes ambiguous.",
        "4. Protocol observability design uses finite-difference sensitivity vectors to rank candidate stimulation protocols.",
        "",
        "## Key Results",
        "",
        "| block | key result | interpretation |",
        "| --- | --- | --- |",
        f"| Multi-protocol recoverability | `{multi['num_cases']}` cases; best protocol `{multi['best_protocol']}`; worst protocol `{multi['worst_protocol']}` | Tests whether recovery generalizes beyond triangle. |",
        f"| Profile likelihood | condition number `{profile['condition_number']}`; confounded `{profile['whether_gamma_sub_and_T_sw_are_locally_confounded']}` | Quantifies objective valley geometry. |",
        f"| Joint boundary | most ambiguous `{joint['most_ambiguous_case']['case_name']}`; worst error `{joint['worst_relative_error_case']['case_name']}` | Shows conditional, not arbitrary joint, identifiability. |",
        f"| Protocol design | best protocol `{design['best_protocol_by_distinguishability']['protocol_name']}`; recommended `{design['recommended_protocols']}` | Converts identifiability analysis into protocol-design guidance. |",
        "",
        "## Validation Commands",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -m pytest tests/test_gamma_sub_multi_protocol_recoverability.py tests/test_gamma_sub_tsw_profile_likelihood.py tests/test_gamma_sub_joint_inversion_boundary.py tests/test_gamma_sub_protocol_observability_design.py",
        ".\\.venv\\Scripts\\python.exe -m pytest tests/test_gamma_sub_auxiliary_observability_sweep.py tests/test_gamma_sub_tsw_confounding_phase_map.py tests/test_gamma_sub_tsw_prior_width_sweep.py tests/test_gamma_sub_temperature_anchor_placement.py tests/test_gamma_sub_scalar_baselines.py",
        ".\\.venv\\Scripts\\python.exe -m pytest",
        "```",
        "",
        "## Boundary",
        "",
        "- 是否修改 frozen GT: No.",
        "- 是否新增 F-SPS-PINN 实验: No.",
        "- Supported claim: synthetic numerical conditional identifiability and recoverability boundary for reduced `gamma_sub` inversion.",
        "- Still unsupported: experimental validation, full hidden-field recovery, full 3D device extraction, and unconstrained joint parameter identifiability.",
        "",
        "## Next Step",
        "",
        "Use these tables to draft the main manuscript figures and a concise reviewer-defense section. Do not expand into new F-SPS-PINN training until the constrained `gamma_sub` manuscript is drafted.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_figures(figure_dir: Path = DEFAULT_FIGURE_DIR, report_path: Path = DEFAULT_REPORT) -> dict[str, str]:
    figure_dir = _resolve(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    multi_summary = _read_json("outputs/tables/gamma_sub_multi_protocol_recoverability_summary.json")
    profile_summary = _read_json("outputs/tables/gamma_sub_tsw_profile_likelihood_summary.json")
    joint_summary = _read_json("outputs/tables/gamma_sub_joint_inversion_boundary_summary.json")
    design_summary = _read_json("outputs/tables/gamma_sub_protocol_observability_design_summary.json")
    multi_rows = _read_csv("outputs/tables/gamma_sub_multi_protocol_recoverability_cases.csv")
    profile_grid = _read_csv("outputs/tables/gamma_sub_tsw_profile_likelihood_grid.csv")
    profile_rows = _read_csv("outputs/tables/gamma_sub_tsw_profile_likelihood_profiles.csv")
    joint_rows = _read_csv("outputs/tables/gamma_sub_joint_inversion_boundary_cases.csv")
    design_rows = _read_csv("outputs/tables/gamma_sub_protocol_observability_design_cases.csv")
    outputs = {
        "multi_protocol_recoverability": figure_dir / "multi_protocol_recoverability.png",
        "profile_likelihood_landscape": figure_dir / "profile_likelihood_landscape.png",
        "profile_likelihood_ridge": figure_dir / "profile_likelihood_ridge.png",
        "joint_inversion_boundary": figure_dir / "joint_inversion_boundary.png",
        "protocol_observability_design": figure_dir / "protocol_observability_design.png",
    }
    _bar_multi_protocol(multi_rows, outputs["multi_protocol_recoverability"])
    _profile_landscape(profile_grid, outputs["profile_likelihood_landscape"])
    _profile_ridge(profile_rows, outputs["profile_likelihood_ridge"])
    _joint_boundary(joint_rows, outputs["joint_inversion_boundary"])
    _protocol_design(design_rows, outputs["protocol_observability_design"])
    _write_report(_resolve(report_path), {"multi": multi_summary, "profile": profile_summary, "joint": joint_summary, "design": design_summary})
    return {key: str(value.relative_to(ROOT)) for key, value in outputs.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    outputs = build_figures(args.figure_dir, args.report)
    print(json.dumps(outputs, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
