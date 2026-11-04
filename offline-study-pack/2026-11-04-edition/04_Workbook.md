# 04 — Workbook: 36 Worked Exercises, Derivations & Adversarial Scenarios

**Repository**: `2D_regatta_replay` | **Snapshot**: `2026-11-04` | **Companion Answer Key**: [`04_Workbook_Solutions.pdf`](04_Workbook_Solutions.pdf) / [`04_Workbook_Solutions.html`](04_Workbook_Solutions.html)

> **Instructions for Mountain Study**:
> This workbook contains **36 substantive problems** organized into three progressive difficulty tiers:
> * **Tier I — Foundational (Questions 1–12)**: Hand-checkable numerical calculations, coordinate geometry, sign conventions, and archive structure.
> * **Tier II — Intermediate (Questions 13–24)**: Debugging scenarios, historical metric formulas, matched-leg peer normalization, and causal forecasting mechanics.
> * **Tier III — Advanced, Mathematical Derivations & False-Confidence Traps (Questions 25–36)**: Analytical proofs, "Explain this to another person" critiques, and adversarial questions designed to expose false confidence.
>
> **Data Provenance Tag**: Every problem explicitly declares whether it uses **`[ACTUAL REPOSITORY EVIDENCE]`** (with exact session/boat identifiers and artifact paths) or **`[SYNTHETIC DATA]`** (designed for clean hand-calculation). Attempt each problem before consulting `04_Workbook_Solutions`.

---

## Tier I — Foundational: Numerical Hand-Calculations & Core Conventions (Q1–Q12)

### Question 1 — WGS84 Local Tangent Plane Projection `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/config.py:L15-L21`](source-companion/view/pipeline/config.py.html#L15), [`pipeline/projection.py:L20-L36`](source-companion/view/pipeline/projection.py.html#L20), and `public/data/replays/naples_pr1.json`.
In `naples_pr1`, the course reference origin is $(\phi_0, \lambda_0) = (40.80948067^\circ\text{ N},\; 14.23726898^\circ\text{ E})$ with local curvature scale factors $k_{\text{lat}} = 111{,}047.746\text{ m/deg}$ and $k_{\text{lon}} = 84{,}374.839\text{ m/deg}$.
1. Suppose an autonomous mark reports geodetic coordinates $(\phi, \lambda) = (40.81848636^\circ\text{ N},\; 14.24912086^\circ\text{ E})$. Calculate its local Cartesian coordinates $(x, y)$ in metres to two decimal places.
2. Why is $k_{\text{lon}}$ approximately $24\%$ smaller than $k_{\text{lat}}$ at Naples, and how much larger is $k_{\text{lon}}$ at Cagliari ($\phi_0 = 39.18^\circ\text{ N}$, $k_{\text{lon}} = 86{,}407.9\text{ m/deg}$)?

---

