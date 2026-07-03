# Submission Checklist

## Claim Boundary

- [ ] Every result is labeled synthetic numerical digital-twin benchmark.
- [ ] No measured experimental validation is claimed.
- [ ] Full hidden-field recovery is stated as ill-posed for port-only observations.
- [ ] `gamma_sub` recovery is stated as conditional on fixed or tightly bounded priors.
- [ ] `T_sw` is treated as the dominant confounder and calibration boundary.
- [ ] Protocol gain is described as secondary to calibration gain.
- [ ] Stiffness-continuation is described as preflight, not full STL-PINN.
- [ ] Fourier/F-SPS superiority is not claimed.
- [ ] Quasi-2D is described as extensibility and observability-boundary evidence only.

## Evidence Files

- [ ] `docs/paper/final_claim_matrix.md`
- [ ] `docs/paper/final_figure_list.md`
- [ ] `docs/paper/final_table_list.md`
- [ ] `docs/literature/drive_and_web_literature_evidence_lock.md`
- [ ] `outputs/tables/stiffness_2d_story_figure_manifest.json`
- [ ] `docs/manuscript/reviewer_defense_matrix.md`

## Before Submission

- [ ] Rebuild final figures from scripts.
- [ ] Check figure captions against forbidden claims.
- [ ] Confirm no untracked large files are staged.
- [ ] Confirm frozen Ground Truth files are unchanged.
- [ ] Run full pytest.
