"""Hard physical variable transforms for PINN raw outputs."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def apply_physical_transforms(
    raw: dict[str, torch.Tensor],
    params: dict[str, float],
    v_scale: float = 1.0,
) -> dict[str, torch.Tensor]:
    """Map raw network outputs to physically constrained variables."""

    t0 = torch.as_tensor(params["T0"], dtype=raw["T_raw"].dtype, device=raw["T_raw"].device)
    return {
        "phi": v_scale * raw["phi_raw"],
        "c_v": torch.sigmoid(raw["c_raw"]),
        "T": t0 + F.softplus(raw["T_raw"]),
        "m": torch.sigmoid(raw["m_raw"]),
    }