### Question 2 — Shortest-Arc Circular Interpolation Across North `[SYNTHETIC DATA]`
**Source**: [`pipeline/synchronize.py:L29-L48`](source-companion/index.html) and [`src/engine/interpolate.ts:L7-L10`](source-companion/view/src/engine/interpolate.ts.html#L7).
A boat's raw `heading` is $352.0^\circ$ at $t_0 = 1000\text{ ms}$ and $12.0^\circ$ at $t_1 = 1200\text{ ms}$.
1. Evaluate the shortest-arc angular difference $\Delta\theta = ((12.0 - 352.0 + 540.0) \bmod 360.0) - 180.0$.
2. Compute the synchronized 10 Hz heading at $t = 1050\text{ ms}$ ($\alpha = 0.25$) and $t = 1100\text{ ms}$ ($\alpha = 0.50$).
3. What heading would naive linear interpolation $a + \alpha(b - a)$ produce at $t = 1100\text{ ms}$, and what physical error does that represent on the water?

---

### Question 3 — AC40 Bowsprit Offset and Sub-Frame Start Crossing `[SYNTHETIC DATA]`
**Source**: [`pipeline/reconstruction.py:L25,L39-L83`](source-companion/view/pipeline/reconstruction.py.html#L25).
Consider an East–West start line running from port mark $\vec{q}_0 = (-60, 0)$ to starboard mark $\vec{q}_1 = (60, 0)$ in metres. Between $t_0 = 10{,}000\text{ ms}$ and $t_1 = 10{,}100\text{ ms}$, an AC40 sails at true heading $\psi = 0^\circ$ (due North), and its transom GNSS coordinate moves from $(x_0, y_0) = (10.0, -13.363)$ to $(x_1, y_1) = (10.0, -12.363)$.
1. Using the AC40 bowsprit offset $L_{\text{bow}} = 12.963\text{ m}$, compute the world coordinates of the bow tip $\vec{p}_{\text{bow}}(t_0)$ and $\vec{p}_{\text{bow}}(t_1)$.
2. Compute the segment intersection fractions $(u, v)$ and the rounded millisecond crossing timestamp $t_{\text{cross}}$.
3. If the code used the raw transom GNSS coordinates $(x, y)$ instead of $\vec{p}_{\text{bow}}$, by how many milliseconds would the start crossing be delayed at this boat speed ($10\text{ m/s}$)?

---

### Question 4 — Wind-Referenced vs Mark-Referenced VMG Sign Convention `[SYNTHETIC DATA]`
**Source**: [`pipeline/ingest.py`](source-companion/view/pipeline/ingest.py.html#L1), [`pipeline/historical_analysis.py:L375-L420`](source-companion/view/pipeline/historical_analysis.py.html#L375), and [`src/components/panels/LeaderboardPanel.tsx`](source-companion/index.html).
On Leg 2 (a downwind leg where the leeward gate lies at bearing $\theta_{\text{leg}} = 225^\circ$), the true wind blows from $\text{TWD} = 45^\circ$. A boat sails on port gybe with $\text{SOG} = 30.0\text{ kt}$ and course over ground $\text{COG} = 195^\circ$ (heading $30^\circ$ left of dead downwind).
1. Calculate the signed True Wind Angle $\text{TWA} = \text{signed\_angle}(\text{TWD} - \text{COG})$.
2. Calculate the **wind-referenced VMG** ($\text{SOG}\cos(\text{TWA})$) stored in `replay.telemetry.boats[id].vmg` and displayed on the live Replay leaderboard.
3. Calculate the **mark-referenced VMG** ($\text{SOG}\cos(\theta_{\text{leg}} - \text{COG})$) computed by `historical_analysis.py` for Leg 2. Why do their signs differ?

---

### Question 5 — Archive Denominators: 28 Sessions, 224 Replayed vs 227 Scheduled `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`evidence/scheduled_entry_ledger.json`](evidence/scheduled_entry_ledger.json), [`evidence/analysis_index.json`](evidence/analysis_index.json), and [`pipeline/ingest.py:L699-L700`](source-companion/view/pipeline/ingest.py.html#L699).
1. How many sessions and replayed boat-races belong to Cagliari (`cagliari_2026`) vs Naples (`naples_2026`)?
2. Identify the exact 3 boat-race entries that exist in `.forecast/scheduled_entry_ledger.json` (`227` entries) but are absent from `public/data/analysis/index.json` (`224` boat-races).
3. Which two lines in `pipeline/ingest.py` cause those 3 entries to be omitted from replay exports, and why must the forecasting pipeline (`pipeline/prediction/labels.py`) restore them?

---

### Question 6 — Instantaneous Pairwise Boat Comparison Geometry (`B − A`) `[SYNTHETIC DATA]`
**Source**: [`src/engine/analytics.ts:L86-L99`](source-companion/view/src/engine/analytics.ts.html#L86).
In the `Compare` workspace, suppose the course axis is $\theta_{\text{axis}} = 0^\circ$ (due North), and both boats are on **Leg 2 (downwind, even leg)**.
- Primary Boat $A$ is at $(x_A, y_A) = (0, 500)\text{ m}$, sailing due South ($\text{COG}_A = 180^\circ$) at $20\text{ kt}$ ($10.289\text{ m/s}$).
- Comparison Boat $B$ is at $(x_B, y_B) = (60, 420)\text{ m}$, sailing due South ($\text{COG}_B = 180^\circ$) at $25\text{ kt}$ ($12.861\text{ m/s}$).
1. Calculate Euclidean `separationM`, `eastM` ($\Delta x$), and `northM` ($\Delta y$).
2. Calculate `alongLegM` and `lateralM`. Explain why `alongLegM` is **positive** ($+80\text{ m}$) even though $y_B - y_A = -80\text{ m}$.
3. Calculate the closure rate `closureMps` in $\text{m/s}$. Are the boats approaching or separating?

---

### Question 7 — Held Telemetry Tails vs Active Racing `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/synchronize.py:L22-L25`](source-companion/index.html) and [`evidence/analysis_snapshot_naples_pr1.json`](evidence/analysis_snapshot_naples_pr1.json).
In `naples_pr1`, the synchronized replay window runs for $1{,}948.7\text{ s}$ (`19,488` frames at `100 ms`). However, `GBR B` (`f535f0dc-a45b-4668-ae07-bd52e0cdd947`) stops transmitting new `boat_state` records $951.55\text{ s}$ (`15m 51.55s`) before `window_end`.
1. What does `TimelineSynchronizer` store in `replay.telemetry.boats["f535f0dc..."]["x"]` and `["y"]` for the final $9{,}515$ frames of `naples_pr1`?
2. How does `historical_analysis.py` prevent this $951.55\text{ s}$ frozen tail from corrupting `GBR B`'s race speed, distance, and peer radar metrics?

---

### Question 8 — Manoeuvre Detection Four-Gate Thresholds `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/manoeuvres.py:L48-L207`](source-companion/view/pipeline/manoeuvres.py.html#L48) and [`pipeline/historical_analysis.py:L265-L333`](source-companion/view/pipeline/historical_analysis.py.html#L265).
1. List the four sequential numeric conditions a 10 Hz telemetry window must satisfy in `ManoeuvreDetector.detect_for_boat` to be flagged as a tack or gybe.
2. What is the exact numeric discrepancy between the `pipeline/manoeuvres.py` module docstring (`L10`) and the executable `ManoeuvreDetector.__init__` default (`L57`) for minimum speed loss?
3. Explain the difference between how `manoeuvres.py` (`L192-L207`) and `historical_analysis.py` (`_event_analysis`, `L294-L313`) define `recovery_s`.

---

### Question 9 — Enhanced vs True Boat Scale on the 2D Canvas `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`src/components/canvas/boatModels.ts:L28-L50,L221-L231`](source-companion/view/src/components/canvas/boatModels.ts.html#L28) and `PROJECT.md`.
1. At a course-wide zoom level where `viewportScalePxPerM = 0.35 px/m`, what render scale (in `px/m`) and what total screen pixel length does `computeBoatRenderScale` return for an `AC40` in `'true'` mode vs `'enhanced'` mode?
2. Repeat for an `AC75` (`totalLengthM = 21.9 m`, `minPixelFloor = 34.0 px`).
3. Does switching from `'true'` to `'enhanced'` mode alter `virtual_contact_incidents` or live SAT overlap detection in `CourseCanvas.tsx`? Why or why not?

---

### Question 10 — Causal Reorder Buffer and Publication Timestamp `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/state.py`](source-companion/view/pipeline/prediction/state.py.html#L1) and [`src/engine/predictionCatalog.ts:L133-L146`](source-companion/view/src/engine/predictionCatalog.ts.html#L133).
Suppose a live checkpoint represents the on-water state at $t_{\text{state}} = 1{,}790{,}079{,}100{,}000\text{ ms}$ ($\text{Gun} + 100\text{ s}$).
1. What is its `published_at_ms` timestamp in `public/data/predictions/races/naples_pr1.json`?
2. If the user scrubs the replay playhead to $t_{\text{playhead}} = 1{,}790{,}079{,}104{,}000\text{ ms}$ ($\text{Gun} + 104\text{ s}$), which checkpoint index does `selectForecastCheckpoint` display: the $\text{Gun} + 100\text{ s}$ checkpoint or the $\text{Gun} + 90\text{ s}$ checkpoint? Why?

---

### Question 11 — Evidence Ladder Classification `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: `docs/source_audit.md`, `docs/historical_analysis.md`, and Figure 3 (`fig03_evidence_ladder.svg`).
Classify each of the following 6 quantities onto its exact rung of the 6-rung Evidence Ladder (Rung 1: Raw Measured, Rung 2: Synchronized/Interpolated, Rung 3: Geometrically Reconstructed, Rung 4: Quality-Gated Historical Metric, Rung 5: Causal Probabilistic Estimate, Rung 6: Unverified/Unidentifiable):
a) `boat_state.sog` in `Data/26_09_22_nap_ipr_pr1.jsonl`
b) `FRA` `RANK_1` official race committee sheet confirmation
c) `ITA G` Downwind VMG index `109.9671` in `public/data/analysis/naples_pr1.json`
d) `ETNZ` 2027 AC38 baseline win probability interval `[0.1686, 0.5132]` in `cup_2027.json`
e) `FRA` start-line bow crossing at `1790079000436 ms` in `naples_pr1.json`
f) `replay.telemetry.boats[id].x[500]` at a 100 ms grid step between two raw GNSS packets

