# M40R Qiu Mesh Forensics (Non-Voting)

This audit does not generate a scientific pass vote and does not overwrite M40.

- Old 2/4/8 CSV reproduced: `True`.
- Current observed order: `1.029678119127076`.
- Current fine-pair change: `0.005925864994084377`.
- Repaired common-grid p99 observed order: `1.0425909784624143`.
- Repaired common-grid p99 fine-pair change: `0.008474185042585899`.
- The raw-grid p99 triplet is oscillatory; no Richardson/GCI precision claim is made for it.
- The unrounded terminal corner produces a growing raw maximum field and remains an unresolved ideal-corner singularity.
- The M40 legacy field estimator contract is incorrect in general, although it is numerically coincident with J/sigma in this uniform core anchor.
- No contact rounding, parameter fit, exclusion-window change, percentile change, inverse, or PINN action is supported.

The supported bounded repair is: retain terminal-flux current, extend the static triplet to 8/16/32, reconstruct bulk field from conservative face current, and evaluate the unchanged p99 on one fixed physical sampling grid.
