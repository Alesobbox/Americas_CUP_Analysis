# Replay data schema

The browser loads `public/data/manifests.json` and then the selected `public/data/replays/<id>.json`. `src/types/replay.ts` is the client type contract; `pipeline/export_replay.py` writes the artifact. Keep both in sync when adding a field. Historical analysis has separate versioned artifacts and definitions.

## Catalog

Current manifests contain `regattas[]`. Each regatta has an ID, name, venue, and `races[]`; each race identifies its ID, name, date, and `replay_file`. The client also accepts older flat catalogs with `races[]` and `file`. The catalog separates nine Cagliari and nineteen Naples sessions. A winner field, when present, describes the reconstruction and must carry `result_provenance`; it is not an independently verified official result.

## Replay object

| Field | Meaning |
| --- | --- |
| `id`, `name`, `venue`, `date` | Race identity and location. Date uses `YYYY-MM-DD`. |
| `event_edition`, `boat_class`, `class_evidence` | Event and yacht class are separate. Class evidence includes description, confidence, and source. |
| `course` | Metric reference frame, active mark definitions, source gate order, and changing boundaries. |
| `wind` | Reference direction/speed and a reduced official wind timeline. |
| `chronology` | Gun time and replay window, in Unix milliseconds. |
| `competitors[]` | Boat/team identity, source classification, reconstructed starts, gates, manoeuvres, and summaries. |
| `telemetry` | Shared 100 ms timestamps and parallel boat/mark columns. |
| `safety_borders`, `virtual_contact_incidents` | Model envelopes and precomputed geometric overlaps. These are not umpire decisions. |
| `provenance` | Source record count, sample interval, measured streams, and derived-field descriptions. |

`boat_class` is `AC40`, `AC75`, or `UNKNOWN`. Class evidence is `CONFIRMED`, `INFERRED`, or `UNKNOWN`. A replay consumer must treat absent optional fields as unavailable, not as a zero measurement.

## Course and marks

`course.origin` is a WGS84 latitude/longitude anchor; `course.projection.k_lat` and `k_lon` convert angular offsets to local metres. Local `x` is east and `y` north. `course.axis_deg` is a true bearing, and `course.length_m` is a metre distance. `course.boundaries.race` and `.safety` are polygons of `[x,y]` pairs; `boundary_timeline[]` supplies timestamped changes.

`course.marks` is keyed by the actual RM code, with name, target point, and optional telemetry asset ID, role, and code. `course.sequences[]` identifies each leg's port and starboard mark and gate type (`START`, `TOP`, `BOTTOM`, `FINISH`). `course.start_marks` names the two sequence-zero marks. The active line may use RM3/RM7 in Cagliari and different pairs in Naples. Mark positions at a replay frame come from `telemetry.marks`, not from assuming a fixed target.

## Parallel telemetry columns

Every boat's array has exactly the length of `telemetry.timestamps`. Ingestion interpolates source streams with different sample rates onto that 100 ms grid. A repeated value in an array does not prove it was measured at that frame; source timestamp coverage belongs in the historical analysis quality contract.

| Column | Unit | Meaning |
| --- | --- | --- |
| `x`, `y` | m | Projected position, east and north. |
| `heading`, `cog`, `twd` | degrees clockwise from north | Yacht heading, course over ground, and local true-wind direction. |
| `sog`, `vmg`, `tws` | knots | Speed over ground, replay course-axis VMG, and local true-wind speed. |
| `twa` | signed degrees | Local wind angle relative to the bow. |
| `progress_m` | m | Reconstructed course progress for replay ranking. |
| `leg` | integer | Reconstructed active leg; zero is prestart. |

`telemetry.marks[markId]` has parallel `x[]` and `y[]` arrays. `wind.timeline[]` has timestamp `t`, direction `twd`, and speed `tws`. The replay's fixed-axis `vmg` is retained for compatibility; historical leg-directed and wind-relative VMG are different metrics defined in [historical_analysis.md](historical_analysis.md).

## Source and result boundaries

Source classification and recorded gate times must remain distinct from reconstructed crossing times, finish rank, and elapsed time. `virtual_contact_incidents[]` are SAT overlaps of modeled Keep Clear envelopes, not recorded penalties. Historical scalar metrics include quality, coverage seconds, and null with a reason when unavailable. See [source_audit.md](source_audit.md) for source availability and reconstruction limits.
