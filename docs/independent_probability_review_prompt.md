# Independent probability-model review and repair prompt

You are an independent reviewer with expertise in statistical forecasting, Bayesian inference, ranking models, stochastic simulation, machine learning, sailing dynamics and production software. Review the actual probability implementation in this repository, research suitable alternatives, and implement corrections you can substantiate.

This is an independent audit and repair task. You are not being asked to defend the existing plan, agree with the previous LLM, or find faults for their own sake. Treat documentation, comments, prior reviews and this prompt's orientation notes as claims to verify. Follow the code to the exported artifacts and rendered interface. Explain both the supporting evidence and the strongest objections to consequential choices.

You are explicitly authorized to change model choices, assumptions, features, priors, fitting, simulation, validation, availability gates, integration, tests and documentation when evidence supports a better approach. Prefer the simplest defensible solution. Do not preserve an incorrect implementation merely to keep existing tests green, and do not remove meaningful tests merely to obtain a pass. Make changes concrete and executable when you have repository access; otherwise provide exact proposed patches and state what you could not verify.

## 1. Product objective: exactly three user-facing outputs

The user wants:

1. **Live race-win probability:** for each boat at replay time t, the probability of being the first valid on-water finisher, given information actually available by t, conditions, position on the course, opponents and eligible history.
2. **Pre-race expected finishing position:** for each scheduled boat, its expected finishing position before the gun, given the opponents, historical relative strength and recorded or explicitly entered conditions. This is an expectation derived from an outcome distribution, not itself a probability.
3. **Whole-event win probability:** the probability of winning the named event after accounting for its actual format, scores, remaining races and dependencies. The current application's third card targets the **2027 America's Cup, raced in AC75s**, using an archive of **2026 AC40 sessions**. A 2026 preliminary regatta and the 2027 Cup are different targets. Verify that this target matches the code and intended product; do not silently substitute an easier event.

Write the estimands mathematically, including the information set, eligible field, race status, conditioning events and scoring convention. Distinguish first valid on-water finish from official classification after protests or later disqualifications. Ask a focused clarification only if an irreducible target ambiguity materially affects implementation; continue independent work meanwhile.

The existing expected-position convention assigns nonfinishers the scheduled field size N, so several boats may receive N. Check whether this is appropriate and explain alternatives before changing it. Under tied-N scoring, expected positions need not sum to N(N+1)/2. A boat can have the highest win probability and a worse expected position than another boat in a perfectly coherent joint distribution. Do not introduce either false constraint.

Keep exactly these three product outputs. Internal finish/nonfinish risks, rank distributions, latent states, no-valid-finisher mass and uncertainty diagnostics may be necessary. They do not authorize additional probability cards or a silent change to a conditional-on-finishing target.

## 2. Repository access and operating constraints

Repository root:

    C:\Workspace\Americas Cup\2D_regatta_replay

Read AGENTS.md if present, PROJECT.md and the relevant documentation before changing behavior. Inspect the current working tree and preserve existing changes. Do not reset unrelated work, upload data, push, deploy or delete the archive.

The raw archive contains 28 JSONL source files, approximately 6.87 GB. Exclude Data/, dist/, node_modules/ and .agents/teamwork/ from routine searches and prompts. Stream raw sources only for specific questions. Report counts, ranges, exclusions and a few bounded examples. Do not dump telemetry arrays or entire large artifacts into context.

Start with:

    python scripts/analysis_snapshot.py
    python scripts/analysis_snapshot.py --race naples_pr1

Use .venv\Scripts\python.exe if appropriate for the installed environment. Check available commands before using them. Existing local .forecast/ summaries and caches may save substantial time, but verify their identity and freshness before trusting them. Do not rebuild or rehash the entire archive reflexively.

For Windows Command Prompt instructions, use one command per line and the correct directory syntax:

    cd /d "C:\Workspace\Americas Cup\2D_regatta_replay"

Reuse installed dependencies. A running Vite process can lock Rolldown's native module on Windows, causing npm ci to fail and leave dependencies partly removed. Stop only this project's server before a necessary reinstall; do not kill unrelated Node processes.

If you lack repository access, say so immediately and request a bounded evidence bundle: PROJECT.md, the forecasting documents, selected implementation files, a compact active-artifact summary and relevant test excerpts. Do not imply that reading this prompt constitutes a code audit. Do not request the complete raw archive by default.

