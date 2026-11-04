# 06 — Spoken Narration & Oral Defense Script (25-Minute Mountain Audio Companion)

**Repository**: `2D_regatta_replay` | **Snapshot**: `2026-11-04` | **Audio Generation Note**: *Delivered as a structured plain-text/Markdown and HTML spoken-word script for reading aloud or oral rehearsal; synthetic TTS audio files were not bundled so the archive remains compact and free of robotic mispronunciations of mathematical notation.*

---

## Act I — What Problem Does This System Solve, and How Is It Architected? (00:00 – 04:30)

Welcome to the offline audio walkthrough of the `2D_regatta_replay` repository. If you are hiking or sitting in a cabin without Wi-Fi, this script walks you through the entire system from raw satellite telemetry to 60-frame-per-second browser rendering and causal tournament probability bounds.

At its core, this project solves three distinct analytical problems for America's Cup foiling regattas — problems that are often conflated in sports analytics, but which require completely different mathematical machinery:

1. **First: Retrospective Observation (`Replay` and `Compare` Workspaces)**. What physically happened on the water at every tenth of a second? Where were the nine AC40 foiling monohulls and the eight autonomous robotic course marks (`RM1` through `RM8`), when did each boat's bowsprit cross the starting line or gate line, when did they tack or gybe, and where did their umpiring keep-clear zones overlap?
2. **Second: Retrospective Performance Evaluation (`Analysis` and `Reports` Workspaces)**. Once a race or regatta is finished, how fast was a boat relative to the peers that actually sailed the same legs in the same wind? Why did a team lose twenty seconds on Leg 3 — was it straight-line upwind VMG, a bad wind header, or speed loss in a tack?
3. **Third: Causal Forward Prediction (`Forecast` Workspace)**. Using only information legally available up to a strict historical cutoff timestamp, what is each boat's expected finishing position before the gun (`pre-race-pl-mc-1`), what is each boat's live probability of winning the race from its current on-water position (`live-mc-kalman-1`), and what can — and cannot — be said about the 2027 38th America's Cup in AC75s (`cup-ac38-conditional-2`)?

To keep these three worlds from contaminating one another, the repository enforces one cardinal architectural boundary:
**Python owns all historical metric formulas and all forecasting models. TypeScript owns only display-rate interpolation, live instantaneous geometry, and the user interface.**
The browser never recalculates a historical metric, never re-runs a Plackett–Luce regression, and never fabricates a fallback probability when an artifact is marked `unavailable`.

---

## Act II — What Information Actually Exists in the Archive? (04:30 – 08:30)

Before trusting any equation, you have to know the exact shape of the raw archive.
Inside `Data/`, there are **28 raw `.jsonl` session files** totaling **6.87 gigabytes** (`6,866,006,601` bytes). Those 28 sessions span **9 race days** across two 2026 AC40 preliminary events:
- **Cagliari, Sardinia (May 22 to May 24, 2026)**: 9 sessions (`63` boat-races).
- **Naples, Italy (September 22 to September 27, 2026)**: 19 sessions (`161` replayed boat-races, `164` scheduled boat-races).

Why do we constantly distinguish **224 replayed boat-races** from **227 scheduled boat-races**?
Because on September 22 in Naples, in Practice Races 2, 3, and 4 (`26_09_22_nap_ipr_pr2`, `pr3`, and `pr4`), `GBR B` was listed in the scheduled race roster (`race_start_status`), but transmitted **zero `boat_state` telemetry packets**. During replay ingestion (`pipeline/ingest.py`, lines 699 to 700), boats with empty telemetry lists are dropped so the 2D canvas doesn't render phantom boats at `(0, 0)` — leaving `224` replayed boat-races in `manifests.json` and `analysis/index.json`. However, the forecasting pipeline (`pipeline/prediction/labels.py`) restores all `227` scheduled starts in `.forecast/scheduled_entry_ledger.json`, because dropping a scheduled DNS entrant would bias completion rates upward and shrink the field size $N$ used in tied-$N$ scoring.

Even more importantly: across all 28 sessions, **`official_order_verified` is `False`**. We do not have signed race-committee finishing sheets or umpire penalty logs. Every finishing rank in the archive (`RANK_1`, `RANK_2`, `DNF`, `OCS`) is reconstructed from telemetry and autonomous mark roundings. And while the synchronized replays contain **331,089 frames** at 100-millisecond spacing, 331,089 frames do **not** mean 331,089 independent observations! For cross-race team skill or weather effects, your sample size is 28 sessions across 9 calendar days.

---

## Act III — How Raw Telemetry Becomes a 10 Hz Replay (08:30 – 13:00)

