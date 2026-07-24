# Physics-Informed Digital Twin for Oxide Memristive and Phase-Transition Devices

A reproducible Python 3.11 research codebase for sparse-observation inverse identification, identifiability audits, and physics-informed digital twins of oxide memristive and phase-transition devices.

The selected research line is `GeoPhase-OQ-PINN`: a Qiu-inspired coplanar VO2
device resolved in the true x-y plane, a passive K-state reduction of vertical
thermal transport, a phase-transition-localized PINN, stiffness homotopy, and
solver-gated observation-quotient inversion. A Chen-inspired SnSe/NbO2 device
is reserved for material-specific cross-model numerical validation.

The historical frozen Nb/NbOx/V2O5/Ni-inspired 1D benchmark, constrained
`gamma_sub` inverse, complete-PINN failures, and M40/M40R source bridge remain
read-only baselines and reviewer-defense evidence. They are not the intended
final structure and are not fabricated-device replicas.

## Evidence Boundary

All repository Ground Truth and model outputs are synthetic numerical digital-twin evidence unless a provenance-backed external or experimental dataset is explicitly identified. Experimental validation is currently absent. Literature-guided and engineering priors are not measured material parameters.

The GeoPhase route is currently a preregistered research design. No positive
2.5D reference, GeoPhase training, architecture benefit, geometry
generalization, sensitivity fidelity, observation quotient, refusal, or
cross-model result exists yet. Full 2D hidden-field recovery, terminal-only
raw-parameter inverse, full STL reproduction, universal Fourier superiority,
and device-grade FEM/3D reproduction remain unestablished.

## Goal And Context

The persistent delivery target is a complete, reproducible, ethically bounded Q2 SCI manuscript and submission package; this is not a guarantee of journal acceptance. Exactly one highest-value research bottleneck is active per round.

- Delivery goal: [PROJECT_GOAL.md](PROJECT_GOAL.md)
- Low-token Codex entry: [CODEX_CONTEXT.md](CODEX_CONTEXT.md)
- Current phase: [active_phase.md](docs/research_strategy/active_phase.md)
- Current evidence: [current_evidence_index.md](docs/project_state/current_evidence_index.md)
- SCI pipeline: [sci_delivery_pipeline.md](docs/research_strategy/sci_delivery_pipeline.md)
- GeoPhase execution contract: [geophase_oq_pinn_execution_contract.md](docs/research_strategy/geophase_oq_pinn_execution_contract.md)
- Innovation portfolio: [innovation_portfolio.md](docs/research_strategy/innovation_portfolio.md)
- Governance: [AGENTS.md](AGENTS.md)

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

Current evidence entrypoints are indexed in `docs/project_state/current_evidence_index.md`. The root registries are cumulative history and should be opened only to trace a specific older run. Do not rerun or overwrite frozen GT v1.1 during ordinary work.

## Directory Guide

```text
configs/                 versioned experiment and physics configuration
src/pinnpcm/physics/     physical models, solvers, parameters, topology
src/pinnpcm/solvers/     independent numerical judges; do not share PINN residual code
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

Sparse terminal observations constrain integrated device behavior but do not
uniquely determine arbitrary hidden fields. The new route therefore requires a
positive field/port/ledger GeoPhase forward result before inverse work, then
compares only solver-supported observation quotients and refuses unsupported
raw recovery. The current active task is the independent G0/E0 2.5D reference;
no PINN training is authorized before it passes.

## Academic Ethics

Do not describe synthetic data as measured data, priors as measurements, a smoke test as a method result, or a local observability rank gain as full field recovery. Any future digitized literature curves must be stored with provenance in `data/external/` and documented in `docs/data_provenance.md`.
