# Forecast implementation

The Forecast view (key 5) has the three requested outputs: current on-water race-win probability, pre-race expected position with nonfinish scored N, and the 2027 America's Cup winner. Python produces the probabilities; the browser only selects validated, published artifacts.

## Run locally

Install the locked Python 3.12 environment once. The replay pipeline retains its existing standard-library imports. Core forecasting needs NumPy, SciPy and PyArrow; optional shallow ML packages are locked but not installed by this command. No model weights or external services are needed for verification.

```text
uv sync --locked --extra forecast-core
uv run --locked --extra forecast-core python -m pipeline.prediction dataset
uv run --locked --extra forecast-core python -m pipeline.prediction audit
uv run --locked --extra forecast-core python -m pipeline.prediction backtest
uv run --locked --extra forecast-core python -m pipeline.prediction backtest --include-audit
uv run --locked --extra forecast-core python -m pipeline.prediction build
uv run --locked --extra forecast-core python -m pipeline.prediction verify
powershell -ExecutionPolicy Bypass -File run.ps1 verify
```

`dataset` streams the raw archive and verifies source bytes before cache reuse. `.forecast/` holds ignored local Parquet tables, source evidence, fitting diagnostics, backtests and QA. `--race <id>` limits dataset conversion or a baseline build; a limited build publishes an index for that subset, so use the unrestricted build for the full dashboard.

An exact custom pre-race scenario is a separate artifact; it does not replace live or Cup output:

```text
uv run --locked --extra forecast-core python -m pipeline.prediction build --race naples_pr1 --tws-knots 12 --direction-offset-deg 0
```

Unsupported scenarios export null values and an explicit reason. Presets select exact values; arbitrary inputs never borrow the nearest forecast. Current direction changes require validated direction-response evidence. The conservative reference retains zero wind-response until a conditional alternative passes the release procedure. A generated scenario can consequently have the same expectation as the reference; it does not imply a measured weather effect.

## Evidence and the current release

The archive is AC40 telemetry. It has source gate times and reconstructed results, with no independently verified official finishing orders. A source `started=false`, missing track, reconstructed DNF, OCS or practice stop is not an audited exogenous failure. Official classification and on-water order are distinct targets. Later protest disqualifications do not automatically change the on-water target.

Unconditional win/place output requires an audited, complete scheduled-entry denominator. Until then it is null. Source-confirmed terminal outcomes can be deterministic only when the whole field's valid on-water order/nonfinish states are resolved; the first received finish does not establish that. The UI explains missing evidence instead of displaying a prior as measured reliability. Numeric availability never asserts calibration.

To add independent completion evidence, create `docs/forecast_completion_review.json` with schema `completion-review-1` and `races`: each item contains `race_id`, `evidence_ref`, `available_at_ms` and `entries`. Every scheduled asset must appear exactly once with `asset_id`, boolean `started`, boolean `completed`, and `failure_type` (`none`, `exogenous`, or `time_rule`). Unknown causes remain unresolved. Time-rule censoring without an approved exposure treatment prevents the pooled random-failure denominator from being used. Do not fill this file from the dashboard's reconstructed RET/DNF labels. Availability must reflect when the evidence was actually usable.

## Statistical implementation

`models.py` implements uniform and race-equal empirical references, regularized Plackett–Luce strength, a training-standardized conditional logit comparator, pooled audited Beta-Binomial completion, empirical leg-time regression and a gated positive-delay mixture fitter. Practice is excluded from competitive fitting. A completed interval remains a physical observation when its boat later retires. The first interval is gun-to-gate and already includes start loss; no second start delay is added.

The severe-performance-loss candidate jointly refits a clean lognormal component and a Bernoulli times positive Gamma delay in seconds. Reviewed clean/loss labels, identification checks, earlier dates and frozen held-out improvement are required. It is not activated by this archive. Ordinary manoeuvres remain in the fitted total-time baseline rather than being sampled again. There is no asserted touchdown/foil-height sensor or universal low-wind switch.

`simulation.py` generates joint complete orders and correlated positive gate times with one persistent crew-form factor, shared race/weather variation at each boat's simulated calendar time and boat innovations. Current remaining and future full legs share their generative prior. Reliability is conditioned on observed survival, DNS is excluded after a known start, and failure exposure uses a normalized constant/transition hazard. Timing limits are separate from exogenous failure. No future XY tracks or opponent arrivals become observed tactical information. Unvalidated tactical coefficients and serial innovation effects remain pooled to zero.

Both win chances and tied-N expectations come from one joint distribution. An internal no-finisher category preserves total mass. A fixed 0.0001 mixture with a legally valid uniform-order reference regularizes possible tails coherently; terminal impossibilities remain exact. Standard live builds use 20,000 draws and final pre-race/Cup scenarios use 100,000. The reported 95% Monte Carlo half-width concerns simulation noise only.

The published default is the conservative joint ranking reference. The correlated simulator and positive-loss mixture are candidates, not promoted merely because they run. Chronological backtests use the fixed development dates and a separately frozen September 26–27 descriptive audit. Scores average within race before race-equal/day-equal summaries. Small-sample guardrail budgets are operational rules, not confidence or noninferiority claims. Conditional-on-observed-finisher diagnostics are clearly separate from full-field win/place validation. A prospective frozen evaluation still requires new data.

