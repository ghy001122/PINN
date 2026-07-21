# E1F Qiu source-equation external-anchor results

- Status: `failed_but_informative`.
- Formal execution: `1/1`; forward integrations: `6`; wall time: `38.657 s`.
- Source boundary: S1--S7 are reported, but the executable reversal update, numerical initial conditions, integrator/tolerances, author code, and raw arrays are not public. Exact author-code reproduction remains `forbidden`.
- The 12.5 V curve is repository-withheld but comes from the same paper and may have informed source-author parameter development; it is not independent external validation.

## Numerical and curve gates

- DOP853/Radau parity: `True`; worst waveform NRMSE `2.77807144e-07`.
- Source-figure setting check: `False`; max current/voltage NRMSE `0.699090785` versus `0.10`.
- Same-paper 12.5 V curve: `False`; current NRMSE `0.494238595` versus `0.15`.
- Effective-coordinate preflight: `not_run_upstream_gate_failed`; it is local diagnostic evidence only.

## Read-only source-to-PDE bridge audit

Locked M40/M40R artifacts give local/source ratios that disagree by 2.330233 in resistance; source/local ratios are 635.5145 for thermal capacitance, 206 for thermal conductance, and 3.085022 for thermal time constant. These values forbid direct transfer of lumped author fits into local PDE material or boundary parameters; they do not authorize another M40 repair.

## Claim disposition

The formal external-anchor vote failed at setting_curve, same_paper_holdout. Passed numerical/provenance sub-results and the bridge-refusal audit remain usable; no refit or replacement curve is authorized.

The constrained synthetic rank-1 `gamma_sub` result remains the only positive inverse mainline. M40/M40R, full-PINN training, M41, public inverse identification, and experimental-validation claims are unchanged.
