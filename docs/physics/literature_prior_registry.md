# Literature Prior Registry

This registry records literature-guided and engineering priors for synthetic numerical digital-twin benchmarks. It is not an experimental database and does not contain measured parameters for the current repository benchmark.

## Boundary

Allowed use: shape and parameter-plausibility priors for reduced synthetic models.

Forbidden use: experimental validation, device replication claims, or fitted material constants without provenance-backed measured data.

## Device Families

| Family | Stack | Direct use in this repo | Claim boundary |
|---|---|---|---|
| NbO2/SnSe sandwich thermal engineering | TE / NbO2 / SnSe thermal barrier / BE / substrate | Main multilayer sandwich and thermal-boundary prior | Motivates thermal barrier and boundary terms only |
| VO2 thermal neuristor | Ti/Au electrode / VO2 / Al2O3 substrate | Hysteretic R(T), delay/spiking, and thermal coupling prior | Shape prior, not a fitted VO2 device |
| NbOx/AlN coplanar Mott memristor | Ti/Pt coplanar electrodes / NbOx / AlN passivation / SiO2 / p++Si | Lateral 2D and multi-terminal/coplanar motivation | Supports observability tests, not full FEM validation |

## Provenance Rule

Each prior entry must carry family, stack, quantity, units, value/range or trend, provenance note, allowed use, and forbidden use. Curve digitization is currently recorded as `not_digitized_repo_registry_only`; no curve from this file may be described as measured repository data.
