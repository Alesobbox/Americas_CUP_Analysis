# AC37 AC75 learned simulator: implementation specification

Version: 1.0  
Prepared: 2026-11-09  
Status: implementation plan only; no training or application behavior changes are authorized by the existence of this file.

## Read this first

Implement a learned model of the observed behavior of the 2024 AC75 boats using the AC37 archive. Training and evaluating a small neural network is mandatory. Making it the default model depends on evidence. Deliver a reproducible, reviewable experimental simulator even if the neural network loses to a simpler learned model.

Quality has priority over token savings. Reduce repeated context, raw-data dumps, unnecessary retries, and repeated processing. Do not reduce source coverage, remove validation, fabricate labels, or claim accuracy to save tokens.

Repository root: C:/Workspace/Americas Cup/2D_regatta_replay.

Companion files:

- docs/ac75_learning_executor_prompt.md: small-model starting instructions.
- docs/ac75_learning_task_index.json: task order, dependencies, and section identifiers.
- This file: contracts, design decisions, individual work packets, and acceptance criteria.

The implementing agent must read AGENTS.md, PROJECT.md, the executor prompt, and only the relevant global sections and task packet. Reading this entire specification on every turn defeats its purpose.

## G0. Scope and verified starting point

### G0.1 Available data

The separately audited AC37 archive is not the 28-session AC40 replay archive.

| AC37 section | Class | Raw files | Format |
|---|---|---:|---|
| Official practice | AC75 | 41 | JSONL |
| Barcelona preliminary | AC75 | 16 | JSONL |
| Louis Vuitton round robins | AC75 | 31 | JSONL |
| Louis Vuitton semifinals | AC75 | 15 | .ac37 binary |
| Louis Vuitton finals | AC75 | 12 | JSONL |
| 2023 preliminary regattas | AC40 | 17 | JSONL |

The inventory checked on 2026-11-09 contains 132 files and 22,966,771,945 bytes: approximately 22.97 decimal GB or 21.39 GiB. Of these, 115 source files are AC75. File counts are not counts of independent completed races. AC75 filenames span August 2 through October 4, 2024; derive authoritative dates and attempts from session evidence, not filenames alone.

The source audit describes high-rate position/heading, lower-rate SOG/COG, and wind. Measure actual per-file cadence, gaps, fields, and units during ingestion; the prose cadence statement is not a substitute for measured coverage.

The current audit does not establish telemetry for the October America's Cup Match. The 81 rows in docs/ac37_results.json include Match outcomes; outcome rows do not establish corresponding physical telemetry.

### G0.2 Starting defects to remove from the learned path

1. scripts/extract_ac75_primitives.py selects the first 12 sorted round-robin/final files and caps reading at 100,001 lines per file.
2. Its maneuver distributions, race-duration summaries, and nonfinish rate include literal constants.
3. pipeline/kinematic_ml/export.py loads primitives but does not pass them into simulation; course/rules metadata can be assigned after the calculation.
4. Interactive simulation does not receive the same fitted team information as saved scenarios.
5. GB1/INEOS and other historical/current labels do not resolve consistently.
6. features.py mixes wind sources, can use future wind, invents missing speeds, and applies unsuitable shared boundary-support rules.
7. evaluate.py's feature selection does not establish the claimed chronological isolation. Existing evaluation status is not transferable to the new model.
8. The current service uses synchronous child execution, incomplete cache matching, and unbounded request bodies.
9. The UI can attach changed controls to an older result; its interval and attribution labels are misleading.
10. Existing result-construction code contains manually specified tuples and generic source URLs. Series-score agreement does not authenticate every winner, margin, date, and wind field.

Preserve existing user changes. At planning time the checkout already contains many modified and untracked files. Do not reset, clean, stash, format, or regenerate unrelated files.

### G0.3 Required and excluded deliverables

Required:

- Full accounting of the supplied AC37 sources, exhaustive eligible AC75 extraction, and explicit exclusions.
- Supported binary decoding, or an accurately recorded external schema dependency while JSONL work continues.
- A learned empirical ground-relative performance model, learned maneuver/event timing, an observed-behavior routing policy, and uncertainty.
- A real trained small neural network and fair simpler learned baselines.
- Causal chronological evaluation, an immutable evidence report, and an honest selected experimental candidate.
- One inference path for saved and interactive scenarios; compatible UI, contracts, and regression tests.
- Compact resumable execution records and content-addressed data/model artifacts.

Excluded from version 1:

- Identifying unmeasured foil geometry, hydraulic settings, through-water polars, or full fluid dynamics.
- Claiming an optimal tactical policy from observational telemetry.
- Automatically forecasting AC38 boats or new entrants by relabeling AC37 identities.
- Training on simulator-generated winners as evidence of real-world predictive skill.
- Replacing the separate Replay, Analysis, Forecast, or Cup pipelines.
- Public promotion, deployment, or mutation of historical public datasets merely to complete this plan.

A separate explicit request can authorize promotion after the candidate and evidence are concrete.

## G1. Optimization objective and operating rules

Use a lexicographic objective, not a weighted score that trades away correctness:

1. Satisfy data integrity, information-time, numerical, and compatibility constraints.
2. Maximize defensible predictive quality and coverage, measured on the registered population.
3. Minimize total LLM input/output and repeated-work tokens among implementations meeting 1 and 2.
4. Minimize unnecessary training and I/O without weakening the registered experiment.

Token targets are guidance, not permission to stop required work:

- Initial execution context: executor prompt, task index entry, G2/G3 as needed, one task packet, and relevant function excerpts.
- Typical packet context: about 4,000-8,000 tokens. Add necessary evidence rather than obeying an artificial cap.
- Read functions or 80-200-line ranges; do not repeatedly print entire modules.
- Human-facing progress: learned fact, remaining issue, next gate; no full logs.
- End-of-packet handoff: at most approximately 250 words plus machine-readable artifact/test references.
- Full diagnostics live under .forecast/ac75_learning/logs/. Terminal summaries show counts, ranges, hashes, exclusions, and at most three examples.
- Never send telemetry arrays, model tensors, Parquet tables, or the 23 GB archive into model context.
- Use deterministic programs for computation. The LLM designs, edits, and examines bounded evidence.
- Cache by content/configuration hashes. Resume completed stages; never retrain to recover a lost conversation.
- Two unchanged attempts at the same engineering failure trigger root-cause inspection and a precise blocker record. This is not a permanent stop: continue independent packets and resume when resolved.
- A model losing the comparison is a completed experiment, not an engineering failure to hide.

Use subagents for disjoint packets or independent review. Do not have agents edit the same file concurrently. A reviewer needs the contract, diff, and evidence summary, not the entire archive or conversation.

## G2. Frozen scientific and engineering contracts

### G2.1 Targets and information sets

Keep these targets separate:

| Target | Inputs | Label |
|---|---|---|
| Empirical speed response | Supported contemporaneous wind, heading/COG geometry, leg type, historical identity | Duration-weighted SOG and COG-based progress in a steady interval |
| Maneuver/event timing | Selected route-event geometry, issued conditions, supported identity, predicted entry state | Event-plus-recovery duration, including censoring |
| Historical pre-race scenario | Training-only model/policy, declared course, wind scenario available at issuance | Race time, margin, on-water outcome |
| Historical live forecast | Pre-race inputs plus observations available by the issue time | Remaining time, margin, on-water outcome |

Do not call an instantaneous conditional speed surface a future-speed forecast without specifying its input/target timing. Version 1 fits steady five-second intervals and explicitly assumes the selected heading and wind scenario apply over that interval. A genuinely future-target live model is a separate task.

Pre-race evaluation must not read held-out future headings, maneuver counts, trajectories, actual later weather, finish order, or post-race team ratings. A diagnostic conditioned on observed later weather/route is permissible only if labeled hindsight reconstruction and excluded from forecast-selection scores.

Existing archive receipt times are not established. Use the repository's modeled six-second latency assumption for causal historical reconstruction, record it as assumed, and perform 0/6/12-second development sensitivity. Do not claim actual production latency.

### G2.2 Identities

Historical canonical IDs:

- ac37:ETNZ
- ac37:INEOS
- ac37:LUNA_ROSSA
- ac37:AMERICAN_MAGIC
- ac37:ALINGHI
- ac37:ORIENT_EXPRESS

The registry records competition, effective dates, class, session asset IDs, aliases, evidence, and registry version. Display alias GB1 may resolve to ac37:INEOS only inside an explicitly historical AC37 request. AC38 GB1, ARC_USA, LA_ROCHE_POSAY, and AUSTRALIA are not automatically observed AC37 identities.

Unknown identity returns unsupported or an explicitly requested pooled experiment. A missing identity must never silently become an observed zero effect. An existing team with sparse evidence may use a documented pooled component, with the support level and uncertainty visible.

### G2.3 Units and formulas

Native normalization uses SI: metres, metres per second, degrees, Unix milliseconds. Display conversions are explicit. Preserve float64 values and int64 timestamps; round only presentation output.

- Course progress = SOG times cosine of COG minus the directed leg bearing.
- Wind VMG uses COG relative to true wind-from bearing, reversing sign downwind.
- Signed TWA uses heading relative to the selected wind source.
- Heading does not replace COG in ground-relative VMG.
- Ground-relative performance does not establish through-water performance or identify current.
- Race time starts at the gun and ends at the supported finish event.
- Do not add the old 120-second countdown or synthetic 30-second finish component.

Reuse the formula owners in pipeline/historical_analysis.py: leg_course_vmg_kt and wind_relative_vmg_kt. Add named SI adapters: convert input m/s to knots, call the existing owner, convert its output back to m/s. Test the conversion round trip. Do not recalculate historical metrics in TypeScript or change their existing definitions. Barcelona geometry requires a recorded per-attempt WGS84/local metric projection derived from supported coordinates; the existing non-Cagliari-to-Naples projection fallback and hard-coded AC40 metadata must not be used unchanged.

### G2.4 Proposed record schemas

Implement dataclasses/typed records plus boundary validators and explicit Arrow schemas. Do not introduce a general schema framework or permissive dictionaries.

