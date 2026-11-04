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

### Generate from the dashboard

With the ordinary local server running (`npm.cmd run dev`), open Forecast, Before the start, select Enter wind conditions, and choose Generate forecast. Existing exact scenarios load immediately. New supported inputs run the existing Python pre-race exporter through `/api/forecast-scenarios`; no source edits or terminal command are required. Progress, retryable errors and exported availability reasons are displayed in the card. Editing inputs cancels that browser's polling and clears the old running state; it does not mislabel an old result as the new conditions.

The service requires the existing local `.forecast/dataset/index.json`, published prediction index, and Python environment. It is installed for Vite development and local preview. A static-only deployment can read existing scenarios but needs the local service to prepare new ones. Forecast JSON and the artifact catalog are read directly from the current public directory in both local modes, so new immutable publications are available without a frontend build.

The current model accepts only a zero direction offset: a course-relative direction response has not passed validation. A request such as 12 knots and 17° is explained before generation and the UI offers an explicit Use 0° offset action. Wind speed support still depends on earlier competitive race coverage. Numeric output remains the conservative zero-effect wind reference where supported; changing wind speed need not change expected positions. Live and Cup forecasts retain their separate targets and evidence gates.

The local endpoint accepts same-origin loopback requests, bounded JSON and catalog race IDs, then launches Python with fixed argument positions and no shell. One workspace lock protects publication across development and preview processes. The child PID is recorded before a startup handshake allows the exporter to run; a live owner or child keeps the lock. An abandoned lock is recovered only after both have exited. The child also owns a ten-minute watchdog. The existing scenario exporter validates and writes immutable objects before replacing the index, preserving all race/live and Cup references. Reports refreshes to include the new scenario and its model/provenance objects.

## Evidence and the current release

The raw archive comprises 28 raw sessions across 9 race days totaling 6,866,006,601 bytes (~6.87 GB / 6.39 GiB). Source gate times and reconstructed results are audited against the scheduled entry roster in `.forecast/scheduled_entry_ledger.json`.
- **Scheduled Field Denominator**: 227 scheduled boat-races.
- **Replay Telemetry Field**: 224 boat-races.
- **Telemetry-Free Entries**: Exactly 3 scheduled practice starts (`GBR B` in `26_09_22_nap_ipr_pr2`, `pr3`, and `pr4`) lack telemetry tracks but are fully tracked in the scheduled denominator and scored tied-N when unstarted/uncompleted.
- **Audited Non-Completions**: 4 competitive DNS (`GBR B` x2, `ITA G`, `FRA`), and 3 competitive started non-completions (`GBR G` unresolved in PR1, `SUI` DSQ in Race 4, `FRA` RET in Race 7).

A source `started=false`, missing track, reconstructed DNF, OCS or practice stop is not an audited exogenous failure. Official classification and on-water order are distinct targets. Later protest disqualifications do not automatically change the on-water target.

Unconditional win/place output requires an audited, complete scheduled-entry denominator. Until then it is null. Source-confirmed terminal outcomes can be deterministic only when the whole field's valid on-water order/nonfinish states are resolved; the first received finish does not establish that. The UI explains missing evidence instead of displaying a prior as measured reliability. Numeric availability never asserts calibration.

To add independent completion evidence, create `docs/forecast_completion_review.json` with schema `completion-review-1` and `races`: each item contains `race_id`, `evidence_ref`, `available_at_ms` and `entries`. Every scheduled asset must appear exactly once with `asset_id`, boolean `started`, boolean `completed`, and `failure_type` (`none`, `exogenous`, or `time_rule`). Unknown causes remain unresolved. Time-rule censoring without an approved exposure treatment prevents the pooled random-failure denominator from being used. Do not fill this file from the dashboard's reconstructed RET/DNF labels. Availability must reflect when the evidence was actually usable.

## Statistical implementation

`models.py` implements uniform and race-equal empirical references, regularized Plackett–Luce strength, a training-standardized conditional logit comparator, pooled audited Beta-Binomial completion, empirical leg-time regression and a gated positive-delay mixture fitter. Practice fleet sessions under official marks and timing are ingested with a discount weight ($w = 0.5$) for latent ability fitting, preventing 40% sample truncation while keeping competitive regatta titles distinct. Plackett–Luce latent skills use a calibrated empirical-Bayes prior ($\sigma = 1.2$) and discrimination scale ($\kappa = 1.8$) to align simulated order variance with empirical regatta finishing distributions, eliminating artificial rank compression in pre-race expected positions. A completed interval remains a physical observation when its boat later retires. The first interval is gun-to-gate and already includes start loss; no second start delay is added.

### Ranking Mathematics & Benchmark Invariants

