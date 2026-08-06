"""Small atomic-artifact helpers for the bounded current-clamp admission gate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def to_builtin(value: Any) -> Any:
    """Convert supported scientific values to strict JSON builtins."""

    if is_dataclass(value):
        return to_builtin(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.ndarray):
        return to_builtin(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NaN and infinity are forbidden in CC-A artifacts")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported CC-A artifact type: {type(value).__name__}")


def atomic_write_json(path: Path, payload: Any) -> str:
    """Write strict, pretty JSON atomically and return its SHA-256."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        to_builtin(payload),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return file_sha256(path)


def atomic_write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str],
) -> str:
    """Write a fixed-schema CSV atomically and return its SHA-256."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), extrasaction="raise"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {name: to_builtin(row.get(name)) for name in fieldnames}
            )
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return file_sha256(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def environment_record(repository_root: Path, *, run_id: str) -> dict[str, Any]:
    """Record the execution identity without importing retired solver code."""

    return {
        "run_id": run_id,
        "git_sha": git_head(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "blas_thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "command": [sys.executable, *sys.argv],
    }
