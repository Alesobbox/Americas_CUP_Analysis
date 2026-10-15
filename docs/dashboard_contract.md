# Dashboard contract

## Views and shared state

Replay, Analysis, Compare, and Reports share the race and selected boats. Replay and Compare share the playhead. The visible-boat filter controls map and telemetry traces; the fleet table retains the complete ranking. Selecting A never silently changes B. The default boat selection is temporary.

Keys 1–4 select views. Space plays or pauses; arrows seek five seconds. Shortcuts respect focused controls and typing. Race changes reset selections and visibility. Notes are stored locally per race.

## Sources and availability

The archive contains 28 races and 224 replayed boat-races. Source session assets determine team identity. Replay exports preserve synchronized positions, moving marks, wind, boundaries, and reconstruction provenance. Wind uses exported knots; angles use degrees. Unsupported heel, pitch, current, sea state, and temperatures explain their unavailability.

Historical schema `2.0`, method `historical-2`, is owned by Python. The browser reads exported definitions, values, coverage, and quality. Start analysis contains observed gun-relative geometry and reconstructed crossings. Analysis and Reports are retrospective archive views.

Timeline and event list consume the same Python event feed. Replay displays only events and result states reached by the playhead. Continuous time gaps are labeled estimates derived from progress and leader speed; zero leader speed yields no estimate. Final ranks and elapsed times are reconstructed results.

## Maps and downloads

OpenStreetMap is the default map and retains attribution. Offline Grid has no tile requests. Both modes share vessel geometry, hit testing, marks, trails, and scale controls. Virtual safety-border contacts are geometric overlaps.

Reports exposes every replay, analysis detail, and archive index. Raw telemetry arrays remain downloads. Ingestion refreshes the artifact inventory automatically.

## Verification

`run.ps1 verify` covers frontend tests, build, Python unit tests, reconstruction, and generated-data integrity. `npm run test:browser` checks all 28 races and detailed fleet and match scenarios at 1586×992, 1280×720, and 390×844.
