# Post-d23a576 Research Decision Audit

## Purpose And Manuscript Use

This audit reconciles the external stage-review and brainstorm document against current Git evidence at base SHA `e2e2669adfd66aacefacfbfceafcdfc18eafbbee`. Its manuscript use is to lock the defensible 1D constrained `gamma_sub` line, route v10 evidence to supplementary claims, and prevent candidate innovations from being described as completed results.

Evidence type: synthetic numerical digital-twin code, tables, tests, and documentation. No measured experimental validation is present.

## 1. Repository Anchor

- Reviewed branch: `main`.
- Base HEAD before this round: `e2e2669adfd66aacefacfbfceafcdfc18eafbbee`.
- Relation to review anchor: four documented governance/handoff commits after `d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`; no later experimental-code advance before this round.
- Worktree before this round: clean.
- Final evidence-lock commit SHA: `d1121e16fa5015a297da468e3e6f0504b9e97d17`.
- Frozen GT v1.1: read-only; pre-task SHA-256 hashes and mtimes were recorded and will be checked again at round close.

## 2. Key Files Introduced Or Changed At d23a576

The v10 commit changed the following evidence-bearing groups:

- Configs: `configs/active_protocol_design_v3.yaml`, `configs/cv_multidomain_oasis_v10.yaml`.
- Forward/physics implementation: `src/pinnpcm/physics/multilayer_sandwich.py`, `src/pinnpcm/physics/multiterminal_yz.py`, `src/pinnpcm/pinn/oasis_components.py`.
- Audit/training scripts: `scripts/audit_physical_semantics_v10.py`, `scripts/train_cv_multidomain_oasis_v10.py`, `scripts/audit_active_protocol_design_v3.py`, `scripts/audit_multiterminal_yz_forward_v10.py`, `scripts/audit_oasis_algorithms_v10.py`, `scripts/audit_oasis_generalization_v10.py`.
- Tests: `tests/test_physical_semantics_v10.py`, `tests/test_cv_multidomain_oasis_v10.py`, `tests/test_active_protocol_design_v3.py`, `tests/test_multiterminal_yz_v10.py`, `tests/test_oasis_v10_gates.py`.
- Machine-readable outputs: `physical_semantics_v10_{summary.json,cases.csv}`, `cv_multidomain_oasis_{training_summary.json,cases.csv}`, `active_protocol_design_v3_summary.json`, `sequential_terminal_inverse_v3_summary.json`, `multiterminal_yz_forward_summary.json`, `oasis_algorithm_gate_v10_summary.json`, and `oasis_generalization_v10_summary.json`.
- Equation/report/claim surfaces: `docs/method_equations.md`, `docs/codex_reports/cv_multidomain_oasis_and_inverse_repair_v10_report.md`, `docs/manuscript/reviewer_defense_matrix.md`, `docs/paper/claim_gate_resolution_matrix.md`, and `docs/paper/final_claim_matrix.md`.
- Registries/state: `CODEX_CONTEXT.md`, `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, `DATASET_REGISTRY.md`, `EXPERIMENT_REGISTRY.md`, `FIGURE_REGISTRY.md`, and `RESEARCH_LOG.md`.

## 3. P0-P4 Code Gates And Raw-Artifact Agreement

| Gate | Code definition | Recomputed/raw check | Status | Allowed interpretation |
| --- | --- | --- | --- | --- |
| P0 physical semantics | all cases finite; NbO2 PF/electrothermal activation rate at least `2/3`; normalized VO2 activation at least `2/3` | profile CSV gives VO2 normalized `3/3`, VO2 literature-shape `3/3`, NbO2 `2/3`; topology and RC flags agree with the JSON | `qualified_supported` | Reduced topology/mechanism implementation and shape-prior activation only |
| P1 CV multidomain training | median `E_T <= 0.25`, median `E_m <= 0.25`, median interface residual `<=0.05`, three-seed success rate `>=0.70` | full-mortar CSV rows give medians `0.3756306`, `0.0681153`, `106.1546`, success `0/3`; summary agrees | `failed_but_informative` | Scaling, boundary-face, coordinate, and interface optimization failure boundary |
| P2 active inverse | every material block median error `<=0.20`, success `>=0.70`, 90% coverage `>=0.80`; design reports full rank | NbO2 thermal error `1.3130` and coverage `0.5333` fail; VO2 thermal success `0.6` fails; selected ranks are `2/4` and `1/5` | `failed_but_informative` | Local block-specific recoverability only |
| P3 segmented y-z forward | uniform-series relative error `<=0.05`, current balance, direct flux-integrated terminals; no field inverse | uniform error `7.67e-12`, current-balance errors below `1e-12`, local rank `1->3` | `qualified_supported` | Forward/current integration and low-dimensional local observability only |
| P4 STL/Fourier/F-SPS | positive experiment authorization requires `P1_gate_passed=true` | P1 is false; all three algorithm statuses are `not_run_blocked` and positive claim is false | `forbidden` | No positive v10 algorithm claim |

The v10 report is consistent with the authoritative JSON/CSV for the quoted P0-P4 metrics. Test success is engineering evidence only and does not upgrade the scientific gates.

## 4. P1 Feature Coordinates, Hard Boundary Transform, And Interface Derivatives

`_grid_features` constructs ten features:

1. local layer coordinate `z_local` (cell-center value `0.5` in the training grid);
2. normalized lateral coordinate `y`;
3. normalized time;
4. normalized global stack layer-center coordinate `z_global`;
5. log layer thickness;
6. log thermal conductivity;
7. log volumetric heat capacity;
8. combined neighboring electrical contact-resistance feature;
9. combined neighboring thermal-boundary-resistance feature;
10. normalized layer index.

The hard potential transform uses feature 4 (`z_global`):

\[
\phi=(1-z_{\mathrm{global}})V+z_{\mathrm{global}}(1-z_{\mathrm{global}})\phi_{\mathrm{raw}}.
\]

The interface routine instead perturbs feature 1 (`z_local`) from `1` to `1-10^{-3}` on the left and from `0` to `10^{-3}` on the right. During those one-sided differences, the hard-transform global coordinate remains the corresponding layer-center value rather than the physical interface coordinate. Therefore the derivative is taken with respect to a local coordinate while the hard envelope is frozen at a different global coordinate. Boundary conditions are imposed through a cell-center global transform rather than explicit boundary-face evaluation.

Disposition: `failed_but_informative`. This is a concrete Priority B repair target; it is not a reason to add epochs.

## 5. Field-Anchor Dependence

The P1 anchor mask is `anchor_mask[::3, :, ::2] = True`. For the configured `nt=12`, all layers, and `ny=5`, it directly anchors 4 time slices and 3 lateral positions: 20% of the full `T` grid. The PCM `m` loss uses the same time/lateral mask and therefore anchors 20% of the PCM state grid.

Allowed label: field-anchored CV physics-regularized neural surrogate.

Forbidden label: sparse-port-only multidomain PINN solver.

## 6. P2 Inverse Boundary And Protocol-Rank Ordering

The implemented estimator solves, block by block,

\[
\Delta\theta=(J^\top J+10^{-4}I)^{-1}J^\top\Delta y,
\]

and constructs 90% intervals from a local Gaussian covariance approximation. It is local linearized recovery near the nominal prior, not nonlinear inversion over the full prior domain and not Bayesian posterior inference.

The design code first filters only for safety/activation, chooses the maximum D/E-optimal candidate, then computes `selected_full_rank`. `run_active_protocol_design_v3` nevertheless passes the selected protocol to `_linearized_inverse` even when `design_gate_passed=false`. Thus the rank gate is reported after selection but does not reject the candidate before inverse. This matches the review document's criticism and remains a Priority C blocker.

## 7. P3 Rank Basis

The multi-terminal rank is not a field-space rank. The conductivity field is parameterized by a Gaussian lateral PCM profile with

\[
\theta=(\text{center},\text{width},\text{contrast}).
\]

Finite differences of these three coefficients form the terminal-current Jacobian. Rank `1->3` therefore means improved local observability of this three-parameter profile basis only. Arbitrary pixel-wise, low-rank spatiotemporal, and full hidden-field recovery were not run.

## 8. OOD Preflight Split

The generalization audit contains 48 synthetic forward cases:

\[
2\ \text{materials}\times2\ \text{stacks}\times3\ \text{geometries}\times2\ \text{pulses}\times2\ \text{interface scales}.
\]

All cases use seed `2026`. A ridge response model maps five hand-coded features to log-transformed `max_delta_T`, conductance ratio, and maximum absolute current. Each factor is held out in turn. This is a leave-one-factor response preflight, not trained OASIS neural-operator generalization. Geometry holdouts have moderate normalized error; interface/pulse/stack holdouts degrade; cross-material errors are about `59` and `440`.

Status: `failed_but_informative`. The result supports within-family validation and material-specific constitutive kernels, not universal transfer.

## 9. Current Claim Ledger

The authoritative detailed ledger is generated at `docs/paper/final_claim_matrix.md` and `docs/paper/gamma_sub_evidence_lock.md`.

- `supported`: configured sparse-port full-field recovery boundary; Figure 1 evidence.
- `qualified_supported`: constrained `gamma_sub`, calibration gate, conditional robustness, protocol-after-calibration, P0 reduced semantics, and P3 local forward/observability.
- `failed_but_informative`: P1 strict neural training, P2 local active inverse, OOD preflight, and the broad protocol stress audit as a main-figure candidate.
- `forbidden`: completed experimental/external validation, full STL/Seiler reproduction, universal Fourier/F-SPS superiority, arbitrary terminal-only 2D field recovery, and device-grade FEM/3D claims.

No non-standard status such as `qualified_supported as implementation` is allowed in the generated current matrix.

## 10. Selective Integration Of Brainstorm Candidates

Scores below are heuristic planning scores from 1 (low) to 5 (high), not experimental measurements.

| Rank | Candidate | Scientific value | Cost | Evidence gap | One-month feasibility | Manuscript relevance | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Recoverability phase map and claim ladder | 5 | 2 | 2 | 5 | 5 | Adopt now; it organizes existing positive and negative `gamma_sub` evidence |
| 2 | Numerical-forward / neural-inverse division of labor | 5 | 1 | 1 | 5 | 5 | Adopt now as manuscript and architecture principle |
| 3 | Physical residual scaling plus staged continuation | 5 | 3 | 3 | 4 | 5 | Priority B; directly targets P1 failure |
| 4 | CV-cPINN interface repair | 5 | 4 | 4 | 3 | 4 | Priority B, but only after coordinate/scale definitions are repaired |
| 5 | Identifiability-gated hierarchical inverse | 5 | 4 | 4 | 3 | 5 | Priority C; rank must gate released parameter blocks before inverse |
| 6 | Time-windowed active design | 4 | 3 | 4 | 4 | 4 | Priority C; pair with full-rank material-specific protocol combinations |
| 7 | Provenance-backed external curve anchor | 5 | 3 | 5 | 3 | 5 | Priority D Must-have; proceed only with clear provenance |
| 8 | Material-mechanism routing | 4 | 3 | 3 | 4 | 4 | Partly adopted in P0/P2; retain for within-family extension |
| 9 | Low-rank PDE-constrained 2D recovery | 5 | 5 | 5 | 2 | 3 | Defer to Priority E after dynamic forward/observability evidence |
| 10 | Electrical-thermal dual-graph neural encoder | 4 | 5 | 5 | 2 | 3 | Defer; topology semantics are useful now, a neural encoder is not yet justified |

The proposal to reuse one declared simulator matrix for sensitivity, rank, protocol, uncertainty, OOD, and phase-map analysis is accepted only with explicit case-reuse provenance. Candidate innovations remain exploratory until their own gates pass.

## 11. Priority A Evidence-Lock Decision

This round implements a declarative evidence chain in `configs/gamma_sub_evidence_lock.yaml`, built by `scripts/build_gamma_sub_evidence_lock.py` and checked by `tests/test_gamma_sub_evidence_lock.py`. It generates:

- `outputs/tables/gamma_sub_evidence_lock_summary.json`;
- `docs/paper/gamma_sub_evidence_lock.md`;
- `docs/paper/final_claim_matrix.md`;
- `docs/paper/final_figure_list.md`.

The pre-lock cumulative claim matrix remains available through Git history as `git show e2e2669:docs/paper/final_claim_matrix.md`.

Figure 5 is resolved unambiguously: the 720-case calibrated sequential validation is the primary result (`success_rate=1.0`, `max_error=0.1111`), while the 2400-case robustness stress audit is supplementary because its own JSON sets `whether_ready_as_main_figure=false`.

The reviewer-defense generator now emits the current 17-question matrix from code, accepts an output path, and its test writes only to `tmp_path`; a passing test no longer rewrites the tracked manuscript file.

## 12. Validation And Frozen-GT Check

- Evidence-lock, main-figure, submission-figure, and reviewer-defense builders completed successfully.
- Targeted tests passed before status synchronization: `8 passed in 65.45s`; the final post-synchronization governance/evidence regression also passed: `8 passed in 43.37s`.
- Full CPU suite passed: `187 passed in 336.70s`.
- Re-running the generators produced identical hashes for the generated Markdown/JSON artifacts (`GENERATORS_IDEMPOTENT=True`).
- Figure 5 received visual QA after changing it to show both success rate and maximum relative error; the 720-case calibrated protocol is visible rather than hidden by zero medians.
- `git diff --check` reported no whitespace errors.
- Pre/post SHA-256 hashes and mtimes for both frozen acceptance configs, the frozen acceptance report, manifest, and four frozen NPZ arrays are identical. Frozen GT v1.1 was not modified.

## 13. Round Disposition

- Actual work: absorbed the external review, audited P0-P4/OOD semantics against code and raw artifacts, locked the constrained `gamma_sub` evidence chain, repaired the reviewer-defense test side effect, corrected Figure 5 routing/visualization, and synchronized the manuscript-facing claim surfaces.
- Distance-to-goal change: the Priority A reproduction-command/evidence-map gap is closed; full manuscript assembly and the external quantitative anchor remain open.
- Claim changes: no scientific claim was upgraded or downgraded by documentation assembly. The current matrix now uses only the four allowed statuses and makes the pre-existing boundaries explicit.
- New blockers: none. Confirmed blockers are P1 coordinate/face/scaling failure, P2 rank/thermal coverage failure, absent external provenance-backed evidence, and non-geometric OOD failure.
- Next single priority: Priority B P1 coordinate/face semantics, nondimensional CV/mortar scaling, and staged optimization under the unchanged strict gate.
- Disposition: move the locked Priority A evidence to manuscript and continue with Priority B in the next research round.
