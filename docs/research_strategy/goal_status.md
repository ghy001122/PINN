# Goal Status Dashboard

- Goal: `Q2_SCI_DELIVERY_MODE`
- Updated: 2026-07-14
- Evidence-lock base SHA: `e2e2669adfd66aacefacfbfceafcdfc18eafbbee`
- Evidence-lock commit SHA: `d1121e16fa5015a297da468e3e6f0504b9e97d17`
- Current review-integration base SHA: `d1121e16fa5015a297da468e3e6f0504b9e97d17`
- Active bottleneck: Priority D provenance-backed external quantitative anchor

| Workstream | Status | Distance to goal |
| --- | --- | --- |
| Frozen GT and reproducibility | `supported` | Evidence-lock commit recorded; frozen hashes/mtimes unchanged in that round. |
| Mainline constrained `gamma_sub` evidence | `qualified_supported` | Locked; Figure 2 direct recovery visualization corrected. |
| External quantitative anchor | `forbidden` as completed claim | Active; primary open-source-data candidate identified, no fit/holdout result yet. |
| Complete manuscript and supplementary | not complete | Priority M follows the anchor. |
| P0 physical semantics | `qualified_supported` | Reduced synthetic implementation only. |
| P1 neural training | `failed_but_informative` | Deferred to one bounded repair; cross-family field-anchored benchmark only. |
| P2 active inverse | `failed_but_informative` | Thermal, rank, and coverage gates fail. |
| P3 segmented forward | `qualified_supported` | Three-parameter local observability only; no device-level 2D inverse. |
| P4 STL/Fourier/F-SPS | `forbidden` as positive claim | Blocked until P1 passes. |
| GitHub CI | `forbidden` as a current claim | No `.github` workflow exists; only local test records are available. |

Current blockers: no external quantitative fit/holdout anchor; incomplete manuscript/supplement; P1 semantic/scaling/interface failure; P2 rank/thermal ambiguity; weak non-geometric OOD transfer.

Next decision: disposition one provenance-complete Qiu VO2 external anchor under the predeclared fit/holdout gate, then activate Priority M.