| Record/table | Required content |
|---|---|
| source_manifest, ac75-source-1 | Relative path, bytes, SHA-256, format, schema/decoder hashes, class evidence, session/time ranges, counts, status, reasons |
| race_attempts, ac75-attempts-1 | Family/attempt/session IDs, stage/date, practice flag, class, scheduled entries, gun revisions, stop/resail links, geometry evidence |
| native, ac75-native-1 | Source ID, packet ordinal/offset, sequence/correlation IDs where supplied, asset, channel, event/availability times, typed scalar or position values, unit/source/quality |
| events, ac75-events-1 | Session/competitor/mark/rule events, revisions, effective and available times, evidence |
| steady_windows, ac75-features-1 | Attempt/team/day, interval, feature-available and target-available times, physical summaries, feature/target split, coverage, reasons, source ranges |
| maneuvers, ac75-maneuvers-1 | Candidate/version, turn type, supported timing/path, entry/exit state, duration/recovery/censoring, optional local deficit proxy, review status |
| legs/routes, ac75-routes-1 | Attempt/team/leg, course frame, geometry, partitioned route segments, conditions, support and train-only references |
| outcomes/completion, ac75-outcomes-1 | Official versus on-water target, timed finish, scheduled denominator, cause/censoring, per-field evidence and availability |
| splits, ac75-splits-1 | Source/dataset hashes, family/day assignments, cutoffs, exposure/consumption ledger, exact fold IDs |
| model_bundle, ac75-model-1 | Fitted model and preprocessing, support, routes, uncertainty, completion scope, training/cutoff/fold/config/code/environment hashes |
| scenario, kinematic-race-sim-2 | Pinned model/configuration, actual applied inputs, availability, probability scope, outputs, uncertainty, accounting and evidence |
| evaluation, ac75-evaluation-1 | Exact model and split IDs, population/target, unrounded predictions, grouped scores, support, exposure, selection decision |

For every learned quantity retain formula/target, unit, window, denominator, source, coverage, quality, and availability. Null, zero, unsupported, unresolved, and censored have distinct meanings.

### G2.5 Concrete module ownership

Prefer these boundaries; split further only to satisfy repository limits or clear ownership:

| Module | Responsibility |
|---|---|
| contracts.py, config.py | Typed contracts, validation, versioned configuration |
| inventory.py | Source discovery, hashes, compact source/coverage summaries |
| source.py, ac37_wire.py | Streaming normalization and verified wire adapters |
| dataset.py | Bounded sorting, partitioned Parquet, sealing/loaders |
| features.py | Causal joins, steady intervals, candidate turn detection |
| labels.py | Reviewed/derived labels, censoring and evidence reconciliation |
| routes.py | Training-only route policy, supported geometry, path partition |
| splits.py | Immutable folds, feature allowlists and exposure controls |
| baselines.py | Empirical and regularized spline models |
| neural.py, training.py | Small neural model, deterministic fitting and exports |
| uncertainty.py, completion.py | Joint residual sampler, uncertainty ledger, reviewed completion |
| inference.py, simulator.py | Single scenario entry point and physical rollout |
| artifacts.py, export.py | Content identity, exact scenario cache and staged export |
| evaluate.py | New honest evaluator; legacy evaluation remains labeled legacy |
| __main__.py | Small CLI dispatch; no mathematics in argument parsing |

All are under pipeline/kinematic_ml/. Existing modules may be refactored into these owners; do not maintain two learned pipelines. Retain the old fixed model only as an explicitly named legacy benchmark/compatibility path with tests and a sunset note.

Proposed configuration: pipeline/kinematic_ml/configs/ac75_2024_v1.json.

### G2.6 Defaults to implement and preregister

These are engineering/experiment settings, not established physical laws or accuracy claims:

- Primary class/cycle: AC75 / AC37.
- Native data retained; retrospective label integration grid: 100 ms.
- Steady windows: nonoverlapping five seconds.
- Required supported duration: at least 95%.
- Initial maximum internal gap: 1,200 ms for position/heading/SOG/COG; 2,500 ms for wind.
- Causal maximum age must be separately specified per stream after measured cadence review; start with the same limits and report the realized age distribution.
- No speed-based eligibility cutoff such as SOG > 12 knots.
- Turn candidate seed settings: 65-degree rotation within 18 seconds; 1.5-second reversal tolerance. These require AC75-specific validation.
- Ordinary same-leg tack/gybe recovery: reference is duration-weighted median SOG over [turn_start - 7 s, turn_start - 2 s]; recovery search starts at angular turn end and requires two continuous supported seconds at or above 95%. Endpoint is the end of that hold. Censor at turn_end + 30 s or earlier coverage loss, next event, terminal state, gate ambiguity, or incompatible regime change. A missing/nonpositive reference makes recovery unavailable. Leg-changing roundings use the separate transition contract in G8.
- Straight-motion exclusion: candidate turn/event interval plus five seconds on each side; exclude the entire measured recovery interval.
- Residual blocks: 30 seconds; development sensitivities at 15 and 60 seconds.
- Neural model: 2 hidden layers of 32 SiLU units; distributional outputs; three final seeds 2027, 2028, 2029.
- Initial CPU fitting, at most four threads, 512-row minibatches, maximum 150 epochs, early-stopping patience 15.
- Search: learning rate 0.001/0.0003, weight decay 0.0001/0.001, dropout 0/0.1; eight configurations. Screen with seed 2027.
- Empirical/spline regularization grid: 0.1, 1, 10, 100.
- Scenario purposes: preview 2,000 trials; standard 10,000; evaluation 20,000. Purpose, seed, and count are part of the exact key. Saved/on-demand parity compares identical purposes.
- Memory: bounded batches; begin with 50,000 normalized rows and at most 512 simulated trials per batch. Measure peak memory rather than claiming a fixed full-archive footprint.
- Default seed: 2027. Per-purpose child random streams are deterministic and named.

Changing a data-eligibility rule, feature, split, target, or model search after scoring creates a new experiment version. Do not overwrite the old evidence.

## G3. Statistical design decisions

### G3.1 Mandatory neural model

Implement a small distributional MLP. Predict log SOG in m/s from TWS, sine/cosine of TWA, leg type, tack side, supported heading-to-COG offset, course-relative wind direction, and historical team identity. Include an explicit practice-domain indicator if practice rows are used.

Team identity enters as a penalized linear deviation on top of the pooled nonlinear function. Do not infer physical boat/hardware changes from a team label. No inferred foil/cyclor/crew covariate without actual evidence.

Use Gaussian likelihood on log speed, producing mu and positive sigma = softplus(raw_scale) + a small documented numerical epsilon. Gaussian log-speed implies a lognormal positive-speed model. Do NOT exponentiate an unbounded Student-t variable: its resulting speed/time moments need not exist. Student-t residuals in the old simulator are not a requirement for the learned model.

Treat measured speeds at/below the confirmed measurement floor as left-censored observations. Use the normal log-CDF likelihood at that floor; do not drop slow states or insert a fictional speed. Confirm the floor from the source precision; 0.05 m/s is a provisional numerical value to review before fitting. Partition rows into mutually exclusive straight, start, maneuver/recovery, rounding-transition, and explicit dwell domains. Explicit dwell/start/event rows train their duration models, not the straight-speed model; remaining slow straight-motion rows remain included. Stationary route intervals retain dwell duration exactly once.

Fit transformations and encodings on training rows only. The primary speed target is duration-weighted observed SOG; COG-derived VMG/progress is a separate physical and evaluation target. Reject train batches containing target columns in the feature allowlist.

Train the pooled empirical baseline and regularized spline on the same rows/weights/folds. Use race-equal weights, then equal boat weights within a race, then duration within a boat. Duplicate recordings or denser sensor cadence must not increase a race's influence. Practice is a declared domain; compare inclusion versus competitive-only in development, applying the same selected row policy to the compared candidates.

Export tensor weights and preprocessing to validated JSON plus numeric NPZ with allow_pickle=False; NumPy/SciPy can perform this small network's inference. A PyTorch-to-NumPy parity test must pass. Do not require PyTorch in a browser request or silently initialize random weights when artifacts are absent.

A three-seed spread is sensitivity to fitting, not a calibrated Bayesian posterior. Do not label it as complete parameter uncertainty.

### G3.2 Observed-behavior route policy

Version 1 samples training-only normalized leg-route templates. It does not select the highest predicted VMG angle or claim optimal tactics.

A template records normalized course coordinates, selected heading/COG relation, straight segments, maneuver/recovery segments, dwell/start segments, and gate endpoints. Remove observed elapsed time/outcome from the policy's selection predictors; any empirical timing retained is a declared fitted event distribution, not an unnoticed future input.

Select among the ten nearest compatible training templates using a fixed standardized distance in issued TWS and dimensionless course geometry. Require compatible leg type, boundaries/gates, and course-relative wind regime. Use inverse-distance weights with a documented finite epsilon. Prefer team templates only with at least ten eligible legs across three training days; otherwise use explicit pooled templates and report that support tier. These are versioned minimum-support policies, not proof of forecast reliability.

Freeze feature scales and support envelopes within training folds. Sampling target headings/routes is legitimate scenario generation; using the held-out race's actual heading sequence is leakage.

Transform longitudinal/lateral coordinates with the requested course frame, preserving legal boundary containment and actual distances. Recompute segment COG from transformed tangents; derive heading using the sampled heading-minus-COG offset, then recompute TWA, turn angles and distances. Check each resulting motion/event feature tuple against training support. Reject a request if its geometry lies outside the training envelope, a route crosses a boundary/gate incompatibly, or supported templates cannot be sampled within 20 deterministic attempts. Do not silently clip a path to fit. Report the supported geometry range and route availability.

A two-boat joint route-template variant may be evaluated later. Version 1's independently sampled observed routes do not model adversarial covering/interaction; state that limitation. Never use a full held-out route as a shortcut in the pre-race evaluator.

### G3.3 Maneuver, start, and dwell accounting

Partition every simulated path into disjoint straight, maneuver-plus-recovery, start, and dwell segments. Every segment contributes exactly once.