1. **Estimand & Winner Assignment Invariant**:
   The on-water race winner is the fastest boat among valid finishers. If $M < N$ boats finish, the fastest finisher is awarded the win. An internal no-finisher state (`-1`) occurs if and only if **all** boats in the scheduled field fail to finish:
   $$\text{winners}[(\sim \text{isfinite}(\text{times})).\text{all}(\text{axis}=1)] = -1$$
   Checking `(~isfinite).any(axis=1)` is strictly prohibited as it erroneously nullifies competitive wins whenever any trailing boat DNFs.

2. **Tied-N Rank Sum Identity**:
   When all $M$ nonfinishers receive tied rank $N$ ($0 \le M \le N$), the realized rank sum of the field satisfies:
   $$\sum_{i=1}^N R_i = \frac{N(N+1)}{2} + \frac{M(M-1)}{2}$$
   - When $M = 0$ (all finish) or $M = 1$ (single nonfinisher), the rank sum is identically $\frac{N(N+1)}{2}$.
   - When $M \ge 2$, the rank sum strictly exceeds the standard permutation sum by exactly $\frac{M(M-1)}{2}$.

3. **Analytic Plackett–Luce Expected Rank Benchmark**:
   Under Plackett–Luce latent skills with weights $w_i = \exp(\theta_i)$ and independent completion probabilities $s_i \in [0, 1]$, the exact analytic expected rank is given by:
   $$\mathbb{E}[\text{rank}_i] = N(1 - s_i) + s_i \left( 1 + \sum_{j \ne i} s_j \frac{w_j}{w_i + w_j} \right)$$
   This deterministic formula is implemented in `analytic_plackett_luce_expected_ranks` as a closed-form unit benchmark against Monte Carlo sampling.

4. **Contrast Subspace Covariance**:
   In latent ability sampling (`sample_log_worth`), draws are centered on the zero-sum contrast hyperplane ($\theta \mapsto \theta - \frac{1}{N}\sum_k \theta_k$). This preserves all pairwise contrast variances $\mathrm{Var}(\theta_i - \theta_j) = \Sigma_{ii} + \Sigma_{jj} - 2\Sigma_{ij}$ while anchoring seen entries to zero mean relative to unseen entries.

### Candidate Ablation & Promotion Evidence

`simulation.py` generates joint complete orders and correlated positive gate times with one persistent crew-form factor, shared race/weather variation at each boat's simulated calendar time and boat innovations. Current remaining and future full legs share their generative prior. Reliability is conditioned on observed survival, DNS is excluded after a known start, and failure exposure uses a normalized constant/transition hazard. Timing limits are separate from exogenous failure. No future XY tracks or opponent arrivals become observed tactical information. Unvalidated tactical coefficients and serial innovation effects remain pooled to zero.

Chronological expanding-window ablations across development race days evaluated static Plackett–Luce and time-based correlation models:
- **Pre-Race Evaluations**:
  - `pl_kappa_18`: Race-equal Brier = 0.8580, LogLoss = 1.8704, NormMSE = 0.1444; Day-equal Brier = 0.8525, LogLoss = 1.8587, NormMSE = 0.1419.
  - `pl_kappa_10`: Race-equal Brier = 0.8184, LogLoss = 1.8107, NormMSE = 0.1366; Day-equal Brier = 0.8196, LogLoss = 1.8195, NormMSE = 0.1339.
  - `time_persistent_only`: Race-equal Brier = 0.8165, LogLoss = 1.7998, NormMSE = 0.1219; Day-equal Brier = 0.8404, LogLoss = 1.8543, NormMSE = 0.1225.
  - `time_shared_only`: Race-equal Brier = 0.8162, LogLoss = 1.8007, NormMSE = 0.1219; Day-equal Brier = 0.8402, LogLoss = 1.8556, NormMSE = 0.1225.
  - `time_combined`: Race-equal Brier = 0.8162, LogLoss = 1.8007, NormMSE = 0.1219; Day-equal Brier = 0.8402, LogLoss = 1.8556, NormMSE = 0.1225.
- **Live Checkpoint Evaluations**:
  - Static Plackett–Luce (`pl_kappa_18`): Race-equal Brier = 0.8387, LogLoss = 1.8340.
  - Correlated Time Simulation (`time_combined`): Race-equal Brier = 0.4534, LogLoss = 0.9158 (Day-equal Brier = 0.4450, LogLoss = 0.9024).
  - Time simulation achieves a ~45% reduction in Brier score and ~50% reduction in log-loss over static ranking by conditioning on physical on-water gate progress and Kalman tracking projections.
