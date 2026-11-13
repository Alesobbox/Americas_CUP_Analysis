"""Versioned configuration management and hashing for AC75 learning pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

CONFIG_DIR = Path(__file__).resolve().parent / "configs"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "ac75_2024_v1.json"


@dataclass(frozen=True)
class SteadyWindowsConfig:
    duration_s: float = 5.0
    nonoverlapping: bool = True
    min_supported_duration_fraction: float = 0.95
    max_internal_gap_ms_telemetry: int = 1200
    max_internal_gap_ms_wind: int = 2500
    speed_eligibility_filter: bool = False


@dataclass(frozen=True)
class CausalLatencyConfig:
    modeled_latency_ms: int = 6000
    sensitivities_ms: tuple[int, ...] = (0, 6000, 12000)


@dataclass(frozen=True)
class TurnDetectionConfig:
    seed_min_rotation_deg: float = 65.0
    seed_max_duration_s: float = 18.0
    seed_reversal_tolerance_s: float = 1.5


@dataclass(frozen=True)
class RecoveryConfig:
    reference_window_offset_s: tuple[float, float] = (-7.0, -2.0)
    recovery_threshold_fraction: float = 0.95
    continuous_hold_duration_s: float = 2.0
    censor_timeout_s: float = 30.0
    straight_motion_exclusion_buffer_s: float = 5.0


@dataclass(frozen=True)
class UncertaintyConfig:
    residual_block_duration_s: float = 30.0
    residual_block_sensitivities_s: tuple[float, ...] = (15.0, 60.0)


@dataclass(frozen=True)
class NeuralTrainingConfig:
    max_threads: int = 4
    batch_size: int = 512
    max_epochs: int = 150
    early_stopping_patience: int = 15
    learning_rates: tuple[float, ...] = (0.001, 0.0003)
    weight_decays: tuple[float, ...] = (0.0001, 0.001)
    dropouts: tuple[float, ...] = (0.0, 0.1)
    screen_seed: int = 2027


@dataclass(frozen=True)
class NeuralModelConfig:
    hidden_layers: int = 2
    units_per_layer: int = 32
    activation: str = "silu"
    distribution: str = "lognormal"
    final_seeds: tuple[int, ...] = (2027, 2028, 2029)
    training: NeuralTrainingConfig = field(default_factory=NeuralTrainingConfig)


@dataclass(frozen=True)
class SplineBaselineConfig:
    regularization_grid: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0)


@dataclass(frozen=True)
class TrialCountsConfig:
    preview: int = 2000
    standard: int = 10000
    evaluation: int = 20000


@dataclass(frozen=True)
class MemoryLimitsConfig:
    max_normalized_rows_per_batch: int = 50000
    max_simulated_trials_per_batch: int = 512


@dataclass(frozen=True)
class LearningConfig:
    """Master typed configuration for AC75 learning pipeline."""
    schema_version: str = "ac75-config-1"
    config_id: str = "ac75_2024_v1"
    description: str = ""
    primary_class: str = "AC75"
    cycle: str = "AC37"
    retrospective_grid_ms: int = 100
    steady_windows: SteadyWindowsConfig = field(default_factory=SteadyWindowsConfig)
    causal_latency: CausalLatencyConfig = field(default_factory=CausalLatencyConfig)
    turn_detection: TurnDetectionConfig = field(default_factory=TurnDetectionConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    neural_model: NeuralModelConfig = field(default_factory=NeuralModelConfig)
    spline_baseline: SplineBaselineConfig = field(default_factory=SplineBaselineConfig)
    scenario_trial_counts: TrialCountsConfig = field(default_factory=TrialCountsConfig)
    reference_seed: int = 2027
    memory_limits: MemoryLimitsConfig = field(default_factory=MemoryLimitsConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_json(data: Any) -> bytes:
    """Produce deterministic byte representation for canonical hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def compute_config_hash(config: LearningConfig | Mapping[str, Any]) -> str:
    """Compute SHA-256 hash of canonical configuration representation."""
    data = config.to_dict() if isinstance(config, LearningConfig) else dict(config)
    return hashlib.sha256(canonical_json(data)).hexdigest()


def validate_config_dict(data: Mapping[str, Any]) -> None:
    """Validate raw or parsed configuration dict against all G2.6 rules."""
    if data.get("schema_version") != "ac75-config-1":
        raise ValueError(f"Invalid schema_version: {data.get('schema_version')}")
    if data.get("primary_class") != "AC75":
        raise ValueError(f"Expected primary_class 'AC75', got {data.get('primary_class')}")
    if data.get("cycle") != "AC37":
        raise ValueError(f"Expected cycle 'AC37', got {data.get('cycle')}")
    
    # Windows
    sw = data.get("steady_windows", {})
    if sw.get("duration_s", 0) <= 0:
        raise ValueError("steady_windows.duration_s must be positive")
    if not (0.0 < sw.get("min_supported_duration_fraction", 0) <= 1.0):
        raise ValueError("steady_windows.min_supported_duration_fraction must be in (0, 1]")
    
    # Neural model
    nm = data.get("neural_model", {})
    if nm.get("hidden_layers") != 2 or nm.get("units_per_layer") != 32:
        raise ValueError(f"Neural architecture must have 2 layers of 32 units (got {nm})")
    if nm.get("activation") != "silu":
        raise ValueError("Neural activation must be 'silu'")
    if nm.get("distribution") != "lognormal":
        raise ValueError("Neural distribution must be 'lognormal'")


