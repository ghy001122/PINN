from __future__ import annotations

import torch

from pinnpcm.pinn.network import FourierPyramidEmbedding, StiffAwareMLP


def test_fourier_pyramid_embedding_shape_for_matrix_and_grid() -> None:
    emb = FourierPyramidEmbedding(in_dim=2, scales=[1.0, 2.0, 4.0], include_input=True)
    coords = torch.rand(5, 2)
    out = emb(coords)
    assert out.shape == (5, 2 + 2 * 2 * 3)
    assert torch.all(torch.isfinite(out))

    grid = torch.rand(3, 4, 2)
    grid_out = emb(grid)
    assert grid_out.shape == (3, 4, emb.out_dim)
    assert torch.all(torch.isfinite(grid_out))


def test_fourier_pyramid_embedding_is_differentiable() -> None:
    emb = FourierPyramidEmbedding(in_dim=2, scales=[1.0, 3.0], include_input=True)
    coords = torch.rand(6, 2, requires_grad=True)
    loss = emb(coords).square().mean()
    loss.backward()
    assert coords.grad is not None
    assert torch.all(torch.isfinite(coords.grad))


def test_stiff_aware_mlp_is_opt_in_and_shape_stable() -> None:
    model = StiffAwareMLP(in_dim=2, out_dim=3, hidden_dim=8, hidden_layers=1, scales=[1.0, 2.0])
    coords = torch.rand(7, 2)
    out = model(coords)
    assert out.shape == (7, 3)
    assert torch.all(torch.isfinite(out))