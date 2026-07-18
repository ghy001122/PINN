# M34 Optimization, Gradient, and Conservation-Ledger Contract Audit

## Decision

M34 is `failed_but_informative`. The zero-training/low-compute audit found a material mismatch between the optimizer described for M33 and the optimizer actually implemented, but the preregistered corrected-run preflight did not pass. No corrected training was authorized or executed.

The exact disposition is:

> `M33-v1 contract closed; no corrected run authorized`

The complete 1D PINN architecture remains a project and manuscript scaffold. This audit does not support trained forward fidelity, conservation fidelity, sensitivity fidelity, inverse readiness, or novelty for mixed formulations, augmented-Lagrangian methods, gradient alignment, or fixed-grid neural trajectory models.

## Execution identity and evidence boundary

- Baseline HEAD: `84bc5c5db2f5233b70bf97756734272c3eae36ca`.
- M34 preregistration/audit implementation commit: `ee83d73a16a219e02a19a5d7f6419dea3d224bb6`.
- M33 checkpoint SHA256: `6a1e0a09644dd8e5fc03135e1631db9847a84889e977d5082e341349d66786ce`.
- Audit execution count: one.
- Corrected training execution count: zero.
- Sealed 13 V access: false.
- Frozen GT v1.1 and the locked M33 checkpoint/config/equations remained unchanged.
- Evidence types:
  - optimizer classification and static contract: `implementation_fact`;
  - gradient, dtype, ledger, and representability results: `diagnostic_evidence`;
  - positive full-PINN scientific evidence: false.

Primary machine evidence is in:

- `outputs/tables/m34_contract_audit_summary.json`;
- `outputs/tables/m34_alm_toy_benchmark.csv`;
- `outputs/tables/m34_gradient_geometry.csv`;
- `outputs/tables/m34_ledger_reconciliation.csv`.

## A. Exact optimizer classification

M33-v1 used a group residual norm (r_g=\operatorname{RMS}(c_g)), a nonnegative scalar accumulator, unconditional geometric penalty growth, a multiplier cap of `100`, and global gradient-norm clipping at `100`:

\[
L_g=\lambda_g r_g+\frac{\rho_g}{2}r_g^2,
\qquad
\lambda_g\leftarrow \min(100,\lambda_g+\rho_g r_g).
\]

This is not a signed/vector equality-constrained augmented Lagrangian because it discards the sign and coordinate structure of (c_g). Its precise M34 classification is:

> `adaptive_group_norm_exact_penalty_with_nonnegative_scalar_accumulators`

The analytic toy audit separates primal feasibility from multiplier semantics:

| Toy case | Signed/vector ALM constraint error | Signed/vector dual error | Group-RMS constraint error | Group-RMS dual error | Quadratic-penalty constraint error |
| --- | ---: | ---: | ---: | ---: | ---: |
| positive dual | `1.19209e-7` | `1.19209e-7` | `1.19209e-7` | `1.19209e-7` | `1.0` |
| negative dual | `1.19209e-7` | `1.19209e-7` | `1.19209e-7` | `4.0` | `1.0` |
| shifted negative dual | `2.98023e-8` | `2.98023e-8` | `2.98023e-8` | `1.0` | `0.25` |

