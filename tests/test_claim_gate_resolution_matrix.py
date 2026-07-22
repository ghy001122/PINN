from __future__ import annotations

from scripts.build_claim_gate_resolution_matrix import build_claim_gate_matrix


def test_claim_gate_resolution_matrix_builds(tmp_path) -> None:
    # The matrix consumes committed evidence. Re-running three historical
    # benchmarks here rewrites tracked evidence and creates six figures.
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
