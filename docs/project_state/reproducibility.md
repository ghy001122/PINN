# Reproducibility

## Environment

Use Python 3.11 with the repository requirements:

```powershell
python -m pip install -r requirements.txt
```

The local development environment used for the latest verification was the
workspace `.venv` Python 3.11 interpreter.

## Unit tests

```powershell
python -m pytest
```

## Low-token context workflow

For future non-trivial tasks, begin with:

```text
CODEX_CONTEXT.md
docs\research_strategy\active_phase.md
```

Then follow:

```text
docs\research_strategy\context_loading_policy.md
```

Do not load all long reports, raw reference-pack files, or full papers by
default. Long-context reads must be justified by the active task.

The local reference pack was integrated as documentation only. Re-running this
integration should not modify frozen Ground Truth files, source code, configs,
tests, generated arrays, or generated figures.

## Ground Truth v1.1 acceptance reproduction

```powershell
python scripts/run_gt_v1_acceptance.py
```

This regenerates:

- `data\processed\gt_v1_acceptance\`
- `outputs\figures\gt_v1_acceptance\`
- `outputs\tables\gt_v1_acceptance\`

## PINN inverse v0 ablation reproduction

```powershell
python scripts/run_pinn_inverse_v0_ablation.py
```

This regenerates:

- `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `outputs\pinn_inverse_v0\triangle_port_only\`
- `outputs\tables\pinn_inverse_v0_ablation_summary.json`

Only the lightweight summary JSON is intended to be committed.

## PINN inverse v0 ablation smoke test

For evidence-chain or CI-style checks that should not overwrite the official
ablation summary, run:

```powershell
python scripts/run_pinn_inverse_v0_ablation.py --smoke-test
```

This writes ignored smoke artifacts to:

- `outputs\pinn_inverse_v0_smoke\`
- `outputs\tables\pinn_inverse_v0_ablation_smoke_summary.json`

## PINN inverse v1 smoke test

```powershell
python scripts/train_pinn_inverse_v1.py --config configs/pinn_inverse_v1_triangle_physics.yaml --epochs 2
```

## PINN inverse v1 experiment reproduction

```powershell
python scripts/run_pinn_inverse_v1_experiments.py
```

This regenerates:

- `outputs\pinn_inverse_v1\triangle_physics\`
- `outputs\pinn_inverse_v1\triangle_weak_anchor\`
- `outputs\pinn_inverse_v1\triangle_port_physics\`
- `outputs\tables\pinn_inverse_v1_summary.json`

Only the lightweight v1 summary JSON is intended to be committed.

## PINN inverse v1.1 smoke test

```powershell
python scripts/train_pinn_inverse_v1.py --config configs/pinn_inverse_v1_1_triangle_physics_balanced.yaml --epochs 2
```

## PINN inverse v1.1 experiment reproduction

```powershell
python scripts/run_pinn_inverse_v1_1_experiments.py
```

This regenerates:

- `outputs\pinn_inverse_v1_1\triangle_physics_balanced\`
- `outputs\pinn_inverse_v1_1\triangle_port_physics_balanced\`
- `outputs\tables\pinn_inverse_v1_1_summary.json`

Only the lightweight v1.1 summary JSON is intended to be committed.

## PINN identifiability audit reproduction

```powershell
python scripts/analyze_pinn_identifiability.py
```

This regenerates:

- `outputs\tables\pinn_identifiability_summary.json`
- `outputs\tables\pinn_identifiability_correlation.csv`
- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

Only the lightweight summary JSON and correlation CSV are intended to be
committed. The generated figures remain ignored by Git.

## v2a gamma_sub identifiability reproduction

```powershell
python scripts/scan_gamma_sub_identifiability.py
python scripts/invert_gamma_sub_v0.py
```

This regenerates:

- `outputs\tables\gamma_sub_identifiability_summary.json`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

Only the lightweight summary JSON is intended to be committed. The generated
figures remain ignored by Git.

## gamma_sub confounding audit reproduction

```powershell
python scripts/audit_gamma_sub_confounding.py
python scripts/invert_gamma_sub_with_mismatch.py
```

This regenerates:

- `outputs\tables\gamma_sub_confounding_summary.json`
- `outputs\tables\gamma_sub_sensitivity_ranking.csv`

The audit intentionally writes only lightweight tabular evidence.

## Academic boundary

All generated results are synthetic numerical digital-twin benchmark outputs.
They must not be described as measured experimental data.
