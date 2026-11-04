# 05 — Study Routes, Dependency-Aware Reading Order & Unresolved Trip Questions

**Repository**: `2D_regatta_replay` | **Snapshot**: `2026-11-04` | **Offline Location**: `study-materials/05_Study_Routes_and_Questions.html`

> **How to Use These Routes in the Mountains**: Whether you have a single hour on the train, a full day at a cabin table, or three uninterrupted days in the mountains, follow the structured tracks below. Every reference points to a local file in this pack that works without internet access.

---

## 1. The One-Hour Orientation Route (60 Minutes)

**Goal**: Understand what the system does, where the Python/TypeScript boundary sits, what data actually exists in the 28-race archive, and why the three forecasting targets behave differently.

| Time Block | Activity | Local Pack Files to Open | Key Takeaway to Verify |
| :--- | :--- | :--- | :--- |
| **00:00 – 00:15** | **System on One Page & Ownership** | [`02_Field_Guide.pdf`](../02_Field_Guide.pdf) (Sections 1–2) & `fig02_system_architecture_ownership.svg` | Python owns historical metrics (`historical-2`, `performance-1`) and forecasts (`prediction-1`, `cup-1`); TypeScript owns 60 fps display interpolation and live pairwise geometry. |
| **00:15 – 00:30** | **Problem, Sailing Primer & Archive Reality** | [`01_Repository_Explained.pdf`](../01_Repository_Explained.pdf) (Parts I & II) + `fig01_sailing_primer_course.svg` & `fig03_evidence_ladder.svg` | 28 sessions across 9 race days (`6.87 GB`), `224` replayed vs `227` scheduled boat-races, and `0` official race-committee result sheets (`official_order_verified = False`). |
| **00:30 – 00:45** | **Three Forecasting Targets & Rule Bounds** | [`02_Field_Guide.pdf`](../02_Field_Guide.pdf) (Section 4) + `fig06_forecasting_three_targets_and_cup.svg` + Screenshot `08_forecast_cup_2027_bounds.png` | Why pre-race sums exceed $K(K+1)/2$ (tied-$N$), why live checkpoints have $+6\text{ s}$ publication delay, and why 2027 Cup point probabilities are `null` (`34.46%` RRSAC 102.1 ties). |
| **00:45 – 01:00** | **Interactive Sandbox & Oral Rehearsal** | [`examples/interactive_sailing_and_forecast_lab.html`](../examples/interactive_sailing_and_forecast_lab.html) + [`04_Workbook.pdf`](../04_Workbook.pdf) (Question 36) | Test wind-referenced vs mark-referenced VMG and practice the 4-part oral defense (Explain, Critique, Defend, Improve). |

---

## 2. The One-Day Conceptual Review Route (6–8 Hours)

**Goal**: Master the end-to-end mathematical pipeline from raw `.jsonl` telemetry to 10 Hz replay reconstruction, peer-normalized historical radar indices, causal forecasting, and UI rendering.

