# Discussion V1

The main scientific point is not optimizer novelty or full-field recovery. The point is that sparse-port inverse diagnosis must first pass an identifiability audit. In this benchmark, the defensible route is to reduce the target space and estimate \(\gamma_{\mathrm{sub}}\) only under fixed or tightly bounded priors.

The new quasi-2D preflight increases physical depth by documenting how a laterally resolved phase-transition thin-film extension could be constructed. It remains forward-only. Because the unknown field dimension grows sharply in two dimensions, sparse terminal current cannot identify full 2D fields without additional observability.

F-SPS-PINN evidence remains supplementary or future work. Current small-run evidence does not justify a performance-superiority claim.

## Supplementary Stiffness And Phase-Field Defense

The stiffness-continuation audit supports a limited reviewer-defense point: as the synthetic phase-transition width is reduced, the autograd residual proxy increases sharply, so a phase-transition cliff is a valid numerical stress case. Continuation reduces the residual proxy in this preflight, while Fourier features are not uniformly beneficial. This should be discussed as stability motivation, not as proof of F-SPS-PINN superiority.

The phase-field alignment smoke benchmark passes as a full-field-anchor Allen-Cahn mobility inversion sanity check. It aligns the manuscript with phase-field inverse-PINN literature, but it does not alter the main sparse-port `gamma_sub` claim.

## Final Stiffness And Quasi-2D Placement

The stiffness and quasi-2D results increase reviewer-defense depth without changing the core contribution. The paper should present them as physics-consistent extensibility and observability-boundary evidence. The main story remains one-dimensional sparse-port calibration-gated `gamma_sub` inversion.

The correct interpretation is: calibration gain dominates protocol gain; protocol gain is secondary; 2D inverse diagnosis requires additional observability; continuation helps residual stiffness in a preflight but is not a full STL-PINN result.

## Discussion Addendum: Claim-Gated 2D And Stiffness Evidence

The new audits convert prior narrative gaps into bounded evidence. Reduced 2D forward computability is now supported by a finite benchmark, but this does not alter the main one-dimensional `gamma_sub` claim. The observability ladder is especially important: terminal-only 2D inverse diagnosis fails, while augmented port/proxy observations support only low-dimensional parameter diagnosis. This gives the manuscript a defensible path to discuss 2D extensibility without overclaiming full-field recovery.

The stiffness-aware algorithm benchmark supports the weaker statement that continuation, scale-aware weighting, and mini-STL-style transfer mitigate stiffness-induced degradation in a synthetic residual-proxy setting. It does not support full STL-PINN reproduction or F-SPS superiority.

## Public-Data And Full-PINN Failure Boundary

The VO2 audit shows why source-code agreement is weaker than numerical convergence. Matching the author implementation at its declared step does not establish a step-converged reference, and therefore cannot justify a repository refit or protocol-identifiability story. The source paper's parameter-optimization statement also prevents 13 V from being called strictly independent external validation.

The N0 result similarly separates an architecture contract from learned evidence. Hard constraints and a manufactured solution can pass while out-of-sample residuals and terminal trajectories fail. This justifies the rule that trajectory fit alone cannot open an inverse claim and that solver/PINN sensitivity comparison must remain blocked until forward residual fidelity is demonstrated. The calibration-gated `gamma_sub` evidence remains the safe inverse mainline while the complete neural scaffold undergoes a bounded numerical repair.

The bounded repair sharpens that conclusion. Correcting the electrode orientation and replacing a finite-band proxy with exact layer traces materially improves the potential and interface diagnostics, but local strong-form residuals still do not close terminal-current, defect-mass, or energy ledgers. This rules out a simple interface-only explanation. Any further neural forward attempt must change the numerical residual contract toward solver-consistent face/control-volume or weak conservation, not repeatedly tune the completed strong-form branch.

The final control-volume attempt separates operator correctness from optimization evidence even more sharply. Its analytic electric head, frozen-RHS translation, independent trajectory ledgers, hard constraints, gradients, and negative controls all pass before training. Nevertheless, the locked optimization terminates before producing a checkpoint or score trajectory. Thus, neither a correct differentiable operator nor a successful preflight is evidence that a trained PINN satisfies the forward or conservation gates. Because this was the preregistered final bounded N0 attempt, the appropriate response is to preserve the failure and close N0 rather than alter the schedule, normalization, or supervision after observing it.
