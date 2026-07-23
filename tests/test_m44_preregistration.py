from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m44_qiu_heterogeneous_3d_thermal.yaml"
ATTESTATION = ROOT / "outputs" / "tables" / "m43_postcommit_attestation.json"
CLOSEOUT = ROOT / "outputs" / "tables" / "m44_classic_reproduction_closeout.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _crlf_sha256(path: Path) -> str:
    canonical_lf = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(canonical_lf.replace(b"\n", b"\r\n")).hexdigest().upper()


def test_m43_attestation_binds_final_head_and_portable_text_identities() -> None:
    record = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    assert record["attested_remote_head"] == "e433fe900cb4376b5e1d5cfe81333e527f5454a5"
    assert record["execution"]["unique_thermal_pde_forwards"] == 15
    assert record["execution"]["scientific_or_contract_gates"] == 19
    assert record["execution"]["budget_gates"] == 2
    assert record["execution"]["postcommit_identity_tests_passed"] == 6
    assert record["execution"]["full_suite_rerun_on_final_head"] is False

    for relative, expected in record["artifact_sha256"].items():
        assert _sha256(ROOT / relative) == expected
    for relative, identities in record["newline_portability"].items():
        path = ROOT / relative
        assert _sha256(path) == identities["committed_lf_sha256"]
        assert _crlf_sha256(path) == identities["runtime_crlf_sha256"]
        assert identities["canonical_lf_equivalent"] is True


def test_classic_reproduction_closeout_uses_only_allowed_claim_statuses() -> None:
    record = json.loads(CLOSEOUT.read_text(encoding="utf-8"))
    assert record["no_new_reproduction_runs"] is True
    assert len(record["entries"]) == 6
    allowed = {
        "supported",
        "qualified_supported",
        "failed_but_informative",
        "forbidden",
        "not_applicable",
    }
    status_fields = {
        "formula_identity",
        "author_code_behavior_parity",
        "numerical_convergence",
        "literature_curve_agreement",
        "independent_validation",
        "final_status",
    }
    for entry in record["entries"]:
        assert all(entry[field] in allowed for field in status_fields)
        assert "unassessed" not in json.dumps(entry)
    zhang = next(entry for entry in record["entries"] if entry["source_id"] == "zhang_2024")
    assert zhang["literature_curve_agreement"] == "failed_but_informative"
    assert zhang["locked_metrics"]["author_code_to_experiment_11V_nrmse"] == 0.446114


def test_m44_preregistration_locks_scope_budget_and_exact_case_count() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    matrix = config["forward_matrix"]
    count = len(matrix["fixed_cases"])
    count += len(matrix["heterogeneous_3d_templates"]["source_ids"]) * len(
        matrix["heterogeneous_3d_templates"]["cases"]
    )
    count += len(matrix["xz_templates"]["source_ids"]) * len(
        matrix["xz_templates"]["cases"]
    )
    assert count == config["budget"]["preregistered_unique_thermal_forwards"] == 31
    assert count <= config["budget"]["maximum_unique_thermal_forwards"] == 32
    assert config["evidence_boundary"]["electrical_forward_runs"] == 0
    assert config["evidence_boundary"]["inverse_runs"] == 0
    assert config["evidence_boundary"]["pinn_training_runs"] == 0
    assert config["evidence_boundary"]["sealed_13V_accessed"] is False
    assert config["geometry"]["contact_support_provenance"] == "engineering-prior"
    assert config["decision"]["unique_Qiu_device_kernel_claim"] == "forbidden_for_all_outcomes"
    assert config["layered_reference"]["self_refinement_change_max"] == 0.002


def test_active_phase_authorizes_heterogeneous_bridge_not_reduction_fit() -> None:
    text = (ROOT / "docs" / "research_strategy" / "active_phase.md").read_text(
        encoding="utf-8"
    )
    assert "Q2_M44_QIU_HETEROGENEOUS_3D_THERMAL_BRIDGE_AND_REPRODUCTION_CLOSEOUT" in text
    assert "RC/kernel" in text and "fitting" in text
    assert "forbidden" in text
