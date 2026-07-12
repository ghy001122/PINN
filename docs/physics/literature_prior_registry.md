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


## V9 SnSe And Phase-Change Kernel Priors

All values below are literature-guided / engineering priors for synthetic numerical digital-twin benchmarks, not measured parameters.

| Prior | Value or range | Unit | Provenance note | Allowed use | Forbidden use |
| --- | --- | --- | --- | --- | --- |
| SnSe barrier thermal conductivity | nominal `0.35`, range `0.2-0.8` | W m^-1 K^-1 | Chalcogenide/thermoelectric low-thermal-conductivity trend prior | Thermal-barrier reduced stack audits | Claiming measured SnSe film property |
| SnSe barrier electrical conductivity | nominal `1.0e4`, range `1.0e3-1.0e5` | S m^-1 | Engineering high-conductivity barrier prior to avoid treating SnSe as the active electrical bottleneck | Phase-activated multilayer forward audits | Claiming calibrated contact stack parameter |
| NbO2 Poole-Frenkel kernel | `J=J0 E exp[-(Ea-sqrt(q^3|E|/(pi eps0 epsr)))/(kBT)]` | A m^-2 | Standard monotonic Poole-Frenkel form used as synthetic shape prior | NbO2 electrothermal activation; NDR only through circuit/thermal feedback | Local ad-hoc NDR current law |
| VO2 branch-memory kernel | independent `Tc_up`, `Tc_down`, and width | K | Hysteretic thermal transition shape prior | Synthetic branch-memory switching | Claiming direct fitted VO2 experiment |
| Generic phase kernel | reduced Allen-Cahn/free-energy target | dimensionless | Phase-field-inspired switching prior | Generic ablation family | Claiming material-specific kinetics |
