"""Audit the versioned N0 full-PINN contract without starting training."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from pinnpcm.physics.gt_solver import equilibrium_m
from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.full_pinn_1d import FullPINN1D
from pinnpcm.pinn.full_residuals_1d import compute_boundary_terms, compute_full_residuals, residual_rms


class ConstantEquilibriumModel(torch.nn.Module):
    """Autograd-compatible zero-voltage manufactured equilibrium."""

    def __init__(self, params: dict[str, Any], t_max_s: float) -> None:
        super().__init__()
        self.params = {**params, "layer_profile": "uniform", "initial_defect_mode": "uniform"}
        self.t_max_s = float(t_max_s)
        self.voltage_scale_v = 0.2
        self.temperature_scale_k = 20.0

    def equilibrium_phase(self, c_v: torch.Tensor, temperature: torch.Tensor) -> torch.Tensor:
        argument = (
            temperature - float(self.params["T_sw"])
            + float(self.params["alpha_c"]) * (c_v - float(self.params["c_v0"]))
        ) / float(self.params["dT_sw"])
        return torch.sigmoid(argument)

    def forward(self, coords: torch.Tensor) -> dict[str, Any]:
        zero = coords[..., 0:1] * 0.0 + coords[..., 1:2] * 0.0
        c_v = zero + float(self.params["c_v0"])
        temperature = zero + float(self.params["T0"])
        m = self.equilibrium_phase(c_v, temperature)
        sigma_off = zero + float(self.params["sigma_off0"])
        sigma_on = zero + float(self.params["sigma_on0"])
        log_sigma = (1.0 - m) * torch.log(sigma_off) + m * torch.log(sigma_on)
        profiles = {
            key: zero + float(self.params[key])
            for key in ("sigma_off0", "sigma_on0", "D_v0", "mu_v0", "k_th")
        }
        return {
            "phi": zero,
            "c_v": c_v,
            "T": temperature,
            "m": m,
            "sigma": torch.exp(log_sigma),
            "V": zero,
            "profiles": profiles,
        }


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def audit(config_path: Path) -> dict[str, Any]:
    config = _load_config(config_path)
    gt_config = _load_config(Path(config["frozen_gt_config"]))
    params = merge_params(gt_config.get("params"))
    gt_npz = np.load(config["frozen_gt_path"])
    duration = float(np.max(gt_npz["t"]))
    architecture = config["architecture"]
    model = FullPINN1D(
        params=params,
        t_max_s=duration,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
    ).cpu()

    contract = model.contract()
    required = {
        "states", "residuals", "initial_conditions", "boundary_conditions",
        "interface_conditions", "history_state", "observation_operator", "inverse_outputs",
    }
    contract_complete = required.issubset(contract) and not contract["independent_log_sigma_output"]

    x = torch.linspace(0.0, 1.0, 33).reshape(-1, 1)
    zero_t = torch.zeros_like(x)
    with torch.no_grad():
        initial = model(torch.cat([x, zero_t], dim=-1))
        expected_c = model.initial_defect(x)
        expected_m = model.equilibrium_phase(expected_c, torch.ones_like(x) * float(params["T0"]))
        ic_max = max(
            float(torch.max(torch.abs(initial["c_v"] - expected_c))),
            float(torch.max(torch.abs(initial["T"] - float(params["T0"]))) / architecture["temperature_scale_K"]),
            float(torch.max(torch.abs(initial["m"] - expected_m))),
        )

    t = torch.linspace(0.0, 1.0, 17).reshape(-1, 1)
    bc = compute_boundary_terms(model, t)
    phi_bc_max = max(float(torch.max(torch.abs(bc["phi_left"]))), float(torch.max(torch.abs(bc["phi_right"]))))

    manufactured = ConstantEquilibriumModel(params, duration)
    rng = torch.Generator().manual_seed(20260715)
    coords = torch.rand((128, 2), generator=rng, dtype=torch.float64)
    manufactured = manufactured.to(dtype=torch.float64)
    m_residuals = compute_full_residuals(manufactured, coords)
    manufactured_rms = residual_rms(m_residuals)
    manufactured_max = max(manufactured_rms.values())

    gates = config["gates"]
    checks = {
        "contract_complete": bool(contract_complete),
        "physical_conductivity_closure": architecture["conductivity_source"] == "physical_state_closure"
        and not bool(architecture["independent_log_sigma_output"]),
        "no_field_or_port_label_training": not bool(config["training"]["full_field_training"])
        and not bool(config["training"]["port_label_training"]),
        "initial_condition_max": ic_max <= float(gates["ic_bc_max_normalized_error"]),
        "hard_phi_boundary_max": phi_bc_max <= float(gates["ic_bc_max_normalized_error"]),
        "manufactured_residual_rms": manufactured_max <= float(gates["manufactured_normalized_residual_rms_max"]),
        "finite_cpu_forward": all(torch.isfinite(value).all().item() for key, value in initial.items() if isinstance(value, torch.Tensor)),
    }
    status = "preflight_passed" if all(checks.values()) else "preflight_failed"
    result = {
        "schema_version": "full_pinn_contract_v1",
        "stage_id": "N0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "claim_status": "forbidden",
        "claim_note": "N0 training evidence is not established by this contract audit.",
        "contract": contract,
        "checks": checks,
        "metrics": {
            "initial_condition_max_normalized_error": ic_max,
            "hard_phi_boundary_max_normalized_error": phi_bc_max,
            "manufactured_residual_rms": manufactured_rms,
        },
        "frozen_gt_role": "score_only",
        "p1_boundary": "Interface terms are diagnostics/losses only; no multidomain or interface-innovation claim is activated.",
    }
    output = Path(config["outputs"]["contract_json"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.config)
    print(json.dumps({"status": result["status"], "checks": result["checks"], "metrics": result["metrics"]}, indent=2))
    if result["status"] != "preflight_passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
