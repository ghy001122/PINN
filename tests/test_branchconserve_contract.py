from __future__ import annotations

from pathlib import Path

import pytest

from pinnpcm.branchconserve.contract import (
    ALLOWED_BATCH1_STAGES,
    load_branchconserve_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml"


def test_contract_hashes_parent_and_keeps_batch2_closed() -> None:
    contract = load_branchconserve_contract(CONFIG, repository_root=ROOT)
    assert contract.parent_sha256 == (
        "ea668ac66c8f2f2267b059bd816a4116def086708f2f7eeded07d64a2857aff4"
    )
    assert contract.raw["batch2"]["authorized"] is False
    assert set(contract.batch1["allowed_stages"]) == ALLOWED_BATCH1_STAGES
    assert contract.raw["claim_boundary"]["batch1_scientific_vote"] is False
    assert contract.series_resistance_ohm == 12000.0


def test_candidate_biases_are_frozen_and_exclude_oscillation_label() -> None:
    contract = load_branchconserve_contract(CONFIG, repository_root=ROOT)
    candidates = contract.candidate_source_voltages_V
    assert candidates[0] == 0.5
    assert candidates[-1] == 15.8
    assert 12.5 not in candidates
    assert len(candidates) == 31


def test_batch1_authorization_fails_closed() -> None:
    contract = load_branchconserve_contract(CONFIG, repository_root=ROOT)
    contract.assert_batch1_stage_authorized("nominal_l1_smoke")
    with pytest.raises(PermissionError):
        contract.assert_batch1_stage_authorized("b2")
