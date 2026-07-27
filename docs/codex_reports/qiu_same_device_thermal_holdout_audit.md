# Bounded same-device thermal-holdout audit

## Disposition

```text
no_eligible_holdout_found_within_bounded_audit
```

The audit found no public observation satisfying all locked requirements:

- the same physical Qiu device, or an explicit one-to-one source link to it;
- a direct temperature transient, multi-frequency thermal impedance/admittance,
  or isolatable thermal pulse/ringdown response;
- at least two independent observations or windows; and
- discrimination between S1 and S2 without refitting electrical or phase
  parameters.

Accordingly, Phase 1-v2 retains S2 as its nominal closure. S1 remains a
non-blocking model-form sensitivity even if its self-consistency MVE passes.
No digitization, ingestion, or model selection was triggered.

## Sources inspected

1. Erbin Qiu, Yuan-Hang Zhang, Massimiliano Di Ventra, and Ivan K. Schuller,
   “Reconfigurable Cascaded Thermal Neuristors for Neuromorphic Computing,”
   *Advanced Materials* 36, 2306818 (2024), DOI
   [10.1002/adma.202306818](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adma.202306818).
   The [combined preprint and supporting information](https://arxiv.org/pdf/2307.11256)
   and [OSTI author manuscript](https://www.osti.gov/servlets/purl/2575760)
   were also checked. Main Fig. 1C is quasistatic resistance-temperature
   hysteresis. Main Fig. 2A-D reports terminal current/frequency; Fig. 2E is a
   simulated internal quantity. None is a direct thermal-kernel holdout.
2. The [official supporting information](https://advanced.onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1002%2Fadma.202306818&file=adma202306818-sup-0001-SuppMat.pdf)
   was checked at Eqs. S5-S7 and Figs. S1-S4. The locked thermal coefficients
   arise in the compact electrothermal fit itself, while the plotted dynamic
   observations are electrical. Reuse would therefore be self-validation.
3. Yuan-Hang Zhang et al., “Collective dynamics and long-range order in thermal
   neuristor networks,” *Nature Communications* 15, 6986 (2024), DOI
   [10.1038/s41467-024-51254-4](https://www.nature.com/articles/s41467-024-51254-4),
   including [Zenodo record 13119587](https://zenodo.org/records/13119587) and
   its public code/data repository. The experiment files are electrical; the
   temperature dynamics are model variables, and no one-to-one identity with
   the locked Qiu device is established.
4. Erbin Qiu, *Collective Dynamics in Coupled Spiking Oscillators*, UC San
   Diego dissertation (2024), [eScholarship record](https://escholarship.org/uc/item/770794wz),
   Chapter 5 and Appendix C. These reproduce the paper and supporting material
   without a new direct thermal response.
5. Erbin Qiu et al., “Stochastic transition in synchronized spiking
   nanooscillators,” *PNAS* 120, e2303765120 (2023), DOI
   [10.1073/pnas.2303765120](https://pmc.ncbi.nlm.nih.gov/articles/PMC10515151/).
   This is a different coupled-device experiment and any temperature estimate
   is indirect/model-dependent.
6. The APS March Meeting 2024 abstract
   [“Thermal neuristors for computing”](https://meetings-archive.aps.org/mar/2024/g13/3/)
   contains no additional numeric direct thermal response.

The Wiley data-availability statement permits a request to the corresponding
author, but the public record does not identify a qualifying data object.
External contact was not authorized and would not be allowed to block S2.

## Timing metadata

The delegated audit did not create a run registry at launch. Exact UTC start,
finish, and wall-clock values are therefore recorded as null rather than
reconstructed from chat or file timestamps. This limits only the timing audit;
it does not change the eligibility disposition.

## Claim boundary

Allowed:

> This bounded primary-source audit did not find an eligible same-device direct
> thermal holdout.

Forbidden:

- such data do not exist;
- independent thermal validation was completed;
- S1 is more accurate than S2;
- terminal current, a threshold, or one oscillation frequency selects S1;
- a Qiu thermal impedance was recovered.
