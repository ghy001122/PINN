"""Device-effective VO2 closure locked by the Phase 1 source contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit


@dataclass(frozen=True)
class EffectiveVO2Closure:
    length_m: float
    width_m: float
    thickness_m: float
    resistance_prefactor_ohm: float
    metallic_resistance_ohm: float
    activation_temperature_K: float
    sigma_metallic_S_m: float
    T_c_up_K: float
    T_c_down_K: float
    transition_width_K: float
    state_relaxation_s: float
    branch_relaxation_s: float
    branch_rate_scale_K_s: float
    temperature_min_K: float
    temperature_max_K: float

    @classmethod
    def from_config(cls, config: dict) -> "EffectiveVO2Closure":
        conductivity = config["parameter_contract"]["vo2_conductivity"]
        phase = config["parameter_contract"]["vo2_phase_shape"]
        validity = config["parameter_contract"]["validity"]["temperature_K"]
        return cls(
            length_m=float(conductivity["effective_current_path_m"]),
            width_m=float(conductivity["effective_width_m"]),
            thickness_m=float(conductivity["active_thickness_m"]),
            resistance_prefactor_ohm=float(
                conductivity["source_resistance_prefactor_ohm"]
            ),
            metallic_resistance_ohm=float(
                conductivity["source_metallic_resistance_ohm"]
            ),
            activation_temperature_K=float(
                conductivity["source_activation_temperature_K"]
            ),
            sigma_metallic_S_m=float(conductivity["sigma_met_ref_S_m"]),
            T_c_up_K=float(phase["T_c_up_K"]),
            T_c_down_K=float(phase["T_c_down_K"]),
            transition_width_K=float(phase["transition_width_K"]),
            state_relaxation_s=float(phase["state_relaxation_s"]),
            branch_relaxation_s=float(phase["branch_relaxation_s"]),
            branch_rate_scale_K_s=float(phase["branch_rate_scale_K_s"]),
            temperature_min_K=float(validity[0]),
            temperature_max_K=float(validity[1]),
        )

    @property
    def cross_section_m2(self) -> float:
        return self.width_m * self.thickness_m

    def validate_temperature(self, temperature_K: np.ndarray | float) -> np.ndarray:
        temperature = np.asarray(temperature_K, dtype=float)
        if not np.isfinite(temperature).all():
            raise ValueError("temperature must be finite")
        if np.any(temperature < self.temperature_min_K) or np.any(
            temperature > self.temperature_max_K
        ):
            raise ValueError("temperature is outside the locked VO2 validity range")
        return temperature

    def insulating_conductivity_S_m(
        self, temperature_K: np.ndarray | float
    ) -> np.ndarray:
        temperature = self.validate_temperature(temperature_K)
        resistance = self.resistance_prefactor_ohm * np.exp(
            self.activation_temperature_K / temperature
        ) + self.metallic_resistance_ohm
        return self.length_m / (self.cross_section_m2 * resistance)

    def transition_temperature_K(self, branch_memory: np.ndarray | float) -> np.ndarray:
        branch = np.asarray(branch_memory, dtype=float)
        if not np.isfinite(branch).all() or np.any(np.abs(branch) > 1.0 + 1.0e-12):
            raise ValueError("branch memory must be finite and inside [-1, 1]")
        return 0.5 * (1.0 + branch) * self.T_c_up_K + 0.5 * (
            1.0 - branch
        ) * self.T_c_down_K

    def equilibrium_state(
        self,
        temperature_K: np.ndarray | float,
        branch_memory: np.ndarray | float,
    ) -> np.ndarray:
        temperature = self.validate_temperature(temperature_K)
        threshold = self.transition_temperature_K(branch_memory)
        return expit((temperature - threshold) / self.transition_width_K)

    def conductivity_S_m(
        self,
        temperature_K: np.ndarray | float,
        conductive_state: np.ndarray | float,
    ) -> np.ndarray:
        temperature = self.validate_temperature(temperature_K)
        state = np.asarray(conductive_state, dtype=float)
        if not np.isfinite(state).all() or np.any(state < -1.0e-12) or np.any(
            state > 1.0 + 1.0e-12
        ):
            raise ValueError("conductive-state coordinate must be inside [0, 1]")
        insulating = self.insulating_conductivity_S_m(temperature)
        state = np.clip(state, 0.0, 1.0)
        return np.exp(
            (1.0 - state) * np.log(insulating)
            + state * np.log(self.sigma_metallic_S_m)
        )

    def branch_rate_drive(
        self,
        new_temperature_K: np.ndarray,
        old_temperature_K: np.ndarray,
        dt_s: float,
    ) -> np.ndarray:
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")
        new = np.asarray(new_temperature_K, dtype=float)
        old = np.asarray(old_temperature_K, dtype=float)
        return np.tanh((new - old) / (dt_s * self.branch_rate_scale_K_s))

    def branch_activations(
        self,
        new_temperature_K: np.ndarray,
        old_temperature_K: np.ndarray,
        dt_s: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return C1 one-sided heating/cooling activations.

        Squared positive parts vanish with zero temperature rate, preserve a
        stationary branch exactly, and drive the bounded branch coordinate
        only in the physically indicated direction.
        """

        drive = self.branch_rate_drive(
            new_temperature_K, old_temperature_K, dt_s
        )
        return np.maximum(drive, 0.0) ** 2, np.maximum(-drive, 0.0) ** 2
