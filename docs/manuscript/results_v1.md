# Results V1

The locked evidence supports a narrow result chain.

First, terminal data constrain integrated conductance but do not uniquely recover all hidden fields. Second, constrained \(\gamma_{\mathrm{sub}}\) inversion works when micro-kinetic parameters are fixed and \(T_{\mathrm{sw}}\) is calibrated or tightly bounded. Third, confounding audits identify \(T_{\mathrm{sw}}\) as the dominant limitation.

The response-surface tolerance sweep finds a synthetic audit threshold near \(0.1\,\mathrm{K}\) residual \(T_{\mathrm{sw}}\) error and prior width near \(0.05\). The ODE-backed spot-check adds 270 simulator-backed cases and supports the \(0.1\,\mathrm{K}\) threshold under the configured \(\leq 15\%\) median-error criterion. This is not an experimental calibration requirement.

Calibration-vs-protocol disentanglement shows calibration gain dominates protocol gain. The best ODE-backed protocol remains qualified because worst-case errors are non-negligible.

## Supplementary Stiffness And 2D Story Results

Supplementary stiffness figures show that the residual proxy increases as transition width narrows. The sharpest-to-widest residual ratio is `11.894639315460832`, all `180` cases are finite, and continuation reduces the residual proxy in this preflight. Fourier-feature gains are not uniform, so the result is not a Fourier or F-SPS superiority claim.

The phase-field alignment smoke benchmark estimates Allen-Cahn mobility `M` from synthetic full-field anchors. It contains `27` finite cases with median relative error `0.04331110242687686` and success rate `0.8148148148148148` at relative error <= 0.1. This is related-work alignment only, not sparse-port phase-field inversion.

Quasi-2D forward/preflight evidence remains supplementary: `4` forward cases have finite fields and observables, the residual preflight is finite, and `whether_2d_inverse_claim_allowed` remains `False`.
