# Current Research Handoff

Resume in this order:

1. `CODEX_CONTEXT.md`
2. `PROJECT_STATE.md`
3. `docs/research_strategy/active_phase.md`
4. `NEXT_ACTIONS.md`
5. `docs/project_state/current_evidence_index.md`
6. `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`
7. `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`
8. `configs/geophase_phase1_v2_s2_reference.yaml`
9. `configs/geophase_phase1_v2_formal_manifest.yaml`
10. `configs/qiu_vo2_phase1_source_contract.yaml`

Current phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`. Current checkpoint:
`PHASE1_V2_S2_PREREGISTERED_PENDING_IMPLEMENTATION`.

The fixed-bottom material-stack/K-state route ended at v8
`NO_GO_VERTICAL_REFERENCE`. Its 96-item manifest remains immutable and
`planned_not_executed`; formal count is zero.

Phase 1-v2 makes S2 nominal: real VO2 x-y plane, explicit VO2 plus mask-local
Ti/Au thermal terms, and area-normalized Qiu device-level uniform-mode
\(G_\theta,C_\theta\). It has no independent vertical state. Its 63 items are
unexecuted.

After the anchor is pushed: implement/test S2 and run bounded non-voting
smoke. A <=4 h same-device source audit and <=24 h active/48 h elapsed S1 MVE
may run in parallel but cannot delay/replace S2. S1 is sensitivity only.

No formal campaign, PINN/inverse, source fitting/digitization, nonzero
coupling, Phase 2 data, 3D/FEM, M44, or NbO2 is authorized. Correct S2 physics,
conservation, or convergence failure triggers the `gamma_sub`/identifiability
downgrade.

Frozen GT and historical evidence remain unchanged. Archives are provenance,
not execution authority.
