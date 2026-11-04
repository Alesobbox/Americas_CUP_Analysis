# Repository atlas and evidence index

This atlas describes the selected first-party reading snapshot of4 November2026. It maps conceptual responsibilities, execution order, inputs, consumers, status and tests. The actual source copy contains213 files; evidence/snapshot.json identifies their bytes and the dirty working tree. This is a reading set, not a complete Git clone or operational backup. No raw telemetry, dependency tree, credentials or prepared feature cache is bundled.

## Execution order

Replay path: session identity → local projection and channel synchronization → crossing/leg/manoeuvre reconstruction → replay and historical exports → catalogs and browser. Forecast path branches from raw causal observations → sealed dataset → state and cutoff-aware labels → strength/completion models → correlated simulation or declared reference → tournament adaptation → validated immutable publication. Historical summaries are not causal live features. Environment acquisition and report/previews generation are separate refresh paths.

## Explicit subsystem coverage

Every row below was routed through project contracts and focused current source review. “Inspected” means key paths and relevant tests were examined, not every line formally proved. The textbook contains the deep explanations and five interface journeys. The complete manifest lists the copied files without pretending a directory listing explains them.

| Subsystem | Phase | Status | Explained |

| --- | --- | --- | --- |

| Session identity | Ingestion | Active | Inspected and explained below |

| Configuration and venue projection | Ingestion | Active | Inspected and explained below |

| Streaming ingestion and synchronization | Ingestion | Active | Inspected and explained below |

| Gate and race reconstruction | Ingestion | Active | Inspected and explained below |

| Progress and legacy summaries | Ingestion | Active with compatibility fields | Inspected and explained below |

| Manoeuvre detection | Ingestion | Active | Inspected and explained below |

| Contact coalescing | Ingestion | Active | Inspected and explained below |

| Pipeline orchestration and export | Ingestion | Active | Inspected and explained below |

| Historical metric producer | Historical refresh | Active scientific owner | Inspected and explained below |

| Peer performance and debrief | Analytics refresh | Active optional extension | Inspected and explained below |

| Tactical insights | Analytics refresh | Active recorded trends; projections gated | Inspected and explained below |

| Environment context | Acquisition and browser display | Active contextual estimates | Inspected and explained below |

| Causal forecast dataset | Forecast preparation | Active | Inspected and explained below |

| Forecast weather support | Forecast preparation and scenario support | Active support gates; directional response unavailable | Inspected and explained below |

| Forecast state | Forecast checkpoints | Active | Inspected and explained below |

| Completion labels and results | Forecast preparation and evaluation | Active source-reconstructed evidence | Inspected and explained below |

| Strength and ranking models | Forecast fitting | Active reference plus experimental alternatives | Inspected and explained below |

| Joint race simulation | Forecast generation | Provisional correlated candidate selected for baseline | Inspected and explained below |

| Chronological evaluation | Research evaluation | Active evaluation; calibration unestablished | Inspected and explained below |

| Cup tournament adaptation | Event forecast generation | Active conditional scenarios | Inspected and explained below |

| Forecast contracts and publications | Generation and verification | Active | Inspected and explained below |

| Shared browser context | Browser interaction | Active | Inspected and explained below |

| Replay catalogs and interpolation | Browser loading and playback | Active plus legacy catalog compatibility | Inspected and explained below |

| Analysis and prediction catalogs | Browser artifact loading | Active | Inspected and explained below |

| World to screen and course layers | Browser rendering | Active | Inspected and explained below |

| Vessels labels trails and physical geometry | Browser rendering and geometry | Active | Inspected and explained below |

| Analysis evidence and radar | Browser interaction | Active | Inspected and explained below |

| Replay tactical and debrief navigation | Browser interaction | Active | Inspected and explained below |

| Two boat comparison | Browser interaction | Active | Inspected and explained below |

| Reports inventory CSV and discovery | Export generation and browser downloads | Active | Inspected and explained below |

