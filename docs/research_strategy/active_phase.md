# Active Phase

Active phase ID: `D_EXTERNAL_ANCHOR`

## Current Phase

`Q2 SCI delivery - Priority D provenance-backed external quantitative anchor`

This is a bounded external-literature evidence phase. It does not authorize changes to frozen GT v1.1, unclear-provenance data, post-hoc success thresholds, a new manuscript core line, or wording that converts literature data into measurements performed by this project.

## Manuscript Use

Close one Must-have submission gap by comparing a declared reduced model against at least one trace used for fitting and one independent trace or branch held out from fitting. The allowed result label is `external literature-curve validation`, never experimental validation of the repository model.

## Single Active Bottleneck

Priority D: establish one provenance-complete quantitative anchor. The primary candidate is the open-access VO2 thermal-neuristor article by Zhang, Sipling, Qiu et al., Nature Communications 15, 6986 (2024), DOI `10.1038/s41467-024-51254-4`, because the publisher provides source data, supplementary information, code provenance, and a CC BY 4.0 license.

The Slesazeck et al. NbO2 Frenkel-Poole paper, DOI `10.1039/C5RA19300A`, is a material-mechanism fallback. The SnSe/NbO2 source and exact parameter set quoted by the external review are not authorized until the exact primary paper, figure/table, units, and reuse terms are identified.

Required evidence chain:

```text
source identity/license -> immutable raw/source-data file + SHA-256 -> provenance registry -> extraction/normalization config -> fit/holdout implementation -> tests -> JSON/CSV -> comparison figure/table -> report -> claim matrix -> manuscript sentence
```

## Predeclared Completion Gate

A positive VO2 literature-family external-anchor result requires all conditions:

- DOI/version, authors, material, device topology, figure or source-data identifier, units, access date, license/reuse terms, extraction method, and raw-file SHA-256 are recorded;
- raw external data are stored under `data/external/` and are never overwritten by processed values;
- at least one curve/branch/protocol is used for calibration and at least one distinct curve/branch/protocol is held out;
- the holdout is not used for parameter selection, normalization tuning, or threshold selection;
- normalized RMSE is `<= 0.20` for both fit and holdout traces, and any reported threshold, holding, or spike-frequency feature has relative error `<= 0.20`;
- uncertainty from digitization or source-data precision is reported;
- a CPU reproduction test verifies provenance schema, split isolation, metric recomputation, and unchanged frozen GT.

These are manuscript gates, not claims about universal device accuracy.

## Failure Interpretation And Claim Boundary

If provenance closes but the quantitative gate fails, the result is `failed_but_informative` and may support a model-family limitation. If provenance, units, license, or holdout isolation is incomplete, external validation remains `forbidden`.

Allowed wording after a pass: the declared reduced VO2 model reproduces specified literature curves within the declared metric and holdout protocol.

Forbidden wording: this project experimentally validates VO2/NbO2 devices; the anchor validates the frozen Nb/NbOx/V2O5/Ni-inspired benchmark; literature-fit parameters are universal material constants; a VO2/SnSe stack was reproduced; or a fit to one curve proves cross-material/general device validity.

## Locked Cross-Gate Context

- Priority A constrained `gamma_sub` evidence lock: `supported` as evidence assembly; commit `d1121e16fa5015a297da468e3e6f0504b9e97d17`.
- P0: `qualified_supported` reduced physical semantics.
- P1: `failed_but_informative`; baseline `E_T=0.37563055753707886`, `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success `0.0`; it is a field-anchored synthetic cross-family method benchmark and is queued for one bounded repair cycle.
- P2: `failed_but_informative`; thermal, full-rank protocol, and coverage gates fail.
- P3: `qualified_supported` segmented y-z forward/local observability in a three-parameter basis only; no device-level field inverse.
- P4: blocked; positive STL/Fourier/F-SPS claims remain `forbidden` until P1 passes.

## Next Decision

Stop after the first provenance-complete fit/holdout anchor is dispositioned. A pass moves the result into the manuscript and activates Priority M complete-manuscript assembly. A quantitative failure is preserved and may trigger one predeclared fallback source; an unresolved provenance failure requires user direction rather than silent substitution.
