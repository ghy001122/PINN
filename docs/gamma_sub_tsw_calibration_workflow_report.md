# Gamma_Sub T_sw Calibration Workflow Report

This report summarizes synthetic numerical digital-twin workflow evidence. It is not experimental data and it does not prove unconstrained joint identifiability.

## Result

- Best workflow: `synthetic_probe_calibrated_T_sw`.
- No-calibration relative error: `0.8309764722472351`.
- Best calibrated relative error: `0.037771657829419776`.
- Improvement over no calibration: `0.7932048144178153`.
- Minimum tested calibration accuracy needed for <=10% recovery: `0.04` K.
- Wrong-calibration control relative error: `0.3021732626353582`.

## Interpretation

The evidence supports a calibration-before-inversion workflow: constrain or probe `T_sw` before estimating `gamma_sub`. It does not support releasing `T_sw` and `gamma_sub` jointly from sparse electrical ports.
