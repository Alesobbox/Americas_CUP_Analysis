# UI redesign verification

Date: 3 November 2026. Status: implemented and verified against the production build.

The approved [redesign plan](google_store_ui_redesign_plan.md) is implemented across Replay, Analysis, Compare, Reports, Forecast, and the race library. [The interface system](design-system.md) records the current visual authority and tokens.

## Delivered interface

- One canonical light palette, self-hosted DM Sans variable font with OFL license/provenance, consistent controls, readable headings, and selectable evidence text.
- A simpler navigation shell with separate race context, recorded wind, and a disclosure for historical environment estimates.
- A larger course area with controls above the scene, playback directly beneath it, selected-boat values, and a complete fleet rail. Short-height and phone layouts reflow these regions. Fullscreen retains camera and playback controls.
- Pale Grid water, restrained map tiles, neutral readable labels, and contrast under-strokes for team trails. Vessel geometry, true/enhanced scale, hit testing, moving marks, and team/VMG identity remain intact.
- A searchable race library with actual source-course schematics, clear race metadata, empty/fallback states, focus containment/return, and background scroll locking.
- Full-page inline Analysis with its existing report/history, radar/axis/leg evidence, debrief, provenance, and interval-review interactions.
- Balanced A/B comparison, aligned per-boat values, and a separate pairwise section retaining each sign and unit.
- Three locally navigable forecast questions, visible readiness for all three, distinct conditioning, probability marks, Cup interval marks, and complete uncertainty/source evidence.
- Canonical Reports metrics, compact download rows, and the complete searchable technical archive, including the new preview index.

## Data and presentation artifacts

`scripts/build_race_previews.py` publishes `public/data/presentation/race_previews.json`, schema `1.0`, method `course-preview-1`. Its 28 entries describe north-up static source-course schematics, replayed boat count, class, race type, and replay source/hash. They contain no tracks or historical metric values. The index is approximately 18.8 KB.

The generator runs after ingestion and analysis-index export, before the artifact inventory is rebuilt. It can also run independently:

```text
.venv/Scripts/python.exe scripts/build_race_previews.py
.venv/Scripts/python.exe scripts/build_artifact_inventory.py
```

The library shares one cached index request across mounts, including React development StrictMode. A browser check confirmed one request and one successful response, with no additional race replay downloads. Missing artwork leaves the searchable catalog usable.

Published-data reconciliation against the pre-redesign baseline:

- 495 existing data files retain identical SHA-256 hashes, including all replay, historical analysis, environment and prediction files.
- `artifacts.json` changes to expose the new presentation index.
- `presentation/race_previews.json` is the only added data file; none were removed.
- All 497 files under `public/data` match their production copies under `dist/data` byte for byte.
- The inventory exposes 496 downloadable files, excluding itself, and retains 28 races / 224 replayed boat-races. Forecast verification retains the separate 227 scheduled-entry denominator.

## Final repository gate — passed

Command: `.\run.ps1 verify`.

| Check | Result |
| --- | --- |
| Frontend | 35 files / 385 tests passed |
| TypeScript and production build | Passed |
| Python unit tests | 291 passed |
| Reconstruction/workload tiers 1–4 | 123 passed |
| Generated-data integrity | 8 passed |
| Prediction artifact verification | Passed for 28 races |
| Historical environment verification | Passed for 28 races / 18 response objects |
| Team analytics verification | Passed for 28 races / 224 boat-races / 3,455 snapshots |

The build emits a chunk-size advisory for the main bundle, which includes MapLibre; the production build succeeds. No new runtime framework or package dependency was introduced.

Intentional test updates follow sentence-case map labels and the shared pale/wind palette while retaining callback, opacity, geometry, coverage, and causal assertions. New preview checks cover determinism, source hashes, bounded coordinates, unknown type, path confinement, and inventory visibility.

## Browser verification against the production build — passed

Production preview: `http://127.0.0.1:4173` during verification.

| Suite | Result | Coverage |
| --- | --- | --- |
| `tests/browser/dashboard.mjs` | 18 groups; zero browser or application-request errors | All 28 races, fleet/match at 1586×992, 1280×720, 1096×704, 390×844; playback, selection/filter independence, notes, keyboard, event gating, debrief links, archive/downloads, missing-feed/replay recovery, Map/Grid |
| `tests/browser/annotations.mjs` | 18 groups; zero browser/request errors; 56 captures | White Analysis, axis/leg evidence, interval review, canonical Reports, complete archive and Cup sensitivity/provenance |
| `tests/browser/forecast.mjs --real` | 17 groups | Three question tabs, keyboard, exact scenarios, publication cutoffs, backseeking, stale-state clearing, race reset, errors, real Cup evidence, all 28 fields and 227 scheduled entries |
| `tests/browser/redesign.mjs` | 10 groups | Local font, course dominance, one compact preview request, no other replay downloads, missing artwork, dialog focus/return, fullscreen, all five views without document overflow at 1440, 1280, 768, 390 and 320 px |

The production map worker returned HTTP 200. The map run recorded 44 tile requests and 18 successful tile responses; attribution remained available. The suite separately verified offline fallback, and Grid made no tile requests.

The new suite is available as `npm run test:redesign`, using `REGATTA_URL` to select a development or production preview.

## Visual and accessibility checks

Screenshots were inspected across all five workspaces, the race library, and phone layouts. Review caught and corrected competing style order, cramped 320 px navigation, inherited Compare styling, and the map toolbar occluding race content at short heights. The toolbar now occupies its own row above the course.

Additional checks:

- DM Sans loaded from the local 240,164-byte font file; no external font request was required.
- Delayed loading and forced catalog failure fit 390 px and retained Retry.
- Settings and race-library dialogs keep keyboard focus and return it to the opener.
- A 200% desktop zoom equivalent (640×360 CSS pixels at device scale 2 for a 1280×720 display) had no document overflow.
- Reduced-motion CSS produced zero-duration control transitions.
- Canonical contrast checks: primary text on white 16.10:1; secondary text on white 6.05:1; white on primary blue 5.37:1; preview labels on pale water 5.36:1. These are checks of the specified pairs, not a complete accessibility certification.

Final review images are saved in the chat's visualization directory as `regatta-redesign-desktop.png`, `regatta-redesign-library.png`, and `regatta-redesign-phone.png`. The browser suites also retain their detailed captures/results in their reported local output directories.

Historical formulas, source definitions, forecast computations and their statistical interpretation were not changed by this redesign. Software verification does not establish predictive calibration.
