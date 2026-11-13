"""Authoritative exact serving engine for AC75 kinematic simulator (Work Packet P5).

Enforces:
- Single canonical request normalization with SI units and [0, 360) wind direction.
- Authoritative scenario hashing via compute_canonical_scenario_hash.
- Strict service limits: 1 running inference process, at most 4 queued requests.
- Browser trial count policy: preview = 2,000 / standard = 10,000.
- Payload limit: <= 2 KiB.
- Exact catalog scenario matching without nearest-neighbor fallback or tolerance bands.
- Exact scenario reversal preserving central 80% intervals and disjoint seconds accounting.
- Direct execution through predict_scenario on reloaded, authenticated model bundle.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import threading
from typing import Any, Mapping

from pipeline.kinematic_ml.contracts import (
    KNOTS_TO_MPS,
    ScenarioStatus,
    compute_canonical_scenario_hash,
    knots_to_mps,
    resolve_team_identity,
    validate_scenario_v2,
)
from pipeline.kinematic_ml.inference import (
    InstalledModelBundle,
    predict_scenario,
)
from pipeline.kinematic_ml.loader import (
    load_authenticated_bundle,
    load_staged_ac75_bundle,
)
from pipeline.kinematic_ml.serving.limits import (
    BROWSER_TRIAL_COUNTS,
    MAX_CONCURRENT_INFERENCE,
    MAX_PAYLOAD_BYTES,
    MAX_QUEUED_REQUESTS,
)

ROOT = Path(__file__).resolve().parents[3]


class ServingError(Exception):
    """Base exception for serving operations."""
    pass


class PayloadTooLargeError(ServingError):
    """Raised when request payload exceeds 2 KiB limit."""
    pass


class QueueFullError(ServingError):
    """Raised when request queue exceeds 4 waiting requests."""
    pass


class UnsupportedRequestError(ServingError):
    """Raised when request parameters are unsupported or invalid."""
    pass


def _neg_zero_safe(val: float, decimals: int = 2) -> float:
    rounded = round(-val, decimals)
    return 0.0 if rounded == -0.0 else rounded


def reverse_scenario_v2_dict(scen: dict[str, Any]) -> dict[str, Any]:
    """Reverse competitor roles in a kinematic-race-sim-2 scenario dictionary."""
    if scen.get("schema_version") != "kinematic-race-sim-2":
        raise ValueError(f"Expected kinematic-race-sim-2, got {scen.get('schema_version')}")

    out = json.loads(json.dumps(scen))  # deep copy
    inp = out.get("applied_inputs", {})
    team_a = inp.get("team_a", out.get("team_a"))
    team_b = inp.get("team_b", out.get("team_b"))

    # Swap applied inputs teams
    inp["team_a"] = team_b
    inp["team_b"] = team_a

    def _negate_acct(acct: dict[str, Any] | None) -> dict[str, Any] | None:
        if not acct:
            return acct
        for k in ("straight_delta_s", "maneuver_delta_s", "start_delta_s", "total_mean_delta_s"):
            if k in acct and isinstance(acct[k], (int, float)):
                acct[k] = _neg_zero_safe(acct[k], 2)
        return acct

    if "seconds_accounting" in inp:
        inp["seconds_accounting"] = _negate_acct(inp["seconds_accounting"])
    if "time_accounting" in out:
        out["time_accounting"] = _negate_acct(out["time_accounting"])

    # Swap probabilities
    probs = out.get("probabilities")
    if probs:
        win_a = probs.get("win_a", 0.0)
        win_b = probs.get("win_b", 0.0)
        probs["win_a"] = win_b
        probs["win_b"] = win_a

    # Swap timing and invert interval
    timing = out.get("timing")
    if timing:
        time_a = timing.get("mean_time_a_s")
        time_b = timing.get("mean_time_b_s")
        timing["mean_time_a_s"] = time_b
        timing["mean_time_b_s"] = time_a
        if "mean_delta_t_s" in timing and isinstance(timing["mean_delta_t_s"], (int, float)):
            timing["mean_delta_t_s"] = _neg_zero_safe(timing["mean_delta_t_s"], 2)
        interval = timing.get("central_80_margin_interval_s")
        if interval and len(interval) == 2:
            p10, p90 = interval
            timing["central_80_margin_interval_s"] = [
                _neg_zero_safe(p90, 2),
                _neg_zero_safe(p10, 2),
            ]

    out["applied_inputs"] = inp
    if "team_a" in out:
        out["team_a"] = team_b
    if "team_b" in out:
        out["team_b"] = team_a

    return out


_ALLOWED_TOP_KEYS = frozenset({
    "schema_version",
    "model_id",
    "team_a",
    "team_b",
    "course_id",
    "environment",
    "purpose",
    "scenario_policy_id",
    "seed",
    "trial_count",
    "n_sims",
    "tws_kt",
    "twd_deg",
    "mode",
})
_ALLOWED_ENV_KEYS = frozenset({"kind", "tws_kt", "tws_mps", "wind_from_deg", "twd_deg"})


def _canon_float(val: float) -> float:
    return 0.0 if val == 0.0 else float(val)


def _exact_cache_key(
    *,
    model_id: str,
    team_a: str,
    team_b: str,
    course_id: str,
    tws_mps: float,
    twd_deg: float,
    purpose: str,
    trial_count: int,
    seed: int,
) -> tuple[str, str, str, str, float, float, str, int, int]:
    twd_mod = _canon_float(float(twd_deg) % 360.0)
    if twd_mod == 360.0:
        twd_mod = 0.0
    return (
        str(model_id),
        str(team_a),
        str(team_b),
        str(course_id),
        _canon_float(float(tws_mps)),
        twd_mod,
        str(purpose),
        int(trial_count),
        int(seed),
    )


def normalize_serving_request(
    raw_request: Mapping[str, Any] | str,
    installed_model_id: str,
) -> dict[str, Any]:
    """Validate and normalize an incoming simulation request according to G8.5 wire format."""
    if isinstance(raw_request, str):
        if len(raw_request.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise PayloadTooLargeError(
                f"Scenario request payload ({len(raw_request.encode('utf-8'))} bytes) exceeds {MAX_PAYLOAD_BYTES} bytes maximum limit"
            )
        try:
            req_dict = json.loads(raw_request)
        except Exception as e:
            raise UnsupportedRequestError(f"Invalid JSON request: {e}") from e
    else:
        req_dict = dict(raw_request)
        encoded_len = len(json.dumps(req_dict).encode("utf-8"))
        if encoded_len > MAX_PAYLOAD_BYTES:
            raise PayloadTooLargeError(
                f"Scenario request payload ({encoded_len} bytes) exceeds {MAX_PAYLOAD_BYTES} bytes maximum limit"
            )

    if not isinstance(req_dict, dict):
        raise UnsupportedRequestError("Request body must be a JSON object")

    unknown_top = set(req_dict.keys()) - _ALLOWED_TOP_KEYS
    if unknown_top:
        raise UnsupportedRequestError(f"Unknown request fields not allowed: {sorted(unknown_top)}")

    if "model_id" in req_dict and req_dict["model_id"] is not None:
        if str(req_dict["model_id"]).strip() != installed_model_id:
            raise UnsupportedRequestError(
                f"Requested model_id '{req_dict['model_id']}' does not match pinned installed model '{installed_model_id}'"
            )

    # 1. Competitors
    team_a_raw = str(req_dict.get("team_a", "")).strip()
    team_b_raw = str(req_dict.get("team_b", "")).strip()
    if not team_a_raw or not team_b_raw:
        raise UnsupportedRequestError("Both team_a and team_b must be provided")

    try:
        team_a = resolve_team_identity(team_a_raw, cycle="AC37")
        team_b = resolve_team_identity(team_b_raw, cycle="AC37")
    except Exception as e:
        raise UnsupportedRequestError(f"Failed to resolve competitor identities: {e}") from e

    if team_a == team_b:
        raise UnsupportedRequestError(f"Competitor teams must be distinct: got {team_a} vs {team_b}")

    # 2. Wind magnitude and direction (reject contradictory duplicate fields; keep full precision)
    env_raw = req_dict.get("environment")
    if env_raw is not None and not isinstance(env_raw, Mapping):
        raise UnsupportedRequestError("environment must be a JSON object")
    env_in = dict(env_raw) if isinstance(env_raw, Mapping) else {}
    unknown_env = set(env_in.keys()) - _ALLOWED_ENV_KEYS
    if unknown_env:
        raise UnsupportedRequestError(f"Unknown environment fields not allowed: {sorted(unknown_env)}")
    if env_in.get("kind") is not None and env_in.get("kind") != "fixed_wind":
        raise UnsupportedRequestError(f"Unsupported environment kind '{env_in.get('kind')}'")

    top_kt = req_dict.get("tws_kt")
    env_kt = env_in.get("tws_kt")
    env_mps = env_in.get("tws_mps")
    if top_kt is not None and env_kt is not None and abs(float(top_kt) - float(env_kt)) > 1e-6:
        raise UnsupportedRequestError("Contradictory tws_kt values between top-level and environment")

    kt_source = env_kt if env_kt is not None else top_kt
    tws_mps: float | None = None
    tws_kt: float | None = None

    if env_mps is not None:
        try:
            tws_mps = _canon_float(float(env_mps))
            tws_kt = tws_mps * (3600.0 / 1852.0)
        except (ValueError, TypeError):
            raise UnsupportedRequestError("Invalid tws_mps in environment")
        if kt_source is not None:
            try:
                kt_val = float(kt_source)
            except (ValueError, TypeError):
                raise UnsupportedRequestError("Invalid tws_kt")
            if abs(tws_mps - knots_to_mps(kt_val)) > 1e-4:
                raise UnsupportedRequestError("Contradictory tws_mps and tws_kt values")
    elif kt_source is not None:
        try:
            tws_kt = _canon_float(float(kt_source))
            tws_mps = _canon_float(knots_to_mps(tws_kt))
        except (ValueError, TypeError):
            raise UnsupportedRequestError("Invalid tws_kt")
    else:
        raise UnsupportedRequestError("Missing wind speed (tws_kt or tws_mps required)")

    if not math.isfinite(tws_kt) or not math.isfinite(tws_mps) or tws_kt < 6.0 or tws_kt > 24.0:
        raise UnsupportedRequestError(
            f"Wind speed {tws_kt:.2f} kt out of supported range [6, 24] kt"
        )

    # Wind direction [0, 360) with contradiction check
    dir_candidates: list[float] = []
    for raw_d in (env_in.get("wind_from_deg"), env_in.get("twd_deg"), req_dict.get("twd_deg")):
        if raw_d is not None:
            try:
                d_val = float(raw_d)
            except (ValueError, TypeError):
                raise UnsupportedRequestError("Invalid wind direction")
            if not math.isfinite(d_val):
                raise UnsupportedRequestError("Wind direction must be finite")
            dir_candidates.append(d_val % 360.0)
    for other_d in dir_candidates[1:]:
        diff_deg = abs(((dir_candidates[0] - other_d + 540.0) % 360.0) - 180.0)
        if diff_deg > 1e-4:
            raise UnsupportedRequestError("Contradictory wind direction fields")
    wind_from_deg = _canon_float(dir_candidates[0] if dir_candidates else 180.0)
    if wind_from_deg == 360.0:
        wind_from_deg = 0.0

    # 3. Purpose and trial counts (fail closed on unknown purpose or contradiction)
    purpose_raw = req_dict.get("purpose", "preview")
    purpose = str(purpose_raw).strip()
    if purpose not in BROWSER_TRIAL_COUNTS:
        raise UnsupportedRequestError(
            f"Unsupported purpose '{purpose}': must be one of {sorted(BROWSER_TRIAL_COUNTS)}"
        )

    if req_dict.get("trial_count") is not None and req_dict.get("n_sims") is not None:
        if int(req_dict["trial_count"]) != int(req_dict["n_sims"]):
            raise UnsupportedRequestError("Contradictory trial_count and n_sims values")

    default_trial_count = BROWSER_TRIAL_COUNTS[purpose]
    trial_count_in = req_dict.get("trial_count") if req_dict.get("trial_count") is not None else req_dict.get("n_sims")
    try:
        trial_count = int(trial_count_in) if trial_count_in is not None else default_trial_count
    except (ValueError, TypeError):
        raise UnsupportedRequestError("Invalid trial_count")
    if trial_count <= 0:
        raise UnsupportedRequestError("trial_count must be positive")

    # 4. Course and policy
    course_id = str(req_dict.get("course_id", "barcelona_lvc_4leg")).strip()
    if not course_id:
        course_id = "barcelona_lvc_4leg"
    policy_id = str(req_dict.get("scenario_policy_id", "training_observed_routes_v1")).strip()

    seed_raw = req_dict.get("seed")
    if seed_raw is not None:
        try:
            seed = int(seed_raw)
        except (ValueError, TypeError):
            raise UnsupportedRequestError("Invalid integer seed")
    else:
        seed = 2027

    normalized = {
        "schema_version": "kinematic-race-sim-2",
        "model_id": installed_model_id,
        "team_a": team_a,
        "team_b": team_b,
        "course_id": course_id,
        "environment": {
            "kind": "fixed_wind",
            "tws_kt": tws_kt,
            "tws_mps": tws_mps,
            "wind_from_deg": wind_from_deg,
            "twd_deg": wind_from_deg,
        },
        "purpose": purpose,
        "scenario_policy_id": policy_id,
        "seed": seed,
        "trial_count": trial_count,
    }

    # Authoritative scenario hash derived from unrounded normalized request
    canonical_for_hash = {
        "schema_version": "ac75-scenario-request-1",
        "model_id": installed_model_id,
        "team_a": team_a,
        "team_b": team_b,
        "course_id": course_id,
        "environment": {
            "kind": "fixed_wind",
            "tws_kt": tws_kt,
            "tws_mps": tws_mps,
            "wind_from_deg": wind_from_deg,
        },
        "purpose": purpose,
        "scenario_policy_id": policy_id,
        "trial_count": trial_count,
        "seed": seed,
    }
    normalized["authoritative_hash"] = compute_canonical_scenario_hash(canonical_for_hash)
    return normalized


class ServingService:
    """Thread-safe, rate-limited simulation service enforcing exact catalog matching."""

    def __init__(
        self,
        bundle: InstalledModelBundle | None = None,
        root: Path = ROOT,
    ) -> None:
        self.root = root
        self._bundle = bundle
        self._lock = threading.Lock()
        self._inference_semaphore = threading.Semaphore(MAX_CONCURRENT_INFERENCE)
        self._queued_requests = 0
        self._catalog_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._catalog_envelope: dict[str, Any] | None = None
        self._load_catalog()

    @property
    def bundle(self) -> InstalledModelBundle:
        if self._bundle is None:
            self._bundle = load_staged_ac75_bundle(self.root)
        return self._bundle

    def _load_catalog(self) -> None:
        """Load and cryptographically authenticate staged scenarios catalog into exact index."""
        ptr_path = self.root / ".forecast" / "ac75_learning" / "latest_candidate.json"
        if not ptr_path.exists():
            return
        authenticated = load_staged_ac75_bundle(self.root)
        if self._bundle is None:
            self._bundle = authenticated

        ptr = json.loads(ptr_path.read_text(encoding="utf-8"))
        man_path = (self.root / ptr["manifest_path"]).resolve()
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
        cat_rel = manifest.get("artifacts", {}).get("scenarios_catalog")
        if not cat_rel:
            raise ServingError("Manifest missing scenarios_catalog path")
        cat_path = (self.root / cat_rel).resolve()
        envelope = json.loads(cat_path.read_text(encoding="utf-8"))
        self._catalog_envelope = envelope
        scenarios = envelope.get("scenarios", []) if isinstance(envelope, dict) else envelope

        self._catalog_cache.clear()
        for s in scenarios:
            if s.get("schema_version") == "kinematic-race-sim-2":
                inp = s.get("applied_inputs", {})
                env_s = inp.get("environment", {})
                if "tws_mps" not in env_s or env_s["tws_mps"] is None:
                    continue
                twd_s = env_s.get("twd_deg") if env_s.get("twd_deg") is not None else env_s.get("wind_from_deg", 180.0)
                k = _exact_cache_key(
                    model_id=str(s.get("model_id", manifest.get("candidate_id", ""))),
                    team_a=str(inp.get("team_a", "")),
                    team_b=str(inp.get("team_b", "")),
                    course_id=str(inp.get("course_id", "barcelona_lvc_4leg")),
                    tws_mps=float(env_s["tws_mps"]),
                    twd_deg=float(twd_s),
                    purpose=str(inp.get("purpose", "preview")),
                    trial_count=int(inp.get("trial_count", 2000)),
                    seed=int(inp.get("seed", 2027)),
                )
                self._catalog_cache[k] = s

    def get_catalog_envelope(self) -> dict[str, Any]:
        """Return staged catalog envelope."""
        if self._catalog_envelope is None:
            self._load_catalog()
        if self._catalog_envelope is None:
            raise ServingError("No staged kinematic candidate catalog found")
        return self._catalog_envelope

    def simulate(self, raw_request: Mapping[str, Any] | str) -> dict[str, Any]:
        """Process simulation request: normalize, check exact cache, or run with concurrency limits."""
        # 1. Normalize request
        b = self.bundle
        norm_req = normalize_serving_request(raw_request, installed_model_id=b.model_id)

        team_a = norm_req["team_a"]
        team_b = norm_req["team_b"]
        cid = norm_req["course_id"]
        tws_mps = norm_req["environment"]["tws_mps"]
        twd_deg = norm_req["environment"]["wind_from_deg"]
        purpose = norm_req["purpose"]
        trial_count = int(norm_req["trial_count"])
        seed = int(norm_req["seed"])

        # 2. Exact match in catalog across ALL normalized request fields (NO rounding or nearest neighbor)
        direct_key = _exact_cache_key(
            model_id=b.model_id,
            team_a=team_a,
            team_b=team_b,
            course_id=cid,
            tws_mps=tws_mps,
            twd_deg=twd_deg,
            purpose=purpose,
            trial_count=trial_count,
            seed=seed,
        )
        if direct_key in self._catalog_cache:
            return self._catalog_cache[direct_key]

        reverse_key = _exact_cache_key(
            model_id=b.model_id,
            team_a=team_b,
            team_b=team_a,
            course_id=cid,
            tws_mps=tws_mps,
            twd_deg=twd_deg,
            purpose=purpose,
            trial_count=trial_count,
            seed=seed,
        )
        if reverse_key in self._catalog_cache:
            return reverse_scenario_v2_dict(self._catalog_cache[reverse_key])

        # 3. Not in exact cache: enforce queue & concurrency limits before executing
        with self._lock:
            if self._queued_requests >= MAX_QUEUED_REQUESTS:
                raise QueueFullError(
                    f"Simulation request queue full (max {MAX_QUEUED_REQUESTS} queued). Try again later."
                )
            self._queued_requests += 1

        try:
            # Wait for inference slot (max 1 concurrent)
            acquired = self._inference_semaphore.acquire(timeout=15.0)
            if not acquired:
                raise ServingError("Timed out waiting for inference execution slot")
            try:
                # Authoritative simulation via predict_scenario
                sim_payload = {
                    "schema_version": norm_req["schema_version"],
                    "model_id": norm_req["model_id"],
                    "team_a": norm_req["team_a"],
                    "team_b": norm_req["team_b"],
                    "course_id": norm_req["course_id"],
                    "environment": {
                        "tws_mps": norm_req["environment"]["tws_mps"],
                        "twd_deg": norm_req["environment"]["wind_from_deg"],
                    },
                    "purpose": norm_req["purpose"],
                    "scenario_policy_id": norm_req["scenario_policy_id"],
                    "seed": norm_req.get("seed", 2027),
                    "trial_count": norm_req.get("trial_count", 2000),
                }
                sim_res = predict_scenario(b, sim_payload)
                return sim_res.to_dict()
            finally:
                self._inference_semaphore.release()
        finally:
            with self._lock:
                self._queued_requests -= 1
