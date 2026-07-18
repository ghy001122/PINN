# Title, Abstract, Keywords

## Working Title

Calibration-gated sparse-port inverse diagnosis for phase-transition material digital twins

## Abstract Draft

This manuscript studies a one-dimensional reduced phase-transition / memristive channel digital twin for sparse-port inverse diagnosis. The benchmark is synthetic and numerical, not experimental data. Terminal voltage, current, and conductance observations are first used to show that port-only full hidden-field recovery is ill-posed. The inverse target is therefore reduced to the effective substrate heat-loss coefficient \(\gamma_{\mathrm{sub}}\), with micro-kinetic and switching parameters fixed or tightly bounded by literature-guided / engineering priors.

The evidence chain combines Ground Truth v1.1 acceptance, identifiability analysis, constrained \(\gamma_{\mathrm{sub}}\) inversion, confounding audits, calibration-tolerance sweeps, protocol disentanglement, and simulator-backed ODE spot-checks. The current results support a conditional claim: \(\gamma_{\mathrm{sub}}\) can be recovered in this synthetic benchmark only after \(T_{\mathrm{sw}}\) is calibrated or tightly bounded. Calibration control dominates the smaller protocol-associated response-surface difference, while the 720-case Figure 5 comparison supports only bundled configuration performance because waveform and calibration error vary together. A truth-free simulation-calibrated set passes nominal discrete-grid coverage but fails to refuse severe model mismatch. A literature-anchored quasi-2D preflight is provided only as extension feasibility and does not solve two-dimensional inverse diagnosis.

## Keywords

physics-informed digital twin; phase-transition material; sparse-port inverse problem; identifiability; substrate heat loss; memristive device; synthetic benchmark
