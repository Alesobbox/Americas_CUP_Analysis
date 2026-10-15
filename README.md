# America's Cup AC40 replay dashboard

Replay and historical analysis for 28 sessions: nine Cagliari races and nineteen Naples races, containing 224 boat-race tracks.

## Dashboard views

- **Replay:** boat and moving-mark tracks, wind, reconstructed events, standings, telemetry, and local race notes.
- **Analysis:** exported race metrics, definitions, units, coverage, quality, and team history. Python owns historical calculations.
- **Compare:** two explicitly selected boats at the shared playhead.
- **Reports:** retrospective summaries and downloads for every replay, analysis detail, and archive index.

Map mode uses OpenStreetMap with attribution. Offline Grid mode uses a 250 m metric grid without tile requests. True metric scale and enhanced visibility are available in Settings. Unsupported channels explain their unavailability. Reconstructed results and virtual contacts are not official classifications or umpire decisions.

## Run locally

From Windows Command Prompt:

```cmd
cd /d "C:/Workspace/Americas Cup/2D_regatta_replay"
npm ci
npm run dev
```

Stop the development server with Ctrl+C before reinstalling dependencies.

Regenerate replay and historical artifacts with `npm run ingest`. Run frontend tests, production build, Python tests, reconstruction checks, and artifact integrity checks with `npm run verify`. Set `REGATTA_PYTHON` to a Python executable if it is installed outside the default Windows location. With the development server running, `npm run test:browser` checks the dashboard using installed Chrome.

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