Let's trace how a 250-megabyte `.jsonl` file becomes a compact replay JSON in `public/data/replays/`.
1. **Projection (`pipeline/projection.py`)**: Raw GNSS latitudes and longitudes are projected onto a local tangent plane in metres East ($x$) and metres North ($y$) using WGS84 ellipsoidal curvature coefficients ($k_{\text{lat}} \approx 111{,}048\text{ m/deg}$ and $k_{\text{lon}} \approx 84{,}375\text{ m/deg}$ at Naples; $86{,}408\text{ m/deg}$ at Cagliari).
2. **10 Hz Synchronization (`pipeline/synchronize.py`)**: Boats transmit at roughly 10 Hz with clock jitter; robotic marks transmit at roughly 1 Hz. `TimelineSynchronizer` resamples every channel onto a uniform 100-millisecond grid. Scalar channels (`x, y, sog, vmg, tws, twa`) use linear interpolation. Angular bearings (`heading, cog, twd`) use shortest-arc circular interpolation modulo 360 degrees: $\Delta\theta = ((\theta_1 - \theta_0 + 540^\circ) \bmod 360^\circ) - 180^\circ$. If a boat stops transmitting early — like `GBR B` in `naples_pr1`, which retires 15 minutes and 51 seconds before the window ends — its coordinates are clamped to its final packet, creating a "held tail" that `historical_analysis.py` explicitly excludes.
3. **Bow-Tip Crossing Geometry (`pipeline/reconstruction.py`)**: An AC40's GNSS receiver sits at the transom centerline $(0, 0)$, while the bowsprit tip sits $+12.963\text{ metres}$ forward along the boat's true heading $\psi$. At every 100-millisecond step, `CourseReconstructor` projects the bow tip $\vec{p}_{\text{bow}}(t) = (x + 12.963\sin\psi,\; y + 12.963\cos\psi)$ and solves the 2D cross-product segment intersection $u, v \in [0, 1]$ against the start line or active gate segment. If a boat rounds slightly outside a mark or if one gate mark is missing, it falls back to a 200-metre virtual gate corridor (`MAX_GATE_RADIUS_M = 100.0`). Cumulative race progress `progress_m` is then computed and clamped with a running maximum so `progress_m` is strictly non-decreasing.
4. **Manoeuvres & Virtual Contacts (`pipeline/manoeuvres.py`, `pipeline/analytics.py`)**: Because raw `manoeuvres` records are empty (`0` records), `ManoeuvreDetector` scans 10 Hz telemetry for a 4-gate signature: smoothed turn rate $\ge 8^\circ/\text{s}$, opposite-sign entry/exit TWA in $[20^\circ, 160^\circ]$, heading change $\ge 32^\circ$, and speed loss $\ge 2.5\text{ kt}$. Meanwhile, `detect_virtual_contacts` transforms each boat's 9-vertex `keep_clear_border` ($\pm 7.415\text{ m}$) and `platform_border` ($\pm 5.415\text{ m}$) into world space and runs the Separating Axis Theorem (SAT) at 10 Hz, coalescing overlaps separated by $\le 2.0\text{ s}$ into incidents.

---

## Act IV — Historical Metrics and the Peer-Normalized Radar (13:00 – 17:30)

In `pipeline/historical_analysis.py` (`schema_version = "2.0"`, `formula_version = "historical-2"`), every race, leg, and manoeuvre metric is paired with coverage metadata and a strict quality badge (`derived` requires $\ge 95\%$ valid source-second coverage).

Two subtleties in Part IV are essential for your oral defense:
1. **First: The VMG Sign Convention**. In raw replay telemetry, `vmg` is wind-referenced ($\text{SOG}\cos(\text{TWA})$), which is negative whenever a boat sails downwind ($|\text{TWA}| > 90^\circ$). In `historical_analysis.py`, leg VMG (`avg_vmg_kt`, `upwind_vmg`, `downwind_vmg`) is **mark-referenced** along the active leg vector, so progress toward the leeward gate is positive!
2. **Second: The 6-Axis Self-Excluding Peer Radar (`performance-1`)**. To compare boats fairly when wind speed changes across legs or when some boats DNF early, `_boat_performance` restricts comparison to `matched_legs` — legs where both the subject boat and at least one peer have valid derived metrics. On each matched leg $\ell$, the baseline $\bar{x}_{-b,\ell}$ is the mean of all valid peers **excluding boat $b$ itself**, and the leg index is $I_{b,\ell} = 100 \cdot x_{b,\ell} / \bar{x}_{-b,\ell}$. The dimension index $I_{b,d}$ is the **unweighted mean of per-leg indices**. Because the average of ratios is not the ratio of averages ($\frac{1}{2}(\frac{x_2}{\bar{y}_2} + \frac{x_4}{\bar{y}_4}) \ne \frac{x_2+x_4}{\bar{y}_2+\bar{y}_4}$), `ITA G`'s Downwind VMG index in `naples_pr1` is `109.9671`, whereas `100 * value / peer_mean` is `108.0853`.

