"""Train control-volume multidomain OASIS variants on activated synthetic data."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pinnpcm.physics.multilayer_sandwich import default_layers, phase_interface_map, simulate_phase_activated_multilayer_case
from pinnpcm.pinn.oasis_components import control_volume_residuals, one_sided_interface_mortar
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/cv_multidomain_oasis_training_summary.json")
CASES_CSV = Path("outputs/tables/cv_multidomain_oasis_cases.csv")
VARIANTS = ["monolithic", "ordered_surrogate", "cv_multidomain", "cv_hard_bc", "cv_interface_mortar"]


class CVFieldModel(nn.Module):
    def __init__(self, layer_count: int, *, monolithic: bool, hard_bc: bool, hidden: int = 32) -> None:
        super().__init__()
        self.layer_count = int(layer_count)
        self.monolithic = bool(monolithic)
        self.hard_bc = bool(hard_bc)
        count = 1 if monolithic else layer_count
        self.experts = nn.ModuleList([
            nn.Sequential(nn.Linear(10, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(), nn.Linear(hidden, 3))
            for _ in range(count)
        ])

    def forward(self, features: torch.Tensor, layer_ids: torch.Tensor, voltage: torch.Tensor, pcm_index: int) -> dict[str, torch.Tensor]:
        raw = torch.empty((features.shape[0], 3), dtype=features.dtype, device=features.device)
        for layer in range(self.layer_count):
            mask = layer_ids == layer
            if torch.any(mask):
                raw[mask] = self.experts[0 if self.monolithic else layer](features[mask])
        global_z = features[:, 3]
        if self.hard_bc:
            phi = (1.0 - global_z) * voltage + global_z * (1.0 - global_z) * raw[:, 0]
        else:
            phi = voltage * torch.sigmoid(raw[:, 0])
        T = 300.0 + 30.0 * torch.nn.functional.softplus(raw[:, 1])
        m = torch.where(layer_ids == int(pcm_index), torch.sigmoid(raw[:, 2]), torch.zeros_like(raw[:, 2]))
        return {"phi": phi, "T": T, "m": m}


def _case(seed: int) -> dict[str, Any]:
    return simulate_phase_activated_multilayer_case(
        "full_stack_with_SnSe_barrier",
        "localized_filament",
        "vo2",
        "activation_triangle",
        seed,
        {
            "ny": 5,
            "nt": 12,
            "dt": 1.2e-7,
            "V_peak": 10.0,
            "R_load_ohm": 8.0e3,
            "vo2_profile": "normalized_activated",
            "vo2_sigma_ins": 2.0,
            "vo2_sigma_met": 8.0e4,
        },
    )


def _grid_features(case: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[int, int, int]]:
    nt, nl, ny = np.asarray(case["temperature"]).shape
    layers = default_layers(case["structure"])
    dz = np.asarray([layer.thickness_m for layer in layers], dtype=float)
    z_edges = np.r_[0.0, np.cumsum(dz)]
    z_global = 0.5 * (z_edges[:-1] + z_edges[1:]) / z_edges[-1]
    rows: list[list[float]] = []
    ids: list[int] = []
    voltage: list[float] = []
    imap = phase_interface_map(layers)
    for it in range(nt):
        for il, layer in enumerate(layers):
            left_rc = imap["Rc_ohm_m2"][il - 1] if il > 0 else 0.0
            right_rc = imap["Rc_ohm_m2"][il] if il < nl - 1 else 0.0
            left_rth = imap["Rth_m2K_W"][il - 1] if il > 0 else 0.0
            right_rth = imap["Rth_m2K_W"][il] if il < nl - 1 else 0.0
            for iy in range(ny):
                rows.append([
                    0.5,
                    iy / max(ny - 1, 1),
                    it / max(nt - 1, 1),
                    z_global[il],
                    np.log10(max(dz[il], 1.0e-30)) + 9.0,
                    np.log10(max(layer.k_w_mk, 1.0e-30)) / 2.0,
                    np.log10(max(layer.rho_c_j_m3k, 1.0)) / 8.0,
                    np.log10(max(left_rc + right_rc, 1.0e-14)) + 12.0,
                    np.log10(max(left_rth + right_rth, 1.0e-12)) + 9.0,
                    il / max(nl - 1, 1),
                ])
                ids.append(il)
                voltage.append(float(case["voltage_device"][it]))
    return torch.tensor(rows, dtype=torch.float32), torch.tensor(ids, dtype=torch.long), torch.tensor(voltage, dtype=torch.float32), (nt, nl, ny)


def _sigma(fields: dict[str, torch.Tensor], shape: tuple[int, int, int], layers, pcm_index: int) -> torch.Tensor:
    T = fields["T"].reshape(shape)
    m = fields["m"].reshape(shape)
    sigma = torch.zeros_like(T)
    for index, layer in enumerate(layers):
        if layer.is_pcm:
            sigma[:, index] = (1.0 - m[:, index]) * 2.0 + m[:, index] * 8.0e4
        elif layer.is_barrier:
            sigma[:, index] = 1.0e4
        elif layer.name == "substrate":
            sigma[:, index] = 1.0e-12
        else:
            sigma[:, index] = float(layer.sigma_s_m)
    return torch.clamp(sigma, min=1.0e-12)


def _interface_loss(model: CVFieldModel, base_features: torch.Tensor, base_ids: torch.Tensor, base_voltage: torch.Tensor, layers, pcm_index: int) -> torch.Tensor:
    nt = int(torch.unique(base_features[:, 2]).numel())
    ny = int(torch.unique(base_features[:, 1]).numel())
    imap = phase_interface_map(layers)
    losses: list[torch.Tensor] = []
    for interface in range(len(layers) - 1):
        sample = base_features[(base_ids == interface)][: nt * ny].clone()
        volts = base_voltage[(base_ids == interface)][: nt * ny]
        left = sample.clone(); left[:, 0] = 1.0
        left_inner = sample.clone(); left_inner[:, 0] = 1.0 - 1.0e-3
        right = sample.clone(); right[:, 0] = 0.0; right[:, 3] = base_features[base_ids == interface + 1][0, 3]
        right_inner = right.clone(); right_inner[:, 0] = 1.0e-3
        left_ids = torch.full((sample.shape[0],), interface, dtype=torch.long)
        right_ids = torch.full((sample.shape[0],), interface + 1, dtype=torch.long)
        f_l = model(left, left_ids, volts, pcm_index); f_li = model(left_inner, left_ids, volts, pcm_index)
        f_r = model(right, right_ids, volts, pcm_index); f_ri = model(right_inner, right_ids, volts, pcm_index)
        dz_l = layers[interface].thickness_m; dz_r = layers[interface + 1].thickness_m
        dphi_l = (f_l["phi"] - f_li["phi"]) / (1.0e-3 * dz_l)
        dphi_r = (f_r["phi"] - f_ri["phi"]) / (1.0e-3 * dz_r)
        dT_l = (f_l["T"] - f_li["T"]) / (1.0e-3 * dz_l)
        dT_r = (f_r["T"] - f_ri["T"]) / (1.0e-3 * dz_r)
        sigma_l = _sigma(f_l, (sample.shape[0], 1, 1), [layers[interface]], 0).reshape(-1)
        sigma_r = _sigma(f_r, (sample.shape[0], 1, 1), [layers[interface + 1]], 0).reshape(-1)
        terms = one_sided_interface_mortar(
            f_l["phi"], f_r["phi"], f_l["T"], f_r["T"], dphi_l, -dphi_r, dT_l, -dT_r,
            sigma_l, sigma_r,
            torch.as_tensor(layers[interface].k_w_mk), torch.as_tensor(layers[interface + 1].k_w_mk),
            torch.as_tensor(imap["Rc_ohm_m2"][interface]), torch.as_tensor(imap["Rth_m2K_W"][interface]),
        )
        losses.extend(terms.values())
    return torch.stack(losses).mean() if losses else torch.zeros((), dtype=base_features.dtype)


def _train(seed: int, variant: str, epochs: int) -> dict[str, Any]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    case = _case(seed)
    layers = default_layers(case["structure"])
    pcm = next(i for i, layer in enumerate(layers) if layer.is_pcm)
    features, layer_ids, voltage, shape = _grid_features(case)
    model = CVFieldModel(len(layers), monolithic=variant == "monolithic", hard_bc=variant in {"cv_hard_bc", "cv_interface_mortar"})
    optimizer = torch.optim.Adam(model.parameters(), lr=2.0e-3)
    target_T = torch.tensor(case["temperature"], dtype=torch.float32)
    target_m = torch.tensor(case["state_m"], dtype=torch.float32)
    target_I = torch.tensor(case["current"], dtype=torch.float32)
    dz = torch.tensor([layer.thickness_m for layer in layers], dtype=torch.float32)
    k = torch.tensor([layer.k_w_mk for layer in layers], dtype=torch.float32)
    rho_c = torch.tensor([layer.rho_c_j_m3k for layer in layers], dtype=torch.float32)
    imap = phase_interface_map(layers)
    Rc = torch.tensor(imap["Rc_ohm_m2"], dtype=torch.float32)
    Rth = torch.tensor(imap["Rth_m2K_W"], dtype=torch.float32)
    anchor_mask = torch.zeros(shape, dtype=torch.bool)
    anchor_mask[::3, :, ::2] = True
    losses: list[float] = []
    start = time.perf_counter()
    for _ in range(int(epochs)):
        optimizer.zero_grad(set_to_none=True)
        fields = model(features, layer_ids, voltage, pcm)
        phi = fields["phi"].reshape(shape); T = fields["T"].reshape(shape); m = fields["m"].reshape(shape)
        sigma = _sigma(fields, shape, layers, pcm)
        cv = control_volume_residuals(
            phi, T, m, sigma, torch.tensor(case["voltage_device"], dtype=torch.float32), target_I,
            dt_s=1.2e-7, dy_m=8.0e-7 / (shape[2] - 1), dz_m=dz, k_w_mk=k, rho_c_j_m3k=rho_c,
            Rc_ohm_m2=Rc, Rth_m2K_W=Rth, electrical_layers=len(layers) - 1, area_m2=7.5e-13,
            T0_K=300.0, h_top_w_m2k=5.0e4, h_sub_w_m2k=2.0e5, tau_m_s=4.0e-7,
            Tc_up_K=308.0, Tc_down_K=304.0, transition_width_K=1.2,
        )
        anchor = torch.mean(((T[anchor_mask] - target_T[anchor_mask]) / 30.0).square()) + torch.mean((m[:, pcm][anchor_mask[:, pcm]] - target_m[anchor_mask[:, pcm]]).square())
        physics = cv["electric_cv_loss"] + cv["thermal_cv_loss"] + cv["state_cv_loss"] + cv["port_circuit_loss"]
        if variant in {"monolithic", "ordered_surrogate"}:
            loss = anchor + 0.2 * cv["port_circuit_loss"]
        else:
            loss = anchor + 0.3 * physics
        if variant == "cv_interface_mortar":
            loss = loss + 0.01 * _interface_loss(model, features, layer_ids, voltage, layers, pcm)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        optimizer.step()
        losses.append(float(loss.detach()))
    wall = time.perf_counter() - start
    with torch.no_grad():
        fields = model(features, layer_ids, voltage, pcm)
        T = fields["T"].reshape(shape); m = fields["m"].reshape(shape); phi = fields["phi"].reshape(shape)
        sigma = _sigma(fields, shape, layers, pcm)
        cv = control_volume_residuals(
            phi, T, m, sigma, torch.tensor(case["voltage_device"], dtype=torch.float32), target_I,
            dt_s=1.2e-7, dy_m=8.0e-7 / (shape[2] - 1), dz_m=dz, k_w_mk=k, rho_c_j_m3k=rho_c,
            Rc_ohm_m2=Rc, Rth_m2K_W=Rth, electrical_layers=len(layers) - 1, area_m2=7.5e-13,
            T0_K=300.0, h_top_w_m2k=5.0e4, h_sub_w_m2k=2.0e5, tau_m_s=4.0e-7,
            Tc_up_K=308.0, Tc_down_K=304.0, transition_width_K=1.2,
        )
        E_T = float(torch.sqrt(torch.mean((T - target_T).square())) / torch.clamp(target_T.max() - target_T.min(), min=1.0))
        E_m = float(torch.sqrt(torch.mean((m[:, pcm] - target_m).square())))
    interface = float(_interface_loss(model, features, layer_ids, voltage, layers, pcm).detach()) if variant == "cv_interface_mortar" else float("nan")
    success = bool(np.isfinite(losses).all() and E_T <= 0.25 and E_m <= 0.25 and (not np.isfinite(interface) or interface <= 0.05))
    return {
        "seed": seed, "variant": variant, "epochs": int(epochs), "initial_loss": losses[0], "final_loss": losses[-1],
        "E_T": E_T, "E_m": E_m, "interface_residual": interface, "electric_cv_residual": float(cv["electric_cv_loss"]),
        "thermal_cv_residual": float(cv["thermal_cv_loss"]), "state_cv_residual": float(cv["state_cv_loss"]),
        "port_residual": float(cv["port_circuit_loss"]), "wall_time_s": wall, "finite": bool(np.isfinite(losses).all()),
        "success": success, "uses_target_non_pcm_sigma": False, "uses_control_volume_physics": variant.startswith("cv_"),
    }


def run_cv_multidomain_oasis(*, epochs: int = 300, seeds: tuple[int, ...] = (2026, 2027, 2028)) -> dict[str, Any]:
    rows = [_train(seed, variant, epochs) for seed in seeds for variant in VARIANTS]
    full = [row for row in rows if row["variant"] == "cv_interface_mortar"]
    success_rate = float(np.mean([row["success"] for row in full]))
    summary = {
        "benchmark": "cv_multidomain_oasis_v10", "synthetic_not_experimental": True, "epochs": int(epochs), "seeds": list(seeds),
        "variants": VARIANTS, "median_E_T_full": float(np.median([row["E_T"] for row in full])),
        "median_E_m_full": float(np.median([row["E_m"] for row in full])),
        "median_interface_residual_full": float(np.median([row["interface_residual"] for row in full])),
        "success_rate_full": success_rate,
        "P1_gate_passed": bool(success_rate >= 0.70 and np.median([row["E_T"] for row in full]) <= 0.25 and np.median([row["E_m"] for row in full]) <= 0.25 and np.median([row["interface_residual"] for row in full]) <= 0.05),
        "success_definition": "E_T<=0.25 and E_m<=0.25 and interface_residual<=0.05; loss decrease alone is insufficient",
        "uses_actual_cv_residuals": True, "uses_target_non_pcm_sigma": False,
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")},
    }
    path = ROOT / CASES_CSV; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seeds", nargs="*", type=int, default=[2026, 2027, 2028])
    args = parser.parse_args()
    print(json.dumps(run_cv_multidomain_oasis(epochs=args.epochs, seeds=tuple(args.seeds)), indent=2))


if __name__ == "__main__":
    main()