## Causal source contract

Raw ordinal, original timestamp and modeled availability are retained. There is no true receipt clock, so the time basis is explicitly **event-time reconstruction with modeled latency**. The reorder buffer is 6 seconds. A 1 Hz bucket is consumable only once that second has closed; a later sample cannot rewrite a previously published subsecond checkpoint. Live checkpoints are every ten seconds plus source terminal-event checkpoints. Publication is state time plus six seconds. Pre-race observed conditions stop early enough to be available before the gun.

The constant-velocity Kalman filter only moves forward; COG means ground-course direction, not heading. Noise/process settings use earlier observations. Outage masks use earlier-date settings and nonoverlapping truth windows, with separate steady, turning, recovery-proxy and gate strata. Containment/count/date/normalized-error gates certify only a contiguous horizon prefix. No unsupported 60/90-second bridge is assumed. Predicted gate crossings do not confirm phase. Missing opponents stay in the field, and unresolved state suppresses the entire joint forecast.

Mark endpoints use fresh raw fixes with an explicit random-walk variance allowance in crossing uncertainty. Longer mark bridges have not been certified, so the current cap is two seconds, below the planned thirty-second engineering ceiling. Course changes are used only once known. Leg categories are odd/even course segments; the implementation does not assume that the first segment is always upwind. Source coordinate/mark/flag inconsistencies remain quality failures.

`weather.py` separates forecast issue, availability and valid time. Reanalysis is rejected as a historical forecast. No external weather archive has been silently substituted for the observed wind or an explicit scenario.

## Cup adapter

`cup.py` implements all seven entrants, six fleet races, distinct Challenger/overall carry schedules, up to three complete round robins, Challenger-only qualification, both repechages with initial points, observable semifinal opponent choice, and first-to-five/first-to-seven series. Fixed known scores and selections override simulation. Zero-score races do not impose an invented thirteen-race cap.

The downloaded official PDFs are pinned in [forecast_rules_sources.json](forecast_rules_sources.json). Direct checking corrected two details in the earlier plan: RRSAC 105.2 fleet scores are **10,9,8,7,6,5,4** for seven boats, and Conditions 5.2(b) overall fleet carry is **3,2.5,2,1.5,1,0.5,0**. Challenger carry remains **2.5,2,1.5,1,0.5,0**. Fleet ties have a rule 107 resolution. The six-Challenger seeding tie procedure and some timing/incomplete-series branches still need authoritative clarification; no equal weighting of possible rulings is invented.

The conditional engine supports persistent `rho * AC40_strength + AC75_effect` scenarios, population-prior Australia, match-concentration and hazard sensitivities. It can produce conservative outer bounds for unresolved paths. Synthetic complete tie rules exist only for engine fixtures and benchmarks. They are never enabled for the public Cup artifact. With no validated AC40-to-AC75 transfer/reliability/timing evidence and unresolved governing branches, the public Cup probability stays unavailable.

## Artifacts and verification

The wire schema is `prediction-1`; Cup is `cup-1`. The index points to immutable content-addressed race, Cup and provenance objects. All objects are written and verified before the index is atomically replaced, preserving the previous publication on failure. Actual source-manifest, model, race and Cup contents are checked against their hashes. The browser checks raw JSON body hashes too, along with complete field/class, status, probability mass, scenario and publication timestamps. Unavailable values are null; missing boats never become zero probability.

Vite excludes the generated forecast directory from file watching to avoid persistent Windows locks during publication. JSON is fetched on view/race selection; refresh an already open Forecast view after rebuilding data. Atomic writes use unique temporary files and bounded retries for transient readers, retaining the previous index on a permanent failure.

Forecast retains all 227 scheduled boat-races, including the three source entries absent from legacy replay telemetry (224 replayed boat-races). The index and each artifact bind the complete scheduled roster and exact replay subset separately. Source-only entrants remain visible in both probability tables and in the rank-N denominator; this does not create synthetic replay telemetry.

Model cards record source/code/lock hashes, training cutoffs, posterior completion, model parameters, outage certification and assumptions. Only active index race/Cup/index payload counts toward the 1.5 MiB target/3 MiB hard browser baseline budget; referenced model/provenance bytes and compressed race bytes are separately reported. Pre-race scenarios have a separate lazy-loaded budget. Builds refresh Reports automatically. Current downloads keep their specific labels, while retained immutable objects are explicitly labeled Forecast archive artifact so every public JSON remains discoverable for readers holding an older index.

Focused tests cover causality, prefix invariance, covariance, rank conventions, no-finisher mass, joint tails, start/full-leg boundary identity, shared dependence, seeded reproducibility, Cup format, fixed results, actual-byte tampering, transactional publication and scenario scope. Browser tests use explicitly synthetic routed fixtures for numeric states, then a separate real-archive smoke. `run.ps1 verify` runs the existing replay tests/build/integrity checks plus public forecast validation. Foundation models, neural networks and optional shallow ML comparisons remain the research phases defined in [the execution plan](probability_execution_plan.md), not release dependencies.
