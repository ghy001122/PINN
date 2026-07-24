# GeoPhase-OQ-PINN Execution Contract

## Status And Authority

This document converts the revised 2026-07-24 brainstorm into the versioned,
claim-gated research contract for the active repository. It is a research
design, not evidence that the proposed method works. Current authorization is
limited to G0/E0 in `docs/research_strategy/active_phase.md`.

The selected candidate paper identity is:

> **GeoPhase-OQ-PINN: geometry-aware physics-informed learning and
> observation-quotient inversion for hysteretic phase-transition neuristors.**

The defensible scientific hypothesis is that a PINN for phase-transition
devices must address three coupled obstacles: real in-plane geometry,
transition-localized stiffness, and non-unique terminal observation. A positive
claim requires independent-solver field and ledger fidelity first, followed by
PINN sensitivity fidelity and fresh-case inverse/refusal evidence.

## Evidence Boundary

- Primary device: Qiu-inspired coplanar VO2/Ti/Au/Al2O3 thermal neuristor.
- Auxiliary device: Chen-inspired SnSe/NbO2 vertical threshold switch.
- Project evidence type: `literature_guided_solver_generated_synthetic_numerical_digital_twin`.
- Literature geometry, trends, fitted parameters, and digitized curves remain
  external-literature evidence and retain their provenance labels.
- The project has no self-generated measurements and cannot claim experimental
  validation, exact author-code reproduction, or calibrated real-device fields.
- `s` is an **effective conductive-state coordinate**, not a measured metallic
  phase volume fraction.
- VO2 and NbO2 share framework interfaces, not constitutive laws or parameters.

## Live-Workspace Migration Map

### Reuse without scientific-status transfer

| Existing asset | Permitted use | Not permitted |
| --- | --- | --- |
| `configs/m40_qiu_vo2_real_device_2d.yaml`, `qiu_vo2_device.py` | Qiu geometry, circuit, provenance roles, contact uncertainty | inheriting M40/M40R x-z convergence or quantitative device status |
| `qiu_vo2_2d_fvm.py`, `m40r_qiu_e0_repair.py` | conservative face-flux, RC, ledger, and fixed-grid comparison patterns | treating the old solver as the new x-y/K-state reference |
| `vo2_constitutive.py`, `vo2_thermal_neuristor.py` | candidate white-box VO2 components after unit/state audit | exact Qiu hysteresis or measured material truth |
| `multilayer_sandwich.py`, `oasis_components.py` | material separation, interface, CV, and baseline patterns | positive OASIS/2.5D/PINN evidence transfer |
| `network.py`, `mixed_flux_pinn.py` | Fourier and mixed-form baselines/components | localized-expert novelty or trained success |
| `identifiability.py` | SVD, rank, bootstrap, and principal-angle utilities | reusing failed historical SID/EC-OQ votes as new evidence |
| frozen GT and constrained `gamma_sub` evidence | historical baseline, motivation, reviewer defense | final device structure or positive GeoPhase result |

### Missing in live `main`

The following must be implemented and cannot be described as existing:

- an x-y Qiu-inspired 2.5D reference solver;
- passive local K-state vertical thermal memory and higher-order reference;
- transition-localized smooth/spectral/interface experts;
- joint phase-sharpness/electrothermal-feedback homotopy;
- geometry-conditioned GeoPhase forward training;
- PINN--solver sensitivity-fidelity regularization;
- event-canonicalized observation-quotient inverse and refusal;
- Chen-inspired SnSe/NbO2 cross-model run.

### Historical Closure Versus New Authorization

Historical stop decisions remain binding to their named contracts: do not rerun
M44, M40/M40R active-transient rescue, the old complete-1D N0/M33 training
routes, or the D0/M35--M37R public-source chain as though their budgets and
gates had reset. Their artifacts remain historical and cannot be relabeled as
GeoPhase evidence.

Those route-specific closures do **not** permanently prohibit the distinct x-y
GeoPhase reference, complete or hybrid GeoPhase PINN, transition-localized
homotopy, geometry holdouts, or solver-gated observation-quotient program.
Those are new scientific objects authorized sequentially by G0--G5 after their
upstream gates pass.

