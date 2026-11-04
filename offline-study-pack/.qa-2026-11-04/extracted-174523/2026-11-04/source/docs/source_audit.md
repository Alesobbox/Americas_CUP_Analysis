# Source telemetry audit

## Expanded 28-race archive, 10 October 2026

The source directory now holds 28 distinct session IDs and 6,866,006,601 bytes of JSONL: nine Cagliari races (63 boat-races, eight distinct teams) and nineteen Naples races (164 boat-races, nine distinct teams). There are 26 fleet sessions and two match sessions. Source competitor messages provide 181 eligible final-gate timings, but **zero independently verified official finishing orders**. Six final classifications are `RETIRED`, five are `DID_NOT_START`, and 12 boat-races have a false source start state alongside a recorded start crossing. Three Naples practice sessions have no final-gate times.

Tracked telemetry messages may be out of timestamp order by as much as 5,850 ms. The source inventory changed after the audit below, which remains a detailed audit of the original two exported races.

## Original two-race replay audit, 8 October 2026

Audited the two `Data/*.jsonl` files and their corresponding `public/data/replays/*.json` exports on 8 October 2026. Counts below come from a streaming parse of every raw line and checks of the complete exported arrays. Times are UTC; timestamps in the files are Unix milliseconds. This is a source and transformation audit, not independent verification of race results.

## Inventory and time base

| Race | Raw size | Raw records | Session / telemetry / competitor records | Source window (UTC) | Export grid |
| --- | ---: | ---: | ---: | --- | ---: |
| Naples PR1, fleet | 323,965,659 bytes | 1,481,064 | 9 / 1,480,726 / 329 | 22 Sep 2026, 12:07:00–12:39:28.700 | 19,488 frames at 100 ms |
| Naples MR Final, match | 138,580,342 bytes | 636,801 | 10 / 636,692 / 99 | 27 Sep 2026, 14:17:00–14:42:00 | 15,001 frames at 100 ms |

Both raw files parsed without malformed JSON lines. Each telemetry message carries exactly one of the six fields used by ingestion. Source session membership is nine boats in PR1 and two in MR Final; the exports contain the same boat counts and four moving marks each. The raw files also contain support assets that the replay intentionally excludes. Export `provenance.source_records` matches the raw record count in each race.

The source's high-rate GNSS position and heading are usually 50 ms apart (20 Hz). Boat SOG, COG, and local true wind are commonly 200–250 ms apart, with the modal interval 250 ms. Official wind speed and direction have 1,897 samples each in PR1 and 1,459 each in MR Final, at about one-second cadence. These are measured streams at different times, not native 10 Hz samples. The pipeline projects positions to local metres, converts speeds from m/s to knots, and interpolates every stream onto the common 100 ms grid. The exported official wind timeline is reduced again to 1 Hz (1,949 / 1,501 points).

## Availability and held values

All tracked boat and official-wind field values inspected in both raw files are present and non-null. This does **not** imply continuous coverage through the window. In PR1, GBR B's six boat streams end at 12:23:37.150, 15 minutes 51.55 seconds before the window closes. The current resampler extends the last value to the end of the export, so the late GBR B track and metrics are held values, not new measurements. Its raw competitor classification becomes `RETIRED` in later events.

Four other PR1 boats have one internal GNSS/heading gap over two seconds: USA 19.05 s (12:31:34.552–12:31:53.602), NZL G 74.60 s (12:32:32.530–12:33:47.130), ITA G 10.85 s (12:34:20.250–12:34:31.100), and NZL B 13.90 s (12:35:41.800–12:35:55.700). The corresponding SOG/COG/wind streams have gaps of similar duration. No tracked MR Final boat stream has a gap over two seconds. Scalar and position interpolation currently bridges these gaps, while values before the first and after the last sample are held. A genuinely absent stream would become zero in `resample_scalar_series` / `resample_circular_series`, which would make missing data look measured.

All exported boat and mark columns have exactly the expected frame count. Repeated adjacent numbers in the export are common, especially for rounded wind speed and SOG; those repeats alone cannot distinguish a stationary value from rounding, interpolation, or a source outage. Coverage must be determined from raw timestamps.

## Events, boundaries, and classification

