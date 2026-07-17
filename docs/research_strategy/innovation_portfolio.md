# Claim-Gated Innovation Portfolio

## Bottom Line

The repository has substantial engineering work but only moderate publishable contribution density. The strongest existing contribution is **identifiability before inversion**: sparse terminals fail to identify arbitrary hidden fields, so the target is reduced and calibration-gated. The weakest point is the mismatch between a PINN-oriented project identity and a successful mainline that is currently dominated by numerical simulation plus scalar optimization.

The paper should not invent a new architecture to hide this mismatch. It should either publish the identifiability/digital-twin method honestly, or add one bounded neural-value experiment that demonstrates something the scalar optimizer does not provide.

## Ranked Portfolio

Planning scores are heuristic, not experimental results.

| Rank | Candidate | Manuscript value | Evidence basis | Cost/risk | Decision and gate |
| --- | --- | --- | --- | --- | --- |
| 1 | Provenance-backed VO2 fit/holdout anchor | 5 | Nature source data, equations, code, CC BY 4.0 | medium | **Active Must-have.** Separate fit and holdout protocols; NRMSE and feature error `<=0.20`; otherwise preserve failure. |
| 2 | Complete one coherent manuscript/supplement | 5 | locked five-claim/six-figure chain | low | **Next Must-have.** One manuscript, no duplicate narrative fragments. |
| 3 | Identifiability-gated hierarchical inverse | 5 | current P2 rank failures and `gamma_sub` confounding | medium | Release a parameter block only after full-rank multi-window/protocol evidence, then test nonlinear noisy recovery and coverage. |
| 4 | Amortized probabilistic `gamma_sub` inverse | 5 | current scalar inverse plus surrogate/compact-model literature | medium | Train on declared simulator cases; compare accuracy, calibration, OOD, and wall time with the scalar optimizer. Main claim requires matched holdouts and a real speed/uncertainty advantage. |
| 5 | Dimensionless CV/mortar P1 repair | 4 | P1 interface residual `106.1546` and failed field gate | medium-high | One finite cycle: coordinate semantics, manufactured solution, nondimensional residuals, gradient conflict, continuation, then mortar. Stop on unchanged strict gate failure. |
| 6 | Time-window active design | 4 | distinct thermal/electrical time scales and current P2 rank deficiency | medium | Optimize window/protocol combinations for released blocks; require full rank before inversion and bootstrap/profile-likelihood coverage afterward. |
| 7 | Mechanism-routed composable surrogate | 4 | Chen/Qiu material distinction and Li composable emulators | high | Separate VO2 hysteresis and NbO2 PF experts; first prove within-family holdout. Cross-material transfer is not a gate. |
| 8 | Segmented-terminal low-rank diagnosis | 3 | P3 local rank `1 -> 3`; Liu coplanar motivation | high | Choose one physical topology and a low-dimensional source/channel basis. Require dynamic nonlinear inversion; no arbitrary-field claim. |
| 9 | Compact LUT/Verilog-A export | 3 | Lee compact PINN; current deferred engineering need | medium | Only after external anchor and manuscript. Compare circuit outputs and runtime; it cannot substitute for device validation. |
| 10 | Canonical STL benchmark | 2 | Seiler shared-trunk/multi-head method | high | Run only after P1 passes and only if stiffness remains a paper contribution. Full reproduction and matched baselines are mandatory. |

## Prompt-30 Bounded Idea Registry

These are the only new candidates retained on `2026-07-17`. None is active, none was executed, and none has novelty status. The CPCF pilot itself is downgraded to `failed_but_informative` supplementary evidence because its solver-anchor, `20%` improvement, and bootstrap-direction gates failed.

### Candidate H1: residual-triggered enthalpy/latent-heat upgrade

- **New scientific question:** does a provenance-backed thermal residual show missing phase-change enthalpy that cannot be explained by H0 parameter uncertainty?
- **Nearest precedent:** Patra et al., CPC 2025, diffuse-interface enthalpy PINN for 2D phase change, DOI `10.1016/j.cpc.2025.109854`.
- **Substantive difference:** H1 would be triggered by external thermal discrepancy and tested against an independent conservative solver in a coupled electrothermal/hysteretic setting.
- **Why not A+B:** adding an established enthalpy residual to the current network is only engineering unless a predeclared H0 discrepancy is resolved without harming conservation.
- **Fatal flaw:** no provenance-backed thermal trace currently diagnoses latent-heat omission; without it, latent heat is an unsupported free parameter.
- **MVE:** one small heating/cooling thermal-trace batch; compare H0 against one literature-fixed H1 model with unchanged observation windows and no PINN retraining.
- **Go/stop gate:** proceed only if H0 has a reproducible structured thermal residual, H1 reduces held-out thermal NRMSE by at least `20%`, all energy-ledger errors remain within the existing solver tolerance, and the effect survives source-parameter uncertainty. Otherwise stop.
- **Allowed claim:** `qualified_supported` evidence that an enthalpy term is required for that trace/model pair. **Forbidden:** universal VO2 latent heat, experimental PINN validation, or H1 superiority without the external residual.
- **Expected cost:** at most `30` independent-solver forwards, `0` GPU-h, `<=2 h`.

### Candidate H2: branch/minor-loop history-state discrepancy gate

