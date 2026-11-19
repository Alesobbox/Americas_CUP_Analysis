# AC38 research implementation verification

Verified on the local 28-session AC38 archive after rebuilding with `python scripts/refresh_ac38_research.py --extract`. Generated data remains excluded from Git; `npm run research` reproduces the local artifacts from available telemetry/replays and environment exports.

## Results and interpretation

- Accepted population: 132,165 individual 1 Hz observations, 25 sessions, eight days and 987 boat-leg clusters. Source/traffic filtering differs from the earlier polar-1 population; comparisons must disclose that change.
- Sample-level LODO RMSE: 2.671 kt against 4.039 kt for the mode-only baseline on the same 132,036 supported samples. LORO RMSE is 2.555 kt; earlier-day chronological RMSE is 2.514 kt on 98,302 supported samples. Different evaluation populations prevent treating these three numbers as a simple method ranking.
- Nested model comparison: sample-weighted LODO RMSE 2.6492 kt for the tuned kernel and 2.6686 kt for local-linear fitting, on common supported rows. Added complexity was not promoted.
- Matched wind-source comparison: onboard RMSE 2.6140 kt, official 2.9204 kt and nearby-peer consensus 2.6883 kt on 79,480 matched observations. These are retrospective predictive comparisons, not sensor accuracy certification.
- Current features did not improve the declared baseline. Waves and thermal covariates improved their own fixed-cohort retrospective comparisons; realized environment and venue/date associations prevent causal or pre-race claims.
- Wind benchmark: 2,583 scored forecasts across eight chronological days. Day-equal Brier 0.217394 for probabilistic persistence and 0.202714 for local-angle autoregression. The latter remains an experimental challenger; overlapping targets and few independent days limit evidence.
- Timing: 168 complete checkpoint ledgers across 224 boat-races. All observed checkpoint and disjoint-phase ledgers reconcile. Geometry yielded 3,101 turn candidates, including clean turns omitted by the previous speed-loss filter. There are 6,895 complete horizon estimates and 1,895 censored horizons. Physical event labels require review.

The research receipt's dependency hash and all three artifact hashes were independently recomputed successfully. Cached report attachment was also checked. No official outcomes or physical foil-state labels were invented.

## Required gates

`python scripts/verify.py --with-format` passed:

- Prettier, Ruff, TypeScript and production build.
- 379 frontend tests across 36 files.
- 234 Python unit tests, including the new independent statistical, environmental, timing and wind checks.
- 123 reconstruction/workload tests and eight generated-data integrity tests.
- All 152 environmental cache tasks, 28 race exports, 28 boat files and 28 provenance bundles.
- Analytics verification and documentation links.

`npm run test:browser` passed 18 checks, covering every race, desktop/mobile fleet and match views, playhead causality, controls, download inventory, missing-feed recovery and offline map fallback. It reported zero page errors and zero failed data requests. `npm run test:redesign` (10 checks), `npm run test:feedback` (5 checks, including plain-language display wording on Analysis/Reports) and `npm run test:annotations` (14 checks, 0 errors, WCAG contrast and overflow across viewports) also passed.

Earlier focused research browser checks also passed at 1280×900 and 390×844 (screenshots saved locally under `.cache/ac38_research_qa/`, excluded from Git): actual research results render, report links return HTTP 200, horizon selection works, and mobile page width remains 390 pixels.

Clean-clone zero-data verification (`git archive main` + `npm ci` + `python scripts/verify.py --with-format` + headless missing-archive preview) also passes without local `public/data/`.

Direct `npm audit --json` reported zero vulnerabilities. The aislop security subprocess could not launch npm in its own environment; the direct audit completed that check.

## Remaining quality warnings

The final changed-file aislop scan scored 94/100, with zero errors and zero fixable warnings. It reports 22 non-mechanical warnings:

- Existing size, function-length, parameter-count and nesting warnings in `pipeline/historical_analysis.py`, `scripts/refresh_team_analytics.py`, `scripts/build_artifact_inventory.py`, `src/engine/analysisCatalog.ts` and `AnalysisModal.tsx`.
- Existing duplicate render blocks and a state/effect warning in `AnalysisModal.tsx`. Resolving these requires broader legacy UI/refactoring work.
- SVG `role="img"` warnings in the extracted polar chart and existing analysis chart. These are retained accessibility false positives: replacing the inline vector chart with an HTML image would change the rendering contract. An existing grouped-content role warning is also retained.

Mechanical warnings encountered during implementation were fixed. No quality rules or thresholds were disabled or changed. New polar/research modules are split by responsibility rather than extending the old monolithic polar file.
