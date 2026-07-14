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

## V10 Source Anchors

- NbO2 primary mechanism: Slesazeck et al., *RSC Advances* 5 (2015),
  DOI `10.1039/C5RA19300A`. The repository uses its temperature-activated
  Frenkel-Poole plus Joule-heating mechanism as a shape and parameter prior.
- VO2 literature profile: Qiu et al., *Collective dynamics and long-range order
  in thermal neuristor networks* (2024), using the published reduced-model
  values `Tc=332.8 K`, hysteresis width `w=7.19 K`, `C=145 pF`, and
  `Rload=12 kOhm` as literature-shape priors. The v10 split thresholds are a
  symmetric reduced mapping around `Tc`, not measured repository data.

These sources do not upgrade any synthetic result to experimental validation.

## P1 Cross-Family Benchmark Boundary

The v10 P1 training case combines `full_stack_with_SnSe_barrier`, which is motivated by NbO2 thermal-barrier stacks, with the `vo2:normalized_activated` synthetic kernel. It is therefore a field-anchored synthetic cross-family method benchmark. It is not a reproduction of a VO2/SnSe device, a Qiu thermal-neuristor geometry, or an SnSe/NbO2 measured stack.

Future positive device-family claims require a topology-consistent constitutive kernel and provenance-backed external data. The exact VO2 and SnSe/NbO2 parameter sets quoted in the post-d1121e16 external review remain candidate values only until their primary source, table/figure, units, and fitted-versus-measured status are locked.
