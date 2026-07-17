"""Fixed-point diagnostics shared by the N0 baseline and bounded repair."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.pinn.full_residuals_1d import (
    compute_boundary_terms as compute_global_boundary_terms,
    compute_full_residuals,
    compute_interface_terms as compute_global_interface_terms,
)
from pinnpcm.pinn.full_residuals_1d_split import (
    compute_boundary_terms as compute_split_boundary_terms,
    compute_domain_quantities,
    compute_domain_residuals,
    compute_exact_interface_terms,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_points_content_sha256(points: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in sorted(points):
        array = np.ascontiguousarray(points[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def generate_fixed_points(config: dict[str, Any]) -> dict[str, np.ndarray]:
    """Generate fixed, disjoint train/evaluation/boundary/interface sets."""

    settings = config["diagnostics"]
    rng = np.random.default_rng(int(settings["point_seed"]))
    band = float(settings["near_interface_band_fraction_of_domain"])

    def interior(count: int, t_low: float = 0.0, t_high: float = 1.0) -> np.ndarray:
        return np.column_stack(
            [rng.uniform(band, 1.0 - band, count), rng.uniform(t_low, t_high, count)]
        ).astype(np.float64)

    train_count = int(settings["train_interior_per_domain"])
    eval_count = int(settings["heldout_interior_per_domain"])
    train_base = {domain: interior(train_count) for domain in ("left", "right")}
    points: dict[str, np.ndarray] = {}
    for domain in ("left", "right"):
        for fraction, label in ((0.25, "025"), (0.50, "050"), (0.75, "075"), (1.00, "100")):
            staged = train_base[domain].copy()
            staged[:, 1] *= fraction
            points[f"train_{domain}_stage_{label}"] = staged
        points[f"eval_{domain}"] = interior(eval_count)

    boundary_count = int(settings["boundary_times"])
    interface_count = int(settings["interface_times"])
    points["boundary_t"] = ((np.arange(boundary_count) + 0.5) / boundary_count).reshape(-1, 1)
    points["interface_t"] = ((np.arange(interface_count) + 0.25) / interface_count % 1.0).reshape(-1, 1)

    near_count = int(settings["near_interface_per_domain"])
    points["near_interface_left"] = np.column_stack(
        [rng.uniform(1.0 - band, 1.0, near_count), rng.uniform(0.0, 1.0, near_count)]
    )
    points["near_interface_right"] = np.column_stack(
        [rng.uniform(0.0, band, near_count), rng.uniform(0.0, 1.0, near_count)]
    )
    transition_low, transition_high = [float(value) for value in settings["near_transition_t_norm"]]
    transition_count = int(settings["near_transition_points"])
    for domain in ("left", "right"):
        points[f"near_transition_{domain}"] = interior(transition_count, transition_low, transition_high)

    ordinary_count = int(settings["ordinary_points"])
    ordinary_windows = settings["ordinary_t_norm_windows"]
    for domain in ("left", "right"):
        first = interior(ordinary_count // 2, float(ordinary_windows[0][0]), float(ordinary_windows[0][1]))
        second = interior(
            ordinary_count - ordinary_count // 2,
            float(ordinary_windows[1][0]),
            float(ordinary_windows[1][1]),
        )
        points[f"ordinary_{domain}"] = np.vstack([first, second])

    score_x = int(settings["score_space_points_per_domain"])
    score_t = int(settings["score_time_points"])
    points["ledger_x_left"] = np.linspace(0.0, 1.0, score_x).reshape(-1, 1)
    points["ledger_x_right"] = np.linspace(0.0, 1.0, score_x).reshape(-1, 1)
    points["ledger_x_global"] = np.linspace(0.0, 1.0, 2 * score_x - 1).reshape(-1, 1)
    points["ledger_t"] = np.linspace(0.0, 1.0, score_t).reshape(-1, 1)
    return {key: np.asarray(value, dtype=np.float64) for key, value in points.items()}


def save_fixed_points(points: dict[str, np.ndarray], path: Path) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **points)
    return {
        "path": path.as_posix(),
        "content_sha256": fixed_points_content_sha256(points),
        "file_sha256": sha256_file(path),
    }


def _nrmse95(prediction: np.ndarray, target: np.ndarray) -> float:
    target_array = np.asarray(target, dtype=float)
    scale = max(float(np.quantile(target_array, 0.95) - np.quantile(target_array, 0.05)), 1.0e-30)
    return float(np.sqrt(np.mean((np.asarray(prediction, dtype=float) - target_array) ** 2)) / scale)


def _rms_tensor(value: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(value.detach().square())).cpu())


def _rms_array(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(value, dtype=float)))))


def _arrhenius(prefactor: torch.Tensor, energy_eV: float, temperature: torch.Tensor, reference_K: float) -> torch.Tensor:
    safe_temperature = torch.clamp(temperature, 1.0, 5000.0)
    exponent = -float(energy_eV) / K_B_EV_PER_K * (1.0 / safe_temperature - 1.0 / float(reference_K))
    return prefactor * torch.exp(torch.clamp(exponent, -80.0, 80.0))


def _grad(value: torch.Tensor, coordinates: torch.Tensor) -> torch.Tensor:
    result = torch.autograd.grad(
        value,
        coordinates,
        grad_outputs=torch.ones_like(value),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    return torch.zeros_like(coordinates) if result is None else result


def _local_to_global(points: np.ndarray, interface_norm: float, domain: str) -> np.ndarray:
    result = np.asarray(points, dtype=np.float64).copy()
    if domain == "left":
        result[:, 0] *= interface_norm
    else:
        result[:, 0] = interface_norm + result[:, 0] * (1.0 - interface_norm)
    return result


def _combine_residual_rms(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    return {
        key: _rms_tensor(torch.cat([left[key], right[key]], dim=0))
        for key in ("r_phi", "r_c", "r_T", "r_m")
    }


def _term_rms(terms: dict[str, torch.Tensor]) -> dict[str, float]:
    return {key: _rms_tensor(value) for key, value in terms.items()}


def gradient_diagnostics(model: torch.nn.Module, losses: dict[str, torch.Tensor]) -> dict[str, Any]:
    """Return per-loss gradient norms and cosine/conflict matrix."""

    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    vectors: dict[str, torch.Tensor] = {}
    norms: dict[str, float] = {}
    for name, loss in losses.items():
        gradients = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
        pieces = [
            torch.zeros_like(parameter).reshape(-1) if gradient is None else gradient.reshape(-1)
            for parameter, gradient in zip(parameters, gradients, strict=True)
        ]
        vector = torch.cat(pieces).detach()
        vectors[name] = vector
        norms[name] = float(torch.linalg.vector_norm(vector).cpu())
    cosine: dict[str, dict[str, float]] = {}
    conflicts: list[dict[str, Any]] = []
    for first, first_vector in vectors.items():
        cosine[first] = {}
        for second, second_vector in vectors.items():
            denominator = float(torch.linalg.vector_norm(first_vector) * torch.linalg.vector_norm(second_vector))
            value = 0.0 if denominator <= 1.0e-30 else float(torch.dot(first_vector, second_vector) / denominator)
            cosine[first][second] = value
            if first < second and value < 0.0:
                conflicts.append({"first": first, "second": second, "cosine": value})
    return {"gradient_norms": norms, "cosine_matrix": cosine, "negative_cosine_pairs": conflicts}


def _field_and_port_score(model: torch.nn.Module, gt: dict[str, np.ndarray]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    x = torch.as_tensor(gt["x"] / float(model.params["L_eff"]), dtype=torch.float32)
    t = torch.as_tensor(gt["t"] / float(np.max(gt["t"])), dtype=torch.float32)
    xx = x.repeat(t.numel())
    tt = t.repeat_interleave(x.numel())
    coordinates = torch.stack([xx, tt], dim=-1)
    with torch.no_grad():
        fields = model(coordinates)
        nt, nx = t.numel(), x.numel()
        prediction = {
            key: fields[key].reshape(nt, nx).cpu().numpy() for key in ("c_v", "T", "m", "phi", "sigma")
        }
        sigma = fields["sigma"].reshape(nt, nx)
        voltage = fields["V"].reshape(nt, nx)[:, 0]
        port = model.port_observation(sigma, voltage)
        current = port["I"].cpu().numpy()
    metrics = {
        "port_full_trace_nrmse95": _nrmse95(current, gt["I"]),
        "field_score_only_nrmse95": {
            key: _nrmse95(prediction[key], gt[key]) for key in ("c_v", "T", "m", "phi", "sigma")
        },
        "finite_outputs": bool(np.all(np.isfinite(current)))
        and all(np.all(np.isfinite(value)) for value in prediction.values()),
        "physical_state_bounds": bool(
            np.min(prediction["T"]) > 0.0
            and np.min(prediction["c_v"]) >= 0.0
            and np.max(prediction["c_v"]) <= 1.0
            and np.min(prediction["m"]) >= 0.0
            and np.max(prediction["m"]) <= 1.0
        ),
    }
    return metrics, {**prediction, "I": current}


def _worst_time_window(prediction: np.ndarray, target: np.ndarray, window_fraction: float = 0.10) -> dict[str, Any]:
    count = len(target)
    width = max(4, int(round(count * window_fraction)))
    scale = max(float(np.quantile(target, 0.95) - np.quantile(target, 0.05)), 1.0e-30)
    candidates: list[tuple[float, int]] = []
    for start in range(0, count - width + 1, max(1, width // 2)):
        error = float(np.sqrt(np.mean((prediction[start : start + width] - target[start : start + width]) ** 2)) / scale)
        candidates.append((error, start))
    error, start = max(candidates)
    return {"normalized_rmse": error, "start_index": start, "end_index_exclusive": start + width}


def _global_first_quantities(model: torch.nn.Module, global_coords: torch.Tensor) -> dict[str, Any]:
    coordinates = global_coords.detach().clone().requires_grad_(True)
    fields = model(coordinates)
    params = model.params
    length = float(params["L_eff"])
    duration = float(model.t_max_s)
    phi_gradient = _grad(fields["phi"], coordinates)
    concentration_gradient = _grad(fields["c_v"], coordinates)
    temperature_gradient = _grad(fields["T"], coordinates)
    electric_field = -phi_gradient[:, :1] / length
    concentration_x = concentration_gradient[:, :1] / length
    concentration_t = concentration_gradient[:, 1:] / duration
    temperature_x = temperature_gradient[:, :1] / length
    temperature_t = temperature_gradient[:, 1:] / duration
    diffusion = _arrhenius(
        fields["profiles"]["D_v0"], float(params["E_D_eV"]), fields["T"], float(params["T0"])
    )
    mobility = _arrhenius(
        fields["profiles"]["mu_v0"], float(params["E_mu_eV"]), fields["T"], float(params["T0"])
    )
    reaction_rate = _arrhenius(
        torch.ones_like(fields["c_v"]) * float(params["k_r0"]),
        float(params["E_r_eV"]),
        fields["T"],
        float(params["T0"]),
    )
    defect_flux = -diffusion * concentration_x + mobility * fields["c_v"] * (1.0 - fields["c_v"]) * electric_field
    heat_flux = -fields["profiles"]["k_th"] * temperature_x
    return {
        "coords": coordinates,
        "fields": fields,
        "current_density": fields["sigma"] * electric_field,
        "defect_flux": defect_flux,
        "heat_flux": heat_flux,
        "c_t": concentration_t,
        "T_t": temperature_t,
        "reaction": reaction_rate * (fields["c_v"] - float(params["c_v0"])),
        "joule": fields["sigma"] * electric_field.square(),
        "sink": float(params["gamma_sub"]) * (fields["T"] - float(params["T0"])),
    }


def _ledger_metrics(
    *,
    storage_heat: np.ndarray,
    boundary_heat: np.ndarray,
    sink: np.ndarray,
    joule: np.ndarray,
    storage_mass: np.ndarray,
    boundary_mass: np.ndarray,
    reaction: np.ndarray,
    current_left: np.ndarray,
    current_right: np.ndarray,
    current_port: np.ndarray,
) -> dict[str, float]:
    energy_balance = storage_heat + boundary_heat + sink - joule
    energy_scale = sum(_rms_array(value) for value in (storage_heat, boundary_heat, sink, joule))
    mass_balance = storage_mass + boundary_mass + reaction
    mass_scale = sum(_rms_array(value) for value in (storage_mass, boundary_mass, reaction))
    current_scale = max(_rms_array(current_port), 1.0e-30)
    current_error = np.concatenate([current_left - current_port, current_right - current_port])
    return {
        "global_energy_account_normalized_imbalance": _rms_array(energy_balance) / max(energy_scale, 1.0e-30),
        "defect_mass_account_normalized_imbalance": _rms_array(mass_balance) / max(mass_scale, 1.0e-30),
        "terminal_current_conservation_normalized_error": _rms_array(current_error) / current_scale,
    }


def global_model_conservation(model: torch.nn.Module, points: dict[str, np.ndarray]) -> dict[str, float]:
    x_norm = torch.as_tensor(points["ledger_x_global"].reshape(-1), dtype=torch.float32)
    t_norm = torch.as_tensor(points["ledger_t"].reshape(-1), dtype=torch.float32)
    xx = x_norm.repeat(t_norm.numel())
    tt = t_norm.repeat_interleave(x_norm.numel())
    quantities = _global_first_quantities(model, torch.stack([xx, tt], dim=-1))
    nt, nx = t_norm.numel(), x_norm.numel()
    x_m = x_norm * float(model.params["L_eff"])
    reshape = lambda value: value.reshape(nt, nx)
    storage_heat = torch.trapezoid(
        float(model.params["rho"]) * float(model.params["Cp"]) * reshape(quantities["T_t"]), x_m, dim=1
    )
    sink = torch.trapezoid(reshape(quantities["sink"]), x_m, dim=1)
    joule = torch.trapezoid(reshape(quantities["joule"]), x_m, dim=1)
    heat_flux = reshape(quantities["heat_flux"])
    boundary_heat = heat_flux[:, -1] - heat_flux[:, 0]
    storage_mass = torch.trapezoid(reshape(quantities["c_t"]), x_m, dim=1)
    reaction = torch.trapezoid(reshape(quantities["reaction"]), x_m, dim=1)
    defect_flux = reshape(quantities["defect_flux"])
    boundary_mass = defect_flux[:, -1] - defect_flux[:, 0]
    sigma = reshape(quantities["fields"]["sigma"])
    resistance_area = torch.trapezoid(1.0 / sigma, x_m, dim=1)
    voltage = model.voltage(t_norm.reshape(-1, 1)).reshape(-1)
    current_port = voltage / resistance_area
    current_density = reshape(quantities["current_density"])
    return _ledger_metrics(
        storage_heat=storage_heat.detach().numpy(),
        boundary_heat=boundary_heat.detach().numpy(),
        sink=sink.detach().numpy(),
        joule=joule.detach().numpy(),
        storage_mass=storage_mass.detach().numpy(),
        boundary_mass=boundary_mass.detach().numpy(),
        reaction=reaction.detach().numpy(),
        current_left=current_density[:, 0].detach().numpy(),
        current_right=current_density[:, -1].detach().numpy(),
        current_port=current_port.detach().numpy(),
    )


def split_model_conservation(model: torch.nn.Module, points: dict[str, np.ndarray]) -> dict[str, float]:
    t_norm = torch.as_tensor(points["ledger_t"].reshape(-1), dtype=torch.float32)
    nt = t_norm.numel()
    domain_data: dict[str, dict[str, Any]] = {}
    for domain in ("left", "right"):
        x_local = torch.as_tensor(points[f"ledger_x_{domain}"].reshape(-1), dtype=torch.float32)
        xx = x_local.repeat(nt)
        tt = t_norm.repeat_interleave(x_local.numel())
        quantities = compute_domain_quantities(model, torch.stack([xx, tt], dim=-1), domain)
        domain_data[domain] = {"x": x_local, "quantities": quantities, "nx": x_local.numel()}

    integrated: dict[str, list[torch.Tensor]] = {key: [] for key in ("storage_heat", "sink", "joule", "storage_mass", "reaction", "resistance")}
    for domain in ("left", "right"):
        entry = domain_data[domain]
        quantities = entry["quantities"]
        nx = entry["nx"]
        x_m = entry["x"] * model.domain_length_m(domain)
        reshape = lambda value: value.reshape(nt, nx)
        integrated["storage_heat"].append(
            torch.trapezoid(
                float(model.params["rho"]) * float(model.params["Cp"]) * reshape(quantities["T_t"]),
                x_m,
                dim=1,
            )
        )
        integrated["sink"].append(torch.trapezoid(reshape(quantities["fields"]["T"] - float(model.params["T0"])) * float(model.params["gamma_sub"]), x_m, dim=1))
        integrated["joule"].append(torch.trapezoid(reshape(quantities["fields"]["sigma"] * quantities["electric_field"].square()), x_m, dim=1))
        integrated["storage_mass"].append(torch.trapezoid(reshape(quantities["c_t"]), x_m, dim=1))
        integrated["reaction"].append(
            torch.trapezoid(
                reshape(quantities["reaction_rate"] * (quantities["fields"]["c_v"] - float(model.params["c_v0"]))),
                x_m,
                dim=1,
            )
        )
        integrated["resistance"].append(torch.trapezoid(1.0 / reshape(quantities["fields"]["sigma"]), x_m, dim=1))

    left_q = domain_data["left"]["quantities"]["heat_flux"].reshape(nt, -1)
    right_q = domain_data["right"]["quantities"]["heat_flux"].reshape(nt, -1)
    left_f = domain_data["left"]["quantities"]["defect_flux"].reshape(nt, -1)
    right_f = domain_data["right"]["quantities"]["defect_flux"].reshape(nt, -1)
    left_j = domain_data["left"]["quantities"]["current_density"].reshape(nt, -1)
    right_j = domain_data["right"]["quantities"]["current_density"].reshape(nt, -1)
    resistance = sum(integrated["resistance"])
    voltage = model.voltage(t_norm.reshape(-1, 1)).reshape(-1)
    current_port = voltage / resistance
    return _ledger_metrics(
        storage_heat=sum(integrated["storage_heat"]).detach().numpy(),
        boundary_heat=(right_q[:, -1] - left_q[:, 0]).detach().numpy(),
        sink=sum(integrated["sink"]).detach().numpy(),
        joule=sum(integrated["joule"]).detach().numpy(),
        storage_mass=sum(integrated["storage_mass"]).detach().numpy(),
        boundary_mass=(right_f[:, -1] - left_f[:, 0]).detach().numpy(),
        reaction=sum(integrated["reaction"]).detach().numpy(),
        current_left=left_j[:, 0].detach().numpy(),
        current_right=right_j[:, -1].detach().numpy(),
        current_port=current_port.detach().numpy(),
    )


def diagnose_global_baseline(
    model: torch.nn.Module,
    gt: dict[str, np.ndarray],
    points: dict[str, np.ndarray],
    baseline_config: dict[str, Any],
) -> dict[str, Any]:
    interface = float(model.params["L_int"]) / float(model.params["L_eff"])
    train_coordinates = np.vstack(
        [
            _local_to_global(points["train_left_stage_100"], interface, "left"),
            _local_to_global(points["train_right_stage_100"], interface, "right"),
        ]
    )
    eval_coordinates = np.vstack(
        [
            _local_to_global(points["eval_left"], interface, "left"),
            _local_to_global(points["eval_right"], interface, "right"),
        ]
    )
    train_residuals = compute_full_residuals(model, torch.as_tensor(train_coordinates, dtype=torch.float32))
    eval_residuals = compute_full_residuals(model, torch.as_tensor(eval_coordinates, dtype=torch.float32))
    train_rms = {key: _rms_tensor(train_residuals[key]) for key in ("r_phi", "r_c", "r_T", "r_m")}
    eval_rms = {key: _rms_tensor(eval_residuals[key]) for key in ("r_phi", "r_c", "r_T", "r_m")}
    boundary = compute_global_boundary_terms(model, torch.as_tensor(points["boundary_t"], dtype=torch.float32))
    interface_terms = compute_global_interface_terms(
        model,
        torch.as_tensor(points["interface_t"], dtype=torch.float32),
        float(baseline_config["training"]["interface_probe_fraction"]),
    )
    loss_blocks = {
        key: torch.mean(train_residuals[key].square()) for key in ("r_phi", "r_c", "r_T", "r_m")
    }
    loss_blocks["boundary"] = torch.stack([torch.mean(value.square()) for value in boundary.values()]).mean()
    loss_blocks["interface_proxy"] = torch.stack(
        [torch.mean(value.square()) for value in interface_terms.values()]
    ).mean()
    gradient = gradient_diagnostics(model, loss_blocks)
    score, predictions = _field_and_port_score(model, gt)
    conservation = global_model_conservation(model, points)
    state_interface = {
        "phi": _rms_tensor(interface_terms["phi_jump"]),
        "c_v": _rms_tensor(interface_terms["c_jump"]),
        "T": _rms_tensor(interface_terms["temperature_jump"]),
        "m": _rms_tensor(interface_terms["m_jump"]),
    }
    flux_interface = {
        "current": _rms_tensor(interface_terms["current_flux_jump"]),
        "heat": _rms_tensor(interface_terms["heat_flux_jump"]),
        "defect": _rms_tensor(interface_terms["defect_flux_jump"]),
    }
    return {
        "model_role": "current_single_global_network_baseline",
        "interface_semantics": "finite-band proxy from one smooth network; not an exact trace",
        "parameter_count": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
        "train_residual_rms": train_rms,
        "heldout_residual_rms": eval_rms,
        "boundary_rms": _term_rms(boundary),
        "interface_state_rms": state_interface,
        "interface_flux_rms": flux_interface,
        "gradient_diagnostics": gradient,
        **score,
        **conservation,
        "worst_time_window_current_error": _worst_time_window(predictions["I"], gt["I"]),
    }


def diagnose_split_model(
    model: torch.nn.Module,
    gt: dict[str, np.ndarray],
    points: dict[str, np.ndarray],
) -> dict[str, Any]:
    train = {
        domain: compute_domain_residuals(
            model, torch.as_tensor(points[f"train_{domain}_stage_100"], dtype=torch.float32), domain
        )
        for domain in ("left", "right")
    }
    evaluation = {
        domain: compute_domain_residuals(
            model, torch.as_tensor(points[f"eval_{domain}"], dtype=torch.float32), domain
        )
        for domain in ("left", "right")
    }
    boundary = compute_split_boundary_terms(model, torch.as_tensor(points["boundary_t"], dtype=torch.float32))
    interface = compute_exact_interface_terms(model, torch.as_tensor(points["interface_t"], dtype=torch.float32))
    score, predictions = _field_and_port_score(model, gt)
    return {
        "model_role": "matched_budget_dual_domain_conservative_full_pinn",
        "interface_semantics": "independent exact left/right traces at declared L_int",
        "parameter_count": model.parameter_counts()["total"],
        "train_residual_rms": _combine_residual_rms(train["left"], train["right"]),
        "heldout_residual_rms": _combine_residual_rms(evaluation["left"], evaluation["right"]),
        "boundary_rms": _term_rms(boundary),
        "interface_state_rms": _term_rms(interface["state"]),
        "interface_flux_rms": _term_rms(interface["flux"]),
        **score,
        **split_model_conservation(model, points),
        "worst_time_window_current_error": _worst_time_window(predictions["I"], gt["I"]),
    }


def evaluate_repair_gates(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    gates = config["gates"]
    boundary_flux_keys = ("defect_left", "defect_right", "heat_left", "heat_right")
    checks = {
        "port": metrics["port_full_trace_nrmse95"] <= float(gates["port_full_trace_nrmse95_max"]),
        "heldout_residuals": all(
            value <= float(gates["residual_rms_max"]) for value in metrics["heldout_residual_rms"].values()
        ),
        "fields": all(
            metrics["field_score_only_nrmse95"][key] <= float(limit)
            for key, limit in gates["field_score_only_nrmse95_max"].items()
        ),
        "interface_state": all(
            metrics["interface_state_rms"][key] <= float(limit)
            for key, limit in gates["interface_state_rms_max"].items()
        ),
        "interface_flux": all(
            metrics["interface_flux_rms"][key] <= float(limit)
            for key, limit in gates["interface_flux_rms_max"].items()
        ),
        "endpoint_flux": all(
            metrics["boundary_rms"][key] <= float(gates["endpoint_flux_rms_max"])
            for key in boundary_flux_keys
        ),
        "current_conservation": metrics["terminal_current_conservation_normalized_error"]
        <= float(gates["terminal_current_conservation_max"]),
        "energy_conservation": metrics["global_energy_account_normalized_imbalance"]
        <= float(gates["global_energy_account_imbalance_max"]),
        "finite_states": bool(metrics["finite_outputs"]),
        "physical_bounds": bool(metrics["physical_state_bounds"]),
    }
    return {"checks": checks, "all_pass": all(checks.values())}
