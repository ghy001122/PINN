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

## Academic boundary

All generated results are synthetic numerical digital-twin benchmark outputs.
They must not be described as measured experimental data.