| Forecast workspace and exact scenario service | Browser and local server | Active local generation; static display supported | Inspected and explained below |

| Race library presentation and design | Presentation refresh and browser | Active optional previews | Inspected and explained below |

| Verification and operating scripts | Local verification and operation | Active | Inspected and explained below |

## Session identity

Session asset metadata resolves boats and marks before any track is attributed. It feeds ingestion and source provenance; a wrong identity can contaminate every downstream calculation.

Entry points: pipeline/identity.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_dashboard_identity.py.

[pipeline/identity.py:L1-L1] [tests/unit/test_dashboard_identity.py:L1-L1]

## Configuration and venue projection

Geographic origins, local curvature coefficients and unit conversions turn WGS84 positions into east/north metres. Replay exports retain the inverse-map parameters for Map rendering.

Entry points: pipeline/config.py, pipeline/projection.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_projection_adversarial.py.

[pipeline/config.py:L1-L1] [pipeline/projection.py:L1-L1] [tests/unit/test_projection_adversarial.py:L1-L1]

## Streaming ingestion and synchronization

JSONL observations become identity-resolved channel streams, source coverage and a regular replay grid. Angular interpolation differs from scalar interpolation; regular frames do not create source support.

Entry points: pipeline/ingest.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_ingest.py.

[pipeline/ingest.py:L1-L1] [tests/unit/test_ingest.py:L1-L1]

## Gate and race reconstruction

Positions, course sequences, source timing and classifications become starts, directed crossings, legs and finish states. Endpoint extension and sampled moving marks are reconstruction assumptions. Consumers include analytics, exports and historical windows.

Entry points: pipeline/reconstruction.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_reconstruction.py.

[pipeline/reconstruction.py:L1-L1] [tests/unit/test_reconstruction.py:L1-L1]

## Progress and legacy summaries

Reconstructed leg state and positions become progress, rank, continuous-gap estimates and legacy replay summaries. Their display definitions must not replace canonical historical fields.

Entry points: pipeline/analytics.py. Phase: Ingestion. Status: Active with compatibility fields. Test route: tests/unit/test_analytics.py.

[pipeline/analytics.py:L1-L1] [tests/unit/test_analytics.py:L1-L1]

## Manoeuvre detection

Wind side, motion and source support produce candidate tacks, gybes and detector windows. Historical analysis subsequently applies its own event eligibility and recovery definition. Detected events are a selected set.

Entry points: pipeline/manoeuvres.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_manoeuvres.py.

[pipeline/manoeuvres.py:L1-L1] [tests/unit/test_manoeuvres.py:L1-L1]

## Contact coalescing

Frame-level modeled overlap evidence is grouped into incidents for replay. These intervals describe geometry, not fault, official penalties or damage. Browser geometry has complementary tests.

Entry points: pipeline/contact_coalescer.py. Phase: Ingestion. Status: Active. Test route: tests/unit/test_contact_coalescer.py.

[pipeline/contact_coalescer.py:L1-L1] [tests/unit/test_contact_coalescer.py:L1-L1]

## Pipeline orchestration and export

Orchestration orders identity, projection, reconstruction, analytics and exports. Replay column arrays, grouped manifests, historical detail and index support existing consumers. Sequence-aware courses preserve six-leg compatibility.

Entry points: pipeline/run_pipeline.py, pipeline/export_replay.py. Phase: Ingestion. Status: Active. Test route: tests/tier5_integrity.py.

[pipeline/run_pipeline.py:L1-L1] [pipeline/export_replay.py:L1-L1] [tests/tier5_integrity.py:L1-L1]

## Historical metric producer

Source-supported race windows, completed legs, timing records and selected events become canonical values with formula, unit, window, denominator, coverage and quality. Python alone decides availability. Analysis, Reports and Compare read the exports.

Entry points: pipeline/historical_analysis.py. Phase: Historical refresh. Status: Active scientific owner. Test route: tests/unit/test_historical_analysis.py.

