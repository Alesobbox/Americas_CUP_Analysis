# AC40 replay dashboard

The dashboard has five views: Replay, Analysis, Compare, Reports, and Forecast. It exposes 28 source sessions: nine Cagliari races and nineteen Naples races, containing 224 replayed boat-races.

## Runtime and data flow

- `src/main.tsx` mounts `App.tsx`, which owns race, playhead, primary boat, comparison boat, and visibility state.
- `src/components/dashboard/` contains the dashboard controls. `canvas/` renders boats, marks, boundaries, and trails. `panels/ComparisonPanel.tsx` compares boats at the shared playhead. `modals/` provides race selection and historical analysis.
- `src/engine/` loads data, interpolates replay frames, and calculates instantaneous replay geometry.
- `pipeline/run_pipeline.py` streams `Data/*.jsonl`, reconstructs events, and exports replay and historical artifacts.
- `pipeline/historical_analysis.py` owns historical formulas, units, availability rules, coverage, and event feeds. The browser reads its metrics.
- `scripts/build_artifact_inventory.py` publishes replay, analysis, and index downloads in Reports.
- `pipeline/environment.py` acquires historical model estimates for the header's sea height and temperatures, with source hashes and hourly availability. These provide replay context separately from the recorded wind and forecasting inputs. See [environment data](docs/environment_data.md).
- `scripts/analysis_snapshot.py` provides a bounded archive overview without printing telemetry arrays.
- `pipeline/prediction/` builds causal raw-data features, audited completion, joint ranking references, correlated Monte Carlo candidates and the AC38 tournament adapter. Forecast consumes immutable, content-addressed static JSON; it never fits a model in TypeScript. See [forecast implementation and evidence gates](docs/forecasting_implementation.md).

Source measurements, interpolation, reconstructed results, estimated continuous gaps, and unavailable channels remain distinguishable. Source session assets determine boat identity and course marks. Map mode uses OpenStreetMap with attribution; Grid mode makes no tile requests. Virtual contacts describe geometric overlaps rather than official rulings.

Historical analysis uses schema `2.0` and method `historical-2`. Event feeds retain their separate schema `1.0` and method `event-feed-1`. Replay compatibility is unchanged.

## Interface and race previews

The current interface follows the approved [Google Store-inspired redesign](docs/google_store_ui_redesign_plan.md): a shared light palette, self-hosted DM Sans, a course-first Replay with playback below, distinct workspaces, and a visual race library. [Design-system rules](docs/design-system.md) own visual decisions; [redesign verification](docs/ui_redesign_verification.md) records implementation evidence.

The library loads the optional `public/data/presentation/race_previews.json` (`1.0`, `course-preview-1`) rather than every replay. It contains north-up static course schematics, replayed boat counts, class/type, and source hashes; it does not contain tracks or historical metrics. After regenerating replay/analysis artifacts, refresh it with `.venv/Scripts/python.exe scripts/build_race_previews.py`. Missing previews retain a usable text-first race catalog.

## Verification

Run focused tests, then `run.ps1 verify`. Run `npm run test:browser` against a local server for browser interactions. See [dashboard behavior](docs/dashboard_contract.md), [architecture](docs/architecture.md), [historical formulas](docs/historical_analysis.md), [source audit](docs/source_audit.md), and [ingestion](docs/ingesting_new_regattas.md).

Team analytics adds playhead-aware Tactical insights in Replay/Compare and a peer-relative Boat performance radar plus replay-linked Team debrief in Analysis, within the existing design. Python exports all new calculations as optional versioned extensions of historical details. Refresh them with `npm run analytics`; see [team analytics](docs/team_analytics.md).

The annotation revision adds white Analysis, axis/leg performance evidence with interval review, canonical Reports and CSVs, a collapsed technical archive, and inspectable Cup uncertainty. See [revision verification](docs/annotation_revision_verification.md). For evidence-only refreshes, use `.venv/Scripts/python.exe scripts/refresh_team_analytics.py --performance-only` without reading raw telemetry.
