# M40 Qiu VO2 Model Responsibility Contract

## Scientific responsibility

M40 implements a new `qiu_2024_vo2_2d` source-constrained numerical
namespace. It does not reuse Zhang M35-M37R data roles, parameters, fits,
gates, or the sealed 13 V curve. The source is Qiu et al., *Advanced
Materials* 36, 2306818 (2024), DOI
[`10.1002/adma.202306818`](https://doi.org/10.1002/adma.202306818), together
with its official Supporting Information.

The source reports a 100 nm thick VO2 device with a 100 x 500 nm2 footprint,
15 nm Ti/40 nm Au electrodes, and an Al2O3 substrate. It also reports the RC
topology, major/minor R-T loops, and author-fitted compact-model parameters.
The source model is a uniform-temperature lumped ODE. It is not a two-
dimensional PDE solver.

## State and topology boundary

The M40 state is exactly `phi`, `T`, and `h`:

- `phi`: electrical potential on Ti/Au/VO2 only;
- `T`: temperature on Ti/Au/VO2/Al2O3;
- `h`: continuous hysteretic insulating-fraction/history state on VO2.

Al2O3 is excluded from the electrical matrix. Conductivity is computed from
`T`, `h`, and locked constitutive parameters; it is not a predicted state.
No vacancy field, free phase field, `sigma`, or `log_sigma` output exists.

## Parameter responsibility

`literature-reported` and `source-author-fitted` values are listed in
`data/external/qiu_2024_thermal_neuristor/manifest.json`. The following remain
`engineering-prior/unresolved`: substrate truncation, lateral electrode
overlap, local thermal properties not reported by Qiu, individual contact
resistivity, thermal interface resistance, remote heat-loss boundary, and the
local differentiable history time scale.

The approximate 260 ohm total contact contribution is a difference between
the author-fitted 262.5 ohm metallic resistance and the paper's 2.5 ohm
intrinsic estimate. Equal contact splitting and conversion to an areal value
depend on the explicitly marked contact-area prior. They are not measurements.

Qiu's `Sth=0.206 mW/K` and `Cth=49.6 pJ/K` are author-fitted lumped
equivalents for VO2, electrodes, and surrounding substrate. M40 does not
assign them to a local material or interface. The E0 bottom thermal boundary
is an engineering-prior verification closure.

## E0 claim boundary

Passing E0 can support only:

> A source-traceable, topology-explicit Qiu-inspired x-z electro-thermal-
> hysteresis-RC finite-volume implementation satisfies its preregistered
> manufactured, interface, conservation, refinement, and reduction checks.

It cannot support real-device calibration, exact Qiu trace reproduction,
experimental validation, inverse recovery, PINN fidelity, or a `gamma_eff`
mapping. Any hard-gate failure blocks M41.
