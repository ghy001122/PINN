# Codex Context

## Low-Token First Read

Read this file and `docs/research_strategy/active_phase.md` first. Load longer context through `docs/research_strategy/context_loading_policy.md`.

- Authoritative goal: `PROJECT_GOAL.md`
- Phase ID: `N0_FULL_PINN_NUMERICAL_REPAIR`
- Current evidence: `docs/project_state/current_evidence_index.md`
- Safe historical evidence lock: `d1121e16fa5015a297da468e3e6f0504b9e97d17`
- Current report: `docs/codex_reports/vo2_protocol_quotient_full_pinn_v2_report.md`

## Corrected North Star

A complete phase-transition PINN is an indispensable project and paper scaffold, while an independent numerical solver remains the sensitivity/reference judge. The candidate claim is that public terminal observations may identify physical time-scale quotients or equivalence classes rather than unique raw parameters, and branch/protocol may change the observable quotient. This is a hypothesis, not an established result.

D0 public VO2 work is a reality/identifiability bridge, not a substitute for PINN contribution or project-generated experimental validation. The existing calibration-gated constrained `gamma_sub` rank-1 result remains the safe inverse mainline until a stronger full-PINN chain passes.

## Single Active Bottleneck

`N0_FULL_PINN_NUMERICAL_REPAIR`: diagnose why the versioned complete 1D PINN contract passes manufactured/IC/BC checks while its fixed single-seed training MVE fails the frozen synthetic port and residual gates. Do not run N1-N3 until N0 passes in at least 2/3 fixed seeds.

## Evidence Snapshot

- Frozen GT v1.1: unchanged.
- P0: `qualified_supported`.
- P1: `failed_but_informative`; `E_T=0.37563055753707886`, `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success `0.0`. It is not an automatic gate for the minimum 1D scaffold; it becomes a prerequisite for multidomain/2D/interface claims.
- P2: `failed_but_informative`.
- P3: `qualified_supported` only for a static pure-electrical three-parameter local rank result.
- P4: positive claims `forbidden`.
- D0a: `failed_but_informative`; source/SI parity passes, but 5-to-2.5 ns NRMSE95 is `0.163148 > 0.01`.
- D0b-D0d: not run; no fit lock; 13 V remains sealed.
- N0 contract: implemented and preflight passed.
- N0 trained evidence: `failed_but_informative`; port NRMSE95 `0.123764`; all four residual RMS values exceed `0.01`.
- N1-N3: not run and positive claims `forbidden`.

## Evidence Semantics

Keep `public_external_raw`, `derived`, `interpolated`, `solver_generated`, `pinn_predicted`, and `synthetic_gt` distinct. Zhang Methods states source parameters were optimized against experimental results, so 13 V can at most become a `repository-withheld, preregistered cross-voltage evaluation`; it cannot be called an independent external holdout.

## Operating Rule

One bottleneck per round. Preserve all failed seeds and historical artifacts. Do not change frozen GT or post-hoc gates. Close every round through config, implementation, test, machine evidence, figure/table, report, claim matrix and manuscript wording. Use only `supported`, `qualified_supported`, `failed_but_informative`, or `forbidden`.