Full 3D, full Landau/phase-field modeling, VO2 oxygen-vacancy dynamics, full
Seiler-style STL, and terminal-only arbitrary hidden-field recovery are outside
the selected G0--G5 critical path. They are unestablished and not currently
authorized, but this is not a universal research ban: a future active phase may
open a bounded, preregistered audit without inheriting any positive status.

## Additive Workspace Structure

Do not move the large historical tree. New work is isolated by the `geophase`
prefix inside the existing responsibility-based subtrees:

```text
configs/geophase_e0_2p5d_reference.yaml
src/pinnpcm/physics/geophase_2p5d.py
src/pinnpcm/solvers/geophase_2p5d_fvm.py
src/pinnpcm/pinn/geophase_network.py
src/pinnpcm/pinn/geophase_residuals.py
src/pinnpcm/pinn/geophase_training.py
scripts/run_geophase_e0_reference.py
scripts/train_geophase_forward.py
scripts/audit_geophase_observation_quotient.py
tests/test_geophase_2p5d_*.py
tests/test_geophase_pinn_*.py
outputs/tables/geophase_*/
outputs/figures/geophase_*/
```

Files are created only when their phase is authorized; empty placeholders are
not evidence. Large arrays and checkpoints remain ignored under
`data/processed/` or `outputs/`.

## Gated Research Chain

### G0/E0 - independent 2.5D reference

Question: can a conservative x-y device plane plus passive vertical thermal
memory form a numerically trustworthy judge?

Required evidence:

- manufactured electrical and thermal solutions;
- finite-contact current integration and current conservation;
- full active-plane plus K-state energy ledger;
- independent spatial and temporal fine-pair convergence;
- passive/positive K-state poles, capacities, and conductances;
- K=2/3 reduction against a higher-order vertical reference;
- zero-drive, uniform-field, decoupled-device, and strong-coupling limits;
- one formal, budget-locked run after preflights.

Failure blocks every later PINN claim. Passing conservation without convergence
does not authorize G1.

### G1/E1 - positive forward GeoPhase PINN

Predict:

\[
\phi(x,y,t),\quad T(x,y,t),\quad s(x,y,t),\quad
b(x,y,t),\quad z_1(x,y,t),\ldots,z_K(x,y,t),\quad I_p(t).
\]

Compare data-free PINN, sparse-anchor hybrid PINN, and pure supervised
surrogate identities. Solver and PINN must use different numerical
representations. A positive result requires field, port, event, interface, and
energy-ledger gates jointly; a hybrid result must be named `hybrid PINN`.

### G2/E2 - phase-localized architecture and stiffness training

Candidate method:

\[
u_\theta=u_{\mathrm{smooth}}+
g_{\mathrm{tr}}u_{\mathrm{spectral}}+
g_{\mathrm{int}}u_{\mathrm{interface}},
\qquad
g_{\mathrm{tr}}=\exp\!\left[-
\left(\frac{T_{\mathrm{coarse}}-T_c}{\delta_T}\right)^2\right].
\]

Training follows two physical axes:

\[
w_T^{(0)}>\cdots>w_T^{(*)},\qquad
0<\lambda_J^{(0)}<\cdots<\lambda_J^{(*)}=1.
\]

Mandatory baselines are vanilla PINN, global Fourier PINN, homotopy only,
localized expert only, domain-decomposed PINN/FBPINN-lite, hybrid PINN without
the proposed modules, and pure MLP/TCN surrogate. Budgets, anchors, seeds,
stopping rules, and cases must match. Report success rate and every failed seed.
Do not call the homotopy full STL.

### G3/E3 - within-family geometry generalization

Lock train/validation/test splits over VO2 length, width, electrode overlap,
device separation, vertical thermal parameters, load/capacitance, and drive
protocol. The full network cannot be refit on held-out cases. Report joint OOD
and each factor separately; pooled averages may not hide a failed factor.

### G4/E4-E5 - observation quotient, sensitivity fidelity, and refusal

The solver-first Jacobian is

\[
J_{p,b}=\frac{\partial \mathcal O_{p,b}[u(\theta)]}{\partial\theta},
\qquad
J_{p,b}=U\Sigma V^\top,
\qquad
q_{p,b}=V_r^\top\theta.
\]

