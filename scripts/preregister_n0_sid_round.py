"""Create clean-tree, real-commit preregistration locks for prompt 29."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml

from pinnpcm.pinn.n0_cv_evidence import stable_file_hash
from pinnpcm.pinn.optimizer_forensics import atomic_json_write


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str, root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def build_lock(config_path: Path, *, root: Path = ROOT) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dirty = _git("status", "--porcelain", root=root)
    if dirty:
        raise RuntimeError("Preregistration requires a clean worktree before lock creation.")
    head = _git("rev-parse", "HEAD", root=root)
    origin_main = _git("rev-parse", "origin/main", root=root)
    if head != origin_main:
        raise RuntimeError(f"HEAD {head} does not equal origin/main {origin_main}.")
    remote = _git("remote", "get-url", "origin", root=root)
    expected_remote = config.get("preregistration", {}).get("require_remote_url")
    if expected_remote and remote != expected_remote:
        raise RuntimeError(f"Remote mismatch: expected {expected_remote}, observed {remote}.")
    locked: dict[str, Any] = {}
    for relative in config["preregistration"]["locked_files"]:
        path = root / relative
        if not path.exists():
            raise FileNotFoundError(f"Locked file does not exist: {relative}")
        locked[relative] = stable_file_hash(path)
    return {
        "schema_version": f"{config['schema_version']}_preregistration_lock_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": head,
        "origin_main_commit": origin_main,
        "git_remote_url": remote,
        "git_branch": _git("branch", "--show-current", root=root),
        "worktree_clean_before_lock": True,
        "config_path": str(config_path.relative_to(root)).replace("\\", "/"),
        "config_hash": stable_file_hash(config_path),
        "locked_files": locked,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        },
        "immutable_rules": {
            "frozen_gt_unchanged": True,
            "old_results_and_checkpoints_not_overwritten": True,
            "hidden_field_labels_forbidden": True,
            "port_labels_for_n0_training_forbidden": True,
            "external_13v_forbidden": True,
            "nan_to_num_forbidden": True,
            "posthoc_gate_or_window_changes_forbidden": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configs",
        nargs="+",
        type=Path,
        default=[
            Path("configs/n0_cv_e_v3r_optimizer_forensics.yaml"),
            Path("configs/sid_ec_oq_event_geometry.yaml"),
        ],
    )
    args = parser.parse_args()
    pending = []
    for supplied in args.configs:
        config_path = supplied if supplied.is_absolute() else ROOT / supplied
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        output = ROOT / config["outputs"]["preregistration"]
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite preregistration lock: {output}")
        payload = build_lock(config_path)
        pending.append((output, payload))

    # Build every lock against the same clean tree before writing any lock.
    # Otherwise the first generated output dirties the tree and invalidates the
    # second preregistration in the same invocation.
    outputs = []
    for output, payload in pending:
        atomic_json_write(output, payload)
        outputs.append({"path": str(output.relative_to(ROOT)).replace("\\", "/"), "commit": payload["git_commit"]})
    print(json.dumps({"status": "locked", "outputs": outputs}, sort_keys=True))


if __name__ == "__main__":
    main()
