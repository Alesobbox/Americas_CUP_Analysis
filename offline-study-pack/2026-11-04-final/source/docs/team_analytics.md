# Team analytics

Added 1 November 2026. These features extend the existing dashboard design and downloadable historical details. Python owns their formulas and availability; the browser only selects snapshots, formats values, and draws scores.

## Where to use them

- **Replay / Compare:** Tactical insights follows the shared playhead. Rewind selects an earlier snapshot; a future or expired observation is never displayed as current.
- **Analysis:** Select a race and boat, choose all comparable legs or a single leg, then activate a circular-chart dimension to pin exact exported evidence. Expand a contributing leg to inspect peers and review its interval in Replay. Team debrief lists further review priorities.
- **Reports:** Use the race summary and boat/leg performance CSVs or the full analysis JSON. The collapsed Technical data and provenance explorer retains every published object.

## Tactical insights: tactical-1, schema 1.0

The input consists of independent raw official-wind direction and speed observations with their original measurement timestamps. It does not use the replay's interpolated wind, a retrospective whole-race baseline, boat-local wind as a substitute, or an external weather service.

Snapshots are exported every 10 seconds from the gun through the replay window end. A session that ended before its gun has an empty snapshot grid with an explicit reason. Each uses a trailing 120-second window. A one-second grid takes the most recent observation at or before each grid instant, with a maximum source age of two seconds. A direction or speed window requires at least 60 source samples, every grid instant covered, and no source interval longer than two seconds. Missing direction is unavailable rather than north/zero. Direction and speed availability are independent.

Direction is unwrapped using shortest circular differences. The observed direction change is the end-minus-start unwrapped angle; positive means clockwise (veering), negative counterclockwise (backing). The direction rate is the ordinary least-squares slope on the one-second trailing grid, in degrees per minute. Speed change is the difference between fresh endpoint speed observations, in knots. Coverage counts one-second intervals with fresh endpoints and no overlap with a rejected source gap. Direction and speed each export their own coverage, source sample count, quality and missing-data reason.

A conditional five-minute projection is five times the recent direction rate. It requires at least a one-degree net change, absolute rate of at least 0.2 degrees/minute, projected change no greater than 30 degrees, consistent nonzero rate signs across the two one-minute halves, half-window rates within max(0.25 degrees/minute, 50% of the full-window rate), residual RMS at most max(1 degree, 20% of net change), and no one-second directional jump over three degrees. These are deterministic suppression rules, not learned or validated forecast gates. A projection states the assumption that the recent trend continues; it has no calibrated probability, interval, or promised arrival time. Variable, flat or steep windows explain why a projection is unavailable.

The browser selects the latest snapshot at or before the playhead, verifies the race ID, and expires it after 12 seconds. Before the first snapshot, it explicitly reports that no window has been reached. Observation and projection are labelled separately.

Source provenance records the file, SHA-256 and official-wind asset ID. Causality is by measurement timestamp for retrospective replay. Raw records can arrive out of order; arrival-time availability is not established, and adding late records with earlier timestamps can revise historical snapshots. Hashes identify the exact source used for this export.

## Boat performance: performance-1, schema 1.0

Six dimensions describe this race: upwind and downwind leg-directed course VMG, upwind and downwind mean SOG, and detector-conditioned tack and gybe speed retention. Odd legs follow the existing upwind course-axis convention, and even legs its reciprocal. There is no measured polar or optimal-speed target, so these are relative observed-performance indexes.

A boat is excluded for OCS, retirement, DNS, a missing start crossing, or a flagged source-state conflict. A non-finisher may contribute its valid completed legs. Speed and VMG require positive finite values, a completed leg, derived quality and at least 95% valid source coverage over the reconstructed leg duration.

For each eligible boat and leg, the baseline is the equal-weight mean of **other eligible boats on that exact leg**. The leg index is `100 * boat_value / peer_mean`. The dimension index is the arithmetic mean of its matched-leg indexes; every matched leg has one vote. A peer boat has one vote per leg. Displayed raw boat values and peer means are arithmetic matched-leg means, so their ratio need not equal the mean of per-leg ratios. Evidence retains the per-leg values, indexes, peer identities, sample counts and coverage. Dimension peer count is the unique union of contributing other boats; the exact count on each leg is available in the JSON evidence.

Speed retention is `100 * minimum_SOG / entry_SOG` for qualifying detected manoeuvres. Each boat's same-kind events are averaged within a completed leg before comparison with the other boats. The full detector source window, 65 replay samples before through 60 samples after the timestamp, must be inside the leg and valid for SOG, heading and local TWD, without source gaps. At the default 100 ms cadence this is 6.5 seconds before through six seconds after; at 200 ms it is 13 seconds before through 12 seconds after. Nondefault regular grids record `race.sample_interval_ms`; omitted cadence means the existing 100 ms default. Events near gate roundings are excluded. The detector requires a speed reduction of at least 2.5 knots, so this describes its qualifying event population rather than every real tack or gybe. Coverage is the union of cadence-scaled validated event support windows, avoiding overlap double-counting; debrief manoeuvre source checks use the same cadence.

