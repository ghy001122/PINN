# M44 Qiu-scale heterogeneous thermal contract

## Scope

M44 is a small-signal, constant-property, sensible-heat component study. Its
geometric scale is anchored to Qiu et al., *Advanced Materials* 36, 2306818
(2024), DOI `10.1002/adma.202306818`; it is not a calibrated Qiu replica.

The source reports a 100 nm by 500 nm VO2 footprint, 100 nm VO2 thickness,
15 nm Ti and 40 nm Au electrodes on an Al2O3 substrate. Substrate truncation,
electrode overlap, local heat generation, local thermal properties and every
thermal boundary resistance remain unresolved by that source.

## Governing equation

For each active control volume,

\[
\rho c_p\frac{\partial T}{\partial t}
=\nabla\cdot(k\nabla T)+\dot q,
\]

with SI units. A face between cells \(i,j\) has conductance

\[
G_{ij}=\frac{A_f}{d_i/(2k_i)+R''_{ij}+d_j/(2k_j)}.
\]

The voting baseline sets \(R''_{ij}=0\). Symmetry and exposed surfaces are
adiabatic. The remote x/y/bottom faces are fixed at \(T_0\). Input power,
remote outflow, and sensible storage are integrated independently from the
source vector, boundary conductances, and cell capacities.

## Geometry responsibility

| Quantity | Value | Provenance | Voting role |
| --- | ---: | --- | --- |
| VO2 current-path length | 100 nm | Qiu-reported footprint; x-axis assignment literature-derived | voting |
| VO2 width | 500 nm | Qiu-reported footprint; y-axis assignment literature-derived | voting |
| VO2 thickness | 100 nm | Qiu-reported | voting |
| Ti thickness | 15 nm | Qiu-reported | voting |
| Au thickness | 40 nm | Qiu-reported | voting |
| substrate lateral/depth truncation | diffusion-length ladder | engineering prior; numerical-domain quantity | voting convergence ladder |
| contact support | 20% of each half x-axis | engineering prior in locked 10--30% family; axis is not Qiu-reported | voting nominal family only |
| electrode overlap beyond contact support | unresolved | not reported | excluded |

## Material responsibility

| Material | \(k\) (W m\(^{-1}\) K\(^{-1}\)) | \(\rho c_p\) (J m\(^{-3}\) K\(^{-1}\)) | Separate \(\rho,c_p\) | Provenance | Voting |
| --- | ---: | ---: | --- | --- | --- |
| VO2 | 4.0 | 3.07e6 | unresolved / not factorized | Qiu SI quotes capacity at 336 K; \(k\) is a locked in-range branch from Kizuka et al., DOI `10.7567/JJAP.54.053201` | yes, literature-scale family only |
| Ti | 21.9 | 2.35e6 | unresolved / not used | engineering prior; not reported by Qiu | yes, nuisance prior |
| Au | 317.0 | 2.49e6 | unresolved / not used | engineering prior; thin-film values are process dependent | yes, nuisance prior |
| Al2O3 | 35.0 | 3.0e6 | unresolved / not used | \(k\) lies in a non-orientation-matched sapphire literature bracket; capacity is an engineering prior inherited from M43 | yes, component prior |

These values define a bounded numerical family, not measured device
parameters. Temperature dependence, anisotropy, phase fraction and latent heat
are excluded. The correct wording is "latent heat is outside the validated
scope," not "latent heat is physically zero."

## Independent limits

1. Homogeneous limit: setting every active cell to the M43 Al2O3 component and
   applying the registered surface isoflux must recover M43 steady Eq. 21 and
   transient Green impedance within 2%.
2. Layered 1D limit: making the stack laterally uniform with adiabatic sides
   must recover the analytic series resistance and an independently assembled,
   exact-in-time modal 1D finite-element reference within 2%. The reference
   must first recover a single-slab analytic series and self-refine within 0.2%.

The 1D reference never imports the 3D grid, matrix, source assembly or time
integrator.

## Source and observation responsibility

M42 proves that port resistance cannot identify a unique local conductivity or
contact heat map. M44 therefore compares three equal-power hypotheses rather
than inferring Joule heat: bulk VO2, symmetric x-end/contact VO2 engineering
prior, and a 50/50 mixture. Qiu does not uniquely assign footprint axis or
contact support, so no source-family outcome is a unique Qiu kernel. The M43
full-footprint surface isoflux remains a solver anchor only.

The primary observable is VO2-volume-mean impedance. `Tmax` is secondary and
may abstain when a localized source prevents convergence. A resolved x-z/3D
bias above 10% forbids x-z quantitative use; it does not constitute a 3D solver
failure and cannot be repaired by one scalar factor over all time.
