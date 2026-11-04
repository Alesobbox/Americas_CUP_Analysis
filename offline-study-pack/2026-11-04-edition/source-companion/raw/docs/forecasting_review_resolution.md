# Resolution of the full forecasting-plan review

15 October 2026. Applies to execution-plan revision 2. This is a point-by-point response and a binding mathematical/engineering annex to [the revised plan](probability_execution_plan.md). It resolves the complete pasted review, including its six-item summary. It does not claim the proposed models, gap bridges or payload budgets have been implemented or validated.

The review correctly identified an overlarge initial delivery scope, fragile missing-data rules, incomplete infrastructure governance and an insufficiently tested residual distribution. Some mathematical claims and numeric thresholds require correction rather than literal adoption. Reviewer credentials, praise and suggested constants are not independent evidence.

## Point-by-point disposition

| ID | Review point | Resolution and implementation location |
| --- | --- | --- |
| C01 | Preserve causal raw-timestamp ingestion, reviewed truth, and explicit class transfer | **Accept.** Keep P1/P2/P8 evidence boundaries and prefix tests. Estimation must never become measured data or an official result. |
| C02 | Tied-N breaks rank-sum conservation; switch to mid-rank or add finish probability | **Modify.** Tied-N intentionally defines the user's penalized last-place score; it is not bias relative to that estimand. Keep it, label it, show mid-rank impact in the audit, and do not add a fourth user-facing probability. See section F. |
| C03 | Static custom-build workflow is too awkward | **Accept with bounds.** P9 adds supported pre-race presets at 8/12/16/20 knots and -15/0/+15-degree course-relative wind offsets. Exact preset selection is immediate; no silent nearest-value substitution or probability interpolation. Arbitrary compass quadrants on a fixed windward course are inappropriate. Custom/live/Cup scenarios remain explicitly scoped and cached. |
| C04 | No Git means immutable provenance is impossible | **Accept Git governance; correct the absolute claim.** P0 requires a local source baseline and clean release commit, alongside source-byte, lock and data hashes. Hash-addressed experiments are possible without Git; Git alone also misses uncommitted code and ignored model/data bytes. No Git initialization, commit or upload is performed by this plan revision. |
| C05 | Static config/asset IDs can misidentify changing crews | **Accept with current-code correction.** Ingestion already overrides names from session metadata, but first indexes the static catalog. P1 introduces one audited effective-time resolver and explicit unknown-ID handling, preserving legacy fixtures. Static unit constants remain valid. |
| C06 | AGENTS.md still describes only 441 MiB | **Accept and fix now.** Guidance now states 28 files, 6,866,006,601 bytes, and identifies 441 MiB as the original subset. Raw telemetry was not reprinted or re-audited. |
| C07 | Empirical next-gate simulation is preferable to an unsupported full VPP | **Accept.** P5 remains an empirical event/leg simulator. No hidden physical polar, foil-height sensor or optimal tactical policy is invented. |
| C08 | One coherent distribution should prevent highest win chance/worse expected position | **Accept coherence; reject that implication.** Both orderings can legitimately differ in one joint distribution. Add the exact counterexample in F to prevent an incorrect test. Coherence means common outcome draws, statuses and definitions. |
| C09 | Dependency isolation needs pyproject/locks and concrete verification | **Accept.** P0 specifies empty base dependencies, locked forecast-core, optional shallow ML and separately isolated sequence research. Ordinary verification runs frozen fixtures without Torch, live APIs or checkpoint downloads. The inspected interpreter is Python 3.12.14; project runtime imports and available bundled libraries are different facts. |
| C10 | Practice peel-offs contaminate residual scale/tails | **Accept; avoid a biased hard filter.** Practice is excluded from competitive variance, jump, failure and start distributions by default. Only reviewed windows may inform the mean, with a separate practice scale and competitive-only ablation. Low SOG triggers review; it cannot distinguish a deliberate stop from legitimate light-air or severe-loss behavior. |
| C11 | Geometry should override false source starts | **Modify.** A validated legal bow crossing supports a separate derived on-water start, while preserving the raw false flag. Check marks, uncertainty, class offset, gun/window, direction and corrected OCS. Do not override definitive rule evidence or use later gates before their availability. |
| C12 | The two-second/all-boats rule will black out forecasts; use Kalman/mark hold | **Accept the architecture, correct the math and fixed horizons.** Two seconds labels freshness. A supplies full covariance propagation and masked-gap certification; mark motion has its own uncertainty. Thirty/sixty/ninety seconds are tested ceilings, not safe defaults. An unresolved boat stays in the field; unresolved gate/finish state may still justify unavailable output. |
| C13 | Add wind-relative geometry and the supplied sailing-distance expression | **Accept features; reject the expression as a route formula.** Along/cross-wind, endpoints and gate width are useful. The proposed 145-degree version can return a negative distance; even the upwind expression does not define feasibility outside the fixed-heading cone. No universal 42/145-degree polar is established. See B. |
| C14 | Three noisy guardrails and delete-one-day veto have little power | **Accept.** P3 replaces exact nondegradation with frozen practical loss budgets, distinguishes live-only from pre-race changes and reports sensitivity rather than treating every day deletion as a veto. This does not manufacture power. A 0.5-bootstrap-SE margin from three dates is not evidence of noninferiority. |
| C15 | Expand rolling-origin scoring and show race-equal weights | **Accept.** Evaluate each competitive race chronologically with a model frozen on earlier days; show both race- and day-equal loss summaries. Intra-day updating is a separate ablation with verified result availability. More race rows do not create more independent days. The locked dates remain locked. |
| C16 | Inverse-square-root remaining-distance lead scaling | **Accept as a strong fixed benchmark feature, not a universal law.** P4 adds a bounded dimensionless diffusion-inspired feature and a raw-lead ablation. Brownian models motivate inverse square root of remaining time under assumptions; sailing noise, speed and first-passage boundaries need testing. |
| C17 | Hazard is higher near starts/roundings; elapsed=0 must not mean instant finish | **Accept the sensitivity and sentinel check.** D defines normalized phase-weighted hazard with the same total risk. Six raw retirements do not establish phase coefficients. Legacy zero elapsed requires terminal status/valid crossing validation, never time-based winning. |
| C18 | A single smooth lognormal misses touchdown/jump behavior | **Accept a pooled positive-delay candidate, qualify the physics.** C defines a dimensionally valid mixture and joint-fit/identification checks. Current sensors cannot prove a foil state. No fixed 9-knot change point, 11-knot classifier or 25–60-second delay is assumed. Retrospective detector outputs are labels only; live features are causal. |
| C19 | Gate switching can create artificial variance sawteeth | **Accept zero-new-information consistency; reject forced equality after information arrives.** P5 shares the leg prior/latent pace and tests the no-information boundary across mean, variance, mixture and tails. Real rounding/entry-speed observations may legitimately change probabilities. Do not hide those updates through smoothing. |
| C20 | P6/P7 cost is disproportionate; use simple kinematic features | **Accept MVP reduction.** Keep optional shallow CatBoost; defer SVR/HMM/foundation/GRU/TCN work. Add continuous SOG, acceleration, turn/recovery and wind-shift features first. The review's 95%-redundancy claim is unmeasured, so Phase 2 requires incremental-value evidence rather than assuming redundancy or superiority. |
| C21 | Match-race dominance needs a 2–3x concentration adjustment | **Accept a separate sensitivity; reject the asserted empirical ratio.** P8 adds concentration c in {1,2,3} to match logits while leaving fleet concentration fixed. This tests transient match noise separately from persistent AC75 capability. It is not a fitted AC75 result. Generated scenario subsets are listed exactly. |
| C22 | Semifinal selection must learn from that trajectory's round robins | **Accept.** Use public simulated Challenger round-robin win fraction, with deterministic observable policy tie-breaks. Never inspect hidden ability. A future Bayesian option must use a binary/multiplayer likelihood; normal-normal conjugacy is not automatically valid for binary wins. |
| C23 | Repeated metadata will bloat artifacts; use columnar arrays | **Accept.** E specifies one header/pre-race block and parallel live columns, preserving time-varying quality. Target 1.5 MiB and hard 3 MiB uncompressed for the baseline archive; measure rather than claim attainment. Lazy custom bundles are separate. |
| C24 | Key 5 should open Forecast | **Accept.** P9 specifies key 5, preserves keys 1–4, and tests typing/modal/focus guards. |
| C25 | Draft the exact gap/mixture/promotion spec before execution | **Accept.** Annexes A–F and revised P3 provide the concrete rules. These remain executable-work specifications, not implemented model claims. |