[pipeline/historical_analysis.py:L1-L1] [tests/unit/test_historical_analysis.py:L1-L1]

## Peer performance and debrief

Completed same-leg values and supported events become leave-one-out peer ratios, equal-leg indexes and ranked observed deficits. Six dimensions do not imply full-course support. Replay links allow inspection of the underlying moment or leg interval.

Entry points: pipeline/historical_analysis.py. Phase: Analytics refresh. Status: Active optional extension. Test route: tests/unit/test_performance_analysis.py.

[pipeline/historical_analysis.py:L1-L1] [tests/unit/test_performance_analysis.py:L1-L1]

## Tactical insights

Recorded wind windows become trend snapshots with source provenance. Conditional projections require stricter gates; no current window passes them. Performance-only refresh uses existing exports without raw wind reads.

Entry points: pipeline/tactical_insights.py, scripts/refresh_team_analytics.py. Phase: Analytics refresh. Status: Active recorded trends; projections gated. Test route: tests/unit/test_tactical_insights.py.

[pipeline/tactical_insights.py:L1-L1] [scripts/refresh_team_analytics.py:L1-L1] [tests/unit/test_tactical_insights.py:L1-L1]

## Environment context

Historical model responses become hourly context for sea height and temperatures. Cached response hashes and availability remain inspectable. This is distinct from recorded local wind and causal forecasting weather. Acquisition may require network; cached display does not.

Entry points: pipeline/environment.py, src/engine/environment.ts. Phase: Acquisition and browser display. Status: Active contextual estimates. Test route: tests/unit/test_environment.py.

[pipeline/environment.py:L1-L1] [src/engine/environment.ts:L1-L1] [tests/unit/test_environment.py:L1-L1]

## Causal forecast dataset

Raw observations are sealed into a feature dataset with source fingerprints. Forecast state uses causal availability rather than retrospective replay events or historical summaries. Prepared caches are omitted from the pack.

Entry points: pipeline/prediction/source.py. Phase: Forecast preparation. Status: Active. Test route: tests/unit/test_prediction_pipeline.py.

[pipeline/prediction/source.py:L1-L1] [tests/unit/test_prediction_pipeline.py:L1-L1]

## Forecast weather support

Issued weather records are checked for publication availability and earlier independent competitive dates. Historical context is not silently substituted for causal issued weather. Support gates and zero-effect reference behavior are distinct.

Entry points: pipeline/prediction/weather.py. Phase: Forecast preparation and scenario support. Status: Active support gates; directional response unavailable. Test route: tests/unit/test_prediction_evaluation.py.

[pipeline/prediction/weather.py:L1-L1] [tests/unit/test_prediction_evaluation.py:L1-L1]

## Forecast state

Available positions, velocities, marks and timings become checkpoint state with gap uncertainty and gate ambiguity. Observation, issue and available-at clocks constrain usable evidence. State consumers are live models and simulations.

Entry points: pipeline/prediction/state.py. Phase: Forecast checkpoints. Status: Active. Test route: tests/unit/test_prediction_state.py.

[pipeline/prediction/state.py:L1-L1] [tests/unit/test_prediction_state.py:L1-L1]

## Completion labels and results

Complete scheduled rosters and source-reconstructed reviews supply targets, starters and nonfinish states. The evidence tier is weaker than independently audited official outcomes. Training cutoff and label availability prevent later results entering earlier fits.

Entry points: pipeline/prediction/labels.py. Phase: Forecast preparation and evaluation. Status: Active source-reconstructed evidence. Test route: tests/unit/test_prediction_pipeline.py.

[pipeline/prediction/labels.py:L1-L1] [tests/unit/test_prediction_pipeline.py:L1-L1]

## Strength and ranking models

Prior race evidence becomes relative strength and ranking parameters. Plackett-Luce is an active reference and exact-scenario path; ridge, pace, neural or boosted alternatives must be read with their model-card status. Mere implementation is not publication.