- Straight segment time comes from actual segment distance divided by predicted/sampled SOG.
- Maneuver-plus-recovery duration REPLACES straight integration over that event's path segment. Do not integrate the whole path and add the full maneuver duration.
- Fit a pooled lognormal event-duration model with regularized team deviations and right-censored likelihood; inputs include event type, issued TWS, speed-independent angular/entry geometry selected by policy, and predicted entry speed. Eventual recovery time, recovery-defined path length and exit position are targets/diagnostics, never predictors. Only complete paths can enter the route library; censored onset records can still train a censoring likelihood.
- Training entry-speed predictors for pre-race event fitting are chronological out-of-fold predictions, not actual future speeds handed to inference.
- Live observed entry speeds may be used only in a separately labeled causal live variant.
- Retain zero-distance dwell intervals and slow progress. They cannot vanish during polyline compression.
- Sample start state/initial acceleration behavior from supported training gun-to-steady segments. Start timing begins at the gun. No extra countdown, unexplained fixed finish time, or invented boundary penalty.
- Actual gate rounding is either its own event or part of the sampled path; never both.
- An unmodeled penalty remains unsupported/unresolved rather than a made-up time adjustment.

Local speed/progress deficit is an optional descriptive diagnostic, not the target needed to identify the whole event duration. If no recovery is observed, retain censoring and available partial information. A model-relative excess-time explanation is not an independently identified causal maneuver effect.

### G3.4 Predictive uncertainty without double counting

First implement a coherent conditional predictive distribution; do not add every available source of variance.

1. Produce chronological out-of-fold predictions for the selected motion/event model using training-only fits.
2. Form randomized-quantile residuals using the predictive CDF. For an exact observation use U=F(y); left-censored speed uses U drawn uniformly from [0,F(floor)]; right-censored event duration uses U drawn uniformly from [F(censor),1]. Transform with inverse normal CDF, clipping only to the registered numerical interval [1e-6,1-1e-6]. Store five seeded censor-imputation replicates and report tail assumptions; never selectively discard censored observations.
3. Store contemporaneous paired-boat STEADY-MOTION residual blocks on a common calendar clock. Preserve serial/cross-boat dependence, availability masks and phase. Unavailable channels are missing, not zero. Version 1 samples event-duration innovations separately by supported event type/context; cross-boat event-error dependence is explicitly not modeled. It does not try to find an asynchronous event in a steady-motion block.
4. At rollout use predicted mean + predicted scale times the sampled residual in log units. Do not also draw an independent Gaussian/t innovation or a separate shared-weather shock containing the same residual variance.
5. If seed members are mixed, calibrate and evaluate that complete mixture. Do not add its spread again as independent noise.
6. Fit any residual recentering/scale calibration only on chronological calibration predictions inside the outer training period.
7. When paired residual evidence is insufficient, expose the uncertainty/correlation limitation and run preregistered development sensitivities; do not invent a fixed correlation.
8. A day/race bootstrap used for score confidence intervals is separate from a model-parameter bootstrap used for simulation. Version 1 requires the former; parameter-refit ensembles are a later registered extension unless implemented and calibrated in full.

A variance ledger states which fitted object represents serial execution variation, shared conditions, between-seed sensitivity, model-parameter uncertainty, and Monte Carlo numerical error. If a component is not modeled, say so.

For fixed-wind scenarios, both boats receive the same declared wind. Remaining joint residuals represent unexplained observed variation; they are not evidence of a validated weather process. A future time-varying weather model is a separate registered extension.

### G3.5 Completion and probability scope

Do not reuse the old hard-coded failure probabilities.

Maintain scheduled denominator, start status, valid timed finish, official classification, cause, and recording censoring separately. Recording loss is not a mechanical failure. Practice sessions are not the competitive reliability denominator.

Default output when reviewed completion evidence is insufficient:

- probability_scope = completion_assumed_on_water
- Display which boat is faster in a scenario that assumes both complete; do not claim the observational distribution conditional on actual joint completion.
- Unconditional win, no-winner, and completion probabilities are unavailable, not zero.
- Timing/margin summaries use that same completion-assumed population. Physical intervals from later-retired boats may train motion, so disabling failure alone does not identify P(win | actual joint completion).

A pooled Beta-Binomial completion model may be enabled only for a fully reviewed, comparable competitive denominator; record its prior and interval sensitivity. Do not infer team-specific reliability from a few events. If exposure/time limits need different treatment, leave unconditional output unsupported until that model is validated. Mechanical failure, DNS, OCS/DSQ, abandonment, and race time limits are separate phenomena.

A trajectory exceeding its configured physical time budget is unresolved_simulation, not DNF. A worker wall-clock timeout is a failed job. In version 1 ANY unresolved trial makes headline probabilities and timing summaries unavailable; retain diagnostic counts and an explicit reason, never silently renormalize. G8 defines denominators and limits.

### G3.6 Evaluation and model selection

Freeze split membership using source/session metadata before candidate scoring.

- Keep both boats, all windows, overlapping recordings, stopped attempts, and linked resails in one race-family group.
- Outer development: expanding chronological days; inner tuning: earlier whole-day blocks only.
- Reserve the latest 20% of competitive AC75 dates, at least three if feasible, as a locked chronological evaluation block. T02 creates a metadata-only reservation and T05 resolves/freezes whole families BEFORE T07 detector tuning/review. T09 seals these assignments with feature hashes; it cannot move held-out families because labels were inconvenient or unsupported. Keep unsupported final cases in the coverage denominator.
- Mark prior exposure honestly. Existing summaries/ratings may already use later races. A newly locked block is not automatically historically untouched.
- Record holdout access and consumption. If no genuinely unused evidence remains, report historical development evidence and require prospective/external evidence for a future validated claim.
- Fit identity effects, routes, preprocessing, support, calibration, completion, and residual samplers inside each training cutoff. The existing full-data AC37 transfer ratings are prohibited inputs to a historical fold.
- Outcome-only Match rows can score a suitable pre-race winner forecast only after per-race verification and information-cutoff checks. They cannot provide speed, maneuver, or margin labels without supported telemetry/timing.
- ETNZ has no later Louis Vuitton racing equivalent to the finalists' observations. Report stale/sparse team coverage; do not invent later ETNZ development.
- Report all-supported and common-support subsets, team/wind/phase/stage errors, and leave-one-team-out stress tests. A final block containing mostly two teams does not validate all six teams.

Component tuning objective: race-equal motion negative log likelihood; event tuning uses censored duration negative log likelihood. END-TO-END selection objective: race-margin CRPS, frozen before training. Secondary metrics are SOG/VMG MAE/RMSE, event duration, race-time MAE, matched-target Brier/log loss, and 50/80/95% predictive coverage/interval scores.

Compute paired candidate-minus-best CRPS differences per date on the common supported race set. With at least five scored development dates, a candidate is within one standard error when mean difference <= sample standard deviation of date differences / sqrt(number of dates). Choose the simplest such eligible candidate, ordering empirical < spline < neural. With fewer than five dates, retain empirical as the default experimental reference and report point-best challengers without a superiority claim. Report each candidate's coverage on the full registered population; a candidate cannot win by silently abstaining on difficult races. Use date-clustered paired confidence intervals and show per-date differences. Do not bootstrap telemetry frames. Both baseline and NN must still be trained/scored.

Do not reuse universal Brier 0.18/log-loss 0.55 thresholds as a validation guarantee. First learned release remains experimental. A better speed fit alone does not establish better win probabilities. Engineering pass, data support, default-candidate selection, and predictive validation are separate statuses.

## G4. Artifact layout, CLI, and runtime contract

All paths below are proposed, not existing completed features.

~~~text
.forecast/ac75_learning/
  sources/<inventory_id>/manifest.json
  native/<dataset_id>/...parquet
  datasets/<feature_id>/index.json + tables
  experiments/<experiment_id>/registration.json + splits.json
  runs/<run_id>/config.json + predictions.parquet + logs/
  models/<model_id>/manifest.json + weights.npz + preprocessing.json
  policies/<policy_id>/routes.parquet + support.json
  uncertainty/<uncertainty_id>/residual_blocks.parquet + ledger.json
  evaluations/<evaluation_id>/report.json + report.md
  scenarios/<scenario_id>.json
  candidates/<bundle_id>/catalog.json
  latest_candidate.json
  progress.json
  logs/
~~~

Never include creation timestamps in logical content identity. Keep them in an external audit envelope. Verify actual file bytes as well as logical hashes. Parquet writer/environment differences may alter physical bytes; preserve logical-table hashes and actual transport-file hashes separately.

Cache identity includes source bytes, decoder/schema/unit rules, quality/feature/label versions, identity registry, splits, code hashes, fitted preprocessing/model, route/residual/completion objects, course, scenario policy, seed, and trial count. Hash only the actual owning code/configuration, not unrelated dirty worktree contents.

Use atomic writes to a temporary sibling and validate all references before advancing a candidate pointer. Corrupt/missing artifacts fail explicitly. No permissive pickle/object loading or unverified remote model download.

Proposed CLI, implemented incrementally:

~~~powershell
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml inventory --config <config>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml decode --inventory <id>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml dataset --inventory <id> --config <config>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml labels --dataset <id>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml splits --dataset <id> --registration <path>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml train --experiment <id> --candidate empirical
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml train --experiment <id> --candidate spline
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml train --experiment <id> --candidate neural
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml evaluate --experiment <id> --development
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml evaluate --experiment <id> --final --consume-holdout
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml simulate --request-file <path>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml export --model <id> --scenario-set <path>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml verify --bundle <id>
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml snapshot --stage <stage> --max-examples 3
~~~

All substantial commands write durable artifacts and return a compact JSON receipt containing status, IDs, paths, counts, elapsed time, and relevant blockers. Logs go to stderr/files; machine-readable stdout is bounded and valid JSON. A receipt is evidence of execution, not a statistical validation assertion.