- **New scientific question:** do heating/cooling or minor-loop observations require a history state beyond the H0 phase variable and fixed hysteresis rule?
- **Nearest precedent:** Nag et al., JAP 2012, DOI `10.1063/1.4764040`, plus the reversal-state compact hysteresis in Zhang et al., Nature Communications 2024, DOI `10.1038/s41467-024-51254-4`.
- **Substantive difference:** H2 would add history freedom only after a branch-conditioned residual pattern is observed and would require held-out minor-loop prediction, not same-loop fitting.
- **Why not A+B:** an event ledger or hysteresis network is established machinery; value would come only from a falsifiable discrepancy-to-state link and fresh-loop prediction.
- **Fatal flaw:** no current repository dataset contains provenance-backed heating, cooling, and minor-loop traces sufficient to separate history from temperature miscalibration.
- **MVE:** one small branch-resolved trace batch with a fixed train/held-out minor-loop split; compare H0, source reversal rule, and one bounded H2 state.
- **Go/stop gate:** proceed only if held-out minor-loop full-trace NRMSE improves by at least `20%`, event count/class stays correct, and profile likelihood does not put the new state parameter on its prior boundary. Otherwise stop and retain H0.
- **Allowed claim:** `qualified_supported` branch-history evidence for the declared source/model. **Forbidden:** generic hysteresis discovery, unique microscopic state recovery, or device-general minor-loop prediction.
- **Expected cost:** at most `40` independent-solver forwards, `0` GPU-h, `<=3 h`.

### Candidate N0-D: solver-fidelity conditioning diagnostic

- **New scientific question:** can an operator/gradient conditioning diagnostic predict which complete-PINN residual blocks will fail solver fidelity before another costly training attempt?
- **Nearest precedent:** Rathore et al., ICML 2024, and De Ryck et al., ICLR 2024.
- **Substantive difference:** the only repository-specific element would be mapping diagnostics to independent solver residual/ledger failures in the complete multidomain contract.
- **Why not A+B:** generic PINN preconditioning is already established; it cannot be a main innovation merely by attaching it to this device model.
- **Fatal flaw:** a conditioning score may correlate with the known N0 failure without causally improving forward fidelity, and the current optimizer route is closed.
- **MVE:** read-only single-checkpoint gradient/Hessian-spectrum proxy on existing v3r diagnostics; no training, no new optimizer, one fixed collocation batch.
- **Go/stop gate:** retain only as reviewer defense if the diagnostic correctly ranks all preregistered failed residual/ledger blocks and is stable to two fixed batch resamples; otherwise reject. It cannot reopen N0.
- **Allowed claim:** an implementation-specific conditioning diagnosis. **Forbidden:** a new universal preconditioner, repaired full PINN, or inverse readiness.
- **Expected cost:** `0` solver forwards, `0` GPU-h, `<=1 h` CPU. **Portfolio disposition:** rejected as a main innovation; optional reviewer-defense audit only under new authorization.

## Practical Research Tricks That Are Ethical

1. **Turn a failed inverse into a designed boundary.** Lead with why terminal compression destroys field identifiability, then show the smallest target that becomes recoverable.
2. **Make calibration an experimental-design variable.** The `T_sw` ridge is more useful as a probe-placement/protocol requirement than as a nuisance hidden in an average error.
3. **Use one simulator matrix repeatedly only with provenance.** The same declared cases may support sensitivity, rank, phase maps, and uncertainty, but reuse must be explicit and fresh solves must be distinguished from interpolated surfaces.
4. **Demand an economic reason for the neural network.** A neural module earns main-text space only through amortized speed, posterior uncertainty, online assimilation, or OOD performance—not by replacing a reliable scalar solver with a larger model.
5. **Use a negative supplementary ladder.** P1/P2/P4 failures answer likely reviewer objections without contaminating the five-claim mainline.
6. **Prefer within-family generalization.** Material-routed experts are more defensible than universal transfer across VO2, NbO2, V2O5, and Nb2O5.
7. **Stop tuning after a gate.** A passed claim is locked; a failed finite-budget rescue becomes a limitation. This prevents post-hoc thresholds and endless architecture churn.

## Architecture Audit

- Vanilla fully connected PINNs are not the current bottleneck; observability and scaling are.
- Fourier features are `forbidden` as a superiority claim because existing on/off evidence is neutral or negative.
- Full STL is absent; current continuation/proxy work may only motivate a future canonical experiment.
- A shared encoder with material-specific constitutive heads is physically defensible only after the VO2/NbO2 mechanisms are separated.
- For terminal-only outputs, a compact supervised emulator may be more efficient than a field PINN. Physics regularization should be used only where it improves OOD or reduces data, with a matched ablation.

## Paper Logic And Workload Judgment

- Engineering workload: high (frozen GT, many audits, extension modules, and broad CPU tests).
- Independent scientific results: narrower than the file count suggests.
- Current mainline: viable for a focused computational methods paper.
- Current neural-algorithm novelty: insufficient for a high-impact PINN algorithm paper.
- Device-validation depth: insufficient for an experimental device paper.
- Best positioning: a synthetic, identifiability-guided physics-informed digital-twin inverse workflow with an external literature-family anchor and explicit failure boundaries.

## Forbidden Shortcuts

Do not count documentation volume as scientific workload; fit and test the same curve; call literature data project experiments; import VO2 parameters into NbO2; call a local Jacobian a solved inverse; call a ridge preflight a neural operator; or put STL/F-SPS/full-field recovery in the title before their gates pass.
