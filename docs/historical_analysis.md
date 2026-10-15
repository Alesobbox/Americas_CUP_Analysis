# Historical race analysis

## Artifacts and lifecycle

`run.ps1 ingest` processes every `Data/*.jsonl` file, upserts its replay into `public/data/manifests.json`, writes `public/data/analysis/<race-id>.json`, then rebuilds `public/data/analysis/index.json` from the catalog. The detail and index use schema `2.0` and method `historical-2`. Repeating ingestion with the same sources yields the same statistics. The index contains compact boat-race results, start outcomes, completed-leg measures for the source course's four or six legs, and manoeuvre distributions with originating race counts, but no 10 Hz telemetry. The browser loads the index when analysis opens and fetches a race detail only when that race is selected. New catalog races with a matching analysis artifact enter the history automatically.

Python defines the metric catalog in `pipeline/historical_analysis.py:DEFINITIONS`; the exporter embeds it in every detail artifact. The TypeScript analysis view consumes those definitions and values and performs no metric calculations. Each scalar value carries its unit, quality, covered seconds, and an unavailability reason where applicable. Quality `derived` means at least 95% of the requested active interval passed the source timestamp checks; `partial` means some samples were available but coverage fell below 95%. An empty source or invalid window produces null with a reason. `reconstructed` identifies detector or checkpoint outputs. The historical median/range excludes partial and unavailable observations and counts each boat-race once. Event distributions use individual manoeuvres and show counts.

## Compact event feed

Each race detail has an additive `event_feed` object with `schema_version: "1.0"`, `method_version: "event-feed-1"`, and timestamp-sorted `events[]`. An event has a stable `id`, `timestamp_ms` (Unix milliseconds), `type`, `label`, `source`, and `quality`; boat events also have the source asset `boat_id`. `unavailable_reason` is optional for future event types. The feed selects the session gun, reconstructed bow-line start crossings, source-timed or geometrically reconstructed gate crossings, detected tacks and gybes, and finish crossings only when a ranked boat has a final-leg gate timestamp. Missing crossings are omitted rather than assigned a gun, window-end, or other fallback time. Source start-state conflicts are marked `source_conflict`; `source_timing` on a gate means a source leg-time record, not an independently verified official result.

Wind-shift events use the bounded official-wind samples already exported in `wind.timeline`, not local boat wind or a visual estimate. Python emits a shift when the shortest circular change from the last emitted reference reaches 10° and at least 30 seconds have passed. The event timestamp is the selected official sample time, its quality is `measured_sample`, and no wind event is emitted without a qualifying sample. This is a descriptive change in reported direction, not evidence of a tactical cause.

## Timing, provenance, and coverage

The source GNSS, heading, COG, SOG, and boat wind streams are measured at different rates. Ingestion projects GNSS to local metres, converts speeds to knots, and interpolates on the 100 ms replay grid. Analysis uses those unrounded synchronized arrays and source timestamp coverage. It rejects samples before the first source timestamp, after the last timestamp, or inside a source gap longer than two seconds. Leg intervals are clipped at the actual reconstructed crossing timestamps rather than at the nearest 100 ms frame. The existing replay's rounded telemetry and fixed-axis VMG remain compatible, but neither is used as a rounded input to the new calculations.

The source does **not** provide independently verified official finishing classifications for most boats. The supplied leg timing records and geometric fallbacks determine the exported rankings and elapsed times. The keys `official_rank` and `official_elapsed_s` remain in the schema for compatibility; the analysis display calls them reconstructed results and sets both to null for DNF/RET. USA's PR1 nested `start_state.started` is false even though the reconstruction assigns a start and finish. That conflict is flagged for adjudication. A DNF has no finish time, and a RET/OCS boat without a valid start has no active-race performance score.

## Metric contract

The artifact's `definitions` object is the machine-readable contract for each scalar: label, unit, formula, window, denominator, and source. The main calculations are:

| Group | Definition and availability |
| --- | --- |
| Course VMG | `SOG × cos(COG − leg bearing)` in knots. Odd legs use the course axis; even legs use axis + 180°. Mean and time-weighted 10th/90th percentiles are per leg. The replay's `vmg` remains a signed fixed-axis trace and is never averaged across the whole course for performance. |
| Wind VMG | `SOG × cos(COG − boat TWD)` on upwind legs and its negative on downwind legs. TWD is the direction the wind comes **from**. Mean and percentiles require valid local wind timestamps. |
| True wind angle | Signed shortest difference `TWD − heading` remains in replay. Analysis uses `|TWA|` for distributions and separate port/starboard stable-period medians. It does not average signed port and starboard TWA. |
| Sailed distance | Sum of projected GNSS segment lengths in the valid active interval, clipped at exact start/gate/finish times. Missing source intervals are excluded, with covered seconds and quality reported. |
| Route ratio | Straight distance between a leg's observed endpoint positions divided by its sailed distance. This geometric reference is **not** a feasible route through marks or gates. It is unavailable without both endpoints and a valid path. |
| Tack allocation | Signed TWA above +15° is starboard, below −15° is port. A ±3 s window around detected manoeuvres and angles close to head-to-wind are excluded. Time and path distance are reported by leg and side. |
| Manoeuvres | Reuses the detector's tack/gybe events, entry/minimum speed, and speed loss. Recovery is first sampled SOG reaching 95% of entry speed after the local minimum, within 15 s. Missing recovery is null, never zero. Acceleration is `(0.95 × entry − minimum) / recovery seconds`; events within 5 s of a gate are flagged ambiguous. Counts and medians are separated by event type. |
| Boundary | Minimum signed distance from the boat centre to the **race** polygon active at the sample timestamp, positive inside. Time in the 0–25 m buffer and time outside are sampled exposure, not a rule decision. Outside periods lasting at least one second are linkable to replay. Safety polygon and boat Keep Clear border are different geometries and are not substituted. |
| Start | Bow signed distance to the moving source sequence-0 port–starboard line at the gun; normalized along-line fraction 0 at port, 1 at starboard, and unclamped beyond ends. Cagliari uses RM3/RM7; Naples marks vary by session. Gun SOG and signed closing component use COG. OCS has no valid crossing order. |
| Checkpoints | Each completed leg uses actual crossing timestamps. Gate split is the observed difference from the earliest valid crossing at that checkpoint. Split/rank change compares the boat's prior completed checkpoint. These are timestamp observations, distinct from replay's continuous progress time-gap estimate. |
| Mark approach | Moving chosen mark at 20 s before crossing yields bearing and absolute COG-to-mark angle. Entry/exit SOG uses ±5 s. No stable rounding start/end event exists, so rounding duration is unavailable. |
| Tactical separation | During overlapping active windows and matching legs, one-second samples yield median physical and lateral distance for each selected pair. They measure geometry, not race-progress advantage. |
| Wind | Official roughly 1 Hz TWD shifts use the shortest circular difference from the first active official reading. Boat-reported local TWD is aligned to official samples only during valid active windows; deviations over 60° are excluded as outliers. Fleet spread requires at least two active valid boats. This is descriptive exposure, not proof of tactical causation. |

## Deferred and limited measures

Measured target TWA, polar speed, and a reliable tactical baseline are absent, so estimated laylines are not exported. Bearing-to-moving-mark and approach angle remain available. Rounding duration and integrated manoeuvre distance loss have no stable event or baseline definition in these files. The historical-analysis exports contain 28 races and 224 replayed boat-races in separate fleet and match cohorts. The source files contain 227 competitor entries; GBR B has no replay telemetry in three 22 September Naples practice sessions, so those source entries do not become boat-race observations. Each race is one observation, not a telemetry-frame-weighted sample.

The current ingestion maps known AC40 competitor and mark asset IDs from `pipeline/config.py`. Future files using new IDs or boat classes need a configuration update before they can be reconstructed, although any successfully ingested catalog race appears in the history automatically.

## Verification

Use `run.ps1 verify` for the project's test/build workflow. `python -m unittest tests.unit.test_historical_analysis -v` covers hand-checkable formula and geometry cases, incomplete results, sparse wind, missing recovery, and catalog boat-race counts. Re-run `run.ps1 ingest` after changing metric formulas or adding source data, then inspect the regenerated index and selected race detail. The integrity suite checks all 28 replay and analysis paths, venue grouping, the six-leg Cagliari course, and the 22 September Naples benchmark.