Index 100 is the other-boats baseline; higher indicates a larger observed value for every dimension. An overall index uses an equal-weight average only when all six dimensions are available and is labelled a heuristic profile summary. Missing dimensions remain null with a reason, and the chart leaves gaps. The graph uses one shared full-range scale for all boats and legs in the race, starting at 0–150 and expanding when necessary. A focused detail plot makes small differences around 100 visible; full arithmetic remains inspectable. This comparison does not control for changing wind, start times, traffic or tactical obligations, and establishes no intrinsic yacht/crew ranking.

The additive `scope` evidence records expected and matched course legs, excluded-leg reasons, minimum peer count and source-covered seconds. Coverage counts the union of contributing leg intervals once, avoiding duplicate SOG/VMG support. Each dimension's `leg_evidence` now also includes interval boundaries, per-peer values/coverage/quality/counts, excluded-peer reasons and qualifying manoeuvre events. No performance-1 formula changed. Thirteen profiles with six available dimensions cover only part of their course: the match-final ITA B profile compares legs 1–4 of six, with 847.085 source-covered seconds. Missing or inconsistent source crossings remain excluded.

## Team debrief: debrief-1, schema 1.0

The queue contains up to three largest positive leg-time differences from the mean of other eligible boats on that same completed and sufficiently covered leg, plus up to two covered detected manoeuvres with the largest entry-to-minimum SOG reductions. Items retain units, source, quality, timestamps and peer identities where applicable. A leg-time difference is an observed deficit; manoeuvre speed reduction is neither seconds lost nor distance lost. Replay links support analyst review; neither item identifies a causal explanation.

## Refresh and compatibility

Run `npm run analytics` to stream source wind and refresh all race extensions, the historical index and the artifact inventory. Replay telemetry arrays, existing historical scalar values, historical schema `2.0` / method `historical-2`, event-feed schema `1.0` / method `event-feed-1`, Forecast and historical environment artifacts remain compatible. New ingestion also exports the extensions automatically.

For performance/evidence or CSV-only changes, run `.venv/Scripts/python.exe scripts/refresh_team_analytics.py --performance-only`. This uses existing exported historical evidence and never scans the raw archive; tactical snapshots remain unchanged. Both refresh paths and ingestion generate the canonical per-race summary/performance CSVs and rebuild the inventory.

Use `python scripts/analysis_snapshot.py` for the bounded archive overview. Set `REGATTA_PYTHON` if necessary. `npm run verify` includes analytics integrity verification; `npm run test:browser` exercises visible behavior against the running app. The implementation plan and acceptance criteria are in [team_analytics_plan.md](team_analytics_plan.md).

## Verification evidence

The annotation revision of 3 November 2026 supersedes the chart range and UI checks in the dated baseline below. See [annotation revision verification](annotation_revision_verification.md) for the final acceptance matrix, current counts, reproducibility and production-browser evidence.

Verified on 1 November 2026. Every stage in [the implementation plan](team_analytics_plan.md) is complete.

| Output / check | Result |
| --- | --- |
| Archive | 28 sessions, 224 replayed boat-races |
| Boat performance | 173 eligible boats have all six dimensions and an overall index |
| Team debrief | 707 evidence-linked review items across 180 boats |
| Tactical snapshots | 3,455 snapshots; 3,438 valid direction windows and 3,438 valid speed windows |
| Five-minute projections | Zero windows pass the deterministic stability gates; projection remains unavailable |
| Pregun practice session | Explicit empty timeline for `26_09_23_nap_ipr_pr1`, whose recorded window ends before its gun |
| Frontend | 371 tests passed across 34 files |
| Python unit tests | 274 passed, including circular wind, future-prefix invariance, independent fields, source gaps, peer exclusion, matching legs and custom-cadence detector windows |
| Reconstruction / workloads | 123 passed |
| Generated-data integrity | 8 passed |
| Total deterministic tests | 776 passed; production build and Forecast/environment/analytics verification gates also passed |
| Browser | 16 scenarios passed: all 28 races plus fleet/match at 1586x992, 1280x720 and 390x844; zero unexpected exceptions, failed application requests or console errors |
| Final visual checks | 13 feature screenshots; radar, inner evidence-table scrolling, debrief contrast, separate wind evidence and all four formula disclosures verified |
| Preservation | All 28 replay SHA-256 hashes, all 28 existing historical-detail values and the historical index are unchanged |
| Production data | All 438 public data files match production by SHA-256; all 437 inventory download sizes match |
| Refresh reproducibility | A representative `naples_pr1` refresh is byte-identical, including formula metadata, index and inventory |

The browser checks include rewind and future/mismatched-race guards, debrief replay navigation, missing analysis/replay recovery, downloads, notes, selection, map attribution, worker loading and offline Grid fallback. Desktop and mobile page widths match their viewports; the performance evidence table scrolls inside its own container. The five existing navigation views and design are preserved.

Verification logs are `%TEMP%/ac40-team-analytics-delivery-verify.log` and `%TEMP%/ac40-team-analytics-browser.log`. Browser results, final visual metrics and screenshots are in `%TEMP%/ac40-team-analytics-browser/`. `--verify` checks source existence, file size and recorded hash format without rehashing the multi-gigabyte raw archive; a refresh computes the full source hashes while streaming it. These implementation checks do not establish forecast calibration or causal performance attribution.