### Review's six priority actions

1. Infrastructure/locks/source-size guidance: C04/C06/C09 → P0; only the factual guidance correction is executed now.
2. Gap bridging: C12 → P2 and A, with validation rather than unconditional long extrapolation.
3. Severe-loss mixture: C18 → P5 and C, with corrected units and identification.
4. Lead scaling/gate consistency: C16/C19 → P4/P5, retaining appropriate uncertainty and information updates.
5. Observable semifinal selection: C22 → P8.
6. Scope reduction: C20 → explicit MVP P0–P5/P8–P9; research follows later.

## A. Causal state estimation and missing-data certification

### A1. State and propagation

Use state `s=(x,y,vx,vy)` in metres and m/s. COG, not boat heading, defines the measured ground-velocity direction. For elapsed time dt, use the continuous-white-acceleration constant-velocity model:

```text
F(dt) = [[I, dt I], [0, I]]
Q(dt) = q [[dt^3/3 I, dt^2/2 I], [dt^2/2 I, dt I]]
m_minus = F m
P_minus = F P F' + Q
```

Here q is acceleration spectral density, not the variance of a position random walk. Position uncertainty includes propagated velocity uncertainty and cubic process-noise growth. The review's `sigma_position^2 = sigma0^2 + q*dt` is appropriate for a different position-random-walk model; it is not this filter's covariance equation.

