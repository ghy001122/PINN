# M32 SCIS, profile likelihood, and inverse-UQ red team

Date: 2026-07-18
Scope: six primary sources; component-level novelty and claim-boundary audit
Evidence role: external literature only; it does not upgrade repository experiment status

## Findings

| Primary source | Problem and core mechanism | Stated or applicable boundary | Material overlap with this repository | Project role |
| --- | --- | --- | --- | --- |
| [Raue, Kreutz & Timmer, Bioinformatics 2009, DOI 10.1093/bioinformatics/btp358](https://doi.org/10.1093/bioinformatics/btp358) | Structural and practical identifiability of partially observed dynamical models through one-parameter profile likelihood with nuisance re-optimization. | Profiles are model-, data-, parameter-range-, and optimization-dependent; local minima and flat remote regions complicate interpretation. | Direct precedent for using objective profiles and retained parameter regions to diagnose non-identifiability. | Baseline/background. A five-percent profile set or profile-based refusal is not novel by itself. |
| [Talts et al., arXiv:1804.06788](https://arxiv.org/abs/1804.06788) | Simulation-based calibration validates Bayesian inference algorithms using repeated draws and rank diagnostics. | It diagnoses calibration under the assumed generative model; it does not confer robustness to simulator misspecification or prove physical identifiability. | Direct precedent for simulator-generated calibration and for separating algorithm validation from scientific model validity. | Background and semantic warning; M32 is not Bayesian SBC and must not borrow its claims. |
| [Sadinle, Lei & Wasserman, JASA 2019, DOI 10.1080/01621459.2017.1395341](https://doi.org/10.1080/01621459.2017.1395341) | Set-valued classification with user-controlled coverage/error and minimized ambiguity; empty sets are explicitly treated. | Guarantees concern the stated statistical population and classifier construction, not arbitrary distribution shift. | Strong precedent for candidate sets, coverage, ambiguity, and refusal/empty-set semantics. | Near-neighbor baseline; set-valued output and abstention are not innovations. |
| [Romano, Sesia & Candès, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/244edd7e85dc81602b7615cd705545f5-Abstract.html) | Hold-out conformal classification sets with marginal coverage and distribution-adaptive conformity scores. | Finite-sample marginal coverage relies on the sampling/exchangeability contract; approximate conditional behavior is not universal out-of-distribution protection. | Strong precedent for split calibration, finite-sample order statistics, and label-specific set scores. | Methodological baseline; SCIS may claim only its locked discrete-simulator implementation and observed gates. |
| [Masserano et al., AISTATS/PMLR 2023](https://proceedings.mlr.press/v206/masserano23a.html) | WALDO constructs simulator-based inverse confidence regions with finite-sample conditional validity through regression-assisted Neyman test inversion. | Validity is tied to the simulator and calibration design; it does not establish material/device truth under misspecification. | Closest inverse-problem precedent for simulation-calibrated confidence regions that do not merely report a point estimate. | Strong novelty blocker and preferred future baseline if a new UQ phase is authorized. |
| [Stuart, Acta Numerica 2010, DOI 10.1017/S0962492910000061](https://doi.org/10.1017/S0962492910000061) | Bayesian formulation of inverse problems, regularization, posterior uncertainty, and function-space well-posedness. | Posterior uncertainty depends on likelihood, prior, and forward-model assumptions and can be computationally expensive. | Establishes that uncertainty-aware constrained inversion is a mature field; a physics constraint or uncertainty set alone is not novel. | Foundational background and claim-discipline reference. |

## Red-team resolution

The following components have clear precedent and cannot be packaged separately as novelty: profile likelihood, simulator-based calibration, finite-sample calibrated sets, set-valued classification/refusal, confidence regions for simulator-based inverse problems, and constrained/Bayesian inverse uncertainty quantification.

The project-specific combination remains only a hypothesis: a complete phase-transition PINN, independently verified sensitivity geometry, and a branch/protocol-conditioned identifiable coordinate with an explicit refusal mechanism. M32 does not support that hypothesis. Its nominal discrete-grid coverage passes, but its severe-mismatch refusal fails, so the result is a negative boundary rather than a new UQ method claim.

No absence-of-literature search is interpreted as world-first evidence.
