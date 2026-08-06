"""Ideal-current-clamp research components.

The namespace is independent of the retired dynamic solver/controller routes.
Only the bounded zero-dimensional CC-A admission gate is active in Batch 1.
"""

from pinnpcm.current_clamp.contract import (
    CurrentClampContractError,
    load_current_clamp_contract,
)

__all__ = ["CurrentClampContractError", "load_current_clamp_contract"]