For the small neural network add a forecast-neural optional dependency group with a stable Python-3.12-compatible PyTorch 2.x CPU build, bounded below by 2.7 and below 3. Resolve the exact compatible version with uv and commit uv.lock. Keep forecast-core independent. CPU is the reference environment; no CUDA, torchvision, or torchaudio dependency is required. Optional GPU acceleration must use a separately recorded environment and equivalent tests.

Example environment command after dependency changes:

~~~powershell
uv sync --locked --extra forecast-core --extra forecast-ml --extra forecast-neural
~~~

Do not install into an unrelated global interpreter. Record Python, NumPy, SciPy, PyArrow, sklearn, Torch, OS, CPU/device, thread count, source version, and code hashes. Reproducibility claims are scoped to the pinned environment; cross-platform floating-point identity is not promised.

## G5. Dependency schedule and review gates

| Gate | Tasks | Required evidence |
|---|---|---|
| A: contract/source | T00-T05 | Source/identity/wire/attempt accounting; preservation manifest |
| B: labels/dataset | T06-T09 | Correct units/timing, reviewed or labeled-provisional events, sealed data, frozen folds |
| C: learned components | T10-T13 | Fitted baselines and mandatory NN, event policy, calibrated residual ledger |
| D: race forecast | T14-T15 | Coherent rollout and honest end-to-end development/final evaluation |
| E: application | T16-T18 | Same inference for saved/on-demand, exact cache, responsive service, accurate UI |
| F: delivery | T19-T20 | Focused/full verification, candidate/evidence, compact handoff and rollback |

Review is an evidence check, not a recurring user-permission request. Continue authorized reversible work when a gate passes. If a schema or independent label source is unavailable, record it precisely and continue unaffected work. Do not silently lower a contract to mark a gate passed.

Potential parallelism:

- T03 and T04 can proceed after T02 with separate files.
- Outcome evidence review in T05 can continue while T06 sensor/window work proceeds against already resolved attempts.
- T10 and T11 can run in parallel after shared T09 feature/preprocessing interfaces are fixed.
- T17 may be built against deterministic T16 fixtures while the expensive full evaluation runs.
- T18 may use final-contract fixture artifacts, but cannot change numerical contracts independently.
- Serialize edits to shared contracts, feature builders, split manifests, and inference interfaces.

## T00. Establish preservation, environment, and execution receipts

Dependencies: none.  
Read: AGENTS.md, PROJECT.md, this file G0-G5, pyproject.toml, run.ps1.  
Own: initial progress/registration receipts; narrowly scoped dependency changes later needed by T11.

Actions:

1. Capture git status and list pre-existing changes. Do not modify them.
2. Hash existing public replay/analysis/prediction files and their indexes into a preservation receipt; avoid printing their contents.
3. Record existing data audits and a metadata fingerprint. Do not stream 23 GB simply to rediscover paths.
4. Capture installed interpreter/dependency availability and available disk/RAM/CPU. Estimate native-cache space from a bounded pilot before full extraction.
5. Create .forecast/ac75_learning/progress.json with tasks, dependencies, status, artifact IDs, checks, and blockers.
6. Add a small CLI shell and configuration validation in the appropriate later-owned modules only when needed; avoid empty placeholder functions.
7. Capture an existing quality-tool baseline without accepting/resetting its baseline or editing .aislop/config.yml.

Acceptance:

- Existing changes remain present.
- Preservation receipt covers actual existing public artifacts and includes paths/counts/hashes.
- Missing optional packages have a planned install path; their absence is not a false test pass.
- Progress can survive a new chat with no need for the old conversation.
- Disk shortfall stops the affected extraction before partial caches are treated as valid.

## T01. Freeze dataset, model, request, and identity contracts

Dependencies: T00.  
Read: G2-G4; src/types/kinematic.ts; pipeline/prediction/contracts.py; pipeline/identity.py.  
Own: contracts.py, config.py, configs/ac75_2024_v1.json, docs/ac75_learning_contract.md, focused contract tests.

Actions:

1. Implement G2 typed records, enums, stable reason codes, explicit units, and validators.
2. Separate predictors from targets in the schema and expose an allowlist per task.
3. Implement historical identity resolution before model lookup.
4. Define scenario-v2 as a discriminated available/unavailable result with nullable probability objects and explicit scope.
5. Define installed-model references by IDs/hashes, never caller-supplied paths.
6. Define a versioned config hash including all G2.6 settings, experiment defaults, and support policy.
7. Define legacy-v1 read compatibility without silently upgrading old values to learned results.

Acceptance tests:

- Null/zero/unresolved/censored round-trip distinctly.
- NaN/infinity, wrong units, missing provenance, unknown enums, target-as-feature, and unknown request keys fail.
- Historical GB1 alias resolves to INEOS only in AC37 scope; AC38 identity does not.
- Existing old catalogs remain readable as explicitly legacy, not learned.

## T02. Inventory the complete archive and register evidence

Dependencies: T01.  
Read: docs/source_audit_ac37.md; scripts/audit_ac37_source.py; relevant inventory helpers.  
Own: inventory.py; source manifest; docs/ac75_learning_data_audit.md; inventory tests.

Actions:

1. Enumerate the known AC37 tree with filenames/metadata, including files outside the six known sections.
2. Classify every file as included, unsupported format/schema, duplicate, pending review, or excluded with reason.
3. Reuse existing source hashes only when their binding to current bytes is trustworthy. At initial normalization verify content hashes while streaming; thereafter verify sealed caches and changed-file metadata.
4. Gather bounded header/schema samples, then full-stream counts/ranges/field coverage during normalization.
5. Register source schema/unit/field evidence and actual decoder availability. Search for schema files by targeted filename/metadata inventory, not raw-text recursion.
6. Inventory docs/ac37_results.json and anchors as candidate outcome evidence, field by field; do not accept their self-description as verification.
7. Record known prior exposure of summaries/results and reserve the chronological evaluation dates using metadata only; T05 freezes family membership before detector/label tuning.

Acceptance:

- All current source files are accounted for; the 132-file audit is reconciled, not hard-coded as an invariant if files changed.
- AC40 and AC75 cannot mix accidentally.
- One compact report shows sources, bytes, stages, dates, decoded status, and missing evidence.
- No fabricated count of unique races or claim that all Match telemetry exists.

## T03. Implement full streaming JSONL normalization

Dependencies: T02.  
Read: source.read_source/digest, ingest identity/interpolation helpers, G2.3/G2.4.  
Own: source.py, dataset.py's native-write helpers, JSONL fixtures and tests.

Actions:

1. Retain source ordinal/offset and every relevant field in a packet; no first-field-only elif chain.
2. Use a metadata pass or equivalent staged join so pre-session telemetry survives.
3. Parse UTF-8/JSON errors explicitly with counts/offsets and at most three bounded examples. Never ignore decoding errors or swallow exceptions. If corruption prevents reliable session/channel/time attribution, quarantine the file pending recovery/review. Localizable recoverable corruption excludes an explicitly bounded affected interval; it does not silently count as eligible coverage.
4. Normalize confirmed units once; retain native channel/source provenance.
5. Write bounded native Parquet batches and deterministically sort disordered streams without whole-archive lists.
6. Preserve revisions/conflicts and source availability. A single late packet must not terminate reading the rest of the file.
7. Do not use the legacy one-hertz AC40 reader as the native AC75 label dataset.

Acceptance tests:

- Data beyond 100,001 lines and beyond an out-of-order late packet survives.
- Multiple fields, pre-session packets, repeated timestamps, malformed records, and missing units behave explicitly.
- Generated tenfold-longer streams do not require tenfold in-memory storage.
- Re-running produces the same logical data hash; changed raw bytes invalidate affected cache entries.

## T04. Support verified AC37 binary decoding

Dependencies: T02.  
Read: schema evidence inventory and ac37 wire descriptions; do not assume the audit prose is a descriptor.  
Own: ac37_wire.py, verified descriptor metadata, schema-generated fixtures/tests.

Actions:

1. Locate and pin an authoritative .proto/descriptor and any authorized decoding dependency.
2. Verify frame prefix/endianness/length limits from bounded real frames and the schema.
3. Decode using generated or descriptor-based protobuf support; preserve unknown optional fields.
4. Map units, timestamps, positions, session/competitor enums and channels using the same normalization contract as JSONL.
5. Reject malformed/truncated frames with offsets.
6. If descriptors are unavailable, implement the explicit unsupported_wire_schema path, record all affected files, and continue the JSONL pipeline. Request only the genuinely missing external schema/evidence while independent tasks proceed.

Acceptance:

- Equivalent generated JSONL/binary fixtures normalize identically.
- Truncated prefixes/payloads and unknown schema versions fail predictably.
- No guessed numeric tag creates a training value.
- Coverage claims distinguish the full inventoried archive from the successfully decoded training subset.

## T05. Resolve race attempts, duplicates, geometry, and outcome evidence

Dependencies: T03; incorporate T04 results when available.  
Read: identity.py; prediction/labels.py; extract_ac37_archive_results.py; session/competitor contracts.  
Own: attempt/identity parts of source.py and labels.py; evidence ledger; tests.

Actions:

1. Resolve session-local assets and class before assigning historical team IDs.
2. Construct family/attempt IDs from evidence; link stopped races and resails without merging their timing.
3. Deduplicate exact files and identical packet observations. Reconcile overlap by verified packet identity; preserve unresolved contradictory values.
4. Keep practice physical intervals separate from scored competitive outcomes and reliability denominators.
5. Extract timestamped marks, boundaries, gates, leg direction/length, gun changes and finish status with provenance.
6. Reconcile candidate winner/margin/wind fields against per-race source evidence. A generic URL or series score is insufficient for every field.
7. Mark official, reconstructed, reviewed, unknown and censored labels distinctly. Keep valid earlier intervals after a later retirement.
8. Freeze metadata-only final-evaluation family membership before T07 review/tuning; expose only authorized training groups for detector selection. Unsupported final labels remain in the coverage report.

Acceptance tests:

- Duplicating a recording cannot change training weights, race counts or scored outcomes.
- A stopped/resailed family has distinct attempts but at most one valid scored outcome.
- Conflicting values do not silently use filename order as authority.
- Missing telemetry does not imply DNS/DNF.
- Every scored outcome and timed margin has appropriate field-level evidence.