PR1 has 329 competitor records across nine boats; MR Final has 99 across two. These are changing state snapshots containing start state, course position, leg timings, penalties, and protests, not necessarily one unique event per line. PR1's session messages contain prestart and racing states but no `FINISHED` session state; MR Final has two `FINISHED` session messages. The exports preserve four and six distinct dynamic race/safety boundary snapshots, respectively.

The final raw `classification` is `UNSPECIFIED` for eight PR1 boats and both MR Final boats; only PR1 GBR B is explicitly `RETIRED`. Exported `RANK_1` etc., `DNF`, ranks, and elapsed seconds are reconstruction results. `pipeline/reconstruction.py` uses source leg timings plus geometric crossings, sorts reconstructed finish times, assigns DNF order by completed gates, and applies a GBR B OCS/RET special case. Thus the labels `official_rank`, “official classification,” and “official elapsed time” in code/docs overstate what these files directly establish. A further conflict deserves review: all 24 USA PR1 competitor messages have `start_state.started = false`, while the export assigns USA `RANK_4` with four reconstructed gate crossings. The parser reads a top-level `started` key instead of nested `start_state.started`, so this source state does not enter that check. Treat the result as derived until adjudicated.

PR1 has six exported `virtual_contact_incidents`; MR Final has none. They are simulated geometric overlaps of modeled safety borders, not source penalty or protest records. Manoeuvres, continuous progress, distance sailed, and average speed are also derived. `vmg` is calculated from SOG and COG against the configured **course axis**; it is not a direct sensor reading or wind-axis VMG. A zero `elapsed_s` for DNF/RET in the export means no computed finish time, not a zero-duration race.

## Wind angles and reference value

Raw PR1 official wind direction crosses the 0°/360° boundary twice; the 1 Hz exported timeline also shows two wrap crossings. Shortest-arc interpolation handles these crossings. At the start of this audit, `reference_twd_deg` used an arithmetic mean: PR1 showed 54.3°, while the circular mean of its 1 Hz directions was about 53.6°. The exporter was corrected in this phase to use a circular mean, because an arithmetic mean is invalid near north. MR Final has no official wind wrap. Display and analysis distinguish boat-local wind from the official wind asset.

## Recommended source-to-replay contract

1. Treat the session's race window, gun time, race type, competitor IDs, mark IDs, and official wind ID as source metadata. Keep units explicit: WGS84 degrees for raw GNSS, compass degrees for angles, m/s for raw speed, metres and knots only after transformation.
2. Preserve per-asset/per-field first and last measured timestamps, sample counts, and intervals of missing coverage. Mark grid samples as `measured`, `interpolated`, `held`, or `unavailable`; retain a `gap_duration_ms` or equivalent. Never encode absent measurements as numeric zero. Use a documented maximum interpolation gap, with longer gaps unavailable or visibly flagged.
3. Keep raw event classification and nested start state separate from reconstructed start, gates, finish, classification, and rank. Label ranks and elapsed time `reconstructed` unless an external official results source validates them. Explicitly reconcile USA PR1 before claiming an official start or finish. Deduplicate cumulative penalty/protest snapshots before treating them as incident counts.
4. Use shortest-arc interpolation and a circular mean for compass directions. State whether wind is boat-local or from the official wind asset. Label `vmg` as course-axis VMG and ensure any wind-axis metric uses a separate name and formula.
5. Keep derived tactical metrics and virtual contacts in a provenance block with input streams, formula/version, and any quality flags. An unavailable or held position must not silently produce a precise collision, start-line measurement, distance sailed, or ranking.

## AI token use in this project

The original two audited sources totaled 462,546,001 bytes (about 441 MiB); their replay JSONs totaled 15,083,994 bytes at that audit. Sending either wholesale to an AI assistant would consume enormous context for little insight. `python scripts/analysis_snapshot.py` emits a compact archive overview; `--race <id>` adds quality and coverage counts for one race. Use a deterministic, streaming audit that emits only counts, ranges, anomaly intervals, and a few schema examples. For coding work, provide the relevant function or bounded line range and a concise failing assertion rather than entire files or test logs; cap command output and filter file searches to `pipeline/`, `src/`, `tests/`, and `docs/`. Exclude `Data/`, `dist/`, `node_modules/`, and generated agent metadata from routine AI context. Run deterministic tests/builds locally and pass only the failure excerpt to the model; use a full log only when the excerpt is insufficient. These steps reduce input tokens without discarding the evidence required to verify a change.
