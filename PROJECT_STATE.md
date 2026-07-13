# Project State

## Authoritative Current Snapshot

This top-level snapshot is the only current-state authority in this file. Archived histories and old reports are evidence records, not authorization to resume an old phase.

- Current phase: `control-volume multidomain OASIS and inverse repair v10`.
- Delivery mode: `Q2_SCI_DELIVERY_MODE`.
- Main manuscript line: calibration-gated constrained `gamma_sub` inverse under fixed or tightly bounded priors in a 1D synthetic numerical digital twin.
- Extension line: OASIS multilayer physics, segmented terminals, strict CV neural training, active inverse, stiffness, and observability audits.
- Frozen GT v1.1: unchanged and read-only.
- Experimental validation: absent.

## Current Gate Ledger

| Gate | Status | Evidence boundary |
|---|---|---|
| P0 physical semantics | `qualified_supported` | Reduced synthetic topology/material implementation only. |
| P1 CV multidomain neural training | `failed_but_informative` | `E_T=0.37563055753707886`, `E_m=0.06811526417732239`, interface residual `106.15460205078125`, success rate `0.0`. |
| P2 noisy active inverse | `failed_but_informative` | Local/material-specific blocks only; thermal, rank, and coverage gates fail. |
| P3 segmented-terminal y-z forward | `qualified_supported` | Forward/current integration and local rank gain `1` to `3`; no field recovery. |
| P4 STL/Fourier/F-SPS | `forbidden` as positive claim | Experiment blocked by failed P1; exploration remains allowed after gate repair. |
| External experimental validation | `forbidden` | No measured dataset with provenance exists. |

## Stable Evidence Chain

1. Frozen GT v1.1 provides the common synthetic benchmark.
2. v0/v1/v1.1 showed field-anchor dependence and persistent temperature error.
3. Identifiability audits showed terminal conductance does not uniquely determine all hidden fields.
4. Constrained `gamma_sub` audits support a reduced target only under fixed/tight priors; `T_sw` is the dominant confounder.
5. Protocol, noise, prior-width, response-surface, off-grid, and calibration audits define the supported region and its limitations.
6. F-SPS/Fourier/STL audits remain method-development or negative evidence, not main claims.
7. OASIS v10 improves physical topology and segmented-terminal forward modeling, while strict neural training and full inverse claims remain unresolved.

## Current Priority And Blockers

Highest priority: P1 scaling, boundary-face/local-coordinate consistency, and staged optimization repair. Blockers are interface residual scale, inconsistent boundary coordinate semantics, field-anchor dependence, rank-deficient protocol selection, weak thermal identifiability, and absent external quantitative validation.

## Historical Record

The previous cumulative state file is preserved verbatim at `docs/archive/project_state/project_state_pre_v10.md`. Chronological detail remains in `RESEARCH_LOG.md`, registries, reports, and the canonical handoff. Historical sections must not override this snapshot.