---

### Question 12 — Python vs TypeScript Racing Time-Gap Discrepancy `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/analytics.py:L263-L265`](source-companion/view/pipeline/analytics.py.html#L263), [`src/engine/analytics.ts:L71`](source-companion/view/src/engine/analytics.ts.html#L71), and `docs/derived_metrics.md:L9`.
While racing on Leg 3, the leader `FRA` is `160.0 m` ahead of `ITA B` in `progress_m` and is currently sailing at `SOG = 31.104 kt` ($16.0\text{ m/s}$).
1. What time gap (`gap_s`) does Python's `AnalyticsEngine` (`pipeline/analytics.py:L263-L265`) compute?
2. What time gap (`gapS`) does the browser's `getStandings` (`src/engine/analytics.ts:L71`) compute and display in the UI?
3. Which implementation matches `docs/derived_metrics.md:L9`?

---

## Tier II — Intermediate: Historical Metrics, Debugging & Causal Forecasting (Q13–Q24)

### Question 13 — Self-Excluding Peer Radar: Mean-of-Ratios vs Ratio-of-Means `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/historical_analysis.py:L656-L712`](source-companion/view/pipeline/historical_analysis.py.html#L656) and [`evidence/naples_pr1_performance.csv`](evidence/naples_pr1_performance.csv) (Rows 65–67).
In `naples_pr1`, `ITA G` records the following Downwind VMG (`downwind_vmg`) values on the two downwind legs:
- **Leg 2**: `value = 19.572515 kt`, `peer_mean = 15.408508 kt` (`peer_count = 6`: `FRA, NZL G, ITA B, GBR G, NZL B, SUI`).
- **Leg 4**: `value = 17.866515 kt`, `peer_mean = 19.229889 kt` (`peer_count = 4`: `FRA, NZL G, ITA B, GBR G`).
1. Compute `ITA G`'s Leg 2 index $I_{\text{ITA G}, 2}$ and Leg 4 index $I_{\text{ITA G}, 4}$ to 4 decimal places.
2. Compute the exported race dimension `value`, `peer_mean`, and `index` (`109.9671`).
3. Why does `100 * value / peer_mean` give `108.0853` instead of `109.9671`? Why did `peer_count` drop from `6` on Leg 2 to `4` on Leg 4?