## 3. Reading map

Read in stages, following actual imports and call sites rather than loading everything at once.

**Specification and previous reasoning:**

- PROJECT.md
- docs/source_audit.md
- docs/probability_execution_plan.md
- docs/forecasting_review_resolution.md
- docs/forecasting_research_review.md
- docs/forecasting_implementation.md
- docs/forecast_rules_sources.json
- docs/environment_data.md
- The user's original critique, if available. A previously supplied copy was at C:\Users\alex9\.codex\attachments\241ee7ca-dd43-43f8-ab72-f5c681e74e75\Testo incollato.txt. Do not assume it remains accessible.

**Probability pipeline:**

- pipeline/prediction/source.py: source identity, ingestion, timestamps and caches.
- pipeline/prediction/labels.py: race orders, interval targets and completion reviews.
- pipeline/prediction/state.py: causal filtering, geometry and outage certification.
- pipeline/prediction/models.py: strengths, references, conditional logit, completion and leg-time/loss models.
- pipeline/prediction/simulation.py: race continuation, orders, survival, dependence and numerical error.
- pipeline/prediction/evaluation.py and backtest.py: scoring, temporal folds and promotion.
- pipeline/prediction/build.py: fitting, selection, scenarios and publication.
- pipeline/prediction/cup.py: event rules, tournament simulation and public Cup export.
- pipeline/prediction/weather.py and __main__.py: forecast-time contract and executable workflow.
- pipeline/prediction/contracts.py: validation, hashes and atomic publication.

**Consumer and historical context:**

- src/engine/predictionCatalog.ts and src/types/prediction.ts.
- src/components/dashboard/ForecastWorkspace.tsx.
- public/data/predictions/index.json, then only the race, model, Cup and provenance objects it actually references.
- pipeline/environment.py, src/engine/environment.ts and the relevant public/data/environment/ metadata.
- Relevant tests/unit/test_prediction_*.py, src/engine/predictionCatalog.test.ts, src/engine/forecastArtifactRouting.test.ts and tests/browser/forecast.mjs.
- run.ps1 and the dependency lockfiles.

Historical metric formulas are owned by pipeline/historical_analysis.py. Preserve replay compatibility and do not recreate historical statistics in TypeScript.

## 4. Orientation snapshot: verify independently

The following was observed on 16 October 2026. It is a starting point, not evidence that the choices are correct or that a later checkout is unchanged:

- 28 AC40 source sessions; 227 scheduled boat-races versus 224 boat-races with replay telemetry.
- Local audit: 10 practice sessions, 23 usable source-started finisher orders and 1,061 valid gate intervals; zero independently verified official orders and zero audited completion records.
- The active archive had 4,069 live checkpoints: 1,963 gate_ambiguous, 1,992 unavailable and 114 estimated. All 28 pre-race estimates were unavailable.
- All eight referenced model cards selected joint_pl_reference. Correlated Monte Carlo code existed but had not passed promotion.
- The public Cup artifact was unavailable. The normal build called public_cup_artifact without mapped strengths; that function returned unavailable even when arguments were supplied. A separate conditional tournament engine existed.
- Historical environmental APIs had been connected for header context across all 28 races. Those retrospective hourly model estimates were deliberately separate from weather forecasts available before a race and from probability-model inputs.
- The interface's global experimental-estimate banner had been removed at the user's request. Technical Cup diagnostics were collapsed under an explanation. Neither cosmetic change establishes statistical validity.

Produce a capability matrix distinguishing **specified, implemented, connected, fitted, evaluated, selected, exported, displayed and empirically supported**. These are separate claims. Count usable forecasts before outcomes become known, not merely terminal results, valid JSON objects or passing tests.

## 5. Audit questions

### A. Targets, labels, identity and effective sample size

Reconcile source entries, replay entries, teams, A/B crews, asset IDs and their effective-time mappings. Do not merge distinct crews without a model or discard boats lacking telemetry. Determine which unit is being predicted and which unit shares historical strength.

Audit practice versus competition, source flags versus geometry, reconstructed results versus independent evidence, DNS/DNF/RET/OCS/DSQ, censoring, shortened races and ambiguous completion. Distinguish recording failure from actual retirement. Include scheduled entries in the correct denominator.

