"""Build final manuscript figure/table/claim lock documents.

The generated documents are planning artifacts for a synthetic numerical
digital-twin manuscript. PNG figures remain generated/ignored unless a later
submission task explicitly exports them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/tables/final_submission_lock_summary.json"


def _json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_final_submission_lock() -> dict[str, Any]:
    tol = _json("outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json")
    dis = _json("outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json")
    rob = _json("outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json")
    ext = _json("outputs/tables/literature_targeted_curve_extraction_attempt_summary.json")
    figures = [
        ("Figure 1", "Synthetic digital-twin sparse-port inverse workflow", "docs/gt_v1_acceptance_report.md; outputs/tables/pinn_identifiability_summary.json", "GT acceptance and identifiability scripts", "Sparse-port full-field recovery is ill-posed, motivating reduced inversion", "Measured device validation or unique full hidden-field recovery", "synthetic digital-twin"),
        ("Figure 2", "gamma_sub/T_sw confounding and calibration necessity", "outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json", "scripts/audit_gamma_sub_tsw_calibration_workflow.py", "T_sw calibration before gamma_sub inversion is required", "Unconditional joint gamma_sub/T_sw identifiability", "response-surface synthetic"),
        ("Figure 3", "T_sw calibration tolerance sweep", "outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json", "scripts/audit_gamma_sub_tsw_calibration_tolerance_sweep.py", f"Reliable recovery requires residual T_sw error around {tol.get('maximum_tolerable_calibration_error_for_le_0p15')} K or tighter under the <=15% criterion", "Experimental calibration accuracy claim", "response-surface synthetic"),
        ("Figure 4", "Calibration-vs-protocol disentanglement", "outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json", "scripts/audit_gamma_sub_calibration_protocol_disentanglement.py", dis.get("manuscript_claim_update", "Protocol and calibration gains are separated"), "Protocol identity alone solves the inverse problem", "response-surface synthetic"),
        ("Figure 5", "Calibrated protocol robustness", "outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json", "scripts/audit_gamma_sub_calibrated_protocol_robustness_final.py", f"{rob.get('best_protocol')} is the strongest ODE-backed synthetic candidate under calibrated priors", "Experimentally validated stimulation protocol", "simulator-backed synthetic"),
        ("Figure 6", "Recoverability phase diagram and statistical robustness", "outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json; outputs/tables/gamma_sub_statistical_robustness_summary.json", "scripts/audit_gamma_sub_recoverability_phase_diagram.py; scripts/audit_gamma_sub_statistical_robustness.py", "Recoverable and non-recoverable regions are mapped under bounded priors", "All dense points are fresh ODE solves", "response-surface with qualification"),
        ("Figure 7 or Supplementary", "Literature parameter sanity / external curve status", "outputs/tables/literature_targeted_curve_extraction_attempt_summary.json", "scripts/attempt_literature_curve_extraction_from_sources.py", f"External curve fitting remains blocked: {ext.get('blocked_reason_if_any')}", "Fitted literature curves without digitized data", "literature-prior / blocked external data"),
    ]
    lines = ["# Final Figure List", "", "All figures are for a synthetic numerical digital-twin benchmark, not experimental data.", "", "| Figure | Title | Data table | Script | Supported claim | Forbidden overclaim | Evidence label | Caption draft |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for fig, title, data, script, claim, forbid, label in figures:
        caption = f"{fig} summarizes {title.lower()} using {label} evidence."
        lines.append(f"| {fig} | {title} | `{data}` | `{script}` | {claim} | {forbid} | {label} | {caption} |")
    paper = ROOT / "docs/paper"
    paper.mkdir(parents=True, exist_ok=True)
    (paper / "final_figure_list.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tables = [
        ("Table 1", "Frozen GT v1.1 benchmark metrics", "docs/gt_v1_acceptance_report.md"),
        ("Table 2", "Identifiability and hidden-field limitation summary", "outputs/tables/pinn_identifiability_summary.json"),
        ("Table 3", "Prior registry and literature sanity", "docs/parameter_prior_registry.md; data/literature/literature_parameter_sanity_table.csv"),
        ("Table 4", "T_sw calibration tolerance", "outputs/tables/gamma_sub_tsw_calibration_tolerance_sweep_summary.json"),
        ("Table 5", "Calibration-vs-protocol disentanglement", "outputs/tables/gamma_sub_calibration_protocol_disentanglement_summary.json"),
        ("Table 6", "Calibrated protocol robustness", "outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json"),
        ("Supplementary Table", "F-SPS negative/small-run benchmark", "outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json"),
    ]
    table_lines = ["# Final Table List", "", "All tables report synthetic numerical digital-twin evidence unless explicitly marked as literature-prior metadata.", "", "| Table | Content | Source |", "| --- | --- | --- |"]
    for table, content, source in tables:
        table_lines.append(f"| {table} | {content} | `{source}` |")
    (paper / "final_table_list.md").write_text("\n".join(table_lines) + "\n", encoding="utf-8")
    claim_lines = ["# Final Claim Matrix", "", "Allowed claims are restricted to synthetic numerical digital-twin evidence.", "", "| Claim | Status | Required qualifier | Forbidden wording |", "| --- | --- | --- | --- |",
        "| Sparse-port full hidden-field recovery is ill-posed in the current benchmark | Supported | one-dimensional synthetic benchmark | unique full-field recovery |",
        "| gamma_sub is a reduced inverse target | Supported conditionally | fixed or tightly bounded priors | unconditional identifiability |",
        "| T_sw calibration is required before gamma_sub inversion | Supported | response-surface and ODE-backed synthetic audits | measured calibration result |",
        f"| Calibrated protocol robustness can be a main figure | {'Supported' if rob.get('whether_ready_as_main_figure') else 'Qualified'} | synthetic ODE-backed, calibrated priors | experimental protocol validation |",
        f"| Literature curve fitting validates model curves | {'Blocked' if not ext.get('whether_ready_for_literature_curve_ingestion_rerun') else 'Qualified'} | requires provenance-backed CSV/JSON data | fitted public curves without data |",
        "| F-SPS-PINN is superior | Not supported | appendix/future work only | performance superiority |",
    ]
    (paper / "final_claim_matrix.md").write_text("\n".join(claim_lines) + "\n", encoding="utf-8")
    (paper / "results_narrative_locked_v1.md").write_text(f"""# Results Narrative Locked V1\n\nAll results are synthetic numerical digital-twin benchmark evidence, not experimental data.\n\nThe manuscript should present a narrow chain: sparse-port hidden-field recovery is ill-posed, target-space reduction is required, `gamma_sub` is conditionally recoverable under fixed or tightly bounded priors, and `T_sw` calibration is the central boundary condition. The new tolerance sweep quantifies the required calibration accuracy, the disentanglement audit separates calibration gain from protocol gain, and the ODE-backed robustness audit decides whether calibrated protocol evidence can be used as a main figure.\n\nExternal curve fitting is not claimed because the targeted extraction attempt found no provenance-backed digitized numerical curve table.\n""", encoding="utf-8")
    (paper / "methods_narrative_locked_v1.md").write_text("""# Methods Narrative Locked V1\n\nThe method is a calibration-gated sparse-port reduced inversion workflow. First, use literature/engineering priors and a calibration or probe step to constrain `T_sw`. Second, estimate only `gamma_sub` from port `G/I` response with fixed or tightly bounded nuisance parameters. Third, audit protocol robustness with ODE-backed synthetic cases. This is not a full hidden-field PINN recovery claim.\n""", encoding="utf-8")
    (paper / "limitations_locked_v1.md").write_text("""# Limitations Locked V1\n\n1. Synthetic numerical digital-twin benchmark only.\n2. No measured experimental validation.\n3. No full 3D device model.\n4. No sparse-port unique full hidden-field recovery.\n5. `gamma_sub` recovery requires fixed or tightly bounded `T_sw`, `tau_m`, `sigma_on0`, `eta_A`, and micro-defect priors.\n6. External curve fitting remains blocked until provenance-backed digitized numerical curves are added.\n7. F-SPS-PINN evidence remains appendix/future-work material.\n""", encoding="utf-8")
    summary = {
        "benchmark": "final_submission_lock",
        "note": "Final manuscript planning lock for synthetic numerical digital-twin evidence.",
        "num_figures_locked": len(figures),
        "num_tables_locked": len(tables),
        "claim_matrix_locked": True,
        "external_curve_status": ext.get("blocked_reason_if_any"),
        "calibrated_protocol_main_figure_ready": bool(rob.get("whether_ready_as_main_figure")),
        "outputs": {
            "summary_json": "outputs/tables/final_submission_lock_summary.json",
            "figure_list": "docs/paper/final_figure_list.md",
            "table_list": "docs/paper/final_table_list.md",
            "claim_matrix": "docs/paper/final_claim_matrix.md",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    print(json.dumps(build_final_submission_lock(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
