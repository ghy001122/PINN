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

## Academic boundary

All generated results are synthetic numerical digital-twin benchmark outputs.
They must not be described as measured experimental data.
