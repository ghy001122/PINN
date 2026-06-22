# File inventory

## Core package

- `src\pinnpcm\physics\`: Ground Truth physics, electrostatics, conductivity,
  parameters, and voltage protocols.
- `src\pinnpcm\pinn\`: PINN skeleton plus inverse v0 data loading, model,
  losses, and residual utilities.
- `src\pinnpcm\utils\`: YAML, JSON, path, and seed helpers.
- `src\pinnpcm\visualization\`: plotting helpers.

## Current PINN inverse v0 files

- `src\pinnpcm\pinn\data.py`: loads frozen Ground Truth data, sparse
  observations, and manifest metadata.
- `src\pinnpcm\pinn\models.py`: constrained neural field model for `c_v`,
  `delta_T`, `m`, and positive surrogate `sigma`.
- `src\pinnpcm\pinn\losses.py`: series port reconstruction, normalized MSE,
  smoothness, and light feasibility losses.
- `src\pinnpcm\pinn\physics_residuals.py`: autograd-based v1 heat, state,
  defect, sigma-consistency, and boundary residuals.
- `scripts\train_pinn_inverse_v0.py`: single-run training entry point.
- `scripts\run_pinn_inverse_v0_ablation.py`: three-run ablation audit runner.
  It also supports `--smoke-test`, which runs one epoch per ablation in ignored
  smoke-test output directories without overwriting the official ablation
  summary.
- `scripts\train_pinn_inverse_v1.py`: single-run v1 physics-regularized
  training entry point.
- `scripts\run_pinn_inverse_v1_experiments.py`: three-run v1 experiment runner.

## Current test coverage

- `tests\test_pinn_inverse_v0.py`: data loading, model forward, conductance
  reconstruction, single-run smoke test, ablation config checks, ablation smoke
  test, and nRMSE metrics checks.
- `tests\test_pinn_inverse_v1.py`: v1 config checks, physics residual finite
  checks, autograd derivative checks, and v1 training smoke test.

## Evidence-chain reports

- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`: main ablation
  audit report for commit `ffad313297c78cfc158e6ae270c3b86639d79e1d`.
- `docs\codex_reports\evidence_chain_patch_report.md`: evidence-chain patch
  report for state-file consistency and smoke-test verification.
- `docs\codex_reports\pinn_inverse_v1_physics_report.md`: final Codex report
  for the v1 physics-regularized implementation and experiment run.

## Frozen files not to modify during PINN audit

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- Ground Truth equations and default Ground Truth parameters.
