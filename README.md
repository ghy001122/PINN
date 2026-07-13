# Physics-Informed Digital Twin for Oxide Memristive and Phase-Transition Devices

A reproducible Python 3.11 research codebase for sparse-observation inverse identification, identifiability audits, and physics-informed digital twins of oxide memristive and phase-transition devices.

The project contains two connected lines:

- main manuscript: calibration-gated constrained `gamma_sub` inversion on a frozen 1D synthetic benchmark;
- extension: VO2/NbO2 multilayer OASIS models, segmented terminals, stiffness audits, and strict neural-solver claim gates.

The historical frozen benchmark is Nb/NbOx/V2O5/Ni-inspired. It is not the whole current scope, and it is not a fabricated-device replica.

## Evidence Boundary

All repository Ground Truth and model outputs are synthetic numerical digital-twin evidence unless a provenance-backed external or experimental dataset is explicitly identified. Experimental validation is currently absent. Literature-guided and engineering priors are not measured material parameters.

Current high-risk claims such as full 2D hidden-field recovery, terminal-only 2D inverse solved, full STL reproduction, universal F-SPS/Fourier superiority, and device-grade FEM/3D reproduction are not established.

## Goal And Context

The persistent delivery target is a complete, reproducible, ethically bounded Q2 SCI manuscript and submission package; this is not a guarantee of journal acceptance. Exactly one highest-value research bottleneck is active per round.

- Delivery goal: [PROJECT_GOAL.md](PROJECT_GOAL.md)
- Low-token Codex entry: [CODEX_CONTEXT.md](CODEX_CONTEXT.md)
- Current phase: [active_phase.md](docs/research_strategy/active_phase.md)
- Canonical full handoff: [codex_new_dialog_handoff_d23a576.md](docs/research_strategy/codex_new_dialog_handoff_d23a576.md)
- Governance: [AGENTS.md](AGENTS.md)

Workspace path used by the project owner: `E:\Python demo\PINN`.

## Environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e .
```

The supported runtime is Python `>=3.11,<3.12` with pinned dependencies in `requirements.txt`.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Governance-only validation:

```powershell
.\.venv\Scripts\python.exe scripts\audit_project_governance.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py
```

## Core Reproduction Entrypoints

Frozen GT smoke generation, only for a new non-frozen output directory:

```powershell
.\.venv\Scripts\python.exe scripts\run_gt_v1.py --protocol triangle --nx 11 --nt 80 --outdir data/processed/gt_v1_quick
```

Current v10 evidence entrypoints are indexed in `EXPERIMENT_REGISTRY.md`; do not rerun or overwrite frozen GT v1.1 during ordinary work. Lightweight committed results live under `outputs/tables/`.

## Directory Guide

```text
configs/                 versioned experiment and physics configuration
src/pinnpcm/physics/     physical models, solvers, parameters, topology
src/pinnpcm/pinn/        neural fields, transforms, residuals, losses
scripts/                 config-driven CLI and audit entrypoints
tests/                   unit, behavior, integrity, and claim-gate tests
data/external/           provenance-backed literature curves, if added
data/processed/          generated synthetic data; frozen GT is read-only
outputs/tables/          lightweight committed evidence
outputs/figures/         generated figures
docs/                    equations, strategy, reports, manuscript evidence
```

## Current Scientific Interpretation

Sparse terminal observations constrain integrated conductance strongly but do not uniquely determine all hidden thermal, defect, phase, and conductivity fields. The most defensible result is therefore reduced-target inverse identification under calibrated or tightly bounded priors. OASIS v10 adds a credible multilayer and segmented-terminal scaffold, but strict CV neural training and thermal inverse blocks remain failed or incomplete.

## Academic Ethics

Do not describe synthetic data as measured data, priors as measurements, a smoke test as a method result, or a local observability rank gain as full field recovery. Any future digitized literature curves must be stored with provenance in `data/external/` and documented in `docs/data_provenance.md`.
