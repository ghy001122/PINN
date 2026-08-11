# Q2 BranchConserve 2D Steady MVE v1

> **Lifecycle notice (2026-08-11):** This is a frozen historical contract/snapshot, not current authorization. Original preregistration and status wording is retained below for provenance; use the applicable `AGENTS.md`, `docs/research_strategy/active_phase.md`, `PROJECT_STATE.md`, and `NEXT_ACTIONS.md` for current status and queue.

## Disposition and manuscript destination

This versioned route is a two-batch attempt to establish a branch-resolved
steady 2.5D forward judge before any new PINN work. Batch 1 is a non-voting
implementation and cost pilot. It cannot validate S2 physics, establish
rank-2 sensitivity, or authorize Batch 2.

The manuscript destination, if later gates pass, is a steady major-branch
forward model with independently reconstructed current, power, and thermal
ledgers, followed by a two-parameter minimum-viable sensitivity experiment.
All project-generated results retain the evidence identity
`literature-guided synthetic numerical digital-twin evidence`.

## Frozen problem

The resolved state is the Qiu-inspired VO2 x-y plane. The steady equations are

\[
\nabla\!\cdot J=0,\quad J=-t_v\sigma_b(T)\nabla\phi,
\]

\[
q_T=-K_A\nabla T,\qquad
\nabla\!\cdot q_T-p_J+g_z(T-T_0)=0,
\]

with the source-load identity

\[
V_s=V_d+R_LI.
\]

The left and right exterior boundary faces impose \(\phi=V_d\) and
\(\phi=0\), respectively. All other electrical exterior faces are insulating;
all thermal exterior faces are adiabatic. Contact masks modify material
coefficients but do not turn interior contact-covered cells into Dirichlet
nodes. The S2 coefficient \(K_A\) is a sheet conductance and is never multiplied
by device thickness a second time.

Major branches are fixed metadata: heating uses \(b=+1\), cooling uses
\(b=-1\). The state \(s\) is an effective conductive-state coordinate, not a
measured metallic fraction. No branch-switching or minor-loop dynamics are
present.

## Unique nonlinear identity

At fixed \(V_d\), the only nonlinear unknown is

\[
z_i=(T_i-T_0)/T_{\rm ref}.
\]

Every residual call reconstructs \(s\) and \(\sigma\), performs a conservative
electrical subsolve, reconstructs electrical face currents and Joule power,
and returns the complete control-volume integrated thermal residual. The sole
production method is the preregistered damped Newton--Krylov method in
[`q2_branchconserve_2d_steady_mve_v1.yaml`](../../configs/q2_branchconserve_2d_steady_mve_v1.yaml).
It has fixed Jv, residual, LGMRES, iteration, and Armijo budgets; it has no
fallback solver. The preconditioner is the sheet thermal operator plus the
vertical sink with the Joule derivative frozen.

Pseudo-arclength is the scaled augmented form

\[
\begin{bmatrix}\widehat R_T(y)\\t^\top(y-y_{\rm pred})\end{bmatrix}=0,
\qquad y=[z,V_d/V_{\rm ref}],
\]

and is eligible only when fixed-\(V_d\) parameterization fails at its minimum
step and the registered \(V_d\)-tangent condition holds. A reversal of
\(dV_s/dV_d\) is not a trigger.

## Reachability and stability

`reachable` means the continuous component obtained from the low heating or
high cooling endpoint while source voltage moves monotonically in the
prescribed direction and every intervening point is stable. A marginal,
unstable, invalid, or discontinuous gap permanently ends reachability. Later
stable pseudo-arclength points may remain in the atlas but cannot vote.

Local stability is branch-conditioned. With

\[
u=[T_1,\ldots,T_N,V_d],\quad
M=\operatorname{diag}(C_{A,i}A_i,C_{\rm ext}),
\]

the code computes the six rightmost eigenpairs of
\(B=S^{-1}M^{-1}(\partial f/\partial u)S\) using three deterministic starts.
Every eigenpair and the repeated spectra must pass the residual and
consistency gates. Only

\[
\max\Re\lambda\le-\tau_\lambda,
\quad
\tau_\lambda=\max(10^{-3}/\tau_\theta,10\max_i\delta_{\lambda,i})
\]

is stable. Dense L4 spectra are forbidden.

## Batch 1 task contract

- **Inputs:** hash-locked source-corrected S2 configuration and existing
  conservative electrical/S2 face operators.
- **Allowed outputs:** B0 implementation, focused tests, one nominal L1
  fixed-source smoke, nominal L1 heating/cooling atlas and cost pilot, their
  common reachable source interval, and at most one 30-minute nominal L2
  equilibrium-plus-stability cost sentinel.
- **Prohibited:** LU/RD execution, B1b, finite-difference Jacobians, O1--O4,
  B2, dynamic solvers/controllers, S0/equivalence reruns, Phase 2, and PINN.
- **Success gate:** both L1 branches produce a stable-reachable common interval
  containing at least five preregistered candidate source voltages, and the L2
  sentinel completes within its hard cap.
- **Failure route:** exactly one of the five Batch 1 terminal dispositions in
  the YAML; no automatic Batch 2 execution.
- **Budget:** at most 4 aggregate CPU-hours and 4 wall-hours, with no individual
  batch over 30 minutes.

Large source fields and fluxes are atomically stored under
`data/processed/q2_branchconserve_2d_steady_mve_v1/<run_id>/equilibria/` and
hash-indexed by compact manifests. Aggregation must use those persisted source
records and may not silently rerun a solver.
