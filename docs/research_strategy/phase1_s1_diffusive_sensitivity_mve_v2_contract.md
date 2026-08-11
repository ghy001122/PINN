# Phase 1-v2 S1 diffusive sensitivity MVE amendment

> **Lifecycle notice (2026-08-11):** This is a frozen historical contract/snapshot, not current authorization. Original preregistration and status wording is retained below for provenance; use the applicable `AGENTS.md`, `docs/research_strategy/active_phase.md`, `PROJECT_STATE.md`, and `NEXT_ACTIONS.md` for current status and queue.

Status: preregistered amendment; no S1 numerical fit or response evaluation is
authorized until the amendment commit is pushed.

This document amends only the optional, non-blocking S1 sensitivity contract.
It does not change the nominal Phase 1-v2 S2 model, the 63-item future formal
inventory, any S2 gate, or the formal execution count. The original S1 v1 YAML
and its hash remain historical evidence of the pre-implementation contract.

## Why an amendment is required

A read-only implementation review found three contract-level defects before
any S1 fitting was run:

1. an unsuccessful or infeasible optimizer result could still yield a model
   object and be passed by response-only metrics;
2. the proposed Cauer ledger reconstructed derivatives from the same fluxes it
   then balanced, making the residual algebraically self-cancelling; and
3. the analytic step and pulse references used an unregistered modal
   truncation.

The v2 amendment therefore locks candidate eligibility, numerical-safety
bounds, analytic-reference convergence, the Cauer port topology, and an
independent backward-Euler ledger before numerical fitting.

## Source-scale authority

S1 must derive the active area, explicit plane coefficient, memory coefficient,
areal conductance, and areal first-moment coefficient from the nominal S2
source-scale function and config. Values mirrored in the original S1 YAML are
cross-checks only. Any mismatch is a foundation failure.

The analytic sensitivity remains

\[
Y(s)=g_\theta^A\frac{\sqrt{s\tau}}{\tanh\sqrt{s\tau}},
\qquad
\tau=\frac{3c_m^A}{g_\theta^A},
\]

with zero unverified interface resistance. Passing a self-fit never identifies
this spectrum in the Qiu device.

## Controlled analytic reference

The production modal expansion uses 16,384 modes and is compared with a
32,768-mode evaluation on both fit and validation grids for step and
regularized-pulse responses. Every discrepancy must be at most \(5\times
10^{-4}\), one percent of the 0.05 model-response gate. The pulse end and its
two declared neighboring points are always audited.

Failure here is `STOP_S1_REFERENCE_EVALUATION`, not evidence against orders two
or three.

## Candidate eligibility and selection

The three previously registered deterministic starts are retained. No fourth
start is permitted. Each start is isolated from overflow or construction
errors. A candidate is eligible only when the optimizer succeeds, its objective
and parameters are finite, both equality constraints satisfy the registered
tolerance, no numerical parameter bound is active, and all Foster elements are
positive.

Exactly one eligible start is selected using training objective alone.
Validation cannot reselect a start. If all starts are ineligible, the result is
`STOP_S1_OPTIMIZATION`. If the selected order-three model fails a response or
network gate, the result is `STOP_S1_MODEL_FORM_SENSITIVITY`.

## Cauer topology and independent ledger

The first Cauer shunt capacity is at the thermal port and shares the resolved
active-plane temperature. A K-node Cauer realization therefore adds only
K-1 independent vertical temperatures. The active equation stores
\(C_{\rm plane}^A+C_0\) at the port; the remaining capacities store energy in
their own states. The terminal conductance is the only ambient sink.

No arithmetic sum of Cauer elements is interpreted as \(C_m\) or
\(C_\theta\). DC, first moment, continued-fraction transfer, state-space
transfer, step, pulse, positive elements, negative real poles, and positive
realness are all checked.

The ledger advances a separately assembled backward-Euler state system. It
then computes storage from state increments and the terminal sink from the new
last-node temperature. Storage and sink tampering must fail the gate.

## Evidence boundary

The MVE writes non-formal CSV before JSON and report. It cannot create a formal
ID, increment the formal execution count, delay S2, or select S1 for production.
Without an eligible same-device thermal holdout, its strongest possible result
is a qualified self-consistency statement for a model-form sensitivity. S2
remains nominal in every disposition.