---

### Question 14 — Debugging the `USA` Start Conflict in `naples_pr1` `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/reconstruction.py:L228`](source-companion/view/pipeline/reconstruction.py.html#L228) and [`pipeline/historical_analysis.py:L755-L759`](source-companion/view/pipeline/historical_analysis.py.html#L755).
In `naples_pr1`, `USA` (`126368d2-98e9-4c3e-97ce-fb047d40ab0e`) has 24 raw `race_start_status` records, all reporting `started = False`. Yet in `public/data/replays/naples_pr1.json`, `USA` has `classification = "RANK_4"` and `elapsed_s = 1143.112`, whereas in `public/data/analysis/naples_pr1.json`, `USA` has `quality = "conflict"` on all race metrics and `overall_index = null` in `performance-1`.
1. Trace the exact dictionary key bug at `pipeline/reconstruction.py:L228` that allowed `USA` to be classified as `RANK_4` in the replay manifest.
2. How does `pipeline/historical_analysis.py` detect this conflict and protect the peer-normalized radar and historical cohort index?

---

### Question 15 — Debugging Non-Monotonic Source Leg Timings in `26_09_22_nap_ipr_pr2` `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/historical_analysis.py:L336-L469`](source-companion/view/pipeline/historical_analysis.py.html#L336) and `public/data/analysis/26_09_22_nap_ipr_pr2.json`.
In `26_09_22_nap_ipr_pr2`, `USA`'s raw `leg_timings` records report:
- Gun time: `1790081100000`
- Leg 1 `gate_time`: `1790081421799`
- Leg 2 `gate_time`: `1790081725693`
- Leg 3 `gate_time`: `1790081553791` (note: earlier than Leg 2!)
- Leg 4 `gate_time`: `1790081965371` (`elapsed_s = 865.371 s`)
1. When `_leg_entry_for_boat` constructs intervals $[t_{\text{start}, \ell}, t_{\text{end}, \ell}]$ sequentially from source `leg_timings`, what happens to Leg 3 (`1790081725693` $\to$ `1790081553791`)?
2. What interval is assigned to Leg 4, and why does the sum of covered leg durations for `USA` (`321.799 + 303.894 + 411.580 = 1037.273 s` window / `1036.288 s` covered) exceed `USA`'s total race elapsed time of `865.371 s`?

---

### Question 16 — Match-Race Matched-Leg Scope in `naples_mr_final` `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`evidence/naples_mr_final_performance.csv`](evidence/naples_mr_final_performance.csv) and `public/data/analysis/naples_mr_final.json`.
In the 6-leg Cagliari/Naples Match Race Final `naples_mr_final` (`26_09_27_nap_ipr_mr_final`, `ITA B` vs `NZL B`), `NZL B` completes all 6 legs (`elapsed_s = 856.032 s`), while `ITA B` misses the Leg 5 windward gate rounding (`Gates = [1, 2, 3, 4, 6]`).
1. Why is `matched_legs = [1, 2, 3, 4]` for **both** `NZL B` and `ITA B` in `performance-1`, even though `NZL B` has valid derived metrics on all 6 legs?
2. On any matched leg $\ell \in \{1, 2, 3, 4\}$ in a 2-boat race, if `NZL B` has index $I_{\text{NZL B}, \ell}$, what is the exact algebraic formula for `ITA B`'s index $I_{\text{ITA B}, \ell}$ on that same leg? Verify using Leg 1 `upwind_vmg` (`NZL B = 96.6538`, `ITA B = 103.4620`).

---

### Question 17 — Tactical Wind-Shift OLS Slope & Why 0 Projections Fire `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/tactical_insights.py:L75-L356`](source-companion/view/pipeline/tactical_insights.py.html#L75).
Across all 28 sessions, `build_tactical_insights` emits `3,455` 10-second snapshots, yet `0` snapshots emit a non-null 5-minute conditional wind-shift projection (`projection_change_deg` is `null` in all `3,455` rows).
1. Explain how `tactical_insights.py` unwraps directional wind samples around the circular mean $\bar{\theta}$ before fitting the Ordinary Least Squares slope $\hat{\beta}_1$ ($\text{deg/s}$).
2. List the 7 sequential quality/stability gates in `tactical_insights.py:L255-L295` that a snapshot must pass before `projection_change_deg = 300.0 * slope_deg_per_s` is emitted. Which gates suppress the noisy race-course wind traces in practice?

---

