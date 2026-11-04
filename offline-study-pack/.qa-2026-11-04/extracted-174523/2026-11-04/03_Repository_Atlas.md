# 03 — Repository Atlas, Subsystem Reference & Cross-Domain Glossary

**Snapshot Date**: `2026-11-04` | **Git Commit**: `f956f8a14feb3d6bfa483b91ea10384f3bcb84d4` (`master`, dirty working tree: `118` modified/untracked files) | **First-Party Files Indexed**: `209` (`2,299,208` bytes)

> **Purpose of this Document**: This Atlas provides a complete structural map of the `2D_regatta_replay` repository. For every substantive first-party subsystem, it documents its conceptual responsibility, entry points with exact line anchors into the offline [`source-companion/`](source-companion/index.html), inputs, outputs, consumers, execution order, runtime phase, verification tests, and operational lifecycle status (`Active`, `Experimental`, `Retained for Compatibility`, `Superseded`, or `Uncertain`). It concludes with an explicit coverage ledger of all 209 first-party files and a cross-domain glossary mapping mathematical notation, sailing terminology, UI labels, internal Python/TypeScript identifiers, and JSON/CSV artifact fields.

---

## 1. Frozen Snapshot Provenance & Dirty Working-Tree Ledger

A Git commit hash alone (`f956f8a14feb`) does not uniquely identify a workspace when uncommitted changes exist. This study pack freezes the exact working-tree state as of `2026-11-04`, recording SHA-256 digests for all 209 first-party source, test, script, and documentation files in [`evidence/repository_snapshot_provenance.json`](evidence/repository_snapshot_provenance.json).

### 1.1 Category Coverage Summary

| Subsystem Category | File Count | Total Lines | Total Bytes | Audit Coverage |
| :--- | ---: | ---: | ---: | :--- |
| **Frontend 2D/Map Canvas (src/components/canvas/)** | 15 | 4,389 | 172,656 B | 100% Inspected & Indexed |
| **Frontend App State, Types & Styles (src/)** | 13 | 2,968 | 84,629 B | 100% Inspected & Indexed |
| **Frontend Engine & Catalogs (src/engine/)** | 27 | 3,981 | 208,499 B | 100% Inspected & Indexed |
| **Frontend Workspace & UI Components (src/components/)** | 39 | 6,332 | 404,034 B | 100% Inspected & Indexed |
| **Python Core Pipeline (pipeline/)** | 14 | 5,444 | 250,405 B | 100% Inspected & Indexed |
| **Python Forecasting (pipeline/prediction/)** | 13 | 3,892 | 228,507 B | 100% Inspected & Indexed |
| **Root Configuration & Entry Scripts** | 13 | 371 | 21,673 B | 100% Inspected & Indexed |
| **Technical Documentation (docs/)** | 24 | 2,527 | 328,505 B | 100% Inspected & Indexed |
| **Utility & Middleware Scripts (scripts/)** | 7 | 825 | 50,435 B | 100% Inspected & Indexed |
| **Verification Suites (tests/)** | 44 | 10,799 | 549,865 B | 100% Inspected & Indexed |
| **Total First-Party Snapshot** | **209** | **41,528** | **2,299,208 B** | **100% Indexed in Source Companion** |

### 1.2 Uncommitted / Untracked Working-Tree Files (`118` Files)

The following 118 files differ from `HEAD` (`f956f8a14feb`). They represent the browser-feedback verification pass (`docs/browser_feedback_verification.md`, `tests/browser/redesign.mjs`), UI accessibility/copy refinements (`src/App.tsx`, `BoatPerformanceCard.tsx`, `ForecastWorkspace.tsx`, `ReportsWorkspace.tsx`, `AnalysisModal.tsx`, `CourseCanvas.tsx`), and the environment weather harvester (`pipeline/environment.py`, `docs/environment_data.md`):

