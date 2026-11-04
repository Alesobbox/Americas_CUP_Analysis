# Field guide to the regatta repository

## The entire system on one page

The useful output is an inspectable chain from recorded telemetry to replay, descriptive comparison and conditional forecasts. It serves three different tasks: review what occurred, compare supported past performance and explore future outcomes under declared assumptions.

Source sessions branch into two paths. Replay path: identity and local projection → regular replay and reconstructed events → historical metrics and indexes. Forecast path: causal raw-data features → state, models and simulation → immutable forecast publications. Both paths feed browser workspaces and downloads.

Python owns historical formulas, source coverage and forecast calculations. The browser owns playback, instantaneous interpolation/geometry, selection and rendering. The browser consumes historical exports instead of reimplementing their definitions.

Current review: 4 November 2026. Twenty-eight sessions,224 replayed boat-races,227 scheduled entries; AC40 only. Nine Cagliari sessions and 19 Naples sessions. Commit f956f8a is the base; the actual reviewed checkout has uncommitted changes, identified by the source snapshot manifest.

Five views: Replay follows a shared playhead; Analysis explains historical metrics and debriefs; Compare contrasts boats; Reports exposes canonical exports and provenance; Forecast separates three prediction targets.

The central discipline: always state the evidence tier, window, denominator, unit, cutoff and limitation. A smooth picture is not proof of continuous observation. An index is not ability. A probability is not automatically calibrated. A virtual contact is not an official ruling.

## Data flow and component responsibilities

Ingestion streams raw JSONL and resolves assets within each session. Projection converts latitude/longitude to local east/north metres. Resampling synchronizes a 100 ms replay grid. Reconstruction assigns gates, starts, legs, progress and classifications under documented approximations. Export writes replay-compatible column arrays and compact catalogs.

Historical analysis uses source timestamp coverage to decide eligible windows. It publishes values with formula, unit, source, quality, coverage and denominator. Team analytics attaches optional tactical, performance and debrief evidence. Forecasting uses causal raw-data features, scheduled-field labels, training cutoffs and content-addressed output objects.

App owns selected race, playhead, primary boat, comparison and visibility state. Engine catalogs fetch versioned artifacts; canvases transform world metres into pixels. Changing a selected boat can change the performance baseline because the selected boat is excluded from peers. Hiding boats does not shrink the scheduled forecast denominator.

Reports is the route from a visible value to its download. The source companion is the route from an explanation to frozen code. Read the atlas to distinguish active paths, experimental models and legacy fallbacks. Do not infer current use simply because a file exists.

Order to read: schemas → one case → identity/projection → reconstruction → coverage/metrics → forecast targets/evaluation → interface/loading → publication and tests.

## Quantities units and sign conventions

x is east and y is north in metres. Bearings are degrees clockwise from north; wrap angles before averaging. One knot is 1852/3600 m/s. A speed in knots multiplied by seconds needs conversion before becoming metres. Time fields ending_ms are milliseconds, not seconds.

Course-axis VMG is a velocity projection along the course unit vector. It can be signed in the replay; a downwind boat can have negative raw course-axis VMG while making correct leg progress. Historical leg-oriented definitions must be read with their sign transformation.

Wind-relative VMG projects speed along a wind-relative direction and differs from course-axis VMG when wind and course axes differ. Replay TWA uses heading and local TWD; wind-relative velocity uses course over ground, so the two angles need not match.

Checkpoint timing gap is a difference between observed/reconstructed passage times at the same checkpoint. Continuous gap is an estimate using current geometry/progress and speed assumptions. Do not call either the other.

Start delay is relative to the scheduled gun under the field's convention. Negative time relative to gun means before the start; an apparent early crossing still requires the proper source state and geometry checks. Null means unavailable under a definition;0 is a valid numerical value when supported.

Whole-race means, valid seconds, event counts, completed legs and boat-races have different denominators. Write the denominator next to the number when rehearsing.

## The peer performance calculation

On an eligible leg l, x_l is the selected boat's supported value and m_l is the equal-boat mean of other eligible boats on that same leg. Leg index I_l=100 x_l/m_l. Dimension index I=(Σ I_l)/L over L matched legs, with equal leg weighting.