def load_config(path: Path | str | None = None) -> LearningConfig:
    """Load, validate, and return LearningConfig instance."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config_dict(raw)
    
    sw_data = raw.get("steady_windows", {})
    cl_data = raw.get("causal_latency", {})
    td_data = raw.get("turn_detection", {})
    rec_data = raw.get("recovery", {})
    unc_data = raw.get("uncertainty", {})
    nm_data = raw.get("neural_model", {})
    train_data = nm_data.get("training", {})
    spline_data = raw.get("spline_baseline", {})
    trials_data = raw.get("scenario_trial_counts", {})
    mem_data = raw.get("memory_limits", {})

    return LearningConfig(
        schema_version=raw.get("schema_version", "ac75-config-1"),
        config_id=raw.get("config_id", "ac75_2024_v1"),
        description=raw.get("description", ""),
        primary_class=raw.get("primary_class", "AC75"),
        cycle=raw.get("cycle", "AC37"),
        retrospective_grid_ms=raw.get("retrospective_grid_ms", 100),
        steady_windows=SteadyWindowsConfig(
            duration_s=float(sw_data.get("duration_s", 5.0)),
            nonoverlapping=bool(sw_data.get("nonoverlapping", True)),
            min_supported_duration_fraction=float(sw_data.get("min_supported_duration_fraction", 0.95)),
            max_internal_gap_ms_telemetry=int(sw_data.get("max_internal_gap_ms_telemetry", 1200)),
            max_internal_gap_ms_wind=int(sw_data.get("max_internal_gap_ms_wind", 2500)),
            speed_eligibility_filter=bool(sw_data.get("speed_eligibility_filter", False)),
        ),
        causal_latency=CausalLatencyConfig(
            modeled_latency_ms=int(cl_data.get("modeled_latency_ms", 6000)),
            sensitivities_ms=tuple(cl_data.get("sensitivities_ms", (0, 6000, 12000))),
        ),
        turn_detection=TurnDetectionConfig(
            seed_min_rotation_deg=float(td_data.get("seed_min_rotation_deg", 65.0)),
            seed_max_duration_s=float(td_data.get("seed_max_duration_s", 18.0)),
            seed_reversal_tolerance_s=float(td_data.get("seed_reversal_tolerance_s", 1.5)),
        ),
        recovery=RecoveryConfig(
            reference_window_offset_s=tuple(rec_data.get("reference_window_offset_s", (-7.0, -2.0))),
            recovery_threshold_fraction=float(rec_data.get("recovery_threshold_fraction", 0.95)),
            continuous_hold_duration_s=float(rec_data.get("continuous_hold_duration_s", 2.0)),
            censor_timeout_s=float(rec_data.get("censor_timeout_s", 30.0)),
            straight_motion_exclusion_buffer_s=float(rec_data.get("straight_motion_exclusion_buffer_s", 5.0)),
        ),
        uncertainty=UncertaintyConfig(
            residual_block_duration_s=float(unc_data.get("residual_block_duration_s", 30.0)),
            residual_block_sensitivities_s=tuple(unc_data.get("residual_block_sensitivities_s", (15.0, 60.0))),
        ),
        neural_model=NeuralModelConfig(
            hidden_layers=int(nm_data.get("hidden_layers", 2)),
            units_per_layer=int(nm_data.get("units_per_layer", 32)),
            activation=str(nm_data.get("activation", "silu")),
            distribution=str(nm_data.get("distribution", "lognormal")),
            final_seeds=tuple(nm_data.get("final_seeds", (2027, 2028, 2029))),
            training=NeuralTrainingConfig(
                max_threads=int(train_data.get("max_threads", 4)),
                batch_size=int(train_data.get("batch_size", 512)),
                max_epochs=int(train_data.get("max_epochs", 150)),
                early_stopping_patience=int(train_data.get("early_stopping_patience", 15)),
                learning_rates=tuple(train_data.get("learning_rates", (0.001, 0.0003))),
                weight_decays=tuple(train_data.get("weight_decays", (0.0001, 0.001))),
                dropouts=tuple(train_data.get("dropouts", (0.0, 0.1))),
                screen_seed=int(train_data.get("screen_seed", 2027)),
            ),
        ),
        spline_baseline=SplineBaselineConfig(
            regularization_grid=tuple(spline_data.get("regularization_grid", (0.1, 1.0, 10.0, 100.0))),
        ),
        scenario_trial_counts=TrialCountsConfig(
            preview=int(trials_data.get("preview", 2000)),
            standard=int(trials_data.get("standard", 10000)),
            evaluation=int(trials_data.get("evaluation", 20000)),
        ),
        reference_seed=int(raw.get("reference_seed", 2027)),
        memory_limits=MemoryLimitsConfig(
            max_normalized_rows_per_batch=int(mem_data.get("max_normalized_rows_per_batch", 50000)),
            max_simulated_trials_per_batch=int(mem_data.get("max_simulated_trials_per_batch", 512)),
        ),
    )
