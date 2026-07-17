# Prompt-31 QoI/Event-Conditioned PINN Literature Red Team

Search date: `2026-07-17`. Scope: eight nearest primary papers. This is a bounded overlap audit, not a systematic review; absence from this table is not evidence of novelty.

## Search strings

- `PirateNet physics-informed residual adaptive network`
- `Dual-Balancing DB-PINN loss weighting`
- `NysNewton-CG PINN loss landscape`
- `SOAP structured preconditioning PINN`
- `XPINN domain decomposition generalization`
- `DeepONet nonlinear operator learning`
- `Neural Event ODE differentiable event time`
- `dual-weighted residual goal-oriented PINN adaptive sampling`

## Primary-paper comparison

| Primary source | Abstract problem and Methods mechanism | Discussion/Conclusion boundary | Substantive overlap and project position |
| --- | --- | --- | --- |
| [Wang et al., PirateNets, arXiv:2402.00326](https://arxiv.org/abs/2402.00326) | Diagnoses derivative-trainability failure in deep MLP PINNs and introduces adaptive residual connections initialized as shallow networks plus physics-informed initialization. | Evidence is benchmark-based; stable depth does not itself establish solver agreement, interface conservation, event handling, or inverse fidelity for this device. | Direct architecture precedent. PirateNet may be a baseline, never a standalone novelty claim. |
| [Zhou et al., DB-PINN, arXiv:2505.11117 / IJCAI 2025](https://arxiv.org/abs/2505.11117) | Uses inter-loss gradient balancing and intra-condition difficulty balancing with robust weight updates to address PINN multi-objective imbalance. | Reported gains concern convergence and prediction accuracy on the authors' benchmark set; they do not certify physical ledgers or make dynamic weighting a new device mechanism. | Direct precedent for block scaling/loss balancing. It is a component baseline only. |
| [Rathore et al., ICML 2024](https://proceedings.mlr.press/v235/rathore24a.html) | Links PINN optimization difficulty to differential-operator-induced ill-conditioning and introduces NysNewton-CG after Adam/L-BFGS comparisons. | Better optimization on benchmark PDEs does not repair an incompatible physics contract or prove forward/sensitivity fidelity. | NNCG is prior art and a future matched optimizer baseline, not a contribution by itself. |
| [Priyadarsini et al., ICLR 2026, SOAP+MoQ](https://openreview.net/forum?id=IYKeKBFKCo) | Studies SOAP-style structured preconditioning and adds momentum/extrapolation for PINN training. | The authors characterize the study as preliminary across a small PDE set; performance remains problem- and noise-regime dependent. | SOAP is established optimizer machinery. It cannot reopen the stopped N0 route without a new authorized contract. |
| [Hu et al., SISC, arXiv:2109.09444](https://arxiv.org/abs/2109.09444) | Analyzes when XPINN domain decomposition improves generalization using prior/posterior bounds and PDE experiments. | Domain decomposition trades lower local function complexity against fewer samples per subdomain; XPINN can outperform, match, or underperform a global PINN. | Direct warning that two-domain structure is not automatically superior. Interface/conservation gates remain mandatory. |
| [Lu et al., Nature Machine Intelligence 2021](https://doi.org/10.1038/s42256-021-00302-5) | DeepONet encodes input functions with a branch network and output coordinates with a trunk network to learn nonlinear operators over parameter/function families. | Generalization is tied to the represented input distribution and sensorization; the original paper does not establish this repository's event-rich multiphysics conservation or OOD ladder. | Operator learning is prior art. It is allowed only after within-family waveform/parameter holdouts and solver/field gates. |
| [Chen, Amos and Nickel, Neural Event ODE, ICLR 2021](https://openreview.net/forum?id=kW_zpEmMLdP) | Makes event times and state transitions differentiable in Neural ODEs using solver event handling and event-function gradients. | Hybrid-event differentiation can become delicate near non-transversal/grazing events and does not supply a VO2 history law or identifiable coordinate by itself. | Event-time features and event heads are established components, not innovation. The project must retain physical event ledgers and independent finite-difference checks. |
| [Govoeyi and Richter, arXiv:2604.01835](https://arxiv.org/abs/2604.01835) | Uses a dual-weighted-residual QoI estimator to guide functional-oriented adaptive sampling for PINNs and Deep Ritz models. | Current evidence is for Laplace/Deep-Ritz-style goal functionals; transfer to nonlinear hysteretic multidomain conservation is unproven. | Direct precedent for QoI-guided residual allocation. Repository novelty, if any, must come from the falsifiable event/conservation/refusal combination and direct solver evidence. |

## Deduplication result

- PirateNet, DB-PINN, SOAP/NNCG, XPINN, DeepONet, differentiable event handling, and DWR/QoI sampling all have direct prior art.
- The only retained combination hypothesis is a complete multidomain PINN whose allocation is driven by an identifiable QoI, whose phase events are physically ledgered, whose interfaces and global ledgers are independently checked, and which abstains when the QoI is not identifiable.
- That combination has no novelty status. The repository has not trained it, and the current N0 failures make any success claim `forbidden`.
- The allowed search statement is only: "As of `2026-07-17`, no substantively isomorphic work was identified within the recorded bounded search." It is not a world-first claim and must not appear as a definitive novelty assertion.
