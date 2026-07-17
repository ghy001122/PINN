# N0-CV-E v3 evidence-semantics amendment

This addendum does not overwrite the b380 machine result, report, or absent checkpoint. The historical status remains `failed_but_informative`, but its precise substatus is `runtime_abort_unassessed`; because no scored `pinn_predicted` trajectory survived, it is not a scientific falsification of the frozen model.

The statement that 1200 Adam steps completed is derived from the locked four-stage configuration and the fact that control reached the L-BFGS block. Original stdout, stderr, full traceback, stage history, and per-step telemetry are absent. This limitation is now explicit rather than reconstructed as direct runtime evidence.

The historical “unified rescore” is renamed `counterfactual_projected_state_rescore`. It takes legacy checkpoint `c_v/T/m` states and projects them through the later analytic electrical head. Consequently, near-zero current spread and zero shared-face flux are properties of that projection, not the legacy model's original end-to-end learned performance. Its NumPy saved-state gradient residual is also not directly comparable to the v3 JVP residual.

For v3r, `sigma*E=J`, analytic-head current continuity, and equal-and-opposite shared-face conservation are structural invariants and do not vote for learned success. Interface state is scored from one-sided reconstructed face traces rather than an adjacent-cell-centre jump. Interface flux is split into a structural shared-face invariant and score-only predicted-versus-frozen-GT face-flux accuracy.

The gate evaluator now fails closed on missing expected keys, empty mappings or lists, and any non-finite numeric leaf; Python's vacuous `all(empty)` cannot authorize a pass.
