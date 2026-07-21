"""E1F must not mutate M40, M40R, frozen GT, or raw Qiu sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "outputs/tables/e1f_qiu_author_anchor_preregistration.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


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
            assert path.stat().st_size == int(record["size_bytes"]), record["path"]
            assert _sha256(path) == record["sha256"], record["path"]
