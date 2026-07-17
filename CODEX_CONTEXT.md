# Codex Context

## Low-Token First Read

Read this file and `docs/research_strategy/active_phase.md` first. Load longer context through `docs/research_strategy/context_loading_policy.md`.

- Authoritative goal: `PROJECT_GOAL.md`
- Phase ID: `M_GAMMA_SUB_MANUSCRIPT_ASSEMBLY`
- Current evidence: `docs/project_state/current_evidence_index.md`
- Safe historical evidence lock: `d1121e16fa5015a297da468e3e6f0504b9e97d17`
- Current report: `docs/codex_reports/n0_cv_e_v3_report.md`

## Corrected North Star

A complete phase-transition PINN remains an indispensable project and paper scaffold, while an independent numerical solver remains the reference judge. Positive PINN claims are evidence-gated. The public-data quotient hypothesis remains untested; it is not an established result.

The calibration-gated constrained `gamma_sub` rank-1 result is the safe `qualified_supported` inverse mainline. D0 is a reality/identifiability bridge, not a substitute for PINN contribution or experimental validation.

## Single Active Bottleneck

`M_GAMMA_SUB_MANUSCRIPT_ASSEMBLY`: close N0 after the final bounded N0-CV-E v3 attempt and assemble the manuscript only from locked `gamma_sub` evidence plus explicit D0/N0 failure boundaries. No further N0 tuning, N1-N3, SC-LOS, 13 V access, or external refit is active.

## Evidence Snapshot

- Frozen GT v1.1: unchanged.
- P0: `qualified_supported`; P1 and P2: `failed_but_informative`; P3: narrowly `qualified_supported`; P4 positive claims: `forbidden`.
- D0a: `failed_but_informative`; source/SI parity passes, but 5-to-2.5 ns NRMSE95 is `0.163148 > 0.01`. D0b-D0d were not run and 13 V remains sealed.
- N0 teacher-equation audit: `supported`. The old conservation artifact is now classified only as an algebraic bookkeeping smoke test; an independent adjacent-state trajectory audit gives defect ledger `4.03948e-06`, energy ledger `0.00258234`, and Radau replay error `1.30271e-07`.
- N0-R v2 trained evidence: `failed_but_informative`; the local untracked checkpoint and missing final pytest record remain explicit reproducibility gaps.
- N0-CV-E v3 implementation/preflight: `supported` as a code/operator fact. All 18 no-training checks pass; analytic electrostatic parity is `2.30787e-08`, CV-RHS parity `2.12586e-08`, and current spread `3.83609e-16`.
- N0-CV-E v3 training: `failed_but_informative`. The locked seed `20260715` run reached L-BFGS after 1200 Adam steps, then a strong-Wolfe closure produced a non-finite loss before checkpoint or metric serialization. All result gates are `unassessed_fail_closed`; no balancing arm, seed expansion, sparse anchor, N1-N3, or SC-LOS was run.
- Reliable full-PINN forward, sensitivity fidelity, and inverse claims remain `forbidden`.

## Evidence Semantics

Keep `public_external_raw`, `derived`, `interpolated`, `solver_generated`, `pinn_predicted`, and `synthetic_gt` distinct. Zhang Methods states source parameters were optimized against experimental results, so 13 V can at most become a `repository-withheld, preregistered cross-voltage evaluation`; it cannot be called an independent external holdout.

## Operating Rule

Preserve all negative artifacts and unchanged preregistered gates. N0-CV-E v3 is the final bounded N0 attempt: do not reinterpret its operator preflight as trained PINN evidence or rerun it with altered optimization. Use only `supported`, `qualified_supported`, `failed_but_informative`, or `forbidden`.