Synthetic example: selected 20,30 kt; peers 10,30 kt. Leg indexes 200 and 100; aggregate 150. Raw aggregate ratio 100×25/20=125 answers a different question. A browser must not recalculate 150 from those aggregate labels.

Peer eligibility includes completed matching legs, source-supported windows and exclusions for conflicts/nonstarting states. Per-leg source coverage at least 95% is a consequential gate. Different legs and selected boats can have different eligible peers. Missing peer support can remove a comparison.

Retention uses eligible detected events with supported whole search windows. Compute each peer boat's mean before giving boats equal votes. A peer with many detected events should not dominate simply because of event count. Retention describes selected detected events; it is not all maneuvers that occurred on water.

Index 110 supports a 10% mean relative advantage under the defined ratio weighting and scope. It does not establish causal tactics, intrinsic skill, a full-course advantage or a 10% greater win chance. A six-axis profile can cover only four of six legs; inspect exclusions and covered seconds.

## Three forecasts and three different targets

Live on-water win probability is conditional on causally available race state at the checkpoint, including completion assumptions and uncertain gaps. Its field can include scheduled boats absent from replay telemetry. Estimated means model-produced, not calibrated.

Pre-race expected finishing position uses the scheduled field N and the nonfinish convention. A nonfinisher is scored N; multiple nonfinishers can tie there. E[position]=Σ k P(finish at k)+N P(nonfinish). A conditional-on-finishing expectation is a different quantity.

Event/Cup outcomes combine stages, classes, rules, strength uncertainty and series dependence. Current Cup publication provides scenario-conditioned rule bounds and an outer envelope. Unconditional point probabilities remain null while tournament paths are unresolved.

Current baseline publications select a correlated Monte Carlo candidate provisionally; custom exact wind scenarios use the declared reference path. Implemented alternatives and benchmarks are not automatically active. Inspect the model card.

Weather support is not a learned effect. Supported speeds can yield equal expectations under the current zero-effect wind reference. Direction offsets without a validated response remain unavailable. Never silently replace 17° with 0°.

A probability can pass numeric/schema validation and still be uncalibrated. A tested publication workflow establishes that the requested conditions reach an artifact, not that its expectation predicts well.

## Uncertainty and the current evidence ceiling

Monte Carlo uncertainty is sampling noise from a finite number of simulated paths. At 5,000 independent trials the approximate worst-case 95% half-width is 1.96√(.25/5000)=1.386 percentage points. It is conditional on the specified model.

Model uncertainty concerns strength, completion, residuals and transfer assumptions. Structural uncertainty concerns unknown rules or unresolved paths. More trials do not fix a missing rule or identify cross-class transfer.

Actual Cup baseline:3,277 resolved and 1,723 unresolved paths out of 5,000; unresolved fraction 34.46%. If a team wins w resolved trials, its conservative interval is[w/5000,(w+1723)/5000]. These coordinatewise upper limits allocate unresolved mass differently and cannot form one probability vector.

Envelope endpoints may originate from different scenarios. Preserve endpoint attribution. Transfer loading is a sensitivity assumption, not measured AC40/AC75 correlation.

The live descriptive audit covers seven races over two days; the development set and repeated checkpoints are not independent external validation. Pre-race errors do not uniformly beat the reference. Current completion evidence is source reconstructed. Software tests do not change those empirical limitations.

Best next information: independently verified scheduled results and additional race-days; AC75 evidence for transfer; authoritative rule completion for unresolved tournament ties.

## Common interpretation mistakes

Do not count frames as independent races. Do not replace missing values with zero. Do not parse the source ID as a guaranteed date: one race_3 ID contains 25 September while its exported date is 26 September.

Do not equate smooth replay motion with source coverage. Regularized numeric streams can bridge long gaps. Historical support rules intentionally reject windows that the animation can still draw.

Do not infer full-course support from six available radar axes. Do not pool all peer events if the definition gives each boat one vote. Do not turn a ratio of aggregate means into the mean of same-leg ratios.

Do not call reconstructed classifications independently verified official results. Current visible wording says Calculated or Calculated from telemetry while source codes preserve quality. Do not call a geometric contact a racing penalty.

