# M42 Reference-Model Responsibility Matrix

| Quantity or mechanism | Source role | M42 use | Boundary |
| --- | --- | --- | --- |
| 100 nm x 500 nm footprint; 100 nm VO2 | Qiu literature-reported | Geometry and finite-width scale | Coordinate assignment is literature-derived, not tomography |
| 15 nm Ti / 40 nm Au | Qiu literature-reported | Electrode domains | Lateral overlap remains unresolved |
| `Rload`, `C`, `Vin`, ambient temperature | Qiu reported/fitted circuit contract | Three-RC horizon and circuit ledger | Not local material properties |
| Qiu S1--S4 hysteresis | Printed source formula contract | Default path-dependent operator | Missing author code, event deadband, and full initialization prevent exact reproduction |
| `Cth`, `Sth` | Qiu author-fitted lumped equivalents | Aggregate scale diagnostics only | Never assigned to a local cell, material, or boundary |
| Local sapphire `k` and `rho cp` | M40 engineering prior | Diffusion-length sensitivity only | Not Qiu-measured; uncertainty blocks calibration wording |
| Latent heat | Unresolved | Disabled in preflight ledger (`L=0`) | A declared missing-model term, not a zero-real-physics claim |
| Contact resistivity and thermal boundary resistance | Unresolved/derived | Analytic sensitivity or refusal | No fitted local value and no direct transfer from a lumped resistance |
| Zhang author code and public curves | External comparator | Discrete/continuous semantics only | No independent validation; 13 V sealed |
| Chen SnSe/NbO2 | Cross-material literature | Future trend check only | No parameter or mechanism transfer to VO2 |
| Liu coplanar NbOx | Geometry-family literature | Future topology holdout only | No quantitative Qiu validation |
| Full PINN, STL, Fourier/F-SPS, Lee/Jurj surrogate | Existing/future algorithms | Registry-only in M42 | No training or reproduction in this round |

M42 outputs are solver-generated preflight evidence. They are neither
measurements nor an independent literature-curve validation.
