"""E1F must not mutate M40, M40R, frozen GT, or raw Qiu sources."""

from __future__ import annotations

import json
from pathlib import Path

from pinnpcm.audit.evidence_identity import assert_evidence_lock


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "outputs/tables/e1f_qiu_author_anchor_preregistration.json"


def test_e1f_protected_files_match_preregistration() -> None:
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    for group in (
        "raw_source_records",
        "m40_protected_records",
        "m40r_protected_records",
        "frozen_gt_records",
    ):
        records = payload[group]
        assert records
        for record in records:
            path = ROOT / record["path"]
            assert path.exists(), record["path"]
            assert_evidence_lock(
                path,
                record["sha256"],
                expected_size=int(record["size_bytes"]),
                root=ROOT,
                allow_historical_revision=str(record["path"]).startswith(
                    ("configs/", "scripts/", "src/", "tests/")
                ),
            )