Do not normalize unresolved bounds. Do not call an assumption envelope a calibrated confidence interval. Do not assume an implemented model is used in the current publication.

Do not call identical supported-wind outputs a cache failure without checking exact conditions and the zero-effect model. Do not call a successful synthetic generation fixture a real Python model run.

Before repeating a claim: target, evidence, time cutoff, denominator, window, unit, producer, limitation. If one is absent, trace it before defending it.

## Startup and offline use

The study pack requires no installation. Extract the ZIP; open START_HERE.html or a PDF. All essential prose, diagrams, images and navigation are local. HTML search filters sections without contacting a service. Source pages have stable relative line links. The saved lab output remains readable without Python.

For scripts, a standard Python 3 runtime runs tools/concept_lab.py. It uses only the standard library and synthetic values. Its output is not a forecast artifact. Authoring tools are optional and need reportlab, pypdf and a PDF renderer; reading does not.

For the separate existing dashboard, open a terminal in C:\Workspace\Americas CupD_regatta_replay and use npm.cmd run dev after dependencies have been installed. On this repository run.ps 1 dev also starts it. The usual address is localhost:5173; read the displayed address if that port is occupied.

Grid makes no map-tile requests. Serving already built application files locally still needs an HTTP server; opening dist/index.html directly is not the supported workflow. Forecast generation additionally needs the prepared dataset, Python environment and Vite's local generation service. Static hosting displays published scenarios only.

Before travel, test the exact device with Wi-Fi off, copy the extracted pack plus ZIP, open the main PDF and answer key, and verify any optional dashboard/backend separately. The core study materials do not depend on that preparation.

## Troubleshooting decision tree

START: Can you open START_HERE.html? If no, extract the ZIP completely and open the extracted file in a browser. Do not browse inside a ZIP preview. If PDFs open but HTML is restricted by a mobile file provider, use the PDFs or choose Open in browser.

Missing image or source link? Confirm the directory tree was copied intact. Open the self-contained textbook HTML to read the main material without companion image paths. The manifest verifier can identify missing/changed files if Python is available.

Search finds nothing? Clear the query; use a shorter term or PDF text search. Source pages have line numbers; search a symbol such as attach_performance_analysis instead of a prose label.

Concept lab fails? Confirm Python 3 is installed and run the script from a terminal. Otherwise open evidence/concept_lab_output.json; no exercise requires executing it.

Dashboard blank? Check that a local HTTP server is running and its URL is correct. No map surface? Select Grid; map tiles need separate availability. Published forecast unavailable? Read its reason and model references; an honest unavailable state can be expected.

New generation unavailable? Check backend, prepared data, Python and exact supported conditions. Do not replace unsupported direction silently. Stuck job? Read service status/ownership; do not delete an active shared publication lock. Returning to the study pack never requires fixing the dashboard.

## Five minute oral recall checklist

Tell the story in this order. One: the archive records sessions, boats and course assets with irregular source timing. Two: Python converts local geometry, regularizes replay and reconstructs events, while retaining provenance. Three: historical metrics admit only defined source-supported windows and explicitly preserve missingness. Four: peer performance compares matching completed legs, excludes self and averages leg ratios. Five: the browser shares race/playhead/selection across five views without owning historical formulas.

Six: live win, pre-race expectation and Cup outcomes have different targets and denominators. Seven: correlated simulation represents dependencies, while completion and nonfinish conventions change ranking targets. Eight: current weather and cross-class evidence limits prevent stronger interpretations. Nine: unresolved tournament paths create bounds, and outer envelopes combine assumption scenarios. Ten: tests establish software contracts and reproducibility; predictive quality needs independent outcomes and held-out race-days.

Actual evidence anchors: PR1 is a rich nine-boat fleet; the Naples match final exposes four-of-six ITA B comparison support; the unfinished September 23 practice illustrates missing completed windows. These cases should be explained with bounded observations, not telemetry dumps.

Ask yourself: What would change if a source crossing were wrong? If a peer were excluded? If the nonfinish probability doubled? If the transfer loading were zero? If all tie rules became known? A good explanation predicts the direction and scope of the change without pretending all other uncertainties disappear.
