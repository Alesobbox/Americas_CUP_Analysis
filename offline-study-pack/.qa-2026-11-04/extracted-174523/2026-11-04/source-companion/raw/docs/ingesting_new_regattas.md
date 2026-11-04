# Ingesting and Selecting Races

The AC40 Tactical Replay application lists the 28 ingested source sessions in two regattas: nine Cagliari races and nineteen Naples races. Reconstruction uses each session's projection, sequence-0 start marks, subsequent gate pairs, and four- or six-leg course. Three GBR B entries in 22 September practice sessions have no replay telemetry and do not become replayed boat-races.

## How It Works

1. **Automatic Batch Ingestion**:
   When you place raw `.jsonl` telemetry files into the `Data/` directory, running the ingestion pipeline:
   ```powershell
   npm run ingest
   # or
   powershell -NoProfile -ExecutionPolicy Bypass -File ./run.ps1 ingest
   ```
   discovers all `.jsonl` files in `Data/` and reconstructs the currently mapped AC40 sessions. The exact 22 September Naples PR1 file retains the `naples_pr1` benchmark ID; the 23 September PR1 uses `26_09_23_nap_ipr_pr1`. Each successful race writes `public/data/replays/<race_id>.json` and `public/data/analysis/<race_id>.json`, then rebuilds the historical index. Re-ingesting the same race replaces its analysis and leaves the archive count unchanged. A new venue, boat class, asset map, or course format still requires checking its source contract before ingestion.

2. **Catalog Indexing**:
   The pipeline updates `public/data/manifests.json` with separate `cagliari_2026` and `naples_2026` groups, each race's venue and date, and its replay path. A `winner` is present only when a final-leg finish can be reconstructed; it is explicitly marked as reconstructed, not an independently verified official result. The exporter also syncs to `dist/data/` when it exists.

3. **In-App Race Selection**:
   In the browser, click the **`RACES ▾`** button in the top navigation bar. The modal presents all available races grouped by regatta, showing their venue, date, and status (`CURRENT` vs `OPEN`). Clicking any race immediately loads its full replay, telemetry traces, and dynamic buoy positions without reloading the page.

4. **Single-File Ingestion**:
   To ingest a specific race file individually:
   ```powershell
   python pipeline/run_pipeline.py --input "Data/26 09 27 NAP IPR MR Final.jsonl"
   ```

The **Analysis** button opens the current race report or the historical archive. Race detail is fetched only when selected. Metric formulas, coverage rules, and unavailable cases are documented in [historical_analysis.md](historical_analysis.md). `public/data/analysis/index.json` counts replayed boat-races, not telemetry frames or source entries without a track. The current ingestion configuration recognizes the known AC40 asset IDs; a new fleet with different IDs or a different boat class requires updating `pipeline/config.py` before ingestion.