- **Promotion Status**: `correlated_mc` passed all development and descriptive audit gates and is selected for live Monte Carlo simulation. `PositiveDelayMixture` correctly remains `available=False` because the raw telemetry archive lacks reviewed clean/loss labels (requires 50 clean, 20 loss, 3 dates).

Both win chances and tied-N expectations come from one joint distribution. An internal no-finisher category preserves total mass. A fixed 0.0001 mixture with a legally valid uniform-order reference regularizes possible tails coherently; terminal impossibilities remain exact. Standard live builds use 20,000 draws and final pre-race scenarios use 100,000. Cup builds explicitly default to 5,000 draws per scenario; their published build budget records the actual draws and seed. The reported 95% Monte Carlo half-width concerns simulation noise only.

## Causal source contract

Raw ordinal, original timestamp and modeled availability are retained. There is no true receipt clock, so the time basis is explicitly **event-time reconstruction with modeled latency**. The reorder buffer is 6 seconds. A 1 Hz bucket is consumable only once that second has closed; a later sample cannot rewrite a previously published subsecond checkpoint. Live checkpoints are every ten seconds plus source terminal-event checkpoints. Publication is state time plus six seconds. Pre-race observed conditions stop early enough to be available before the gun.

The constant-velocity Kalman filter only moves forward; COG means ground-course direction, not heading. Noise/process settings use earlier observations. Outage masks use earlier-date settings and nonoverlapping truth windows, with separate steady, turning, recovery-proxy and gate strata. Containment/count/date/normalized-error gates certify only a contiguous horizon prefix. No unsupported 60/90-second bridge is assumed. Predicted gate crossings do not confirm phase. Missing opponents stay in the field, and unresolved state suppresses the entire joint forecast.

Mark endpoints use fresh raw fixes with an explicit random-walk variance allowance in crossing uncertainty. Longer mark bridges have not been certified, so the current cap is two seconds, below the planned thirty-second engineering ceiling. Course changes are used only once known. Leg categories are odd/even course segments; the implementation does not assume that the first segment is always upwind. Source coordinate/mark/flag inconsistencies remain quality failures.

`weather.py` separates forecast issue, availability and valid time. Reanalysis is rejected as a historical forecast. No external weather archive has been silently substituted for the observed wind or an explicit scenario.

The dashboard header's sea height and air/water temperatures are separately acquired historical model estimates through `pipeline.environment` ([environment data](environment_data.md)). They provide retrospective replay context and are not inputs to the causal probability model. The Forecast view keeps unavailable-publication diagnostics under “Why this is unavailable”. Available scenario artifacts expose their assumptions, counts and “Unresolved evidence” under “Scenario sensitivity and evidence”.

## Cup adapter

`cup.py` implements all seven entrants, six fleet races, distinct Challenger/overall carry schedules, up to three complete round robins, Challenger-only qualification, both repechages with initial points, observable semifinal opponent choice, and first-to-five/first-to-seven series. Fixed known scores and selections override simulation. Zero-score races do not impose an invented thirteen-race cap.

The downloaded official PDFs are pinned in [forecast_rules_sources.json](forecast_rules_sources.json). Direct checking corrected two details in the earlier plan: RRSAC 105.2 fleet scores are **10,9,8,7,6,5,4** for seven boats, and Conditions 5.2(b) overall fleet carry is **3,2.5,2,1.5,1,0.5,0**. Challenger carry remains **2.5,2,1.5,1,0.5,0**. Fleet ties have a rule 107 resolution. The six-Challenger seeding tie procedure and some timing/incomplete-series branches still need authoritative clarification; no equal weighting of possible rulings is invented.

### 2027 America's Cup Domain Assumptions & Series Transfer

1. **Class Architecture & Technical Assumptions**:
   - AC75 hull reuse: Strict one-new-hull rule for the 38th America's Cup (2027); competitors modify existing AC37 generation hulls.
   - Crew configuration: Reduced from 8 to 5 sailors.
   - Power generation: Human cyclors removed in favor of stored hydraulic/electrical energy battery systems.
2. **First-to-7 Match Series Dependence**:
   Team ability factors are sampled once per tournament trial and held persistent across all match races in a series. Independent per-race ability sampling changes the series win probability by averaging away persistent ability uncertainty (under a 50/50 mix of latent $p \in \{0.5, 0.9\}$, persistent draws yield $\approx 75.00\%$ series win probability, whereas independent draws yield $\approx 93.76\%$).