Evaluate label fitness for the actual on-water estimand. Independent official classification is valuable but is not automatically the only possible ground truth for a first-on-water target. Conversely, telemetry-derived order is not automatically verified truth. Establish what can be supported, reviewed, bounded or estimated under explicit assumptions.

Count independent races, dates, crews and conditions. Millions of correlated frames are not millions of independent outcome labels. Examine label uncertainty, selection effects and exclusion coverage.

### B. Causality and time availability

Trace source event time, original order, modeled receipt/availability, closed buckets, state time and publication time. Inspect the six-second modeled reorder buffer, out-of-order messages and the distinction between real receipt clocks and event-time reconstruction.

Test that modifying or deleting future telemetry, course changes, statuses, wind, final results or final metadata cannot change earlier predictions. Inspect corrections arriving late, last-observation holds, backward smoothing, interpolation, feature scaling and training cutoffs. All fitted preprocessing must use only eligible training history.

Check source-prefix equivalence, race/day boundaries and the gun-time display. An estimate appearing only after a terminal outcome is not useful pre-outcome forecasting. Retrospective reanalysis, modelled header temperatures and realised future wind must not be passed off as information known at the historical prediction cutoff.

### C. Generative model and mathematical coherence

Reconstruct the actual fitted model and how an observation changes its conditional distribution. Explain whether Monte Carlo is integrating a learned model, a hand-set stochastic model or a mixture. More simulation draws reduce numerical error; they do not establish model accuracy.

Audit ranking likelihoods, identifiability, regularization, pooling, recency, unseen entrants, changing crews and field-size effects. Determine whether weather, course position, velocity, opponents, geometry and remaining distance actually influence the published outputs.

Audit positive leg/finish times, leg-specific lengths, start-loss accounting, current-leg versus future-leg conditioning, manoeuvres, severe performance losses, wind sensitivity, finish constraints and near-finish behavior. Verify dimensions and avoid counting the same uncertainty or delay twice.

Separate exogenous failure, DNS, time-limit censoring and severe but recoverable performance loss. Condition correctly on survival and confirmed starts. Examine whether sparse failure data justify pooled priors, hierarchical shrinkage, sensitivity bounds, conditional estimates or abstention. Challenge overly restrictive availability gates as well as unsupported availability. Do not silently assume all boats finish to make numbers appear.

Generate race-win and expected-position outputs from compatible joint outcomes. Check total mass including no valid finisher, legal impossibilities, ties, nonfinish scores and terminal constraints. Any numerical tail regularizer must preserve impossible events and have a justified scale.

Examine shared weather, persistent ability/form, opponent dependence and temporal dependence. Common factors may cancel in relative rankings or create misleading certainty. Distinguish physical dependence from dependence caused by shared uncertain parameters.

Separate race randomness, state uncertainty, parameter uncertainty, structural uncertainty, class-transfer assumptions and Monte Carlo sampling error. A reported numerical half-width is not automatically a calibrated predictive interval. Check the estimator used to compute it, including any analytic marginalization or weighted mixtures.

### D. Focused implementation leads, not predetermined verdicts

Independently verify these suspected weak points and reject any that do not survive inspection:

- Whether current condition scenarios pass wind into a model whose fitted wind response is fixed at zero, while direction only controls support eligibility.
- Whether a fixed diffusion-inspired live lead adjustment, including its coefficient and remaining-distance scaling, behaves sensibly and outperforms simple alternatives.
- Whether covariance factors estimated from in-sample leg-time residuals, fixed shrinkage/caps and the shared weather construction are identifiable or calibrated with this archive.
- Whether point-estimated strength/time coefficients remain fixed across draws, understating parameter uncertainty.
- Whether conditional-logit and positive-delay candidates are merely defined rather than connected to fitting, comparison and publication.
- Whether backtesting substitutes a reference when the nominal candidate is unavailable, obscuring candidate coverage or performance.
- Whether frozen-audit flags have actual dated configuration/commit evidence, and whether earlier model selection already used those outcomes.
- Whether the Cup public path remains unavailable because of unfinished plumbing in addition to legitimate evidence limitations.

Do not accept these as findings without code or experiment evidence. Do not reject every heuristic merely because it is heuristic; compare performance, sensitivity and complexity.

### E. Independent research and model comparison

