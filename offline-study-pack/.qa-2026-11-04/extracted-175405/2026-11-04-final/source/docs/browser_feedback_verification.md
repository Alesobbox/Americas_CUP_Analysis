# Browser feedback implementation and verification

Verified on 4 November 2026 against Naples Practice Race 1 at replay time 240 seconds, including the reported 775 × 704 viewport. This extends the [visual redesign](ui_redesign_verification.md).

## Delivered behavior

- Boats default to an enhanced visible size. Every on-screen boat has a readable team label and optional signed course-axis VMG, with leader lines to its actual position. The selected A has a solid blue border; an explicitly highlighted B has a dashed purple border. Labels are placed away from one another, vessel anchors, course badges and the lower wind display where space allows. True metric scale remains selectable; physical boat and contact geometry are unchanged.
- Trail visibility supports All boats, Highlighted boats and No trails. Highlighted means A plus the explicitly enabled B. Trail colour supports team, speed and VMG; length is available under Trail settings & boat B. All boats and the complete fleet ranking remain visible when only highlighted trails are drawn.
- Grid/Map switching preserves the current metric scale and center, including the first switch from Grid. The map camera derives its zoom from the current viewport rather than a stale cached zoom. A browser regression checks scale, center and all nine labels at 775 pixels.
- Forecast can generate exact wind-speed scenarios through the local dashboard, show progress, retry failures and load the published result. Changing conditions while preparation is running clears stale display state and permits retrying the original inputs. Development and local preview share the same workspace publication lock, including publisher-child ownership.
- The current forecasting model has no validated direction response. Nonzero offsets, including 17°, are explained before submission. Use 0° offset is an explicit action; there is no silent condition substitution. Unsupported historical coverage still produces an unavailable reason. Supported speeds can have identical expectations because the current model uses a conservative zero-effect wind reference.
- Reports uses Result, and visible quality/provenance wording uses Calculated or Calculated from telemetry. Source quality codes and downloads retain their provenance. The note that finishing classifications have not been independently verified remains visible. An expanded-disclosure audit found no occurrence of the old wording in the five workspaces.
- Performance uses a solid selected profile, dashed peer baseline and an explicit legend. Six signed difference rows show the exported index relative to 100, with above/below-mean wording, a shared difference scale and linked evidence. The absolute readings, eligible peer baseline, leg scope, missing values and coverage remain available. Historical indexes are not recalculated in the browser.

## Verification

`run.ps1 verify` covers the full frontend suite and production build, Python unit tests, replay tests, generated-data integrity, published forecasts, environment data and team analytics. Browser checks run against the production preview on port 4173.

| Check | Passed |
| --- | ---: |
| Frontend tests | 406 |
| Python unit tests | 291 |
| Replay end-to-end tests | 123 |
| Generated-data integrity tests | 8 |
| Dashboard browser groups | 18 |
| Annotation browser groups | 18 |
| Forecast browser groups, including the real archive | 19 |
| Redesign and responsive browser groups | 10 |
| Browser-comment regression groups | 6 |

The browser groups cover all 28 race fields, source-only scheduled entrants, Map/Grid and offline fallback, missing-data states, keyboard/focus interactions, exact-condition generation fixtures, changing conditions during generation, performance evidence, downloads and layouts down to 320 pixels. No application exceptions or failed application requests were found. The six browser-comment groups run with `npm.cmd run test:feedback`.

## Real generation and artifact reconciliation

Real dashboard generation was verified at 13 knots and 13.25 knots, both at 0°, without modifying Python forecast source or manually running its exporter. Both completed with estimated numeric expected-position output for the complete scheduled field. The second run also verified that the publisher child was recorded in the shared lock before generation started; the lock was removed on completion. A further completed 12-knot scenario is also present in the final publication. These runs verify the workflow, not predictive accuracy or calibration.

| Conditions | Immutable scenario |
| --- | --- |
| 13 kt, 0° | `scenarios/c76e537e834b8d39450c21eb773499a671fe50ba9629899585a7e19d43679b04.json` |
| 13.25 kt, 0° | `scenarios/4355e67cca423703a9a6f482eed6c021989b2eb50196dbb1c17c9d7efae063d8.json` |
| 12 kt, 0° | `scenarios/987b8ca1d40c4ace0c386847ddc02db6b71005be1beb731c481ac050aa3346d8.json` |

Compared with the 497-file snapshot taken before this feedback work, the public data directory has nine new immutable objects: three scenarios, three model cards and three source manifests. Only `predictions/index.json` and `artifacts.json` changed among existing files. No old files were removed; every pre-existing replay, analysis, environment and immutable forecast object remains byte-identical. Reports lists 505 downloadable artifacts. All 506 public data files, including the inventory itself, match their built copies byte for byte. This snapshot already contained the earlier redesign and analytics work; it is not a comparison with Git HEAD.

Local generation needs the prepared forecasting dataset and Python environment. Static-only hosting can display published scenarios but cannot launch a new local generation job. See the [forecast workflow and model limitations](forecasting_implementation.md#generate-from-the-dashboard).