Update position/ground velocity only when their timestamped measurements are available. Estimate positive measurement/process scales from earlier source innovations, distinguishing steady/turning windows by causal turn-rate summaries. Use robust fitting and nonzero covariance floors; no fabricated zero GPS error. Keep source event time, filter update/publication time and replay watermark separate. Never run a backward smoother into the prediction cutoff.

During missing measurements, sample `(x,y,vx,vy)` from its filtered predictive distribution once per race continuation. Do not also add the same state covariance as independent time-noise. Label quality `measured`, `estimated`, `gate_ambiguous` or `unavailable` and export source age. Filtered state is a modeling assumption, not a new measurement.

### A2. Certification and stopping rules

Create disjoint artificial gaps of 2/5/10/20/30/60/90 seconds within otherwise well-covered earlier races. Test position-only loss and loss of both position/velocity; stratify steady motion, turns, recovery and gate approaches. Use held-out source positions only as scoring targets. Keep all tuning inside past data.

Preregister the following engineering gates: at least 50 nonoverlapping masks and two earlier dates for a certified stratum; at least 90% empirical containment by the claimed 95% position ellipse; median position error below 10% of leg length; and current 95% major radius at most min(50 metres, 10% of leg length). These thresholds are risk policies, not confidence guarantees. Report counts and containment by date/stratum, rejection/availability rates and natural-gap error. A mask failing a phase test is not removed to improve calibration scores.

Choose the largest contiguous tested duration prefix passing the gates. No certification beyond 90 seconds. Early folds without enough evidence use the declared reference procedure; they do not borrow later dates. Inspect the 74.6-second natural dropout separately: it may remain unavailable. A long extrapolation is never justified merely because its mean looks plausible.

Do not confirm legal starts/gates from propagation alone. If predictive state permits different gate/finish histories, export that ambiguity. The MVP declines a numeric live forecast when the field's necessary phase cannot be resolved; the competitor remains registered. A broad history-conditioned missing-state mixture is Phase 2 and requires its own masked-gap end-to-end validation. This replaces common short-gap blackouts without pretending every outage is recoverable.

