# Active Phase

## Current Phase

`Q2 SCI delivery - Priority B P1 CV/mortar validity repair`

This is a bounded implementation-and-audit phase. It does not authorize changes to frozen GT v1.1, gate relaxation, a new manuscript core line, or a high-cost training campaign before the CPU diagnostic ladder passes.

## Manuscript Use

Produce either one valid neural-method result under the locked strict P1 gate or a precise limitation showing why the present control-volume/mortar formulation fails. The numerical forward solver remains authoritative; the neural model is an inverse/surrogate extension and cannot redefine the synthetic Ground Truth.

## Single Active Bottleneck

Priority B: repair P1 coordinate and face semantics, nondimensional residual scaling, and staged optimization in this order:

1. replace positional feature assumptions with a declared feature layout;
2. evaluate Dirichlet conditions and interface one-sided derivatives at physical boundary faces with consistent local/global coordinates;
3. define dimensionless PDE, interface, data, and phase residuals with auditable reference scales;
4. add CPU smoke and manufactured/behavioral tests before training;
5. run staged continuation only after the semantic and scaling diagnostics pass.

Required evidence chain:

```text
config -> implementation -> behavioral test -> JSON/CSV diagnostics -> figure/table -> report -> claim matrix -> manuscript sentence
```

## Locked P1 Gate

A positive P1 result requires all predeclared conditions:

- median `E_T <= 0.25`;
- median `E_m <= 0.25`;
- median interface residual `<= 0.05`;
- three-seed success rate `>= 0.70`;
- no direct field-anchor leakage may be described as sparse-port-only recovery;
- frozen GT hashes and mtimes remain unchanged.

Current baseline remains `failed_but_informative`: median `E_T=0.37563055753707886`, median `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success rate `0.0`.

## Interpretation Boundary

If the full gate passes, allowed wording is limited to a qualified, field-anchored CV/mortar neural surrogate under the declared synthetic protocol. If any gate fails, allowed wording is a numerical-method limitation or diagnostic boundary. Forbidden wording includes sparse-port-only multidomain PINN solved, arbitrary hidden-field recovery, terminal-only 2D inverse solved, experimental validation, and device-grade multiphysics reproduction.

## Locked Cross-Gate Context

- Priority A constrained `gamma_sub` evidence lock: completed; main positive claims are `supported` or `qualified_supported` and remain the manuscript mainline.
- P0: `qualified_supported` reduced physical semantics.
- P1: `failed_but_informative` baseline under repair.
- P2: `failed_but_informative`; thermal blocks, full-rank protocol selection, and coverage fail.
- P3: `qualified_supported` segmented-electrode y-z forward/local observability only; no field recovery.
- P4: blocked; positive STL/Fourier/F-SPS claims remain `forbidden` until P1 passes.

## Stop And Next Decision

Stop this phase after one gate-complete three-seed run or after the predeclared diagnostic ladder shows that the formulation remains invalid. The disposition is then one of: move the qualified result to manuscript, preserve a `failed_but_informative` boundary and continue once with a concrete repair, or stop P1 and activate Priority C. Do not add epochs merely to hide a semantic or scaling failure.