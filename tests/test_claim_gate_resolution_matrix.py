from __future__ import annotations

from scripts.audit_reduced_2d_phase_transition_forward import run_forward_benchmark
from scripts.audit_reduced_2d_observability_limited_inverse import run_observability_audit
from scripts.audit_stiffness_aware_algorithm_benchmark import run_stiffness_algorithm_benchmark
from scripts.build_claim_gate_resolution_matrix import build_claim_gate_matrix


def test_claim_gate_resolution_matrix_builds(tmp_path) -> None:
    run_forward_benchmark()
    run_observability_audit()
    run_stiffness_algorithm_benchmark()
    out = tmp_path / "claim_gate.md"
    build_claim_gate_matrix(out_path=out)
    text = out.read_text(encoding="utf-8")
    assert "synthetic numerical digital-twin benchmark" in text
    assert "Authoritative V10 Claim Gate" in text
    assert "CV multidomain OASIS solves the activated fields" in text
    assert text.count("\n| ") >= 10
    for item in [
        "2D reduced forward supported?",
        "Terminal-only 2D inverse supported?",
        "Full 2D hidden-field recovery supported?",
        "Stiffness cliff mitigated?",
        "Full STL-PINN reproduction supported?",
        "Fourier/F-SPS superiority supported?",
    ]:
        assert item in text
    assert "forbidden" in text
    assert "qualified_supported" in text
    assert "failed_but_informative" in text
    assert "partially_supported" not in text
    assert "Terminal-only sparse observations fail" in text
    assert "Full 2D hidden-field recovery remains unsupported" in text
