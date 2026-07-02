# Main Text Results V1

All results are synthetic numerical digital-twin benchmark evidence. They are not measured experimental data, not full 3D device simulation, and not proof of sparse-port full hidden-field recovery.

## Result 1: Full Hidden-Field Recovery Is Ill-Posed

Existing v0/v1/v1.1 and identifiability audits show that terminal port observations primarily constrain integrated conductance. This motivates target-space reduction instead of claiming unique recovery of `delta_T`, `c_v`, `m`, or `sigma` fields.

## Result 2: Reduced `gamma_sub` Inversion Is Conditional

The constrained inversion and confounding audits support `gamma_sub` as a reduced inverse target only when `T_sw`, `tau_m`, `sigma_on0`, `eta_A`, and micro-defect parameters are fixed or tightly bounded. `T_sw` remains the dominant confounder.

## Result 3: Literature Curves Are Not Yet Usable As Direct External Anchors

The v2 ingestion workflow found `0` valid provenance-backed digitized curve files. External curve fitting is `blocked` because `blocked: no provenance-backed digitized curves available`. This is a strength for ethics and reproducibility: no curve points were fabricated.

## Result 4: T_sw Calibration Before Inversion Is Necessary

The no-calibration workflow gives relative `gamma_sub` error `0.8309764722472351`. The best calibrated workflow, `synthetic_probe_calibrated_T_sw`, reduces this to `0.037771657829419776`. A wrong-calibration control remains worse at `0.3021732626353582`.

## Result 5: Calibrated Sequential Protocol Validation

The ODE-backed validation contains `720` finite synthetic cases. The best candidate is `calibrated_multi_pulse_to_ltp_ltd` with success rate `1.0` and max error `0.1111111111111111`. This supports a manuscript claim that protocol design can reduce ambiguity under calibrated priors, not a real-device protocol claim.
