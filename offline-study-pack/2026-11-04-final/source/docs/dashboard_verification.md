# Dashboard implementation and verification

Verified on 15 October 2026.

The dashboard provides Replay, Analysis, Compare and Reports. Boat selection, explicit comparison boat B, race, playhead and visibility are shared. Legacy workbench links open the corresponding main view.

## Verified data coverage

| Output | Current result |
| --- | --- |
| Replay archive | 28 unique races, 224 replayed boat-races |
| Analysis | 28 details, historical index, 4,508 sourced event-feed entries |
| Artifact library | 58 replay, analysis and index artifacts, plus the downloadable inventory itself |
| Historical contract | Schema 2.0, method historical-2; separate event-feed schema unchanged |

Every replay, historical detail and archive index has a discoverable view or download. Full telemetry arrays remain available through JSON exports. Data requests observed in the browser all resolved through the published artifact inventory.

Race-specific session assets corrected 23 team-code assignments. Competitor names, colours, historical cohorts, event labels, contact labels and catalog winners now use the same identity. Telemetry arrays were preserved.

## Behavior and provenance

- Fleet, map, telemetry and Analysis selections update the shared primary boat. Changing A preserves B; selecting the same boat for both produces an explicit prompt.
- The named-boat filter affects map vessels and chart traces while retaining the complete fleet table.
- Playback, seeking, speed, restart at the end, timeline filters, map tools, settings, chart selectors, race picker, notes, exports and detail panels perform their stated actions.
- Notes are saved separately for each race. Race changes reset the race-specific selection and visibility.
- Timeline and events use the Python event feed. Future events and untimed retirements remain hidden at earlier playheads.
- Historical metrics retain Python formulas, coverage, quality, windows and denominator definitions. Analysis and Reports explicitly show retrospective results.
- Heel and pitch are unavailable because no measured attitude channel exists. Current, sea state, temperatures, remaining route distance and map scale explain their unavailability.
- Wind uses replay knots. Sparklines use actual replay samples; racing time gaps are labelled estimates.
- OpenStreetMap is the default, with its attribution. Grid works without tile requests; failed tiles produce an explicit Grid fallback.

## Source-tree cleanup

Every retained frontend production module is reachable from `src/main.tsx`; all ten Python pipeline modules are reachable from ingestion. The automated source-tree contract guards frontend reachability and the closed set of published data directories. Unused UI panels, duplicate render helpers, obsolete migrations, old milestone harnesses, generated environments and stale outputs were removed. The two top-level helpers imported by active Python tests remain.

The style cleanup removed 317 rules for absent UI classes. Replays load their analysis detail directly instead of fetching the entire archive index first. Artifact inventory generation uses validated catalog counts instead of reopening all telemetry arrays. Browser evidence is written outside the repository by default.

## Verification results

`run.ps1 verify` completed successfully:

| Gate | Result |
| --- | --- |
| Frontend | 326 tests passed across 29 files |
| Production build | Passed |
| Python unit tests | 131 passed |
| Reconstruction and workload checks | 123 passed |
| Generated-data integrity | 8 passed |
| Total deterministic tests | 588 passed |

The real-browser suite passed 14 scenario groups. It checked all 28 races in Replay, Analysis and Reports, then ran detailed fleet and match-race interactions at 1586×992, 1280×720 and 390×844. It covered keyboard use, map clicks, selection/filter synchronization, explicit comparison, seeking, playback, settings, notes, exports, all 58 artifact URLs, and missing replay/analysis recovery. It also checked page clipping, OpenStreetMap attribution, live tile responses and offline fallback. The map worker is explicitly emitted by Vite and registered with MapLibre; the production browser check requires its successful response and checks map-context HTTP failures and console errors.

There were no unexpected browser exceptions, console errors or failed application requests. Intentionally injected failures showed their unavailable/recovery states. These are local Chrome browser and viewport checks, including responsive viewport emulation.

The production build passed. A bounded streaming content audit read 87 source/export JSON and JSONL files totaling 7,104,203,679 bytes; no retired-feature content was found. No raw source records were changed. All production data files matched the public exports by SHA-256; every listed download size matched its file.

## Evidence and reproduction

- Deterministic verification log: `%TEMP%/ac40-cleanup-verify.log`.
- Browser results, map network evidence and screenshots: `%TEMP%/ac40-cleanup-browser/`.
- The browser script normally writes to `%TEMP%/ac40-dashboard-qa/`; set `REGATTA_QA_OUTPUT` to select another location.
- [Output and interaction contract](dashboard_contract.md)

Start the local app with `npm run dev`, then run `npm run test:browser`. Run `./run.ps1 verify` for the deterministic gate. Rebuild data discovery with `python scripts/build_artifact_inventory.py` after regenerating artifacts.
