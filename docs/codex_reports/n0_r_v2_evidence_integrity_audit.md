# N0-R v2 Evidence-Integrity Audit

Base commit: `e3f5765801991ebd1006dc762f8804a48e2d7a5a`

Audit commit/worktree HEAD: `e3f5765801991ebd1006dc762f8804a48e2d7a5a` (pre-commit working tree).

Status: `completed_with_documented_v2_evidence_gaps`. This is a no-training audit.

## Findings

- v2 gate coverage complete: `False`; fail-closed gaps: `ic_bc_max_normalized_error, positive_temperature_required, bounded_c_v_and_m_required, frozen_gt_hash_unchanged_required, minimum_passing_seeds, total_seeds, defect_mass_ledger_max`.
- v2 checkpoint is locally present but Git-tracked: `False`; classification: `missing_from_versioned_evidence`.
- Remote CI: `no_runs_for_commit`; the audit does not infer CI success from an empty run list.
- Historical pytest evidence: `missing`.
- `n0_global_conservation_audit_v1.json` is now explicitly treated as an algebraic bookkeeping smoke test, not independent trajectory validation.

## Independent adjacent-state ledger

- Defect gate value: `4.03948394e-06` (gate `0.01`).
- Energy gate value: `0.00258233858` (gate `0.05`).
- Radau replay maximum relative RMS: `1.30271265e-07`.
- Tamper detection: defect `True`, energy `True`.

## Unified frozen-scale rescore

| Model | Port NRMSE95 | max CV residual | defect ledger | energy ledger |
| --- | ---: | ---: | ---: | ---: |
| global baseline | 0.123764 | 2569.68 | 1 | 0.999876 |
| e3f5765 split repair | 0.120358 | 500143 | 1 | 0.999874 |

Both rows use the same analytic series-electrical reconstruction, frozen CV RHS, full 31-cell time grid, and dimensionless registry. The comparison does not reuse the incompatible v2 interface scales.

## Claim boundary

Phase A repairs evidence routing but does not upgrade trained full-PINN evidence. N0-CV-E v3 remains forbidden until its independent preflight and conditional training gates pass.
