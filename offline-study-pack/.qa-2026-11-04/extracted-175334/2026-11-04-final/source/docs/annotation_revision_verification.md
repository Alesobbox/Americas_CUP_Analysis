# Annotation revision verification

Completed 3 November 2026 against the production build at `http://127.0.0.1:5190`. This closes the implementation work in [the approved plan](annotation_revision_plan.md). Existing uncommitted work was retained; the pre-change patch and preservation hashes are saved in `%TEMP%/ac40-annotation-baseline/`.

## Six annotations: delivered behavior

| Annotation | Delivered result | Acceptance evidence |
| --- | --- | --- |
| Artifact library | Canonical race metrics, six or fewer useful race exports, summary/performance CSVs; collapsed, searchable Technical data and provenance with current/catalog/supporting/retained/all filters. Every published object remains discoverable. | All 224 report rows reconcile with analysis, including unavailable retired GBR B metrics. All 495 inventory entries resolve and their sizes agree. CSV and legacy-catalog compatibility checks pass. |
| Blue Analysis | White Race Report and Historical View, including headers, cards, plots, controls, definitions, loading and error surfaces. | Four viewport checks; sampled text contrast at least 4.7588:1, light color scheme and no dark Analysis surface. |
| Precise performance chart | Axis activation with mouse, touch, Enter and Space; all-comparable or single-leg scope; exact pinned arithmetic, named peers, coverage, exclusions and qualifying events; focused detail plot and correct race/boat/interval Replay navigation. | All 1,038 available indexes and 2,895 leg ratios independently checked; 18,950 peer values reconcile. Chart scores stay on a common race scale, including tested scores above 150. No active score/label overlaps in tested states. Race/boat changes reset inspection scope. |
| Heel | Removed the permanently unavailable card; the banner has SOG, VMG, TWA and TWS. | Four viewport checks and standard/adversarial component tests. Supported channels still retain missing-sample reasons. |
| Current | Removed the unavailable Current cell and divider, leaving the recorded-wind HUD. | Four viewport checks; map toolbar, boat selection, playback, scale and map/offline behavior pass. |
| Wide Cup ranges | Separate baseline rule bounds, selected-scenario bounds and the outer assumption envelope; inspectable counts, assumptions, unresolved evidence, numerical error, model cutoff and missing-team mapping. | Nine scenarios × 5,000 trials, seed 2027. Counts, bounds, extrema and references reconcile. Both Python and browser validators reject missing required evidence and injected unresolved point probabilities. |

Reports never substitutes a differently defined replay summary for an unavailable historical metric. The producer owns inventory classification and CSV serialization. The browser draws/selects exported metrics; no historical formula moved to TypeScript. Original navigation, map geometry, course rendering, team identity and replay compatibility remain intact.

## Numerical and source checks

The `performance-1` arithmetic is unchanged. Naples ITA G downwind course VMG is 109.9671: the equal-weight mean of leg indexes 127.0241 (six peers) and 92.9101 (four peers). The ratio of its aggregate raw means, 108.0853, is a different calculation; the evidence panel explains this distinction.

All 173 complete six-dimension profiles remain available. Thirteen cover only part of their course. A bounded audit of original competitor timing records found no supported correction for their 21 excluded leg comparisons: 17 missing endpoints, one missing previous crossing, one nonchronological timestamp and two legs without an eligible peer. The new exclusion reason explicitly identifies the nonchronological source timing. Missing crossings were not invented. Match-final ITA B visibly compares four of six legs and 847.085 source-covered seconds.

| Preservation / export check | Result |
| --- | --- |
| Original replay bytes | All 28 SHA-256 hashes unchanged |
| Existing historical details | All 28 canonical digests unchanged after removing the optional tactical/performance/debrief extensions |
| Historical index | Canonical digest unchanged; 28 races / 224 replayed boat-races |
| Performance numbers | Existing values, indexes, peer counts, coverage, sample counts, matched legs and quality preserved by metadata refresh tests |
| Canonical CSVs | 56 files; 3,772 summary rows and 4,239 aggregate/leg performance rows reconciled |
| Fast refresh | All 496 public data files byte-identical before/after a full `--performance-only` refresh |
| Production publication | All 496 public data files match `dist/data` by SHA-256; all 495 inventory download sizes verified |
| Tactical data | 3,455 snapshots retained; zero windows pass the existing conditional five-minute projection gates |

The targeted refresh reads existing exports, without scanning raw telemetry. Raw source coverage rules and gaps remain documented in [source audit](source_audit.md) and [historical analysis](historical_analysis.md). Tactical insights report recorded trends and suppress unsupported projections; a promised wind shift in five minutes is not supported by this archive.