### Question 18 — Constant-Velocity Kalman Filter State & Covariance Propagation `[SYNTHETIC DATA]`
**Source**: [`pipeline/prediction/state.py:L8-L86`](source-companion/view/pipeline/prediction/state.py.html#L8) and `docs/forecasting_review_resolution.md` (Section A1).
A boat's filtered 2D state at $t_0$ has position $(x, y) = (100, 200)\text{ m}$, ground velocity $(v_x, v_y) = (5, 12)\text{ m/s}$, diagonal position variance $P_{xx} = P_{yy} = 4.0\text{ m}^2$, diagonal velocity variance $P_{v_x v_x} = P_{v_y v_y} = 0.5\text{ (m/s)}^2$, zero cross-covariance, and acceleration spectral density $q = 0.12\text{ m}^2/\text{s}^3$.
1. Propagate the state mean $\vec{m}^-$ forward across a $\Delta t = 10.0\text{ s}$ telemetry dropout without new measurements.
2. Compute the propagated position variance $P^-_{xx}(\Delta t) = P_{xx} + 2\Delta t P_{x v_x} + (\Delta t)^2 P_{v_x v_x} + \frac{1}{3} q (\Delta t)^3$.
3. Why would the naive random-walk formula $\sigma^2_{\text{pos}} = \sigma_0^2 + q \Delta t$ severely underestimate position uncertainty during a 10-second outage?

---

### Question 19 — Empirical Bayes Beta-Binomial Completion Posterior `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/models.py:L426-L547`](source-companion/view/pipeline/prediction/models.py.html#L426).
In `CompletionModel`, each entry's completion probability is regularized toward the pooled prior using Jeffreys / Beta-Binomial pseudocounts. Suppose prior pseudocounts are $\alpha_0 = 6.20, \beta_0 = 1.80$ (prior mean $0.775$, concentration $\alpha_0 + \beta_0 = 8.0$).
1. If an entry has started $n_i = 12$ earlier races and completed $c_i = 9$ of them, compute its posterior mean completion probability $\hat{s}_i = \frac{\alpha_0 + c_i}{\alpha_0 + \beta_0 + n_i}$.
2. Why does the pre-race completion model gate off (`status = "unavailable"`) on Day 1 (`2026-05-22`, the first Cagliari race day)?

---

### Question 20 — Plackett–Luce Discrimination Scale $\kappa = 1.8$ and Prior $\sigma = 1.2$ `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/models.py:L45-L225`](source-companion/view/pipeline/prediction/models.py.html#L45) and `docs/forecasting_implementation.md:L56,L84-L86`.
1. In a 2-boat race between Boat $A$ ($\hat{\theta}_A = +0.50$) and Boat $B$ ($\hat{\theta}_B = -0.50$) with $100\%$ completion probability, calculate Boat $A$'s win probability $\frac{\exp(\kappa \hat{\theta}_A)}{\exp(\kappa \hat{\theta}_A) + \exp(\kappa \hat{\theta}_B)}$ under $\kappa = 1.0$ vs $\kappa = 1.8$.
2. According to the expanding-window backtest in `docs/forecasting_implementation.md:L85-L86`, how did changing $\kappa$ from $1.0$ to $1.8$ affect pre-race Brier score (`0.8184` vs `0.8580`) vs rank spread, and why was `correlated_mc` (`Brier = 0.8162`, `NormMSE = 0.1219`) promoted instead as the primary simulator?

---

### Question 21 — Why Custom Pre-Race Wind Speeds Return Identical Expected Positions `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/build.py:L387-L438`](source-companion/view/pipeline/prediction/build.py.html#L387), [`pipeline/prediction/weather.py:L40-L54`](source-companion/view/pipeline/prediction/weather.py.html#L40), and `public/data/predictions/scenarios/`.
In `public/data/predictions/scenarios/`, there are three generated scenario files for `naples_pr1` at `tws_kt = 12.0`, `13.0`, and `13.25 kt` (all with `direction_offset_deg = 0`).
1. Inspect or explain why `expected_position_by_boat` is numerically identical across `12.0 kt`, `13.0 kt`, and `13.25 kt`.
2. What happens when a user requests `tws_kt = 12.0, direction_offset_deg = +15.0` in the Forecast workspace, and what geometric/physical reason does the codebase give for rejecting non-zero direction offsets?

---

### Question 22 — Separating Axis Theorem (SAT) Contact Classification `[SYNTHETIC DATA]`
**Source**: [`src/engine/contactDetector.ts:L9-L38,L141-L203`](source-companion/view/src/engine/contactDetector.ts.html#L9) and [`pipeline/analytics.py:L127-L220`](source-companion/view/pipeline/analytics.py.html#L127).
Two AC40 boats sail side-by-side due North ($\psi_A = \psi_B = 0^\circ$) at the exact same Northing $y_A = y_B = 0\text{ m}$, separated laterally in Easting by $\Delta x = x_B - x_A = 12.0\text{ m}$.
1. Using the AC40 half-spans (`platform_border` max $|x| = 5.415\text{ m}$, `keep_clear_border` max $|x| = 7.415\text{ m}$), determine whether their `platform_border` polygons overlap and whether their `keep_clear_border` polygons overlap.
2. Calculate the exact 1D penetration depth `overlapDepthM` along the lateral East–West normal axis for the overlapping border.

---

### Question 23 — Greedy Label Collision Avoidance Cost Function `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`src/components/canvas/boatPresentation.ts:L14-L60`](source-companion/view/src/components/canvas/boatPresentation.ts.html#L14).
In `layoutBoatLabels`, each candidate label rectangle is scored by the cost function (`L38`):
$$\text{cost} = 10^6 \cdot \text{obstacles} + 10^3 \cdot \text{courseOverlap} + 10 \cdot \text{hudOverlap} + 10^5 \cdot \text{coveredVessels} + \text{distance}$$
1. Explain the strict lexicographic hierarchy implied by the weights $(10^6, 10^5, 10^3, 10, 1)$.
2. Under what exact condition (`L50-L59`) does `layoutBoatLabels` abandon the 40-candidate radial ring search around each boat and fall back to a multi-column grid layout? When that happens, do the boat hull polygons move on screen?

---

### Question 24 — Local Forecast Scenario Middleware Lock & PID Handshake `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`scripts/forecastScenarios.ts`](source-companion/view/scripts/forecastScenarios.ts.html#L1) and `docs/forecasting_implementation.md:L38`.
When a user clicks **Generate forecast** in the `Forecast` workspace during `npm run dev`:
1. How does `scripts/forecastScenarios.ts` prevent two concurrent browser tabs or a dev server + preview server from corrupting `public/data/predictions/index.json`?
2. Why does the middleware record the child Python process PID *before* completing the startup handshake, and how is an abandoned lock file recovered?

---

## Tier III — Advanced, Derivations & False-Confidence Traps (Q25–Q36)

### Question 25 — Mathematical Derivation: The Tied-$N$ Expected Rank Sum Identity `[MATHEMATICAL DERIVATION]`
**Source**: [`docs/forecasting_implementation.md:L65-L70`](source-companion/view/docs/forecasting_implementation.md.html#L65) and [`examples/03_plackett_luce_and_cup_bounds.py`](examples/03_plackett_luce_and_cup_bounds.py).
In a scheduled field of $N$ boats, suppose $F \in \{0, 1, \dots, N\}$ boats finish (receiving distinct ranks $1, 2, \dots, F$) and $M = N - F$ boats fail to finish (each receiving tied rank $N$).
1. Prove algebraically that for any realization with $M$ nonfinishers, the sum of assigned ranks is:
   $$\sum_{i=1}^N R_i = \frac{N(N+1)}{2} + \frac{M(M-1)}{2}$$
2. Take expectations over the distribution of $M$ to derive the exact excess rank sum formula $\sum_{i=1}^N \mathbb{E}[R_i] - \frac{N(N+1)}{2} = \frac{1}{2}\mathbb{E}[M(M-1)]$.
3. Explain why $M = 0$ and $M = 1$ both conserve the standard permutation sum $\frac{N(N+1)}{2}$, whereas $M \ge 2$ strictly increases it.

---

### Question 26 — Mathematical Derivation: Analytic Plackett–Luce Expected Rank `[MATHEMATICAL DERIVATION]`
**Source**: [`docs/forecasting_implementation.md:L71-L75`](source-companion/view/docs/forecasting_implementation.md.html#L71) and [`pipeline/prediction/models.py`](source-companion/view/pipeline/prediction/models.py.html#L1).
Under Plackett–Luce with positive worths $w_i = \exp(\kappa \theta_i)$ and independent Bernoulli completion indicators $C_i \sim \operatorname{Bernoulli}(s_i)$ ($s_i \in [0, 1]$):
1. Using Luce's Choice Axiom (that Plackett–Luce marginalizes consistently to subsets of size 2 so $\mathbb{P}(j \text{ finishes ahead of } i \mid C_i = 1, C_j = 1) = \frac{w_j}{w_i + w_j}$), prove that under the tied-$N$ rule:
   $$\mathbb{E}[R_i] = N(1 - s_i) + s_i \left(1 + \sum_{j \ne i} s_j \frac{w_j}{w_i + w_j}\right)$$
2. Verify that summing this expression over $i = 1, \dots, N$ when $s_1 = \dots = s_N = 1$ yields $\frac{N(N+1)}{2}$.

---

### Question 27 — Counterexample Proof: Highest Win Probability $\ne$ Best Expected Finish Position `[MATHEMATICAL DERIVATION]`
**Source**: [`docs/forecasting_review_resolution.md:L180-L191`](source-companion/view/docs/forecasting_review_resolution.md.html#L180) (Section F2).
An external reviewer claimed that in any coherent joint ranking model, the boat with the highest win probability must also have the lowest (best) expected finishing position.
1. Using the 3-boat distribution $P(A,B,C) = 0.45$, $P(B,C,A) = 0.40$, $P(C,B,A) = 0.15$, compute $\mathbb{P}(\text{win})$ and $\mathbb{E}[R]$ for Boats $A$, $B$, and $C$.
2. Explain physically in sailing terms why a high-variance tactical flyer (splitting to the unfavored side of the course) can simultaneously maximize $\mathbb{P}(\text{Rank } 1)$ while worsening $\mathbb{E}[\text{Rank}]$.

---

### Question 28 — Mathematical Derivation: Contrast Subspace Projection & Pairwise Variance Preservation `[MATHEMATICAL DERIVATION]`
**Source**: [`pipeline/prediction/models.py`](source-companion/view/pipeline/prediction/models.py.html#L1) and [`docs/forecasting_implementation.md:L76-L78`](source-companion/view/docs/forecasting_implementation.md.html#L76).
Let $\vec{\theta} \sim \mathcal{N}(\vec{\mu}, \Sigma)$ in $\mathbb{R}^K$, and let $P = I_K - \frac{1}{K}\mathbf{1}_K \mathbf{1}_K^\top$ be the centering projection matrix onto the zero-sum contrast subspace $\mathcal{H}_0 = \{\vec{v} \in \mathbb{R}^K : \mathbf{1}_K^\top \vec{v} = 0\}$.
1. Prove that $P^2 = P$, $P^\top = P$, and $P\mathbf{1}_K = \vec{0}$.
2. Let $\tilde{\theta} = P\vec{\theta}$ have covariance $\tilde{\Sigma} = P\Sigma P$. Prove that for every pair $(i, j)$, the pairwise difference variance is invariant under projection:
   $$\operatorname{Var}(\tilde{\theta}_i - \tilde{\theta}_j) = \tilde{\Sigma}_{ii} + \tilde{\Sigma}_{jj} - 2\tilde{\Sigma}_{ij} = \Sigma_{ii} + \Sigma_{jj} - 2\Sigma_{ij} = \operatorname{Var}(\theta_i - \theta_j)$$

---

### Question 29 — Mathematical Derivation: Boundary Identity Between Pre-Race and Live Checkpoint $t = \text{Gun}$ `[MATHEMATICAL DERIVATION]`
**Source**: [`docs/forecasting_review_resolution.md:L121-L125`](source-companion/view/docs/forecasting_review_resolution.md.html#L121) and [`pipeline/prediction/simulation.py`](source-companion/view/pipeline/prediction/simulation.py.html#L1).
In `simulate_race`, a leg's total log-duration is modeled as $\ln T_\ell = \mu_{\ell} + \eta_{\text{crew}} + \eta_{\text{weather},\ell} + \epsilon_{i,\ell}$.
1. Show why splitting Leg 1 at progress fraction $u \in (0, 1)$ into two independent log-normal draws with full variance $\sigma^2$ would violate zero-information boundary consistency as $u \to 0^+$.
2. Show how scaling the remaining-leg innovation variance by $(1 - u)$ while sharing the persistent crew factor $\eta_{\text{crew}}$ ensures that at $u = 0$ (the starting gun with no new information), the live continuation distribution is identical to the pre-race full-race distribution.

---

### Question 30 — Mathematical Derivation: Persistent vs Independent Ability Draws in First-to-7 Series `[MATHEMATICAL DERIVATION]`
**Source**: [`docs/forecasting_implementation.md:L122-L123`](source-companion/view/docs/forecasting_implementation.md.html#L122) and [`examples/03_plackett_luce_and_cup_bounds.py`](examples/03_plackett_luce_and_cup_bounds.py).
In the 2027 America's Cup Match (first to $W = 7$ wins, maximum $2W - 1 = 13$ races), suppose Team $A$'s single-race win probability $P$ against Team $B$ is uncertain before the regatta: with probability $0.5$, the teams are equal ($P = 0.50$), and with probability $0.5$, Team $A$'s AC75 hull design is dominant ($P = 0.90$).
1. Using the negative binomial series win function $S(p) = \sum_{k=0}^{6} \binom{6+k}{k} p^7 (1-p)^k$, compute the exact series win probability under **persistent** tournament-level ability sampling: $\mathbb{E}[S(P)] = 0.5\,S(0.50) + 0.5\,S(0.90)$.
2. Compute the series win probability if a simulator mistakenly resampled abilities **independently** on every race ($S(\mathbb{E}[P]) = S(0.70)$). Explain intuitively why independent per-race sampling inflates the favorite's series win chance from $75.00\%$ to $93.76\%$.

---

### Question 31 — False-Confidence Trap: Why `1,723 / 5,000` AC38 Cup Trials Are Unresolved & Why Bounds Cannot Be Normalized `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/cup.py:L298-L400`](source-companion/view/pipeline/prediction/cup.py.html#L298), [`docs/forecast_rules_sources.json:L24-L45`](source-companion/view/docs/forecast_rules_sources.json.html#L24), and [`evidence/cup_2027.json`](evidence/cup_2027.json).
In `cup_2027.json` (baseline scenario `rho0.5_sigma1_c1_k1`), `3,277` of `5,000` trials resolve cleanly, and `1,723` (`34.46%`) are flagged unresolved at `round_robin_challengers`.
1. Trace the exact two mechanisms in `cup.py:L302-L353` (6-race fleet point ties affecting `CHALLENGER_CARRY` `2.5, 2.0, 1.5, 1.0, 0.5, 0.0`, and post-Round-Robin parity ties among `.5` or `.0` carry holders) that trigger `round_robin_challengers` unresolved status.
2. Prove why $\sum_{i=1}^7 \text{lower}_i = 1 - u = 0.6554$ and $\sum_{i=1}^7 \text{upper}_i = 1 + 6u = 3.0676$.
3. Suppose a colleague proposes computing a point probability for each team by normalizing the midpoints $\tilde{p}_i = \frac{(\text{lower}_i + \text{upper}_i)/2}{\sum_{j=1}^7 (\text{lower}_j + \text{upper}_j)/2}$. Prove what hidden tie-break rule this normalization secretly imposes, and explain why it violates the repository's evidence contract.

---

### Question 32 — False-Confidence Trap: Unobserved Entrant (`AUSTRALIA`) vs Observed Zero Strength (`0.0`) `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/cup.py:L52-L90,L241-L261`](source-companion/view/pipeline/prediction/cup.py.html#L52) and `docs/forecasting_implementation.md:L145-L146`.
In `cup_2027.json`, `AUSTRALIA` ("Team Australia") has no 2026 AC40 preliminary regatta starts (`observed = False`, `mapped_strength = null`).
1. Write down the latent AC75 capability sampling equation in `cup.py:L241-L261` for an **observed** team with $\hat{\mu}_{\text{team}} = 0.0$ vs an **unobserved** team (`AUSTRALIA`) when transfer loading is $\rho = 1.0$ and $\sigma_{\text{team}} = 0.5$.
2. What bug occurred in an earlier version of the code when `AUSTRALIA` was initialized to `mapped_strength = 0.0` before missing-history detection?

---

### Question 33 — False-Confidence Trap: First Received Finish vs Globally Resolved Winner `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/state.py`](source-companion/view/pipeline/prediction/state.py.html#L1), [`docs/forecasting_review_resolution.md:L79`](source-companion/view/docs/forecasting_review_resolution.md.html#L79), and `public/data/predictions/races/naples_mr_final.json`.
In `naples_mr_final` (`ITA B` vs `NZL B`), after `NZL B` crosses the finish line on Leg 6, the live forecast checkpoint status transitions to `"unavailable"` with reason `"First received finish is not a globally resolved first finisher"`.
1. Why doesn't the live forecast immediately publish `win_prob_by_boat["NZL B"] = 1.0` when `NZL B`'s finish crossing is observed?
2. What specific anomaly in `ITA B`'s gate history (`Gates = [1, 2, 3, 4, 6]`, missing Leg 5 rounding) prevents the causal state machine from certifying the global on-water finishing order?

---

### Question 34 — False-Confidence Trap: What a Peer Index of `110` Does and Does Not Support `[EXPLAIN TO ANOTHER PERSON]`
**Source**: [`pipeline/historical_analysis.py:L580-L746`](source-companion/view/pipeline/historical_analysis.py.html#L580) and `docs/team_analytics.md`.
A syndicate coach looks at the Analysis workspace for `naples_pr1`, sees `FRA` has an `upwind_vmg` index of `110.32`, and concludes: *"Our AC40 hull and foil package is 10.3% faster upwind than the other 8 boats in the fleet, and this proves our upwind boat speed will dominate in 18 knots of breeze."*
Write a clear, rigorous 4-point briefing to the coach explaining:
1. Who is actually in the denominator (`6` peers, not `8`, and why `USA` and `GBR B` are excluded).
2. The difference between `upwind_vmg` (`110.32`) and `upwind_speed` (`109.32`) — i.e., tactical wind shifts, headers/lifts, and course-axis geometry vs hull drag.
3. Why equal-weighted leg ratios can overweight a short or light-air leg.
4. Why single-race AC40 one-design VMG in `12.9 kt` breeze does not identify AC75 hull design performance in `18 kt`.

---

### Question 35 — Adversarial Audit: Why `PositiveDelayMixture` Is `available = False` `[ACTUAL REPOSITORY EVIDENCE]`
**Source**: [`pipeline/prediction/models.py:L668-L856`](source-companion/view/pipeline/prediction/models.py.html#L668) and `docs/forecasting_implementation.md:L94`.
`pipeline/prediction/models.py` contains nearly 200 lines of sophisticated numerical code implementing a 64-point Gauss–Legendre quadrature Expectation-Maximization (EM) algorithm for a `LogNormal + Bernoulli-Gamma` positive-delay convolution (`PositiveDelayMixture`).
1. Inspect the model cards in `public/data/predictions/models/*.json` or `sub2_forecast.md`: what is the value of `delay_mixture.available` and `delay_mixture.promoted` across all published models?
2. What exact quantitative evidence thresholds (`reviewed_clean >= 50`, `reviewed_loss >= 20`, `dates >= 3`) prevent this model from activating, and why would activating an unanchored 2-component EM mixture on small unreviewed leg-time samples be scientifically dangerous?

---

### Question 36 — Oral Defense Synthesis: Explain, Critique, Defend & Improve the System `[EXPLAIN TO ANOTHER PERSON]`
Suppose you are presenting this repository to a panel of quantitative sports analysts and software architects. Answer four rapid-fire questions in 1–2 concise paragraphs each:
1. **Explain**: Why does the architecture strictly forbid TypeScript from calculating historical metrics or forecast probabilities, yet allow TypeScript to calculate live leaderboard gaps and pairwise boat comparisons?
2. **Critique**: What is the single most consequential data or statistical limitation in the current 28-session archive?
3. **Defend**: Why does the 2027 America's Cup forecast publish `null` headline point probabilities and `34.46 pp`-wide intervals instead of a clean bar chart summing to `100%`?
4. **Improve**: If you had one week of engineering time and access to the race committee's signed official result sheets and penalty logs, which two pipeline modules would you update first, and what measurable improvement would you expect in `.forecast/backtest.json` and `public/data/analysis/`?
