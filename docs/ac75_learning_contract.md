# AC37 AC75 Learned Simulator: Scientific & Engineering Contract

**Version:** 1.0  
**Schema Version:** `ac75-learning-contract-1`  
**Governing Plan Sections:** G2, G4, G8.1, G8.5  
**Owning Code:** `pipeline/kinematic_ml/contracts.py`, `pipeline/kinematic_ml/config.py`, `pipeline/kinematic_ml/configs/ac75_2024_v1.json`

---

## 1. Executive Summary & Objective

This document defines the frozen scientific and engineering contracts for learning the observed behavior of last-cycle AC75 boats from the AC37 telemetry archive. It removes all 10 starting defects identified in G0.2, including arbitrary file/line caps, hard-coded maneuver constants, unlinked simulator primitives, mixed wind sources, inconsistent historical identity mapping, and unverified request handling.

---

## 2. Historical Identity Specification (G2.2)

### 2.1 Canonical Historical Identifiers
Historical observations are strictly keyed to the AC37 America's Cup cycle:
- `ac37:ETNZ` (Emirates Team New Zealand)
- `ac37:INEOS` (INEOS Britannia)
- `ac37:LUNA_ROSSA` (Luna Rossa Prada Pirelli)
- `ac37:AMERICAN_MAGIC` (NYYC American Magic)
- `ac37:ALINGHI` (Alinghi Red Bull Racing)
- `ac37:ORIENT_EXPRESS` (Orient Express Racing Team)

### 2.2 Cycle-Scoped Alias Resolution
- In an **AC37** historical query, session display aliases (`GB1`, `INEOS`, `GBR`, `NZL`, `ITA`, `USA`, `SUI`, `FRA`) deterministically resolve to their canonical `ac37:*` identifiers.
- Outside the AC37 cycle (e.g. AC38 requests), `GB1` does **NOT** resolve to `ac37:INEOS`.
- AC38 entrants (`ARC_USA`, `LA_ROCHE_POSAY`, `AUSTRALIA`, `ac38:GB1`) are strictly rejected with `UnsupportedIdentityError` when presented in AC37 historical queries.
- Missing historical identities raise errors or enter explicit pooled experiments; they are never silently converted into zero effects.

---

## 3. Physical Units and Mathematical Formulas (G2.3)

### 3.1 SI Normalization
All internal calculations use SI base units:
- **Distance / Position:** Metres ($m$)
- **Speed / Velocity:** Metres per second ($m/s$)
- **Angle / Bearing:** Degrees ($^\circ$) modulo $360.0$
- **Time:** Unix epoch milliseconds ($ms$) for timestamps; seconds ($s$) for durations

The exact conversion factor is:
$$1\text{ international knot} \equiv \frac{1852}{3600}\text{ m/s} \approx 0.5144444444444445\text{ m/s}$$

### 3.2 Ground-Relative Progress and VMG
Ground-relative progress is derived from **Course Over Ground (COG)**, not heading:
- **Course VMG:** $SOG \cdot \cos(COG - \text{leg\_bearing})$
- **Wind VMG:** $SOG \cdot \cos(COG - TWD)$ on upwind legs; reversed on downwind legs.
- **TWA and Turn Geometry:** Heading ($\psi$) is used for aerodynamic angle of attack (TWA) and turn rotation geometry.

Calculations reuse the validated historical formula owners in `pipeline.historical_analysis` via SI adapters (`leg_course_vmg_mps` and `wind_relative_vmg_mps`).

---

## 4. Information-Time Separation & Anti-Leakage (G2.1, G8.1)

To guarantee zero future-data and target leakage:
- **Motion Predictors (`MOTION_PREDICTOR_ALLOWLIST`):** `tws_mps`, `twa_sin`, `twa_cos`, `tack_side`, `leg_type`, `course_wind_angle_deg`, `heading_cog_offset_deg`, `team_id`, `practice_domain`.
- **Motion Targets (`MOTION_TARGET_ALLOWLIST`):** `sog_mps`, `mu_log_mps`, `sigma_log`, `ground_vmg_mps`, `wind_vmg_mps`.
- **Strictly Forbidden:** `sog_mps` (as input), future wind, future headings, future turn counts, finish order, race margin, and post-race team ratings.
- **Event Predictors:** Only turn onset conditions, out-of-fold predicted entry speed, rotation geometry, and team ID. Future minimum speed or recovery path length cannot be used as features.

---

## 5. Scenario-v2 Contract (`kinematic-race-sim-2`) (G8.5)

### 5.1 Request Contract
- Maximum wire payload: **2 KiB**
- Model identifier: Content-addressed hash / ID only. **No filesystem paths** or arbitrary file pointers allowed.
- Environment: Fixed wind speed (0, 40] kt and wind direction [0, 360) deg.
- Purposed counts: `preview` (2,000 trials), `standard` (10,000 trials), `evaluation` (20,000 trials).
- Rejection of unknown keys with HTTP 422 / fail-closed validation.

### 5.2 Discriminated Result Semantics
The simulation result schema `kinematic-race-sim-2` discriminates three statuses:
1. `available`: Full valid simulation. `probabilities` and `timing` objects are non-null.
2. `unavailable`: Scientific or numerical criteria unfulfilled (e.g., unresolved simulation mass). Headline probabilities and timing are explicitly `null` (not zero), and `reason_codes` list specific failure causes.
3. `unsupported`: Input outside registered domain (e.g. unknown team, extreme weather).

### 5.3 Probability Scope & Time Accounting
- **Probability Scope:** Explicitly labeled `completion_assumed_on_water`. Unconditional win/loss probabilities remain unavailable without reviewed non-finish denominators.
- **Time Accounting:** Elapsed time for maneuvers replaces straight-line integration; travel time is never double-counted.

---

## 6. Versioned Configuration (`ac75_2024_v1`) (G2.6)

All pipeline parameters are frozen in `pipeline/kinematic_ml/configs/ac75_2024_v1.json`:
- **Steady Windows:** Non-overlapping 5.0 s, $\ge 95\%$ supported duration, max internal gap 1200 ms (telemetry) / 2500 ms (wind).
- **Causal Latency:** Modeled 6000 ms; sensitivities at 0, 6000, 12000 ms.
- **Turn Detection Seeds:** 65.0 deg rotation within 18.0 s, 1.5 s reversal tolerance.
- **Neural Model:** 2 hidden layers $\times$ 32 units, SiLU activation, lognormal distribution, seeds 2027, 2028, 2029.
- **Configuration Hash:** Canonical JSON SHA-256 digest (`666df1c75bfecc8e81e80292d83a636baa9f7e62bf71e4e8bd5e3bf2b2d0c6cd`).

---

## 7. Legacy Compatibility (G0.2, G2.4)

Existing `kinematic-race-sim-1` scenarios and catalogs remain readable as explicitly **legacy** via `is_legacy_scenario()`. They are never silently promoted to learned v2 models or displayed with learned uncertainty semantics.
