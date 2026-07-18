"""Build the M33 figure and focused scientific report from locked outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import torch_cv_rhs
from pinnpcm.pinn.mixed_flux_pinn import MixedStateFluxPINN
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt


ROOT = Path(__file__).resolve().parents[1]


def _build(config: Mapping[str, Any], params: Mapping[str, Any], duration: float) -> MixedStateFluxPINN:
    architecture = config["architecture"]
    return MixedStateFluxPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=duration,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=config["dimensionless_registry"],
        seed=int(config["training"]["seed"]),
    )


def _failure_summary(config: Mapping[str, Any], preflight: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "m33_mixed_flux_final_summary_v1",
        "stage_id": config["stage_id"],
        "preregistration_commit": preflight["preregistration_commit"],
        "preflight_all_pass": False,
        "training_executed": False,
        "training_seed": None,
        "metrics": {"preflight": preflight["metrics"]},
        "gates": {"checks": preflight["checks"], "all_pass": False},
        "comparison_to_v3r": {"performed": False, "reason": "preflight_failed"},
        "status": "failed_but_informative",
        "positive_forward_claim_allowed": False,
        "failure_interpretation": "A preregistered no-training check failed, so the single M33 training run was not authorized.",
    }


def _plot(config: Mapping[str, Any], result: Mapping[str, Any], gt: Mapping[str, np.ndarray], params: Mapping[str, Any]) -> None:
    output = ROOT / config["outputs"]["figure"]
    output.parent.mkdir(parents=True, exist_ok=True)
    if not result["training_executed"]:
        fig, axis = plt.subplots(figsize=(8.0, 4.5))
        failed = [name for name, passed in result["gates"]["checks"].items() if not passed]
        axis.axis("off")
        axis.text(0.5, 0.62, "M33 preflight failed; training not executed", ha="center", va="center", fontsize=15)
        axis.text(0.5, 0.40, "Failed checks: " + ", ".join(failed), ha="center", va="center", wrap=True)
        fig.tight_layout()
        fig.savefig(output, dpi=180)
        plt.close(fig)
        return

    model = _build(config, params, float(gt["t"][-1])).float()
    checkpoint = torch.load(ROOT / config["outputs"]["checkpoint"], map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    t = np.asarray(gt["t"], dtype=float)
    time = torch.as_tensor((t / t[-1])[:, None], dtype=torch.float32)
    with torch.no_grad():
        prediction = model(time)
    gt_time = time.double()
    target_flux = torch_cv_rhs(
        model.double(), gt_time,
        torch.as_tensor(gt["c_v"], dtype=torch.float64),
        torch.as_tensor(gt["T"], dtype=torch.float64),
        torch.as_tensor(gt["m"], dtype=torch.float64),
    )
    face = model.interface_face
    pred = {name: prediction[name].detach().cpu().numpy() for name in prediction}
    q_target_T = target_flux["heat_flux"].detach().cpu().numpy()[:, face]
    q_target_c = target_flux["defect_flux"].detach().cpu().numpy()[:, face]
    model.float()

    fig, axes = plt.subplots(3, 2, figsize=(11.2, 10.0))
    axes[0, 0].plot(t * 1e3, np.asarray(gt["I"]) * 1e6, label="frozen GT", lw=2)
    axes[0, 0].plot(t * 1e3, pred["I"] * 1e6, label="M33 PINN", lw=1.5)
    axes[0, 0].set(title="Port current", xlabel="time (ms)", ylabel="I (uA)")
    axes[0, 0].legend()

    axes[0, 1].plot(t * 1e3, np.mean(gt["T"], axis=1), label="GT mean T")
    axes[0, 1].plot(t * 1e3, np.mean(pred["T"], axis=1), label="M33 mean T")
    axes[0, 1].set(title="Thermal field summary", xlabel="time (ms)", ylabel="T (K)")
    axes[0, 1].legend()

    axes[1, 0].plot(t * 1e3, q_target_T, label="frozen face flux")
    axes[1, 0].plot(t * 1e3, pred["q_T"][:, face], label="explicit q_T head")
    axes[1, 0].set(title="Interface heat flux", xlabel="time (ms)", ylabel="q_T (W m$^{-2}$)")
    axes[1, 0].legend()

    axes[1, 1].plot(t * 1e3, q_target_c, label="frozen face flux")
    axes[1, 1].plot(t * 1e3, pred["q_c"][:, face], label="explicit q_c head")
    axes[1, 1].set(title="Interface defect flux", xlabel="time (ms)", ylabel="q_c (m s$^{-1}$)")
    axes[1, 1].legend()

    field_names = ["c_v", "T", "m", "phi", "sigma"]
    field_values = [result["metrics"]["field_score_only_nrmse95"][name] for name in field_names]
    axes[2, 0].bar(field_names, field_values)
    axes[2, 0].axhline(config["result_gates"]["field_score_only_nrmse95_max"], color="black", ls="--", label="gate")
    axes[2, 0].set(title="Held-out field NRMSE95", ylabel="NRMSE95")
    axes[2, 0].legend()

    gate_names = ["port", "PDE", "constit.", "interface", "energy", "mass"]
    ratios = [
        result["metrics"]["port_full_trace_nrmse95"] / config["result_gates"]["port_full_trace_nrmse95_max"],
        max(result["metrics"]["cv_residual_rms"].values()) / config["result_gates"]["residual_rms_max"],
        max(result["metrics"]["constitutive_rms"].values()) / config["result_gates"]["constitutive_rms_max"],
        max(value for value in result["metrics"]["interface_flux_rms"].values() if isinstance(value, (int, float))) / config["result_gates"]["interface_flux_rms_max"],
        result["metrics"]["global_energy_ledger"]["gate_value"] / config["result_gates"]["global_energy_imbalance_max"],
        result["metrics"]["defect_mass_ledger"]["gate_value"] / config["result_gates"]["defect_mass_ledger_max"],
    ]
    axes[2, 1].bar(gate_names, ratios, color=["#2c7fb8" if value <= 1 else "#d95f0e" for value in ratios])
    axes[2, 1].axhline(1.0, color="black", ls="--")
    axes[2, 1].set_yscale("log")
    axes[2, 1].set(title="Gate ratios (<=1 passes)", ylabel="metric / gate")
    fig.suptitle(f"M33 mixed-flux full-PINN MVE: {result['status']}")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _report(config: Mapping[str, Any], preflight: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    failed = [name for name, passed in result["gates"]["checks"].items() if not passed]
    lines = [
        "# M33 Feasibility-First Mixed-Flux Full-PINN MVE",
        "",
        f"Base snapshot: `{config['base_snapshot']}`  ",
        f"Preregistration commit: `{result['preregistration_commit']}`  ",
        "Evidence: frozen synthetic numerical digital twin; no public data or experiment.  ",
        f"Claim status: `{result['status']}`",
        "",
        "## Scientific result",
        "",
        f"Preflight passed: `{preflight['all_pass']}`. Training executed: `{result['training_executed']}`.",
    ]
    if result["training_executed"]:
        metrics = result["metrics"]
        lines.extend(
            [
                f"The single locked Adam run used `{result['training_steps']}` steps ({result['training_budget_ratio_to_v3r']:.2f}x v3r Adam budget) and seed `{result['training_seed']}`.",
                "",
                "| Gate block | Value | Pass |",
                "| --- | ---: | :---: |",
                f"| Port NRMSE95 | {metrics['port_full_trace_nrmse95']:.8g} | {result['gates']['checks']['port']} |",
                f"| Max PDE residual RMS | {max(metrics['cv_residual_rms'].values()):.8g} | {result['gates']['checks']['cv_residuals']} |",
                f"| Max constitutive RMS | {max(metrics['constitutive_rms'].values()):.8g} | {result['gates']['checks']['constitutive']} |",
                f"| Max field NRMSE95 | {max(metrics['field_score_only_nrmse95'].values()):.8g} | {result['gates']['checks']['fields']} |",
                f"| Max explicit interface-flux NRMSE95 | {max(v for v in metrics['interface_flux_rms'].values() if isinstance(v, (int, float))):.8g} | {result['gates']['checks']['interface_flux']} |",
                f"| Energy ledger | {metrics['global_energy_ledger']['gate_value']:.8g} | {result['gates']['checks']['energy_ledger']} |",
                f"| Defect ledger | {metrics['defect_mass_ledger']['gate_value']:.8g} | {result['gates']['checks']['defect_ledger']} |",
                f"| No regression vs v3r | {result['comparison_to_v3r']['no_worse_count']}/{result['comparison_to_v3r']['required_metrics']} | {result['gates']['checks']['v3r_no_regression']} |",
            ]
        )
    lines.extend(
        [
            "",
            "Failed gates: " + (", ".join(failed) if failed else "none"),
            "",
            "## Claim boundary",
            "",
        ]
    )
    if result["positive_forward_claim_allowed"]:
        lines.append("Allowed: `qualified_supported` minimum forward-fidelity evidence for this single frozen 1D synthetic mixed-flux full-PINN MVE. N1-N3 remain unrun.")
    else:
        lines.append("Allowed: `failed_but_informative`; the one-shot mixed-flux plus feasibility-first contract remains insufficient under at least one locked gate.")
    lines.extend(
        [
            "",
            "Forbidden: component novelty for mixed formulations or augmented Lagrangians; sensitivity fidelity; inverse recovery; experimental validation; cross-material generalization; gate relaxation; seed expansion.",
            "",
            "## Disposition",
            "",
            "A failed M33 permanently closes new full-PINN training exploration under this project contract and routes the project back to immediate assembly of the calibration-gated rank-1 `gamma_sub` manuscript. A passing M33 only registers an N1 sensitivity-fidelity gate; it does not execute it.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    preflight = json.loads((ROOT / config["outputs"]["preflight"]).read_text(encoding="utf-8"))
    result_path = ROOT / config["outputs"]["final_summary"]
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = _failure_summary(config, preflight)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    _plot(config, result, gt, params)
    report_path = ROOT / config["outputs"]["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(config, preflight, result), encoding="utf-8", newline="\n")
    return {"status": result["status"], "figure": config["outputs"]["figure"], "report": config["outputs"]["report"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m33_feasibility_first_mixed_flux.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    print(json.dumps(run(config_path)))


if __name__ == "__main__":
    main()