Search academic papers, official model documentation and relevant primary sporting/forecasting research. Recheck citations in existing documents. Cite direct links, publication/version dates where material, the relevant result and its applicability limits. Clearly distinguish a paper's finding from an inference for this archive. Do not fabricate references or use popularity as performance evidence.

Compare proportionately: uniform/empirical references; Bradley–Terry/Plackett–Luce and conditional/mixed logit; Bayesian hierarchical or dynamic strength; survival/competing-risk and empirical leg-time models; joint Monte Carlo; regularized supervised learning/boosted trees; unsupervised regimes or hidden-state models; sequence neural networks; and Google's TimesFM or other time-series foundation models when relevant.

For TimesFM, determine the exact version, task, covariate/multivariate support, sampling and uncertainty capabilities from primary documentation. Specify what it would forecast, how that would translate into coherent joint finishing outcomes, and whether the archive can test it fairly. Inspect pretrained-data overlap/cutoff risks. A good speed forecast or plausible trajectory does not establish a good race-win forecast.

For every serious candidate, state its estimand/likelihood, required labels, data sufficiency, leakage risks, uncertainty treatment, dependence assumptions, computational cost and decisive comparison. Unsupervised regimes are potential features, not automatically winner labels. Fit representations and clusters inside training folds.

Do not implement every technique. Select a modest shortlist against credible simple baselines. Retaining a simple model is acceptable; unmeasured sophistication and untested dismissal are not.

### F. Validation and selection

Use chronological, race-grouped evaluation, preferably with date grouping where appropriate. Reconstruct actual information availability. No random frame split, future-trained normalization or calibration on the evaluation set.

The existing plan names development assessment dates May 23, May 24 and September 25, and a descriptive audit on September 26–27, 2026. Verify eligibility and actual gun dates rather than filenames. If those audit outcomes have already informed design, do not relabel them as an untouched holdout after another round of tuning. Document exposure and specify a future frozen evaluation.

Use proper scoring for the actual target: winner log loss and Brier, full-rank/RPS where meaningful, and expected-position error with its denominator and nonfinish convention. Inspect the implementation of each score. Report race-equal and day-equal results, coverage, exclusions, fallback rates, field size, progress bands and simpler-model comparisons.

Conditional-on-observed-finisher diagnostics must not be presented as unconditional live win validation. Missing candidate forecasts must not disappear from comparisons without a stated policy. Source-derived labels, synthetic fixtures and official outcomes require separate reporting.

Assess calibration only with a defensible sample. Use dependence-aware uncertainty and sensitivity; many within-race checkpoints do not increase the number of independent race days. Explain small-sample limits without equating absence of statistical significance with equivalence. Operational promotion budgets are not automatically statistical noninferiority evidence.

Predefine tuning and promotion decisions. Include ablations for current position, historical strength, weather response, completion risk and shared dependence when estimable. Report actionable forecast coverage before the result is known. Do not tune and then call the same historical audit independent validation.

### G. Whole-event/Cup correctness

Research authoritative rules, amendments, entrants, effective dates, schedules and scoring for the exact edition. Trace each implemented branch to the applicable document/version and distinguish document publication date, applicability and information availability. Never invent missing dates.

Verify fleet and Challenger scoring, carry-over, ties, qualification, repechages, semifinal selection, series win conditions, no-score/shared-score races, withdrawals, incomplete series and continuation. Investigate whether an apparent ambiguity can actually be resolved from the official text rather than preserving it indefinitely.

Simulate the event through legal state transitions. Do not multiply unconditional race-win marginals or assume future races independent. Carry persistent strength and transfer uncertainty through a tournament trajectory, allow genuine learning/results to update later stages, and respect known scores and observable opponent-selection policies. Never give a simulated team access to hidden true latent ability for its selection decision.

Posterior predictive dependence can be represented through shared latent draws; it does not require arbitrary refitting after each simulated race. If modeling a team's learning or adaptive policy, update only its beliefs from observable simulated results. Avoid redrawing persistent true ability or double-conditioning on the same evidence.

Audit AC40-to-AC75 transfer and mapping from crews to teams, including entrants without observations. A scenario under explicit assumptions is different from an empirically calibrated unconditional trophy probability. Rule bounds, sensitivity ranges, posterior uncertainty and calibrated intervals are different objects. Do not average unresolved rule branches with invented probabilities.