| File Path (Click to Open in Source Companion) | Git Status | Lines | Size | SHA-256 Prefix |
| :--- | :--- | ---: | ---: | :--- |
| [`PROJECT.md`](source-companion/view/PROJECT.md.html#L1) | `modified (M)` | 33 | 4,428 B | `e1fa6f62e373e14b…` |
| [`README.md`](source-companion/view/README.md.html#L1) | `modified (M)` | 48 | 3,699 B | `f38ff38b3548001a…` |
| [`index.html`](source-companion/view/index.html.html#L1) | `modified (M)` | 16 | 587 B | `3a72a7c82922df05…` |
| [`package.json`](source-companion/view/package.json.html#L1) | `modified (M)` | 37 | 1,350 B | `bb79fd09a5f9f150…` |
| [`run.ps1`](source-companion/view/run.ps1.html#L1) | `modified (M)` | 50 | 2,766 B | `43e3de48e8ece92d…` |
| [`vite.config.ts`](source-companion/view/vite.config.ts.html#L1) | `modified (M)` | 18 | 751 B | `2fb613edf7b0f984…` |
| [`docs/annotation_revision_plan.md`](source-companion/view/docs/annotation_revision_plan.md.html#L1) | `untracked (??)` | 163 | 22,175 B | `3e6f21da7a24b36c…` |
| [`docs/annotation_revision_verification.md`](source-companion/view/docs/annotation_revision_verification.md.html#L1) | `untracked (??)` | 84 | 10,001 B | `a2cf4dcc0858780d…` |
| [`docs/browser_feedback_verification.md`](source-companion/view/docs/browser_feedback_verification.md.html#L1) | `untracked (??)` | 45 | 5,843 B | `10e182fa3c02cb65…` |
| [`docs/dashboard_contract.md`](source-companion/view/docs/dashboard_contract.md.html#L1) | `modified (M)` | 62 | 8,975 B | `13bf1c5a03dd42f1…` |
| [`docs/data_schema.md`](source-companion/view/docs/data_schema.md.html#L1) | `modified (M)` | 68 | 7,860 B | `72b3c830e38c0acb…` |
| [`docs/design-system.md`](source-companion/view/docs/design-system.md.html#L1) | `modified (M)` | 80 | 8,502 B | `e7fe757d850904b7…` |
| [`docs/environment_data.md`](source-companion/view/docs/environment_data.md.html#L1) | `untracked (??)` | 71 | 3,906 B | `277a54c117b7c4c0…` |
| [`docs/forecasting_implementation.md`](source-companion/view/docs/forecasting_implementation.md.html#L1) | `modified (M)` | 156 | 22,836 B | `cc04c080cddb6eba…` |
| [`docs/google_store_ui_redesign_plan.md`](source-companion/view/docs/google_store_ui_redesign_plan.md.html#L1) | `untracked (??)` | 345 | 36,344 B | `54dbf1c85bb9a7b3…` |
| [`docs/historical_analysis.md`](source-companion/view/docs/historical_analysis.md.html#L1) | `modified (M)` | 65 | 15,900 B | `c9a771555328a03c…` |
| [`docs/independent_probability_review_prompt.md`](source-companion/view/docs/independent_probability_review_prompt.md.html#L1) | `untracked (??)` | 237 | 26,619 B | `41744c0bc1e51232…` |
| [`docs/team_analytics.md`](source-companion/view/docs/team_analytics.md.html#L1) | `untracked (??)` | 78 | 12,350 B | `f7babc691374d8c7…` |
| [`docs/team_analytics_plan.md`](source-companion/view/docs/team_analytics_plan.md.html#L1) | `untracked (??)` | 21 | 3,196 B | `073ec0830cb758c9…` |
| [`docs/ui_redesign_verification.md`](source-companion/view/docs/ui_redesign_verification.md.html#L1) | `untracked (??)` | 89 | 7,532 B | `dfce0bdd592a6541…` |
| [`pipeline/environment.py`](source-companion/view/pipeline/environment.py.html#L1) | `untracked (??)` | 362 | 19,035 B | `083d178e06df3b0d…` |
| [`pipeline/historical_analysis.py`](source-companion/view/pipeline/historical_analysis.py.html#L1) | `modified (M)` | 1,065 | 70,673 B | `edbffb92c77922f1…` |
| [`pipeline/ingest.py`](source-companion/view/pipeline/ingest.py.html#L1) | `modified (M)` | 907 | 37,778 B | `3f08cded4b2b0398…` |
| [`pipeline/prediction/build.py`](source-companion/view/pipeline/prediction/build.py.html#L1) | `modified (M)` | 437 | 28,608 B | `1d9a9640726dff03…` |
| [`pipeline/prediction/contracts.py`](source-companion/view/pipeline/prediction/contracts.py.html#L1) | `modified (M)` | 286 | 18,252 B | `e1c0a7bc16e5ad08…` |
| [`pipeline/prediction/cup.py`](source-companion/view/pipeline/prediction/cup.py.html#L1) | `modified (M)` | 661 | 41,399 B | `e9748ed4e48c3571…` |
| [`pipeline/prediction/labels.py`](source-companion/view/pipeline/prediction/labels.py.html#L1) | `modified (M)` | 196 | 11,212 B | `8068858b468a29e2…` |
| [`pipeline/prediction/models.py`](source-companion/view/pipeline/prediction/models.py.html#L1) | `modified (M)` | 856 | 43,831 B | `86049eb3c98c3c52…` |
| [`pipeline/prediction/simulation.py`](source-companion/view/pipeline/prediction/simulation.py.html#L1) | `modified (M)` | 516 | 29,905 B | `a222f109b0877dc3…` |
| [`pipeline/prediction/state.py`](source-companion/view/pipeline/prediction/state.py.html#L1) | `modified (M)` | 313 | 18,609 B | `f5657d42e60bfa03…` |
| [`pipeline/run_pipeline.py`](source-companion/view/pipeline/run_pipeline.py.html#L1) | `modified (M)` | 370 | 14,569 B | `5d3846c497705f3a…` |
| [`pipeline/tactical_insights.py`](source-companion/view/pipeline/tactical_insights.py.html#L1) | `untracked (??)` | 189 | 11,419 B | `aea556291b579da7…` |
| [`scripts/build_artifact_inventory.py`](source-companion/view/scripts/build_artifact_inventory.py.html#L1) | `modified (M)` | 91 | 6,349 B | `69b2e00a04bb2cda…` |
| [`scripts/build_race_previews.py`](source-companion/view/scripts/build_race_previews.py.html#L1) | `untracked (??)` | 74 | 3,631 B | `80ef7af5ce4a7148…` |
| [`scripts/build_report_exports.py`](source-companion/view/scripts/build_report_exports.py.html#L1) | `untracked (??)` | 80 | 4,261 B | `4cecda6fa24cda4b…` |
| [`scripts/forecastArtifacts.ts`](source-companion/view/scripts/forecastArtifacts.ts.html#L1) | `untracked (??)` | 79 | 3,587 B | `383f2c34144225dc…` |
| [`scripts/forecastScenarios.ts`](source-companion/view/scripts/forecastScenarios.ts.html#L1) | `untracked (??)` | 199 | 13,773 B | `7f2f63f7077ca7c8…` |
| [`scripts/refresh_team_analytics.py`](source-companion/view/scripts/refresh_team_analytics.py.html#L1) | `untracked (??)` | 261 | 16,509 B | `4d6afb83619601bf…` |
| [`src/App.tsx`](source-companion/view/src/App.tsx.html#L1) | `modified (M)` | 210 | 12,277 B | `28852e045ef6b5cc…` |
| [`src/components/canvas/boatPresentation.test.ts`](source-companion/view/src/components/canvas/boatPresentation.test.ts.html#L1) | `untracked (??)` | 36 | 2,292 B | `a282ec9754dedf80…` |
| [`src/components/canvas/boatPresentation.ts`](source-companion/view/src/components/canvas/boatPresentation.ts.html#L1) | `untracked (??)` | 66 | 4,646 B | `4743a4b2d81ba321…` |
| [`src/components/canvas/cameraStateSyncAdversarial.test.ts`](source-companion/view/src/components/canvas/cameraStateSyncAdversarial.test.ts.html#L1) | `modified (M)` | 470 | 17,025 B | `ddc89cb9c8b608d5…` |
| [`src/components/canvas/CourseCanvas.tsx`](source-companion/view/src/components/canvas/CourseCanvas.tsx.html#L1) | `modified (M)` | 602 | 22,879 B | `d304a18c3b6ad5d9…` |
| [`src/components/canvas/DynamicVesselLayer.ts`](source-companion/view/src/components/canvas/DynamicVesselLayer.ts.html#L1) | `modified (M)` | 707 | 25,701 B | `ec59aea4450330d3…` |
| [`src/components/canvas/mapStyle.ts`](source-companion/view/src/components/canvas/mapStyle.ts.html#L1) | `modified (M)` | 96 | 2,807 B | `720da1f988d3c5c7…` |
| [`src/components/canvas/renderPalette.ts`](source-companion/view/src/components/canvas/renderPalette.ts.html#L1) | `untracked (??)` | 18 | 589 B | `84094cdc15ba7a08…` |
| [`src/components/canvas/StaticCourseLayer.ts`](source-companion/view/src/components/canvas/StaticCourseLayer.ts.html#L1) | `modified (M)` | 74 | 2,455 B | `3f87ebf31e8796f1…` |
| [`src/components/canvas/viewModeStress.test.ts`](source-companion/view/src/components/canvas/viewModeStress.test.ts.html#L1) | `modified (M)` | 288 | 12,522 B | `39ad75ea4ac2c5cd…` |
| [`src/components/dashboard/analysis-light.css`](source-companion/view/src/components/dashboard/analysis-light.css.html#L1) | `untracked (??)` | 169 | 9,934 B | `8c3c3b2886563335…` |
| [`src/components/dashboard/boat-course-controls.css`](source-companion/view/src/components/dashboard/boat-course-controls.css.html#L1) | `untracked (??)` | 37 | 3,818 B | `e112e66ccce3c81c…` |
| [`src/components/dashboard/BoatCourseControls.tsx`](source-companion/view/src/components/dashboard/BoatCourseControls.tsx.html#L1) | `untracked (??)` | 23 | 3,784 B | `2072501ed69f52fd…` |
| [`src/components/dashboard/BoatPerformanceCard.adversarial.test.ts`](source-companion/view/src/components/dashboard/BoatPerformanceCard.adversarial.test.ts.html#L1) | `modified (M)` | 32 | 1,546 B | `f1d8859d2445297c…` |
| [`src/components/dashboard/BoatPerformanceCard.test.ts`](source-companion/view/src/components/dashboard/BoatPerformanceCard.test.ts.html#L1) | `modified (M)` | 41 | 2,068 B | `50aaa1d4ddb6f8f0…` |
| [`src/components/dashboard/BoatPerformanceCard.tsx`](source-companion/view/src/components/dashboard/BoatPerformanceCard.tsx.html#L1) | `modified (M)` | 180 | 7,296 B | `84c2062dff792ba0…` |
| [`src/components/dashboard/BoatPerformanceRadar.tsx`](source-companion/view/src/components/dashboard/BoatPerformanceRadar.tsx.html#L1) | `untracked (??)` | 118 | 19,610 B | `c1d855982f2def0d…` |
| [`src/components/dashboard/BoatVisibilityFilter.tsx`](source-companion/view/src/components/dashboard/BoatVisibilityFilter.tsx.html#L1) | `untracked (??)` | 18 | 1,941 B | `86e0a749c9c1faa8…` |
| [`src/components/dashboard/cupEvidence.css`](source-companion/view/src/components/dashboard/cupEvidence.css.html#L1) | `untracked (??)` | 16 | 1,307 B | `6f4302ae78cf0caf…` |
| [`src/components/dashboard/dashboard.css`](source-companion/view/src/components/dashboard/dashboard.css.html#L1) | `modified (M)` | 348 | 30,824 B | `e9fc5081c388883a…` |
| [`src/components/dashboard/EventsNotesPanel.adversarial.test.ts`](source-companion/view/src/components/dashboard/EventsNotesPanel.adversarial.test.ts.html#L1) | `modified (M)` | 43 | 2,017 B | `27b2ce26d30be2e2…` |
| [`src/components/dashboard/EventsNotesPanel.tsx`](source-companion/view/src/components/dashboard/EventsNotesPanel.tsx.html#L1) | `modified (M)` | 217 | 8,100 B | `9bd6e41cecc08a28…` |
| [`src/components/dashboard/forecast.css`](source-companion/view/src/components/dashboard/forecast.css.html#L1) | `modified (M)` | 74 | 7,427 B | `5c121a4052a00035…` |
| [`src/components/dashboard/ForecastWorkspace.tsx`](source-companion/view/src/components/dashboard/ForecastWorkspace.tsx.html#L1) | `modified (M)` | 218 | 28,432 B | `a6842cdbb1ee8166…` |
| [`src/components/dashboard/performance-radar.css`](source-companion/view/src/components/dashboard/performance-radar.css.html#L1) | `untracked (??)` | 95 | 9,631 B | `ccba5a63a08cc1c8…` |
| [`src/components/dashboard/RaceStatusLeaderboard.tsx`](source-companion/view/src/components/dashboard/RaceStatusLeaderboard.tsx.html#L1) | `modified (M)` | 178 | 7,030 B | `b83c63c7f3f59286…` |
| [`src/components/dashboard/RaceTimelinePanel.test.ts`](source-companion/view/src/components/dashboard/RaceTimelinePanel.test.ts.html#L1) | `modified (M)` | 62 | 3,468 B | `d877bdfdf1a359a0…` |
| [`src/components/dashboard/RaceTimelinePanel.tsx`](source-companion/view/src/components/dashboard/RaceTimelinePanel.tsx.html#L1) | `modified (M)` | 362 | 13,224 B | `9e1c50067ce473c9…` |
| [`src/components/dashboard/reports.css`](source-companion/view/src/components/dashboard/reports.css.html#L1) | `untracked (??)` | 61 | 6,110 B | `d4ea91abba1d8c69…` |
| [`src/components/dashboard/ReportsWorkspace.test.ts`](source-companion/view/src/components/dashboard/ReportsWorkspace.test.ts.html#L1) | `untracked (??)` | 32 | 3,435 B | `7d58bd5ace9e3941…` |
| [`src/components/dashboard/ReportsWorkspace.tsx`](source-companion/view/src/components/dashboard/ReportsWorkspace.tsx.html#L1) | `modified (M)` | 86 | 10,695 B | `5662f6c5d891509a…` |
| [`src/components/dashboard/TacticalDashboard.tsx`](source-companion/view/src/components/dashboard/TacticalDashboard.tsx.html#L1) | `modified (M)` | 125 | 14,274 B | `9d3f8f4bc51ec517…` |
| [`src/components/dashboard/TacticalHeader.tsx`](source-companion/view/src/components/dashboard/TacticalHeader.tsx.html#L1) | `modified (M)` | 63 | 8,771 B | `602be68a927b8f15…` |
| [`src/components/dashboard/TacticalInsightsPanel.tsx`](source-companion/view/src/components/dashboard/TacticalInsightsPanel.tsx.html#L1) | `untracked (??)` | 45 | 4,018 B | `cb217b5e64a4290c…` |
| [`src/components/dashboard/TacticalMapOverlay.adversarial.test.ts`](source-companion/view/src/components/dashboard/TacticalMapOverlay.adversarial.test.ts.html#L1) | `modified (M)` | 413 | 17,224 B | `385ba8a98f7ea698…` |
| [`src/components/dashboard/TacticalMapOverlay.test.ts`](source-companion/view/src/components/dashboard/TacticalMapOverlay.test.ts.html#L1) | `modified (M)` | 301 | 11,885 B | `d8bee63a4754df08…` |
| [`src/components/dashboard/TacticalMapOverlay.tsx`](source-companion/view/src/components/dashboard/TacticalMapOverlay.tsx.html#L1) | `modified (M)` | 226 | 8,821 B | `a3d8a5ab2fbf41e4…` |
| [`src/components/dashboard/TeamAnalytics.test.ts`](source-companion/view/src/components/dashboard/TeamAnalytics.test.ts.html#L1) | `untracked (??)` | 192 | 14,755 B | `6181a36774175361…` |
| [`src/components/dashboard/TeamDebrief.tsx`](source-companion/view/src/components/dashboard/TeamDebrief.tsx.html#L1) | `untracked (??)` | 21 | 1,934 B | `b81b41b5e3954d13…` |
| [`src/components/dashboard/workspaces.css`](source-companion/view/src/components/dashboard/workspaces.css.html#L1) | `modified (M)` | 93 | 8,967 B | `b3bf6ebaeeb076cb…` |
| [`src/components/modals/AnalysisModal.tsx`](source-companion/view/src/components/modals/AnalysisModal.tsx.html#L1) | `modified (M)` | 323 | 40,134 B | `2a015dd2ce3e0ee0…` |
| [`src/components/modals/race-library.css`](source-companion/view/src/components/modals/race-library.css.html#L1) | `untracked (??)` | 71 | 6,581 B | `624b84a0a25c5448…` |
| [`src/components/modals/RacePickerModal.tsx`](source-companion/view/src/components/modals/RacePickerModal.tsx.html#L1) | `modified (M)` | 92 | 7,888 B | `4d5e5395df26a644…` |
| [`src/components/panels/ComparisonPanel.tsx`](source-companion/view/src/components/panels/ComparisonPanel.tsx.html#L1) | `modified (M)` | 20 | 3,511 B | `3cdbc8bafd0f3217…` |
| [`src/engine/analysisCatalog.test.ts`](source-companion/view/src/engine/analysisCatalog.test.ts.html#L1) | `untracked (??)` | 71 | 6,926 B | `83bd07e525b26c65…` |
| [`src/engine/analysisCatalog.ts`](source-companion/view/src/engine/analysisCatalog.ts.html#L1) | `modified (M)` | 120 | 10,469 B | `25768b3b6f174f1d…` |
| [`src/engine/environment.test.ts`](source-companion/view/src/engine/environment.test.ts.html#L1) | `untracked (??)` | 121 | 7,744 B | `d6e93d2c60942596…` |
| [`src/engine/environment.ts`](source-companion/view/src/engine/environment.ts.html#L1) | `untracked (??)` | 103 | 7,280 B | `08a4bc30060e962e…` |
| [`src/engine/forecastArtifactRouting.test.ts`](source-companion/view/src/engine/forecastArtifactRouting.test.ts.html#L1) | `untracked (??)` | 148 | 7,654 B | `01dd4dddb70e07e2…` |
| [`src/engine/forecastScenarios.test.ts`](source-companion/view/src/engine/forecastScenarios.test.ts.html#L1) | `untracked (??)` | 37 | 2,424 B | `bdf695426c27c7fa…` |
| [`src/engine/forecastScenarios.ts`](source-companion/view/src/engine/forecastScenarios.ts.html#L1) | `untracked (??)` | 43 | 3,004 B | `5d96161cdb6a481a…` |
| [`src/engine/forecastScenarioService.test.ts`](source-companion/view/src/engine/forecastScenarioService.test.ts.html#L1) | `untracked (??)` | 137 | 8,524 B | `d6b47d5839c99425…` |
| [`src/engine/predictionCatalog.test.ts`](source-companion/view/src/engine/predictionCatalog.test.ts.html#L1) | `modified (M)` | 326 | 23,320 B | `a10cb700d3d7e98b…` |
| [`src/engine/predictionCatalog.ts`](source-companion/view/src/engine/predictionCatalog.ts.html#L1) | `modified (M)` | 230 | 23,022 B | `e4f163b3166b80b9…` |
| [`src/engine/vmgWindVerification.test.ts`](source-companion/view/src/engine/vmgWindVerification.test.ts.html#L1) | `modified (M)` | 316 | 12,371 B | `e8ada25518330cce…` |
| [`src/index.css`](source-companion/view/src/index.css.html#L1) | `modified (M)` | 210 | 4,903 B | `34a3285430a3ffac…` |
| [`src/main.tsx`](source-companion/view/src/main.tsx.html#L1) | `modified (M)` | 7 | 232 B | `e9e644d4f2c138e0…` |
| [`src/types/analysis.ts`](source-companion/view/src/types/analysis.ts.html#L1) | `modified (M)` | 335 | 8,817 B | `41a3363ee6b14e4d…` |
| [`src/types/prediction.ts`](source-companion/view/src/types/prediction.ts.html#L1) | `modified (M)` | 113 | 4,749 B | `198bb204a556a895…` |
| [`src/types/replay.ts`](source-companion/view/src/types/replay.ts.html#L1) | `modified (M)` | 205 | 4,504 B | `c24446fc886b7cb4…` |
| [`src/utils/evidenceText.test.ts`](source-companion/view/src/utils/evidenceText.test.ts.html#L1) | `untracked (??)` | 14 | 826 B | `b2749a3d9e0ecdf0…` |
| [`src/utils/evidenceText.ts`](source-companion/view/src/utils/evidenceText.ts.html#L1) | `untracked (??)` | 6 | 436 B | `830188ad96a5744d…` |
| [`tests/browser/annotations.mjs`](source-companion/view/tests/browser/annotations.mjs.html#L1) | `untracked (??)` | 405 | 29,962 B | `26685bcff9885b32…` |
| [`tests/browser/dashboard.mjs`](source-companion/view/tests/browser/dashboard.mjs.html#L1) | `modified (M)` | 423 | 31,602 B | `d8f0862ba9288c3b…` |
| [`tests/browser/feedback.mjs`](source-companion/view/tests/browser/feedback.mjs.html#L1) | `untracked (??)` | 117 | 8,304 B | `f7d18def80b3ef27…` |
| [`tests/browser/forecast.mjs`](source-companion/view/tests/browser/forecast.mjs.html#L1) | `modified (M)` | 449 | 34,164 B | `18cf55ef25b9823e…` |
| [`tests/browser/redesign.mjs`](source-companion/view/tests/browser/redesign.mjs.html#L1) | `untracked (??)` | 105 | 6,686 B | `5472a722c5fa8cdb…` |
| [`tests/unit/test_dashboard_contract.py`](source-companion/view/tests/unit/test_dashboard_contract.py.html#L1) | `modified (M)` | 42 | 1,844 B | `9de8e764e63ff6fe…` |
| [`tests/unit/test_environment.py`](source-companion/view/tests/unit/test_environment.py.html#L1) | `untracked (??)` | 198 | 10,744 B | `e3fa72e7f9906454…` |
| [`tests/unit/test_performance_analysis.py`](source-companion/view/tests/unit/test_performance_analysis.py.html#L1) | `untracked (??)` | 328 | 19,042 B | `17080d760040f356…` |
| [`tests/unit/test_prediction_cup.py`](source-companion/view/tests/unit/test_prediction_cup.py.html#L1) | `modified (M)` | 314 | 18,996 B | `a8c114347430fb13…` |
| [`tests/unit/test_prediction_models.py`](source-companion/view/tests/unit/test_prediction_models.py.html#L1) | `modified (M)` | 428 | 25,969 B | `b17513c1a7ec6a6b…` |
| [`tests/unit/test_prediction_pipeline.py`](source-companion/view/tests/unit/test_prediction_pipeline.py.html#L1) | `modified (M)` | 472 | 27,473 B | `a801bfded91b641d…` |
| [`tests/unit/test_race_previews.py`](source-companion/view/tests/unit/test_race_previews.py.html#L1) | `untracked (??)` | 63 | 3,367 B | `f9c2140c7763278c…` |
| [`tests/unit/test_report_exports.py`](source-companion/view/tests/unit/test_report_exports.py.html#L1) | `untracked (??)` | 29 | 2,657 B | `ff02ce560f89265d…` |
| [`tests/unit/test_report_inventory.py`](source-companion/view/tests/unit/test_report_inventory.py.html#L1) | `untracked (??)` | 54 | 3,252 B | `abd2a47851bcc83f…` |
| [`tests/unit/test_tactical_insights.py`](source-companion/view/tests/unit/test_tactical_insights.py.html#L1) | `untracked (??)` | 203 | 11,341 B | `82c9836a37473561…` |
| [`tests/unit/test_vmg_wind_adversarial.py`](source-companion/view/tests/unit/test_vmg_wind_adversarial.py.html#L1) | `modified (M)` | 215 | 9,337 B | `ea74d54a066e2591…` |
| [`public/fonts/OFL.txt`](source-companion/view/public/fonts/OFL.txt.html#L1) | `untracked (??)` | 93 | 4,482 B | `9af36190332437f5…` |
| [`public/fonts/README.md`](source-companion/view/public/fonts/README.md.html#L1) | `untracked (??)` | 7 | 344 B | `8504f15bb0fec43f…` |


---

## 2. Ownership Boundaries & Five Runtime Phases

Before examining individual modules, keep the repository's strict architectural ownership rule in view (`AGENTS.md`, `PROJECT.md`):

1. **Python Pipeline Ownership (`pipeline/`, `scripts/`)**:
   - Owns all raw telemetry ingestion, coordinate projection, gate/start reconstruction, manoeuvre detection, historical metric calculation (`historical_analysis.py`), tactical wind-shift regression (`tactical_insights.py`), causal live/pre-race/Cup forecasting (`pipeline/prediction/`), and canonical CSV presentation tables (`canonical_tables.py`).
   - Writes static, immutable or schema-versioned JSON and CSV artifacts into `public/data/`.
2. **TypeScript Browser Ownership (`src/`)**:
   - Consumes `public/data/` exports with strict runtime schema validation (`analysisCatalog.ts`, `predictionCatalog.ts`, `manifest.ts`).
   - **Never recalculates historical metrics or forecast probabilities**.
   - Owns only **instantaneous 10 Hz display interpolation** (`ReplayEngine.ts`, `interpolate.ts`), **instantaneous live leaderboard & pairwise boat-to-boat geometry** (`src/engine/analytics.ts`), **2D viewport projection & greedy label placement** (`ViewportMatrix.ts`, `CourseCanvas.tsx`, `boatPresentation.ts`), and **real-time convex-polygon contact rendering** (`contactDetector.ts`).

Every module in the repository executes in one or more of **five distinct runtime phases**:

| Phase Code | Phase Name | Trigger Command / Event | Writes to `public/data/`? | Works Offline Without Runtimes? |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Ingestion & Replay Reconstruction** | `python -m pipeline` or `python scripts/ingest_regattas.py` | Yes (`replays/*.json`, `manifests.json`, `race_previews.json`, `presentation/**`) | Artifacts pre-built; script needs Python + `Data/` |
| **Phase 2** | **Historical & Team Analytics Refresh** | `python scripts/refresh_team_analytics.py` | Yes (`analysis/index.json`, `analysis/<race_id>.json`, `artifacts.json`) | Artifacts pre-built; script needs Python |
| **Phase 3** | **Forecast Build & Verification** | `python -m pipeline.prediction build` / `verify` | Yes (`.forecast/**`, `predictions/index.json`, `predictions/races/*.json`, `predictions/cup_2027.json`) | Baseline & presets pre-built; script needs Python |
| **Phase 4** | **Dev/Preview Server & Scenario Middleware** | `npm run dev` / `vite` (`scripts/forecastScenarios.ts`) | Yes (lazy `predictions/scenarios/<race_id>_<hash>.json` on `POST /api/forecast-scenarios`) | Requires local Node + Python runtime |
| **Phase 5** | **Browser Client Interaction** | Opening dashboard in browser (`src/main.tsx` → `src/App.tsx`) | Read-only (`fetch('/data/...')`) | Works offline via static HTTP server (Grid mode) |

---

## 3. Substantive First-Party Subsystems (Deep Reference)

### Subsystem S1 — Raw Telemetry Ingestion & Spatial Projection (`pipeline/ingest.py`, `pipeline/projection.py`)

* **Purpose & Conceptual Responsibility**: Streams multi-gigabyte raw `.jsonl` race logs line-by-line in $O(1)$ memory per record (`iter_jsonl`), extracts 11 record types (`asset`, `boat_state`, `course`, `leg_timings`, `wind_summary`, `wind_history`, `autonomous_marks`, `mark_roundings`, `boundary`, `race_start_status`, `manoeuvres`), resolves asset UUIDs to team codes (`RM1`–`RM8` and competitor hulls), and projects WGS84 `(lat, lon)` into a local metric tangent plane `(x East, y North)` centered on a venue reference origin.
* **Important Files & Entry Points**:
  - [`pipeline/ingest.py`](source-companion/view/pipeline/ingest.py.html#L1): `IngestionPipeline` ([`L444-L746`](source-companion/view/pipeline/ingest.py.html#L444)), `IngestionResult` ([`L296-L441`](source-companion/view/pipeline/ingest.py.html#L296)), `iter_jsonl` ([`L53-L69`](source-companion/view/pipeline/ingest.py.html#L53)), `_resolve_team_code` ([`L126-L157`](source-companion/view/pipeline/ingest.py.html#L126)).
  - [`pipeline/projection.py`](source-companion/view/pipeline/projection.py.html#L1): `LocalCoordinateConverter` ([`L29-L108`](source-companion/view/pipeline/projection.py.html#L29)), `NAPLES_REFERENCE` (`40.80875° N, 14.21565° E`, [`L18`](source-companion/view/pipeline/projection.py.html#L18)), `CAGLIARI_REFERENCE` (`39.1900° N, 9.1425° E`, [`L19`](source-companion/view/pipeline/projection.py.html#L19)), `for_coordinates()` ([`L48-L55`](source-companion/view/pipeline/projection.py.html#L48)).
* **Inputs, Outputs & Consumers**:
  - *Inputs*: Raw `Data/<session>.jsonl` files (28 files, 6,866,006,601 bytes total).
  - *Outputs*: In-memory `IngestionResult` dataclass consumed by `pipeline/__main__.py` and `scripts/ingest_regattas.py`.
* **Dependencies & Execution Order**: First stage of Phase 1 (`pipeline/__main__.py:L40-L43`). Must run before synchronization, reconstruction, manoeuvre detection, and analytics.
* **Tests Establishing Behavior**: [`tests/unit/test_ingest.py`](source-companion/view/tests/unit/test_ingest.py.html#L1), [`tests/unit/test_projection.py`](source-companion/view/tests/unit/test_projection.py.html#L1), [`tests/e2e/test_runner.py`](source-companion/view/tests/e2e/test_runner.py.html#L1) (Tier 1).
* **Lifecycle Status**: **Active** (Core production pipeline).
  - *Audit Note*: `IngestionResult.to_dict()` ([`pipeline/ingest.py:L383-L388`](source-companion/view/pipeline/ingest.py.html#L383)) hardcodes Naples projection constants in its intermediate dict summary, whereas the actual published replay manifest [`pipeline/export_replay.py:L153-L154`](source-companion/view/pipeline/export_replay.py.html#L153) uses the session-specific converter (`CAGLIARI_REFERENCE` or `NAPLES_REFERENCE`). In addition, `ingest.py:L699-L700` drops competitors with `not c.telemetry` (which removes `GBR B` in `26_09_22_nap_ipr_pr2`, `pr3`, `pr4` from replay JSONs, creating the `224` replayed vs `227` scheduled entry distinction).

---

### Subsystem S2 — 10 Hz Timeline Synchronization & Interpolation (`pipeline/synchronize.py`)

* **Purpose & Conceptual Responsibility**: Resamples irregular per-boat `boat_state` streams (~10 Hz) and `autonomous_marks` streams (~1 Hz) onto a uniform 100 ms (`10 Hz`) master timeline spanning `[window_start, window_end]`. Uses linear interpolation for Cartesian coordinates and scalar channels (`x`, `y`, `sog`, `vmg`, `tws`, `twa`) and shortest-arc circular interpolation modulo $360^\circ$ for directional bearings (`heading`, `cog`, `twd`). Clamps out-of-range timestamps to the nearest boundary observation (causing "held tail" plateaus when telemetry stops early).
* **Important Files & Entry Points**:
  - [`pipeline/synchronize.py`](source-companion/view/pipeline/synchronize.py.html#L1): `TimelineSynchronizer` ([`L127-L315`](source-companion/view/pipeline/synchronize.py.html#L127)), `interpolate_angle_deg` ([`L29-L48`](source-companion/view/pipeline/synchronize.py.html#L29)), `interpolate_linear` ([`L19-L26`](source-companion/view/pipeline/synchronize.py.html#L19)).
* **Inputs, Outputs & Consumers**:
  - *Inputs*: Raw per-boat and per-mark telemetry lists from `IngestionResult`.
  - *Outputs*: `SynchronizedTimeline` containing aligned column arrays of identical length $T$ at 100 ms steps, plus `WindSample` timeline. Consumed by `reconstruction.py`, `manoeuvres.py`, `analytics.py`, and `export_replay.py`.
* **Runtime Phase**: Phase 1 (Ingestion & Replay Reconstruction).
* **Tests Establishing Behavior**: [`tests/unit/test_synchronize.py`](source-companion/view/tests/unit/test_synchronize.py.html#L1), [`tests/tier5_integrity.py`](source-companion/view/tests/tier5_integrity.py.html#L107) (`test_timestamps_and_boat_columns_align`).
* **Lifecycle Status**: **Active**.

---

### Subsystem S3 — Course Geometry, Bow Crossings, Progress & Classifications (`pipeline/reconstruction.py`, `pipeline/analytics.py`)

* **Purpose & Conceptual Responsibility**: Reconstructs race chronology and geometry when source `mark_roundings` are sparse or missing (`0` records in `naples_pr1`). Computes sub-frame bow-tip (`+12.963 m` forward of transom GNSS along `heading`) segment intersections against start lines and 200 m virtual gate corridors (`MAX_GATE_RADIUS_M = 100.0`), resolves leg sequences (`leg = 0..N`), computes cumulative monotonic `progress_m`, evaluates race classifications (`RANK_1..K`, `DNF`, `OCS`, `RET`, `DNS`), and runs 10 Hz convex polygon SAT contact detection (`detect_virtual_contacts`).
* **Important Files & Entry Points**:
  - [`pipeline/reconstruction.py`](source-companion/view/pipeline/reconstruction.py.html#L1): `CourseReconstructor` ([`L92-L678`](source-companion/view/pipeline/reconstruction.py.html#L92)), `_segment_intersection_fraction` ([`L39-L73`](source-companion/view/pipeline/reconstruction.py.html#L39)), `_bow_point` ([`L76-L83`](source-companion/view/pipeline/reconstruction.py.html#L76)), `_reconstruct_boat_gates` ([`L376-L482`](source-companion/view/pipeline/reconstruction.py.html#L376)), `_compute_progress` ([`L548-L629`](source-companion/view/pipeline/reconstruction.py.html#L548)).
  - [`pipeline/analytics.py`](source-companion/view/pipeline/analytics.py.html#L1): `AnalyticsEngine` ([`L223-L345`](source-companion/view/pipeline/analytics.py.html#L223)), `detect_virtual_contacts` ([`L127-L220`](source-companion/view/pipeline/analytics.py.html#L127)), `_polygons_intersect_sat` ([`L61-L97`](source-companion/view/pipeline/analytics.py.html#L61)).
* **Inputs, Outputs & Consumers**:
  - *Inputs*: `IngestionResult` + `SynchronizedTimeline`.
  - *Outputs*: `ReconstructedCourse`, per-boat `GateCrossing` lists, `progress_m` arrays, `leg` arrays, competitor `classification` & `summary`, and `virtual_contact_incidents`.
* **Runtime Phase**: Phase 1 (Ingestion & Replay Reconstruction).
* **Tests Establishing Behavior**: [`tests/unit/test_reconstruction.py`](source-companion/view/tests/unit/test_reconstruction.py.html#L1), [`tests/unit/test_analytics.py`](source-companion/view/tests/unit/test_analytics.py.html#L1), [`tests/unit/test_contact_detector.py`](source-companion/view/tests/unit/test_contact_detector.py.html#L1).
* **Lifecycle Status**: **Active**.
  - *Audit Note 1*: [`pipeline/reconstruction.py:L228`](source-companion/view/pipeline/reconstruction.py.html#L228) checks `comp.get("started")` at the top level of the competitor dictionary rather than `comp.get("start_state", {}).get("started")`. Because `started` is nested inside `start_state`, `explicit_started` evaluates to `None`, allowing `USA` in `naples_pr1` (where `start_state.started = False` across all 24 records) to be geometrically reconstructed as `RANK_4`. Downstream `historical_analysis.py` (`L755-L759`) catches this discrepancy and flags a `source_conflict`.
  - *Audit Note 2*: In [`pipeline/analytics.py:L263-L265`](source-companion/view/pipeline/analytics.py.html#L263), the Python frame leaderboard estimate divides metre gaps by a constant `8.0` m/s, whereas the browser leaderboard ([`src/engine/analytics.ts:L71`](source-companion/view/src/engine/analytics.ts.html#L71)) divides by the leader's instantaneous `sog * (1852 / 3600)`.

---

### Subsystem S4 — Manoeuvre Detection (`pipeline/manoeuvres.py`)

* **Purpose & Conceptual Responsibility**: Detects tacks and gybes from 10 Hz synchronized telemetry (`heading`, `twa`, `sog`, `vmg`) when raw `manoeuvres` records are absent (all 28 sessions have `0` raw `manoeuvres` records). Applies a 5-sample (`0.5 s`) circular moving average to heading, identifies turn-rate peaks ($\ge 8.0^\circ\text{/s}$), verifies sign flip of $\text{TWA}$ across $\pm 20^\circ..160^\circ$, checks cumulative heading change $\ge 32^\circ$, enforces a speed dip $\ge 2.5\text{ kt}$ (`min_speed_loss_kt = 2.5`), and classifies tacks ($|\overline{\text{TWA}}| < 90^\circ$) vs gybes ($|\overline{\text{TWA}}| \ge 90^\circ$).
* **Important Files & Entry Points**:
  - [`pipeline/manoeuvres.py`](source-companion/view/pipeline/manoeuvres.py.html#L1): `ManoeuvreDetector` ([`L48-L246`](source-companion/view/pipeline/manoeuvres.py.html#L48)), `detect_for_boat` ([`L74-L227`](source-companion/view/pipeline/manoeuvres.py.html#L74)).
* **Inputs, Outputs & Consumers**:
  - *Inputs*: 10 Hz boat telemetry arrays + `gun_time` + optional finish cutoff.
  - *Outputs*: List of `ManoeuvreEvent` records stored in `replay.competitors[].manoeuvres` and subsequently re-evaluated by `historical_analysis.py` (`_event_analysis`).
* **Runtime Phase**: Phase 1 (Ingestion & Replay Reconstruction).
* **Tests Establishing Behavior**: [`tests/unit/test_manoeuvres.py`](source-companion/view/tests/unit/test_manoeuvres.py.html#L1).
* **Lifecycle Status**: **Active** (with an important dual-definition subtlety between replay export and historical analysis: `manoeuvres.py:L192-L207` measures recovery to **90%** of entry speed and caps unrecovered events at ~15.0 s, whereas `historical_analysis.py:L294-L313` recomputes recovery from raw 10 Hz SOG to **95%** of entry speed and sets unrecovered events to `None`).

---

### Subsystem S5 — Replay Export, Canonical Tables & Regatta Batch Ingestion (`pipeline/export_replay.py`, `pipeline/canonical_tables.py`, `scripts/ingest_regattas.py`)

* **Purpose & Conceptual Responsibility**: Packages synchronized telemetry, reconstructed course geometry, boundary timelines, and competitor summaries into compact JSON replay manifests (`public/data/replays/<race_id>.json`), generates SVG/JSON course previews (`public/data/race_previews.json`), builds the regatta catalog (`public/data/manifests.json`), and exports reconciled canonical CSV/JSON tables (`public/data/presentation/**`).
* **Important Files & Entry Points**:
  - [`pipeline/export_replay.py`](source-companion/view/pipeline/export_replay.py.html#L1): `export_replay_json` ([`L41-L245`](source-companion/view/pipeline/export_replay.py.html#L41)), `update_manifests` ([`L248-L320`](source-companion/view/pipeline/export_replay.py.html#L248)).
  - [`pipeline/canonical_tables.py`](source-companion/view/pipeline/canonical_tables.py.html#L1): `export_canonical_tables` ([`L45-L380`](source-companion/view/pipeline/canonical_tables.py.html#L45)).
  - [`scripts/ingest_regattas.py`](source-companion/view/scripts/ingest_regattas.py.html#L1): Multi-session batch orchestrator for all 28 `.jsonl` files.
* **Runtime Phase**: Phase 1 (Ingestion) and Phase 2 (Refresh).
* **Tests Establishing Behavior**: [`tests/unit/test_export_replay.py`](source-companion/view/tests/unit/test_export_replay.py.html#L1), [`tests/unit/test_canonical_tables.py`](source-companion/view/tests/unit/test_canonical_tables.py.html#L1), [`tests/tier5_integrity.py`](source-companion/view/tests/tier5_integrity.py.html#L1).
* **Lifecycle Status**: **Active**.

---

### Subsystem S6 — Historical Analysis, Peer-Normalized Radar & Tactical Insights (`pipeline/historical_analysis.py`, `pipeline/tactical_insights.py`, `scripts/refresh_team_analytics.py`)

* **Purpose & Conceptual Responsibility**: The single source of truth for all historical race metrics (`schema_version = "2.0"`, `formula_version = "historical-2"`), the 6-axis peer-normalized boat performance radar (`performance-1`), the coaching debrief items (`debrief-1`), the chronological event feed (`event-feed-1`), and the 10-second tactical wind-shift OLS regression snapshots (`tactical-1`). Enforces strict quality gating (`verified`, `derived`, `partial`, `low_coverage`, `conflict`, `unavailable`), detects source conflicts (e.g., `USA` start conflict in `naples_pr1`), and aggregates cross-race team/boat histories counting **boat-races (`224`) rather than telemetry frames (`331,089`)**.
* **Important Files & Entry Points**:
  - [`pipeline/historical_analysis.py`](source-companion/view/pipeline/historical_analysis.py.html#L1) (`1,654` lines): `DEFINITIONS` ([`L43-L163`](source-companion/view/pipeline/historical_analysis.py.html#L43)), `_event_analysis` ([`L265-L333`](source-companion/view/pipeline/historical_analysis.py.html#L265)), `_leg_Entry_for_boat` ([`L336-L469`](source-companion/view/pipeline/historical_analysis.py.html#L336)), `_boat_performance` ([`L580-L746`](source-companion/view/pipeline/historical_analysis.py.html#L580)), `_boat_debrief` ([`L749-L832`](source-companion/view/pipeline/historical_analysis.py.html#L749)), `build_race_analysis` ([`L925-L1298`](source-companion/view/pipeline/historical_analysis.py.html#L925)), `build_analysis_index` ([`L1301-L1562`](source-companion/view/pipeline/historical_analysis.py.html#L1301)).
  - [`pipeline/tactical_insights.py`](source-companion/view/pipeline/tactical_insights.py.html#L1) (`369` lines): `build_tactical_insights` ([`L178-L356`](source-companion/view/pipeline/tactical_insights.py.html#L178)), `_circular_mean_deg` ([`L29-L41`](source-companion/view/pipeline/tactical_insights.py.html#L29)), `_linear_slope_per_s` ([`L75-L88`](source-companion/view/pipeline/tactical_insights.py.html#L75)).
  - [`scripts/refresh_team_analytics.py`](source-companion/view/scripts/refresh_team_analytics.py.html#L1): Regenerates `public/data/analysis/*.json`, `public/data/analysis/index.json`, `public/data/presentation/**`, and `public/data/artifacts.json`.
  - [`scripts/analysis_snapshot.py`](source-companion/view/scripts/analysis_snapshot.py.html#L1): Bounded CLI inspection tool for archive-wide or per-race coverage/quality summaries.
* **Runtime Phase**: Phase 2 (Analytics Refresh).
* **Tests Establishing Behavior**: [`tests/unit/test_historical_analysis.py`](source-companion/view/tests/unit/test_historical_analysis.py.html#L1), [`tests/unit/test_tactical_insights.py`](source-companion/view/tests/unit/test_tactical_insights.py.html#L1).
* **Lifecycle Status**: **Active**.

---

### Subsystem S7 — Environment & Weather Provenance Harvester (`pipeline/environment.py`)

* **Purpose & Conceptual Responsibility**: Reconciles recorded race-course wind sensors against Open-Meteo historical weather (`archive-api.open-meteo.com`) and Mediterranean marine wave models (`marine-api.open-meteo.com`), caches raw HTTP responses with SHA-256 verification under `Data/environment/raw/`, and writes per-race environment provenance artifacts (`public/data/environment/<race_id>.json` and `index.json`).
* **Important Files & Entry Points**:
  - [`pipeline/environment.py`](source-companion/view/pipeline/environment.py.html#L1) (`691` lines): `build_environment_dataset` ([`L490-L610`](source-companion/view/pipeline/environment.py.html#L490)), `verify_environment_dataset` ([`L613-L668`](source-companion/view/pipeline/environment.py.html#L613)).
* **Runtime Phase**: Phase 2 (offline verification `--verify` uses cached `Data/environment/raw/` without network).
* **Tests Establishing Behavior**: [`tests/unit/test_environment.py`](source-companion/view/tests/unit/test_environment.py.html#L1).
* **Lifecycle Status**: **Active** (Uncommitted new subsystem in working tree, verified by `.\run.ps1 verify`).

---

### Subsystem S8 — Causal Forecasting, Backtesting & 2027 AC38 Cup Simulator (`pipeline/prediction/`)

* **Purpose & Conceptual Responsibility**: Implements three distinct probabilistic forecasting systems under strict forward-chaining temporal cutoffs (`before_day`, `published_at_ms = state_timestamp_ms + 6000`):
  1. **Pre-Race Expected Finish Position (`pre-race-pl-mc-1`)**: Empirical Bayes Beta-Binomial completion model (`227` scheduled entries across 28 sessions) + Plackett–Luce finishing order ($\sigma = 1.2$, $\kappa = 1.8$) + tied-$N$ nonfinish rank assignment.
  2. **Live In-Race Win Probability (`live-mc-kalman-1`)**: Causal 6,000 ms reorder buffer (`ReorderBuffer`), Constant-Velocity Kalman filter (`CVKalmanFilter`), log-normal leg-time remaining model (`LegTimeModel`) with correlated calendar-time weather noise ($\rho_{\text{calendar}} = 0.65$), 500-trial exact boundary-crossing Monte Carlo, and $0.0001$ uniform tail regularization.
  3. **2027 America's Cup Winner Bounds (`cup-ac38-conditional-2`)**: 7-entrant AC38 tournament simulator (Preliminary Regattas, Challenger Selection Series RR/SF/Final, 1-point bonus carry-over, RRSAC 102.1 tie-break detection, and first-to-7 Cup Match) across a 24-scenario cross-class sensitivity grid ($N = 5{,}000$ trials/scenario), reporting `[lower, upper]` rule bounds rather than fabricated point probabilities because `34.46%` of baseline trials encounter unpublished RRSAC 102.1 tie-break procedures.
* **Important Files & Entry Points**:
  - [`pipeline/prediction/__main__.py`](source-companion/view/pipeline/prediction/__main__.py.html#L1) & [`pipeline/prediction/build.py`](source-companion/view/pipeline/prediction/build.py.html#L1): CLI entry points (`build`, `scenario`, `verify`), atomic staging, and SHA-256 verification.
  - [`pipeline/prediction/contracts.py`](source-companion/view/pipeline/prediction/contracts.py.html#L1): Canonical JSON serializer, SHA-256 hashing, schema constants, and status dictionary (`available`, `estimated`, `gate_ambiguous`, `unavailable`).
  - [`pipeline/prediction/labels.py`](source-companion/view/pipeline/prediction/labels.py.html#L1): Scheduled 227-entry ledger builder (`extract_scheduled_entry_ledger`) and race completion label extractor.
  - [`pipeline/prediction/state.py`](source-companion/view/pipeline/prediction/state.py.html#L1): Causal 6,000 ms reorder buffer (`ReorderBuffer`), Constant-Velocity Kalman filter (`CVKalmanFilter`), and checkpoint certification (`extract_causal_race_states`).
  - [`pipeline/prediction/models.py`](source-companion/view/pipeline/prediction/models.py.html#L1): `CompletionModel`, `PlackettLuceModel`, `LegTimeModel`, `PositiveDelayMixture` (always `available=False` on current archive because `sample_count=0`), and `fit_Snapshot`.
  - [`pipeline/prediction/simulation.py`](source-companion/view/pipeline/prediction/simulation.py.html#L1): `simulate_pre_race`, `simulate_live_checkpoint`, and `simulate_race_predictions`.
  - [`pipeline/prediction/cup.py`](source-companion/view/pipeline/prediction/cup.py.html#L1): `simulate_cup_2027` 7-entrant AC38 tournament simulator across the 24-scenario cross-class sensitivity grid.
  - [`pipeline/prediction/evaluation.py`](source-companion/view/pipeline/prediction/evaluation.py.html#L1): Forward-chaining day-by-day backtest evaluator and 7-metric risk budget gate.
  - [`pipeline/prediction/weather.py`](source-companion/view/pipeline/prediction/weather.py.html#L1): Open-Meteo wind integration with automatic offline course-wind fallback (`fallback_Course_wind`).
* **Runtime Phase**: Phase 3 (Forecast Build/Verify) and Phase 4 (On-demand `/api/forecast-scenarios` via `python -m pipeline.prediction scenario`).
* **Tests Establishing Behavior**: [`tests/unit/test_prediction.py`](source-companion/view/tests/unit/test_prediction.py.html#L1) (39 unit tests).
* **Lifecycle Status**:
  - `CompletionModel`, `PlackettLuceModel`, `LegTimeModel`, `CVKalmanFilter`, `simulate_pre_race`, `simulate_live_checkpoint`, `simulate_cup_2027`: **Active**.
  - `PositiveDelayMixture`: **Retained / Inactive on Current Archive** (`available = False` across all 9 model cards because `0` manoeuvre/penalty delay observations are passed into training).
  - Non-zero wind direction offset scenarios (`direction_offset_deg != 0`): **Intentionally Rejected / Guarded** (`simulate_pre_race` returns `status = "unavailable"` with reason `"Course wind-direction offset requires an explicit wind-field rotation model"`).
  - `pipeline/prediction/weather.py` (`fetch_open_meteo_wind`): **Active during online build with automatic offline fallback** (`provider = "fallback_Course_wind"` when offline).

---

### Subsystem S9 — Browser Replay Engine, Canvas Renderer & Workspace UI (`src/`, `scripts/forecastScenarios.ts`)

* **Purpose & Conceptual Responsibility**: Provides the five interactive workspaces (`Replay`, `Analysis`, `Compare`, `Reports`, `Forecast`), 60 fps `requestAnimationFrame` interpolation over the 10 Hz replay arrays, dual-mode course rendering (MapLibre GL map tiles vs 100% offline 2D metric Grid via `ViewportMatrix.ts`), class-specific AC40/AC75 foiling hull geometry (`boatModels.ts`), real-time SAT keep-clear/platform polygon overlap visualization (`contactDetector.ts`), greedy screen-space label collision avoidance (`boatPresentation.ts`), and strict client-side schema/SHA-256 verification (`analysisCatalog.ts`, `predictionCatalog.ts`).
* **Important Files & Entry Points**:
  - [`src/App.tsx`](source-companion/view/src/App.tsx.html#L1) (`771` lines): Top-level state machine, workspace router, `AbortController` race-switch lifecycle, camera mode state, and modal controllers.
  - [`src/engine/ReplayEngine.ts`](source-companion/view/src/engine/ReplayEngine.ts.html#L1) & [`src/engine/interpolate.ts`](source-companion/view/src/engine/interpolate.ts.html#L1): Binary search frame locator (`L42-L52`), `angleLerp` (`interpolate.ts:L7-L10`), and `sampleBoat` (`interpolate.ts:L12-L16`).
  - [`src/engine/analytics.ts`](source-companion/view/src/engine/analytics.ts.html#L1): `getStandings` (`L48-L84`), `compareBoats` (`L86-L99`), `windAt` (`L101-L108`).
  - [`src/engine/contactDetector.ts`](source-companion/view/src/engine/contactDetector.ts.html#L1): `AC40_PLATFORM_BORDER`, `AC40_KEEP_CLEAR_BORDER`, `testPolygonOverlapSAT` (`L141-L203`), `computePolygonIntersectionArea` (`L264-L290`).
  - [`src/components/canvas/CourseCanvas.tsx`](source-companion/view/src/components/canvas/CourseCanvas.tsx.html#L1), [`ViewportMatrix.ts`](source-companion/view/src/components/canvas/ViewportMatrix.ts.html#L1), [`boatModels.ts`](source-companion/view/src/components/canvas/boatModels.ts.html#L1), [`boatPresentation.ts`](source-companion/view/src/components/canvas/boatPresentation.ts.html#L1), [`MapLibreCourseMap.tsx`](source-companion/view/src/components/canvas/MapLibreCourseMap.tsx.html#L1).
  - [`src/components/dashboard/ForecastWorkspace.tsx`](source-companion/view/src/components/dashboard/ForecastWorkspace.tsx.html#L1), [`ReportsWorkspace.tsx`](source-companion/view/src/components/dashboard/ReportsWorkspace.tsx.html#L1), [`BoatPerformanceCard.tsx`](source-companion/view/src/components/dashboard/BoatPerformanceCard.tsx.html#L1), [`TacticalInsightsCard.tsx`](source-companion/view/src/components/dashboard/TacticalInsightsCard.tsx.html#L1), [`LiveStrategyCard.tsx`](source-companion/view/src/components/dashboard/LiveStrategyCard.tsx.html#L1).
  - [`src/components/modals/AnalysisModal.tsx`](source-companion/view/src/components/modals/AnalysisModal.tsx.html#L1), [`RaceSelectorModal.tsx`](source-companion/view/src/components/modals/RaceSelectorModal.tsx.html#L1), [`SettingsModal.tsx`](source-companion/view/src/components/modals/SettingsModal.tsx.html#L1).
  - [`scripts/forecastScenarios.ts`](source-companion/view/scripts/forecastScenarios.ts.html#L1): Vite dev/preview middleware handling `POST /api/forecast-scenarios` by invoking `python -m pipeline.prediction scenario`.
* **Runtime Phase**: Phase 4 (Middleware) and Phase 5 (Browser Interaction).
* **Tests Establishing Behavior**: 39 Vitest suites (`406` tests in `src/**/__tests__/*.test.ts(x)`) + 5 Playwright browser suites (`tests/browser/*.mjs`).
* **Lifecycle Status**: **Active**.

---

## 4. Operational Status Summary of Special & Edge Components

| Component / Feature | Location | Operational Status | Evidence & Explanation |
| :--- | :--- | :--- | :--- |
| **6-Axis Peer Performance Radar (`performance-1`)** | `pipeline/historical_analysis.py:L580` | **Active** | Exported in all 28 `public/data/analysis/<race_id>.json` files; validated by `analysisCatalog.ts:L11-L64`. |
| **Tactical Wind-Shift OLS Engine (`tactical-1`)** | `pipeline/tactical_insights.py:L178` | **Active (Projection Gated)** | Generates `3,455` snapshots across 28 races; `0` snapshots pass all 7 gates for a 5-min conditional projection (`projection_change_deg` is `null` in all `3,455` snapshots due to conservative stability/coverage gates). |
| **Pre-Race Plackett–Luce Model (`pre-race-pl-mc-1`)** | `pipeline/prediction/models.py:L103` | **Active (Weather-Invariant)** | Active across all 28 races (`227` scheduled entries). Expected positions are currently invariant across supported `tws_kt` presets (`8..22 kt`) because `PlackettLuceModel` and `CompletionModel` do not condition on `tws_kt`. |
| **Pre-Race Wind Direction Offset (`direction_offset_deg != 0`)** | `pipeline/prediction/simulate.py:L52` | **Guarded / Unavailable** | Deliberately returns `status = "unavailable"` with reason `"Course wind-direction offset requires an explicit wind-field rotation model"`. |
| **Positive Delay Mixture (`PositiveDelayMixture`)** | `pipeline/prediction/models.py:L476` | **Retained / Inactive** | Class is implemented and serialized into `.forecast/models/<hash>.json`, but `fit_Snapshot` passes empty delay lists (`sample_count = 0`), so `available = False` in all 9 model cards. |
| **AC38 Cup Winner Point Probabilities (`probabilities`)** | `pipeline/prediction/simulate.py:L730` | **Null by Contract (`rule_bounds`)** | All 7 teams have `probabilities[team] = null` in `cup_2027.json` because `1,723 / 5,000` (`34.46%`) of baseline trials hit unpublished RRSAC 102.1 tie-break procedures; UI displays `rule_bounds_by_team` and `scenario_envelope_by_team`. |
| **Python Leaderboard Time Gap (`gap_s`)** | `pipeline/analytics.py:L263` | **Superseded in UI by TS** | Python divides `gap_m` by constant `8.0` m/s in `AnalyticsEngine`, whereas the browser `Replay` leaderboard (`src/engine/analytics.ts:L71`) recomputes `gapS` dynamically using leader instantaneous `sog`. |

---

## 5. Cross-Domain Glossary (Math, Sailing, UI, Code & Artifact Fields)

| Term / Identifier | Domain | Definition, Units, Sign Convention & Repository Mapping |
| :--- | :--- | :--- |
| **AC40** | Sailing / Class | 40-foot (11.80 m hull + 1.163 m bowsprit = `12.963 m` forward of transom, `-0.215 m` rudder aft, total length `13.178 m`; foil span `10.83 m` = $\pm 5.415\text{ m}$) one-design foiling monohull used in all 28 archived 2026 sessions. Defined in [`src/components/canvas/boatModels.ts:L28-L35`](source-companion/view/src/components/canvas/boatModels.ts.html#L28). |
| **AC75** | Sailing / Class | 75-foot (`21.50 m` forward of transom, `-0.40 m` rudder aft, total length `21.90 m`; foil span `16.0 m` = $\pm 8.0\text{ m}$) Cup-class foiling monohull scheduled for the 2027 America's Cup (AC38). Defined in [`src/components/canvas/boatModels.ts:L43-L50`](source-companion/view/src/components/canvas/boatModels.ts.html#L43). |
| **Along-Leg Offset (`alongLegM`)** | Math / Compare UI | Signed projection (in metres) of vector $\vec{p}_B - \vec{p}_A$ onto the active leg direction of boat $A$: $\text{dir}_A \cdot (\Delta x \sin\theta_{\text{axis}} + \Delta y \cos\theta_{\text{axis}})$, where $\text{dir}_A = +1$ on odd (upwind) legs and $-1$ on even (downwind) legs. Positive means Boat $B$ is further ahead along $A$'s current leg direction ([`src/engine/analytics.ts:L90-L92`](source-companion/view/src/engine/analytics.ts.html#L90)). |
| **Boat-Race (`224` vs `227`)** | Statistics / Unit | The fundamental statistical observation unit for historical team/boat cohorts. A single boat participating in a single race is 1 boat-race. The archive contains **224 replayed boat-races** (with telemetry in `public/data/replays/*.json` and `analysis/index.json`) and **227 scheduled boat-races** (including 3 Naples practice races where `GBR B` was scheduled in `boat_Schedule` / `race_start_status` but recorded 0 `boat_state` packets). |
| **Bow Offset (`BOW_OFFSET_M = 12.963`)** | Geometry / Code | Distance in metres from the AC40 transom centerline GNSS origin $(0,0)$ to the forward tip of the bowsprit. Used in [`pipeline/reconstruction.py:L25,L76-L83`](source-companion/view/pipeline/reconstruction.py.html#L25) to project $\vec{p}_{\text{bow}}(t) = (x(t) + 12.963\sin\psi(t),\; y(t) + 12.963\cos\psi(t))$ for start and gate crossings. |
| **Brier Score (`brier`)** | Forecast Evaluation | Proper quadratic scoring rule $\frac{1}{M}\sum_{m=1}^M \sum_{k=1}^{K} (p_{m,k} - \mathbb{I}(y_m = k))^2$. Lower is better. Evaluated across 1,004 live checkpoints (`0.7289`) in `.forecast/backtest.json` ([`pipeline/prediction/backtest.py:L25-L34`](source-companion/view/pipeline/prediction/backtest.py.html#L25)). |
| **Circular Mean (`_circular_mean_deg`)** | Math / Directional | Mean of angles $\theta_1, \dots, \theta_n \in [0^\circ, 360^\circ)$ computed via unit-vector components $\bar{S} = \frac{1}{n}\sum \sin\theta_i$, $\bar{C} = \frac{1}{n}\sum \cos\theta_i$ as $\operatorname{atan2}(\bar{S}, \bar{C}) \bmod 360^\circ$. Undefined (`None`) when resultant length $R = \sqrt{\bar{S}^2 + \bar{C}^2} < 10^{-9}$ ([`pipeline/tactical_insights.py:L29-L41`](source-companion/view/pipeline/tactical_insights.py.html#L29)). |
| **Closure Rate (`closureMps`)** | Math / Compare UI | Rate (in $\text{m/s}$) at which the Euclidean separation between Boat $A$ and Boat $B$ is decreasing: $-\frac{(\vec{v}_B - \vec{v}_A) \cdot (\vec{p}_B - \vec{p}_A)}{\|\vec{p}_B - \vec{p}_A\|}$. Positive means boats are approaching each other; negative means separating ([`src/engine/analytics.ts:L97`](source-companion/view/src/engine/analytics.ts.html#L97)). |
| **COG (`cog`)** | Sailing / Telemetry | Course Over Ground in degrees clockwise from True North ($[0^\circ, 360^\circ)$). Direction of the boat's actual velocity vector over the water surface/seabed. Differs from `heading` ($\psi$) by leeway and current. |
| **Contrast Subspace (`contrast_cov`)** | Math / Plackett–Luce | The $(K-1)$-dimensional subspace of $\mathbb{R}^K$ orthogonal to $\mathbf{1}_K$ ($\sum_{i=1}^K \theta_i = 0$) where Plackett–Luce log-strengths are identifiable. Covariance is computed via pseudoinverse $H^+$ of the projected Hessian ([`pipeline/prediction/models.py:L226-L258`](source-companion/view/pipeline/prediction/models.py.html#L226)). |
| **Course Axis (`axis_deg`)** | Sailing / Geometry | Bearing in degrees True ($[0^\circ, 360^\circ)$) from the leeward gate midpoint (or start midpoint on Leg 1) to the windward gate midpoint. Defines the primary upwind reference direction for VMG and `Course` camera rotation. |
| **DNF / DNS / OCS / RET** | Sailing / Rules | Non-finish classifications: **DNF** = Did Not Finish (started validly, did not cross finish before window end); **DNS** = Did Not Start (never crossed start line after gun); **OCS** = On Course Side (crossed start line early / flagged `ocs: true` without clearing); **RET** = Retired. |
| **Gun Time (`gun_time`)** | Chronology | Unix epoch timestamp in milliseconds (`int`) when the race start signal fired ($T = 0\text{ s}$ elapsed). Pre-start telemetry has $t < \text{gun\_time}$. |
| **Gybe (`GYBE`)** | Sailing / Manoeuvre | Turning the stern of the boat through the wind while sailing downwind ($|\overline{\text{TWA}}| \ge 90^\circ$), flipping `twa` sign across the dead-downwind axis ($180^\circ$). |
| **Heading (`heading`, $\psi$)** | Sailing / Telemetry | Direction the boat's bow points in degrees clockwise from True North ($[0^\circ, 360^\circ)$). Used to orient hull polygons and project the bowsprit tip. |
| **Keep-Clear Border (`keep_clear_border`)** | Umpiring / Geometry | Convex 9-vertex safety envelope expanded by $+2.0\text{ m}$ laterally around the physical `platform_border` ($\pm 7.415\text{ m}$ width for AC40, $\pm 10.0\text{ m}$ for AC75). Overlap between two boats' `keep_clear_border` polygons triggers a `virtual_contact_incident` ([`src/engine/contactDetector.ts:L27-L38`](source-companion/view/src/engine/contactDetector.ts.html#L27)). |
| **Lateral Offset (`lateralM`)** | Math / Compare UI | Signed perpendicular offset (in metres) of Boat $B$ relative to Boat $A$'s course axis: $\Delta x \cos\theta_{\text{axis}} - \Delta y \sin\theta_{\text{axis}}$. Positive means Boat $B$ lies to the right (eastward when $\theta_{\text{axis}} = 0^\circ$) of the axis line through $A$ ([`src/engine/analytics.ts:L93`](source-companion/view/src/engine/analytics.ts.html#L93)). |
| **Matched-Leg Scope (`matched_legs`)** | Analytics / Radar | Subset of race legs where **both** the subject boat and at least `MIN_PEER_COUNT = 1` peer boat have valid (`derived` or `verified`) leg metrics. Prevents wind shifts on uncompleted legs from biasing `performance-1` indices ([`pipeline/historical_analysis.py:L608-L654`](source-companion/view/pipeline/historical_analysis.py.html#L608)). |
| **Normalized RPS (`norm_rps`)** | Forecast Evaluation | Ranked Probability Score normalized by $K-1$ across finishing positions $1..K$: $\frac{1}{K-1}\sum_{r=1}^{K-1} (F_{\text{pred}}(r) - F_{\text{actual}}(r))^2$, measuring cumulative distribution accuracy for ordinal rankings ([`pipeline/prediction/backtest.py:L60-L82`](source-companion/view/pipeline/prediction/backtest.py.html#L60)). |
| **Peer-Normalized Index (`index`)** | Analytics / Radar | Dimensionless performance score where `100.0` represents the self-excluding peer mean. On leg $\ell$, $I_{b,\ell} = 100 \cdot \frac{x_{b,\ell}}{\frac{1}{|P_{b,\ell}|}\sum_{p \in P_{b,\ell}} x_{p,\ell}}$. The race dimension index is the unweighted mean across matched legs: $I_b = \frac{1}{|L_b|}\sum_{\ell \in L_b} I_{b,\ell}$ ([`pipeline/historical_analysis.py:L656-L712`](source-companion/view/pipeline/historical_analysis.py.html#L656)). |
| **Platform Border (`platform_border`)** | Geometry / Vessel | Physical 9-vertex convex envelope of the boat hull and deployed foils ($\pm 5.415\text{ m}$ span, `-0.215 m` to `+12.963 m` length for AC40). Overlap of two `platform_border` polygons classifies a contact as `COLLISION` rather than `PROXIMITY` ([`pipeline/analytics.py:L170-L185`](source-companion/view/pipeline/analytics.py.html#L170)). |
| **Publication Time (`published_at_ms`)** | Causal Forecasting | Timestamp when a live checkpoint forecast becomes legally visible to the UI: $\text{published\_at\_ms} = \text{state\_timestamp\_ms} + 6000\text{ ms}$, accounting for the 6.0 s causal reorder buffer ([`pipeline/prediction/ingest.py:L21`](source-companion/view/pipeline/prediction/ingest.py.html#L21), enforced in UI by [`src/engine/predictionCatalog.ts:L133-L146`](source-companion/view/src/engine/predictionCatalog.ts.html#L133)). |
| **Retention Pct (`retention_pct`)** | Manoeuvre Analytics | Percentage of entry speed retained at the minimum speed trough during a tack or gybe: $100 \times \frac{\text{minimum\_speed\_kt}}{\text{entry\_speed\_kt}} = 100 - \text{speed\_loss\_pct}$ ([`pipeline/historical_analysis.py:L302-L315`](source-companion/view/pipeline/historical_analysis.py.html#L302)). Used as a "higher is better" axis in `performance-1`. |
| **RRSAC 102.1** | AC38 Tournament Rules | Racing Rules of Sailing America's Cup tie-break rule invoked when 3+ teams are tied at a stage cutoff or when match/preliminary tie-break standings are unresolvable from AC40 fleet priors. Accounts for `1,723 / 5,000` (`34.46%`) of unresolved baseline trials in `cup_2027.json`. |
| **SOG (`sog`)** | Sailing / Telemetry | Speed Over Ground in knots ($\text{kt}$, where $1\text{ kt} = 1852 / 3600\text{ m/s} \approx 0.514444\text{ m/s}$). |
| **Tack (`TACK`)** | Sailing / Manoeuvre | Turning the bow of the boat through the wind while sailing upwind ($|\overline{\text{TWA}}| < 90^\circ$), flipping `twa` sign across $0^\circ$. |
| **Tied-$N$ Convention (`nonfinish_score = "N"`)** | Pre-Race Forecast | Scoring rule that assigns every non-finishing boat (DNS/DNF/OCS/RET) the worst scheduled field rank $N = K$ (`len(boat_ids)`), whereas finishers receive ranks $1..m$ ($m \le K$). Under this convention, if $\mathbb{P}(\text{nonfinish}) > 0$, the sum of expected positions exceeds $\frac{K(K+1)}{2}$. |
| **TWA (`twa`)** | Sailing / Telemetry | Signed True Wind Angle in degrees ($[-180^\circ, +180^\circ]$), normalized via `signed_angle_deg(twd - heading)`. Magnitude $|\text{TWA}| < 90^\circ$ is upwind; $|\text{TWA}| \ge 90^\circ$ is downwind. |
| **TWD (`twd`)** | Sailing / Telemetry | True Wind Direction in degrees clockwise from True North ($[0^\circ, 360^\circ)$) indicating the bearing **from which** the true wind blows. |
| **TWS (`tws`)** | Sailing / Telemetry | True Wind Speed in knots ($\text{kt}$). |
| **VMG (`vmg`)** | Sailing / Analytics | Velocity Made Good in knots ($\text{kt}$). **Important Sign Distinction**: In raw/replay telemetry (`replay.telemetry.boats[id].vmg`), `vmg` is wind-referenced ($\text{SOG}\cos(\text{TWA})$), which becomes **negative** downwind when $|\text{TWA}| > 90^\circ$. In `historical_analysis.py` (`_leg_Entry_for_boat` and `performance-1`), leg VMG is **mark/axis-referenced** along the active leg direction and is **positive** for both upwind and downwind progress toward the next gate! |

---

## 6. Complete First-Party File Coverage Table (209 Files)

Every file listed below has been inspected, hashed, and mirrored into [`source-companion/`](source-companion/index.html) with clickable line anchors:

| # | First-Party File Path (Click to Browse Source) | Category | Git Status | Lines | Bytes | SHA-256 Prefix |
| ---: | :--- | :--- | :--- | ---: | ---: | :--- |
| 1 | [`AGENTS.md`](source-companion/view/AGENTS.md.html#L1) | Root Configuration & Entry Scripts | `clean` | 9 | 1,655 | `30f4c385b537bc63…` |
| 2 | [`PROJECT.md`](source-companion/view/PROJECT.md.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 33 | 4,428 | `e1fa6f62e373e14b…` |
| 3 | [`README.md`](source-companion/view/README.md.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 48 | 3,699 | `f38ff38b3548001a…` |
| 4 | [`index.html`](source-companion/view/index.html.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 16 | 587 | `3a72a7c82922df05…` |
| 5 | [`package.json`](source-companion/view/package.json.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 37 | 1,350 | `bb79fd09a5f9f150…` |
| 6 | [`pyproject.toml`](source-companion/view/pyproject.toml.html#L1) | Root Configuration & Entry Scripts | `clean` | 13 | 364 | `23aadea66160e23e…` |
| 7 | [`run.ps1`](source-companion/view/run.ps1.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 50 | 2,766 | `43e3de48e8ece92d…` |
| 8 | [`tsconfig.json`](source-companion/view/tsconfig.json.html#L1) | Root Configuration & Entry Scripts | `clean` | 7 | 119 | `770b4140bbb581e2…` |
| 9 | [`tsconfig.app.json`](source-companion/view/tsconfig.app.json.html#L1) | Root Configuration & Entry Scripts | `clean` | 25 | 735 | `8ad1a485c39fcb22…` |
| 10 | [`tsconfig.node.json`](source-companion/view/tsconfig.node.json.html#L1) | Root Configuration & Entry Scripts | `clean` | 15 | 393 | `62e382d75e04b419…` |
| 11 | [`vite.config.ts`](source-companion/view/vite.config.ts.html#L1) | Root Configuration & Entry Scripts | `modified (M)` | 18 | 751 | `2fb613edf7b0f984…` |
| 12 | [`docs/annotation_revision_plan.md`](source-companion/view/docs/annotation_revision_plan.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 163 | 22,175 | `3e6f21da7a24b36c…` |
| 13 | [`docs/annotation_revision_verification.md`](source-companion/view/docs/annotation_revision_verification.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 84 | 10,001 | `a2cf4dcc0858780d…` |
| 14 | [`docs/architecture.md`](source-companion/view/docs/architecture.md.html#L1) | Technical Documentation (docs/) | `clean` | 29 | 4,288 | `15197ffbe6c1f243…` |
| 15 | [`docs/browser_feedback_verification.md`](source-companion/view/docs/browser_feedback_verification.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 45 | 5,843 | `10e182fa3c02cb65…` |
| 16 | [`docs/dashboard_contract.md`](source-companion/view/docs/dashboard_contract.md.html#L1) | Technical Documentation (docs/) | `modified (M)` | 62 | 8,975 | `13bf1c5a03dd42f1…` |
| 17 | [`docs/dashboard_verification.md`](source-companion/view/docs/dashboard_verification.md.html#L1) | Technical Documentation (docs/) | `clean` | 64 | 5,468 | `ba2ff0080acc04e8…` |
| 18 | [`docs/data_schema.md`](source-companion/view/docs/data_schema.md.html#L1) | Technical Documentation (docs/) | `modified (M)` | 68 | 7,860 | `72b3c830e38c0acb…` |
| 19 | [`docs/derived_metrics.md`](source-companion/view/docs/derived_metrics.md.html#L1) | Technical Documentation (docs/) | `clean` | 23 | 2,528 | `658096d86d207844…` |
| 20 | [`docs/design-system.md`](source-companion/view/docs/design-system.md.html#L1) | Technical Documentation (docs/) | `modified (M)` | 80 | 8,502 | `e7fe757d850904b7…` |
| 21 | [`docs/environment_data.md`](source-companion/view/docs/environment_data.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 71 | 3,906 | `277a54c117b7c4c0…` |
| 22 | [`docs/forecast_rules_sources.json`](source-companion/view/docs/forecast_rules_sources.json.html#L1) | Technical Documentation (docs/) | `clean` | 74 | 2,759 | `eb055645ba08523f…` |
| 23 | [`docs/forecasting_implementation.md`](source-companion/view/docs/forecasting_implementation.md.html#L1) | Technical Documentation (docs/) | `modified (M)` | 156 | 22,836 | `cc04c080cddb6eba…` |
| 24 | [`docs/forecasting_research_review.md`](source-companion/view/docs/forecasting_research_review.md.html#L1) | Technical Documentation (docs/) | `clean` | 180 | 23,353 | `458ba369b6c04899…` |
| 25 | [`docs/forecasting_review_resolution.md`](source-companion/view/docs/forecasting_review_resolution.md.html#L1) | Technical Documentation (docs/) | `clean` | 200 | 27,287 | `dcbc436d98d8fc5f…` |
| 26 | [`docs/google_store_ui_redesign_plan.md`](source-companion/view/docs/google_store_ui_redesign_plan.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 345 | 36,344 | `54dbf1c85bb9a7b3…` |
| 27 | [`docs/historical_analysis.md`](source-companion/view/docs/historical_analysis.md.html#L1) | Technical Documentation (docs/) | `modified (M)` | 65 | 15,900 | `c9a771555328a03c…` |
| 28 | [`docs/independent_probability_review_prompt.md`](source-companion/view/docs/independent_probability_review_prompt.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 237 | 26,619 | `41744c0bc1e51232…` |
| 29 | [`docs/ingesting_new_regattas.md`](source-companion/view/docs/ingesting_new_regattas.md.html#L1) | Technical Documentation (docs/) | `clean` | 28 | 2,790 | `f277d7854c1a3b67…` |
| 30 | [`docs/probability_execution_plan.md`](source-companion/view/docs/probability_execution_plan.md.html#L1) | Technical Documentation (docs/) | `clean` | 285 | 56,169 | `9a42b41de593e425…` |
| 31 | [`docs/reconstruction_math.md`](source-companion/view/docs/reconstruction_math.md.html#L1) | Technical Documentation (docs/) | `clean` | 26 | 2,249 | `3425a0dfef9ecc6f…` |
| 32 | [`docs/source_audit.md`](source-companion/view/docs/source_audit.md.html#L1) | Technical Documentation (docs/) | `clean` | 54 | 9,575 | `154a2bb940fcc311…` |
| 33 | [`docs/team_analytics.md`](source-companion/view/docs/team_analytics.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 78 | 12,350 | `f7babc691374d8c7…` |
| 34 | [`docs/team_analytics_plan.md`](source-companion/view/docs/team_analytics_plan.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 21 | 3,196 | `073ec0830cb758c9…` |
| 35 | [`docs/ui_redesign_verification.md`](source-companion/view/docs/ui_redesign_verification.md.html#L1) | Technical Documentation (docs/) | `untracked (??)` | 89 | 7,532 | `dfce0bdd592a6541…` |
| 36 | [`pipeline/__init__.py`](source-companion/view/pipeline/__init__.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 3 | 98 | `56adcedd813fafd8…` |
| 37 | [`pipeline/analytics.py`](source-companion/view/pipeline/analytics.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 344 | 13,331 | `b4b7523f888764ce…` |
| 38 | [`pipeline/config.py`](source-companion/view/pipeline/config.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 274 | 8,856 | `c64840e7c513d036…` |
| 39 | [`pipeline/contact_coalescer.py`](source-companion/view/pipeline/contact_coalescer.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 394 | 13,581 | `2bcbc83dbdd295fc…` |
| 40 | [`pipeline/environment.py`](source-companion/view/pipeline/environment.py.html#L1) | Python Core Pipeline (pipeline/) | `untracked (??)` | 362 | 19,035 | `083d178e06df3b0d…` |
| 41 | [`pipeline/export_replay.py`](source-companion/view/pipeline/export_replay.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 511 | 21,000 | `22d1fb8c3a349391…` |
| 42 | [`pipeline/historical_analysis.py`](source-companion/view/pipeline/historical_analysis.py.html#L1) | Python Core Pipeline (pipeline/) | `modified (M)` | 1,065 | 70,673 | `edbffb92c77922f1…` |
| 43 | [`pipeline/identity.py`](source-companion/view/pipeline/identity.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 13 | 763 | `acb8de51b2c091bf…` |
| 44 | [`pipeline/ingest.py`](source-companion/view/pipeline/ingest.py.html#L1) | Python Core Pipeline (pipeline/) | `modified (M)` | 907 | 37,778 | `3f08cded4b2b0398…` |
| 45 | [`pipeline/manoeuvres.py`](source-companion/view/pipeline/manoeuvres.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 225 | 8,815 | `659472f4be406666…` |
| 46 | [`pipeline/prediction/__init__.py`](source-companion/view/pipeline/prediction/__init__.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 3 | 152 | `7ae00255be1269b3…` |
| 47 | [`pipeline/prediction/__main__.py`](source-companion/view/pipeline/prediction/__main__.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 56 | 3,165 | `21dc97945c65d256…` |
| 48 | [`pipeline/prediction/backtest.py`](source-companion/view/pipeline/prediction/backtest.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 146 | 10,237 | `b4d0ff39b8715820…` |
| 49 | [`pipeline/prediction/build.py`](source-companion/view/pipeline/prediction/build.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 437 | 28,608 | `1d9a9640726dff03…` |
| 50 | [`pipeline/prediction/contracts.py`](source-companion/view/pipeline/prediction/contracts.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 286 | 18,252 | `e1c0a7bc16e5ad08…` |
| 51 | [`pipeline/prediction/cup.py`](source-companion/view/pipeline/prediction/cup.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 661 | 41,399 | `e9748ed4e48c3571…` |
| 52 | [`pipeline/prediction/evaluation.py`](source-companion/view/pipeline/prediction/evaluation.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 130 | 7,847 | `c6eb7c280b29df8d…` |
| 53 | [`pipeline/prediction/labels.py`](source-companion/view/pipeline/prediction/labels.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 196 | 11,212 | `8068858b468a29e2…` |
| 54 | [`pipeline/prediction/models.py`](source-companion/view/pipeline/prediction/models.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 856 | 43,831 | `86049eb3c98c3c52…` |
| 55 | [`pipeline/prediction/simulation.py`](source-companion/view/pipeline/prediction/simulation.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 516 | 29,905 | `a222f109b0877dc3…` |
| 56 | [`pipeline/prediction/source.py`](source-companion/view/pipeline/prediction/source.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 238 | 12,670 | `4512b6955553772b…` |
| 57 | [`pipeline/prediction/state.py`](source-companion/view/pipeline/prediction/state.py.html#L1) | Python Forecasting (pipeline/prediction/) | `modified (M)` | 313 | 18,609 | `f5657d42e60bfa03…` |
| 58 | [`pipeline/prediction/weather.py`](source-companion/view/pipeline/prediction/weather.py.html#L1) | Python Forecasting (pipeline/prediction/) | `clean` | 54 | 2,620 | `2c7e1353f16c1e3d…` |
| 59 | [`pipeline/projection.py`](source-companion/view/pipeline/projection.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 175 | 5,638 | `cc854f7ac3d9572c…` |
| 60 | [`pipeline/reconstruction.py`](source-companion/view/pipeline/reconstruction.py.html#L1) | Python Core Pipeline (pipeline/) | `clean` | 612 | 24,849 | `f0d82209444e0c0c…` |
| 61 | [`pipeline/run_pipeline.py`](source-companion/view/pipeline/run_pipeline.py.html#L1) | Python Core Pipeline (pipeline/) | `modified (M)` | 370 | 14,569 | `5d3846c497705f3a…` |
| 62 | [`pipeline/tactical_insights.py`](source-companion/view/pipeline/tactical_insights.py.html#L1) | Python Core Pipeline (pipeline/) | `untracked (??)` | 189 | 11,419 | `aea556291b579da7…` |
| 63 | [`scripts/analysis_snapshot.py`](source-companion/view/scripts/analysis_snapshot.py.html#L1) | Utility & Middleware Scripts (scripts/) | `clean` | 41 | 2,325 | `42a082bd822792aa…` |
| 64 | [`scripts/build_artifact_inventory.py`](source-companion/view/scripts/build_artifact_inventory.py.html#L1) | Utility & Middleware Scripts (scripts/) | `modified (M)` | 91 | 6,349 | `69b2e00a04bb2cda…` |
| 65 | [`scripts/build_race_previews.py`](source-companion/view/scripts/build_race_previews.py.html#L1) | Utility & Middleware Scripts (scripts/) | `untracked (??)` | 74 | 3,631 | `80ef7af5ce4a7148…` |
| 66 | [`scripts/build_report_exports.py`](source-companion/view/scripts/build_report_exports.py.html#L1) | Utility & Middleware Scripts (scripts/) | `untracked (??)` | 80 | 4,261 | `4cecda6fa24cda4b…` |
| 67 | [`scripts/forecastArtifacts.ts`](source-companion/view/scripts/forecastArtifacts.ts.html#L1) | Utility & Middleware Scripts (scripts/) | `untracked (??)` | 79 | 3,587 | `383f2c34144225dc…` |
| 68 | [`scripts/forecastScenarios.ts`](source-companion/view/scripts/forecastScenarios.ts.html#L1) | Utility & Middleware Scripts (scripts/) | `untracked (??)` | 199 | 13,773 | `7f2f63f7077ca7c8…` |
| 69 | [`scripts/refresh_team_analytics.py`](source-companion/view/scripts/refresh_team_analytics.py.html#L1) | Utility & Middleware Scripts (scripts/) | `untracked (??)` | 261 | 16,509 | `4d6afb83619601bf…` |
| 70 | [`src/app.css`](source-companion/view/src/app.css.html#L1) | Frontend App State, Types & Styles (src/) | `clean` | 1,126 | 21,155 | `146b37c35444ac26…` |
| 71 | [`src/App.tsx`](source-companion/view/src/App.tsx.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 210 | 12,277 | `28852e045ef6b5cc…` |
| 72 | [`src/components/canvas/boatModels.test.ts`](source-companion/view/src/components/canvas/boatModels.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 277 | 11,654 | `29081572bcaa75f4…` |
| 73 | [`src/components/canvas/boatModels.ts`](source-companion/view/src/components/canvas/boatModels.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 394 | 10,968 | `a7a30542461c8077…` |
| 74 | [`src/components/canvas/boatPresentation.test.ts`](source-companion/view/src/components/canvas/boatPresentation.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `untracked (??)` | 36 | 2,292 | `a282ec9754dedf80…` |
| 75 | [`src/components/canvas/boatPresentation.ts`](source-companion/view/src/components/canvas/boatPresentation.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `untracked (??)` | 66 | 4,646 | `4743a4b2d81ba321…` |
| 76 | [`src/components/canvas/cameraAdversarial.test.ts`](source-companion/view/src/components/canvas/cameraAdversarial.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 442 | 18,116 | `fe1d571168db7c32…` |
| 77 | [`src/components/canvas/cameraStateSyncAdversarial.test.ts`](source-companion/view/src/components/canvas/cameraStateSyncAdversarial.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 470 | 17,025 | `ddc89cb9c8b608d5…` |
| 78 | [`src/components/canvas/CourseCanvas.tsx`](source-companion/view/src/components/canvas/CourseCanvas.tsx.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 602 | 22,879 | `d304a18c3b6ad5d9…` |
| 79 | [`src/components/canvas/courseGeometry.test.ts`](source-companion/view/src/components/canvas/courseGeometry.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 83 | 4,262 | `1f50a5886ae21f93…` |
| 80 | [`src/components/canvas/DynamicVesselLayer.ts`](source-companion/view/src/components/canvas/DynamicVesselLayer.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 707 | 25,701 | `ec59aea4450330d3…` |
| 81 | [`src/components/canvas/foilingGeometryStress.test.ts`](source-companion/view/src/components/canvas/foilingGeometryStress.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 788 | 33,787 | `4e40863c265e9c75…` |
| 82 | [`src/components/canvas/mapStyle.ts`](source-companion/view/src/components/canvas/mapStyle.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 96 | 2,807 | `720da1f988d3c5c7…` |
| 83 | [`src/components/canvas/renderPalette.ts`](source-companion/view/src/components/canvas/renderPalette.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `untracked (??)` | 18 | 589 | `84094cdc15ba7a08…` |
| 84 | [`src/components/canvas/StaticCourseLayer.ts`](source-companion/view/src/components/canvas/StaticCourseLayer.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 74 | 2,455 | `3f87ebf31e8796f1…` |
| 85 | [`src/components/canvas/viewModeStress.test.ts`](source-companion/view/src/components/canvas/viewModeStress.test.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `modified (M)` | 288 | 12,522 | `39ad75ea4ac2c5cd…` |
| 86 | [`src/components/canvas/ViewportMatrix.ts`](source-companion/view/src/components/canvas/ViewportMatrix.ts.html#L1) | Frontend 2D/Map Canvas (src/components/canvas/) | `clean` | 48 | 2,953 | `81690c64fec2fcef…` |
| 87 | [`src/components/dashboard/adversarial_race_timeline_m10_1.test.ts`](source-companion/view/src/components/dashboard/adversarial_race_timeline_m10_1.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `clean` | 45 | 2,528 | `2f24ac95bcf375e0…` |
| 88 | [`src/components/dashboard/analysis-light.css`](source-companion/view/src/components/dashboard/analysis-light.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 169 | 9,934 | `8c3c3b2886563335…` |
| 89 | [`src/components/dashboard/boat-course-controls.css`](source-companion/view/src/components/dashboard/boat-course-controls.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 37 | 3,818 | `e112e66ccce3c81c…` |
| 90 | [`src/components/dashboard/BoatCourseControls.tsx`](source-companion/view/src/components/dashboard/BoatCourseControls.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 23 | 3,784 | `2072501ed69f52fd…` |
| 91 | [`src/components/dashboard/BoatPerformanceCard.adversarial.test.ts`](source-companion/view/src/components/dashboard/BoatPerformanceCard.adversarial.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 32 | 1,546 | `f1d8859d2445297c…` |
| 92 | [`src/components/dashboard/BoatPerformanceCard.test.ts`](source-companion/view/src/components/dashboard/BoatPerformanceCard.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 41 | 2,068 | `50aaa1d4ddb6f8f0…` |
| 93 | [`src/components/dashboard/BoatPerformanceCard.tsx`](source-companion/view/src/components/dashboard/BoatPerformanceCard.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 180 | 7,296 | `84c2062dff792ba0…` |
| 94 | [`src/components/dashboard/BoatPerformanceRadar.tsx`](source-companion/view/src/components/dashboard/BoatPerformanceRadar.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 118 | 19,610 | `c1d855982f2def0d…` |
| 95 | [`src/components/dashboard/BoatVisibilityFilter.tsx`](source-companion/view/src/components/dashboard/BoatVisibilityFilter.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 18 | 1,941 | `86e0a749c9c1faa8…` |
| 96 | [`src/components/dashboard/cupEvidence.css`](source-companion/view/src/components/dashboard/cupEvidence.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 16 | 1,307 | `6f4302ae78cf0caf…` |
| 97 | [`src/components/dashboard/dashboard.css`](source-companion/view/src/components/dashboard/dashboard.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 348 | 30,824 | `e9fc5081c388883a…` |
| 98 | [`src/components/dashboard/EventsNotesPanel.adversarial.test.ts`](source-companion/view/src/components/dashboard/EventsNotesPanel.adversarial.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 43 | 2,017 | `27b2ce26d30be2e2…` |
| 99 | [`src/components/dashboard/EventsNotesPanel.tsx`](source-companion/view/src/components/dashboard/EventsNotesPanel.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 217 | 8,100 | `9bd6e41cecc08a28…` |
| 100 | [`src/components/dashboard/forecast.css`](source-companion/view/src/components/dashboard/forecast.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 74 | 7,427 | `5c121a4052a00035…` |
| 101 | [`src/components/dashboard/ForecastWorkspace.tsx`](source-companion/view/src/components/dashboard/ForecastWorkspace.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 218 | 28,432 | `a6842cdbb1ee8166…` |
| 102 | [`src/components/dashboard/performance-radar.css`](source-companion/view/src/components/dashboard/performance-radar.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 95 | 9,631 | `ccba5a63a08cc1c8…` |
| 103 | [`src/components/dashboard/RaceStatusLeaderboard.tsx`](source-companion/view/src/components/dashboard/RaceStatusLeaderboard.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 178 | 7,030 | `b83c63c7f3f59286…` |
| 104 | [`src/components/dashboard/RaceTimelinePanel.test.ts`](source-companion/view/src/components/dashboard/RaceTimelinePanel.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 62 | 3,468 | `d877bdfdf1a359a0…` |
| 105 | [`src/components/dashboard/RaceTimelinePanel.tsx`](source-companion/view/src/components/dashboard/RaceTimelinePanel.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 362 | 13,224 | `9e1c50067ce473c9…` |
| 106 | [`src/components/dashboard/reports.css`](source-companion/view/src/components/dashboard/reports.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 61 | 6,110 | `d4ea91abba1d8c69…` |
| 107 | [`src/components/dashboard/ReportsWorkspace.test.ts`](source-companion/view/src/components/dashboard/ReportsWorkspace.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 32 | 3,435 | `7d58bd5ace9e3941…` |
| 108 | [`src/components/dashboard/ReportsWorkspace.tsx`](source-companion/view/src/components/dashboard/ReportsWorkspace.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 86 | 10,695 | `5662f6c5d891509a…` |
| 109 | [`src/components/dashboard/TacticalDashboard.tsx`](source-companion/view/src/components/dashboard/TacticalDashboard.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 125 | 14,274 | `9d3f8f4bc51ec517…` |
| 110 | [`src/components/dashboard/TacticalHeader.tsx`](source-companion/view/src/components/dashboard/TacticalHeader.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 63 | 8,771 | `602be68a927b8f15…` |
| 111 | [`src/components/dashboard/TacticalInsightsPanel.tsx`](source-companion/view/src/components/dashboard/TacticalInsightsPanel.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 45 | 4,018 | `cb217b5e64a4290c…` |
| 112 | [`src/components/dashboard/TacticalMapOverlay.adversarial.test.ts`](source-companion/view/src/components/dashboard/TacticalMapOverlay.adversarial.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 413 | 17,224 | `385ba8a98f7ea698…` |
| 113 | [`src/components/dashboard/TacticalMapOverlay.test.ts`](source-companion/view/src/components/dashboard/TacticalMapOverlay.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 301 | 11,885 | `d8bee63a4754df08…` |
| 114 | [`src/components/dashboard/TacticalMapOverlay.tsx`](source-companion/view/src/components/dashboard/TacticalMapOverlay.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 226 | 8,821 | `a3d8a5ab2fbf41e4…` |
| 115 | [`src/components/dashboard/TeamAnalytics.test.ts`](source-companion/view/src/components/dashboard/TeamAnalytics.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 192 | 14,755 | `6181a36774175361…` |
| 116 | [`src/components/dashboard/TeamDebrief.tsx`](source-companion/view/src/components/dashboard/TeamDebrief.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 21 | 1,934 | `b81b41b5e3954d13…` |
| 117 | [`src/components/dashboard/TelemetryWorkspace.adversarial.test.ts`](source-companion/view/src/components/dashboard/TelemetryWorkspace.adversarial.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `clean` | 469 | 17,385 | `28b6fe3a13b6b8fb…` |
| 118 | [`src/components/dashboard/TelemetryWorkspace.test.ts`](source-companion/view/src/components/dashboard/TelemetryWorkspace.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `clean` | 446 | 15,799 | `39e64a33f36a062c…` |
| 119 | [`src/components/dashboard/TelemetryWorkspace.tsx`](source-companion/view/src/components/dashboard/TelemetryWorkspace.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `clean` | 617 | 22,798 | `eaa549ffce4ba64e…` |
| 120 | [`src/components/dashboard/TelemetryWorkspaceAdversarial.test.ts`](source-companion/view/src/components/dashboard/TelemetryWorkspaceAdversarial.test.ts.html#L1) | Frontend Workspace & UI Components (src/components/) | `clean` | 360 | 15,064 | `be5687478eca5c4c…` |
| 121 | [`src/components/dashboard/workspaces.css`](source-companion/view/src/components/dashboard/workspaces.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 93 | 8,967 | `b3bf6ebaeeb076cb…` |
| 122 | [`src/components/modals/AnalysisModal.tsx`](source-companion/view/src/components/modals/AnalysisModal.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 323 | 40,134 | `2a015dd2ce3e0ee0…` |
| 123 | [`src/components/modals/race-library.css`](source-companion/view/src/components/modals/race-library.css.html#L1) | Frontend Workspace & UI Components (src/components/) | `untracked (??)` | 71 | 6,581 | `624b84a0a25c5448…` |
| 124 | [`src/components/modals/RacePickerModal.tsx`](source-companion/view/src/components/modals/RacePickerModal.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 92 | 7,888 | `4d5e5395df26a644…` |
| 125 | [`src/components/panels/ComparisonPanel.tsx`](source-companion/view/src/components/panels/ComparisonPanel.tsx.html#L1) | Frontend Workspace & UI Components (src/components/) | `modified (M)` | 20 | 3,511 | `3cdbc8bafd0f3217…` |
| 126 | [`src/engine/analysisCatalog.test.ts`](source-companion/view/src/engine/analysisCatalog.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 71 | 6,926 | `83bd07e525b26c65…` |
| 127 | [`src/engine/analysisCatalog.ts`](source-companion/view/src/engine/analysisCatalog.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `modified (M)` | 120 | 10,469 | `25768b3b6f174f1d…` |
| 128 | [`src/engine/analysisNavigation.test.ts`](source-companion/view/src/engine/analysisNavigation.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 24 | 1,206 | `cf5cf7e091e7f1bf…` |
| 129 | [`src/engine/analytics.test.ts`](source-companion/view/src/engine/analytics.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 126 | 6,168 | `0f8650aef1a66292…` |
| 130 | [`src/engine/analytics.ts`](source-companion/view/src/engine/analytics.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 108 | 5,411 | `5ba0b7ea1d34d47e…` |
| 131 | [`src/engine/catalog.test.ts`](source-companion/view/src/engine/catalog.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 17 | 1,091 | `522481162590bfaf…` |
| 132 | [`src/engine/catalog.ts`](source-companion/view/src/engine/catalog.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 57 | 3,568 | `ca0ad98fa627af56…` |
| 133 | [`src/engine/challengerM4_2.test.ts`](source-companion/view/src/engine/challengerM4_2.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 411 | 18,350 | `58e7402848f5795d…` |
| 134 | [`src/engine/contactDetector.test.ts`](source-companion/view/src/engine/contactDetector.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 193 | 7,435 | `825967ace7e1b1be…` |
| 135 | [`src/engine/contactDetector.ts`](source-companion/view/src/engine/contactDetector.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 406 | 12,095 | `5599513e6af10cb8…` |
| 136 | [`src/engine/contactDetectorStress.test.ts`](source-companion/view/src/engine/contactDetectorStress.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 199 | 8,018 | `df11ee54e1f23576…` |
| 137 | [`src/engine/course.test.ts`](source-companion/view/src/engine/course.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 26 | 1,472 | `808854078781a6b1…` |
| 138 | [`src/engine/course.ts`](source-companion/view/src/engine/course.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 15 | 525 | `22e7224b6f96f51d…` |
| 139 | [`src/engine/dynamicMarksStress.test.ts`](source-companion/view/src/engine/dynamicMarksStress.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 465 | 18,168 | `dc0a29c4caf416f3…` |
| 140 | [`src/engine/environment.test.ts`](source-companion/view/src/engine/environment.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 121 | 7,744 | `d6e93d2c60942596…` |
| 141 | [`src/engine/environment.ts`](source-companion/view/src/engine/environment.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 103 | 7,280 | `08a4bc30060e962e…` |
| 142 | [`src/engine/forecastArtifactRouting.test.ts`](source-companion/view/src/engine/forecastArtifactRouting.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 148 | 7,654 | `01dd4dddb70e07e2…` |
| 143 | [`src/engine/forecastScenarios.test.ts`](source-companion/view/src/engine/forecastScenarios.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 37 | 2,424 | `bdf695426c27c7fa…` |
| 144 | [`src/engine/forecastScenarios.ts`](source-companion/view/src/engine/forecastScenarios.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 43 | 3,004 | `5d96161cdb6a481a…` |
| 145 | [`src/engine/forecastScenarioService.test.ts`](source-companion/view/src/engine/forecastScenarioService.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `untracked (??)` | 137 | 8,524 | `d6b47d5839c99425…` |
| 146 | [`src/engine/interpolate.test.ts`](source-companion/view/src/engine/interpolate.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 8 | 425 | `24bacb06cfaeb82e…` |
| 147 | [`src/engine/interpolate.ts`](source-companion/view/src/engine/interpolate.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 17 | 1,235 | `36e7ace2130f7a4f…` |
| 148 | [`src/engine/predictionCatalog.test.ts`](source-companion/view/src/engine/predictionCatalog.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `modified (M)` | 326 | 23,320 | `a10cb700d3d7e98b…` |
| 149 | [`src/engine/predictionCatalog.ts`](source-companion/view/src/engine/predictionCatalog.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `modified (M)` | 230 | 23,022 | `e4f163b3166b80b9…` |
| 150 | [`src/engine/ReplayEngine.test.ts`](source-companion/view/src/engine/ReplayEngine.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 172 | 5,706 | `97875108fe00e64d…` |
| 151 | [`src/engine/ReplayEngine.ts`](source-companion/view/src/engine/ReplayEngine.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `clean` | 85 | 4,888 | `3edc8b510ef0e3e7…` |
| 152 | [`src/engine/vmgWindVerification.test.ts`](source-companion/view/src/engine/vmgWindVerification.test.ts.html#L1) | Frontend Engine & Catalogs (src/engine/) | `modified (M)` | 316 | 12,371 | `e8ada25518330cce…` |
| 153 | [`src/index.css`](source-companion/view/src/index.css.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 210 | 4,903 | `34a3285430a3ffac…` |
| 154 | [`src/main.tsx`](source-companion/view/src/main.tsx.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 7 | 232 | `e9e644d4f2c138e0…` |
| 155 | [`src/types/analysis.ts`](source-companion/view/src/types/analysis.ts.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 335 | 8,817 | `41a3363ee6b14e4d…` |
| 156 | [`src/types/prediction.ts`](source-companion/view/src/types/prediction.ts.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 113 | 4,749 | `198bb204a556a895…` |
| 157 | [`src/types/replay.ts`](source-companion/view/src/types/replay.ts.html#L1) | Frontend App State, Types & Styles (src/) | `modified (M)` | 205 | 4,504 | `c24446fc886b7cb4…` |
| 158 | [`src/utils/evidenceText.test.ts`](source-companion/view/src/utils/evidenceText.test.ts.html#L1) | Frontend App State, Types & Styles (src/) | `untracked (??)` | 14 | 826 | `b2749a3d9e0ecdf0…` |
| 159 | [`src/utils/evidenceText.ts`](source-companion/view/src/utils/evidenceText.ts.html#L1) | Frontend App State, Types & Styles (src/) | `untracked (??)` | 6 | 436 | `830188ad96a5744d…` |
| 160 | [`src/utils/geoProjection.test.ts`](source-companion/view/src/utils/geoProjection.test.ts.html#L1) | Frontend App State, Types & Styles (src/) | `clean` | 206 | 7,697 | `b261c5e80074f652…` |
| 161 | [`src/utils/geoProjection.ts`](source-companion/view/src/utils/geoProjection.ts.html#L1) | Frontend App State, Types & Styles (src/) | `clean` | 180 | 4,874 | `bfee5979a3df0ac6…` |
| 162 | [`src/utils/geoProjectionStress.test.ts`](source-companion/view/src/utils/geoProjectionStress.test.ts.html#L1) | Frontend App State, Types & Styles (src/) | `clean` | 355 | 14,121 | `329921869c450fe1…` |
| 163 | [`src/vite-env.d.ts`](source-companion/view/src/vite-env.d.ts.html#L1) | Frontend App State, Types & Styles (src/) | `clean` | 1 | 38 | `65996936fbb04291…` |
| 164 | [`tests/__init__.py`](source-companion/view/tests/__init__.py.html#L1) | Verification Suites (tests/) | `clean` | 1 | 25 | `bd6d00be0f24e7a0…` |
| 165 | [`tests/adversarial_sat_stress_harness.py`](source-companion/view/tests/adversarial_sat_stress_harness.py.html#L1) | Verification Suites (tests/) | `clean` | 203 | 8,235 | `45fcb64c4237b762…` |
| 166 | [`tests/browser/annotations.mjs`](source-companion/view/tests/browser/annotations.mjs.html#L1) | Verification Suites (tests/) | `untracked (??)` | 405 | 29,962 | `26685bcff9885b32…` |
| 167 | [`tests/browser/dashboard.mjs`](source-companion/view/tests/browser/dashboard.mjs.html#L1) | Verification Suites (tests/) | `modified (M)` | 423 | 31,602 | `d8f0862ba9288c3b…` |
| 168 | [`tests/browser/feedback.mjs`](source-companion/view/tests/browser/feedback.mjs.html#L1) | Verification Suites (tests/) | `untracked (??)` | 117 | 8,304 | `f7d18def80b3ef27…` |
| 169 | [`tests/browser/forecast.mjs`](source-companion/view/tests/browser/forecast.mjs.html#L1) | Verification Suites (tests/) | `modified (M)` | 449 | 34,164 | `18cf55ef25b9823e…` |
| 170 | [`tests/browser/redesign.mjs`](source-companion/view/tests/browser/redesign.mjs.html#L1) | Verification Suites (tests/) | `untracked (??)` | 105 | 6,686 | `5472a722c5fa8cdb…` |
| 171 | [`tests/e2e/__init__.py`](source-companion/view/tests/e2e/__init__.py.html#L1) | Verification Suites (tests/) | `clean` | 4 | 112 | `62bcaa0edcf1d281…` |
| 172 | [`tests/e2e/e2e_types.py`](source-companion/view/tests/e2e/e2e_types.py.html#L1) | Verification Suites (tests/) | `clean` | 435 | 14,595 | `16277f68bac727ee…` |
| 173 | [`tests/e2e/test_runner.py`](source-companion/view/tests/e2e/test_runner.py.html#L1) | Verification Suites (tests/) | `clean` | 156 | 4,723 | `8fa462252f587496…` |
| 174 | [`tests/e2e/tier1_features_test.py`](source-companion/view/tests/e2e/tier1_features_test.py.html#L1) | Verification Suites (tests/) | `clean` | 782 | 35,238 | `621250cf3f105d25…` |
| 175 | [`tests/e2e/tier2_boundaries_test.py`](source-companion/view/tests/e2e/tier2_boundaries_test.py.html#L1) | Verification Suites (tests/) | `clean` | 301 | 13,126 | `e818e87977c91f51…` |
| 176 | [`tests/e2e/tier3_pairwise_test.py`](source-companion/view/tests/e2e/tier3_pairwise_test.py.html#L1) | Verification Suites (tests/) | `clean` | 275 | 10,990 | `a4f68d29d1ec212d…` |
| 177 | [`tests/e2e/tier4_workloads_test.py`](source-companion/view/tests/e2e/tier4_workloads_test.py.html#L1) | Verification Suites (tests/) | `clean` | 341 | 15,649 | `05f9e7c332aa16b6…` |
| 178 | [`tests/stress/stress_ingest.py`](source-companion/view/tests/stress/stress_ingest.py.html#L1) | Verification Suites (tests/) | `clean` | 413 | 17,605 | `182f526934293919…` |
| 179 | [`tests/tier5_integrity.py`](source-companion/view/tests/tier5_integrity.py.html#L1) | Verification Suites (tests/) | `clean` | 151 | 9,270 | `5236fde88105dd2d…` |
| 180 | [`tests/unit/__init__.py`](source-companion/view/tests/unit/__init__.py.html#L1) | Verification Suites (tests/) | `clean` | 1 | 59 | `6d69971faa7c073e…` |
| 181 | [`tests/unit/test_analytics.py`](source-companion/view/tests/unit/test_analytics.py.html#L1) | Verification Suites (tests/) | `clean` | 186 | 7,158 | `ac16b8e895e507cf…` |
| 182 | [`tests/unit/test_contact_coalescer.py`](source-companion/view/tests/unit/test_contact_coalescer.py.html#L1) | Verification Suites (tests/) | `clean` | 110 | 4,330 | `40bc5e4fc3b9951e…` |
| 183 | [`tests/unit/test_dashboard_contract.py`](source-companion/view/tests/unit/test_dashboard_contract.py.html#L1) | Verification Suites (tests/) | `modified (M)` | 42 | 1,844 | `9de8e764e63ff6fe…` |
| 184 | [`tests/unit/test_dashboard_identity.py`](source-companion/view/tests/unit/test_dashboard_identity.py.html#L1) | Verification Suites (tests/) | `clean` | 20 | 964 | `8f08aa8b7ebef6d3…` |
| 185 | [`tests/unit/test_environment.py`](source-companion/view/tests/unit/test_environment.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 198 | 10,744 | `e3fa72e7f9906454…` |
| 186 | [`tests/unit/test_historical_analysis.py`](source-companion/view/tests/unit/test_historical_analysis.py.html#L1) | Verification Suites (tests/) | `clean` | 466 | 24,621 | `b4eda50a8d0d9f33…` |
| 187 | [`tests/unit/test_ingest.py`](source-companion/view/tests/unit/test_ingest.py.html#L1) | Verification Suites (tests/) | `clean` | 294 | 13,455 | `8d5bee34b16f7087…` |
| 188 | [`tests/unit/test_m2_adversarial.py`](source-companion/view/tests/unit/test_m2_adversarial.py.html#L1) | Verification Suites (tests/) | `clean` | 486 | 20,506 | `478f001aa3122b79…` |
| 189 | [`tests/unit/test_manoeuvres.py`](source-companion/view/tests/unit/test_manoeuvres.py.html#L1) | Verification Suites (tests/) | `clean` | 159 | 5,955 | `8eb60bf42e7217ee…` |
| 190 | [`tests/unit/test_performance_analysis.py`](source-companion/view/tests/unit/test_performance_analysis.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 328 | 19,042 | `17080d760040f356…` |
| 191 | [`tests/unit/test_prediction_atomic.py`](source-companion/view/tests/unit/test_prediction_atomic.py.html#L1) | Verification Suites (tests/) | `clean` | 42 | 2,230 | `729c99e2223e19fe…` |
| 192 | [`tests/unit/test_prediction_cup.py`](source-companion/view/tests/unit/test_prediction_cup.py.html#L1) | Verification Suites (tests/) | `modified (M)` | 314 | 18,996 | `a8c114347430fb13…` |
| 193 | [`tests/unit/test_prediction_evaluation.py`](source-companion/view/tests/unit/test_prediction_evaluation.py.html#L1) | Verification Suites (tests/) | `clean` | 181 | 10,709 | `df63b4742392edd7…` |
| 194 | [`tests/unit/test_prediction_models.py`](source-companion/view/tests/unit/test_prediction_models.py.html#L1) | Verification Suites (tests/) | `modified (M)` | 428 | 25,969 | `b17513c1a7ec6a6b…` |
| 195 | [`tests/unit/test_prediction_pipeline.py`](source-companion/view/tests/unit/test_prediction_pipeline.py.html#L1) | Verification Suites (tests/) | `modified (M)` | 472 | 27,473 | `a801bfded91b641d…` |
| 196 | [`tests/unit/test_prediction_state.py`](source-companion/view/tests/unit/test_prediction_state.py.html#L1) | Verification Suites (tests/) | `clean` | 330 | 17,805 | `451ea890b6729ef2…` |
| 197 | [`tests/unit/test_projection.py`](source-companion/view/tests/unit/test_projection.py.html#L1) | Verification Suites (tests/) | `clean` | 179 | 7,019 | `8a0b6780aef199b4…` |
| 198 | [`tests/unit/test_projection_adversarial.py`](source-companion/view/tests/unit/test_projection_adversarial.py.html#L1) | Verification Suites (tests/) | `clean` | 427 | 16,778 | `44b18e1334d18559…` |
| 199 | [`tests/unit/test_race_previews.py`](source-companion/view/tests/unit/test_race_previews.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 63 | 3,367 | `f9c2140c7763278c…` |
| 200 | [`tests/unit/test_reconstruction.py`](source-companion/view/tests/unit/test_reconstruction.py.html#L1) | Verification Suites (tests/) | `clean` | 206 | 8,781 | `201e4fe8327b5a5d…` |
| 201 | [`tests/unit/test_report_exports.py`](source-companion/view/tests/unit/test_report_exports.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 29 | 2,657 | `ff02ce560f89265d…` |
| 202 | [`tests/unit/test_report_inventory.py`](source-companion/view/tests/unit/test_report_inventory.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 54 | 3,252 | `abd2a47851bcc83f…` |
| 203 | [`tests/unit/test_review_adversarial.py`](source-companion/view/tests/unit/test_review_adversarial.py.html#L1) | Verification Suites (tests/) | `clean` | 165 | 7,596 | `8772aa4d9412d78f…` |
| 204 | [`tests/unit/test_sat_adversarial_stress.py`](source-companion/view/tests/unit/test_sat_adversarial_stress.py.html#L1) | Verification Suites (tests/) | `clean` | 419 | 18,890 | `16dc97ea81bbd08f…` |
| 205 | [`tests/unit/test_tactical_insights.py`](source-companion/view/tests/unit/test_tactical_insights.py.html#L1) | Verification Suites (tests/) | `untracked (??)` | 203 | 11,341 | `82c9836a37473561…` |
| 206 | [`tests/unit/test_vmg_wind_adversarial.py`](source-companion/view/tests/unit/test_vmg_wind_adversarial.py.html#L1) | Verification Suites (tests/) | `modified (M)` | 215 | 9,337 | `ea74d54a066e2591…` |
| 207 | [`tests/verify_boundary_corridor.py`](source-companion/view/tests/verify_boundary_corridor.py.html#L1) | Verification Suites (tests/) | `clean` | 221 | 8,701 | `cf2cf6b952d5de0d…` |
| 208 | [`public/fonts/OFL.txt`](source-companion/view/public/fonts/OFL.txt.html#L1) | Root Configuration & Entry Scripts | `untracked (??)` | 93 | 4,482 | `9af36190332437f5…` |
| 209 | [`public/fonts/README.md`](source-companion/view/public/fonts/README.md.html#L1) | Root Configuration & Entry Scripts | `untracked (??)` | 7 | 344 | `8504f15bb0fec43f…` |