1. **Session 1 (90 min) — Raw Archive, Projection & Replay Reconstruction**:
   - Read **Parts I, II, and III** of [`01_Repository_Explained.pdf`](../01_Repository_Explained.pdf).
   - Inspect [`pipeline/ingest.py`](../source-companion/view/pipeline/ingest.py.html#L444), [`pipeline/projection.py`](../source-companion/view/pipeline/projection.py.html#L20), [`pipeline/synchronize.py`](../source-companion/index.html), and [`pipeline/reconstruction.py`](../source-companion/view/pipeline/reconstruction.py.html#L39) in the offline Source Companion.
   - Run or read [`examples/01_verify_projection_and_bow_crossing.py`](../examples/01_verify_projection_and_bow_crossing.py) and solve **Questions 1–4, 7–8** in [`04_Workbook.pdf`](../04_Workbook.pdf).
2. **Session 2 (90 min) — Historical Metrics, Peer Radar & Tactical Wind Slope**:
   - Read **Part IV** of [`01_Repository_Explained.pdf`](../01_Repository_Explained.pdf).
   - Inspect [`pipeline/historical_analysis.py`](../source-companion/view/pipeline/historical_analysis.py.html#L580) (`_boat_performance`, `_event_analysis`) and [`pipeline/tactical_insights.py`](../source-companion/view/pipeline/tactical_insights.py.html#L178).
   - Run or read [`examples/02_reconcile_performance_index.py`](../examples/02_reconcile_performance_index.py) and solve **Questions 13–17, 34** in [`04_Workbook.pdf`](../04_Workbook.pdf).
3. **Session 3 (120 min) — Causal State Estimation, Plackett–Luce, Correlated MC & AC38 Cup Bounds**:
   - Read **Part V** of [`01_Repository_Explained.pdf`](../01_Repository_Explained.pdf).
   - Inspect [`pipeline/prediction/state.py`](../source-companion/view/pipeline/prediction/state.py.html#L1), [`models.py`](../source-companion/view/pipeline/prediction/models.py.html#L1), [`simulation.py`](../source-companion/view/pipeline/prediction/simulation.py.html#L1), and [`cup.py`](../source-companion/view/pipeline/prediction/cup.py.html#L1).
   - Run or read [`examples/03_plackett_luce_and_cup_bounds.py`](../examples/03_plackett_luce_and_cup_bounds.py) and solve **Questions 18–21, 25–33** in [`04_Workbook.pdf`](../04_Workbook.pdf).
4. **Session 4 (90 min) — Frontend Engine, Verification & Case Studies**:
   - Read **Parts VI, VII, VIII, and IX (Case Studies 1–3)** of [`01_Repository_Explained.pdf`](../01_Repository_Explained.pdf).
   - Drill 30+ cards in [`study-materials/flashcards_viewer.html`](flashcards_viewer.html).

---

## 3. The Three-Day Deeper Study Route (Mountain Mastery Track)

### Day 1 — Physical Telemetry, Computational Geometry & Reconstruction Audits
* **Morning**: Deep reading of Parts I–III of `01_Repository_Explained.pdf` alongside `docs/source_audit.md`, `docs/data_schema.md`, and `docs/reconstruction_math.md` in `source-companion/`.
* **Afternoon**: Trace every line of `pipeline/ingest.py`, `pipeline/projection.py`, `pipeline/synchronize.py`, `pipeline/reconstruction.py`, `pipeline/manoeuvres.py`, and `pipeline/analytics.py`. Verify the 6 code-vs-doc discrepancies (such as `reconstruction.py:L228` `comp.get("started")`, `manoeuvres.py:L57` `2.5 kt` vs `3.0 kt` docstring, and `90%` vs `95%` recovery thresholds).
* **Evening**: Complete Workbook Tier I (Q1–Q12) and Case Study 1 (`naples_pr1`).

### Day 2 — Historical Cohort Analytics, Causal Probability Models & Tournament Simulation
* **Morning**: Deep reading of Parts IV & V of `01_Repository_Explained.pdf` alongside `pipeline/historical_analysis.py` (`1,654` lines) and `pipeline/tactical_insights.py` (`369` lines). Reconcile `evidence/naples_pr1_performance.csv` and `evidence/naples_mr_final_performance.csv` by hand.
* **Afternoon**: Trace `pipeline/prediction/{contracts,labels,state,models,simulation,cup,evaluation,build}.py`. Work through the mathematical proofs of the Tied-$N$ Rank Sum Identity, Contrast Subspace Covariance, Zero-Information Boundary Identity, Persistent vs Independent Series Win Probability (`75.00%` vs `93.76%`), and RRSAC 102.1 Rule Bounds (`[lower, upper]`).
* **Evening**: Complete Workbook Tier II (Q13–Q24) and Tier III derivations (Q25–Q33), plus Case Studies 2 (`naples_mr_final`) and 3 (`26_09_22_nap_ipr_pr2` & `26_09_23_nap_ipr_pr1`).

### Day 3 — Frontend Architecture, Verification Engineering, Weaknesses & Next Experiments
* **Morning**: Deep reading of Parts VI, VII, and VIII of `01_Repository_Explained.pdf`. Trace `src/App.tsx`, `src/engine/{ReplayEngine,interpolate,analytics,contactDetector,analysisCatalog,predictionCatalog}.ts`, `src/components/canvas/{CourseCanvas,ViewportMatrix,boatModels,boatPresentation}.ts(x)`, and `scripts/forecastScenarios.ts`.
* **Afternoon**: Review the 828 deterministic tests (`tests/unit/`, `tests/e2e/test_runner.py`, `tests/tier5_integrity.py`, `src/**/__tests__/`) and the 5 falsifiable research experiments in Part VIII.
* **Evening**: Complete all 64 flashcards in `flashcards_viewer.html`, read aloud or rehearse with `06_Audio_Narration_Script.md`, and draft your own architecture improvement plan using Section 5 below.

---

## 4. Dependency-Aware Source Reading Order

Because modules build on upstream data contracts, read the first-party codebase in this exact topological order (all clickable in [`source-companion/index.html`](../source-companion/index.html)):

1. **Level 0 — Contracts & Constants**:
   `PROJECT.md` $\to$ `AGENTS.md` $\to$ `pipeline/config.py` $\to$ `src/types/replay.ts` $\to$ `src/types/analysis.ts` $\to$ `src/types/prediction.ts`.
2. **Level 1 — Ingestion, Projection & Synchronization**:
   `pipeline/projection.py` $\to$ `pipeline/ingest.py` $\to$ `pipeline/synchronize.py`.
3. **Level 2 — Event Reconstruction & Geometry**:
   `pipeline/reconstruction.py` $\to$ `pipeline/manoeuvres.py` $\to$ `pipeline/analytics.py` $\to$ `pipeline/export_replay.py` $\to$ `pipeline/canonical_tables.py`.
4. **Level 3 — Historical & Tactical Analytics**:
   `pipeline/tactical_insights.py` $\to$ `pipeline/historical_analysis.py` $\to$ `pipeline/environment.py` $\to$ `scripts/analysis_snapshot.py`.
5. **Level 4 — Causal Forecasting & AC38 Cup Simulation**:
   `pipeline/prediction/contracts.py` $\to$ `pipeline/prediction/labels.py` $\to$ `pipeline/prediction/state.py` $\to$ `pipeline/prediction/models.py` $\to$ `pipeline/prediction/simulation.py` $\to$ `pipeline/prediction/cup.py` $\to$ `pipeline/prediction/evaluation.py` $\to$ `pipeline/prediction/build.py`.
6. **Level 5 — Frontend Engine & Catalogs**:
   `src/engine/interpolate.ts` $\to$ `src/engine/ReplayEngine.ts` $\to$ `src/engine/analytics.ts` $\to$ `src/engine/contactDetector.ts` $\to$ `src/engine/manifest.ts` $\to$ `src/engine/analysisCatalog.ts` $\to$ `src/engine/predictionCatalog.ts`.
7. **Level 6 — Canvas, Workspaces & Middleware**:
   `src/components/canvas/ViewportMatrix.ts` $\to$ `src/components/canvas/boatModels.ts` $\to$ `src/components/canvas/boatPresentation.ts` $\to$ `src/components/canvas/CourseCanvas.tsx` $\to$ `src/App.tsx` $\to$ `src/components/dashboard/{BoatPerformanceCard,ForecastWorkspace,ReportsWorkspace}.tsx` $\to$ `scripts/forecastScenarios.ts`.
8. **Level 7 — End-to-End Integrity Verification**:
   `tests/tier5_integrity.py` $\to$ `tests/e2e/test_runner.py` $\to$ `tests/unit/test_prediction.py`.

---

## 5. Fifteen Unresolved Questions Worth Thinking About on the Trip

1. **Two-Hull Syndicate Collapse (`GBR B/G`, `ITA B/G`, `NZL B/G`)**: In 2026 AC40 racing, three syndicates sailed two boats simultaneously (often splitting into an "A/Senior" crew and a "Youth/Women/Development" crew), and `cup.py` maps them to 2027 AC75 team strength by taking the unweighted arithmetic mean $(\hat{\beta}_B + \hat{\beta}_G)/2$. Would taking the **maximum** of the two hulls (or weighting by senior helmsman roster) better reflect single-boat AC75 capability?
2. **Equal-Leg vs Time/Distance-Weighted Peer Indices**: `performance-1` computes a dimension's race index as the unweighted mean of per-leg indices $\frac{1}{|L|}\sum_\ell I_{b,\ell}$. If Leg 1 is a 240-second beat and Leg 5 is a shortened 80-second beat to the finish, should leg indices be weighted by leg distance or duration?
3. **Resolving the `USA` Start Conflict (`pipeline/reconstruction.py:L228`)**: If we fix `comp.get("start_state", {}).get("started")` in `reconstruction.py` so `USA` in `naples_pr1` is classified as `DNS`/`OCS` instead of `RANK_4`, how should the replay UI visually distinguish a boat that physically sailed all 4 legs on the water (practice shadow sailing) from a legal competitor?
4. **Monotonic Gate-Time Filtering (`26_09_22_nap_ipr_pr2`)**: In `historical_analysis.py`, when a source `leg_timings` timestamp is non-monotonic (like `USA` Leg 3 in `pr2`), the current code rejects Leg 3 but uses Leg 3's backward timestamp as Leg 4's start time, causing Leg 2 and Leg 4 to overlap by `171.9 s`. Should `_leg_entry_for_boat` enforce $\text{start\_ms}_\ell = \max_{k < \ell}(\text{end\_ms}_k)$ or fall back to reconstructed bow crossings whenever source `leg_timings` violate monotonicity?
5. **Tactical Wind Projection Gates (`0 / 3,455` Active)**: All 7 projection gates in `tactical_insights.py` are well-motivated individually, but their conjunction suppresses 100% of 5-minute projections across all 28 races. Is a linear OLS trend over 120 s fundamentally the wrong functional form for oscillating Mediterranean sea-breeze shifts (where a damped sinusoid / AR(2) spectral peak might capture phase rather than linear drift)?
6. **Pre-Race Wind Speed Conditioning**: Currently, `export_pre_race_scenario` uses the static `joint_pl_reference` model so expected positions are invariant to `tws_kt`. Since `LegTimeModel` already includes a log-TWS slope $\beta_{\text{tws}}$, under what conditions would team-specific wind-speed interactions $\beta_{\text{tws}, i}$ become statistically identifiable without overfitting 9 race days?
7. **Practice vs Competitive Weighting ($w = 0.5$)**: `StrengthModel` weights practice fleet races at $w = 0.5$ relative to competitive fleet races ($w = 1.0$). In practice races, leading boats frequently peel off early on Leg 3 or Leg 4 to save equipment. Does $w = 0.5$ still allow intentional practice peel-offs to bias completion and leg-time models downward for top teams?
8. **RRSAC 102.1 Tie-Break Sensitivity**: In `cup_2027.json`, `34.46%` of baseline trials are unresolved because any tie in 6-race fleet points or 6-Challenger Round Robin standings halts exact point attribution. What if we separate **non-pivot ties** (e.g., a tie between 5th and 6th seed that only swaps Repechage 1 lane assignment) from **pivot ties** (a tie across the 3rd/4th direct-semifinal cutoff)? How much of the `34.46 pp` width would collapse without inventing any tie-break rule?
9. **Manoeuvre Entry/Exit Window Asymmetry**: `ManoeuvreDetector` defines entry speed over $[-6.5\text{ s}, -2.5\text{ s}]$ before peak turn rate, whereas `historical_analysis.py` measures recovery up to $+15.0\text{ s}$ at a $95\%$ threshold. When a boat tacks immediately into a wind header or mark-rounding bear-away, its optimal post-tack target speed changes — how can recovery metrics normalize for target polar speed rather than pre-tack entry speed?
10. **GNSS Attitude vs Heading-Only Bow Projection**: `_bow_point` projects the $+12.963\text{ m}$ bowsprit in 2D using `heading` ($\psi$) assuming zero pitch and heel. During high-speed foiling or a splashdown bow-down pitch of $8^\circ$, how many centimetres does the horizontal projection of the bowsprit foreshorten, and could that affect photo-finish gate calls?
11. **Kalman Filter Turn-Rate Switching**: `CVKalmanFilter` uses a constant-velocity model where acceleration noise $q$ is isotropic. During an $18^\circ/\text{s}$ foiling gybe, the boat experiences strong centripetal acceleration orthogonal to velocity. Would an Interacting Multiple Model (IMM) filter combining Constant-Velocity and Constant-Turn-Rate (CTRV) improve 10–30 s outage containment during manoeuvres?
12. **Separating Tactical Flyers from Boat Speed in `LegTimeModel`**: In live simulation, `LegTimeModel` models remaining leg time as a function of scalar `progress_m` remaining. Two boats at the same `progress_m` — one in the center of the course and one on the extreme layline — have identical distance to go, but the layline boat must sail extra tacks/distance (`cos(TWA)` penalty). How can cross-track distance from the gate centerline be incorporated into effective remaining distance?
13. **Spatial Wind Field Non-Uniformity**: `windAt` and `tactical_insights.py` treat wind on the course at timestamp $t$ as a single spatially uniform vector $(\text{TWD}(t), \text{TWS}(t))$. Since all 9 AC40s log onboard `twd` and `tws` simultaneously across a $2\text{ km} \times 1\text{ km}$ box, could we reconstruct a 2D spatial wind-pressure gradient across the course?
14. **Client-Side Bundle vs Lazy Data Architecture**: As the archive grows from 28 races to 100+ races in 2027, `public/data/analysis/index.json` (`2.1 MB`) and `.forecast/` artifacts will scale linearly. Where should pagination or IndexedDB caching be introduced in `analysisCatalog.ts` and `predictionCatalog.ts`?
15. **Epistemic Honesty as a Design Pattern**: Most sports analytics dashboards hide missing data behind imputed numbers and forced $100\%$ bar charts. This repository does the opposite — surfacing `conflict`, `low_coverage`, `gate_ambiguous`, and `[lower, upper]` rule bounds as first-class UI elements. Where else in quantitative engineering should this "refuse to fabricate precision" architecture be applied?