If the ordinary export cannot consume reviewed strengths/rules or never calls the simulator, identify and repair that integration where supportable. If an unconditional Cup estimate remains unsupported, deliver the working conditional engine, precise remaining blockers and evidence needed. Do not describe an always-null export as a complete implemented forecasting product.

### H. Artifacts and interface

Check that current artifacts correspond to the model/code/data being reviewed, including source bytes, lockfiles, training cutoffs, model selection, scenario identity, complete field, class and units. A producer commit and the current dirty working tree are not automatically the same model version.

Verify atomic publication, byte/hash checks, cache invalidation, browser publication-time selection, backward seeking and stale-state suppression. Missing entrants must not become zero probability. Exact custom conditions must not silently borrow the nearest artifact.

Test actual HTTP responses and the rendered page. Vite previously returned application HTML for immutable JSON created after startup because that directory was excluded from its public-file watcher. The scoped generated-JSON middleware must serve new objects immediately, preserve hashes and avoid Windows publication locks. Do not weaken JSON validation to hide routing bugs.

Preserve the user's removal of the global experimental-estimate banner. Keep concise, truthful statuses and expandable technical detail. Do not treat cosmetic removal as evidence of calibration, or reintroduce a prominent warning banner merely as a substitute for fixing the model.

## 6. Execution and verification

First record the checkout, active artifact identities and a concise baseline of capabilities, evidence and failures. Then prioritize correctness, useful supported coverage and missing integration before optional model complexity.

For each substantive change: give the observed failure, causal explanation, mathematical or empirical justification, affected estimand, minimal correction and a test that would fail beforehand. Add meaningful tests for leakage, field/status edge cases, units, mass, boundary behavior, genuine model selection and artifact delivery. Synthetic tests establish implementation properties, not predictive calibration.

Work in stages: source contract, statistical/pipeline changes, regenerated artifacts where needed, consumer/UI, focused checks, complete verification. Rebuild only what the change requires. A limited baseline build with --race replaces the public index with that subset; do not accidentally remove the rest of the dashboard's races. Preserve or restore the full publication after experiments.

Available commands include:

    python -m pipeline.prediction audit
    python -m pipeline.prediction backtest
    python -m pipeline.prediction backtest --include-audit
    python -m pipeline.prediction build
    python -m pipeline.prediction verify
    python -m pipeline.environment --verify
    npm test
    npm run build
    powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1 verify
    node tests/browser/forecast.mjs --real

These are a menu, not an instruction to rerun every expensive operation blindly. Inspect dependencies, cache freshness and test scope. Use local interpreters where needed. Unit tests and ordinary verification must not silently download model weights or depend on live API calls. If a check cannot run, state the exact limitation; never report it as passed.

## 7. Required deliverables

1. A plain-language verdict for each of the three requested outputs, distinguishing useful working forecasts, provisional assumptions, disconnected code and unsupported claims.
2. The capability matrix and a compact data/label/forecast-coverage inventory, independently reproduced.
3. A prioritized findings table: severity, concrete file/function, evidence, effect on results, proposed fix and validation. Separate confirmed defects, modeling risks, data limits and optional research.
4. Corrected mathematics and a concise end-to-end explanation from available observations to joint outcomes to all three outputs. List parameters and identify which are fitted, fixed, posterior-sampled or unsupported.
5. A source-linked research comparison with justified model choices, including a specific TimesFM verdict. Report evidence against your preferred approach too.
6. Implemented, reviewable patches with appropriate artifact/documentation updates and exact test/experiment results. If editing is impossible, provide a precise patch plan and state that no implementation was performed.
7. An evaluation report with proper scores, baselines, temporal splits, fallback/abstention coverage, limitations and reproducibility details. If no defensible empirical comparison is possible, say so and distinguish that from software verification.
8. A concrete remaining execution plan with dependencies and acceptance criteria. Identify what can be fixed in code now versus what requires labels, official clarification, future observations or user input. Do not invent accuracy percentages, validated intervals or event-win numbers to make the project appear finished.

Begin with an independent reconstruction of the current implementation. Challenge the previous LLM and this prompt when warranted. Preserve what is supported, replace what is wrong, and carry justified changes through verification rather than stopping at an architectural proposal.
