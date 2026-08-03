# Exact Block-Condensation Stage A

## Conclusion

`GO_EXACT_BLOCK_CONDENSATION_PROTOTYPE_ONLY`

The frozen S2 backward-Euler equations admit an exact within-step static
condensation from 751 nonlinear unknowns to the 250 cell temperatures on the
L1 grid.  The simulation state is **not** globally temperature-only: previous
conductive state, branch memory, and device voltage remain propagated state.
No learned closure or lookup table is required.

This is a valid, bounded, non-voting numerical-method diagnostic.  It does not
show that a reduced solver converges, runs faster, avoids fallback, or passes a
12.5 V transition trajectory.  No nonlinear solve or trajectory was executed.

## Task Contract

- Base: `main@f274a7157bab2ec4b68c970d7fe1461c7899f43b`.
- Input: frozen NLS-v1 9 V trace, two frozen controller failure replays, and
  the production S2 fixed-point/residual equations.
- Allowed: residual-only evaluation on frozen states and trace statistics.
- Prohibited: solver modification, new 9/12.5 V trajectories, S0, Phase 2,
  PINN, equivalence, controller changes, and threshold relaxation.
- Gate: reconstructed auxiliary scaled residual at most `1e-12` while the
  future full residual and fixed-point-defect gates remain `1e-8`.
- Manuscript use: numerical-method design rationale or reviewer-defense
  provenance only; not a physical or PINN result.

## Exact Condensation

Let the previous state be

\[
(T^n,s^n,b^n,V_d^n),
\]

and prescribe a candidate temperature field \(T^{n+1}\).  With
\(r_b=\Delta t/\tau_b\), the frozen branch residual has the exact solution

\[
b^{n+1}=
\frac{b^n+r_b(h-c)}{1+r_b(h+c)},
\]

where the production activation functions \(h,c\) depend on
\((T^{n+1},T^n,\Delta t)\).  This retains hysteretic path dependence through
\(b^n\); it does not assume a single-valued \(b(T)\).

With \(r_s=\Delta t/\tau_s\), the conductive-state residual then gives

\[
s^{n+1}=
\frac{s^n+r_s s_{\mathrm{eq}}(T^{n+1},b^{n+1})}{1+r_s}.
\]

For the frozen conductivity field, the sheet electrical problem is linear in
device voltage.  If \(G_{\mathrm{dev}}\) is the unit-voltage terminal
conductance, the circuit residual gives

\[
V_d^{n+1}=
\frac{(C/\Delta t)V_d^n+V_{\mathrm{in}}/R_L}
{C/\Delta t+1/R_L+G_{\mathrm{dev}}(T^{n+1},s^{n+1})}.
\]

Substitution leaves only the thermal backward-Euler equation

\[
R_T(T^{n+1})=0
\]

as a nonlinear root problem.  A future implementation must reconstruct the
full state and re-evaluate the unchanged full scaled residual and fixed-point
defect at `1e-8`; a `1e-6` reconstructed-defect gate is rejected.

## Frozen-State Numerical Check

The production full residual was evaluated after algebraic reconstruction for
both frozen failure states and seven step sizes from 10 ns to 0.15625 ns.

| Quantity | Result |
| --- | ---: |
| Replay states | 2 |
| Step sizes | 7 |
| Residual rows | 14 |
| Maximum auxiliary scaled residual | `1.5139404881252134e-16` |
| Auxiliary diagnostic gate | `1e-12` |
| L1 full nonlinear unknowns | 751 |
| Temperature unknowns after condensation | 250 |
| Unknown-count reduction | `66.7111%` |

In every row, the conductive-state, branch, and circuit residuals vanish to
roundoff and the full residual norm equals the remaining temperature residual.
The nonzero temperature residual is expected because the frozen previous
temperature was used as a candidate; Stage A did not solve for a new state.

## Corrected NLS-v1 Causal Reading

The attachment's phrase “fallback causes timestep shrink” is not the actual
controller logic.  Rejected candidate bundles halve the interval.  An accepted
bundle using fallback keeps its interval, but it cannot enter the two-step easy
streak required for growth.  Therefore fallback suppresses growth rather than
directly shrinking the step.

The frozen standard 9 V T1 trace shows:

| Metric | Frozen result |
| --- | ---: |
| Accepted steps | 61,932 |
| Rejected bundles | 51 |
| Fallback steps | 61,383 (`99.1135%`) |
| Growth events | 45 |
| Median accepted step | `0.15625 ns` |
| Steps at the minimum | `68.9127%` |
| Steps at or below `0.3125 ns` | `93.3056%` |
| Coupled solves per accepted step | `3.00226` |
| Fallback Picard iterations | 2,323,142 |

Thus the observed cost explosion is consistent with three embedded paths per
accepted bundle, a fallback-dominated nonlinear solve, and growth suppression.
The trace does not prove Jacobian conditioning as the unique cause, nor does a
smaller \(\Delta t\) itself imply greater mathematical stiffness.

## Coverage And Claim Boundary

- Available: one incomplete frozen quiescent 9 V trace and two 9 V failure
  replays.
- Unavailable: a frozen 12.5 V transition trace suitable for Stage A
  performance comparison.
- Supported: exact algebraic condensability of the three auxiliary residual
  blocks under the frozen discrete equations.
- Qualified supported: fallback suppresses controller growth on the frozen
  NLS-v1 path; rejection alone performs interval halving.
- Failed but informative: the historical NLS-v1 qualification remains rejected
  by its frozen performance gate.
- Forbidden: reduced-solver speed/convergence, 12.5 V performance, S0/Phase 1
  PASS or FAIL, C01/PINN conclusions, or experimental validation.

`scientific_vote=false`, `formal_execution_count=0`, and
`nonlinear_or_trajectory_execution_count=0`.

## Next Highest-Value Task

Create a new, separately authorized solver identity implementing the exact
temperature-primary residual.  Its first bounded ladder should be:

1. unit tests proving full-state reconstruction and full-residual parity;
2. the two frozen replay states at unchanged `1e-8` residual/defect gates;
3. short 9 V and 12.5 V non-voting trajectories with matched NLS-v1 gates;
4. only if those pass, full standard/strict qualification.

The prototype must not use closure tables, learned reconstruction, relaxed
gates, a new controller, or any S0/PINN bypass.

## Artifacts And Validation

- Config: `configs/geophase_exact_block_condensation_stage_a.yaml`.
- Machine summary:
  `outputs/tables/geophase_exact_block_condensation_stage_a/stage_a_summary.json`.
- Residual table:
  `outputs/tables/geophase_exact_block_condensation_stage_a/exact_condensation_residuals.csv`.
- Time-step distribution:
  `outputs/tables/geophase_exact_block_condensation_stage_a/nls_v1_trace_dt_distribution.csv`.
- Focused Stage A test: `3 passed`; affected route regression: `29 passed`.
- Final governance: zero failed checks; tracked JSON: `306`; historical
  evidence manifest: all current checks passed.
- Frozen GT v1.1: `8/8` hashes unchanged; historical NLS/equivalence results
  remain unchanged.

The final commit SHA is reported in the task handoff because a commit cannot
contain its own SHA.