Entry points: pipeline/prediction/models.py. Phase: Forecast fitting. Status: Active reference plus experimental alternatives. Test route: tests/unit/test_prediction_models.py.

[pipeline/prediction/models.py:L1-L1] [tests/unit/test_prediction_models.py:L1-L1]

## Joint race simulation

Strength, current state and completion assumptions become joint ranks, win probabilities and scheduled-field expected scores. Shared uncertainty changes pairwise differences. Nonfinish scoring permits tied N values.

Entry points: pipeline/prediction/simulation.py. Phase: Forecast generation. Status: Provisional correlated candidate selected for baseline. Test route: tests/unit/test_prediction_models.py.

[pipeline/prediction/simulation.py:L1-L1] [tests/unit/test_prediction_models.py:L1-L1]

## Chronological evaluation

Frozen predictions and available outcome labels become proper scores averaged within race, then race/day summaries. Paired checkpoints and guardrails prevent convenient population changes. Small day counts limit empirical conclusions.

Entry points: pipeline/prediction/evaluation.py, pipeline/prediction/backtest.py. Phase: Research evaluation. Status: Active evaluation; calibration unestablished. Test route: tests/unit/test_prediction_evaluation.py.

[pipeline/prediction/evaluation.py:L1-L1] [pipeline/prediction/backtest.py:L1-L1] [tests/unit/test_prediction_evaluation.py:L1-L1]

## Cup tournament adaptation

Pinned rules, AC40 strength, transfer loadings and persistent latent uncertainty produce AC75 tournament scenarios. Unresolved paths retain coordinatewise bounds; outer envelopes combine assumptions. They are not probability vectors.

Entry points: pipeline/prediction/cup.py. Phase: Event forecast generation. Status: Active conditional scenarios. Test route: tests/unit/test_prediction_cup.py.

[pipeline/prediction/cup.py:L1-L1] [tests/unit/test_prediction_cup.py:L1-L1]

## Forecast contracts and publications

Candidate objects are validated and content addressed before an atomic active-index switch. Schema, roster, exact conditions, source/model references and canonical hashes are checked. Old objects remain accessible.

Entry points: pipeline/prediction/contracts.py, pipeline/prediction/build.py. Phase: Generation and verification. Status: Active. Test route: tests/unit/test_prediction_atomic.py.

[pipeline/prediction/contracts.py:L1-L1] [pipeline/prediction/build.py:L1-L1] [tests/unit/test_prediction_atomic.py:L1-L1]

## Shared browser context

Race, playhead, selected A, comparison B, visibility and interval state coordinate all five workspaces. The replay clock samples synchronized exports; it does not rerun ingestion. Async results must still match current identity.

Entry points: src/App.tsx, src/engine/ReplayEngine.ts. Phase: Browser interaction. Status: Active. Test route: src/engine/ReplayEngine.test.ts.

[src/App.tsx:L1-L1] [src/engine/ReplayEngine.ts:L1-L1] [src/engine/ReplayEngine.test.ts:L1-L1]

## Replay catalogs and interpolation

Grouped or retained flat catalogs select an export; binary search and scalar/angular interpolation sample frames. Current display leg rounding is not an independent checkpoint measurement.

Entry points: src/engine/catalog.ts, src/engine/interpolate.ts, src/engine/course.ts. Phase: Browser loading and playback. Status: Active plus legacy catalog compatibility. Test route: src/engine/interpolate.test.ts.

[src/engine/catalog.ts:L1-L1] [src/engine/interpolate.ts:L1-L1] [src/engine/course.ts:L1-L1] [src/engine/interpolate.test.ts:L1-L1]

## Analysis and prediction catalogs

Versioned detail/index objects become typed display evidence. Historical formulas remain producer-owned. Validators reject malformed or mismatched forecast scope and preserve unavailable states.

Entry points: src/engine/analysisCatalog.ts, src/engine/predictionCatalog.ts. Phase: Browser artifact loading. Status: Active. Test route: src/engine/predictionCatalog.test.ts.