3. **Cross-Class Transfer Scaling**:
   In `cup.py`, `scenario.rho` represents a loading factor onto AC40 ranking effects, yielding realized cross-class correlation:
   $$\mathrm{Corr}(\theta_{\mathrm{ac40}}, \theta_{\mathrm{ac75}}) = \frac{\rho \cdot \sigma_{\mathrm{ac40}}}{\sqrt{\rho^2 \sigma_{\mathrm{ac40}}^2 + \sigma_{\mathrm{mult}}^2 \cdot \mathrm{scale}^2}}$$
   Without validated AC40-to-AC75 transfer, reliability, and timing evidence, public Cup probabilities remain unavailable (`null`), with conditional scenario analysis provided in Python.

## Artifacts and verification

The wire schema is `prediction-1`; Cup is `cup-1`. The index points to immutable content-addressed race, Cup and provenance objects. All objects are written and verified before the index is atomically replaced, preserving the previous publication on failure. Actual source-manifest, model, race and Cup contents are checked against their hashes. The browser checks raw JSON body hashes too, along with complete field/class, status, probability mass, scenario and publication timestamps. Unavailable values are null; missing boats never become zero probability.

Vite excludes the generated forecast directory from file watching to avoid persistent Windows locks during publication. A dedicated development middleware reads forecast JSON directly from the current public directory, including immutable files created after server startup; it does not depend on Vite's watcher-maintained public-file inventory. It preserves exact bytes for hash checks, closes file handles before responding, and returns JSON 404 errors for missing objects instead of the application HTML fallback. Production continues to use exported static JSON. JSON is fetched on view/race selection; refresh an already open Forecast view after rebuilding data. Atomic writes use unique temporary files and bounded retries for transient readers, retaining the previous index on a permanent failure.

Forecast retains all 227 scheduled boat-races, including the three source entries absent from legacy replay telemetry (224 replayed boat-races). The index and each artifact bind the complete scheduled roster and exact replay subset separately. Source-only entrants remain visible in both probability tables and in the rank-N denominator; this does not create synthetic replay telemetry.

Model cards record source/code/lock hashes, training cutoffs, posterior completion, model parameters, outage certification and assumptions. Only active index race/Cup/index payload counts toward the 1.5 MiB target/3 MiB hard browser baseline budget; referenced model/provenance bytes and compressed race bytes are separately reported. Pre-race scenarios have a separate lazy-loaded budget. Builds refresh Reports automatically. Current downloads keep their specific labels, while retained immutable objects are explicitly labeled Forecast archive artifact so every public JSON remains discoverable for readers holding an older index.

Focused tests cover causality, prefix invariance, covariance, rank conventions, no-finisher mass, joint tails, start/full-leg boundary identity, shared dependence, seeded reproducibility, Cup format, fixed results, actual-byte tampering, transactional publication and scenario scope. Browser tests use explicitly synthetic routed fixtures for numeric states, then a separate real-archive smoke. `run.ps1 verify` runs the existing replay tests/build/integrity checks plus public forecast validation. Foundation models, neural networks and optional shallow ML comparisons remain the research phases defined in [the execution plan](probability_execution_plan.md), not release dependencies.


## Cup scenario evidence and targeted publication

Usable `cup-ac38-conditional-2` exports require `scenario_analysis` schema `cup-scenarios-1` (legacy method 1 and explicitly unavailable method 2 remain compatible): baseline ID, nine assumption records, actual trials and seeds, model/cutoff/input lineage, observed-versus-missing team mapping, conditioning assumptions, resolved and unresolved counts, conservative bounds, simulation-error scope and endpoint scenario IDs. First-unresolved-stage counts are mutually exclusive; overlapping reason counts must not be added. Transfer loading is an assumption, not a measured AC40/AC75 correlation. A missing team estimate uses the population prior and remains distinguishable from an observed zero strength.

The mapping corrects the previous public path that gave an unobserved Australian entrant a numerical zero before missing-history detection. This is a model correction, so the new immutable Cup artifact can differ numerically. Baseline/selected-scenario intervals remain conservative: unresolved qualification paths are not assigned invented tie probabilities. A more informative feasible-path refinement requires authoritative tie-resolution evidence; narrower widths are not a release criterion.

A private, reproducible Cup candidate can be built from an already pinned strength model without rescanning telemetry:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from pipeline.prediction.build import build_cup_candidate; print(build_cup_candidate(Path.cwd(), trials=5000, seed=2027))"
```

Review `.forecast/cup_candidate.json`; the candidate helper does not update public data. `publish_cup_candidate` validates the pinned model, training cutoff, mapping and content before staging an immutable Cup object, verifying the staged index and atomically updating the public index/compatibility alias. Refresh the artifact inventory afterward. The model source manifest remains the model provenance; Cup records pin simulation input hashes and explicit generation assumptions.

Browser verification includes `node tests/browser/forecast.mjs --real`, which reads the active referenced Cup artifact and checks real scenario evidence rather than hardcoding an unavailable status.
