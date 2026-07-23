# M44 classic-reproduction closeout matrix

This matrix closes the current reproduction responsibility without launching
new fits or forward runs. Formula identity, author-code behavior, numerical
convergence, source-curve agreement, and independent validation are separate
evidence levels.

| Source | Object | Formula | Author code | Numerics | Source curve | Independent validation | Final status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Yovanovich--Muzychka--Culham 1999, DOI `10.2514/2.6467` | rectangular isoflux half-space Eq. 21 | `supported` | `forbidden` | `qualified_supported` in M43 | n/a | `forbidden` | `qualified_supported` mathematical reference |
| Yovanovich 1997, DOI `10.2514/6.1997-2458` | transient half-space Green kernel and area average | `supported` | `forbidden` | `qualified_supported` in M43 | n/a | `forbidden` | `qualified_supported` mathematical reference |
| Qiu et al. 2024, DOI `10.1002/adma.202306818` | printed S1--S4 model and SI Fig. S1 | `supported` | `forbidden` | dual-solver `supported` | `failed_but_informative` | `forbidden` | source-equation-constrained reimplementation only |
| Zhang et al. 2024, DOI `10.1038/s41467-024-51254-4` | nominal author-code behavior and event reference | `supported` | `supported` nominally | `failed_but_informative` across step/topology changes | `failed_but_informative` (`11 V` NRMSE `0.446114`) | `forbidden` | graded/conditional boundary |
| Chen et al. 2025, DOI `10.1002/adfm.202423800` | future NbO2 trend context | `forbidden` (not run) | `forbidden` | `forbidden` (not run) | `forbidden` (not run) | `forbidden` | `forbidden` for quantitative transfer |
| Liu et al. 2024, DOI `10.1109/LED.2024.3362829` | future NbOx geometry context | `forbidden` (not run) | `forbidden` | `forbidden` (not run) | `forbidden` (not run) | `forbidden` | `forbidden` for quantitative transfer |

Qiu lacks author code, raw arrays, a complete reversal-update contract,
numeric initial conditions, and an event deadband. Its literal implementation
therefore cannot be promoted to exact author-code reproduction. The historical
`atanh` branch has a literature-supported analytic-inverse basis but violated
the locked literal-Qiu implementation contract, so E1F retains no vote. E1F-R
dual-solver parity is `2.23216159e-7`, while SI Fig. S1 current/voltage NRMSE
remain `0.353154`/`0.815643`. Zhang nominal
parity is not independent physical validation: its nominal discrete I/T/V
parity is `4.55e-14`/`1.45e-14`/`9.36e-15`, R-T parity is `4.86e-16`, and event
counts are `32/32`; however, its author-code-to-experiment 11 V NRMSE is
`0.446114`, its time-step gate fails at `0.163148`, and its perturbed event
topology changes `344 -> 343` near the audited bifurcation. The sealed 13 V remains
inaccessible. Chen and Liu use different material families and cannot supply
VO2 parameters.

Unless new author code or raw data appear, Qiu/Zhang reproduction rescue is
closed. Their locked results remain reviewer-defense evidence, not an open
parameter-tuning task.