## T06. Implement causal alignment and exhaustive steady windows

Dependencies: resolved T05 attempts; may overlap remaining outcome review.  
Read: G2.1-G2.6; feature support functions; historical VMG formula owners.  
Own: features.py and narrowly split helpers; feature tests.

Actions:

1. Build per-asset/per-channel as-of lookup using available_at_ms, not nearest future timestamps.
2. Keep boat-local and named official wind streams separate; declare wind selection and stale/missing behavior.
3. Retrospective target integration may use bracketing observations only within documented age/gap support. Predictor features remain causal.
4. First create aligned native views and preliminary angular/event candidates, then provisional nonoverlapping five-second active-leg windows; remove max_windows training caps. T07 finalizes detector/recovery intervals. T08 must rerun this builder with that frozen event version before sealing any training table. Changing a detector/recovery rule invalidates all affected window hashes.
5. Use duration weighting and stream-specific boundary support. One-hertz wind is not required to provide three frames in 500 ms.
6. Calculate SOG, COG-based progress/VMG, TWA, coverage, gaps, availability, phase/domain flags, and source ranges.
7. Include slow states. Exclude unresolved conflicts, unsupported geometry, prestart/abandoned/terminal intervals, and maneuver/recovery/rounding intervals from straight training.
8. Preserve exclusions in a compact reason-count table by team/day/wind/stage.

Acceptance tests:

- Post-issue mutations leave features unchanged.
- Heading differs from COG under synthetic leeway and VMG remains correct.
- One boat's wind cannot become another's by anonymous pooling.
- Valid one-hertz wind passes; stale/gapped wind fails explicitly.
- Zero/missing speeds remain distinct; cadence changes do not change time-weighted summaries.
- No row overlaps a prohibited event or crosses a family/split boundary.

## T07. Validate AC75 maneuver candidates and construct event labels

Dependencies: T06.  
Read: G3.3; angular detector; current feature-audit findings, not the stale progress-log accuracy claims.  
Own: maneuver portions of features.py/labels.py; bounded review export; tests.

Actions:

1. Fix forward wind lookup and source identity before classifying turns.
2. Keep angular detection independent of observed speed loss. Retain other/ambiguous rotations.
3. Distinguish tack, gybe, rounding, overlapping turns, and unsupported classifications.
4. Build two deterministic TRAINING-ONLY review samples: initially 120 candidate clips for type/boundary precision, and 60 complete continuous 60-second windows selected independently of detector output for missed events/recall. Stratify available teams, stages, wind and slow/zero-loss states; use all if fewer. Final-evaluation families are inaccessible for detector tuning. Outer-fold tuning uses only that fold's earlier training groups.
5. Export local heading/speed/progress traces with raw references. An independent reviewer labels all event types/bounds throughout continuous windows. Compute false negatives/recall only from the independently annotated continuous-window subset; candidate clips alone cannot measure recall. Algorithm-to-algorithm agreement is not human ground truth.
6. Freeze detector settings after authorized training-only review. An unavailable independent review keeps labels provisional and the corresponding validation claim unavailable; it must not prevent unrelated training work.
7. Label observed event/recovery duration, entry/exit speeds, progress, censoring, and source support.
8. Remove 25/15-knot fallbacks and minimum-one-second synthetic losses.
9. Optional local-reference deficit uses supported pre/post steady progress, is signed, and is explicitly a proxy. Exclude it when support/confounders fail.

Acceptance tests:

- Constant-speed tack detected; isolated speed loss without rotation not detected.
- Wraparound classification and no-future-wind behavior.
- Censored recovery contributes a censoring record; it does not become 30 seconds or vanish.
- Zero/gain deficits remain zero/negative.
- Overlapping intervals are not double-counted.
- Report actual review precision/recall and uncertainty only against the stated reviewed sample.

## T08. Seal datasets and build route templates

Dependencies: T05-T07, plus supported T04 data.  
Read: G3.2/G3.3 and G4.  
Own: dataset.py sealing/loaders; routes.py extraction; dataset/route tests.

Actions:

1. Regenerate T06 windows using T07's frozen event/recovery partition; no provisional windows may enter fitting. Then materialize native-derived attempts, steady windows, events, legs, outcomes/completion, and quality tables with stable logical hashes.
2. Every row traces to source packet ranges, contract version, units, quality, and availability.
3. Build route templates with disjoint straight/event/start/dwell segments and sufficient geometry for physical distance.
4. Compress only geometry; preserve gate intersections, turn bounds, and zero-distance dwell intervals.
5. Store template eligibility and raw measured environment separately from fold-specific selection/scaling. No fitted support or template library may be global across folds.
6. Generate a compact snapshot showing included files versus excluded/undecoded sources, unique families/attempts/days, boat-legs, event counts, wind coverage, and team imbalance.
7. Verify public preservation hashes before moving on.

Acceptance:

- Every eligible source is processed exhaustively or explicitly excluded.
- Route partitions cover each source interval exactly once.
- Loader rejects corrupt tables, stale unit mappings, or incompatible feature versions.
- Building a training-only policy excludes all held-out IDs even though raw label extraction was cached globally.
- No public replay/analysis hash changes.

## T09. Freeze folds, exposure ledger, and experiment registration

Dependencies: T08.  
Read: G3.6; current eval implementation for defects to avoid.  
Own: splits.py; immutable registration/split manifest; leakage tests.

Actions:

1. Seal the metadata-only development/final family reservation already frozen in T05, attach dataset/feature hashes, and derive expanding development folds using G3.6. Do not reassign final families based on detector results or candidate performance.
2. Keep linked resails and both boats together; expand final membership to whole families when needed.
3. Record exposure from existing results, primitives, team ratings, and previous selection. Label the final block accurately.
4. Freeze inputs, targets, row weighting, baseline definitions, search grid, metrics, aggregation, support rules and selection policy.
5. Implement training-only loaders and a final-target access guard with a consumed-holdout ledger.
6. Register inner chronological validation/calibration splits wholly within each outer training set.
7. Prohibit full-data transfer ratings and held-out route/weather information from fold inputs.
8. Define the practice-domain inclusion ablation and common-support/team stress reports.

Acceptance tests:

- No family/day overlap; training and target availability precede relevant cutoffs.
- Modifying final targets cannot change fit/preprocessing/route/support hashes.
- Accessing final targets records consumption and cannot masquerade as a new untouched test.
- Training a historical forecast with a later full-data rating fails.
- Sparse folds report insufficient evidence rather than silently using future days.

## T10. Fit empirical and regularized learned baselines

Dependencies: T09.  
Read: G3.1/G3.6; fixed feature/preprocessing interfaces.  
Own: baselines.py; baseline training adapters; baseline tests.

Actions:

1. Fit supported pooled empirical wind/angle/phase lookup with explicit counts and bounded interpolation.
2. Fit a penalized spline response for log speed with shrunken team deviations and the registered regularization grid.
3. Estimate predictive scale/residual support using training/calibration only.
4. Use exactly the registered rows, units, weights and cutoffs.
5. Record per-fold predictions and fit receipts; no silent fallback to manually assigned team-speed coefficients.
6. Preserve the old fixed simulator as a labeled legacy benchmark, not the strongest learned comparison.
7. Where appropriate fit a prior-only race-strength baseline on matched verified outcomes, without outcome-target mismatches.

Acceptance:

- Real fitted artifacts and out-of-fold predictions exist.
- Synthetic response data learns a known wind/angle relationship.
- Duplicate windows/sensor cadence do not change race-equal scores.
- Unsupported conditions return documented support states.
- Team effects are learned within each cutoff and shrink when evidence is sparse.

## T11. Train and export the mandatory small neural network

Dependencies: T09; use the same shared feature contract as T10.  
Read: G3.1; pyproject.toml; Torch reproducibility/Gaussian loss documentation.  
Own: neural.py, training.py neural adapter, optional dependencies/uv.lock, neural tests.

Actions:

1. Install and lock the Python-3.12-compatible optional CPU dependency; preserve core-only operation.
2. Implement the 2x32 SiLU architecture, penalized team deviations, Gaussian log-speed likelihood, and censored low-speed handling.
3. Fit fold-local scaling/encoding; enforce the feature allowlist.
4. Train the eight registered configurations with early stopping inside earlier-day validation only.
5. Select using registered development evidence; refit selected settings for three seeds. Record weights, gradients/fit sanity summaries, epochs, time and environment.
6. Save best validation checkpoint deterministically; do not silently load a stale or random checkpoint.
7. Export a safe numeric NPZ and JSON inference representation with content hashes.
8. Implement the equivalent NumPy forward pass; compare distribution parameters and predictions against Torch.
9. Store full logs locally and emit one compact comparison receipt.

Acceptance tests:

- Parameters change from initialization and the optimizer actually reduces synthetic training loss.
- A learnable synthetic problem beats its constant baseline; a shuffled-target control loses that relationship.
- Censored observations have finite correct likelihood and are not dropped.
- Torch/NumPy mean/scale agree within registered numerical tolerance, initially 1e-5 absolute/relative.
- Same pinned CPU environment/seed reproduces the registered tolerance and artifact identity policy.
- Required neural tests are executed in the neural environment, not silently skipped.
- A losing NN still has saved weights, predictions and an honest result.

## T12. Fit event timing, start behavior, and route selection

Dependencies: T08-T11.  
Read: G3.2/G3.3; out-of-fold speed predictions.  
Own: routes.py runtime policy; event model adapters; relevant tests.

Actions:

1. Fit pooled/regularized lognormal maneuver-plus-recovery duration models with censored likelihood.
2. Generate pre-race entry-speed features from chronological out-of-fold motion predictions.
3. Learn supported start/dwell behavior from training attempts; retain pauses and incomplete/censored events.
4. Assemble fold-specific nearest-template selection/support, explicit team-to-pool backoff, and geometry checks.
5. Ensure route geometry supplies simulated future actions without reading a scored race's route.
6. Validate event/path time accounting on held-out legs, not just isolated maneuvers.
7. Do not manufacture a tack/gybe count formula, 2-second boundary penalty, or 30-second finish time.