Canonicalize switching events before differentiation so time shifts are not
silently interpreted as material directions. Test derivative step convergence,
rank stability, singular spectra, principal angles, and protocol null-space
intersections. Then compare `J_PINN` with `J_solver`; trajectory accuracy alone
cannot open the inverse.

If stable rank/rotation is absent, downgrade to a fixed low-rank quotient. If
sensitivity fidelity fails, the PINN may be used only as a forward surrogate.
Any inverse must use fresh nonlinear/noisy cases, compare raw-parameter and
direct-solver inverse baselines, and output an abstention/refusal score.

### G5/E6 - material-specific cross-model numerical validation

Replace the VO2 IMT/hysteresis kernel with a Chen-inspired SnSe/NbO2
Poole--Frenkel/electrothermal-runaway kernel. Reuse only geometry/protocol
encoding, thermal-memory interfaces, port/circuit layers, training machinery,
and identifiability workflow. Test literature-consistent trend directions for
thermal-barrier changes. Name the evidence `cross-model numerical validation`,
not experiment, calibration, or zero-shot generalization.

## Predeclared Claim Routes

| Route | Minimum evidence | Allowed identity |
| --- | --- | --- |
| Strong | G0-G4 pass; localized expert/homotopy stable; quotient/refusal beats raw inverse | GeoPhase-OQ-PINN |
| Robust | G0-G3 pass; quotient is fixed low rank or inverse contribution is limited | GeoPhase-PINN |
| Hybrid minimum | data-free G1 fails but sparse-anchor hybrid G1-G3 passes; inverse remains a boundary | hybrid geometry-aware physics-informed learning |
| Stop | no positive forward/generalization PINN passes | no new positive PINN manuscript; preserve failure evidence |

The route is chosen from results; titles and contribution language cannot be
locked in advance.

## Core Success Gates

These are preregistered design thresholds, not achieved metrics:

- port quantities: median relative error `<=0.05`, 95th percentile `<=0.10`;
- phase-event time: median relative error `<=0.05`;
- energy-ledger relative residual `<=0.01`;
- interface-flux mismatch improvement `>=30%` over the matched baseline;
- sharp-regime success-rate gain `>=0.30` absolute over vanilla PINN;
- geometry-OOD error improvement `>=20%` over the pure surrogate;
- identifiable-region quotient median error `<=0.10`;
- non-identifiable-case refusal AUPRC `>=0.80`;
- maximum principal angle between leading PINN/solver sensitivity subspaces
  `<=15 degrees`.

Phase-specific configs may add stricter gates but may not relax these after
observing formal results.

## Synthetic-Data Leakage And Inverse-Crime Controls

1. Independent solver and PINN residual use different numerical expressions.
2. Sparse field anchors, when used, are declared and separated from test fields.
3. Geometry, protocol, parameter, and seed splits are locked before training.
4. Noise levels are 0%, 1%, 3%, and 5%, with time jitter and port offsets.
5. Fresh tests include declared missing physics such as temperature-dependent
   conductivity, interface resistance, contact drift, or extra thermal scale.
6. Literature fit and holdout curves are separated before any optimization.
7. Worst cases, failed seeds, refusal errors, and out-of-domain cases are kept.
8. Digitized curves remain `derived` external-literature data.

## Current-Route Exclusions And Claim Stops

These are phase and route boundaries, not universal bans on future research.

- no M44 repair or old complete heterogeneous-3D rerun inside G0--G5; any new
  3D study requires a separate phase and cannot inherit M44 status;
- no VO2 vacancy PDE or free `log_sigma` shortcut silently substituted into
  the GeoPhase mainline;
- no full Landau-Ginzburg/LLP/minor-loop dependency on the current critical
  path; a separately authorized bounded audit remains possible;
- no NeuroPINN/VSN/QGAN/full multilevel FBPINN promoted as the main
  contribution without a later matched-budget phase;
- no claim of terminal-only arbitrary 2D hidden-field recovery; a future
  observability audit must remain claim-gated and may end negatively;
- no larger epoch budget used to conceal non-identifiability or failed ledgers;
- no `first`, universal superiority, exact reproduction, or experimental
  validation wording without direct evidence.
