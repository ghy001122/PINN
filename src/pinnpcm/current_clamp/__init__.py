"""Ideal-current-clamp research components.

The namespace is independent of the retired dynamic solver/controller routes.
CC-A remains immutable evidence; the separately authorized CC-B namespace
implements the bounded algebraic conductive-current 2.5D gate.
"""

from pinnpcm.current_clamp.contract import (
    CurrentClampContractError,
    load_current_clamp_contract,
)
from pinnpcm.current_clamp.cc_b_contract import CCBContractError, load_cc_b_contract

__all__ = [
    "CCBContractError",
    "CurrentClampContractError",
    "load_cc_b_contract",
    "load_current_clamp_contract",
]
