from __future__ import annotations

import json
from pathlib import Path

import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import ControlVolumeFullPINN
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt
from pinnpcm.pinn.optimizer_forensics import (
    atomic_torch_save,
    first_nonfinite_attribution,
    parameter_optimizer_finiteness,
    restore_checkpoint,
)


def _script_module():
    import importlib.util

    path = Path("scripts/run_n0_cv_e_v3r_optimizer_forensics.py")
    spec = importlib.util.spec_from_file_location("n0_v3r", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _full_size_model(seed: int = 20260715) -> tuple[ControlVolumeFullPINN, dict, dict]:
    config = yaml.safe_load(Path("configs/full_pinn_n0_cv_e_v3.yaml").read_text(encoding="utf-8"))
    gt, params = load_frozen_gt(Path(config["frozen_inputs"]["gt_path"]))
    architecture = config["architecture"]
    model = ControlVolumeFullPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=float(gt["t"][-1]),
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=config["dimensionless_registry"],
        seed=seed,
    )
    return model, config, gt


def test_full_size_short_adam_to_lbfgs_transition_is_finite() -> None:
    module = _script_module()
    model, config, _ = _full_size_model()
    train_t = torch.linspace(0.01, 0.08, 4).reshape(-1, 1)
    ledger_t = torch.linspace(0.0, 0.08, 4).reshape(-1, 1)
    weights = {name: float(value) for name, value in config["training"]["loss_weights"].items()}
    adam = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    adam.zero_grad(set_to_none=True)
    blocks = module._loss_blocks(model, train_t, ledger_t)
    loss = module._total(blocks, weights)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 100.0, error_if_nonfinite=True)
    adam.step()
    assert parameter_optimizer_finiteness(model, adam)["optimizer_state_finite"] is True

    lbfgs = torch.optim.LBFGS(model.parameters(), max_iter=1, history_size=2, line_search_fn="strong_wolfe")

    def closure() -> torch.Tensor:
        lbfgs.zero_grad(set_to_none=True)
        value = module._total(module._loss_blocks(model, train_t, ledger_t), weights)
        assert torch.isfinite(value)
        value.backward()
        return value

    lbfgs.step(closure)
    assert parameter_optimizer_finiteness(model, lbfgs)["parameters_finite"] is True


def test_injected_nonfinite_is_attributed_to_parameter() -> None:
    model, _, _ = _full_size_model(seed=9)
    name, parameter = next(iter(model.named_parameters()))
    with torch.no_grad():
        parameter.reshape(-1)[0] = float("nan")
    attribution = first_nonfinite_attribution(model)
    assert attribution["kind"] == "parameter"
    assert attribution["name"] == name


def test_atomic_checkpoint_restore_reproduces_output(tmp_path: Path) -> None:
    model, _, _ = _full_size_model(seed=11)
    optimizer = torch.optim.Adam(model.parameters(), lr=1.0e-3)
    times = torch.linspace(0.0, 0.2, 4).reshape(-1, 1)
    expected = model(times)["T"].detach().clone()
    path = tmp_path / "checkpoint.pt"
    atomic_torch_save(
        path,
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "seed": 11,
        },
    )
    with torch.no_grad():
        next(model.parameters()).add_(1.0)
    restore_checkpoint(path, model, optimizer)
    actual = model(times)["T"].detach()
    assert torch.equal(expected, actual)


def test_semantic_amendment_preserves_historical_failure_boundary() -> None:
    payload = json.loads(
        Path("outputs/tables/n0_cv_e_v3_semantic_amendment.json").read_text(encoding="utf-8")
    )
    historical = payload["historical_b380_interpretation"]
    assert historical["claim_status"] == "failed_but_informative"
    assert historical["failure_substatus"] == "runtime_abort_unassessed"
    assert historical["scientific_model_falsification"] is False
    assert payload["historical_rescore_semantics"]["correct_name"] == "counterfactual_projected_state_rescore"