---

## Act V — The Three Causal Forecasting Systems (17:30 – 22:30)

Now let's examine `pipeline/prediction/`. Why do we say there are **three separate forecasting targets**?
1. **Target 1: Pre-Race Expected Finish Position (`pre-race-pl-mc-1`)**:
   Predicts expected finish rank $\mathbb{E}[R_i] \in [1, N]$ across all scheduled starters under the **tied-$N$ nonfinish rule**, where every non-finisher (DNS, DNF, OCS, RET) receives worst rank $N$. When $M$ boats fail to finish, the sum of ranks is $\frac{N(N+1)}{2} + \frac{M(M-1)}{2}$, so expected positions sum to strictly more than $\frac{N(N+1)}{2}$ whenever two or more boats can fail to finish!
2. **Target 2: Live In-Race Win Probability (`live-mc-kalman-1` / `correlated_mc`)**:
   Every 10 seconds during a race, a 6-second `ReorderBuffer` feeds a 2D Constant-Velocity Kalman Filter (`CVKalmanFilter`), publishing at `published_at_ms = state_timestamp_ms + 6000`. The promoted `correlated_mc` simulator samples remaining gate times using a persistent crew factor, shared calendar-time weather noise, and remaining-distance-scaled boat innovations, cutting live Brier score by 45% (`0.8387` down to `0.4534`) compared to static Plackett–Luce.
3. **Target 3: The 2027 America's Cup (`cup-ac38-conditional-2` in `cup_2027.json`)**:
   Simulates the 7-team 2027 AC38 tournament in Naples (6 fleet races with `10..4` points and carry-over, 3 Round Robins, Repechages, first-to-5 Semifinals and Final, and first-to-7 Cup Match against Defender `ETNZ`). Crucially, team capability is drawn **once per tournament trial** and held persistent across all matches (preventing the i.i.d. series law-of-large-numbers distortion that inflates a `75.00%` mixture to `93.76%`). And because **1,723 of 5,000 baseline trials (`34.46%`)** encounter ties in the 6-Challenger fleet carry or Round Robin seeding where RRSAC 102.1 tie-break procedures are unpublished, headline point probabilities are `null`, and each team is reported with an exact conservative rule-bound interval `[lower, upper]` of width `0.3446` (`34.46` percentage points).

---

## Act VI — Verification, Audit Findings & Final Takeaway (22:30 – 25:00)

When we ran `.\run.ps1 verify` on `2026-11-04`, **all 828 deterministic tests passed** (406 frontend Vitest tests, 291 Python unit tests, 123 E2E Tier 1–4 tests, and 8 Tier 5 white-box integrity tests), alongside cryptographic SHA-256 verification of all published forecast and environment artifacts.

At the same time, our code audit uncovered six concrete implementation nuances you can cite from memory:
1. `pipeline/reconstruction.py:L228` checks top-level `comp.get("started")` instead of `comp.get("start_state", {}).get("started")`, causing `USA` in `naples_pr1` to be reconstructed as `RANK_4` before `historical_analysis.py` flags it as `conflict`.
2. `pipeline/analytics.py:L263` divides metre lead gaps by constant `8.0 m/s`, whereas `src/engine/analytics.ts:L71` divides by the leader's live `sog`.
3. `pipeline/manoeuvres.py` uses `2.5 kt` speed dip and `90%` recovery vs its `3.0 kt` docstring and `95%` recovery in `historical_analysis.py`.
4. `26_09_22_nap_ipr_pr2` has a non-monotonic source Leg 3 timestamp for `USA`, causing overlapping leg coverage (`1,036.3 s` vs `865.4 s` elapsed).
5. `tactical_insights.py` suppresses 100% (`0 / 3,455`) of 5-minute wind projections due to strict $R^2 \ge 0.55$ and split-half linearity gates.
6. `PositiveDelayMixture` is fully coded in `models.py` but gated off (`available = False`) because `0` human-reviewed clean/loss leg labels exist.

Keep that separation between **measured truth, geometric reconstruction, quality-gated historical indices, and rule-bounded causal forecasts** at the center of your thinking, and you will be ready to explain, critique, defend, and improve every module in this repository.
