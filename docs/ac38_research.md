# AC38 statistical research

`polar-2` (polar schema `2.0`) uses individual accepted 1 Hz observations. It replaces the earlier cell-mean target used by `polar-1`; their RMSE and percentile coverage are different quantities and must not be compared as algorithmic gains. Existing historical metrics and replay channels retain their definitions.

## Refresh and inspect

Run `npm run research` or `.\run.ps1 research` after ingestion or environmental updates. This re-extracts samples from exported replay precision, rebuilds the polar and uncertainty, evaluates model/wind/environment comparisons, and exports wind and timing research. It uses only local data; raw official wind is scanned once and cached with source hash, size and modification time.

`python scripts/refresh_ac38_research.py` reuses existing timestamped samples. `--extract-only` rebuilds those samples without fitting. Missing sample inputs produce explicit unavailable outputs. New source files require normal ingestion first.

Reports live in `public/data/research/`: `polar_experiments.json`, `wind_forecast.json`, `timing_summary.json`, and `receipt.json`. Race detail contains `polar_samples`, `polar`, `timing_research`, and `wind_forecast`. The historical index contains compact research results. Reports and Analysis link the downloadable artifacts. The receipt binds samples, race timing/coverage, wind provenance, producer code and output bytes. Ordinary historical refresh retains research only while those dependencies match; otherwise run research again.

## Population and targets

Samples retain timestamp, race/day/boat/leg, mode, tack, position, SOG/COG/heading and local wind. Every required own stream must pass source coverage checks. Proximity uses valid active peer positions, independently of peer wind coverage. Completed-leg, speed/angle, gate, turn and traffic exclusions are explicit. This selected steady population is not a complete sample of takeoff, breakdown or manoeuvre states.

Legacy cells retain counts, means, quantiles and sums of squared speeds for inspection. Fitting and validation use the underlying samples. Quantile histograms combine sample counts, never averaged cell quantiles. Mean, p50 and p90 are observed conditional ground-speed summaries; none establishes water speed, a physical limit or intrinsic crew skill.

## Evaluation and uncertainty

- LORO and LODO are retrospective transfer evaluations; LODO can train on later dates.
- Expanding chronological evaluation uses only earlier days and discloses unscored initial/unsupported observations.
- Kernel predictions require at least 12 weighted seconds and two distinct supporting training boat-leg clusters. Unsupported predictions are excluded and counted, rather than silently replaced with a mode mean.
- The mode-only reference is scored on the same supported LODO observations. Diagnostics include day, mode and wind bracket, target counts, bias, RMSE, pinball loss and percentile coverage.
- Full-archive curves are descriptive fits. Cross-validated residuals have a separate scope.
- Primary absolute team residual intervals resample whole days and refit the reported quadratic tack estimator and kernel reference in each draw. Race-block refits are a sensitivity analysis. The original supported evaluation cohort is fixed, and invalid draws are counted.
- Per-boat intervals resample complete legs within the observed race, conditional on the fitted out-of-day reference. They do not include all fitted-model uncertainty. VMG and auxiliary residual intervals also disclose conditional scope.
- Peer contrasts exclude the selected boat, give peers equal votes, average legs within race, then races within team. Day-block sensitivity remains conditional on the cross-fitted polar. It is observational comparison, not crew attribution.

Only eight eligible polar days support the current archive. More bootstrap draws do not increase independent evidence. Calibration is diagnostic; no conformal, conditional subgroup or future-venue coverage guarantee is claimed.

## Model and wind experiments

The candidate comparison uses nested day tuning for kernel and regularized local-linear surfaces, with both outer LODO and chronological evaluation. Predictions are evaluated on common supported rows. Paired day changes and sample-weighted scores are both reported. Added complexity is not automatically promoted.

Wind alternatives use onboard readings, the exported official timeline and a target-excluded nearby peer consensus. Space/time matching, disagreement counts, circular direction differences, day-block sensitivity and training-only boat/tack adjustments are recorded. The official timeline is interpolated and geographically distinct; these comparisons establish agreement and predictive sensitivity, not sensor calibration truth. Large disagreements remain flagged rather than discarded at 60 degrees.

Foil-state mixture fitting is explicitly not physically identified. No verified foil-state labels exist, and the selection omits slow/incomplete portions. Kernel versus local-linear comparison is the supported baseline experiment; latent components must not be called verified foiling states.

## Environmental comparisons

Current, wave and thermal blocks are evaluated separately against their own baseline on identical available observations. Missing wave values never change the baseline cohort silently. The report includes native-support caveats and matched samples/days/venues.

Current-adjusted speed is the norm of ground velocity minus the modeled east/north current vector, in common units. It is a coarse-model sensitivity, not measured speed through water. Wave period means energy period `Tm-1,0`, not peak period. Air-minus-water temperature is a rough retrospective covariate, not air density or a validated stability measurement. Water temperature is model temperature at the disclosed depth, not skin SST.

The acquired current is hourly reanalysis at approximately 4.2 km and 1 m depth; some wet-cell sampling is displaced from the yacht track. Waves have substantial Naples missingness. A null result establishes only failure of these covariates to improve this benchmark; an improvement may capture date/venue associations. Neither result identifies a physical cause or establishes pre-race forecast skill.

## Exact timing and manoeuvres

Gun-to-start delay plus consecutive observed leg durations equals gun-to-endpoint elapsed time. Peer ledgers use the same eligible peers across components. Separately, unavailable, gate, turn and other-sailing phase seconds are mutually exclusive and reconcile to the observed active interval. Prefixes and reconstructed finishes remain distinguished.

Turn candidates use heading/TWA geometry without a minimum speed-loss threshold. Progress deficits compare observed course-axis progress against a declared pre-turn straight continuation. An alternate polar reference uses supported pre-turn conditions and excludes the evaluated day; it never queries mid-turn angles outside polar support. Outputs remain metres, not causal seconds lost. Baseline quartiles and 10/20/30-second horizons show sensitivity rather than confidence guarantees. Gaps, nearby turns, gate approaches and missing recovery cause explicit censoring.

Speed collapse is an unreviewed response label, not verified touchdown. Deterministic non-overlapping event/background review windows support later human annotation. Precision and recall remain unavailable until reviewed labels exist; the evaluator uses one-to-one event matching.

## Probabilistic wind forecast

The binary target is the shortest-arc absolute direction change at exactly 180 seconds reaching five degrees. It is not the probability of any excursion within the horizon. Forecasts use fresh trailing measurements, preserve incomplete targets as censored and score only complete outcomes.

Expanding whole-day evaluation compares training-only climatology, probabilistic persistence and local-angle autoregression. Label-end times precede issuance, and tuning uses prior data. Full empirical circular distributions are scored with Brier/log loss and circular CRPS; day-equal results, reliability and paired day sensitivity accompany sample-weighted scores. The autoregression remains a research challenger. Measurement-time causality is retrospective evidence, not verified historical live delivery.

## Verification

Run `.\run.ps1 verify` for unit, frontend, build, reconstruction, artifact and environmental gates. The research tests challenge sample quantiles/SSE, bootstrap refits, support, equal-peer weighting, chronological isolation, wind wrap and scores, environmental matching, ledger identities, clean turns, source gaps and censoring. Code-quality settings remain unchanged.
