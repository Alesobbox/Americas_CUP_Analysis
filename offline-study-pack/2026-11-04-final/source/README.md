# America's Cup AC40 replay dashboard

Replay and historical analysis for 28 sessions: nine Cagliari races and nineteen Naples races, containing 224 boat-race tracks.

## Dashboard views

- **Replay:** boat and moving-mark tracks, wind, playhead-aware Tactical insights, reconstructed events, standings, telemetry, and local race notes.
- **Analysis:** a white workspace with exported metrics, coverage, team history, interactive circular performance comparisons and a replay-linked Team debrief. Choose a dimension and leg to inspect exact peer evidence. Python owns historical calculations.
- **Compare:** two explicitly selected boats at the shared playhead.
- **Reports:** canonical race metrics, summary/performance CSVs and concise race downloads, plus a collapsed searchable technical archive.
- **Forecast:** experimental race forecasts and gated event/Cup evidence, with separate baseline rule bounds, transfer scenarios and numerical error.

Map mode uses OpenStreetMap with attribution. Offline Grid mode uses a 250 m metric grid without tile requests. True metric scale and enhanced visibility are available in Settings. Unsupported channels explain their unavailability. Reconstructed results and virtual contacts are not official classifications or umpire decisions.

The interface follows the approved Google Store-inspired [design system](docs/design-system.md): a shared light palette, locally hosted DM Sans, a course-first Replay layout, and a searchable race library with lightweight source-course previews. See [implementation and verification](docs/ui_redesign_verification.md). Ingestion refreshes previews automatically; refresh them independently with `.venv/Scripts/python.exe scripts/build_race_previews.py`, then rebuild the download inventory with `.venv/Scripts/python.exe scripts/build_artifact_inventory.py`.

## Run locally

From Windows Command Prompt:

```cmd
cd /d "C:/Workspace/Americas Cup/2D_regatta_replay"
npm ci
npm run dev
```

Stop the development server with Ctrl+C before reinstalling dependencies.

Regenerate replay and historical artifacts with `npm run ingest`. Refresh the team analytics from existing historical evidence and streamed source wind with `npm run analytics` (replay telemetry is preserved). See [team analytics](docs/team_analytics.md) for formulas and limits. Run frontend tests, production build, Python tests, reconstruction checks, and artifact integrity checks with `npm run verify`. Set `REGATTA_PYTHON` to a Python executable if it is installed outside the default Windows location. With the development server running, `npm run test:browser` checks the dashboard using installed Chrome.

`npm run test:redesign` checks the race library's bounded loading, dialog focus, fullscreen, font loading, and all five workspace layouts down to 320 px. Set `REGATTA_URL` when using a different preview address.

## Data flow

```text
Data/*.jsonl
  → pipeline/run_pipeline.py
  → public/data/replays/*.json
  → public/data/analysis/*.json + index.json
  → public/data/manifests.json + artifacts.json
  → Replay / Analysis / Compare / Reports
```

When adding a race, ingest its source and confirm the replay, analysis index, and artifact inventory agree. `python scripts/analysis_snapshot.py` prints a compact overview. Raw sources are streamed; telemetry arrays remain downloads.

See [architecture](docs/architecture.md), [historical metrics](docs/historical_analysis.md), [source audit](docs/source_audit.md), [schema](docs/data_schema.md), and [ingestion](docs/ingesting_new_regattas.md).

Map tiles: [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
