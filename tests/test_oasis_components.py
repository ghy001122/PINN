from __future__ import annotations

import torch

from pinnpcm.pinn.oasis_components import (
    ClaimGatedInverseHead,
    DifferentiablePortCircuit,
    LayerWiseNeuralField,
    LiteratureStackEncoder,
    ObservationOperator,
    StiffnessGatedTrainingController,
    generic_pcm_sigma,
    nb_o2_pf_ndr_current,
    vo2_hysteretic_rt_kernel,
)


def test_oasis_components_forward_and_backward() -> None:
    features = torch.rand(1, 4, 4)
    coords = torch.rand(6, 3, requires_grad=True)
    enc = LiteratureStackEncoder(in_dim=4, embed_dim=8)
    emb = enc(features)
    field = LayerWiseNeuralField(coord_dim=3, stack_dim=8, hidden_dim=12, layers=4)
    out = field(coords, emb)
    assert out["T"].shape == (6, 4)
    assert out["m"].min() >= 0.0 and out["m"].max() <= 1.0
    sigma = generic_pcm_sigma(out["T"], out["m"])
    assert torch.isfinite(sigma).all()
    assert torch.all(sigma > 0)
    port = DifferentiablePortCircuit()(sigma, torch.ones(6))
    obs = ObservationOperator()(port)
    loss = obs.square().mean() + sigma.mean()
    loss.backward()
    assert coords.grad is not None
    assert torch.isfinite(coords.grad).all()


def test_oasis_kernels_and_gate() -> None:
    T = torch.linspace(300.0, 360.0, 5)
    R = vo2_hysteretic_rt_kernel(T)
    I = nb_o2_pf_ndr_current(torch.ones_like(T) * 1.0e6, T)
    assert torch.isfinite(R).all() and torch.all(R > 0)
    assert torch.isfinite(I).all()
    controller = StiffnessGatedTrainingController(chi_c=2.0)
    assert controller.decide(0.05).use_fourier is True
    assert controller.decide(0.2).use_fourier is False
    head = ClaimGatedInverseHead(success_threshold=0.25)
    assert head.status(0.1) == "qualified_supported"
    assert head.status(1.0) == "forbidden"
