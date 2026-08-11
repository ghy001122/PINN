"""Latent mappers for the protocol-selected equilibrium-manifold MVE.

The module contains only train-only preprocessing and mapper definitions.  It
does not fit a POD basis, run a projection, or train a neural network.  All
neural mappers return *normalized* POD coefficients; :class:`LatentFieldCodec`
is the single path from those outputs to physical coefficients and temperature
fields.  Protocol-gated predictions use an explicit, non-trainable ramp-
direction selector.  Root labels and candidate averaging are deliberately not
part of the API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


Tensor = torch.Tensor

HEATING_DIRECTION = 1.0
COOLING_DIRECTION = -1.0
MAX_POD_RANK = 8

HISTORY_BLIND_INPUT_SCHEMA = (
    "device_voltage_V",
    "contact_overlap_m",
    "sink_amplitude",
)
PROTOCOL_INPUT_SCHEMA = (
    "device_voltage_V",
    "ramp_direction",
    "start_voltage_V",
    "contact_overlap_m",
    "sink_amplitude",
)
FORBIDDEN_SCHEMA_FIELDS = frozenset(
    {
        "root_id",
        "root_label",
        "cold_label",
        "hot_label",
        "cold_solution_label",
        "hot_solution_label",
    }
)


def _canonical_field_name(name: str) -> str:
    return str(name).strip().lower().replace("-", "_").replace(" ", "_")


def validate_feature_schema(
    feature_names: Sequence[str],
    *,
    expected_dimension: int | None = None,
    require_protocol_metadata: bool | None = None,
) -> tuple[str, ...]:
    """Validate an input schema without permitting hidden fixed-point labels.

    ``require_protocol_metadata=True`` requires an explicit direction/branch
    field and protocol start voltage.  ``False`` enforces the history-blind
    ablation by rejecting both categories.  ``None`` only applies the common
    dimensional, uniqueness, and forbidden-label checks.
    """

    names = tuple(str(name) for name in feature_names)
    canonical = tuple(_canonical_field_name(name) for name in names)
    if expected_dimension is not None and len(names) != int(expected_dimension):
        raise ValueError(
            f"feature schema must contain {int(expected_dimension)} fields, got {len(names)}"
        )
    if len(set(canonical)) != len(canonical):
        raise ValueError("feature schema contains duplicate fields")
    forbidden = set(canonical).intersection(FORBIDDEN_SCHEMA_FIELDS)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ValueError(f"fixed-point root labels are forbidden: {joined}")

    direction_names = {
        "branch",
        "branch_value",
        "direction",
        "protocol_direction",
        "ramp_direction",
    }
    start_names = {
        "protocol_start_voltage",
        "protocol_start_voltage_v",
        "start_voltage",
        "start_voltage_v",
    }
    has_direction = bool(set(canonical).intersection(direction_names))
    has_start = bool(set(canonical).intersection(start_names))
    if require_protocol_metadata is True and not (has_direction and has_start):
        raise ValueError(
            "protocol-conditioned inputs require ramp direction and start voltage"
        )
    if require_protocol_metadata is False and (has_direction or has_start):
        raise ValueError("history-blind inputs may not contain protocol metadata")
    return names


# Short alias used by experiment code and focused schema tests.
validate_schema = validate_feature_schema


@dataclass(frozen=True)
class TrainOnlyNormalization:
    """Feature normalization fitted exclusively from named training samples."""

    mean: np.ndarray
    scale: np.ndarray
    feature_names: tuple[str, ...]
    train_sample_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        mean = np.asarray(self.mean, dtype=np.float64).copy()
        scale = np.asarray(self.scale, dtype=np.float64).copy()
        names = validate_feature_schema(
            self.feature_names, expected_dimension=int(mean.size)
        )
        sample_ids = tuple(str(value) for value in self.train_sample_ids)
        if mean.ndim != 1 or scale.shape != mean.shape:
            raise ValueError("normalization mean and scale must be matching vectors")
        if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(scale)):
            raise ValueError("normalization statistics must be finite")
        if np.any(scale <= 0.0):
            raise ValueError("normalization scales must be strictly positive")
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise ValueError("training sample IDs must be non-empty and unique")
        mean.setflags(write=False)
        scale.setflags(write=False)
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "feature_names", names)
        object.__setattr__(self, "train_sample_ids", sample_ids)

    @property
    def dimension(self) -> int:
        return int(self.mean.size)

    def transform_numpy(self, values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        if array.ndim != 2 or array.shape[1] != self.dimension:
            raise ValueError(
                f"normalization inputs must have shape [batch, {self.dimension}]"
            )
        if not np.all(np.isfinite(array)):
            raise ValueError("normalization inputs must be finite")
        return (array - self.mean) / self.scale

    def transform_tensor(self, values: Tensor) -> Tensor:
        if values.ndim != 2 or values.shape[1] != self.dimension:
            raise ValueError(
                f"normalization inputs must have shape [batch, {self.dimension}]"
            )
        values64 = values.to(dtype=torch.float64)
        if not bool(torch.all(torch.isfinite(values64)).item()):
            raise ValueError("normalization inputs must be finite")
        mean = torch.as_tensor(self.mean, dtype=torch.float64, device=values.device)
        scale = torch.as_tensor(self.scale, dtype=torch.float64, device=values.device)
        return (values64 - mean) / scale

    def inverse_numpy(self, normalized_values: np.ndarray) -> np.ndarray:
        array = np.asarray(normalized_values, dtype=np.float64)
        if array.ndim != 2 or array.shape[1] != self.dimension:
            raise ValueError(
                f"normalized inputs must have shape [batch, {self.dimension}]"
            )
        return self.mean + self.scale * array


def fit_train_only_normalization(
    train_values: np.ndarray,
    train_sample_ids: Sequence[str],
    *,
    feature_names: Sequence[str],
    forbidden_sample_ids: Sequence[str] = (),
    scale_floor: float = 1.0e-15,
) -> TrainOnlyNormalization:
    """Fit mean/std statistics and explicitly reject named holdout leakage."""

    values = np.asarray(train_values, dtype=np.float64)
    sample_ids = tuple(str(value) for value in train_sample_ids)
    forbidden_ids = {str(value) for value in forbidden_sample_ids}
    names = validate_feature_schema(
        feature_names, expected_dimension=values.shape[1] if values.ndim == 2 else None
    )
    if values.ndim != 2 or values.shape[0] != len(sample_ids):
        raise ValueError("training values and sample IDs must have matching rows")
    if values.shape[0] == 0:
        raise ValueError("at least one training sample is required")
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("training sample IDs must be unique")
    leaked = set(sample_ids).intersection(forbidden_ids)
    if leaked:
        joined = ", ".join(sorted(leaked))
        raise ValueError(f"holdout samples entered train-only normalization: {joined}")
    if not np.all(np.isfinite(values)):
        raise ValueError("training inputs must be finite")
    if not np.isfinite(scale_floor) or scale_floor <= 0.0:
        raise ValueError("scale_floor must be finite and strictly positive")
    mean = np.mean(values, axis=0)
    scale = np.std(values, axis=0, ddof=0)
    scale = np.where(scale > float(scale_floor), scale, 1.0)
    return TrainOnlyNormalization(
        mean=mean,
        scale=scale,
        feature_names=names,
        train_sample_ids=sample_ids,
    )


def degree2_feature_count(input_dimension: int) -> int:
    dimension = int(input_dimension)
    if dimension <= 0:
        raise ValueError("input dimension must be positive")
    return 1 + dimension + dimension * (dimension + 1) // 2


def polynomial_degree2_features(values: np.ndarray | Tensor) -> np.ndarray | Tensor:
    """Return ``[1, x_i, x_i*x_j (i <= j)]`` in deterministic order."""

    if isinstance(values, torch.Tensor):
        squeeze = values.ndim == 1
        matrix = values.unsqueeze(0) if squeeze else values
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValueError("polynomial inputs must have shape [batch, features]")
        matrix = matrix.to(dtype=torch.float64)
        columns: list[Tensor] = [
            torch.ones((matrix.shape[0], 1), dtype=torch.float64, device=matrix.device),
            matrix,
        ]
        products = [
            (matrix[:, i] * matrix[:, j]).unsqueeze(1)
            for i in range(matrix.shape[1])
            for j in range(i, matrix.shape[1])
        ]
        result = torch.cat([*columns, *products], dim=1)
        return result.squeeze(0) if squeeze else result

    array = np.asarray(values, dtype=np.float64)
    squeeze = array.ndim == 1
    matrix = array[None, :] if squeeze else array
    if matrix.ndim != 2 or matrix.shape[1] == 0:
        raise ValueError("polynomial inputs must have shape [batch, features]")
    columns_np = [np.ones((matrix.shape[0], 1), dtype=np.float64), matrix]
    products_np = [
        (matrix[:, i] * matrix[:, j])[:, None]
        for i in range(matrix.shape[1])
        for j in range(i, matrix.shape[1])
    ]
    result_np = np.concatenate([*columns_np, *products_np], axis=1)
    return result_np[0] if squeeze else result_np


# Explicit name retained for callers that spell out the fixed ridge contract.
fixed_degree2_polynomial_features = polynomial_degree2_features


@dataclass(frozen=True)
class ClosedFormPolynomialRidge:
    """Closed-form degree-two ridge mapper for normalized POD coefficients."""

    weights: np.ndarray
    regularization_lambda: float
    input_dimension: int
    design_condition_number: float

    def __post_init__(self) -> None:
        weights = np.asarray(self.weights, dtype=np.float64).copy()
        expected = degree2_feature_count(self.input_dimension)
        if weights.ndim != 2 or weights.shape[0] != expected:
            raise ValueError(
                f"ridge weights must have shape [{expected}, output_dimension]"
            )
        if weights.shape[1] <= 0 or not np.all(np.isfinite(weights)):
            raise ValueError("ridge weights must be finite with nonzero output rank")
        if not np.isfinite(self.regularization_lambda) or self.regularization_lambda < 0:
            raise ValueError("ridge lambda must be finite and non-negative")
        weights.setflags(write=False)
        object.__setattr__(self, "weights", weights)

    @property
    def output_dimension(self) -> int:
        return int(self.weights.shape[1])

    def predict_normalized(self, normalized_inputs: np.ndarray | Tensor) -> np.ndarray | Tensor:
        design = polynomial_degree2_features(normalized_inputs)
        if isinstance(design, torch.Tensor):
            weights = torch.as_tensor(
                self.weights, dtype=torch.float64, device=design.device
            )
            return design @ weights
        return design @ self.weights


def fit_closed_form_degree2_ridge(
    normalized_train_inputs: np.ndarray,
    normalized_train_coefficients: np.ndarray,
    *,
    regularization_lambda: float = 1.0e-8,
) -> ClosedFormPolynomialRidge:
    """Fit the frozen polynomial ridge contract with an unpenalized intercept."""

    inputs = np.asarray(normalized_train_inputs, dtype=np.float64)
    targets = np.asarray(normalized_train_coefficients, dtype=np.float64)
    if inputs.ndim != 2 or targets.ndim != 2 or inputs.shape[0] != targets.shape[0]:
        raise ValueError("ridge inputs and coefficient targets must be matching matrices")
    if inputs.shape[0] == 0 or inputs.shape[1] == 0 or targets.shape[1] == 0:
        raise ValueError("ridge fit requires non-empty inputs and coefficient targets")
    if not np.all(np.isfinite(inputs)) or not np.all(np.isfinite(targets)):
        raise ValueError("ridge fit arrays must be finite")
    lam = float(regularization_lambda)
    if not np.isfinite(lam) or lam < 0.0:
        raise ValueError("ridge lambda must be finite and non-negative")
    design = np.asarray(polynomial_degree2_features(inputs), dtype=np.float64)
    penalty = np.eye(design.shape[1], dtype=np.float64)
    penalty[0, 0] = 0.0
    gram = design.T @ design + lam * penalty
    weights = np.linalg.solve(gram, design.T @ targets)
    return ClosedFormPolynomialRidge(
        weights=weights,
        regularization_lambda=lam,
        input_dimension=int(inputs.shape[1]),
        design_condition_number=float(np.linalg.cond(gram)),
    )


fit_closed_form_ridge = fit_closed_form_degree2_ridge


# Stable experiment-facing names.  Every normalization instance retains the
# exact training-sample IDs used to derive its statistics.
InputNormalization = TrainOnlyNormalization


def fit_input_normalization(
    raw_inputs: np.ndarray,
    sample_ids: Sequence[str],
    *,
    feature_names: Sequence[str] | None = None,
    forbidden_sample_ids: Sequence[str] = (),
    scale_floor: float = 1.0e-15,
) -> InputNormalization:
    """Fit train-only feature normalization with an optional holdout guard."""

    values = np.asarray(raw_inputs, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("raw inputs must have shape [batch, features]")
    names = (
        tuple(str(name) for name in feature_names)
        if feature_names is not None
        else tuple(f"x_{index}" for index in range(values.shape[1]))
    )
    return fit_train_only_normalization(
        values,
        sample_ids,
        feature_names=names,
        forbidden_sample_ids=forbidden_sample_ids,
        scale_floor=scale_floor,
    )


def normalize_inputs(
    raw_inputs: np.ndarray | Tensor,
    normalization: InputNormalization,
) -> np.ndarray | Tensor:
    """Apply one train-only normalization to NumPy or Torch inputs."""

    if isinstance(raw_inputs, torch.Tensor):
        return normalization.transform_tensor(raw_inputs)
    return normalization.transform_numpy(np.asarray(raw_inputs, dtype=np.float64))


Degree2Ridge = ClosedFormPolynomialRidge


def fit_degree2_ridge(
    normalized_train_inputs: np.ndarray,
    normalized_train_coefficients: np.ndarray,
    *,
    regularization_lambda: float = 1.0e-8,
) -> Degree2Ridge:
    return fit_closed_form_degree2_ridge(
        normalized_train_inputs,
        normalized_train_coefficients,
        regularization_lambda=regularization_lambda,
    )


def predict_degree2_ridge(
    ridge: Degree2Ridge,
    normalized_inputs: np.ndarray | Tensor,
) -> np.ndarray | Tensor:
    return ridge.predict_normalized(normalized_inputs)


class LatentFieldCodec(nn.Module):
    """Train-only POD coefficient normalization and physical field decoder."""

    def __init__(
        self,
        *,
        pod_mean_y: Tensor,
        pod_basis: Tensor,
        coefficient_center: Tensor,
        coefficient_scale: Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        super().__init__()
        mean = torch.as_tensor(pod_mean_y, dtype=torch.float64)
        basis = torch.as_tensor(pod_basis, dtype=torch.float64)
        center = torch.as_tensor(coefficient_center, dtype=torch.float64)
        scale = torch.as_tensor(coefficient_scale, dtype=torch.float64)
        if mean.ndim != 1 or basis.ndim != 2 or basis.shape[1] != mean.numel():
            raise ValueError("POD mean/basis must have shapes [cells] and [rank, cells]")
        rank = int(basis.shape[0])
        if not 1 <= rank <= MAX_POD_RANK:
            raise ValueError(f"POD rank must be in [1, {MAX_POD_RANK}]")
        if center.shape != (rank,) or scale.shape != (rank,):
            raise ValueError("coefficient normalization does not match POD rank")
        if not bool(
            torch.all(torch.isfinite(mean)).item()
            and torch.all(torch.isfinite(basis)).item()
            and torch.all(torch.isfinite(center)).item()
            and torch.all(torch.isfinite(scale)).item()
        ):
            raise ValueError("POD and coefficient-normalization arrays must be finite")
        if bool(torch.any(scale <= 0.0).item()):
            raise ValueError("coefficient scales must be strictly positive")
        if not np.isfinite(ambient_temperature_K):
            raise ValueError("ambient temperature must be finite")
        if not np.isfinite(smooth_nonnegative_beta_K) or smooth_nonnegative_beta_K <= 0:
            raise ValueError("smooth nonnegative beta must be finite and positive")

        self.rank = rank
        self.field_size = int(mean.numel())
        self.ambient_temperature_K = float(ambient_temperature_K)
        self.smooth_nonnegative_beta_K = float(smooth_nonnegative_beta_K)
        self.register_buffer("pod_mean_y", mean.detach().clone())
        self.register_buffer("pod_basis", basis.detach().clone())
        self.register_buffer("coefficient_center", center.detach().clone())
        self.register_buffer("coefficient_scale", scale.detach().clone())

    def normalize_coefficients(self, physical_coefficients: Tensor) -> Tensor:
        self._validate_coefficients(physical_coefficients)
        return (physical_coefficients - self.coefficient_center) / self.coefficient_scale

    def physical_coefficients(self, normalized_coefficients: Tensor) -> Tensor:
        self._validate_coefficients(normalized_coefficients)
        return self.coefficient_center + self.coefficient_scale * normalized_coefficients

    def decode_temperature(
        self,
        normalized_coefficients: Tensor,
        *,
        ny: int | None = None,
        nx: int | None = None,
    ) -> Tensor:
        """Decode normalized coefficients to physical temperature in kelvin."""

        coefficients = self.physical_coefficients(normalized_coefficients)
        y = self.pod_mean_y + coefficients @ self.pod_basis
        raw_rise_K = torch.expm1(y)
        beta = self.smooth_nonnegative_beta_K
        protected_rise_K = beta * F.softplus(raw_rise_K / beta)
        temperature = self.ambient_temperature_K + protected_rise_K
        if (ny is None) != (nx is None):
            raise ValueError("ny and nx must either both be provided or both be omitted")
        if ny is not None and nx is not None:
            if int(ny) * int(nx) != self.field_size:
                raise ValueError("requested grid does not match the POD field size")
            return temperature.reshape(-1, int(ny), int(nx))
        return temperature

    def _validate_coefficients(self, coefficients: Tensor) -> None:
        if coefficients.ndim != 2 or coefficients.shape[1] != self.rank:
            raise ValueError(
                f"coefficient tensor must have shape [batch, {self.rank}]"
            )


def _make_codec(
    *,
    pod_mean_y: Tensor,
    pod_basis: Tensor,
    coefficient_center: Tensor,
    coefficient_scale: Tensor,
    ambient_temperature_K: float,
    smooth_nonnegative_beta_K: float,
) -> LatentFieldCodec:
    return LatentFieldCodec(
        pod_mean_y=pod_mean_y,
        pod_basis=pod_basis,
        coefficient_center=coefficient_center,
        coefficient_scale=coefficient_scale,
        ambient_temperature_K=ambient_temperature_K,
        smooth_nonnegative_beta_K=smooth_nonnegative_beta_K,
    )


class _NormalizedLatentMapper(nn.Module):
    input_dimension: int
    hidden_width = 32

    def _finish_codec(
        self,
        *,
        pod_mean_y: Tensor,
        pod_basis: Tensor,
        coefficient_center: Tensor,
        coefficient_scale: Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        self.codec = _make_codec(
            pod_mean_y=pod_mean_y,
            pod_basis=pod_basis,
            coefficient_center=coefficient_center,
            coefficient_scale=coefficient_scale,
            ambient_temperature_K=ambient_temperature_K,
            smooth_nonnegative_beta_K=smooth_nonnegative_beta_K,
        )

    @property
    def rank(self) -> int:
        return self.codec.rank

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def physical_coefficients(self, normalized_coefficients: Tensor) -> Tensor:
        return self.codec.physical_coefficients(normalized_coefficients)

    def decode_temperature(
        self,
        normalized_coefficients: Tensor,
        *,
        ny: int | None = None,
        nx: int | None = None,
    ) -> Tensor:
        return self.codec.decode_temperature(normalized_coefficients, ny=ny, nx=nx)

    def _validate_inputs(self, normalized_inputs: Tensor) -> Tensor:
        if normalized_inputs.ndim != 2 or normalized_inputs.shape[1] != self.input_dimension:
            raise ValueError(
                f"normalized inputs must have shape [batch, {self.input_dimension}]"
            )
        return normalized_inputs.to(dtype=torch.float64)


class HistoryBlindLatentMapper(_NormalizedLatentMapper):
    """H: protocol-history-blind three-input, two-layer latent mapper."""

    input_dimension = 3
    input_schema = HISTORY_BLIND_INPUT_SCHEMA

    def __init__(
        self,
        *,
        pod_mean_y: Tensor,
        pod_basis: Tensor,
        coefficient_center: Tensor,
        coefficient_scale: Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        super().__init__()
        validate_feature_schema(
            self.input_schema,
            expected_dimension=self.input_dimension,
            require_protocol_metadata=False,
        )
        self._finish_codec(
            pod_mean_y=pod_mean_y,
            pod_basis=pod_basis,
            coefficient_center=coefficient_center,
            coefficient_scale=coefficient_scale,
            ambient_temperature_K=ambient_temperature_K,
            smooth_nonnegative_beta_K=smooth_nonnegative_beta_K,
        )
        self.network = nn.Sequential(
            nn.Linear(self.input_dimension, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, self.rank),
        )
        self.to(dtype=torch.float64)

    def forward(self, normalized_inputs: Tensor) -> Tensor:
        """Return normalized POD coefficients."""

        return self.network(self._validate_inputs(normalized_inputs))

    normalized_coefficients = forward


class ProtocolConditionedSingleHead(_NormalizedLatentMapper):
    """S: protocol-conditioned shared trunk with one rank-to-rank head."""

    input_dimension = 5
    input_schema = PROTOCOL_INPUT_SCHEMA

    def __init__(
        self,
        *,
        pod_mean_y: Tensor,
        pod_basis: Tensor,
        coefficient_center: Tensor,
        coefficient_scale: Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        super().__init__()
        validate_feature_schema(
            self.input_schema,
            expected_dimension=self.input_dimension,
            require_protocol_metadata=True,
        )
        self._finish_codec(
            pod_mean_y=pod_mean_y,
            pod_basis=pod_basis,
            coefficient_center=coefficient_center,
            coefficient_scale=coefficient_scale,
            ambient_temperature_K=ambient_temperature_K,
            smooth_nonnegative_beta_K=smooth_nonnegative_beta_K,
        )
        self.trunk = nn.Sequential(
            nn.Linear(self.input_dimension, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, self.hidden_width),
            nn.SiLU(),
        )
        self.shared_latent = nn.Linear(self.hidden_width, self.rank)
        self.output_head = nn.Linear(self.rank, self.rank)
        self.to(dtype=torch.float64)

    def forward(self, normalized_inputs: Tensor) -> Tensor:
        """Return normalized POD coefficients."""

        hidden = self.trunk(self._validate_inputs(normalized_inputs))
        return self.output_head(self.shared_latent(hidden))

    normalized_coefficients = forward


class ProtocolGatedBranchHeads(_NormalizedLatentMapper):
    """G: explicit hard-gated heating/cooling latent heads.

    The gate is selected by the separate raw ramp direction (heating ``+1``,
    cooling ``-1``), never by a trainable classifier or a fixed-point label.
    """

    input_dimension = 5
    input_schema = PROTOCOL_INPUT_SCHEMA

    def __init__(
        self,
        *,
        pod_mean_y: Tensor,
        pod_basis: Tensor,
        coefficient_center: Tensor,
        coefficient_scale: Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        super().__init__()
        validate_feature_schema(
            self.input_schema,
            expected_dimension=self.input_dimension,
            require_protocol_metadata=True,
        )
        self._finish_codec(
            pod_mean_y=pod_mean_y,
            pod_basis=pod_basis,
            coefficient_center=coefficient_center,
            coefficient_scale=coefficient_scale,
            ambient_temperature_K=ambient_temperature_K,
            smooth_nonnegative_beta_K=smooth_nonnegative_beta_K,
        )
        self.trunk = nn.Sequential(
            nn.Linear(self.input_dimension, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, self.hidden_width),
            nn.SiLU(),
        )
        self.shared_latent = nn.Linear(self.hidden_width, self.rank)
        self.heating_head = nn.Linear(self.rank, self.rank)
        self.cooling_head = nn.Linear(self.rank, self.rank)
        self.to(dtype=torch.float64)

        # This architecture is preregistered to stay within 5% of S for rank<=8.
        single_count = self._matched_single_head_parameter_count()
        difference = abs(self.parameter_count - single_count) / max(single_count, 1)
        if difference > 0.05 + 1.0e-12:
            raise ValueError("gated and single-head parameter budgets differ by over 5%")

    def _branch_outputs(self, normalized_inputs: Tensor) -> tuple[Tensor, Tensor]:
        hidden = self.trunk(self._validate_inputs(normalized_inputs))
        latent = self.shared_latent(hidden)
        return self.heating_head(latent), self.cooling_head(latent)

    def forward(self, normalized_inputs: Tensor, raw_direction: Tensor) -> Tensor:
        """Return hard-selected normalized coefficients for a mixed batch."""

        heating, cooling = self._branch_outputs(normalized_inputs)
        direction = torch.as_tensor(
            raw_direction, dtype=torch.float64, device=heating.device
        )
        if direction.ndim == 1:
            direction = direction.unsqueeze(1)
        if direction.shape != (heating.shape[0], 1):
            raise ValueError("raw_direction must have shape [batch] or [batch, 1]")
        heating_value = torch.full_like(direction, HEATING_DIRECTION)
        cooling_value = torch.full_like(direction, COOLING_DIRECTION)
        is_heating = torch.isclose(direction, heating_value, rtol=0.0, atol=1.0e-12)
        is_cooling = torch.isclose(direction, cooling_value, rtol=0.0, atol=1.0e-12)
        if not bool(torch.all(is_heating | is_cooling).item()):
            raise ValueError("raw_direction must contain only +1 heating or -1 cooling")
        return torch.where(is_heating, heating, cooling)

    normalized_coefficients = forward

    def protocol_candidates(
        self,
        heating_normalized_inputs: Tensor,
        cooling_normalized_inputs: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """Return the two explicit branch candidates without averaging them."""

        heating, _ = self._branch_outputs(heating_normalized_inputs)
        _, cooling = self._branch_outputs(cooling_normalized_inputs)
        if heating.shape != cooling.shape:
            raise ValueError("heating and cooling candidate batches must match")
        return heating, cooling

    def _matched_single_head_parameter_count(self) -> int:
        trunk = (
            self.input_dimension * self.hidden_width
            + self.hidden_width
            + self.hidden_width * self.hidden_width
            + self.hidden_width
        )
        shared = self.hidden_width * self.rank + self.rank
        head = self.rank * self.rank + self.rank
        return int(trunk + shared + head)


def matched_parameter_relative_difference(
    single_head: ProtocolConditionedSingleHead,
    gated_heads: ProtocolGatedBranchHeads,
) -> float:
    """Return the conservative parameter-count difference relative to S."""

    return abs(gated_heads.parameter_count - single_head.parameter_count) / max(
        single_head.parameter_count, 1
    )


def validate_matched_parameter_budget(
    single_head: ProtocolConditionedSingleHead,
    gated_heads: ProtocolGatedBranchHeads,
    *,
    relative_tolerance: float = 0.05,
) -> float:
    difference = matched_parameter_relative_difference(single_head, gated_heads)
    if difference > float(relative_tolerance) + 1.0e-12:
        raise ValueError(
            f"S/G parameter-count difference {difference:.6g} exceeds "
            f"the {float(relative_tolerance):.6g} budget"
        )
    return difference


@dataclass(frozen=True)
class UnknownProtocolDecision:
    """Two-candidate set or deterministic non-averaged unique representative."""

    status: str
    heating_candidate: Mapping[str, Any]
    cooling_candidate: Mapping[str, Any]
    unique_candidate: Mapping[str, Any] | None
    unique_candidate_source: str | None
    predicted_current_separation: float
    predicted_temperature_separation: float
    ambiguity_threshold: float
    candidate_averaging_used: bool = False

    def __post_init__(self) -> None:
        if self.candidate_averaging_used:
            raise ValueError("heating/cooling candidate averaging is forbidden")
        if self.status == "AMBIGUOUS_PROTOCOL":
            if self.unique_candidate is not None or self.unique_candidate_source is not None:
                raise ValueError("ambiguous protocol output may not contain a unique field")
        elif self.status == "PRACTICALLY_UNIQUE_PROTOCOL":
            if self.unique_candidate is None or self.unique_candidate_source not in {
                "heating_candidate",
                "cooling_candidate",
            }:
                raise ValueError("unique output must retain one named physical candidate")
        else:
            raise ValueError(f"unsupported unknown-protocol status: {self.status}")


def unknown_protocol_set_or_refusal(
    *,
    heating_candidate: Mapping[str, Any],
    cooling_candidate: Mapping[str, Any],
    predicted_current_separation: float,
    predicted_temperature_separation: float,
    ambiguity_threshold: float = 0.1,
) -> UnknownProtocolDecision:
    """Refuse uniqueness when either predicted branch separation reaches 0.1.

    Below the threshold, the heating candidate is retained verbatim as a
    deterministic representative; it is never averaged with the cooling field.
    """

    current = float(predicted_current_separation)
    temperature = float(predicted_temperature_separation)
    threshold = float(ambiguity_threshold)
    if not all(np.isfinite(value) for value in (current, temperature, threshold)):
        raise ValueError("unknown-protocol separations and threshold must be finite")
    if current < 0.0 or temperature < 0.0 or threshold <= 0.0:
        raise ValueError("separations must be non-negative and threshold positive")
    heating = dict(heating_candidate)
    cooling = dict(cooling_candidate)
    if max(current, temperature) >= threshold:
        return UnknownProtocolDecision(
            status="AMBIGUOUS_PROTOCOL",
            heating_candidate=heating,
            cooling_candidate=cooling,
            unique_candidate=None,
            unique_candidate_source=None,
            predicted_current_separation=current,
            predicted_temperature_separation=temperature,
            ambiguity_threshold=threshold,
        )
    return UnknownProtocolDecision(
        status="PRACTICALLY_UNIQUE_PROTOCOL",
        heating_candidate=heating,
        cooling_candidate=cooling,
        unique_candidate=heating,
        unique_candidate_source="heating_candidate",
        predicted_current_separation=current,
        predicted_temperature_separation=temperature,
        ambiguity_threshold=threshold,
    )


# Experiment-facing model names are deliberately explicit about their roles.
HistoryBlindLatentNet = HistoryBlindLatentMapper
ProtocolSingleHeadLatentNet = ProtocolConditionedSingleHead
ProtocolGatedLatentNet = ProtocolGatedBranchHeads


def validate_surrogate_schema(
    feature_names: Sequence[str],
    *,
    mode: str | None = None,
) -> tuple[str, ...]:
    """Validate H/S/G feature contracts while rejecting root-label leakage."""

    normalized_mode = None if mode is None else str(mode).strip().upper()
    if normalized_mode in {"H", "HISTORY_BLIND"}:
        return validate_feature_schema(
            feature_names,
            expected_dimension=3,
            require_protocol_metadata=False,
        )
    if normalized_mode in {"S", "G", "SINGLE", "GATED", "PROTOCOL"}:
        return validate_feature_schema(
            feature_names,
            expected_dimension=5,
            require_protocol_metadata=True,
        )
    if normalized_mode is not None:
        raise ValueError(f"unknown surrogate schema mode: {mode}")
    return validate_feature_schema(feature_names)


def decode_temperature(
    normalized_coefficients: Tensor,
    codec: LatentFieldCodec,
    *,
    ny: int | None = None,
    nx: int | None = None,
) -> Tensor:
    """Decode normalized POD coefficients through the common physical codec."""

    return codec.decode_temperature(normalized_coefficients, ny=ny, nx=nx)


def parameter_difference_fraction(
    single_head: ProtocolConditionedSingleHead,
    gated_heads: ProtocolGatedBranchHeads,
) -> float:
    return matched_parameter_relative_difference(single_head, gated_heads)


def unknown_protocol_decision(
    *,
    heating_candidate: Mapping[str, Any],
    cooling_candidate: Mapping[str, Any],
    predicted_current_separation: float,
    predicted_temperature_separation: float,
    ambiguity_threshold: float = 0.1,
) -> UnknownProtocolDecision:
    return unknown_protocol_set_or_refusal(
        heating_candidate=heating_candidate,
        cooling_candidate=cooling_candidate,
        predicted_current_separation=predicted_current_separation,
        predicted_temperature_separation=predicted_temperature_separation,
        ambiguity_threshold=ambiguity_threshold,
    )


__all__ = [
    "COOLING_DIRECTION",
    "ClosedFormPolynomialRidge",
    "Degree2Ridge",
    "FORBIDDEN_SCHEMA_FIELDS",
    "HEATING_DIRECTION",
    "HISTORY_BLIND_INPUT_SCHEMA",
    "HistoryBlindLatentMapper",
    "HistoryBlindLatentNet",
    "InputNormalization",
    "LatentFieldCodec",
    "MAX_POD_RANK",
    "PROTOCOL_INPUT_SCHEMA",
    "ProtocolConditionedSingleHead",
    "ProtocolGatedBranchHeads",
    "ProtocolGatedLatentNet",
    "ProtocolSingleHeadLatentNet",
    "TrainOnlyNormalization",
    "UnknownProtocolDecision",
    "decode_temperature",
    "degree2_feature_count",
    "fit_closed_form_degree2_ridge",
    "fit_closed_form_ridge",
    "fit_degree2_ridge",
    "fit_input_normalization",
    "fit_train_only_normalization",
    "fixed_degree2_polynomial_features",
    "matched_parameter_relative_difference",
    "normalize_inputs",
    "parameter_difference_fraction",
    "polynomial_degree2_features",
    "predict_degree2_ridge",
    "unknown_protocol_decision",
    "unknown_protocol_set_or_refusal",
    "validate_feature_schema",
    "validate_matched_parameter_budget",
    "validate_schema",
    "validate_surrogate_schema",
]