[src/engine/analysisCatalog.ts:L1-L1] [src/engine/predictionCatalog.ts:L1-L1] [src/engine/predictionCatalog.test.ts:L1-L1]

## World to screen and course layers

Local metres become Grid pixels or inverse-projected Map coordinates. Camera continuity preserves scale/center across modes. Grid mounts no map tile surface; Map retains attribution.

Entry points: src/components/canvas/CourseCanvas.tsx, src/components/canvas/StaticCourseLayer.ts, src/components/canvas/ViewportMatrix.ts. Phase: Browser rendering. Status: Active. Test route: src/components/canvas/viewModeStress.test.ts.

[src/components/canvas/CourseCanvas.tsx:L1-L1] [src/components/canvas/StaticCourseLayer.ts:L1-L1] [src/components/canvas/ViewportMatrix.ts:L1-L1] [src/components/canvas/viewModeStress.test.ts:L1-L1]

## Vessels labels trails and physical geometry

Physical metre polygons remain separate from enhanced visible display size. Greedy label placement, leader lines and independent trail scopes preserve interpretability within finite screen space. Contact overlap is modeled geometry.

Entry points: src/components/canvas/DynamicVesselLayer.ts, src/components/canvas/boatPresentation.ts, src/engine/contactDetector.ts. Phase: Browser rendering and geometry. Status: Active. Test route: src/engine/contactDetectorStress.test.ts.

[src/components/canvas/DynamicVesselLayer.ts:L1-L1] [src/components/canvas/boatPresentation.ts:L1-L1] [src/engine/contactDetector.ts:L1-L1] [src/engine/contactDetectorStress.test.ts:L1-L1]

## Analysis evidence and radar

Selected boat and leg scope choose exported dimension/leg evidence, peer lists and coverage. The chart does not reimplement indexes. The selected detail can also be requested by App outside the Analysis panel.

Entry points: src/components/modals/AnalysisModal.tsx, src/components/dashboard/BoatPerformanceRadar.tsx. Phase: Browser interaction. Status: Active. Test route: src/components/dashboard/BoatPerformanceCard.test.ts.

[src/components/modals/AnalysisModal.tsx:L1-L1] [src/components/dashboard/BoatPerformanceRadar.tsx:L1-L1] [src/components/dashboard/BoatPerformanceCard.test.ts:L1-L1]

## Replay tactical and debrief navigation

Playhead selects a recent exported tactical snapshot; missing/stale windows display reasons. A debrief link opens a moment; performance-leg review can carry a selected boat and bounded interval.

Entry points: src/components/dashboard/TacticalInsightsPanel.tsx, src/components/dashboard/TeamDebrief.tsx. Phase: Browser interaction. Status: Active. Test route: src/components/dashboard/TeamAnalytics.test.ts.

[src/components/dashboard/TacticalInsightsPanel.tsx:L1-L1] [src/components/dashboard/TeamDebrief.tsx:L1-L1] [src/components/dashboard/TeamAnalytics.test.ts:L1-L1]

## Two boat comparison

Shared A/B selections and playhead drive metric and geometric comparisons. Visibility, highlighting and scheduled forecast field membership are separate concepts.

Entry points: src/components/panels/ComparisonPanel.tsx, src/components/dashboard/TacticalDashboard.tsx. Phase: Browser interaction. Status: Active. Test route: src/components/dashboard/TacticalMapOverlay.test.ts.

[src/components/panels/ComparisonPanel.tsx:L1-L1] [src/components/dashboard/TacticalDashboard.tsx:L1-L1] [src/components/dashboard/TacticalMapOverlay.test.ts:L1-L1]

## Reports inventory CSV and discovery

Historical canonical fields become CSVs retaining nulls and provenance. Inventory classifies current, supporting and retained objects, while Reports exposes useful race exports and a searchable technical archive.