## Cup publication and remaining uncertainty

Active immutable Cup object: `predictions/cup/5cae98e1c3856cd6885831d0b876d6ae048d0d005d5fc373ab7d0651a8f9a6b5.json`.

It pins model `dd9a31a7834ae1e9d8c0c082b437e0c6542302bed171b0d8e5e45f9c6b3940da`, trained before 26 September 2026 (UTC cutoff 1790380800000), plus the original hashed model source manifest and current Cup generator hashes. The public mapping now distinguishes missing Australian history from an observed zero effect and applies the missing-history prior. Model choice and simulation budget are explicit. A repeat candidate build reproduces the full content hash. Immutable objects are validated before the active index is switched; older objects remain accessible.

The baseline has 3,277 resolved and 1,723 unresolved paths of 5,000: **34.46% unresolved**, first occurring at Challenger round-robin qualification. Conservative allocation of that mass gives each baseline interval a 34.46 percentage-point width. The outer envelope adds the tested transfer/residual assumptions; it is not a calibrated confidence interval. Numerical Monte Carlo half-width is disclosed separately and cannot remove structural uncertainty. Overlapping reason counts are labelled separately from first-unresolved-stage counts.

The final publication differs from the previously reviewed `b1c18c…` candidate only in the recorded hash of the strengthened contract validator. Every scenario value is identical. Available method-2 artifacts require scenario evidence and complete null headline probabilities while paths remain unresolved. Independent mutation review rejected all 14 malformed variants in each validator, including deleted evidence/containers/teams, extra teams and inserted point probabilities. Legacy method 1 and explicitly unavailable method 2 remain compatible.

Conservative outer bounds remain because an authoritative six-Challenger tie completion set is not pinned. The artifact explains this fallback. Reliability remains conditioned on scored/completed races, wind response is zero and AC40-to-AC75 transfer is uncalibrated. Acquiring rule clarification, AC75 data and transfer validation remains the separate research work explicitly deferred by the approved plan. Narrower-looking ranges are not a release criterion.

## Verification runs

Final `run.ps1 verify` passed: **805 deterministic tests** (385 frontend across 35 files, 289 Python units, 123 reconstruction/workload checks and eight generated-data checks), production build, prediction budgets, environment integrity and analytics integrity. No tests were skipped. Prediction browser baseline is 1,188,740 bytes, below the 1.5 MiB target and 3 MiB hard limit.

Final production browser suites passed **53 scenarios**: 18 dashboard, 18 annotation-specific and 17 forecast. Viewports: 1096×704, 1586×992, 1280×720 and 390×844. Coverage includes all 28 races, fleet/match, both Analysis tabs, four supported KPIs, header dismissal at the annotated breakpoint, chart interactions/scope/replay intervals, canonical Reports and downloads, all nine Cup scenarios, unavailable recovery, map worker/attribution and offline Grid fallback. Dashboard and annotation suites recorded zero browser exceptions, unexpected console errors or failed application requests; the forecast suite recorded zero page errors.

The annotation suite saved 56 screenshots and computed palette/contrast, page width, internal table scrolling and chart label overlap checks. Final desktop/mobile chart, peer evidence, four-of-six support, race exports, Replay and Cup bounds/disclosures were visually reviewed.

Logs and evidence:

- `%TEMP%/ac40-annotation-final-verify.log`
- `%TEMP%/ac40-annotation-final-dashboard-browser.log` and matching directory
- `%TEMP%/ac40-annotation-final-browser.log` and matching directory (`results.json`, screenshots and visual metrics)
- `%TEMP%/ac40-annotation-final-forecast-browser.log` and matching directory
- `%TEMP%/ac40-annotation-preservation.json`

## Reproduce

Use the repository Python environment with the locked forecast dependencies. Start the application, then set `REGATTA_URL` to its origin for browser tests:

```powershell
$env:REGATTA_PYTHON = Join-Path $PWD '.venv/Scripts/python.exe'
./run.ps1 verify
$env:REGATTA_URL = 'http://127.0.0.1:5190'
npm run test:browser
npm run test:annotations
npm run test:forecast
```

To refresh performance evidence and CSVs without scanning raw wind:

```powershell
./.venv/Scripts/python.exe scripts/refresh_team_analytics.py --performance-only
```

The full source-wind refresh remains `npm run analytics`. See [forecasting implementation](forecasting_implementation.md) for private candidate generation and validated publication. These software and arithmetic checks establish implementation consistency; they do not establish forecast calibration or causal performance attribution.
