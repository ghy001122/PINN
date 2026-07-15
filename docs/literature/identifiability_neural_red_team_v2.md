# Identifiability and Neural Methods Red-Team v2

Review date: 2026-07-15. This is a primary-source overlap audit, not a novelty claim. An absent search hit is never interpreted as world-first evidence.

## Decision

The components `inverse PINN`, SVD/Fisher identifiability, multistart/profile likelihood, differentiable event time, hard constraints, augmented-Lagrangian PINNs, phase-transition PINNs, terminal-boundary inverse imaging, VO2 hysteresis, and thermal-neuristor compact modeling all have direct prior art. The only retained **candidate combination** is:

> complete phase-transition PINN + independently verified sensitivity fidelity + branch/protocol-conditioned identifiable quotient + explicit refusal of unsupported raw-parameter recovery.

This combination is not currently a contribution: D0a and N0 failed their upstream gates, N1-N3 were not run, and no broader novelty search can substitute for direct project evidence.

## Primary-source comparison

| Category and primary source | Abstract problem | Methods mechanism | Reported/scope limitation relevant here | Substantive overlap and project role |
| --- | --- | --- | --- | --- |
| Inverse PINNs — [Raissi et al., JCP 2019](https://doi.org/10.1016/j.jcp.2018.10.045) | Data-driven solution and discovery for nonlinear PDEs | Neural state approximation plus autodifferentiated PDE constraints in continuous/discrete time | Canonical PDE demonstrations do not establish VO2 branch-conditioned parameter equivalence | Background and mandatory vanilla baseline; inverse PINN alone is not novel |
| PINN identifiability — [Kharazmi et al., Nature Computational Science 2021](https://www.nature.com/articles/s43588-021-00158-0) | Structural/practical identifiability and predictability under sparse/noisy epidemiological data | PINNs infer time-dependent parameters/unobserved dynamics and quantify uncertainty | Model/data-specific conclusions; limited data can leave large uncertainty | Direct prior art for “PINN + identifiability”; near-neighbor baseline |
| Hybrid model identifiability — [Giampiccolo et al., npj Systems Biology 2024](https://www.nature.com/articles/s41540-024-00460-3) | Parameter estimation when part of the mechanism is unknown | Hybrid neural ODE, global parameter search, validation split and identifiability analysis | Neural flexibility can reduce parameter identifiability | Requires all multistarts/profile results; methodology baseline |
| PINN local sensitivity — [Hanna et al., EAAI 2024](https://doi.org/10.1016/j.engappai.2024.108764) | Compute local sensitivity with PINNs | Network/physics derivatives generate sensitivity fields | Does not establish VO2 event-corrected quotient geometry | Sensitivity-aware neural model baseline, not contribution |
| Fisher/sensitivity fidelity — [2026 preprint](https://arxiv.org/abs/2601.11638) | Compare learned and reference Fisher/sensitivity geometry | Classical Fisher information from differentiable dynamics versus PINN | Preprint and system-specific audit; trajectory agreement alone is insufficient | N2 is highly overlapping; fidelity is a required gate, not novelty |
| Differentiable events — [Chen, Amos and Nickel, ICLR 2021](https://openreview.net/forum?id=kW_zpEmMLdP) | Learn implicitly timed discrete events in continuous ODEs | Differentiates event time and state through event handling | Generic hybrid dynamics; no VO2 equivalence-class inverse | Event heads/timing derivatives are components or baselines only |
| Exact event gradients — [EventProp, Scientific Reports 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8213775/) | Exact gradients for continuous-time spiking networks | Adjoint jump conditions at spike events | Spiking-network scope; event/grazing sensitivity remains delicate | Supports mandatory jump/event-time audit; not innovation |
| Phase-field PINNs — [Wight and Zhao, 2020](https://arxiv.org/abs/2007.04542) | Allen-Cahn/Cahn-Hilliard interface dynamics | Adaptive space/time sampling for phase-field PINNs | Direct PINN application can be inaccurate for stiff phase fields | Phase-transition PINN itself is prior art; N0 training-risk reference |
| Equality-constrained PINNs — [PECANN, JCP 2022](https://doi.org/10.1016/j.jcp.2022.111301) | Forward/inverse problems with noisy multi-fidelity data | Equality-constrained/augmented-Lagrangian physics training | Constraint satisfaction does not prove parameter identifiability | One optional baseline/ablation, never a standalone claim |
| Hard boundary constraints — [Sukumar and Srivastava, CMAME 2022](https://doi.org/10.1016/j.cma.2021.114333) | Exact BC satisfaction in physics-informed networks | Distance/R-function trial constructions | Does not address hysteresis-event geometry or raw-parameter non-uniqueness | N0 hard electrical BC implementation is established technique |
| Terminal-boundary inverse — [Smyl et al., Neural Networks 2025](https://doi.org/10.1016/j.neunet.2025.107410) | Conductivity imaging from boundary voltages | PINN EIT reconstruction compared with data-driven and classical imaging | Rich EIT boundary protocols differ from one sparse phase-transition terminal trace | Terminal-only neural inverse is not itself a new problem |
| VO2 hysteresis — [de Almeida et al., Optical Engineering 2002](https://doi.org/10.1117/1.1501095) | Model hysteretic VO2 resistance-temperature response | Hysteresis equation and parameter-estimation procedure | Compact R-T model, not a complete phase-transition PINN | Source hysteresis background and parameterization prior art |
| VO2 oscillator hysteresis — [Maffezzoni, Electronics Letters 2015](https://doi.org/10.1049/el.2015.0025) | Circuit-level hysteresis in VO2 relaxation oscillators | Compact switching/hysteresis circuit model | Circuit scope does not establish PDE inverse identifiability | Thermal-oscillator compact-model baseline |
| VO2 memristor neuron — [Yi et al., Nature Communications 2018](https://www.nature.com/articles/s41467-018-07052-w) | Scalable active-memristor neuronal dynamics | Electrothermal/SPICE device and circuit modeling with measured devices | Device/circuit-specific parameters and topology; thermal-management caveats | Mature electrothermal neuristor prior art; no compact-model novelty claim |
| Cascaded thermal neuristor — [Qiu et al., Advanced Materials 2024](https://doi.org/10.1002/adma.202306818) | Reconfigurable and thermally coupled VO2 neuristors | Detailed theoretical model tied to experimental neuristor dynamics | Data/model apply to the reported device family and protocol | Realism/context baseline; not repository validation |
| D0 source — [Zhang et al., Nature Communications 2024](https://www.nature.com/articles/s41467-024-51254-4) | Collective dynamics in thermal-neuristor networks | RC/electrothermal hysteresis model, Euler-Maruyama at 10 ns, public source data/code | Methods states constants were optimized to reproduce experimental results | Source-paper reproduction only; 13 V can at most be repository-withheld cross-voltage evaluation |

## Zhang source semantic lock

The paper Methods states that model constants depend on the experimental setup and were optimized to reproduce experimental results. It also states a fixed 10 ns Euler-Maruyama step, provides experimental raw data in Source Data, and points to demo code. Consequently:

- no voltage from this source can be called proven independent of source-model development;
- a repository fit using only R-T and 11 V could make 13 V repository-withheld, not externally independent;
- cycle bootstrap on one trace would be within-trace uncertainty, not device generalization;
- the current D0a failure is numerical time-step sensitivity, not experimental invalidation of the source paper.

## Red-team outcome after execution

D0a preserved exact code/SI semantic agreement but failed the preregistered integration-convergence gate. N0 established a non-placeholder architecture contract and manufactured solution, but the fixed single-seed MVE failed both terminal and residual thresholds. Therefore none of the candidate combination can enter the manuscript as a positive method contribution yet.