Acceptance:

- Predictors match the pre-race information set.
- Censored difficult events affect likelihood.
- Each path segment is charged once.
- A longer maneuver event increases total elapsed time by the same amount in a controlled fixture.
- Unsupported transformed routes fail explicitly.
- Gun-to-finish time has no hidden countdown/finish offsets.

## T13. Calibrate predictive scales, joint residuals, and completion scope

Dependencies: T10-T12.  
Read: G3.4/G3.5.  
Own: uncertainty.py, completion.py; variance ledger; uncertainty tests.

Actions:

1. Create chronological calibration residuals without using the scored outer day.
2. Fit/normalize paired residual blocks and scale calibration for the complete selected predictor.
3. Preserve common-clock serial/cross-boat structure; record support and sparse contexts.
4. Implement one variance path, with switches for diagnostic ablations; prohibit double-added innovations.
5. Record seed sensitivity separately from estimated model-parameter uncertainty.
6. Review completion denominators/causes. Enable only the supported pooled completion scope; otherwise return explicitly completion-assumed scenario outputs, not observational joint-finisher probabilities.
7. Register 15/30/60-second block sensitivities and completion-prior sensitivity using development data only.

Acceptance tests:

- Shared residuals move both simulated boats together in a controlled fixture.
- Standardization/reconstruction reproduces residual means/variances within sampling tolerance.
- Turning on residual sampling does not also introduce a hidden independent error draw.
- All completion probability objects identify denominator/prior/support.
- Recording loss and computational timeout cannot become mechanical failure.
- Unavailable unconditional probability is null with a reason.

## T14. Implement one learned race simulator and inference entry point

Dependencies: T12-T13.  
Read: all G2/G3; current simulator.py for legacy compatibility only.  
Own: inference.py, simulator.py learned path, canonical scenario request/result validators, simulator tests.

Actions:

1. Implement predict_scenario(installed_model, normalized_request) as the single numerical entry point.
2. Resolve actual model/preprocessing/route/residual/completion/course IDs before calculating.
3. Use canonical competitor order and named random streams; reverse only the presentation if requested.
4. Sample training-only route policy, apply actual requested geometry, integrate straight segments, replace event segments with event duration, and account for start/dwell.
5. Apply shared conditions and supported uncertainty once.
6. Enforce probability scope, no-finisher handling, unresolved simulation mass and time-budget reasons.
7. Calculate unrounded win frequencies, time/margin summaries, central predictive intervals, and numerical MC error.
8. Produce disjoint seconds accounting; put reliability differences in percentage points outside it.
9. Batch/vectorize inference, respect memory/time budgets, and never fit a model inside inference.
10. Historical AC38 rule modifications are unsupported by default. A later explicitly assumed counterfactual must be a different configuration/status, never relabeled empirical evidence.

Acceptance tests:

- Identical profiles are exchangeable; swapping competitors reverses margins and interval endpoints correctly.
- Longer straight distance increases elapsed time; faster fixed model output decreases it.
- With supported unconditional output, P(A)+P(B)+P(no winner)=1 within tolerance, including ties.
- No joint finishers produces unavailable conditional times.
- Seconds accounting sums to the conditional mean margin; reliability does not enter that sum.
- Changing model/course/config changes the applied calculation, not just metadata.
- No hidden neutral model, old rating conversion, or legacy fixed failure rates enters the learned path.

## T15. Run full evaluation and select the experimental candidate

Dependencies: T14.  
Read: G3.6 and immutable registration.  
Own: evaluate.py learned evaluator; unrounded prediction tables; report; metric tests.

Actions:

1. Refit each eligible pipeline inside each outer fold, including policy, residuals and completion.
2. Score motion, event, leg, complete-race timing and matched winner targets separately.
3. Use issued wind/inputs in pre-race scores. Label route/weather-conditioned hindsight diagnostics separately.
4. Compare empirical, spline and mandatory neural candidates under the same information set.
5. Aggregate by race/day with paired grouped uncertainty; publish per-team/wind/stage/common-support results.
6. Report support/abstention and unresolved mass. Accuracy conditional on abstention must show retained coverage.
7. Select the default experimental candidate under the registered rule; preserve losing candidates.
8. Only after configuration/selection is frozen, consume and score the final block once if appropriate. Record prior exposure and all access.
9. If evidence is too sparse or no candidate improves, deliver that finding without retuning on the final block.
10. Record that engineering verification and historical fit do not confer an AC38 validated status.

Acceptance:

- Hand-computed metric fixtures match implementation.
- Bootstrapping frames is impossible in the headline score path.
- Global features/full-data team ratings cannot enter historical folds.
- Reports identify exact candidate/model/split hashes.
- NN training/result is included regardless of winner.
- A reproducible poor model never receives validated merely because generation succeeded.

## T16. Export immutable models, scenarios, and exact caches

Dependencies: T14; candidate selection metadata from T15.  
Read: G4; current export.py and contracts atomic writer.  
Own: artifacts.py, export.py; artifact/serialization tests.

Actions:

1. Export normalized requests exclusively through predict_scenario.
2. Hash the complete applied configuration and pinned artifacts; remove partial/default-rule matching.
3. Keep timestamps outside content identity and serialize finite values canonically.
4. Validate source/model/route/residual/completion references and actual weight/table bytes.
5. Define one exact scenario key, including purpose/count/seed, with deterministic canonical team ordering.
6. Stage candidate catalog and evaluation references atomically under the new private root.
7. Keep legacy catalogs explicitly legacy; missing learned bundles cannot silently fall back.
8. Produce deterministic tiny installed-model fixtures for the service/UI tests.

Acceptance:

- Saved and forced on-demand inference are identical for the same model/request/seed/trials, excluding external audit envelopes.
- Any changed rule/course/model/uncertainty object invalidates the cache.
- Corruption or interrupted export leaves the previous valid pointer usable.
- Safe numeric loading rejects object arrays and unexpected shapes.
- No public historical artifact changes during candidate export.

## T17. Integrate bounded asynchronous inference into the local service

Dependencies: T16 fixtures; full T15 evaluation may run independently.  
Read: scripts/kinematicScenarioMiddleware.ts; scripts/forecastScenarios.ts job pattern.  
Own: middleware and a small worker runner; focused service tests.

Actions:

1. Replace spawnSync with an injectable asynchronous runner and job lifecycle.
2. Start one pinned Python inference worker when needed; load the safe learned artifact once. Never train, extract data, install packages or select models in a request.
3. POST a small allowlisted request; exact cached results return immediately, otherwise return 202 and a job ID. GET job status returns bounded progress and the completed scenario inline, following G8.5.
4. Begin with one running job, queue of at most four, deduplicate exact requests, maximum 32 retained finished jobs, and configured timeouts. Measure actual latency and memory.
5. Validate byte-counted JSON body up to 2 KiB, content type, finite numbers, distinct supported identities, installed model/course IDs and unknown keys.
6. Enforce allowed loopback Host, loopback peer address including IPv4-mapped IPv6, and same-origin browser requests. Do not use a Host header alone as authorization.
7. Resolve installed artifact paths inside a fixed root; callers cannot supply arbitrary paths or executable arguments.
8. Bound worker stdout/stderr, handle crashes/timeout/drain, pin the model for the whole job, and expose useful sanitized errors.
9. Use status categories 400/403/404/405/409/413/415/422/503 as appropriate.
10. No fallback to random weights, neutral teams, a different model, or a nearest cached wind.

Acceptance:

- A slow inference job does not freeze unrelated dashboard requests.
- Oversized/invalid/malicious/off-origin/non-loopback requests fail before worker execution.
- Exact cache matching includes all applied fields.
- Worker failure preserves the previous candidate and yields a clear unavailable/failed job.
- A test spy proves the service never invokes training/extraction.
- Restarted or reloaded workers cannot switch model IDs midway through a job.

## T18. Update the simulator UI and result semantics

Dependencies: T16-T17.  
Read: src/types/kinematic.ts; engine/kinematicCatalog.ts; SimulatorWorkspace.tsx; design-system docs.  
Own: those files, one shared pure reversal/validation module if needed, UI/browser tests.

Actions:

1. Read scenario-v2 with runtime validation and explicit legacy display.
2. Show historical AC37 identity/model/training scope. Do not present AC38 entrant names as observed 2024 teams.
3. Match initial saved requests exactly, including wind, course, model and purpose.
4. Keep draft controls separate from applied result inputs. Display labels from the result; mark stale results and cancel/ignore older responses.
5. Display completion-assumed scenario probabilities when unconditional completion is unavailable; never label this as an identified observational P(win | both finish).
6. Rename the interval to Central 80% simulated margin interval; distinguish predictive spread, fitted-model sensitivity and MC numerical error.
7. Replace the seven-component claim with disjoint simulated time accounting. Reliability is separate and in percentage points.
8. Use Competitor A/B unless a supported entry-side feature actually exists.
9. Present support/exclusion reasons in plain language. Missing values are not zero.
10. Retain accessible controls, loading/progress/error behavior and keyboard interaction within the existing design system.

Acceptance:

- Changing competitors/wind cannot relabel an old result as a new one.
- Reversed intervals become [-P90,-P10]; model/evidence metadata follows the correct team.
- Conditional/unavailable/legacy states render distinctly.
- Browser tests cover cached and generated results, stale response ordering, failures, units and keyboard use.
- TypeScript performs no physical forecasting calculations.

## T19. Run focused and full verification

Dependencies: T15-T18.  
Read: repository verification instructions and the preservation receipt.  
Own: focused tests and any required fixes within learned-model scope.

Focused commands after corresponding tests exist:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_ac75_*.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_kinematic*.py"
npm.cmd test -- src/components/dashboard/SimulatorWorkspace.test.ts
npm.cmd test -- src/engine/kinematicScenarios.test.ts
npm.cmd run build
aislop scan --changes --json
~~~

Create tests/unit/test_ac75_contracts.py, test_ac75_source.py, test_ac75_features.py, test_ac75_labels.py, test_ac75_splits.py, test_ac75_models.py, test_ac75_inference.py and test_ac75_artifacts.py as the corresponding ownership appears; avoid one giant test module. Use small deterministic scientific fixtures rather than fixtures copying implementation outputs.

