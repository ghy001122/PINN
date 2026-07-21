# Submission go/no-go after E1F-R

Date: 2026-07-21

## Decision

**Immediate journal upload: NO-GO. Seven-day submission lock: GO.**

The scientific result set is now frozen. No further Qiu, M40/M40R, M37R,
public-inverse, or full-PINN rescue is authorized. The remaining work is a
bounded manuscript and submission-package task, not another research branch.

## Defensible paper identity

The manuscript is an **identifiability-gated physics-informed digital-twin
inverse study**. It is not a successful new full-PINN solver, a calibrated
real-device model, or an experimentally validated inverse method.

The three main contributions are:

1. a configured sparse-terminal hidden-field recovery boundary that motivates
   inverse-target reduction;
2. calibration-gated, synthetic rank-1 recovery of the effective thermal
   coordinate `gamma_sub`, including retained wide-mismatch failures;
3. a fail-closed evidence protocol separating implementation parity, physical
   conservation, source-equation checks, local-PDE transfer, neural fidelity,
   and external validation.

## Q2 risk assessment

The evidence is technically rigorous but the positive line is synthetic and
one-dimensional. No trained complete-PINN route passes, and neither public VO2
route supplies positive quantitative validation. Those omissions are direct
rejection risks for a device-physics journal expecting fabricated-device or
experimental validation. A Q2 submission remains rational only to a journal
whose current scope accepts numerical inverse methods, physics-informed
digital twins, and rigorous identifiability/limitation studies. Journal scope
and current quartile must be checked immediately before submission.

## Mandatory seven-day closeout

1. Merge the integrated manuscript with a verified bibliography and replace
   every uncited factual statement with a primary-source citation or remove it.
2. Freeze six main figures, supplementary failure figures, captions, and the
   claim-to-evidence table; visually inspect every exported panel.
3. Finish the supplementary methods/failure table, data/code availability,
   reproducibility statement, and reviewer-defense matrix.
4. Run one sentence-level claim audit against
   `docs/paper/final_claim_matrix.md`; any unsupported sentence is deleted or
   qualified, not rescued by new experiments.
5. Run one final full test/governance/clean-clone validation, lock artifact
   hashes, select the scope-compatible journal, format, and submit.

## Stop rule

If the selected journal requires positive experimental validation or a
successful trained PINN as a central contribution, change the journal target;
do not reopen failed science merely to satisfy that scope. Submission within a
month is controllable. Acceptance or publication within a month is not.
