"""Fail-closed route for the source-corrected v3 performance/readiness task.

This routing-only revision deliberately imports no numerical solver.  The
performance implementation may be added only after its independent
preregistration commit has been pushed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage_source_corrected_v3.yaml"
PREREGISTRATION_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "source_correction_preregistration.json"
)
IDENTITY_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "resolved_runtime_identity.json"
)
PERFORMANCE_PREREGISTRATION_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_source_corrected_performance_repair.yaml"
)
PERFORMANCE_PREREGISTRATION_SHA256 = (
    "84e1ecb298cfa6264646cc5e74df602b3e9e790e3eecfdc1abea62c087e87db4"
)
SOURCE_PREREGISTRATION_COMMIT = "0ebe037ef707a56750c5db0c52f7a312ee251b6c"
SOURCE_PREREGISTRATION_SHA256 = (
    "5b132f85c4d94ac504a6558ad889f69f094e30797c694015bb96904268d0e966"
)
IMPLEMENTATION_READY = False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a mapping")
    return value


def validate_active_route() -> dict[str, Any]:
    stage = _yaml(STAGE_PATH)
    active = stage["active_bundle"]
    if stage["formal_execution_count"] != 0 or stage["formal_artifact_count"] != 0:
        raise RuntimeError("source-corrected route cannot consume formal execution")
    if active["source_correction_preregistration_commit"] != SOURCE_PREREGISTRATION_COMMIT:
        raise RuntimeError("source-correction preregistration commit changed")
    if _sha256(PREREGISTRATION_PATH) != SOURCE_PREREGISTRATION_SHA256:
        raise RuntimeError("source-correction preregistration bytes changed")
    if active["high_bias_15V_compatibility_alias"] != "forbidden":
        raise RuntimeError("historical 15 V alias became selectable")
    if not PERFORMANCE_PREREGISTRATION_PATH.is_file():
        raise RuntimeError("performance-repair preregistration is absent")
    if _sha256(PERFORMANCE_PREREGISTRATION_PATH) != PERFORMANCE_PREREGISTRATION_SHA256:
        raise RuntimeError("performance-repair preregistration bytes changed")
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    if identity["formal_execution_count"] != 0 or identity["formal_artifact_count"] != 0:
        raise RuntimeError("resolved v3 identity contains formal evidence")
    return {
        "active_checkpoint": stage["current_checkpoint"],
        "active_high_bias_protocol": active["active_high_bias_protocol"],
        "resolved_runtime_identity_sha256": identity[
            "resolved_runtime_identity_sha256"
        ],
        "source_correction_preregistration_commit": SOURCE_PREREGISTRATION_COMMIT,
        "performance_repair_preregistration_sha256": (
            PERFORMANCE_PREREGISTRATION_SHA256
        ),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-route", action="store_true")
    args = parser.parse_args()
    route = validate_active_route()
    if args.check_route:
        print(json.dumps(route, indent=2, sort_keys=True))
        return
    if not IMPLEMENTATION_READY:
        raise SystemExit(
            "source-corrected performance implementation is not locked; numerical execution is forbidden"
        )
    raise AssertionError("routing-only runner cannot execute numerical work")


if __name__ == "__main__":
    main()
