# Dashboard contract

## Views and shared state

Replay, Analysis, Compare, Reports, and Forecast share the race and selected boats. Replay and Compare share the playhead. The visible-boat filter controls map and telemetry traces; the fleet table retains the complete ranking. Selecting A never silently changes B. The default boat selection is temporary.

Keys 1â€“5 select views. Space plays or pauses; arrows seek five seconds. Shortcuts respect focused controls and typing. Race changes reset selections and visibility. Notes are stored locally per race.

## Sources and availability

The archive contains 28 races and 224 replayed boat-races. Source session assets determine team identity. Replay exports preserve synchronized positions, moving marks, wind, boundaries, and reconstruction provenance. Wind uses exported knots; angles use degrees. Heel and current are omitted from the operational KPI/HUD because the archive has no measured channels; the technical Sources disclosure records this limitation. Supported channels retain genuine missing-sample states. The header's sea height and temperatures use separately acquired historical Open-Meteo model data for the race location and UTC hour, visibly marked as estimates. They remain separate from recorded wind and causal probability inputs. Missing API fields retain a reason; data from a different race or hour is never substituted. See [environment data](environment_data.md).

Historical schema `2.0`, method `historical-2`, is owned by Python. The browser reads exported definitions, values, coverage, and quality. Start analysis contains observed gun-relative geometry and reconstructed crossings. Analysis and Reports are retrospective archive views.

Timeline and event list consume the same Python event feed. Replay displays only events and result states reached by the playhead. Continuous time gaps are labeled estimates derived from progress and leader speed; zero leader speed yields no estimate. Final ranks and elapsed times are reconstructed results.

## Maps and downloads

OpenStreetMap is the default map and retains attribution. Offline Grid has no tile requests. Both modes share vessel geometry, hit testing, marks, trails, and scale controls. Virtual safety-border contacts are geometric overlaps.

Reports exposes every replay, analysis detail, and archive index. Raw telemetry arrays remain downloads. Ingestion refreshes the artifact inventory automatically.

## Verification

`run.ps1 verify` covers frontend tests, build, Python unit tests, reconstruction, and generated-data integrity. `npm run test:browser` checks all 28 races and detailed fleet and match scenarios at 1586Ã—992, 1280Ã—720, and 390Ã—844.

## Team analytics

The five current views retain shared navigation and state through the redesigned shell. Replay and Compare include Tactical insights at the shared playhead. Insights report only an exported snapshot at or before that playhead and become unavailable after the snapshot expiry. Direction and speed coverage remain distinguishable. A five-minute trend projection is conditional, unvalidated linear extrapolation of a stable recent window, never a certain wind-shift arrival time. Recorded measurement timestamps support retrospective causality; arrival-time ordering is unavailable.

Analysis adds Boat performance and Team debrief for the selected boat. The circular chart uses Python-exported six-axis indexes; 100 represents eligible other boats on matching completed legs. Missing axes remain unavailable and are not drawn as zero. The adjacent evidence table exposes absolute values, peer means, source coverage, counts and reasons. Team debrief prioritizes observed peer leg-time deficits and detector speed-loss episodes with replay links; it does not attribute those differences to a tactical cause. These retrospective summaries remain in Analysis.

All extensions are included in the existing downloadable analysis details in Reports. `npm run analytics` refreshes them and the inventory without replacing replay telemetry. See [team analytics](team_analytics.md) for the exact method and verification evidence.


## Annotation revision

Analysis uses white surfaces in Race Report and Historical View. The six-axis performance chart supports keyboard/touch axis selection, all-comparable or single-leg scope, a focused detail plot, full per-leg and peer evidence, and replay links that preserve race, boat and the exported interval. The descriptive overall profile is labelled heuristic; matched versus expected legs and exclusions remain visible. Numerical performance-1 formulas are unchanged.

Reports uses the same canonical historical metrics and availability as Analysis, never a legacy replay average fallback. Six or fewer curated current-race exports lead the page; a collapsed, searchable Technical data and provenance explorer retains every published output and older forecast version. The catalog uses schema 1.1 with explicit kind/status/scope/primary_download metadata and accepts legacy 1.0 catalogs. Two tidy CSV exports per race retain metric definitions, quality, coverage, missing reasons and peer evidence.

The Cup card separates the pinned baseline rule bounds, a selected transfer assumption and the overall outer envelope. Scenario diagnostics expose actual draw counts, unresolved mass/stages, numerical error, mapping provenance and model cutoff. Conservative unresolved intervals stay intervals; scenario endpoints need not sum to one. See [implementation evidence](annotation_revision_verification.md).

## Interface redesign

The [current visual system](design-system.md) follows the user-approved Google Store-inspired plan. The shell uses a shared light palette and self-hosted DM Sans; identity comes from real courses, boats, team colors, and telemetry. Replay remains the default destination. Playback sits directly beneath the course; boat visibility controls remain local to the views they affect, and the fleet retains every competitor. Map, Grid, scale, trails, camera controls, fullscreen, events, notes, and evidence stay available.

Analysis inline mode is a page rather than an embedded modal. Compare distinguishes per-boat values from measurements of the pair. Forecast's local question navigation preserves the live, pre-race, and Cup targets and their separate readiness/evidence; Cup conditioning does not follow the replay playhead. Reports retains canonical metrics and the complete artifact explorer. Race-library previews are presentation metadata and cannot replace or redefine any historical metric.

Layouts reflow for phones and short desktop viewports without reducing essential labels to tiny text. Keyboard focus, reduced motion, copyable evidence, non-hover access, unavailable values, and recoverable loading failures are part of the interface contract. See [redesign verification](ui_redesign_verification.md) for the recorded implementation checks.

## Boat visibility and forecast controls

Replay defaults to the enhanced boat size. Screen-space team labels and optional signed course-axis VMG remain readable when the course is zoomed out. Labels avoid other labels, vessel anchors, course badges and the wind display where space allows; leader lines retain the exact vessel positions. True metric scale is available separately and does not remove labels. Visual enlargement never changes physical geometry or contact calculations.

Trail visibility is independent of fleet visibility: All boats, Highlighted boats, or None. Highlighted trails follow A and the explicitly enabled B. Trail colour can use team, speed or course-axis VMG, and trail length remains adjustable. Hiding trails never removes boats or changes the full fleet ranking.

Boat performance distinguishes the solid blue selected profile from the dashed other-boats baseline. Six signed difference rows show the exported index minus 100, with direct above/below-mean wording. They share a race-level display scale; the browser does not recompute historical indexes from raw means. Axis, leg, coverage and peer evidence remain inspectable.

Visible result and quality labels use Result and Calculated from telemetry. Internal source fields, quality codes and downloadable artifacts retain their original provenance. The result note explains that finishing classifications have not been independently verified.

Forecast can prepare exact custom wind-speed conditions through the local dashboard. The server runs the existing Python scenario exporter, reports progress and refreshes the published scenario without rebuilding the interface. Unsupported direction response is explained before submission, with an explicit Use 0° offset action. No nearby preset or different condition is silently substituted. See [forecast implementation](forecasting_implementation.md) and [browser feedback verification](browser_feedback_verification.md).
