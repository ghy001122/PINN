# Physics-Informed Digital Twin for Oxide Optoelectronic Memristive Devices

This repository supports the SCI paper sprint topic:

**Physics-informed digital twin for sparse-data inverse identification of electro-thermal-defect dynamics in oxide optoelectronic memristive devices**

Internal Chinese title: **面向氧化物光电忆阻器的物理信息数字孪生与稀疏数据多物理参数反演**

## Research Goal

The project builds a reproducible, CPU-runnable Python codebase for a literature-guided synthetic digital twin and inverse-identification workflow. The first version focuses on a stable one-dimensional electro-thermal-defect-conductive-state model instead of high-risk full 3D Maxwell, full phase-field, or unverified fabrication claims.

Hardware anchor: **Nb/NbOx/V2O5/Ni**.

The software model is inspired by this interface-engineered oxide memristor stack, but the generated data is a synthetic benchmark. It is not measured experimental data and does not claim to reproduce every microscopic detail of a real device.

## Current Project Phase

The current active phase is documented in
`docs/research_strategy/active_phase.md`:

**literature-backed constrained gamma_sub inversion preparation**.

The completed v0/v1/v1.1 PINN audits and identifiability audits show that
port-only full hidden-field inversion is ill-posed. The current research route
therefore focuses on constrained reduced inversion of `gamma_sub` under
literature-guided priors for confounding parameters.

## Codex Low-Token Context Workflow

For non-trivial Codex work, first read:

1. `CODEX_CONTEXT.md`
2. `docs/research_strategy/active_phase.md`

Then follow `docs/research_strategy/context_loading_policy.md`. Long reports,
reference packs, papers, and code should be loaded only when the task requires
them.

## Paper Thread

1. One-dimensional coupled Ground Truth solver for electro-thermal-defect-conductive-state dynamics.
2. Sparse port-level observations from synthetic I-V and G(t) traces.
3. PINN-based multiphysics inverse identification.
4. Black-box MLP/LSTM and non-physics baselines.
5. Noise robustness, ablation, and cross-voltage-protocol generalization.

## Environment

Use a single Python 3.11 virtual environment. From Windows PowerShell:

```powershell
cd "E:\Python demo\PINN"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Quick Test

```powershell
python -m pytest
```

## Generate Ground Truth

Quick CPU smoke run:

```powershell
python scripts/run_gt_v1.py --protocol triangle --nx 11 --nt 80 --outdir data/processed/gt_v1_quick
python scripts/plot_gt_v1.py --input data/processed/gt_v1_quick/gt_triangle.npz --outdir outputs/figures/gt_v1_quick
```

Longer first-pass runs:

```powershell
python scripts/run_gt_v1.py --protocol triangle --nx 31 --nt 400 --outdir data/processed/gt_v1
python scripts/run_gt_v1.py --protocol ltp_ltd --nx 31 --nt 500 --outdir data/processed/gt_v1
python scripts/plot_gt_v1.py --input data/processed/gt_v1/gt_triangle.npz --outdir outputs/figures/gt_v1
```

## Outputs

- Ground Truth arrays: `data/processed/**/gt_<protocol>.npz`
- Sparse noisy observations: `data/processed/**/obs_<protocol>_sparse.npz`
- Ground Truth parameter snapshot: `data/processed/**/params_gt_v1.json`
- Figures: `outputs/figures/**`
- Logs, checkpoints, and tables: `outputs/logs/`, `outputs/checkpoints/`, and `outputs/tables/`

Generated data and outputs are ignored by Git. Keep only code, configs, docs, and tests under version control.

## Ground Truth Data

The Ground Truth solver uses finite-volume spatial discretization and `scipy.integrate.solve_ivp(method="Radau")`. It returns synthetic fields and port observables:

- `x`, `t`
- `V`, `I`, `G`
- `c_v`, `T`, `m`, `E`, `phi`, `sigma`
- `params_json`

All default parameters are literature-guided synthetic priors or order-of-magnitude priors, not measured material parameters.

## PINN Status

The repository now includes runnable PINN inverse v0/v1/v1.1 audit workflows
and a reduced `gamma_sub` identifiability path. Earlier skeleton components are
kept for continuity:

- Fourier-feature MLP in `src/pinnpcm/pinn/network.py`
- Physical variable transforms in `src/pinnpcm/pinn/transforms.py`
- Autograd residual interface in `src/pinnpcm/pinn/residuals.py`
- Loss aggregation in `src/pinnpcm/pinn/losses.py`
- Training script placeholder in `scripts/train_pinn_v1.py`

Do not report inverse-identification results as experimental validation. Current
results are synthetic numerical digital-twin benchmark evidence.

## Directory Map

```text
configs/                 YAML configs for Ground Truth and PINN experiments
data/raw/                User-provided or lab raw data
data/external/           Digitized literature curves with provenance records
data/processed/          Generated synthetic benchmark data
docs/                    Device anchor, equations, provenance, plans, reviewer defense
outputs/                 Figures, logs, checkpoints, and tables
scripts/                 CLI entrypoints
src/pinnpcm/             Python package
tests/                   Pytest suite
```

## Academic Ethics Statement

This repository does not fabricate experimental data. The default workflow generates a literature-guided synthetic benchmark for algorithm validation. Synthetic data must not be described as measured experimental data, and order-of-magnitude priors must not be described as measured material parameters. Any later use of real lab data or digitized literature data must be documented before analysis.