After focused checks pass:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 verify
node tests/browser/simulator.mjs
~~~

The focused simulator browser script is new. Follow the repository server-start convention and run the relevant existing dashboard/forecast browser checks when shared navigation/contracts were touched.

Additional acceptance:

- Fix errors and fixable warnings from aislop in this change; do not disable rules or rewrite its baseline.
- Existing limits include 80-line functions, 400-line files, nesting 5, and six parameters.
- Surface inherited unrelated failures separately, with evidence; do not silently mark the whole repository green.
- Correct old tests that ignore no-winner mass or only check that rule-adjustment keys exist.
- Verify target columns are absent from inference inputs and that final-target mutation invariance still holds end to end.
- Compare preserved public file hashes/counts and explain any authorized change; zero unrelated changes is the default.
- CPU full training, statistical evaluation, software tests and browser checks have separate receipts.
- Repeat broad checks only after new changes/failures justify it.

## T20. Deliver the candidate and a compact restartable handoff

Dependencies: T19.  
Own: final evidence report, candidate references, documentation and progress completion.

Deliver:

1. docs/ac75_learning_results.md, a concise human report linking full immutable evidence.
2. Selected experimental model/bundle ID, all baseline/NN run IDs, exact reproduction commands, installed dependency lock and source/split hashes.
3. Training coverage by source/class/stage/team/wind, undecoded/excluded files, reviewed/provisional labels, and final-holdout exposure.
4. Measured component and end-to-end performance, grouped uncertainty, support/abstention, numerical MC error, and unresolved limitations.
5. Model card stating ground-relative observed behavior, routing assumptions, probability conditioning, completion support, and historical scope.
6. A ready-to-inspect candidate in the simulator without pretending it is validated or published.
7. Compact progress/handoff with completed tasks, verification receipts, remaining external dependencies and the next exact action.
8. A rollback description: stop the worker, restore the prior candidate pointer atomically, retain immutable artifacts; never delete raw data or reset user work.

Completion means the intended code/data/model/evaluation/application deliverables exist and are checked. It does not require a winning NN or a fabricated validated label. An external missing decoder schema can remain an accurately reported coverage dependency; do not claim exhaustive decoded learning while it remains unresolved.

## G6. Tests that must catch the specific old failures

These are cross-task invariants, not extra duplicate test suites:

- A record at line 100,002 is still ingested.
- Finals-only sampling cannot claim full AC75 extraction.
- Generic outcome URLs and series totals cannot certify every row.
- GB1 alias retrieves historical INEOS only in the appropriate scope.
- Raw SOG/COG units cannot be converted twice.
- COG/heading differences change ground-relative VMG correctly.
- Future wind, later session revisions and full-data ratings cannot alter an earlier forecast.
- One-hertz wind passes an appropriately supported window.
- Missing entry speed never becomes 25 knots.
- Slow/zero-loss states remain represented.
- A stopped race plus resail cannot add two scored outcomes.
- Row duplication cannot improve race-equal validation by changing its denominator.
- A future route or actual later weather cannot enter the pre-race evaluator.
- A longer course changes the actual calculation and its key.
- A shared speed boost can change race time even if winner probability remains similar.
- Event time replaces its path interval rather than being counted twice.
- Reliability differences are probability points, never seconds.
- Saved and interactive requests use the same pinned model.
- Fixed seed/count/model produces the same result through both routes.
- Displayed result labels come from the applied result, not edited draft controls.
- A task receipt or successful export cannot set statistical status to validated.

## G7. Practical source references

Local owning sources inspected for this plan:

- PROJECT.md and AGENTS.md.
- docs/source_audit_ac37.md, especially inventory, formats and source/downstream distinction.
- scripts/extract_ac75_primitives.py, especially first-12 sampling, line cap and literal summaries.
- scripts/extract_ac37_archive_results.py, especially manually specified tuples and anchor checks.
- pipeline/identity.py and pipeline/historical_analysis.py formula helpers.
- pipeline/prediction/source.py and contracts.py for sealed caches, digest and atomic JSON patterns.
- pipeline/kinematic_ml/features.py, models.py, simulator.py, evaluate.py and export.py.
- scripts/forecastScenarios.ts and kinematicScenarioMiddleware.ts.
- src/types/kinematic.ts, src/engine/kinematicCatalog.ts and SimulatorWorkspace.tsx.
- pyproject.toml, run.ps1, .aislop/config.yml and existing focused tests.

External primary documentation; consult the version matching the resolved environment:

- PyTorch installation/platform guidance: https://pytorch.org/get-started/locally/
- PyTorch reproducibility limitations: https://docs.pytorch.org/docs/stable/notes/randomness.html
- PyTorch Gaussian likelihood reference: https://docs.pytorch.org/docs/stable/generated/torch.nn.GaussianNLLLoss.html
- Grouped/time-aware validation guidance: https://scikit-learn.org/stable/modules/cross_validation.html

These references describe tools/methods. They do not establish predictive performance on this archive.

## G8. Exact interfaces and algorithms for the implementing model

This appendix resolves choices that must not be reinvented independently by separate packets.

### G8.1 Python boundaries

Use keyword-only options/dataclasses to keep function signatures within the repository's parameter limit. Protocol objects describe behavior; they do not import Torch during core inference.

~~~python
iter_source_packets(spec: SourceSpec) -> Iterator[RawPacket]
normalize_packet(packet: RawPacket, context: SourceContext) -> Iterator[NativeRecord]
build_native_dataset(request: DatasetBuildRequest) -> DatasetReceipt
build_steady_windows(request: WindowBuildRequest) -> Iterator[SteadyWindow]
build_maneuver_labels(request: LabelBuildRequest) -> Iterator[ManeuverLabel]
make_splits(dataset: DatasetRef, registration: ExperimentRegistration) -> SplitManifest
fit_motion(train: TrainingView, validation: TrainingView, config: FitConfig) -> MotionFit
fit_events(train: EventTrainingView, validation: EventTrainingView, config: FitConfig) -> EventFit
normalize_request(request: ScenarioRequest, registry: InstalledRegistry) -> NormalizedRequest
load_installed_model(root: Path, model_id: str) -> InstalledModel
check_support(model: InstalledModel, request: NormalizedRequest) -> SupportDecision
predict_scenario(model: InstalledModel, request: NormalizedRequest) -> ScenarioResult
~~~

InstalledModel is immutable and includes:

- model_id and manifest/config/code/environment/source/feature/split hashes.
- Training cutoff and historical class/cycle/identity registry.
- Fitted preprocessing and MotionPredictor.predict(MotionInputs) -> LogNormalBatch.
- EventPredictor, start/dwell distributions, route policy and geometry support.
- Motion residual-block sampler and separate event-innovation sampler.
- Completion scope/model or explicit unavailable reason.
- Numerical configuration, safe runtime limits and exact evaluation references.

LogNormalBatch contains arrays mu_log_mps and sigma_log for motion; event output is mu_log_seconds and sigma_log. Require finite values, positive scales and shapes matching input rows. Sampling and accounting belong to the simulator; a predict method does not draw hidden randomness.

NPZ export holds named numeric weight arrays with shape/dtype registry; JSON holds feature order, scales, encodings, architecture and checksums. Use scipy.special.expit for a stable NumPy SiLU, x * expit(x). Validate the complete representation before loading. No pickle, arbitrary Python class import, random initialization, or permissive missing layer.

### G8.2 Likelihoods, metrics and support

For an exact positive speed y, z=log(y), the distribution is Normal(mu,sigma) in z. Optimize the full lognormal negative log likelihood, including log(y), so scores identify their unit/density. Left censoring at c contributes -log Phi((log(c)-mu)/sigma). Event right censoring at t contributes -log(1-Phi((log(t)-mu)/sigma)); use stable log-CDF/survival implementations. Keep numerical epsilons separate from measured source precision.

A fold-local mean/scale calibrator may estimate a scale multiplier on chronological inner calibration predictions. It must be fit before the outer test and included in the model ID. Use the same distribution definition for likelihoods, residual CDFs, simulation and interval scoring.

Empirical predictive CRPS for sorted samples x[1..N] and observed y is:

~~~text
CRPS = mean(abs(x - y))
       - sum((2*i - N - 1) * x_sorted[i], i=1..N) / N^2
~~~

This avoids allocating an N-by-N pairwise matrix. Test against the direct pairwise definition on tiny fixtures. CRPS is in seconds for a time margin. Day scores average race scores; do not let dates with more races define the confidence-interval sample size.

Motion support combines supported categories with a training-only nearest-neighbor distance rule in physical variables TWS, absolute TWA, heading-minus-COG offset and course-relative wind. Fit scaling and the distance threshold from leave-one-family-out TRAINING distances, initially their 95th percentile. Check joint neighborhoods rather than only independent min/max ranges. Store exact counts/distances and report this as a support policy, not a guarantee of accuracy.

Do not predict a team-specific deviation when its fold lacks evidence; explicitly use the pooled component and flag it. Unseen teams are unsupported by default; a deliberate pooled experiment is separately requested and never called observed team performance.

### G8.3 Two-pass labels, transition events and censoring

Order:

1. T06 builds native alignment, preliminary speed-independent event candidates and PROVISIONAL windows.
2. T07 freezes authorized detector/recovery definitions and annotation evidence.
3. T08 reruns the window builder, recomputes domains/targets, and seals tables with those exact event hashes.
4. Every fold uses only authorized training annotations for detector tuning. Held-out annotation may be used later as an evaluation target, never for choosing the detector.

Stationary/dwell classification must be based on source precision and supported displacement/measurement-floor evidence, not an arbitrary high speed threshold or an inferred foil state. Unresolved movement is labeled unresolved; it cannot silently become either a dwell label or clean steady motion.

For ordinary same-leg tacks/gybes use the G2.6 reference and hold rule. If wind changes by more than two knots or the leg regime changes, the pre-event speed is no longer a valid recovery target. Mark that recovery target unavailable/censored at the regime boundary as appropriate.

