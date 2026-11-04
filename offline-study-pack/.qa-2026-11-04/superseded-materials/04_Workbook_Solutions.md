# 04b — Workbook Solutions: Complete Derivations & Step-by-Step Reasoning

**Companion to**: [`04_Workbook.pdf`](04_Workbook.pdf) / [`04_Workbook.html`](04_Workbook.html) | **Snapshot**: `2026-11-04`

---

## Solutions to Tier I — Foundational (Q1–Q12)

### Solution 1 — WGS84 Local Tangent Plane Projection `[ACTUAL REPOSITORY EVIDENCE]`
1. **Local Cartesian Coordinates**:
   Using [`pipeline/projection.py:L34-L35`](source-companion/view/pipeline/projection.py.html#L34):
   $$x = (\lambda - \lambda_0) \cdot k_{\text{lon}} = (14.24912086 - 14.23726898) \times 84{,}374.839 = 0.01185188 \times 84{,}374.839 = \mathbf{+1000.00\text{ m}}$$
   $$y = (\phi - \phi_0) \cdot k_{\text{lat}} = (40.81848636 - 40.80948067) \times 111{,}047.746 = 0.00900569 \times 111{,}047.746 = \mathbf{+1000.06\text{ m}}$$
2. **Why $k_{\text{lon}} < k_{\text{lat}}$ and Cagliari vs Naples**:
   Meridians converge toward the poles by a factor of $\cos\phi_0$ (modulated slightly by the prime-vertical radius of curvature $N(\phi_0)$). At Naples ($\phi_0 \approx 40.81^\circ$), $\cos(40.8095^\circ) \approx 0.75689$, so $k_{\text{lon}} \approx 0.76\,k_{\text{lat}}$. Because Cagliari lies further south ($\phi_0 = 39.18^\circ$), $\cos(39.18^\circ) \approx 0.77517$, making Cagliari's longitude scale factor $86{,}407.9 - 84{,}374.8 = \mathbf{+2{,}033.1\text{ m/deg}}$ ($+2.41\%$) wider than Naples. Using Naples projection constants on a Cagliari race would compress East–West distances by $2.41\%$.

---

### Solution 2 — Shortest-Arc Circular Interpolation Across North `[SYNTHETIC DATA]`
1. **Shortest-arc delta**:
   $$\Delta\theta = \bigl((12.0 - 352.0 + 540.0) \bmod 360.0\bigr) - 180.0 = (200.0 \bmod 360.0) - 180.0 = \mathbf{+20.0^\circ}$$
2. **Interpolated bearings**:
   * At $t = 1050\text{ ms}$ ($\alpha = 0.25$): $\theta(0.25) = (352.0 + 0.25 \times 20.0) \bmod 360.0 = \mathbf{357.0^\circ}$.
   * At $t = 1100\text{ ms}$ ($\alpha = 0.50$): $\theta(0.50) = (352.0 + 0.50 \times 20.0) \bmod 360.0 = 362.0 \bmod 360.0 = \mathbf{2.0^\circ}$.
3. **Naive linear error**:
   Naive linear interpolation gives $352.0 + 0.50(12.0 - 352.0) = \mathbf{182.0^\circ}$ (pointing due South!), a $180^\circ$ directional reversal that spins the rendered boat through a phantom $340^\circ$ gybe/tack in 200 ms.

---

### Solution 3 — AC40 Bowsprit Offset and Sub-Frame Start Crossing `[SYNTHETIC DATA]`
1. **Bow tip world coordinates**:
   At $\psi = 0^\circ$ ($\sin 0^\circ = 0, \cos 0^\circ = 1$), $\vec{p}_{\text{bow}} = (x, y + 12.963)$:
   $$\vec{p}_{\text{bow}}(t_0) = (10.0,\; -13.363 + 12.963) = \mathbf{(10.0, -0.400)\text{ m}}$$
   $$\vec{p}_{\text{bow}}(t_1) = (10.0,\; -12.363 + 12.963) = \mathbf{(10.0, +0.600)\text{ m}}$$
2. **Intersection fractions & timestamp**:
   Motion vector $\vec{r} = (0, 1.0)$, start line vector $\vec{s} = (120, 0)$ from $\vec{q}_0 = (-60, 0)$:
   $$\vec{r} \times \vec{s} = 0\cdot 0 - 1.0\cdot 120 = -120, \qquad \vec{q}_0 - \vec{p}_0 = (-70.0, +0.400)$$
   $$u = \frac{(-70.0)(0) - (0.400)(120)}{-120} = \frac{-48.0}{-120} = \mathbf{0.4000}, \qquad v = \frac{(-70.0)(1.0) - (0.400)(0)}{-120} = \frac{-70.0}{-120} = \mathbf{0.5833}$$
   $$t_{\text{cross}} = \operatorname{round}(10{,}000 + 0.4000 \times 100) = \mathbf{10{,}040\text{ ms}}$$
3. **Transom GNSS delay**:
   Without the $+12.963\text{ m}$ bow offset, the transom does not reach $y = 0$ until the boat travels an additional $12.963\text{ m}$ at $10\text{ m/s}$, delaying the detected start by $\frac{12.963}{10} = \mathbf{1.2963\text{ s}}$ (`1,296 ms`) — often the difference between an OCS penalty and a legal start!

---

### Solution 4 — Wind-Referenced vs Mark-Referenced VMG Sign Convention `[SYNTHETIC DATA]`
1. **Signed TWA**:
   $$\text{TWA} = ((45^\circ - 195^\circ + 540^\circ) \bmod 360^\circ) - 180^\circ = (390^\circ \bmod 360^\circ) - 180^\circ = \mathbf{-150.0^\circ}$$
2. **Wind-referenced VMG (`replay.telemetry.boats[id].vmg`)**:
   $$\text{VMG}_{\text{wind}} = 30.0 \cos(-150.0^\circ) = 30.0 \times (-0.866025) = \mathbf{-25.98\text{ kt}}$$
3. **Mark-referenced VMG (`historical_analysis.py` Leg 2)**:
   $$\text{VMG}_{\text{mark}} = 30.0 \cos(225^\circ - 195^\circ) = 30.0 \cos(30^\circ) = \mathbf{+25.98\text{ kt}}$$
   *Why they differ*: Wind-referenced VMG measures velocity toward $\text{TWD} = 45^\circ$ (upwind), so sailing downwind away from the wind yields a negative dot product. Historical leg VMG projects velocity onto the unit vector pointing from the windward gate to the leeward gate ($225^\circ$), so progress toward the leeward gate is positive.

---

### Solution 5 — Archive Denominators: 28 Sessions, 224 Replayed vs 227 Scheduled `[ACTUAL REPOSITORY EVIDENCE]`
1. **Regatta breakdown**:
   * **Cagliari (`cagliari_2026`)**: `9` sessions (`2026-05-22` to `2026-05-24`), `63` replayed boat-races (`63` scheduled).
   * **Naples (`naples_2026`)**: `19` sessions (`2026-09-22` to `2026-09-27`), `161` replayed boat-races (`164` scheduled).
   * **Total**: `28` sessions, `224` replayed boat-races, `227` scheduled boat-races.
2. **The 3 telemetry-free scheduled entries**:
   `GBR B` (`f535f0dc-a45b-4668-ae07-bd52e0cdd947`) in `26_09_22_nap_ipr_pr2`, `26_09_22_nap_ipr_pr3`, and `26_09_22_nap_ipr_pr4` (verified by `examples/03_plackett_luce_and_cup_bounds.py`).
3. **Code mechanism & statistical necessity**:
   [`pipeline/ingest.py:L699-L700`](source-companion/view/pipeline/ingest.py.html#L699) executes `result.competitors = [c for c in competitors.values() if c.telemetry]`, dropping scheduled boats with 0 `boat_state` packets so the replay engine does not crash on empty arrays. However, in pre-race forecasting, dropping scheduled non-starters (DNS) would condition on a post-start event (whether a boat's transponder transmitted on course) and change the field size $N$ used in the tied-$N$ score. Therefore `pipeline/prediction/labels.py` reads the full scheduled roster (`227` entries).

---

### Solution 6 — Instantaneous Pairwise Boat Comparison Geometry (`B − A`) `[SYNTHETIC DATA]`
1. **Displacement & Euclidean separation**:
   $$\Delta x = 60 - 0 = \mathbf{+60.0\text{ m}}, \qquad \Delta y = 420 - 500 = \mathbf{-80.0\text{ m}}, \qquad \text{separationM} = \sqrt{60^2 + (-80)^2} = \mathbf{100.0\text{ m}}$$
2. **Along-leg and lateral offsets**:
   In [`src/engine/analytics.ts:L91-L93`](source-companion/view/src/engine/analytics.ts.html#L91), because `a.leg = 2` (even/downwind), `direction = -1`. With $\theta_{\text{axis}} = 0^\circ$ ($\sin 0^\circ = 0, \cos 0^\circ = 1$):
   $$\text{alongLegM} = -1 \cdot (60\cdot 0 + (-80)\cdot 1) = \mathbf{+80.0\text{ m}}$$
   $$\text{lateralM} = 60\cdot 1 - (-80)\cdot 0 = \mathbf{+60.0\text{ m}}$$
   Because Leg 2 runs North-to-South, having a smaller $y$ coordinate ($420 < 500$) means Boat $B$ is $80\text{ m}$ further *downwind* (ahead along Leg 2) than Boat $A$!
3. **Closure rate**:
   Velocities: $\vec{v}_A = (0, -10.289)\text{ m/s}$, $\vec{v}_B = (0, -12.861)\text{ m/s}$, so $\vec{v}_B - \vec{v}_A = (0, -2.572)\text{ m/s}$.
   $$\text{closureMps} = -\frac{(0)(60) + (-2.572)(-80)}{100.0} = -\frac{+205.76}{100.0} = \mathbf{-2.06\text{ m/s}}$$
   Negative closure rate means the boats are **separating** (Boat $B$ is already ahead on the downwind leg and sailing faster, pulling away at $2.06\text{ m/s}$).

---

### Solution 7 — Held Telemetry Tails vs Active Racing `[ACTUAL REPOSITORY EVIDENCE]`
1. **What `TimelineSynchronizer` stores**:
   In [`pipeline/synchronize.py:L22-L25`](source-companion/view/pipeline/synchronize.py.html#L22), `interpolate_series` clamps any timestamp $t > t_{\text{last}}$ to `values[-1]`. Thus `GBR B`'s `(x, y, sog, heading, ...)` remain frozen at its final recorded packet for the last $951.55\text{ s}$ (`9,515` frames).
2. **How `historical_analysis.py` protects metrics**:
   `historical_analysis.py` tracks source packet timestamps via `_source_seconds` (`L198-L246`), records `tail_held_s = 951.55`, restricts leg and race metric windows to active racing before retirement/finish, and requires $\ge 95\%$ valid source-second coverage (`MIN_COVERAGE_RATIO = 0.95`) before marking any leg metric `derived`. Consequently, `GBR B`'s incomplete legs are marked `low_coverage` / `unavailable` and excluded from peer baselines.

---

### Solution 8 — Manoeuvre Detection Four-Gate Thresholds `[ACTUAL REPOSITORY EVIDENCE]`
1. **Four numeric gates (`pipeline/manoeuvres.py:L74-L207`)**:
   - **Gate 1 (Smoothed turn-rate peak)**: 5-sample (`0.5 s`) circular moving average heading rate $|\dot{\psi}| \ge \mathbf{8.0^\circ/\text{s}}$ (`min_turn_rate_dps = 8.0`), with $\ge 4.0\text{ s}$ cooldown between events.
   - **Gate 2 (TWA sign flip in sailing range)**: Entry and exit average $\text{TWA}$ over $[-4\text{ s}, -2\text{ s}]$ and $[+2\text{ s}, +4\text{ s}]$ must have **opposite signs** ($\text{entry\_twa} \times \text{exit\_twa} < 0$) and magnitudes in **$[20^\circ, 160^\circ]$**.
   - **Gate 3 (Cumulative heading change)**: $|\Delta\psi| \ge \mathbf{32.0^\circ}$ (`min_heading_change_deg = 32.0`).
   - **Gate 4 (Speed dip)**: $\text{entry\_speed\_kt} - \text{min\_speed\_kt} \ge \mathbf{2.5\text{ kt}}$ (`min_speed_loss_kt = 2.5`).
2. **Docstring vs Code discrepancy**:
   `pipeline/manoeuvres.py:L10` states speed dip $\ge 3.0\text{ kt}$, whereas `ManoeuvreDetector.__init__` (`L57`) sets `min_speed_loss_kt: float = 2.5`.
3. **Dual `recovery_s` definitions**:
   - `manoeuvres.py:L192-L207` measures time from peak turn to reach **$90\%$ of `entry_speed_kt`** and caps unrecovered manoeuvres at the search window end (~`15.0 s`).
   - `historical_analysis.py:L294-L313` (`_event_analysis`) recomputes recovery from raw 10 Hz SOG to reach **$95\%$ of `entry_speed_kt`** within $+15.0\text{ s}$ after minimum speed, and sets `recovery_s = None` (`null`) if $95\%$ is not reached (which occurs on 18 of 42 manoeuvres in `naples_pr1`).

---

### Solution 9 — Enhanced vs True Boat Scale on the 2D Canvas `[ACTUAL REPOSITORY EVIDENCE]`
1. **AC40 at `0.35 px/m`** (`totalLengthM = 13.178 m`, `minPixelFloor = 22.0 px` in `boatModels.ts:L28-L35`):
   - `'true'` mode: `scale = 0.35 px/m`, screen length $= 0.35 \times 13.178 = \mathbf{4.61\text{ px}}$.
   - `'enhanced'` mode: `minScale = 22.0 / 13.178 = 1.66945 px/m` $> 0.35$, so `scale = \mathbf{1.6695\text{ px/m}}$ and screen length $= \mathbf{22.0\text{ px}}$.
2. **AC75 at `0.35 px/m`** (`totalLengthM = 21.9 m`, `minPixelFloor = 34.0 px` in `boatModels.ts:L43-L50`):
   - `'true'` mode: `scale = 0.35 px/m`, screen length $= 0.35 \times 21.9 = \mathbf{7.67\text{ px}}$.
   - `'enhanced'` mode: `minScale = 34.0 / 21.9 = 1.55251 px/m`, screen length $= \mathbf{34.0\text{ px}}$.
   *(Note: `PROJECT.md` mentions "minimum 30px" generically, whereas `boatModels.ts` implements class-specific floors of `22.0 px` for AC40 and `34.0 px` for AC75.)*
3. **Impact on SAT contact detection**:
   **None.** Both `pipeline/analytics.py` (`detect_virtual_contacts`) and `src/engine/contactDetector.ts` (`evaluateBoatPairContact`) transform `AC40_KEEP_CLEAR_BORDER` and `AC40_PLATFORM_BORDER` into **world metric coordinates (metres)** before running SAT (`testPolygonOverlapSAT`). Visual screen scaling (`computeBoatRenderScale`) affects only the 2D canvas drawing context.

---

### Solution 10 — Causal Reorder Buffer and Publication Timestamp `[ACTUAL REPOSITORY EVIDENCE]`
1. **Publication timestamp**:
   $$\text{published\_at\_ms} = \text{state\_timestamp\_ms} + 6000 = 1{,}790{,}079{,}100{,}000 + 6{,}000 = \mathbf{1{,}790{,}079{,}106{,}000\text{ ms}} \quad (\text{Gun} + 106\text{ s})$$
2. **Selected checkpoint at $\text{Gun} + 104\text{ s}$**:
   `selectForecastCheckpoint` (`src/engine/predictionCatalog.ts:L133-L146`) binary-searches for the largest index satisfying `published_at_ms[index] <= playhead`. At $\text{playhead} = \text{Gun} + 104\text{ s}$, the $\text{Gun} + 100\text{ s}$ checkpoint has not yet been published ($\text{Gun} + 106\text{ s} > \text{Gun} + 104\text{ s}$), so the UI displays the **$\text{Gun} + 90\text{ s}$ checkpoint** (published at $\text{Gun} + 96\text{ s}$). This prevents future-packet lookahead leakage during replay scrubbing.

---

### Solution 11 — Evidence Ladder Classification `[ACTUAL REPOSITORY EVIDENCE]`
- **a) `boat_state.sog` in `.jsonl`**: **Rung 1** (Raw Measured Observation).
- **b) `FRA` `RANK_1` official race committee confirmation**: **Rung 6** (Unavailable / Unverified — `official_order_verified = False` across all 28 sessions).
- **c) `ITA G` Downwind VMG index `109.9671`**: **Rung 4** (Quality-Gated Historical Metric / Peer-Normalized Index).
- **d) `ETNZ` 2027 AC38 baseline interval `[0.1686, 0.5132]`**: **Rung 5 / Rung 6 Boundary** (Conditional Scenario / Rule-Bound Interval where point probability is unidentifiable due to RRSAC 102.1 tie-break ambiguity and unmeasured AC75 transfer).
- **e) `FRA` start-line bow crossing at `1790079000436 ms`**: **Rung 3** (Geometrically Reconstructed Event).
- **f) `replay.telemetry.boats[id].x[500]`**: **Rung 2** (Synchronized / Interpolated 10 Hz State).

---

### Solution 12 — Python vs TypeScript Racing Time-Gap Discrepancy `[ACTUAL REPOSITORY EVIDENCE]`
1. **Python (`pipeline/analytics.py:L263-L265`)**:
   Divides `gap_m = 160.0 m` by a hardcoded constant `8.0 m/s`:
   $$\text{gap\_s}_{\text{Python}} = \frac{160.0}{8.0} = \mathbf{20.0\text{ s}}$$
2. **TypeScript (`src/engine/analytics.ts:L71`)**:
   Divides `gapM = 160.0 m` by the leader's instantaneous speed in $\text{m/s}$ ($31.104 \times \frac{1852}{3600} = 16.0\text{ m/s}$):
   $$\text{gapS}_{\text{TS}} = \frac{160.0}{16.0} = \mathbf{10.0\text{ s}}$$
3. **Documentation alignment**:
   TypeScript matches `docs/derived_metrics.md:L9` ("metre gap divided by the leader's current speed"). The browser UI uses `src/engine/analytics.ts`, so the user sees `10.0 s`.

---

## Solutions to Tier II — Intermediate (Q13–Q24)

### Solution 13 — Self-Excluding Peer Radar: Mean-of-Ratios vs Ratio-of-Means `[ACTUAL REPOSITORY EVIDENCE]`
1. **Per-leg indices**:
   $$I_{\text{ITA G}, 2} = 100 \times \frac{19.57251476}{15.40850752} = \mathbf{127.0241}$$
   $$I_{\text{ITA G}, 4} = 100 \times \frac{17.86651453}{19.22988874} = \mathbf{92.9101}$$
2. **Exported dimension aggregates**:
   $$\text{value} = \frac{19.57251476 + 17.86651453}{2} = \mathbf{18.7195\text{ kt}}, \qquad \text{peer\_mean} = \frac{15.40850752 + 19.22988874}{2} = \mathbf{17.3192\text{ kt}}$$
   $$\text{index} = \frac{127.02407896 + 92.91012947}{2} = \mathbf{109.9671}$$
3. **Why `100 * value / peer_mean` differs (`108.0853`) and why `peer_count` drops**:
   For two legs with peer means $\bar{y}_2 \ne \bar{y}_4$, the mean of ratios $\frac{1}{2}\left(\frac{x_2}{\bar{y}_2} + \frac{x_4}{\bar{y}_4}\right)$ gives equal $50\%$ weight to each leg's relative ratio, whereas $\frac{x_2 + x_4}{\bar{y}_2 + \bar{y}_4} = \frac{\bar{y}_2}{\bar{y}_2 + \bar{y}_4}\frac{x_2}{\bar{y}_2} + \frac{\bar{y}_4}{\bar{y}_2 + \bar{y}_4}\frac{x_4}{\bar{y}_4}$ weights each leg in proportion to the fleet's absolute speed $\bar{y}_\ell$. Because the fleet sailed faster on Leg 4 ($\bar{y}_4 = 19.23\text{ kt}$) where `ITA G` was slower ($92.91$), the ratio of means weights Leg 4 more heavily ($108.09$), whereas equal-leg weighting gives $109.97$. Finally, `peer_count` drops from `6` on Leg 2 to `4` on Leg 4 because `NZL B` and `SUI` suffered telemetry dropouts on Leg 4 that pushed their source coverage below `95%` (`quality = "low_coverage"`).

---

### Solution 14 — Debugging the `USA` Start Conflict in `naples_pr1` `[ACTUAL REPOSITORY EVIDENCE]`
1. **The key lookup bug in `pipeline/reconstruction.py:L228`**:
   In `IngestionResult.to_dict()` (`pipeline/ingest.py:L395-L420`), each competitor's start status is serialized under the nested dictionary `comp["start_state"] = {"started": ..., "ocs": ..., "dsq": ...}`. However, `CourseReconstructor._reconstruct_classifications` (`pipeline/reconstruction.py:L228`) checks `explicit_started = comp.get("started")` at the top level! Because `"started"` is not a top-level key, `explicit_started` is always `None`, so `reconstruction.py` falls back to pure geometry, sees `USA` cross the start line and all 4 gates on the water, and assigns `classification = "RANK_4"`.
2. **Downstream protection in `historical_analysis.py`**:
   `historical_analysis.py` (`L755-L759`, `L970-L1020`) reads the raw `.jsonl` `race_start_status` records directly, sees `source_started = False` alongside reconstructed `RANK_4`, flags `source_conflicts`, marks `USA`'s race metrics as `quality = "conflict"` (`value = null`), and excludes `USA` from `performance-1` (`reason = "boat has no eligible racing window or has a source-state conflict"`).

---

### Solution 15 — Debugging Non-Monotonic Source Leg Timings in `26_09_22_nap_ipr_pr2` `[ACTUAL REPOSITORY EVIDENCE]`
1. **Fate of Leg 3**:
   `_leg_entry_for_boat` sets each leg's start time to the previous leg's end time (`start_ms = 1790081725693`) and end time to Leg 3's `gate_time` (`1790081553791`). Because `end_ms <= start_ms`, Leg 3 has a negative duration (`-171.902 s`) and is immediately rejected as `quality = "unavailable"`!
2. **Overlapping clock intervals on Leg 4**:
   When advancing to Leg 4, the loop sets Leg 4's `start_ms` to Leg 3's timestamp (`1790081553791`) and `end_ms` to Leg 4's timestamp (`1790081965371`). Because `1790081553791 < 1790081725693` (Leg 2's end time), the time window `[1790081553791, 1790081725693]` (`171.902 s`) is counted **twice** — once inside Leg 2 and once inside Leg 4! Thus `USA`'s valid legs 1, 2, and 4 sum to $321.799 + 303.894 + 411.580 = 1037.273\text{ s}$ (`1036.288 s` covered), exceeding the $865.371\text{ s}$ gun-to-finish elapsed time by exactly $171.902\text{ s}$.

---

### Solution 16 — Match-Race Matched-Leg Scope in `naples_mr_final` `[ACTUAL REPOSITORY EVIDENCE]`
1. **Why Legs 5 and 6 are excluded for `NZL B`**:
   In `_boat_performance` (`pipeline/historical_analysis.py:L608-L654`), a leg $\ell$ is included in `matched_legs` if and only if the subject boat has a valid metric **and** at least `MIN_PEER_COUNT = 1` peer has a valid metric on leg $\ell$. Because `ITA B` missed the Leg 5 gate rounding, `ITA B` has no valid Leg 5 or Leg 6 interval (`peer_count = 0` for `NZL B` on Legs 5 and 6). Thus both boats are restricted to `matched_legs = [1, 2, 3, 4]`.
2. **Reciprocal relation in a 2-boat race**:
   With only two boats ($A$ and $B$), Boat $A$'s peer mean on leg $\ell$ is simply Boat $B$'s value ($x_{B,\ell}$), and Boat $B$'s peer mean is $x_{A,\ell}$:
   $$I_{A,\ell} = 100 \frac{x_{A,\ell}}{x_{B,\ell}}, \qquad I_{B,\ell} = 100 \frac{x_{B,\ell}}{x_{A,\ell}} = \frac{10{,}000}{I_{A,\ell}}$$
   Checking Leg 1 `upwind_vmg`: $\frac{10{,}000}{96.6538} = \mathbf{103.4620}$, which matches `ITA B`'s exported Leg 1 index to 4 decimal places!

---

### Solution 17 — Tactical Wind-Shift OLS Slope & Why 0 Projections Fire `[ACTUAL REPOSITORY EVIDENCE]`
1. **Circular unwrapping before OLS**:
   In `pipeline/tactical_insights.py:L65-L88`, the circular mean $\bar{\theta}$ of the 120-second window is computed first. Every directional sample $\theta_k$ is unwrapped into a signed offset $y_k = \bar{\theta} + \text{signed\_angle}(\theta_k - \bar{\theta}) \in [\bar{\theta}-180^\circ, \bar{\theta}+180^\circ)$, eliminating $0^\circ/360^\circ$ discontinuities before computing standard linear regression $\hat{\beta}_1 = \frac{\sum (t_k - \bar{t})(y_k - \bar{y})}{\sum (t_k - \bar{t})^2}$.
2. **The 7 sequential projection suppression gates (`tactical_insights.py:L255-L295`)**:
   1. Window quality is `"derived"` ($\ge 90\text{ s}$ coverage and $\ge 10$ samples in the 120 s window).
   2. Circular resultant length $R \ge 0.85$ (low directional dispersion).
   3. Absolute rate $|\text{rate}| \ge 1.5^\circ/\text{min}$ (non-trivial trend).
   4. $|\text{rate}| \le 12.0^\circ/\text{min}$ (not an erratic sensor spike or boat-wash artifact).
   5. Coefficient of determination $R^2 \ge 0.55$ (strong linear fit over the 120 s window).
   6. Split-half sign and magnitude consistency: slopes on the first 60 s and second 60 s must have the **same sign** and neither half-slope may differ from the full slope by more than $50\%$.
   7. Projected 5-minute shift $|\Delta\theta_{300\text{s}}| \le 35.0^\circ$.
   In real race-course wind records (which oscillate continuously with wave/gust cycles every 20–40 seconds), the $R^2 \ge 0.55$ and split-half consistency gates reject 100% of linear extrapolations (`0 / 3,455`).

---

### Solution 18 — Constant-Velocity Kalman Filter State & Covariance Propagation `[SYNTHETIC DATA]`
1. **Propagated state mean at $\Delta t = 10\text{ s}$**:
   $$x^- = 100 + 10(5) = \mathbf{150.0\text{ m}}, \qquad y^- = 200 + 10(12) = \mathbf{320.0\text{ m}}, \qquad v_x^- = \mathbf{5.0\text{ m/s}}, \qquad v_y^- = \mathbf{12.0\text{ m/s}}$$
2. **Propagated position variance**:
   $$P^-_{xx}(10) = 4.0 + 0 + (10^2)(0.5) + \frac{1}{3}(0.12)(10^3) = 4.0 + 50.0 + 40.0 = \mathbf{94.0\text{ m}^2} \quad (\sigma_x = 9.70\text{ m})$$
3. **Why $\sigma_0^2 + q\Delta t$ fails**:
   A position random walk gives $4.0 + 0.12(10) = 5.2\text{ m}^2$ ($\sigma_x = 2.28\text{ m}$), ignoring both initial velocity uncertainty $(\Delta t)^2 P_{vv} = 50.0\text{ m}^2$ and integrated acceleration noise $\frac{1}{3}q(\Delta t)^3 = 40.0\text{ m}^2$, understating variance by a factor of $18\times$!

---

### Solution 19 — Empirical Bayes Beta-Binomial Completion Posterior `[ACTUAL REPOSITORY EVIDENCE]`
1. **Posterior mean**:
   $$\hat{s}_i = \frac{6.20 + 9}{6.20 + 1.80 + 12} = \frac{15.20}{20.00} = \mathbf{0.7600} \quad (76.0\%)$$
   (Shrinking the raw $9/12 = 75.0\%$ rate slightly toward the $77.5\%$ fleet prior.)
2. **Why Day 1 pre-race is gated off**:
   On `2026-05-22` (`before_day = "2026-05-22"`), there are `0` prior race days in the archive (`scheduled_audited == 0`), and `docs/forecast_completion_review.json` is not present. Rather than publishing an uncalibrated prior with zero historical observations, `build.py` gates Day 1 pre-race forecasts to `status = "unavailable"`.

---

### Solution 20 — Plackett–Luce Discrimination Scale $\kappa = 1.8$ and Prior $\sigma = 1.2$ `[ACTUAL REPOSITORY EVIDENCE]`
1. **Win probability for $\Delta\theta = 1.0$**:
   - At $\kappa = 1.0$: $P(A) = \frac{1}{1 + e^{-1.0}} = \mathbf{73.11\%}$.
   - At $\kappa = 1.8$: $P(A) = \frac{1}{1 + e^{-1.8}} = \mathbf{85.81\%}$.
2. **Backtest trade-off (`docs/forecasting_implementation.md:L85-L89`)**:
   Increasing $\kappa$ from $1.0$ to $1.8$ widened pre-race expected position spread (eliminating artificial rank compression toward $\frac{N+1}{2}$), but slightly increased pure Plackett–Luce Brier score (`0.8184` $\to$ `0.8580`). The time-based simulator `correlated_mc` (`time_combined`) achieved the best of both worlds: `Brier = 0.8162`, `LogLoss = 1.8007`, and `NormMSE = 0.1219` (a $15.6\%$ reduction in rank MSE over `pl_kappa_18`), earning promotion as `selected_model = "correlated_mc"`.

---

### Solution 21 — Why Custom Pre-Race Wind Speeds Return Identical Expected Positions `[ACTUAL REPOSITORY EVIDENCE]`
1. **Why `12.0 kt`, `13.0 kt`, and `13.25 kt` match**:
   In `pipeline/prediction/simulation.py` (`export_pre_race_scenario`), pre-race scenarios use the conservative reference ranking model (`joint_pl_reference` / `StrengthModel`), whose fitted worths $w_i = \exp(\kappa \theta_i)$ and completion probabilities $s_i$ have zero slope on `tws_kt` (as documented in `docs/forecasting_implementation.md:L28,L36`: *"The conservative reference retains zero wind-response until a conditional alternative passes the release procedure"*).
2. **Why `direction_offset_deg != 0` is rejected**:
   `pipeline/prediction/weather.py:L41` rejects any scenario with `direction_offset_deg != 0` (`status = "unavailable"`), because rotating the wind relative to a fixed windward-leeward course changes every leg from symmetrical upwind/downwind tacking into asymmetric reaching/fetch legs, which requires a full velocity-prediction polar (VPP) and layline rotation model not supported by empirical gate-time regressions.

---

### Solution 22 — Separating Axis Theorem (SAT) Contact Classification `[SYNTHETIC DATA]`
1. **Overlap classification at $\Delta x = 12.0\text{ m}$**:
   - **Platform border**: Boat $A$ spans $x \in [-5.415, +5.415]\text{ m}$; Boat $B$ spans $x \in [12.0 - 5.415, 12.0 + 5.415] = [6.585, 17.415]\text{ m}$. Because $5.415 < 6.585$, there is a $+1.170\text{ m}$ gap $\implies$ **no `platform_border` overlap** (not a physical `COLLISION`).
   - **Keep-clear border**: Boat $A$ spans $x \in [-7.415, +7.415]\text{ m}$; Boat $B$ spans $x \in [12.0 - 7.415, 12.0 + 7.415] = [4.585, 19.415]\text{ m}$. Because $7.415 > 4.585$, the `keep_clear_border` envelopes **do overlap** (`KEEP_CLEAR_BORDER_CROSSING` / `PROXIMITY`).
2. **Penetration depth**:
   Along the East–West normal axis $\vec{n} = (1, 0)$ (since longitudinally $y_A = y_B = 0$ has full $13.178\text{ m}$ overlap), the minimum penetration depth is:
   $$\text{overlapDepthM} = \min(\max_A, \max_B) - \max(\min_A, \min_B) = 7.415 - 4.585 = \mathbf{2.830\text{ m}}$$

---

### Solution 23 — Greedy Label Collision Avoidance Cost Function `[ACTUAL REPOSITORY EVIDENCE]`
1. **Lexicographic priority hierarchy**:
   - $10^6 \times \text{obstacles}$: Highest priority — never overlap an already-placed boat label.
   - $10^5 \times \text{coveredVessels}$: Second priority — never cover a boat hull anchor within $\pm 14\text{ px}$.
   - $10^3 \times \text{courseOverlap}$: Third priority — avoid covering course mark/gate pills (`WINDWARD GATE`, `LEEWARD GATE`, `START`).
   - $10 \times \text{hudOverlap}$: Fourth priority — avoid the bottom-left wind HUD reserve box (`320 x 112 px`).
   - $1 \times \text{distance}$: Tie-breaker — pick the candidate closest in Euclidean screen pixels to the boat's anchor $(x, y)$.
2. **Grid fallback condition (`boatPresentation.ts:L50-L59`)**:
   If after greedy placement any two boat labels still overlap (`crowded == true`) or a label overlaps the HUD reserve box (`underHud == true` and the vertical grid fits above the HUD), `layoutBoatLabels` switches to an evenly spaced multi-column slot assignment sorted by anchor distance. **Boat hull geometry never moves**; only the floating HTML callout cards move, connected to the true vessel positions by SVG leader lines.

---

### Solution 24 — Local Forecast Scenario Middleware Lock & PID Handshake `[ACTUAL REPOSITORY EVIDENCE]`
1. **Workspace lock**:
   `scripts/forecastScenarios.ts` acquires an exclusive lock directory/file inside `.forecast/` before spawning `python -m pipeline.prediction build --race ...`.
2. **PID handshake & recovery**:
   The Node middleware writes both its own PID and the spawned Python child PID into the lock metadata before releasing the startup handshake, and attaches a 10-minute watchdog timer. If a previous server crashed, a new server inspects the recorded owner PID and child PID via OS process checks (`process.kill(pid, 0)`); the lock is reclaimed if and only if **both** the parent server and child Python exporter have terminated.

---

## Solutions to Tier III — Advanced, Derivations & False-Confidence Traps (Q25–Q36)

### Solution 25 — Mathematical Derivation: The Tied-$N$ Expected Rank Sum Identity `[MATHEMATICAL DERIVATION]`
1. **Realized rank sum proof**:
   Let $F = N - M$ finishers receive ranks $1, 2, \dots, F$, and let $M$ nonfinishers each receive rank $N$. Notice that in a complete permutation without nonfinishers, the bottom $M$ positions would have received ranks $F+1, F+2, \dots, N$, whose sum is:
   $$\sum_{k=1}^M (F + k) = MF + \frac{M(M+1)}{2} = M(N - M) + \frac{M(M+1)}{2} = MN - \frac{M(M-1)}{2}$$
   Under the tied-$N$ rule, those $M$ boats instead receive total rank $MN$. Replacing the bottom $M$ permutation ranks with $MN$ changes the total sum from $\frac{N(N+1)}{2}$ to:
   $$\sum_{i=1}^N R_i = \frac{N(N+1)}{2} + \left(MN - \left(MN - \frac{M(M-1)}{2}\right)\right) = \mathbf{\frac{N(N+1)}{2} + \frac{M(M-1)}{2}} \qquad \blacksquare$$
2. **Expectation**:
   By linearity of expectation over the random number of nonfinishers $M \in \{0, 1, \dots, N\}$:
   $$\sum_{i=1}^N \mathbb{E}[R_i] = \frac{N(N+1)}{2} + \frac{1}{2}\mathbb{E}[M(M-1)] = \frac{N(N+1)}{2} + \sum_{m=2}^N \mathbb{P}(M = m)\frac{m(m-1)}{2}$$
3. **Why $M=0$ and $M=1$ conserve the sum**:
   When $M = 0$, $\frac{0(-1)}{2} = 0$. When $M = 1$ (a single boat fails to finish), that boat receives rank $N$, which is the **exact same rank** ($N$) it would have received as the last-place boat in a full permutation ($\frac{1(0)}{2} = 0$)! Only when $M \ge 2$ do multiple boats share rank $N$ instead of $N-1, N-2, \dots$, creating a positive excess $\frac{M(M-1)}{2} > 0$.

---

### Solution 26 — Mathematical Derivation: Analytic Plackett–Luce Expected Rank `[MATHEMATICAL DERIVATION]`
1. **Closed-form expected rank**:
   For boat $i$, let $C_i \in \{0, 1\}$ be its completion indicator ($\mathbb{P}(C_i = 1) = s_i$).
   - If $C_i = 0$ (probability $1 - s_i$), boat $i$ receives rank $R_i = N$.
   - If $C_i = 1$ (probability $s_i$), boat $i$'s rank among the finishers is $1$ plus the number of other boats $j \ne i$ that **both** complete ($C_j = 1$) **and** finish ahead of $i$ ($T_j < T_i$):
     $$R_i \big|_{C_i = 1} = 1 + \sum_{j \ne i} C_j \cdot \mathbb{I}(T_j < T_i)$$
   Under Plackett–Luce (equivalently, independent exponential race clocks $E_k / w_k$), conditional on $C_i = 1$ and $C_j = 1$, the pairwise probability that $j$ beats $i$ depends only on $(w_i, w_j)$ by Luce's Choice Axiom: $\mathbb{P}(T_j < T_i \mid C_i=1, C_j=1) = \frac{w_j}{w_i + w_j}$. Since $C_j$ is independent of $C_i$ with $\mathbb{E}[C_j] = s_j$, taking expectations yields:
   $$\mathbb{E}[R_i] = N(1 - s_i) + s_i \left(1 + \sum_{j \ne i} s_j \frac{w_j}{w_i + w_j}\right) \qquad \blacksquare$$
2. **Sum when $s_i \equiv 1$**:
   When $s_i = 1$ for all $i$, $\sum_{i=1}^N \mathbb{E}[R_i] = N + \sum_{i < j} \left(\frac{w_j}{w_i + w_j} + \frac{w_i}{w_i + w_j}\right) = N + \binom{N}{2}(1) = N + \frac{N(N-1)}{2} = \frac{N(N+1)}{2}$.

---

### Solution 27 — Counterexample Proof: Highest Win Probability $\ne$ Best Expected Finish Position `[MATHEMATICAL DERIVATION]`
1. **Exact calculations**:
   - **Boat $A$**: $\mathbb{P}(\text{win}) = \mathbf{0.45}$, $\mathbb{E}[R_A] = 0.45(1) + 0.40(3) + 0.15(3) = 0.45 + 1.20 + 0.45 = \mathbf{2.10}$.
   - **Boat $B$**: $\mathbb{P}(\text{win}) = \mathbf{0.40}$, $\mathbb{E}[R_B] = 0.45(2) + 0.40(1) + 0.15(2) = 0.90 + 0.40 + 0.30 = \mathbf{1.60}$.
   - **Boat $C$**: $\mathbb{P}(\text{win}) = \mathbf{0.15}$, $\mathbb{E}[R_C] = 0.45(3) + 0.40(2) + 0.15(1) = 1.35 + 0.80 + 0.15 = \mathbf{2.30}$.
   Boat $A$ has the highest win probability ($45\% > 40\%$), but Boat $B$ has a substantially better expected finish position ($1.60 < 2.10$).
2. **Physical sailing interpretation**:
   Boat $A$ is a bimodal "flyer" (e.g., splitting hard to the right boundary looking for a wind shift: if the right shift hits, $A$ wins; if the left shift hits, $A$ finishes last in 3rd). Boat $B$ sails down the middle of the course, covering the fleet: it finishes 1st or 2nd 100% of the time, giving a superior average finish ($1.60$) despite a slightly lower outright win rate ($40\%$).

---

### Solution 28 — Mathematical Derivation: Contrast Subspace Projection & Pairwise Variance Preservation `[MATHEMATICAL DERIVATION]`
1. **Projection properties**:
   - Symmetry: $P^\top = I_K^\top - \frac{1}{K}(\mathbf{1}_K \mathbf{1}_K^\top)^\top = P$.
   - Idempotence: $P^2 = I_K - \frac{2}{K}\mathbf{1}_K\mathbf{1}_K^\top + \frac{1}{K^2}\mathbf{1}_K(\mathbf{1}_K^\top \mathbf{1}_K)\mathbf{1}_K^\top = I_K - \frac{1}{K}\mathbf{1}_K\mathbf{1}_K^\top = P$ since $\mathbf{1}_K^\top \mathbf{1}_K = K$.
   - Annihilation of $\mathbf{1}_K$: $P\mathbf{1}_K = \mathbf{1}_K - \frac{K}{K}\mathbf{1}_K = \vec{0}$.
2. **Pairwise contrast invariance**:
   For any pair $(i, j)$, let $\vec{c}_{ij} = \vec{e}_i - \vec{e}_j$. Notice that $\mathbf{1}_K^\top \vec{c}_{ij} = 1 - 1 = 0$, which means $\vec{c}_{ij}$ already lies inside the zero-sum subspace $\mathcal{H}_0$, so $P\vec{c}_{ij} = \vec{c}_{ij}$! Therefore:
   $$\tilde{\theta}_i - \tilde{\theta}_j = \vec{c}_{ij}^\top \tilde{\theta} = \vec{c}_{ij}^\top P \vec{\theta} = (P\vec{c}_{ij})^\top \vec{\theta} = \vec{c}_{ij}^\top \vec{\theta} = \theta_i - \theta_j$$
   Since the random variable $\tilde{\theta}_i - \tilde{\theta}_j$ is point-for-point identical to $\theta_i - \theta_j$, its variance $\operatorname{Var}(\tilde{\theta}_i - \tilde{\theta}_j) = \operatorname{Var}(\theta_i - \theta_j) = \Sigma_{ii} + \Sigma_{jj} - 2\Sigma_{ij}$ is preserved identically. $\blacksquare$

---

### Solution 29 — Mathematical Derivation: Boundary Identity Between Pre-Race and Live Checkpoint $t = \text{Gun}$ `[MATHEMATICAL DERIVATION]`
1. **Why naive splitting fails**:
   If a full leg has log-time variance $\sigma^2$ and a live checkpoint at progress $u \to 0^+$ adds an independent remaining-leg residual with full variance $\sigma^2$ or resamples the crew factor $\eta_{\text{crew}}$, total variance jumps discontinuously at the gun, creating an artificial probability sawtooth at every gate rounding.
2. **Zero-information identity**:
   By holding the persistent crew draw $\eta_{\text{crew}}$ and scaling the remaining-leg innovation variance as $(1 - u)\sigma^2_{\text{innov}}$, at $u = 0$ (zero progress elapsed and no new speed/recovery observation), the remaining-leg distribution has factor $(1 - 0)\sigma^2_{\text{innov}} = \sigma^2_{\text{innov}}$ and identical mean $\mu_\ell$, reproducing the exact pre-race full-leg distribution in mean, variance, and all quantiles.

---

### Solution 30 — Mathematical Derivation: Persistent vs Independent Ability Draws in First-to-7 Series `[MATHEMATICAL DERIVATION]`
1. **Persistent tournament-level ability draw**:
   - At $p = 0.50$: by symmetry, $S(0.50) = \sum_{k=0}^6 \binom{6+k}{k} (0.5)^{7+k} = \mathbf{0.500000}$.
   - At $p = 0.90$: $S(0.90) = \sum_{k=0}^6 \binom{6+k}{k} (0.9)^7 (0.1)^k = \mathbf{0.999982}$.
   - Mixture expectation: $\mathbb{E}[S(P)] = 0.5(0.500000) + 0.5(0.999982) = 0.749991 \approx \mathbf{75.00\%}$.
2. **Independent per-race ability draw**:
   Averaging $P$ before running the series gives marginal single-race win probability $\bar{p} = 0.5(0.50) + 0.5(0.90) = 0.70$. Evaluating the negative binomial sum at $\bar{p} = 0.70$:
   $$S(0.70) = \sum_{k=0}^6 \binom{6+k}{k} (0.7)^7 (0.3)^k = \mathbf{0.937615} \approx \mathbf{93.76\%}$$
   *Intuition*: Because $S(p)$ is strongly concave on $(0.5, 1.0)$, Jensen's inequality guarantees $S(\mathbb{E}[P]) > \mathbb{E}[S(P)]$. Physically, if two boats race 13 times in the America's Cup Match, the same two AC75 hulls race every day — the syndicate does not draw a brand-new random boat design from the prior before Race 2, Race 3, ..., Race 13!

---

### Solution 31 — False-Confidence Trap: Why `1,723 / 5,000` AC38 Cup Trials Are Unresolved & Why Bounds Cannot Be Normalized `[ACTUAL REPOSITORY EVIDENCE]`
1. **Two mechanisms triggering `round_robin_challengers` (`cup.py:L302-L353`)**:
   - **Mechanism A (Fleet tie $\to$ ambiguous carry)**: After 6 preliminary fleet races (scoring `10, 9, 8, 7, 6, 5, 4`), if any two of the 6 Challengers tie on total integer fleet points, `_rank_with_ties` sets `c_fleet_tie = True` because RRSAC 102.1 / Conditions 5.2 do not specify how to break ties when assigning the `0.5`-step `CHALLENGER_CARRY = (2.5, 2.0, 1.5, 1.0, 0.5, 0.0)`.
   - **Mechanism B (Post-RR parity tie)**: Even if all 6 Challengers have distinct fleet points, 3 Challengers start the Round Robins with `.5` fractional carry (`2.5, 1.5, 0.5`) and 3 start with `.0` carry (`2.0, 1.0, 0.0`). Each Round Robin win adds `+1.0`. If any two Challengers of the same fractional parity finish the 3 Round Robins with the same total score, `c_tie = True`, flagging `round_robin_challengers` because the 6-Challenger seeding tie-break rule (which determines direct semifinalists vs Repechage seeds 4, 5, 6) is unpublished.
2. **Sum of lower and upper bounds**:
   Let $c_i$ be resolved wins for team $i$ ($\sum_{i=1}^7 c_i = N_{\text{res}} = 3{,}277$) and $U = 1{,}723$ ($u = U / 5000 = 0.3446$). Then:
   $$\sum_{i=1}^7 \text{lower}_i = \sum_{i=1}^7 \frac{c_i}{5000} = \frac{3277}{5000} = 1 - u = \mathbf{0.6554}$$
   $$\sum_{i=1}^7 \text{upper}_i = \sum_{i=1}^7 \frac{c_i + U}{5000} = (1 - u) + 7u = 1 + 6u = 0.6554 + 7(0.3446) = \mathbf{3.0676}$$
3. **Why normalizing midpoints is invalid**:
   The midpoint of $[\text{lower}_i, \text{upper}_i]$ is $\frac{c_i + U/2}{5000}$, and normalizing midpoints assigns team $i$ a share of the $1{,}723$ unresolved trials equal to $\frac{c_i + U/2}{3277 + 7U/2}$ (a blend of resolved-win proportionality and uniform $1/7$ allocation — even attributing tied Challenger Round Robin trials to Defender `ETNZ` or to Challengers that were not even involved in the tie!). That fabricates a non-existent RRSAC tie-break rule.

---

### Solution 32 — False-Confidence Trap: Unobserved Entrant (`AUSTRALIA`) vs Observed Zero Strength (`0.0`) `[ACTUAL REPOSITORY EVIDENCE]`
1. **Sampling equations at $\rho = 1.0, \sigma_{\text{team}} = 0.5$**:
   - **Observed team with $\hat{\mu} = 0.0$**: $\theta_s = 1.0(0.0) + \sqrt{1 - 1.0^2}(0.5)Z_s = \mathbf{0.0}$ (zero variance! The model is 100% certain the team is exactly average).
   - **Unobserved team (`AUSTRALIA`, `observed = False`)**: $\theta_s = \sigma_{\text{team}} Z_s = \mathbf{0.5\,Z_s} \sim \mathcal{N}(0, 0.25)$ (full population prior uncertainty!).
2. **The historical bug**:
   When an earlier code path initialized `AUSTRALIA` to `0.0` in the strength dictionary before checking `observed`, setting $\rho = 1.0$ collapsed `AUSTRALIA`'s capability variance to $0$, artificially preventing an unknown syndicate from ever drawing a strong or weak AC75 hull design.

---

### Solution 33 — False-Confidence Trap: First Received Finish vs Globally Resolved Winner `[ACTUAL REPOSITORY EVIDENCE]`
1. **Event time vs receipt time & opponent ambiguity**:
   Under causal telemetry ingestion with up to 6 s reorder latency and certified Kalman outages, receiving a finish crossing packet for Boat $A$ does not prove that a missing or uncertified opponent Boat $B$ did not cross earlier during a telemetry dropout or did not have an unresolved course anomaly.
2. **Specific anomaly in `naples_mr_final`**:
   In `naples_mr_final`, `ITA B` has no recorded Leg 5 gate crossing (`Gates = [1, 2, 3, 4, 6]`), so `ITA B`'s causal leg state becomes gate-ambiguous after Leg 4. Because the global on-water status of both match-race boats is not cleanly resolved through all 6 gates, `state.py` refuses to certify a terminal `100%` live probability.

---

### Solution 34 — False-Confidence Trap: What a Peer Index of `110` Does and Does Not Support `[EXPLAIN TO ANOTHER PERSON]`
1. **Denominator Scope (`6` Peers, Not `8`)**: `USA` (start-state conflict) and `GBR B` (retired on Leg 1 with held tail) are excluded from the peer baseline; on Leg 4, `NZL B` and `SUI` also drop out due to $<95\%$ coverage, leaving only `4` peers.
2. **VMG vs Boat Speed (`110.32` vs `109.32`)**: `upwind_vmg` projects velocity onto the course axis (`45°`). Sailing in a localized wind lift or choosing the favored side of the course increases `upwind_vmg` even if through-the-water hull speed is identical.
3. **Equal-Leg Weighting**: `performance-1` averages leg indices with equal weight across matched legs, regardless of leg duration or wind speed variability.
4. **One-Design AC40 vs Custom AC75**: All 2026 races were sailed in strict one-design AC40 hulls in $\sim 13\text{ kt}$ breeze; differences reflect crew helming, trim, and tactics in moderate air, not custom AC75 foil/hull design in $18\text{ kt}$.

---

### Solution 35 — Adversarial Audit: Why `PositiveDelayMixture` Is `available = False` `[ACTUAL REPOSITORY EVIDENCE]`
1. **Published status**:
   In every model card under `public/data/predictions/models/*.json`, `delay_mixture.available = False` and `delay_mixture.promoted = False`.
2. **Evidence gates & statistical danger**:
   `fit_positive_delay_mixture` (`pipeline/prediction/models.py:L668-L710`) requires at least `50` reviewed clean leg intervals and `20` reviewed loss episodes across at least `3` distinct race days (`reviewed_clean = 0, reviewed_loss = 0` currently). Fitting an unconstrained 2-component `LogNormal + Gamma` mixture via EM on small, unlabelled leg-time samples is notoriously ill-conditioned: EM splits skewness or wind-speed differences across race days into phantom "touchdown delay" components with arbitrary mixture weights $\pi$, degrading out-of-sample calibration.

---

### Solution 36 — Oral Defense Synthesis: Explain, Critique, Defend & Improve the System `[EXPLAIN TO ANOTHER PERSON]`
1. **Explain (Ownership Split)**: Historical metrics (`historical-2`, `performance-1`) and causal forecasts (`prediction-1`, `cup-1`) depend on multi-pass quality gates, source-conflict checks, empirical Bayes shrinkage, and Monte Carlo integration over the raw `.jsonl` archive — logic that must remain single-sourced in Python so exports, CSV reports, and UI views never drift. Conversely, 60 fps boat positions, live metre/second lead gaps (`getStandings`), and pairwise offsets (`compareBoats`) are deterministic functions of the current playhead timestamp and user-selected boat pair, requiring zero-latency client-side evaluation in TypeScript.
2. **Critique (Most Consequential Limitation)**: The effective sample size is **28 sessions across 9 race days** (only 15 competitive fleet/match races after excluding 13 practice races), with **zero official race-committee result sheets (`official_order_verified = False`)** and **zero audited completion/penalty logs**. Millions of 10 Hz frames provide rich within-race geometry, but cannot substitute for independent race days when estimating reliability hazards, weather slopes, or cross-class skill transfer.
3. **Defend (`null` Headline Cup Probabilities & `34.46 pp` Bounds)**: In `34.46%` (`1,723 / 5,000`) of baseline AC38 tournament simulations, two or more Challengers tie in the 6-race fleet carry-over or 3-Round-Robin standings where RRSAC 102.1 tie-break procedures for 6 Challengers are unpublished. Converting `[lower, upper]` intervals into single point probabilities would require inventing an unauthorized rule and pretending AC40-to-AC75 transfer $\rho$ is known. Reporting exact outer bounds (`[16.86%, 51.32%]` for `ETNZ`) separates what the simulation proves from what the rules leave open.
4. **Improve (Highest-Leverage Next Engineering Steps)**:
   - *First*: Create `docs/forecast_completion_review.json` (`completion-review-1`) and official finishing order overrides from race-committee sheets, resolving the `USA` start conflict in `naples_pr1`, fixing `reconstruction.py:L228` (`comp.get("start_state", {}).get("started")`), and unlocking audited exogenous-vs-timerule hazard estimation in `CompletionModel`.
   - *Second*: Encode the official RRSAC 107 / 102.1 tie-break hierarchy in `pipeline/prediction/cup.py` (`_rank_with_ties`), collapsing the `34.46 pp` baseline rule-bound width to pure Monte Carlo sampling precision ($\pm 1.39\text{ pp}$).
