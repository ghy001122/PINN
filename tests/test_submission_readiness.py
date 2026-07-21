from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_submission_readiness.py"
SPEC = importlib.util.spec_from_file_location("audit_submission_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _passing_facts() -> dict[str, bool]:
    return {
        "required_documents": True,
        "citations": True,
        "claim_mapping": True,
        "synthetic_disclosure": True,
        "source_contract": True,
        "figures": True,
        "protected_evidence": True,
        "tests": True,
        "governance": True,
        "local_replay": True,
        "data_statement": True,
        "journal_selected": False,
        "format_rendered": False,
        "author_metadata": False,
        "upload_declarations": False,
    }


def test_citation_and_bibtex_parsers_resolve_pandoc_syntax() -> None:
    citations = MODULE.parse_citation_keys("Evidence [@raissi2019; @karniadakis2021].")
    bibtex = MODULE.parse_bibtex_keys("@article{raissi2019,\n}\n@article{karniadakis2021,\n}")
    assert citations == {"raissi2019", "karniadakis2021"}
    assert citations <= bibtex


def test_content_go_remains_upload_no_go_without_journal_metadata() -> None:
    result = MODULE.evaluate_readiness(_passing_facts())
    assert result == {
        "technical_content_package_ready": True,
        "journal_format_ready": False,
        "journal_upload_ready": False,
        "overall_status": "NO_GO",
        "disposition": "CONTENT_GO_UPLOAD_NO_GO",
    }


def test_any_blocking_technical_failure_fails_closed() -> None:
    facts = _passing_facts()
    facts["claim_mapping"] = False
    result = MODULE.evaluate_readiness(facts)
    assert result["technical_content_package_ready"] is False
    assert result["overall_status"] == "NO_GO"
    assert result["disposition"] == "CONTENT_NO_GO"


def test_claim_rows_require_sentence_and_exact_evidence_hash(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"value": 1}\n', encoding="utf-8")
    expected = MODULE.sha256_file(evidence)
    claims = [
        {
            "claim_id": "c1",
            "status": "qualified_supported",
            "sentence": "Conditional recovery is supported.",
            "evidence": [{"path": "evidence.json", "sha256": expected}],
        }
    ]
    rows = MODULE.audit_claim_rows(tmp_path, "Conditional recovery is supported.", claims)
    assert rows[0]["sentence_found"] is True
    assert rows[0]["evidence_verified"] is True
    assert rows[0]["gate_pass"] is True

    claims[0]["evidence"][0]["sha256"] = "0" * 64
    rows = MODULE.audit_claim_rows(tmp_path, "Conditional recovery is supported.", claims)
    assert rows[0]["gate_pass"] is False


def test_pytest_log_parser_counts_smoke_nodes_and_exit_code() -> None:
    text = "tests/test_a.py::test_smoke PASSED\n12 passed in 1.0s\nexit_code=0\n"
    assert MODULE.parse_exit_code(text) == 0
    assert MODULE.parse_pytest_counts(text) == {"passed": 12, "failed": 0, "test_only_smoke_runs": 1}
