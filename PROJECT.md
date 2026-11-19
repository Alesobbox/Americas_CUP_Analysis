# AC40 replay dashboard

The dashboard has four views: Replay, Analysis, Compare, and Reports. It exposes 28 AC38 Preliminary Regatta sessions: nine Cagliari races and nineteen Naples races, containing 224 replayed boat-races.

## Runtime and data flow

- `src/main.tsx` mounts `App.tsx`, which owns race, playhead, primary boat, comparison boat, and visibility state.
- `src/components/dashboard/` contains the dashboard controls. `canvas/` renders boats, marks, boundaries, and trails. `panels/ComparisonPanel.tsx` compares boats at the shared playhead. `modals/` provides race selection and historical analysis.
- `src/engine/` loads data, interpolates replay frames, and calculates instantaneous replay geometry.
- `pipeline/run_pipeline.py` streams `Data/AC38/*.jsonl`, reconstructs events, and exports replay and historical artifacts.
- `pipeline/historical_analysis.py` owns historical formulas, units, availability rules, coverage, and event feeds. The browser reads its metrics.
- `scripts/build_artifact_inventory.py` publishes replay, analysis, environment, and index downloads in Reports.
- `pipeline/environment.py` acquires retrospective Copernicus Marine, Università Parthenope, and Open-Meteo `environment-2` context for the header's sea height, currents, and temperatures, with SHA-256 provenance and hourly availability. See [environment data](docs/environment_data.md).
- `scripts/analysis_snapshot.py` provides a bounded archive overview without printing telemetry arrays.

Source measurements, interpolation, reconstructed results, estimated continuous gaps, and unavailable channels remain distinguishable. Source session assets determine boat identity and course marks. Map mode uses OpenStreetMap with attribution; Grid mode makes no tile requests. Virtual contacts describe geometric overlaps rather than official rulings.

Historical analysis uses schema `2.0` and method `historical-2`. Event feeds retain their separate schema `1.0` and method `event-feed-1`.

## Interface and race previews

The interface follows the Google Store-inspired visual system: a shared light palette, self-hosted DM Sans, a course-first Replay with playback below, distinct workspaces, and a visual race library. [Design-system rules](docs/design-system.md) govern layout, contrast, and interaction contracts.

The library loads the optional `public/data/presentation/race_previews.json` (`1.0`, `course-preview-1`) rather than every replay. It contains north-up static course schematics, replayed boat counts, class/type, and source hashes; it does not contain tracks or historical metrics. After regenerating replay/analysis artifacts, refresh it with `python scripts/build_race_previews.py`. Missing previews retain a usable text-first race catalog.

## Verification

Run `python scripts/verify.py --with-format` (or `.\run.ps1 verify` on Windows). Run `npm run test:browser` against a running preview server for Playwright verification. See [dashboard behavior](docs/dashboard_contract.md), [architecture](docs/architecture.md), [data schema](docs/data_schema.md), [historical formulas](docs/historical_analysis.md), [source audit](docs/source_audit.md), and [ingestion](docs/ingesting_new_regattas.md).

Team analytics adds playhead-aware Tactical insights in Replay/Compare and a peer-relative Boat performance radar plus replay-linked Team debrief in Analysis. Refresh them with `npm run analytics` (or `python scripts/refresh_team_analytics.py --performance-only` without scanning raw JSONL telemetry); see [team analytics](docs/team_analytics.md).

## AC38 statistical research

`pipeline/polar/` owns sample-level conditional distributions and grouped uncertainty. `pipeline/research/` owns matched model/wind/environment comparisons, timing accounting and probabilistic wind experiments. Run `npm run research` after source/environment updates. Versioned research reports and their dependency receipt are exposed in Analysis and Reports; see [methods](docs/ac38_research.md).
