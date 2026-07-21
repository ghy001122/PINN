# Source-contract amendment results

- Task: `SOURCE_CONTRACT_AMENDMENT_AND_FALLBACK_SUBMISSION_LOCK_V2`, C1.
- Base: `76970488118612f6ccf9c3cbf6cb17946ca0d999`.
- Evidence type: isolated formula-contract audit, not a new scientific/device run.
- Formula evaluations: 4002 (2001 reversal fractions on each old branch).
- G1 source fidelity: pass; maximum state and temperature implementation discrepancies are zero against the independent scalar oracle, and anchor reconstruction error is `3.552713678800501e-15`.
- G2 realized tanh-anchor continuity: pass; maximum phase jump `2.434283330465803e-09`, normalized temperature-contract residual `2.675287991138469e-09`.
- Printed-kernel value: `P(0)=0.999999997324712`; its deficit is analytic, not roundoff.
- Literal-S3 sensitivity: maximum realized phase jump `0.11914492485034156`; this does not fail its transcription-fidelity gate and does not refute Qiu or general LLP.
- Protected evidence: 74 records checked; 65 match historical anchors, and 9 are explicitly labeled newly observed rather than historically frozen.
- Frozen GT modified: No.
- Protected production physics modified: No.
- `main_submission_v1.md` modified: No.
- Allowed claim: the `atanh` term is the analytic inverse of the configured tanh limiting-branch anchor.
- Forbidden: Qiu-author-code equivalence, quantitative external validation, general LLP refutation, or RPM/wiping-out claims.
