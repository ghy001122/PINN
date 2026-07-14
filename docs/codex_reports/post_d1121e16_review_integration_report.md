# Post-d1121e16 Review Integration Report

## Purpose And Manuscript Use

This report reconciles `PINN_phase_change_project_review_d1121e16.md` against repository state at base SHA `d1121e16fa5015a297da468e3e6f0504b9e97d17`. Its manuscript use is to correct the evidence map, reorder work around submission-critical Must-have gaps, and keep material/topology extensions inside their actual evidence boundaries.

Evidence type in this round: repository code/document review, existing synthetic numerical digital-twin tables, and primary-source identity checks. No new simulation, training, digitized curve, or project measurement was produced.

## 1. Repository And Validation Metadata

- Branch: `main`.
- Base HEAD: `d1121e16fa5015a297da468e3e6f0504b9e97d17`.
- Base worktree: clean.
- Evidence-lock base SHA: `e2e2669adfd66aacefacfbfceafcdfc18eafbbee`.
- Evidence-lock final commit: `d1121e16fa5015a297da468e3e6f0504b9e97d17`.
- Current round final SHA: pending because this report is part of the current working tree; report the actual commit in the task handoff if committed.
- The repository contains no `.github` workflow directory. The defensible statement is local Codex test execution, not GitHub CI success.

## 2. Review Findings Accepted

1. Priority A materially improved evidence assembly rather than adding a scientific experiment.
2. Figure 1 over-described its visual content: `correlation_heatmap.png` supports the identifiability boundary but does not itself display target-space reduction.
3. C2 lacked a direct recovery visual in the locked main figures.
4. The old B-to-C-to-D queue over-weighted high-risk upgrades relative to the external quantitative anchor and complete manuscript required by the Definition of Done.
5. P1 combines a SnSe-barrier topology prior with a normalized VO2 active kernel and is therefore a synthetic cross-family method benchmark, not a literature device reproduction.
6. P3 rank `1->3` is local observability of Gaussian-profile center/width/contrast, not arbitrary field-space rank or device-level 2D inverse evidence.
7. Numerical forward plus neural inverse/surrogate is the correct division of labor; network capacity alone is not the manuscript thesis.

## 3. Figure And Claim Mapping Correction

Figure 1 is renamed `Sparse-port identifiability boundary`. No target-space-reduction wording remains in the title.

Figure 2 retains the gamma_sub/T_sw confounding ridge as panel (a) and adds panel (b), a true-versus-continuously-estimated off-grid gamma_sub comparison using the existing 36-case continuous-refinement CSV. Figure 2 now directly supports C2 constrained recovery while retaining C3 confounding evidence. This is evidence re-visualization, not a new experiment.

The current claim statuses do not change:

- C1: `supported` within the frozen synthetic benchmark.
- C2-C5: `qualified_supported`.
- P0/P3: `qualified_supported` within their reduced boundaries.
- P1/P2: `failed_but_informative`.
- P4 and completed external/experimental validation: `forbidden`.

## 4. Delivery-Priority Decision

The delivery sequence is reordered to A complete -> D external quantitative anchor -> M complete manuscript/supplement -> B one bounded P1 repair -> C rank-first protocol -> E dynamic multi-terminal -> F blocked algorithms -> G deferred compact export.

Reason: Priority D and Priority M are explicit submission Definition-of-Done items. P1 is valuable but risky and optional. The value/time/compute/risk filter therefore supports moving the external anchor ahead of P1 without changing the manuscript core line or relaxing any scientific gate.

The review proposed parallel external anchoring and manuscript assembly. Repository governance permits exactly one active bottleneck, so they are serialized: D is active, M follows.

## 5. Primary Literature Identity Check

### Qiu-associated VO2 thermal-neuristor source

The primary source is Zhang, Sipling, Qiu et al., *Collective dynamics and long-range order in thermal neuristor networks*, Nature Communications 15, 6986 (2024), DOI `10.1038/s41467-024-51254-4`.

The publisher page confirms VO2 thermal neuristors, the circuit/thermal ODE structure, experimental figure data, supplementary information, downloadable source data, code provenance, and CC BY 4.0 reuse terms. This makes it the preferred first provenance candidate.

The exact numerical parameter list quoted in the review is not imported in this round. Several values require supplementary/source-data verification, and the review's `R_m` value is not confirmed by the publisher HTML inspected here. Exact values remain candidate priors until source file, table/figure, units, and fitted-versus-measured status are recorded.

### NbO2 mechanism source