### A3. Marks and outcome certainty

Marks have a separate slow-position random walk: hold the last causal mean and grow covariance as `P_mark + Q_mark*dt`, with Q fitted from earlier movement. A 30-second ceiling is reduced if masked-mark tests fail. A relocation/course revision invalidates the old hold. Sample endpoint uncertainty when computing line/gate geometry. A target/configured position is labelled configured, not measured.

If a gate/finish is observed, resolve its event time before its publication time. The first received finish message is not necessarily the first on-water finisher. A terminal 100% value requires the global on-water ordering to be resolved, including any missing opponent. This prevents state estimation from manufacturing a winner.

Primary background: [Sinopoli et al., Kalman filtering with intermittent observations](https://people.eecs.berkeley.edu/~jordan/papers/sinopoli-etal.pdf). Its linear/Gaussian setting supports the propagation principle, not a claim that a CV model predicts unseen tacks accurately. Different process-noise conventions must not be mixed; see [motion-model conventions](https://www.mathworks.com/help/fusion/ug/motion-model-state-and-process-noise.html).

## B. Geometry and live kinematic features

Let the vector from the boat to a gate point be d, the unit upwind axis from the causal circular TWD be e, and its perpendicular be e_perp. Use `a=d dot e`, `b=d dot e_perp`, distances to both endpoints, gate width/angular width and current tack as empirical features. Reverse the progress axis for downwind legs. Flag weak/variable wind direction rather than normalizing an unstable vector without warning.

The review's distance expression is not adopted. At a=100 m, b=0 and theta=145 degrees, it gives approximately -52 m. Downwind angles require a different axis convention. Even for 0<theta<90 degrees, two fixed allowed headings +/-theta require `abs(b)<=a*tan(theta)` and imply total length `a/cos(theta)` inside that cone; outside it, the same fixed-heading model is infeasible. Adding an unscaled crosswind remainder does not establish a new feasible route. Without a supported empirical speed/angle model, export geometric features, not an asserted layline distance.

Causal features include SOG, a trailing 10-second acceleration slope, circular turn rate, time since a detected past turn, and speed relative to earlier steady-window speed. Wind shift is the wrapped difference between 30- and 120-second circular means. A signed header/lift interpretation additionally needs tack and leg context. Values such as 12 seconds, 0.85 speed ratio and 11 knots may be review heuristics, never evidence of foil height. The existing manoeuvre detector's future stability/recovery windows may create training labels only after availability; they cannot supply live flags directly.

For the ranking benchmark, test `lead_fraction/sqrt(max(remaining_fraction,0.01))` against raw lead. Brownian score models motivate a denominator proportional to sqrt(remaining time) under drift/noise assumptions; distance is an approximation. Do not infer universal sailing physics or infinite certainty from this feature. [Stern's Brownian sports-score model](https://www.stat.berkeley.edu/~aldous/157/Papers/stern.pdf) is an analogue, not AC40 validation.

## C. Positive-delay mixture and gate consistency

### C1. Units, interpretation and fitting

Use the two-component candidate:

```text
T_clean ~ LogNormal(mu(context, crew), sigma_clean^2)
Z ~ Bernoulli(pi(context))
delay | Z=1 ~ Gamma(shape, scale_seconds)
T = T_clean + Z*delay
```

All durations/delays are seconds. If a multiplicative log-time mixture is tested instead, its jump must be dimensionless. Do not add a 25-second term to log(T). Z means one or more severe performance-loss episodes aggregated for that leg; it is not an observed foil-state label. A recovered speed loss is not a terminal DNF.

Start with pooled pi and pooled delay parameters, sharing conditional wind/leg effects with strong regularization. Add wind/recovery dependence only if the fixed comparison supports it; no hard 9-knot onset. Fit the clean and delay components jointly, anchored where reviewed clean/loss examples exist. The single-lognormal model is a reference competitor, not a fallback labelled physically true. Do not fit on fast-only selected data and then claim competitive unconditional tails.

Review episodes using speed loss, turn history, local/fleet wind, duration, recovery and coverage. Distinguish logging error, deliberate practice and terminal failure. Retrospective detector labels can help this review but do not provide a counterfactual time-loss baseline by themselves. Actual foil touchdown requires independent evidence unavailable in the current sensor schema. Use the empirical component name until that evidence exists.

Accept the mixture only if component parameters and allocations are stable across date deletion/initialization, the delay component is identifiable from reviewed loss examples rather than duplicate means, and held-out gate-time tails plus final race scores improve within P3 budgets. If evidence is insufficient, retain the small reference and show loss-tail sensitivity. A mixture is not made reliable by giving it a physics-sounding name. [Mixtures-of-experts review](https://arxiv.org/abs/1806.08200) provides the statistical background, not sailing-specific threshold evidence.

### C2. No double counting and current recovery

The mixture replaces the existing leg residual distribution. Do not add an event delay to a model already fitted to total loss-inclusive leg times without refitting that baseline. Do not additionally sample the same event through residual blocks, a foundation quantile spread and a separate tack-cost process.

At a live checkpoint, distance/progress and elapsed time already reflect losses incurred. Condition on current recovery evidence and sample only **future residual loss**. Recovery duration and added gate-arrival delay are distinct quantities; subtracting elapsed recovery seconds from an arrival-delay variable is not automatically valid. An episode continuing across a gate retains its latent state rather than triggering a new full delay. New future episodes remain separate opportunities.

### C3. Boundary behavior

Future/full-leg and current/remaining-leg distributions share one leg-level generative prior and latent performance state. With zero progress and no new information, conditioning is the identity operation: the distributions must agree in mixture probability, mean, variance and selected quantiles. A conditional-update implementation must pass this test before release; two independently fitted regressions with unmatched boundary distributions fail it.

Run a second test that introduces measured entry speed, a recovery episode or wind change and confirms the forecast responds. Genuine new information may change variance and win probability at a gate. Do not impose the review's unconditional variance equality after informative observations, and do not smooth output curves to hide either legitimate changes or a broken model.

## D. Reliability shape and observable tournament decisions

Let q be an audited pooled full-race exogenous-failure probability draw and lambda=-log(1-q). With course fraction u, define nonnegative shape g(u), G=integral_0^1 g(v)dv, and hazard `h(u)=lambda*g(u)/G`. Survival from u to v is `exp(-integral_u^v h(w)dw)`. This preserves total risk q for every shape and conditions naturally on survival.

Reference g=1. Sensitivity g=2 in the first leg or within the last 5% of a leg before a gate, and g=1 elsewhere, without double multiplying overlapping zones. These are explicitly hypothetical phase weights; six unreviewed terminal statuses do not fit them. Keep pre-gun DNS separate, and separate timerule failure from random reliability. A further hazard multiplier k uses `q_k=1-(1-q)^k`, never unbounded probability doubling.

For AC75 match sensitivity, use `p_ij=logistic(c*(theta_i-theta_j))` with c in {1,2,3}. c changes match outcome noise conditional on ability; sigma changes persistent differences. These are not interchangeable across a mixed fleet/match tournament. No current evidence supports a particular real-world 2–3x ratio. A dominant-sweep fixture should react in the expected direction under c, without describing that response as empirical accuracy.

Each simulated continuation contains its own public round-robin record. At the semifinal choice, select the eligible opponent with the lowest observed Challenger round-robin win fraction, excluding Defender results where required. Policy ties use pre-tournament predicted match strength and stable ID. Actual official selections override the policy. Its decision uses neither hidden persistent effects nor actual future results. A Bayesian policy would need a Bradley–Terry/ranking likelihood update from these observations; binary results do not have an automatic normal-normal conjugate posterior.

## E. Static scenarios, columnar schema and budgets

Planned baseline shape (names are a wire contract, not an implemented file):

```json
{
  "header": {
    "schema_version": "prediction-1",
    "race_id": "...",
    "boat_ids": ["..."],
    "model_ref": "...",
    "source_manifest_hash": "...",
    "scenario_hash": "...",
    "status_dictionary": ["available", "estimated", "gate_ambiguous", "unavailable"],
    "method_and_assumption_refs": ["..."]
  },
  "pre_race": {"expected_position_by_boat": {"...": 2.4}, "nonfinish_score": "N"},
  "live": {
    "state_timestamps_ms": [],
    "published_at_ms": [],
    "progress_band": [],
    "win_prob_by_boat": {"...": []},
    "no_finisher_prob": [],
    "status_code": [],
    "source_age_ms_by_boat": {"...": []},
    "position_uncertainty_summary_by_boat": {"...": []},
    "quality_code_by_boat": {"...": []},
    "numerical_error": []
  }
}
```

All parallel arrays have identical checkpoint length; unavailable probabilities are null. Store invariants once and reference large model cards. Keep state/publication time distinct. Six-decimal probability serialization may use a declared 1e-5 mass tolerance for these field sizes; serialization cannot turn unknown into zero or repair a missing opponent. Full covariance/draw diagnostics remain local downloads rather than repeated browser payloads.

Measured current asset sizes are 229,605,525 replay bytes and 8,551,065 analysis bytes. The new baseline target is <=1.5 MiB uncompressed across the 28 races; hard release budget <=3 MiB, with compressed bytes also reported. These are test gates, not a current size claim. User-selected scenario bundles have separate budgets and lazy loading. State-quality columns are not removed to hit a byte target.

Preset generation is pre-race only initially: supported TWS {8,12,16,20} knots crossed with course-relative direction offsets {-15,0,+15} degrees. Drop unsupported cells and show their unavailability. A fixed windward/leeward course does not support arbitrary rotated wind as if geometry were unchanged. Exact selected preset values are shown; custom inputs never silently borrow another cell's percentages. Tag every artifact with scope, field, class and condition hashes so a pre-race preset cannot masquerade as a live or Cup scenario. Key 5 selects Forecast, with the same input/modal/focus safeguards as existing keys.

## F. Metric and promotion correctness examples

### F1. Rank convention

In an eight-boat race with five finishers and three nonfinishers, tied-N scores sum to `1+2+3+4+5+8+8+8=39`. Mid-ranks would sum to 36. Both are coherent: they answer different questions. The chosen output is the expected tied-N score, so no conservation assertion belongs in its test. Preserve the agreed definition and label it rather than changing the target covertly.

### F2. Win chance and mean rank can disagree

Consider one joint distribution over three complete orders:

| Order | Probability |
| --- | ---: |
| A, B, C | 0.45 |
| B, C, A | 0.40 |
| C, B, A | 0.15 |

A has the highest win chance (0.45), but expected position 2.10; B has win chance 0.40 and expected position 1.60. All ranks sum to six. A coherent model therefore must not be tested by requiring the two orderings to agree.

### F3. Small-sample release policy

The revised P3 keeps three development dates and the descriptive audit, scores races chronologically and reports race-/day-equal summaries. It does not pretend a bootstrap repairs the independent sample size. Practical frozen guardrail budgets replace an exact-zero veto; a passing change is a provisional operational selection, not a significance or noninferiority finding. Live-only conditioning changes preserve pre-race distributions exactly; shared-strength/dynamics changes face pre-race checks too. A new model cannot omit its difficult early folds: its reference fallback is scored as part of the deployment procedure.

The larger scientific requirement is more independent competitive data and a prospective frozen evaluation. No adjustment of three-day thresholds can substitute for that evidence.

## Implementation status of this revision

This review originally changed the specifications only. The subsequent implementation now includes local Git provenance, a locked environment, session identity, causal filters, mixture fitting, backtests, artifacts and the fifth Forecast view. [The implementation runbook](forecasting_implementation.md) records current evidence gates and verified rule corrections. No experimental numeric output is a claim of established calibration; missing completion evidence, transfer evidence and unresolved rule branches still suppress unsupported probabilities.
