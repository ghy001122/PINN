"""Versioned harness wrapper for the one valid strict-equivalence audit.

This wrapper only fixes audit import identity.  It cannot dispatch runtime
readiness or a formal evaluation.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterator, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = (ROOT / "src").resolve()
RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_geophase_phase1_v2_source_corrected_performance_readiness.py"
)
RUNNER_MODULE_NAME = "_phase1_v2_source_corrected_equivalence_runner_v2"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _activate_current_worktree_src() -> None:
    """Place this worktree's source first and reject a foreign loaded package."""

    source = str(SRC_ROOT)
    sys.path[:] = [item for item in sys.path if Path(item or ".").resolve() != SRC_ROOT]
    sys.path.insert(0, source)
    foreign: list[str] = []
    for name, module in tuple(sys.modules.items()):
        if name != "pinnpcm" and not name.startswith("pinnpcm."):
            continue
        location = getattr(module, "__file__", None)
        if location is not None and not _is_within(Path(location), SRC_ROOT):
            foreign.append(f"{name}={location}")
    if foreign:
        raise RuntimeError(
            "foreign pinnpcm modules were loaded before harness activation: "
            + ", ".join(sorted(foreign))
        )


@contextmanager
def loaded_runner() -> Iterator[ModuleType]:
    """Load the actual task runner with the current worktree source identity."""

    _activate_current_worktree_src()
    specification = importlib.util.spec_from_file_location(
        RUNNER_MODULE_NAME, RUNNER_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("source-corrected performance runner cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    missing = object()
    previous = sys.modules.get(RUNNER_MODULE_NAME, missing)
    sys.modules[RUNNER_MODULE_NAME] = module
    try:
        specification.loader.exec_module(module)
        yield module
    finally:
        if previous is missing:
            sys.modules.pop(RUNNER_MODULE_NAME, None)
        else:
            sys.modules[RUNNER_MODULE_NAME] = previous


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-harness-loader", action="store_true")
    modes.add_argument("--write-audit-harness-identity", action="store_true")
    modes.add_argument("--run-equivalence", action="store_true")
    parser.add_argument("--candidate-identity-sha256")
    parser.add_argument("--audit-harness-identity-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    with loaded_runner() as runner:
        if args.check_harness_loader:
            payload = runner.check_audit_harness_loader()
            payload["wrapper_src_root"] = str(SRC_ROOT)
            print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
            return
        if args.write_audit_harness_identity:
            runner.main(["--write-audit-harness-identity"])
            return
        if not args.candidate_identity_sha256:
            raise SystemExit("--run-equivalence requires --candidate-identity-sha256")
        if not args.audit_harness_identity_sha256:
            raise SystemExit(
                "--run-equivalence requires --audit-harness-identity-sha256"
            )
        runner.main(
            [
                "--run-equivalence",
                "--candidate-identity-sha256",
                args.candidate_identity_sha256,
                "--audit-harness-identity-sha256",
                args.audit_harness_identity_sha256,
            ]
        )


if __name__ == "__main__":
    main()