Entry points: scripts/build_artifact_inventory.py, scripts/build_report_exports.py, src/components/dashboard/ReportsWorkspace.tsx. Phase: Export generation and browser downloads. Status: Active. Test route: tests/unit/test_report_exports.py.

[scripts/build_artifact_inventory.py:L1-L1] [scripts/build_report_exports.py:L1-L1] [src/components/dashboard/ReportsWorkspace.tsx:L1-L1] [tests/unit/test_report_exports.py:L1-L1]

## Forecast workspace and exact scenario service

Exact inputs become a validated local job, progress polling and immutable result. Workspace/child ownership locks protect publication. Static hosting displays existing objects; it cannot launch the prepared Python generator.

Entry points: src/components/dashboard/ForecastWorkspace.tsx, src/engine/forecastScenarios.ts, scripts/forecastScenarios.ts, scripts/forecastArtifacts.ts. Phase: Browser and local server. Status: Active local generation; static display supported. Test route: src/engine/forecastScenarioService.test.ts.

[src/components/dashboard/ForecastWorkspace.tsx:L1-L1] [src/engine/forecastScenarios.ts:L1-L1] [scripts/forecastScenarios.ts:L1-L1] [scripts/forecastArtifacts.ts:L1-L1] [src/engine/forecastScenarioService.test.ts:L1-L1]

## Race library presentation and design

Optional north-up previews support the library without loading every track. Missing previews retain text navigation. Self-hosted font notices, accessible control state and shared light surfaces belong to presentation, not scientific formulas.

Entry points: scripts/build_race_previews.py, src/components/modals/RacePickerModal.tsx, src/index.css. Phase: Presentation refresh and browser. Status: Active optional previews. Test route: tests/unit/test_race_previews.py.

[scripts/build_race_previews.py:L1-L1] [src/components/modals/RacePickerModal.tsx:L1-L1] [src/index.css:L1-L1] [tests/unit/test_race_previews.py:L1-L1]

## Verification and operating scripts

Focused tests precede the full deterministic gate, build, integrity checks and separate browser suites. Fresh results live in verification; dated documentation is historical. Synthetic fixtures and real-export consistency checks support different claims.

Entry points: run.ps1, tests/e2e/test_runner.py, tests/browser/dashboard.mjs, tests/browser/forecast.mjs. Phase: Local verification and operation. Status: Active. Test route: tests/tier5_integrity.py.

[run.ps1:L1-L1] [tests/e2e/test_runner.py:L1-L1] [tests/browser/dashboard.mjs:L1-L1] [tests/browser/forecast.mjs:L1-L1] [tests/tier5_integrity.py:L1-L1]

## Cross domain glossary

| Term or field | Meaning and caution |

| --- | --- |

| Session | One source race/session export; a filename is not a guaranteed date. |

| Boat-race | One boat observed in one race; the historical unit is not a frame. |

| Scheduled entry | A member of the scheduled forecast field, even without replay telemetry. |

| Frame | A regular100 ms replay state, often interpolated. |

| Gate | A directed line between identified marks in an ordered course sequence. |

| Leg | A course segment bounded by start/checkpoint timing. |

| Tack | Upwind change of wind side, subject to detector context and coverage. |

| Gybe | Downwind change of wind side. |

| Heading | Hull orientation bearing clockwise from north. |

| COG | Course over ground, the direction of motion. |

| SOG / sog_mean_kt | Speed over ground; its canonical mean needs an eligible source-supported window. |

| TWD | True wind direction from which wind comes. |

| TWS | True wind speed, with source and units retained. |

| TWA | Derived wind angle relative to heading; not interchangeable with velocity angle. |

| Course-axis VMG | Velocity projected onto the course axis; raw sign can differ by leg direction. |

| Wind-relative VMG | Velocity projection relative to wind, with its own sign convention. |

| x,y | Local east,north metres with exported origin and coefficients. |

| timestamp_ms | Integer milliseconds; distinguish seconds in durations. |

