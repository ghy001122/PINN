# Gamma_Sub Calibrated Sequential Protocol Validation Report

This report is based on synthetic numerical digital-twin simulator-backed ODE cases. It is not experimental protocol validation.

## Result

- Simulator-backed cases: `720`.
- All finite: `True`.
- Frozen GT unchanged: `True`.
- Best calibrated protocol: `calibrated_multi_pulse_to_ltp_ltd`.
- Success rate for best protocol: `1.0`.
- Median error for best protocol: `0.0`.
- Success-rate gain over no calibration: `0.4833333333333333`.
- Success-rate drop under wrong calibration: `0.33333333333333337`.

## Interpretation

The calibrated multi-pulse-to-LTP/LTD sequence is the strongest current synthetic protocol candidate for the constrained `gamma_sub` line. It should be written as protocol-design evidence under bounded priors, not as an experimentally validated stimulation protocol.