The group-RMS implementation can reach the toy primal solution while reporting the wrong multiplier sign. Therefore M33-v1 did not test faithful signed/vector ALM. It also cannot be used to infer that PECANN, ALM, or mixed PINNs are generally ineffective. The relevant primary-method boundaries are [PECANN](https://doi.org/10.1016/j.jcp.2022.111301) and [PECANN-CAPU](https://arxiv.org/abs/2508.15695).

## B. Gradient geometry, dtype, and clipping

### Coordinate derivative parity

The audit preregistered 48 coordinates: 12 each from the shared trunk, state head, heat-flux head, and defect-flux head. Forty-four were nonzero under the locked (g_{\min}=10^{-7}) rule.

| Module | Nonzero coordinates | Passed relative error `<=1e-4` | Failed |
| --- | ---: | ---: | ---: |
| shared trunk | 12 | 12 | 0 |
| state head | 12 | 8 | 4 |
| heat-flux head | 10 | 10 | 0 |
| defect-flux head | 10 | 0 | 10 |
| **Total** | **44** | **30** | **14** |

The maximum nonzero relative error was `0.0918561` in `defect_flux_head.weight[217]`, where autograd gave `-1.02552e-4` and centered finite difference gave `-9.31323e-5`.

Although 30 coordinates individually met the numerical threshold, the committed preregistration used a stricter stratified rule: at least 20 nonzero coordinates must exist, every sampled nonzero coordinate must pass, and every module must contribute a nonzero direction. The second clause failed. The machine field named `at_least_20_nonzero_gradient_directions_pass_parity` therefore records the stricter composite preregistered gate, not a claim that fewer than 20 individual coordinates passed. The rule was not relaxed after observing the result.

### Group scales and clipping

At the unchanged M33 final checkpoint in float64:

| Loss group | Constraint RMS | Gradient norm | Per-group effective ratio after norm-100 clipping |
| --- | ---: | ---: | ---: |
| conservation | `638.421` | `9.03770e8` | `1.10648e-7` |
| constitutive | `0.542782` | `2.30911` | `1.0` |
| phase/current | `2.41909` | `2.05682` | `1.0` |
| interface | `0.0105679` | `0.0358644` | `1.0` |
| ledgers | `0.0138817` | `4.88489e-5` | `1.0` |
| IC/BC | `3.34909e-17` | `2.30231e-35` | `1.0` |

The combined gradient norm was `5.49340e9`; global clipping to `100` produced an effective ratio of `1.82037e-8`. Thus the conservation group dominates the aggregate scale and global clipping suppresses the combined update by nearly eight orders of magnitude. The strongest material float64 directional conflict was constitutive versus phase/current, cosine `-0.162901`.

This is an implementation diagnosis, not evidence that loss conditioning or gradient alignment is a new contribution. Relevant primary baselines include [Rathore et al. on PINN loss conditioning](https://proceedings.mlr.press/v235/rathore24a.html) and [gradient-alignment analysis](https://arxiv.org/abs/2502.00604).

### Float32 versus float64

For conservation, constitutive, phase/current, interface, and ledger groups, float32-to-float64 gradient cosine was at least `0.999999994`; residual relative differences ranged from `8.60e-8` to `7.63e-6`. Float32 is therefore not the primary material distortion for the failing physics groups at this checkpoint.

IC/BC is the exception only because it is already satisfied to roundoff: float64 residual/gradient norms were `3.35e-17`/`2.30e-35`, while float32 produced `1.15e-8`/`5.29e-18`. Its large relative dtype ratio is a near-zero-denominator artifact, not evidence that IC/BC drives the failed trajectory.

## C. Conservation-ledger reconciliation

The same M33 checkpoint and state trajectory were evaluated on `32`, `64`, `96`, `128`, and `400` time points with a unified matrix, fixed physical scaling, interval-relative scaling, prefix-integral ledgers, an independent evaluator, and local-residual integration.

| Grid | Defect fixed-scale interval RMS | Energy fixed-scale interval RMS | Defect prefix max | Energy prefix max |
| ---: | ---: | ---: | ---: | ---: |
| 32 | `6.84338e-4` | `3.99940e-2` | `2.10021e-2` | `1.17949` |
| 96 (M33 training grid) | `2.23322e-4` | `1.30801e-2` | `2.10021e-2` | `1.18024` |
| 128 | `1.67053e-4` | `9.78555e-3` | `2.10021e-2` | `1.18028` |
| 400 | `5.31724e-5` | `3.11515e-3` | `2.10021e-2` | `1.18032` |

Deterministic reconciliation:

- Training and independent implementations agree under the unified fixed scale to a maximum absolute difference of `1.19440e-14`; a sign, unit, boundary, or duplicated-code implementation error is not supported.
- Historical interval-relative energy and defect metrics remain approximately `1`; the historical gate is preserved and was not relaxed.
- Fixed-scale per-interval RMS decreases with time-step size; the relative change from 128 to 400 points is approximately `2.14` when normalized by the finest-grid value. Time sampling therefore materially controls the apparent interval score.
- Prefix-integral failures remain stable at about `0.0210` defect and `1.1803` energy as the grid is refined. Finer sampling does not close global conservation.
- Prefix integrals reconstructed from the local residual match the direct state-flux prefix ledgers closely. This supports a genuine state-flux/local-residual incompatibility in the trained trajectory, not a ledger-only scoring bug.
- The configured low-activity denominator diagnostic is false; no interval exceeded the preregistered low-activity fraction criterion.

The pass/fail discrepancy is therefore multi-causal: normalization mismatch and time-step scaling make the explicit training ledger appear small, while a genuine cumulative state-flux/local-residual mismatch remains. Low-activity denominator pathology and sign/unit/boundary implementation error are not supported as primary causes.

## D. Representability and generalization boundary

The M33 network is exactly:

> a fixed-grid neural temporal trajectory with control-volume physics, not a continuous ((x,t,\mu)) PINN.

It does not establish cross-grid, cross-geometry, cross-material, or cross-waveform generalization.

The permitted 200-step hidden-field representability smoke reduced NRMSE95 as follows:

| Field | Before | After |
| --- | ---: | ---: |
| (T) | `1.71642` | `0.0708518` |
| (c_v) | `0.652767` | `0.0620211` |
| (m) | `0.428069` | `0.0805935` |

This run used frozen hidden-field labels and is explicitly `diagnostic_only=true`, `scientific_vote=false`. It shows finite local representational capacity under label supervision; it is neither data-free forward evidence nor inverse evidence and cannot open N1-N3.

## Corrected-run authorization

| Preregistered condition | Result |
| --- | --- |
| material M33 contract defect found | pass |
| corrected signed/vector toy problem | pass |
| stricter stratified nonzero-gradient parity | **fail** |
| unified ledger implementation parity | pass |
| corrected preflight all pass | **fail** |
| frozen GT/equations unchanged | pass |
| complete state/flux/electrical/interface contract retained | pass |
| parameter count within 3% | pass |
| no labels, sealed 13 V, or search | pass |

Because all nine conditions were required, no training was authorized. No corrected history, checkpoint, final summary, or comparison artifact exists.

## Claim decision and M33 reinterpretation

Still valid:

- The locked M33-v1 run failed its unchanged port, constitutive, PDE, field, interface-flux, independent global-ledger, and no-regression gates.
- Explicit flux heads and the M33 training schedule improved selected thermal/flux diagnostics but did not establish a reliable forward model.
- N1-N3 remain blocked and all positive sensitivity/inverse claims remain `forbidden`.

Must shrink:

- M33-v1 cannot permanently close every conceivable corrected full-PINN contract because it did not implement the declared signed/vector ALM.
- The defensible closure is contract-specific: `M33-v1 permanently closed`; the preregistered M34 corrected run was not authorized.
- No inference is permitted that mixed PINNs, PECANN, or ALM are generally ineffective.

Allowed manuscript use:

> The fixed-grid mixed state-flux neural trajectory failed the frozen forward gates. A zero-training audit found that the implemented optimizer was a nonnegative group-norm penalty rather than signed/vector ALM, but a stricter preregistered gradient-parity preflight also failed, so no corrected run was authorized. Trajectory agreement and small interval ledger penalties cannot substitute for cumulative conservation evidence.

Forbidden wording includes trained full-PINN fidelity, conservation-feasible PINN, cross-grid/material/waveform generalization, solver/PINN sensitivity fidelity, inverse readiness, or method novelty for mixed formulations, ALM, Fourier features, gradient alignment, or finite-volume PINNs.

## Progress, remaining Q2-SCI gap, and next single priority

M34 closes an important reviewer-defense ambiguity: it separates a real optimizer-contract defect from the unchanged scientific failure of the M33 trajectory, quantifies gradient domination/clipping, reconciles the two ledger implementations, and constrains the architecture's generalization semantics. It prevents both overclaiming M33 as a faithful ALM test and using that correction as an excuse for an unbounded neural-training search.

The project remains short of a Q2-SCI evidence package in two decisive ways:

1. the only safe inverse mainline is still calibration-gated, rank-1, frozen-synthetic `gamma_sub` evidence;
2. there is no provenance-locked multi-voltage public-data fit/evaluation bridge, and no trained full-PINN sensitivity or inverse evidence.

Because corrected training was not authorized, the next and only active research priority is preregistration of a public `9/11/15/17 V` repository-side fit with sealed `13 V` retained as a repository-withheld cross-voltage evaluation. This next phase must lock provenance, source/repository model roles, preprocessing, fit/calibration splits, multistart rules, solver convergence, metrics, thresholds, and the 13 V unsealing rule before any fit. It is not an authorization to access 13 V, fit new data, or resume neural search in M34.

## Validation

- Pre-audit focused M34 tests: `7 passed` in `3.18 s`.
- Result-lock focused tests: `12 passed in 6.93 s`.
- Governance audit: `pass_with_manual_review`, with no failed checks; all frozen-GT hashes are unchanged. The two manual items concern client rule loading and active-checkout mtime review, not hash failures.
- Exactly one final full-repository test run: `308 passed in 164.63 s`.
- Machine record: `outputs/tables/prompt34_final_validation.json`.
- No scientific audit or training was rerun for validation.
