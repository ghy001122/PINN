# M42 Qiu 2D Physics Foundation Preflight

## Outcome

M42 is a CPU-only solver preflight. It performed no curve fit, inverse solve,
PINN training, sealed-13-V access, or claim-bearing Qiu device forward. The
fail-closed decision is **B** and the evidence status is
`failed_but_informative`.

The detached P0 replay passed after one retained non-voting abort caused by
Git ownership protection and an incorrect guessed full SHA. The corrected
replay used the same committed
bytes and external assets and completed 442 tests.

## Scope and equations

The electrical audit enforces $P_{port}=P_{bulk}+P_{contact}$ for a
source-level series network. The thermal preflight solves a constant-property,
finite-width conservative substrate problem under a unit load. The unit load
is a linear normalization: reported temperatures are thermal impedances, not
Qiu temperature predictions. Total sensible enthalpy and boundary heat are
checked through separately coded finite-volume bookkeeping paths. This is a
discrete conservation check, not independent validation of the physical
closure. Latent heat is disabled because no source-locked
local value exists; that is a model gap, not evidence for zero latent heat.

## Locked gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
| `contact_power_closure` | 4.202493841322213e-17 | 1e-06 | pass |
| `domain_sensitivity` | 0.8423533466521732 | 0.02 | fail |
| `dynamic_duration_Rload_C` | 3.0 | 3.0 | pass |
| `finest_pair_I_Tmean_Tmax_Qout` | 0.13812905763956299 | 0.02 | fail |
| `no_clip_nan_or_unregistered_extrapolation` | True | True | pass |
| `pure_2d_out_of_plane_closure` | 0.6705793985868671 | 0.1 | fail |
| `relative_current_imbalance` | 0.0 | 1e-06 | pass |
| `smooth_enthalpy_imbalance` | 2.5757174171304294e-14 | 0.0001 | pass |
| `switching_enthalpy_imbalance` | None | 0.001 | fail |
| `uniform_2d_source_resistance` | 1.330233207545514 | 0.01 | fail |

## Main findings

- Source-to-local resistance error is 1.330; therefore the old local $\sigma$ mapping does not preserve the source port resistance.
- The maximum finite-width/x-z extrusion discrepancy is 0.671.
- Domain, mesh, and time fine-pair maxima are 0.842, 0.138, and 0.009.
- 22 bounded manufactured/unit-load forward calls were used across pilot and formal execution (11 unique cases), within the locked budget of 40.

## Highest-risk unresolved assumptions

1. Qiu device-level resistance does not uniquely determine local conductivity or contact partition.
2. Constant-property sapphire and zero registered latent heat are numerical preflight closures, not real-device calibration.
3. The x-z extrusion suppresses finite-width spreading and cannot be quantitative unless the explicit closure gate passes.

## Manuscript and next-step disposition

Decision A would authorize only a later formal reference solver, never an
inverse or PINN claim. Decision B authorizes only a bounded 2.5D/coarse-3D
closure study. Decision C terminates the 2D route. The present decision does
not upgrade any manuscript claim; exact author-code reproduction, external
quantitative validation, terminal-only 2D inverse, and trained 2D PINN remain
`forbidden`.
