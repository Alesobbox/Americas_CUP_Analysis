# System architecture

## Data and application boundaries

The Python pipeline streams `Data/AC38/*.jsonl` sessions. It exports one column-oriented 100 ms replay per ingested race, a grouped catalog, one historical detail per replay, and a compact historical index.

The React application loads the catalog, a selected replay, and only the analysis artifacts needed by the open panel. `src/engine/catalog.ts` accepts the grouped `regattas[]` catalog and the older flat `races[]` form. `pipeline/historical_analysis.py` owns historical formulas and availability rules; TypeScript reads its exported definitions and values.

## Course rendering

`CourseCanvas.tsx` owns the camera and two Canvas 2D layers. In Map mode, MapLibre provides the geographic base and screen projection. In Grid mode, the map is not mounted: `StaticCourseLayer.ts` paints the water surface, a 250 m world-anchored grid, and the active race and safety polygons. Both modes share the dynamic vessel layer, hit testing, trails, moving marks, and course toolbar. The view choice persists locally.

Coordinates are projected to local metres during ingestion. Map mode converts those metre coordinates to longitude and latitude using the race's exported origin and projection coefficients, then samples the map camera to align the Canvas overlay. Grid mode uses `ViewportMatrix.ts` to transform world metres directly to pixels. The camera fits the active boundary with lower-screen clearance for the toolbar. The map requires tiles for its geographic surface; Grid mode makes no tile requests. Map mode retains OpenStreetMap attribution.

Each replay's `course.sequences` supplies ordered start, top, bottom, and finish gate pairs. `course.start_marks` identifies the sequence-zero line. Moving mark coordinates come from `telemetry.marks`; `course.marks` supplies their identifiers and targets. The renderer draws the marks named by the race rather than assuming one Naples gate layout. Older exports without sequences retain a legacy rendering fallback. Reconstructed gate events and source marks are distinct: a mark's position is telemetry, while a boat's crossing is a reconstruction.

## Boat geometry and contacts

`boatModels.ts` defines class-specific yacht-local hull, cockpit, foil, and rudder polygons in metres, relative to the transom GNSS origin. The AC40 model spans 12.963 m forward and 0.215 m aft, with foil tips at ±5.415 m. The AC75 model spans 21.5 m forward and 0.4 m aft, with foil tips at ±8 m. `contactDetector.ts` defines the corresponding Platform and Keep Clear envelopes and transforms them with the boat heading. These are modeled display/contact polygons; a virtual overlap is not a source protest or umpire ruling.

True scale uses the current camera's pixels per metre for every yacht polygon and its displayed safety envelopes. Enhanced mode applies a class-specific minimum visible length to all those polygons together. Thus a border cannot drift away from the hull when zooming or changing mode. Contacts continue to use metre-space geometry, independent of whether borders are shown or vessels are enlarged for display. At a full-course zoom, a true-scale AC40 can occupy roughly one pixel; use Enhanced or zoom in to identify a boat visually.

## Historical analysis contract

Historical detail and index exports carry method/schema version, formula, unit, window, denominator, source, coverage, and quality. Metric availability is decided from source timestamp coverage in Python. The index aggregates complete boat-race observations within separate fleet and match cohorts; it never treats a 100 ms frame as an independent race. [Historical analysis](historical_analysis.md) is the metric contract.

## Verification and provenance

The 22 September `naples_pr1` benchmark has 19,488 frames and six virtual contacts. The original source audit documents raw stream timing, interpolated and held values, start-state conflicts, and why replay ranks are reconstructed. It also explains why broad raw-file searches are inappropriate. Use `python scripts/analysis_snapshot.py` for bounded inventory, focused tests for changed behavior, then `.\run.ps1 verify` for the repository gate. See [source audit](source_audit.md) and [replay schema](data_schema.md).
