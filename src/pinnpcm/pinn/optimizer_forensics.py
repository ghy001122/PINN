"""Fail-closed optimizer telemetry for the bounded N0-CV-E v3r replay."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch


def atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    """Write strict JSON atomically in the target directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def atomic_torch_save(path: Path, payload: Mapping[str, Any]) -> None:
    """Serialize a checkpoint to a temporary sibling before replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        torch.save(dict(payload), temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    """Append telemetry without letting a non-finite diagnostic hide the failure.

    Strict, claim-bearing JSON artifacts still use :func:`atomic_json_write` and
    reject NaN/Infinity.  Streaming telemetry is different: optimizer failure
    may make a diagnostic norm infinite, so it is encoded as JSON ``null``
    while the adjacent finite-state flags preserve the failure semantics.
    """

    def json_safe(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        if isinstance(value, np.ndarray):
            return json_safe(value.tolist())
        if isinstance(value, np.generic):
            return json_safe(value.item())
        if torch.is_tensor(value):
            return json_safe(value.detach().cpu().tolist())
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(json_safe(payload), sort_keys=True, allow_nan=False)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _finite_tensor(value: torch.Tensor | None) -> bool:
    return value is None or bool(torch.isfinite(value).all().item())


def tensor_range(value: torch.Tensor) -> list[float]:
    detached = value.detach()
    return [float(torch.min(detached).cpu()), float(torch.max(detached).cpu())]


def parameter_optimizer_finiteness(
    model: torch.nn.Module, optimizer: torch.optim.Optimizer | None
) -> dict[str, Any]:
    parameter_failures: list[str] = []
    gradient_failures: list[str] = []
    state_failures: list[str] = []
    exp_avg_finite = True
    exp_avg_sq_finite = True
    for name, parameter in model.named_parameters():
        if not _finite_tensor(parameter):
            parameter_failures.append(name)
        if not _finite_tensor(parameter.grad):
            gradient_failures.append(name)
        if optimizer is not None:
            state = optimizer.state.get(parameter, {})
            for state_name, state_value in state.items():
                if torch.is_tensor(state_value) and not _finite_tensor(state_value):
                    state_failures.append(f"{name}:{state_name}")
                if state_name == "exp_avg":
                    exp_avg_finite = exp_avg_finite and _finite_tensor(state_value)
                if state_name == "exp_avg_sq":
                    exp_avg_sq_finite = exp_avg_sq_finite and _finite_tensor(state_value)
    return {
        "parameters_finite": not parameter_failures,
        "gradients_finite": not gradient_failures,
        "optimizer_state_finite": not state_failures,
        "adam_exp_avg_finite": bool(exp_avg_finite),
        "adam_exp_avg_sq_finite": bool(exp_avg_sq_finite),
        "first_nonfinite_parameter": parameter_failures[0] if parameter_failures else None,
        "first_nonfinite_gradient": gradient_failures[0] if gradient_failures else None,
        "first_nonfinite_optimizer_state": state_failures[0] if state_failures else None,
    }


def loss_gradient_diagnostics(
    model: torch.nn.Module, blocks: Mapping[str, torch.Tensor]
) -> dict[str, Any]:
    """Compute per-block gradient scale and conflict without mutating ``.grad``."""

    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    vectors: dict[str, torch.Tensor] = {}
    per_block: dict[str, Any] = {}
    for name, value in blocks.items():
        gradients = torch.autograd.grad(
            value, parameters, retain_graph=True, create_graph=False, allow_unused=True
        )
        pieces = [
            torch.zeros_like(parameter).reshape(-1)
            if gradient is None
            else gradient.detach().reshape(-1)
            for parameter, gradient in zip(parameters, gradients, strict=True)
        ]
        vector = torch.cat(pieces)
        vectors[name] = vector
        per_block[name] = {
            "norm": float(torch.linalg.vector_norm(vector).cpu()),
            "max_abs": float(torch.max(torch.abs(vector)).cpu()),
            "finite": bool(torch.isfinite(vector).all().item()),
        }
    cosine: dict[str, dict[str, float]] = {}
    off_diagonal: list[float] = []
    names = list(vectors)
    for first in names:
        cosine[first] = {}
        for second in names:
            denominator = torch.linalg.vector_norm(vectors[first]) * torch.linalg.vector_norm(
                vectors[second]
            )
            value = (
                float(torch.dot(vectors[first], vectors[second]).div(denominator).cpu())
                if float(denominator) > 0.0
                else 0.0
            )
            cosine[first][second] = value
            if first < second:
                off_diagonal.append(value)
    positive_norms = [
        entry["norm"] for entry in per_block.values() if entry["norm"] > 0.0 and math.isfinite(entry["norm"])
    ]
    ratio = max(positive_norms) / min(positive_norms) if positive_norms else math.inf
    return {
        "per_block": per_block,
        "cosine_matrix": cosine,
        "minimum_pairwise_cosine": min(off_diagonal) if off_diagonal else 0.0,
        "median_pairwise_cosine": float(np.median(off_diagonal)) if off_diagonal else 0.0,
        "negative_pair_count": int(sum(value < 0.0 for value in off_diagonal)),
        "gradient_norm_ratio": float(ratio),
    }


def physical_diagnostics(model: torch.nn.Module, times: torch.Tensor) -> dict[str, Any]:
    with torch.no_grad():
        values = model(times)
    ranges = {name: tensor_range(values[name]) for name in ("c_v", "T", "m", "sigma", "E", "J")}
    c_v = values["c_v"]
    phase = values["m"]
    temperature = values["T"]
    lower = float(getattr(model, "temperature_min_k", 0.0))
    upper = float(getattr(model, "temperature_max_k", 1.0))
    tolerance = max((upper - lower) * 1.0e-4, 1.0e-12)
    return {
        "ranges": ranges,
        "saturation_fraction": {
            "c_v": float(torch.mean(((c_v < 1.0e-4) | (c_v > 1.0 - 1.0e-4)).float()).cpu()),
            "m": float(torch.mean(((phase < 1.0e-4) | (phase > 1.0 - 1.0e-4)).float()).cpu()),
            "T": float(
                torch.mean(((temperature < lower + tolerance) | (temperature > upper - tolerance)).float()).cpu()
            ),
        },
        "all_finite": bool(
            all(torch.isfinite(values[name]).all().item() for name in ("c_v", "T", "m", "sigma", "E", "J"))
        ),
    }


def restore_checkpoint(
    path: Path,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(payload["model_state_dict"])
    if optimizer is not None and payload.get("optimizer_state_dict") is not None:
        optimizer.load_state_dict(payload["optimizer_state_dict"])
    return payload


def first_nonfinite_attribution(
    model: torch.nn.Module,
    blocks: Mapping[str, torch.Tensor] | None = None,
    physical: Mapping[str, torch.Tensor] | None = None,
) -> dict[str, Any]:
    for name, parameter in model.named_parameters():
        if not _finite_tensor(parameter):
            return {"kind": "parameter", "name": name, "layer": name.rsplit(".", 1)[0]}
        if not _finite_tensor(parameter.grad):
            return {"kind": "gradient", "name": name, "layer": name.rsplit(".", 1)[0]}
    for name, value in (blocks or {}).items():
        if not _finite_tensor(value):
            return {"kind": "residual_block", "name": name, "layer": None}
    for name, value in (physical or {}).items():
        if torch.is_tensor(value) and not _finite_tensor(value):
            return {"kind": "physical_quantity", "name": name, "layer": None}
    return {"kind": "unresolved", "name": None, "layer": None}
