# Working in this repository

Read `PROJECT.md` and the relevant file under `docs/` before changing behavior. Historical metric formulas and availability rules are owned by `pipeline/historical_analysis.py` and documented in `docs/historical_analysis.md`. The UI reads exported metrics; do not recalculate them in TypeScript.

Keep AI context small and evidence-rich. Exclude `Data/`, `dist/`, `node_modules/`, and `.agents/teamwork/` from routine searches and prompts. The current archive has 28 raw files totaling 6,866,006,601 bytes (about 6.87 GB / 6.39 GiB); the original two-file subset was about 441 MiB. Stream sources with scripts and report counts, ranges, gaps, and a few bounded examples. Read a function or line range instead of printing an entire large file. Run deterministic tests locally and surface only the relevant failure excerpt. Reuse `docs/source_audit.md` until its source files change. Avoid sending replay telemetry arrays or full test logs to an assistant.

Use `python scripts/analysis_snapshot.py` for a compact archive overview or add `--race <id>` for one race's coverage and quality counts. This gives an AI assistant enough routing context without loading an entire replay or analysis detail.

Implement and verify in stages: source audit and contract, pipeline, artifacts, interface, focused tests, then `run.ps1 verify`. Keep schema version, formula, unit, window, denominator, source, coverage, and quality synchronized across exports and documentation. Preserve existing replay compatibility. When adding a race, ingest it, regenerate the analysis index, and confirm the history counts boat-races rather than frames.