Slesazeck et al., *Physical model of threshold switching in NbO2 based memristors*, DOI `10.1039/C5RA19300A`, directly supports temperature-activated Frenkel-Poole conduction plus Joule-heating feedback and supplies a published parameter table. It does not establish the review's separate SnSe/NbO2 device values.

The review attributes an SnSe/NbO2 parameter set to Chen et al., but the exact primary paper was not identified with sufficient certainty in the current repository or primary-source check. Those numbers and topology remain unauthorized for quantitative use until provenance closes.

## 6. Active Priority D Gate

The active phase requires:

- exact source/version, DOI, authors, material, topology, figure/source-data identity, units, access date, license, extraction method, and SHA-256;
- immutable raw data under `data/external/`;
- one calibration trace and one independent holdout trace/branch/protocol;
- no holdout leakage into fitting, normalization tuning, or threshold selection;
- normalized RMSE `<=0.20` on both fit and holdout plus `<=0.20` relative error for any reported threshold/holding/spike-frequency feature;
- digitization/source precision uncertainty;
- config, implementation, behavioral tests, JSON/CSV, comparison figure/table, report, claim update, and manuscript sentence.

Pass wording is limited to external literature-curve validation under the declared source/protocol. A provenance-complete quantitative miss is `failed_but_informative`; incomplete provenance remains `forbidden`.

## 7. Mechanism And Topology Routing

- VO2: branch-memory/hysteretic thermal-neuristor family; exact values require primary-source provenance.
- NbO2: Frenkel-Poole/electrothermal family; do not add VO2 phase fraction by default.
- P1: explicitly synthetic cross-family method benchmark.
- Future multi-terminal work: choose either coplanar or vertical segmented topology before implementation and restrict the target to a declared low-dimensional basis first.
- Shared components may include conservation, interfaces, topology encoding, and port decoding; material constitutive kernels remain family-specific.

## 8. Selective Innovation Routing

Adopt now:

- recoverability-map/claim-ladder narrative;
- numerical forward plus neural inverse/surrogate division;
- provenance-gated external validation;
- material-mechanism separation;
- explicit P1/P3 topology and basis boundaries.

Retain as bounded later audits:

- one-cycle CV-cPINN coordinate/face/scaling repair;
- rank-gated hierarchical inversion;
- time-window active design with nonlinear re-simulation and coverage;
- dynamic multi-terminal reduced-target observability.

Defer:

- arbitrary 2D hidden-field recovery;
- dual-graph neural emulator;
- compact/LUT/Verilog-A export before the manuscript Must-haves;
- full STL/Fourier/F-SPS story unless P1 passes.

## 9. Manuscript Positioning

The core line remains identifiability-guided, calibration-gated reduced-target inversion. The review's suggested title direction is compatible with this line, but no title is locked in this round.

Until P1 passes, titles and abstracts must not foreground OASIS-PINN, F-SPS-PINN, full-field reconstruction, or device-level 2D inversion. Literature-grounded VO2/NbO2 extension wording becomes a positive contribution only after the external anchor and mechanism provenance are complete.

## 10. Round Disposition

- Actual work: review absorption, Git/evidence verification, metadata repair, Figure 1/2 mapping correction, delivery-priority reordering, P1 cross-family boundary, and external-anchor gate definition.
- Distance-to-goal change: evidence-lock metadata and direct C2 visual gap are closed; external quantitative evidence and the complete manuscript remain open.
- Claim changes: none; existing statuses are preserved.
- New blockers: exact SnSe/NbO2 review-source identity and some quoted parameter provenance are unresolved.
- Next single priority: Priority D Qiu VO2 source-data provenance, fit/holdout audit, and quantitative comparison.
- Disposition: stop automatic P1 activation; continue with the submission-critical external anchor.

## 11. Validation

- Evidence-lock and manuscript-ready figure builders completed successfully.
- Figure 2 received visual QA: panel (a) retains the confounding ridge and panel (b) visibly compares all 36 off-grid true/estimated cases, with noise color and observation-count marker size.
- Targeted evidence/governance/P1-boundary regression: `12 passed in 55.73s`.
- Full CPU test suite: `188 passed in 236.40s`.
- Project-governance audit: `pass_with_manual_review`, no failed checks; the manual items are client-rule loading and portable mtime review.
- Re-running the evidence-lock and figure generators preserved SHA-256 hashes for the generated Markdown, JSON, and Figure 2 PNG (`GENERATORS_IDEMPOTENT=True`).
- `git diff --check` reported no whitespace errors.
- Frozen GT SHA-256 values match the locked governance values, `git diff` is empty for all frozen paths, and every frozen file mtime predates the 2026-07-14 19:03 review-document timestamp. Frozen GT v1.1 was not modified.
- No external data file was added and no scientific claim status changed.
