# AC40 replay dashboard

The dashboard has five views: Replay, Analysis, Compare, Reports, and Forecast. It exposes 28 source sessions: nine Cagliari races and nineteen Naples races, containing 224 replayed boat-races.

## Runtime and data flow

- `src/main.tsx` mounts `App.tsx`, which owns race, playhead, primary boat, comparison boat, and visibility state.
- `src/components/dashboard/` contains the dashboard controls. `canvas/` renders boats, marks, boundaries, and trails. `panels/ComparisonPanel.tsx` compares boats at the shared playhead. `modals/` provides race selection and historical analysis.
- `src/engine/` loads data, interpolates replay frames, and calculates instantaneous replay geometry.
- `pipeline/run_pipeline.py` streams `Data/*.jsonl`, reconstructs events, and exports replay and historical artifacts.
- `pipeline/historical_analysis.py` owns historical formulas, units, availability rules, coverage, and event feeds. The browser reads its metrics.
- `scripts/build_artifact_inventory.py` publishes replay, analysis, and index downloads in Reports.
- `scripts/analysis_snapshot.py` provides a bounded archive overview without printing telemetry arrays.
- `pipeline/prediction/` builds causal raw-data features, audited completion, joint ranking references, correlated Monte Carlo candidates and the AC38 tournament adapter. Forecast consumes immutable, content-addressed static JSON; it never fits a model in TypeScript. See [forecast implementation and evidence gates](docs/forecasting_implementation.md).

Source measurements, interpolation, reconstructed results, estimated continuous gaps, and unavailable channels remain distinguishable. Source session assets determine boat identity and course marks. Map mode uses OpenStreetMap with attribution; Grid mode makes no tile requests. Virtual contacts describe geometric overlaps rather than official rulings.

Historical analysis uses schema `2.0` and method `historical-2`. Event feeds retain their separate schema `1.0` and method `event-feed-1`. Replay compatibility is unchanged.

## Verification

Run focused tests, then `run.ps1 verify`. Run `npm run test:browser` against a local server for browser interactions. See [dashboard behavior](docs/dashboard_contract.md), [architecture](docs/architecture.md), [historical formulas](docs/historical_analysis.md), [source audit](docs/source_audit.md), and [ingestion](docs/ingesting_new_regattas.md).
