from __future__ import annotations

from pathlib import Path

import yaml

import scripts.audit_literature_prior_consistency as audit


def test_literature_prior_consistency(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    summary = audit.audit_literature_prior_consistency(Path("configs/literature_priors_phase_change.yaml"))
    assert summary["required_families_present"] is True
    assert summary["has_provenance_fields"] is True
    assert summary["synthetic_not_experimental"] is True
    assert summary["allowed_use"] == "shape/parameter plausibility prior only"
    assert summary["forbidden_use"] == "experimental validation"
    assert summary["status"] == "qualified_supported"
    assert (tmp_path / "summary.json").exists()
    cfg = yaml.safe_load(Path("configs/literature_priors_phase_change.yaml").read_text(encoding="utf-8"))
    assert len(cfg["device_families"]) == 3