For a leg-changing gate rounding use a separate rounding_transition event: onset is supported entry into the geometric rounding/turn region; endpoint is the first completed two-second supported stable-heading hold in the new leg, with heading range <= five degrees and no new turn. Freeze the geometry/phase rules in the label contract. This is an angular/operating-state transition measure, not a claim of recovering pre-turn speed. Censor if no valid endpoint before turn_end + 30 seconds or coverage ends. A legitimate downwind-to-upwind transition must not be called failed recovery simply because its normal new speed is lower.

The event feature allowlist uses onset state and policy-chosen angular geometry only. Final recovery length, final exit location, observed elapsed time, future minimum speed and eventual outcome are forbidden inputs. The whole event path may be retained as a sampled training-policy shape but its eventual recovery features cannot enter selection/regression. Censored records can train duration likelihood when their onset inputs are supported; incomplete paths cannot masquerade as complete route templates.

### G8.4 Concrete rollout and residual alignment

For each trial:

1. Use a canonical ordered competitor pair and a deterministic trial identifier.
2. Resolve support for the issued course/wind and sample supported training-only route templates.
3. Transform route geometry and recompute COG/heading/TWA; validate all resulting features.
4. Start both boat clocks at the gun. Model shared fixed wind and independently selected observed routes.
5. On straight sections use five-second calendar-time integration steps, shortened at event/gate boundaries. Consume no more than the remaining segment distance. Query motion parameters at the current policy heading/conditions and combine them with the residual value indexed by the common simulated calendar time.
6. For events, advance distance along that event path using its predicted event duration; do not perform straight integration there. Draw a separate supported event innovation. Resume straight residual lookup at the NEW clock time; do not reset the residual clock when a boat turns.
7. Dwell/start segments advance their own duration and prescribed path/state once.
8. End on the supported finish crossing; retain per-domain times. Apply a reviewed completion process only when that scope is enabled.

Pair residual libraries contain observed availability masks. Interpolate only within registered supported short gaps; never fill an absent channel with zero. If no compatible paired block is available, the standard request is unsupported unless its installed config explicitly selects a pooled conditional independence sensitivity. That sensitivity has a different scenario key and status. Event residuals remain separate; version 1 does not claim learned cross-boat event-error covariance.

Initial maximum trajectory time is 21,600 seconds, a numerical guard, not a race rule or failure definition. One unresolved trajectory makes headline output unavailable. Keep n_requested, n_resolved, n_unresolved, modeled completion counts and reason counts.

In completion_assumed_on_water scope with no unresolved trials, each trial contributes win indicators (1,0), (0,1), or (0.5,0.5). Divide by N requested trials. In reviewed unconditional scope, neither finisher contributes to no_winner; all probability mass must be accounted for. Time/margin summaries use the explicitly labeled modeled joint-timed-finisher subset.

Monte Carlo standard error for a win indicator is sqrt(sample_variance(indicator)/N), handling half-win ties correctly. It measures numerical sampling error only. Predictive margin percentiles are sample quantiles, not confidence intervals for the mean/probability. Do not print resolved-only headline percentages when trials are unresolved.

Named random streams must preserve trial identity across batch-size changes. Prefer SeedSequence-derived per-trial/per-purpose keys or a counter-based scheme. If a batched implementation cannot be invariant, pin its batch configuration in the numerical hash and state the limitation; do not silently change outputs under an identical key.

### G8.5 Exact browser request and response

Version 1 serves historical pre-race scenarios. Causal feature contracts prepare future live work, but a new live forecast UI/model is outside this implementation. Existing Forecast live output stays separate.

Wire request, under 2 KiB:

~~~json
{
  "schema_version": "ac75-scenario-request-1",
  "model_id": "<installed content ID>",
  "team_a": "ac37:ETNZ",
  "team_b": "ac37:INEOS",
  "course_id": "<installed course ID>",
  "environment": {
    "kind": "fixed_wind",
    "tws_kt": 11.5,
    "wind_from_deg": 105.0
  },
  "purpose": "standard",
  "scenario_policy_id": "ac37-observed-behavior-v1"
}
~~~

Model/course IDs must exist in the installed catalog. Purpose is preview, standard or evaluation; the browser may select preview/standard only. Counts are fixed by installed purpose configuration and the server selects seed 2027. Advanced arbitrary seeds/counts are CLI-only and included in the full numerical key. Browser requests do not contain weight changes, paths, arbitrary rules, simulation counts or seed overrides.

Convert knots to SI exactly once using 1 knot = 1852/3600 m/s; normalize direction modulo 360. Do not round numeric inputs for cache lookup. A supplied unsupported direction/wind/course returns unsupported; never select the nearest scenario. The UI may default direction to the course axis only as an explicitly displayed scenario assumption.

For example, adding a browser key "team_strength":100 is a 422 unknown_key error, not a way to change the fitted model.

Applied inputs include the normalized SI environment, original declared units, canonical IDs, all installed configuration hashes, purpose, seed and actual trial count. The immutable result has schema_version kinematic-race-sim-2, scenario_id, model_id, applied_inputs, availability, support, probability_scope, probabilities, timing, time_accounting, uncertainty, trial_counts and evidence_refs. Probability values/MC errors are nullable structured objects. Timestamps/request IDs belong in the audit envelope.

Use exact HTTP routes:

~~~text
GET  /api/kinematic/catalog
POST /api/kinematic/simulate
GET  /api/kinematic/jobs/<job_id>
~~~

Catalog response enumerates models/classes/courses/purposes/support policies, learned inference availability and explicitly optional legacy benchmark capability. No installed learned candidate means an unavailable learned workspace, not an automatic legacy fallback.

POST complete cache hit returns 200; POST queued/running returns 202; GET job returns 200 with its current state. Completed scenarios are INLINE summaries, avoiding a missing arbitrary-file-serving endpoint.

~~~json
{"status":"complete","request_id":"r","scenario":{"schema_version":"kinematic-race-sim-2"}}
{"status":"queued","request_id":"r","job_id":"j","model_id":"m"}
{"status":"running","request_id":"r","job_id":"j","model_id":"m"}
{"status":"failed","request_id":"r","job_id":"j","code":"worker_timeout","message":"Simulation did not finish. Please retry."}
~~~

The scenario object above is abbreviated only for illustrating the envelope; validators require every field defined by the real result schema. A completed job can contain an explicitly unavailable scientific scenario; that differs from an infrastructure-failed job.

### G8.6 Worker protocol and limits

New CLI command:

~~~text
python -u -m pipeline.kinematic_ml worker --model <installed_id> --config <installed_config_id>
~~~

One worker pins one installed model and never rediscovers latest during a job. Node launches with fixed arguments, shell disabled, windowsHide true, bounded environment and the known workspace. Core NumPy inference does not require importing Torch.

NDJSON stdout emits:

~~~text
{"type":"ready","model_id":"m","protocol":"ac75-worker-1"}
{"type":"progress","request_id":"r","stage":"simulating"}
{"type":"result","request_id":"r","model_id":"m","scenario":{...}}
{"type":"error","request_id":"r","code":"unsupported_request","message":"..."}
~~~

Stdin accepts only a validated normalized infer message with request_id/model_id, or shutdown. Logs go to stderr. Require the ready model-ID/protocol handshake before dispatch. Reject oversized/malformed messages and mismatched IDs.

Initial limits:

| Setting | Value |
|---|---:|
| Browser body | 2 KiB |
| Running jobs | 1 |
| Queued jobs | 4 |
| Retained finished jobs | 32 |
| Finished job TTL | 1,800 s |
| Worker startup timeout | 30 s |
| Inference job wall-clock timeout | 120 s |
| Graceful shutdown/kill grace | 3 s |
| Worker stdout message | 512 KiB |
| Retained worker stderr | 128 KiB |

Keep total HTTP summaries similarly bounded. A startup/job timeout marks the job failed and retires the worker. Restart lazily for a later new job; do not automatically retry the same expensive job forever. On Vite development/preview shutdown close the worker and timers. Capture warm inference latency/peak memory for standard purpose; if optimization is needed, preserve trials and semantics or explicitly choose preview.

Require loopback socket peer and allowed Host. Mutating browser POST requires exact same Origin; a missing Origin is rejected in this browser endpoint. Local programmatic work uses the Python CLI. Pin all IDs when accepting a job, so a candidate-pointer change cannot alter it.

### G8.7 Receipt schemas and gates

CLI receipt fields:

~~~json
{
  "schema_version": "ac75-command-receipt-1",
  "command": "train",
  "status": "complete",
  "reason_codes": [],
  "input_ids": {},
  "output_ids": {},
  "counts": {},
  "elapsed_s": 0.0,
  "log_path": "relative/path",
  "exit_code": 0
}
~~~

Actual values are mandatory; this is a shape example. Status complete_with_exclusions must list affected source IDs and reason codes. Infrastructure failure has nonzero exit code; a scientifically losing candidate can have successful command execution and a negative selection result.

Progress task records include dependencies, status, owning paths, input/output IDs, check receipts, blockers, next action and four distinct booleans:

- code_complete
- artifact_complete
- engineering_verified
- evaluation_complete

Only applicable dimensions can be marked complete; use applicability metadata for source/contract tasks. Verify referenced artifacts/hashes before resuming. Do not infer trained weights or scored performance merely from code_complete.

Final candidate metadata requires T15 even though T16 infrastructure can proceed earlier. Independent reviews of gates A-D should inspect contracts, diffs, artifact receipts and bounded examples. They must not substitute narrative confidence for checks.

### G8.8 Scope extensions after version 1

Only after the mandatory implementation is complete and evaluated:

- A small temporal network using causal history for a separately registered live target.
- Joint two-boat route/interaction policy, when observational evidence supports it.
- Time-varying weather scenarios with validated issuance and dependence.
- Day-bootstrap parameter ensembles calibrated jointly with residual uncertainty.
- Explicit AC40/AC75 or AC37/AC38 transfer with independent evidence.
- Reviewed hardware/crew covariates, if genuinely available.

These are subsequent experiments, not reasons to skip mandatory extraction, neural training, or honest evaluation now.


