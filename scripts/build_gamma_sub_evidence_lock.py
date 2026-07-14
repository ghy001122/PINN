"""Build the locked gamma_sub evidence-to-manuscript chain from declarative YAML."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = Path("configs/gamma_sub_evidence_lock.yaml")
DEFAULT_JSON = Path("outputs/tables/gamma_sub_evidence_lock_summary.json")
DEFAULT_LOCK = Path("docs/paper/gamma_sub_evidence_lock.md")
DEFAULT_CLAIMS = Path("docs/paper/final_claim_matrix.md")
DEFAULT_FIGURES = Path("docs/paper/final_figure_list.md")
ALLOWED_STATUSES = {"supported", "qualified_supported", "failed_but_informative", "forbidden"}


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_yaml(path: Path) -> dict[str, Any]:
    with _resolve(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Evidence-lock config must be a mapping.")
    return payload


def _source_path(value: str) -> Path:
    return ROOT / value.split("#", 1)[0]


def _declared_paths(config: dict[str, Any]) -> Iterable[str]:
    for claim in [*config["main_claims"], *config["boundary_claims"]]:
        for key in ("method_equations", "config_paths", "implementation_paths", "test_paths", "evidence_paths"):
            for value in claim.get(key, []):
                yield str(value)
    for figure in config["figures"]:
        yield str(figure["builder_path"])
        for value in figure["evidence_paths"]:
            yield str(value)
    for figure in config.get("supplementary_figures", []):
        for value in figure.get("evidence_paths", []):
            yield str(value)


def _validate(config: dict[str, Any]) -> dict[str, Any]:
    expected = set(config.get("allowed_statuses", []))
    if expected != ALLOWED_STATUSES:
        raise ValueError(f"Config status vocabulary must equal {sorted(ALLOWED_STATUSES)}")
    claims = [*config["main_claims"], *config["boundary_claims"]]
    figures = [*config["figures"], *config.get("supplementary_figures", [])]
    invalid = sorted({item["status"] for item in [*claims, *figures]} - ALLOWED_STATUSES)
    if invalid:
        raise ValueError(f"Invalid claim statuses: {invalid}")
    ids = [item["id"] for item in claims]
    if len(ids) != len(set(ids)):
        raise ValueError("Claim ids must be unique.")
    missing = sorted({value.split("#", 1)[0] for value in _declared_paths(config) if not _source_path(value).exists()})
    if missing:
        raise FileNotFoundError("Missing evidence-lock sources: " + ", ".join(missing))
    main_figure_ids = {item["id"] for item in config["figures"]}
    for claim in config["main_claims"]:
        unknown = set(claim.get("figure_ids", [])) - main_figure_ids
        if unknown:
            raise ValueError(f"{claim['id']} references unknown figures: {sorted(unknown)}")
    figure5 = next(item for item in config["figures"] if item["id"] == "Figure 5")
    expected_primary = "outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json"
    if figure5["evidence_paths"][0] != expected_primary:
        raise ValueError("Figure 5 must use the calibrated sequential validation as its primary source.")
    primary = json.loads((ROOT / expected_primary).read_text(encoding="utf-8"))
    stress_path = ROOT / "outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json"
    stress = json.loads(stress_path.read_text(encoding="utf-8"))
    if not primary.get("whether_calibrated_sequential_design_is_manuscript_main_result", False):
        raise ValueError("The declared Figure 5 source does not authorize a main result.")
    if stress.get("whether_ready_as_main_figure", True):
        raise ValueError("The protocol stress audit unexpectedly claims main-figure readiness.")
    return {
        "primary_figure_5_cases": int(primary["num_simulator_backed_cases"]),
        "primary_figure_5_best_protocol": primary["best_calibrated_protocol"],
        "primary_figure_5_success_rate": float(primary["success_rate_by_protocol"][primary["best_calibrated_protocol"]]),
        "primary_figure_5_max_error": float(primary["by_protocol"][primary["best_calibrated_protocol"]]["max_error"]),
        "stress_figure_ready": bool(stress["whether_ready_as_main_figure"]),
    }


def _join_paths(values: list[str]) -> str:
    return "<br>".join(f"`{value}`" for value in values)


def _write_lock(config: dict[str, Any], path: Path) -> None:
    lines = [
        "# Locked gamma_sub Evidence Chain",
        "",
        "This is the authoritative Priority A map for the 1D constrained `gamma_sub` manuscript line. All evidence is synthetic numerical digital-twin evidence, not measured experimental data.",
        "",
        "## One-To-One Claim Chain",
        "",
        "| ID | Status | Claim | Method equation | Config / implementation / test | JSON / CSV | Figure | Limitation | Locked manuscript sentence | Reproduction |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for claim in config["main_claims"]:
        code_chain = [*claim["config_paths"], *claim["implementation_paths"], *claim["test_paths"]]
        lines.append(
            "| " + " | ".join([
                claim["id"], f"`{claim['status']}`", claim["claim"], _join_paths(claim["method_equations"]),
                _join_paths(code_chain), _join_paths(claim["evidence_paths"]), ", ".join(claim["figure_ids"]),
                claim["limitation"], claim["manuscript_sentence"], f"`{claim['reproduction_command']}`",
            ]) + " |"
        )
    lines.extend([
        "",
        "## Boundary Claims",
        "",
        "| ID | Status | Current boundary | Evidence | Allowed sentence | Forbidden wording |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for claim in config["boundary_claims"]:
        lines.append("| " + " | ".join([
            claim["id"], f"`{claim['status']}`", claim["claim"], _join_paths(claim["evidence_paths"]),
            claim["allowed_sentence"], claim["forbidden_wording"],
        ]) + " |")
    lines.extend([
        "",
        "## Reproduction Suite",
        "",
        "```powershell",
        *config["reproduction_suite"],
        "```",
        "",
        "The broader 2400-case calibrated-protocol stress audit remains supplementary because its source explicitly sets `whether_ready_as_main_figure = false`; it cannot replace the 720-case Figure 5 source.",
    ])
    _resolve(path).parent.mkdir(parents=True, exist_ok=True)
    _resolve(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_claim_matrix(config: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Claim Matrix",
        "",
        "This matrix is authoritative for the current manuscript state. Historical claim evolution is archived and remains provenance only. All entries refer to synthetic numerical digital-twin evidence unless explicitly marked absent.",
        "",
        "## Mainline Claims",
        "",
        "| ID | Claim | Status | Evidence | Required qualification | Forbidden wording |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for claim in config["main_claims"]:
        lines.append("| " + " | ".join([
            claim["id"], claim["claim"], f"`{claim['status']}`", _join_paths(claim["evidence_paths"]),
            claim["limitation"], claim["forbidden_wording"],
        ]) + " |")
    lines.extend([
        "",
        "## Active Boundaries And Extensions",
        "",
        "| ID | Claim | Status | Evidence | Allowed wording | Forbidden wording |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for claim in config["boundary_claims"]:
        lines.append("| " + " | ".join([
            claim["id"], claim["claim"], f"`{claim['status']}`", _join_paths(claim["evidence_paths"]),
            claim["allowed_sentence"], claim["forbidden_wording"],
        ]) + " |")
    lines.extend([
        "",
        "## Absolute Manuscript Boundary",
        "",
        "Experimental validation, terminal-only arbitrary full-field recovery, full or Seiler-style STL reproduction, universal Fourier/F-SPS superiority, and device-grade FEM/3D reproduction remain `forbidden` without new direct evidence.",
        "",
        "See `docs/paper/gamma_sub_evidence_lock.md` for equations, configs, scripts, tests, artifacts, figures, limitations, manuscript sentences, and reproduction commands.",
    ])
    _resolve(path).parent.mkdir(parents=True, exist_ok=True)
    _resolve(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_figure_list(config: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Figure List",
        "",
        "All figures are generated from synthetic numerical digital-twin evidence; none is measured experimental data.",
        "",
        "| Figure | Title | Status | Primary data | Generated file | Builder | Reproduction command | Caption boundary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for figure in config["figures"]:
        lines.append("| " + " | ".join([
            figure["id"], figure["title"], f"`{figure['status']}`", _join_paths(figure["evidence_paths"]),
            f"`{figure['figure_path']}`", f"`{figure['builder_path']}`", f"`{figure['reproduction_command']}`", figure["caption"],
        ]) + " |")
    lines.extend([
        "",
        "## Supplementary Stress Figure",
        "",
        "| Figure | Status | Data | Reason |",
        "| --- | --- | --- | --- |",
    ])
    for figure in config.get("supplementary_figures", []):
        lines.append("| " + " | ".join([
            figure["id"], f"`{figure['status']}`", _join_paths(figure["evidence_paths"]), figure["reason"],
        ]) + " |")
    _resolve(path).parent.mkdir(parents=True, exist_ok=True)
    _resolve(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_gamma_sub_evidence_lock(
    config_path: Path = DEFAULT_CONFIG,
    output_json: Path = DEFAULT_JSON,
    lock_md: Path = DEFAULT_LOCK,
    claim_matrix_md: Path = DEFAULT_CLAIMS,
    figure_list_md: Path = DEFAULT_FIGURES,
) -> dict[str, Any]:
    config = _load_yaml(config_path)
    figure5 = _validate(config)
    claims = [*config["main_claims"], *config["boundary_claims"]]
    summary = {
        "schema_version": int(config["schema_version"]),
        "artifact_type": config["artifact_type"],
        "evidence_type": config["evidence_type"],
        "source_sha": config["source_sha"],
        "config_path": str(config_path).replace("\\", "/"),
        "main_claim_count": len(config["main_claims"]),
        "boundary_claim_count": len(config["boundary_claims"]),
        "main_figure_count": len(config["figures"]),
        "status_counts": dict(sorted(Counter(item["status"] for item in claims).items())),
        "status_vocabulary_valid": True,
        "all_declared_sources_exist": True,
        "all_main_positive_claims_allowed": all(item["status"] in {"supported", "qualified_supported"} for item in config["main_claims"]),
        "external_quantitative_validation_completed": False,
        "figure_5_decision": {
            "primary_source": "outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json",
            "supplementary_stress_source": "outputs/tables/gamma_sub_calibrated_protocol_robustness_final_summary.json",
            **figure5,
        },
        "claims": claims,
        "figures": config["figures"],
        "outputs": {
            "summary_json": str(output_json).replace("\\", "/"),
            "evidence_lock_md": str(lock_md).replace("\\", "/"),
            "claim_matrix_md": str(claim_matrix_md).replace("\\", "/"),
            "figure_list_md": str(figure_list_md).replace("\\", "/"),
        },
        "claim_boundary": "Constrained 1D gamma_sub recovery only; synthetic benchmark, calibrated/tight priors, no arbitrary full-field or experimental-validation claim.",
    }
    _write_lock(config, lock_md)
    _write_claim_matrix(config, claim_matrix_md)
    _write_figure_list(config, figure_list_md)
    out = _resolve(output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--lock-md", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--claim-matrix-md", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--figure-list-md", type=Path, default=DEFAULT_FIGURES)
    args = parser.parse_args()
    summary = build_gamma_sub_evidence_lock(args.config, args.output_json, args.lock_md, args.claim_matrix_md, args.figure_list_md)
    print(json.dumps({"main_claim_count": summary["main_claim_count"], "all_declared_sources_exist": summary["all_declared_sources_exist"], "figure_5_decision": summary["figure_5_decision"]}, indent=2))


if __name__ == "__main__":
    main()