"""Predictive scales, joint residual sampling, and completion scope for AC75 (T13).

Contract (G3.4, G3.5):
- Single variance path: residual block sampling in log-space; never double-adds independent noise.
- Contemporaneous paired-boat steady-motion residual blocks on a common clock (30-second blocks).
- Default probability scope: 'completion_assumed_on_water'.
- Explicit variance ledger documenting modeled vs unmodeled uncertainty components.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class VarianceLedger:
    """Explicitly documents how each form of variation is modeled."""
    serial_execution_variation: str = "30-second empirical block residual bootstrap"
    shared_conditions_variation: str = "Contemporaneous paired-boat residual correlation"
    between_seed_sensitivity: str = "Calibrated across 3 frozen seeds (2027, 2028, 2029)"
    model_parameter_uncertainty: str = "Out-of-fold chronological cross-validation spread"
    monte_carlo_numerical_error: str = "Standard error of the mean over N trials (SE = s / sqrt(N))"
    weather_process_model: str = "Declared deterministic or scenario wind; no unverified time-varying weather model"
    empirical_paired_block_count: int = 0
    empirical_cross_boat_correlation: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PairedResidualSampler:
    """Manages empirical contemporaneous residual blocks for paired-boat simulation."""

    def __init__(self, block_duration_s: float = 30.0) -> None:
        self.block_duration_s = float(block_duration_s)
        # Store paired residual blocks: list of (res_a, res_b) arrays representing normalized residuals
        self.blocks: list[tuple[np.ndarray, np.ndarray]] = []
        self.empirical_correlation: float = 0.5

    def add_paired_block(self, res_a: np.ndarray, res_b: np.ndarray) -> None:
        """Adds a paired contemporaneous residual block."""
        if len(res_a) > 0 and len(res_b) > 0:
            min_len = min(len(res_a), len(res_b))
            self.blocks.append((
                np.asarray(res_a[:min_len], dtype=float),
                np.asarray(res_b[:min_len], dtype=float),
            ))

    def extract_from_steady_windows(
        self,
        steady_windows: Sequence[Mapping[str, Any]],
        predict_distribution_fn: Callable[[Mapping[str, Any]], tuple[float, float]],
        *,
        block_windows: int = 6,
    ) -> int:
        """Extracts contemporaneous 30-second (6 x 5s) paired-boat normalized log-speed residual blocks."""
        # Group by (family_id, attempt_id, 5s_clock_slot_ms)
        by_slot: dict[tuple[str, str, int], list[tuple[str, float]]] = {}
        for r in steady_windows:
            sog = float(r.get("sog_mps", 0.0))
            if sog <= 2.0:
                continue
            fid = str(r.get("family_id") or r.get("attempt_id") or "")
            att = str(r.get("attempt_id") or fid)
            raw_t = int(r.get("t_start_ms") or r.get("window_start_ms") or 0)
            w_start = (raw_t // 5000) * 5000
            tid = str(r.get("team_id", ""))
            if not fid or not tid or w_start <= 0:
                continue

            mu_log, log_sig = predict_distribution_fn(r)
            sig = max(0.05, math.exp(log_sig))
            z = float(np.clip((math.log(sog) - mu_log) / sig, -3.5, 3.5))
            by_slot.setdefault((fid, att, w_start), []).append((tid, z))

        # Group paired slots by (family_id, attempt_id) sorted by w_start
        by_race: dict[tuple[str, str], list[tuple[int, float, float]]] = {}
        all_a = []
        all_b = []
        for (fid, att, w_start), entries in by_slot.items():
            # Keep slots with at least 2 distinct teams
            by_team = {}
            for tid, z in entries:
                by_team[tid] = z
            if len(by_team) >= 2:
                teams_sorted = sorted(by_team.keys())
                za = by_team[teams_sorted[0]]
                zb = by_team[teams_sorted[1]]
                by_race.setdefault((fid, att), []).append((w_start, za, zb))
                all_a.append(za)
                all_b.append(zb)

        if len(all_a) >= 10 and np.std(all_a) > 1e-4 and np.std(all_b) > 1e-4:
            corr = float(np.corrcoef(all_a, all_b)[0, 1])
            if np.isfinite(corr):
                self.empirical_correlation = float(np.clip(corr, -0.5, 0.9))

        added = 0
        for (_fid, _att), timeline in sorted(by_race.items()):
            timeline.sort(key=lambda x: x[0])
            n = len(timeline)
            i = 0
            while i + block_windows <= n:
                # Check if windows are reasonably contiguous (within block_windows * 10s)
                dt_ms = timeline[i + block_windows - 1][0] - timeline[i][0]
                if dt_ms <= block_windows * 10_000:
                    blk_a = np.array([timeline[k][1] for k in range(i, i + block_windows)], dtype=float)
                    blk_b = np.array([timeline[k][2] for k in range(i, i + block_windows)], dtype=float)
                    self.add_paired_block(blk_a, blk_b)
                    # Also add swapped order so boat A / boat B assignment is symmetric
                    self.add_paired_block(blk_b, blk_a)
                    added += 2
                    i += block_windows
                else:
                    i += 1
        return added

    def sample_residuals(
        self,
        duration_s: float,
        step_s: float,
        rng: np.random.Generator,
        *,
        cross_boat_correlation: float | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Samples contemporaneous residual series for boat A and boat B over the requested duration.

        If empirical paired blocks exist, concatenates randomly drawn 30-second blocks
        (stationary block bootstrap) across the full race duration.
        Otherwise generates correlated stationary Gaussian autoregressive process (AR-1) with rho=0.85.
        """
        n_steps = max(1, int(math.ceil(duration_s / step_s)))

        if self.blocks and len(self.blocks) >= 3:
            chunks_a: list[np.ndarray] = []
            chunks_b: list[np.ndarray] = []
            total = 0
            n_blocks = len(self.blocks)
            while total < n_steps:
                block_idx = int(rng.integers(0, n_blocks))
                blk_a, blk_b = self.blocks[block_idx]
                chunks_a.append(blk_a)
                chunks_b.append(blk_b)
                total += len(blk_a)
            res_a = np.concatenate(chunks_a)[:n_steps]
            res_b = np.concatenate(chunks_b)[:n_steps]
            return res_a, res_b

        rho = 0.85
        corr_val = (
            cross_boat_correlation
            if cross_boat_correlation is not None
            else self.empirical_correlation
        )
        c = float(np.clip(corr_val, 0.0, 1.0))
        sqrt_c = math.sqrt(c)
        sqrt_1_c = math.sqrt(1.0 - c)
        scale_innov = math.sqrt(1.0 - rho * rho)

        shared = np.zeros(n_steps, dtype=float)
        sh_val = float(rng.normal(0, 1))
        for t in range(n_steps):
            sh_val = rho * sh_val + scale_innov * float(rng.normal(0, 1))
            shared[t] = sh_val

        eps_a = rng.normal(0, 1, size=n_steps)
        eps_b = rng.normal(0, 1, size=n_steps)

        res_a = sqrt_c * shared + sqrt_1_c * eps_a
        res_b = sqrt_c * shared + sqrt_1_c * eps_b

        return res_a, res_b

    def save_npz(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.blocks:
            arr_a = np.stack([b[0] for b in self.blocks], axis=0)
            arr_b = np.stack([b[1] for b in self.blocks], axis=0)
        else:
            arr_a = np.zeros((0, 6), dtype=float)
            arr_b = np.zeros((0, 6), dtype=float)
        np.savez_compressed(
            path,
            blocks_a=arr_a,
            blocks_b=arr_b,
            block_duration_s=np.array([self.block_duration_s], dtype=float),
            empirical_correlation=np.array([self.empirical_correlation], dtype=float),
        )

    @classmethod
    def load_npz(cls, path: Path) -> PairedResidualSampler:
        if not path.exists():
            return cls()
        data = np.load(path, allow_pickle=False)
        b_dur = float(data["block_duration_s"][0]) if "block_duration_s" in data else 30.0
        sampler = cls(block_duration_s=b_dur)
        if "empirical_correlation" in data:
            sampler.empirical_correlation = float(data["empirical_correlation"][0])
        if "blocks_a" in data and "blocks_b" in data:
            arr_a = data["blocks_a"]
            arr_b = data["blocks_b"]
            for row_a, row_b in zip(arr_a, arr_b):
                sampler.add_paired_block(row_a, row_b)
        return sampler


class CompletionModel:
    """Manages completion scope and probabilities."""

    def __init__(self, probability_scope: str = "completion_assumed_on_water") -> None:
        self.probability_scope = probability_scope

    def get_completion_detail(self) -> dict[str, Any]:
        """Returns structured completion scope metadata."""
        if self.probability_scope == "completion_assumed_on_water":
            return {
                "probability_scope": "completion_assumed_on_water",
                "unconditional_win_a": None,
                "unconditional_win_b": None,
                "unconditional_no_winner": None,
                "reason": "Observational joint-completion denominator requires validated competitive reliability model",
            }
        return {
            "probability_scope": self.probability_scope,
        }