| Checkpoint gap | Difference in passage times at a shared checkpoint. |

| Continuous gap | A moving geometry/speed estimate, not a checkpoint observation. |

| OCS | Start-side/source-state concept; a visual early intersection alone is insufficient. |

| DNS | Did not start; preserve field membership and missing telemetry separately. |

| RET / DNF | Retired/nonfinish labels with source and evidence limits. |

| Calculated result | Reconstructed classification, not independently verified official results. |

| quality | Provenance/availability category such as derived, reconstructed, partial or unavailable. |

| coverage_s | Supported seconds under the owning metric definition. |

| sample_count | Event/leg or other defined sample count; not necessarily telemetry frames. |

| matched_legs | Eligible same-leg comparisons admitted into an index. |

| peer_mean | Equal-boat other-boat baseline within eligible scope. |

| peer_ids | Named contributing boats; selected boat excluded. |

| index | 100 times selected/peer ratio, averaged equally over eligible legs. |

| overall_index | Aggregate defined only under required dimension availability; not ability. |

| retention | Minimum versus entry-speed ratio over selected eligible detected events. |

| debrief | Ranked observed review items with replay links, not causal advice. |

| tactical_insights | Exported recorded trend snapshots; projections remain gated. |

| schema_version | Structural contract version, distinct from formula/method version. |

| method_version | Version of scientific calculation or export method. |

| Historical View | Index/cohort view over boat-races, not frames. |

| A / B | Primary selection and explicit comparison selection; not forecast team rankings. |

| Grid / Map | Direct metre canvas versus geographic base; Grid avoids tile requests. |

| Enhanced | Readable display scaling, separate from physical contact calculation. |

| Keep Clear | Modeled safety envelope; overlap is not an official ruling. |

| training_cutoff | Only prior available evidence may fit the model. |

| available_at | Information publication/availability time, distinct from observation time. |

| Plackett-Luce | Sequential positive-weight ranking reference. |

| correlated_mc | Joint Monte Carlo candidate with shared uncertainty, currently provisional. |

| N | Complete scheduled field size; nonfinish score convention uses N. |

| expected_position | Unconditional expected scheduled-field score including nonfinish. |

| Brier | Summed multiclass squared probability error under this evaluator. |

| Log loss | Negative logarithm of probability assigned to the observed winner. |

| RPS | Ranked probability score for an ordered distribution, normalized by contract. |

| Calibration | Empirical frequency agreement requiring independent outcomes. |

| Pseudoreplication | Treating dependent repeated measurements as independent evidence. |

| Monte Carlo error | Numerical finite-trial sampling uncertainty conditional on a model. |

| Transfer loading | Assumed AC40-to-AC75 strength relationship, not measured correlation. |

| Rule bound | Conservative allocation of unresolved tournament mass. |

| Scenario envelope | Coordinatewise extremes across assumptions; endpoints can differ in origin. |

| model_ref | Canonical model-card content hash. |

| source_manifest_hash | Canonical manifest identity; does not imply all raw bytes rehashed today. |

| scenario_hash | Declared scenario input identity, distinct from byte SHA of a file. |

| Immutable object | Content-addressed publication retained after active index changes. |

| Atomic index | Validated pointer switch using replacement, with prior publication surviving failures. |

| Publication lock | Shared local job ownership guard including publisher child process. |

| Static hosting | Can display saved objects; new generation needs the prepared local service. |

## Evidence routes and preservation

Start with [frozen source navigation](source/_SOURCE_INDEX.html), [the snapshot manifest](evidence/snapshot.json), [bounded actual case evidence](evidence/data_metrics_review.json), [current model/evaluation findings](evidence/forecast_review.json), [UI findings](evidence/interface_review.json), and [fresh verification](VERIFICATION.html). Source citations above point to entry points; detailed line ranges in the textbook point to producing functions. Existing notices are preserved. No top-level repository license or independent official-result verification is invented.
