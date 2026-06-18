"""Import smoke tests."""

from __future__ import annotations


def test_core_imports() -> None:
    """Core modules should import without side effects."""

    import pinnpcm
    from pinnpcm import constants
    from pinnpcm.baselines.least_squares import fit_linear_least_squares
    from pinnpcm.baselines.mlp import BlackBoxMLP
    from pinnpcm.physics import conductivity, electrostatics, gt_solver, params, voltage_protocols
    from pinnpcm.pinn import losses, residuals, transforms, trainer
    from pinnpcm.pinn.network import FourierFeatureMLP
    from pinnpcm.utils import config, io, seed
    from pinnpcm.visualization import plots

    assert pinnpcm.__version__
    assert constants.K_B_EV_PER_K
    assert conductivity.mixed_conductivity
    assert electrostatics.solve_series_electrostatics
    assert gt_solver.simulate_ground_truth
    assert params.default_gt_params
    assert voltage_protocols.get_voltage_protocol
    assert FourierFeatureMLP
    assert transforms.apply_physical_transforms
    assert residuals.compute_residuals
    assert losses.total_loss
    assert trainer.PINNTrainer
    assert BlackBoxMLP
    assert fit_linear_least_squares
    assert config.load_yaml
    assert io.ensure_dir
    assert seed.seed_everything
    assert plots.save_figure
