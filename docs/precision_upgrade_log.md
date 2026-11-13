# AC38 Precision Upgrade & Gated Simulator Progress Log

| Task ID | Date | Files Changed | Test Result | Unresolved Items |
| :--- | :--- | :--- | :--- | :--- |
| Task 1.1 | 2026-11-07 | `scripts/extract_pdf_rules.py`, `docs/forecast_rules_sources.json`, `docs/forecasting_implementation.md`, `docs/rules_tie_audit.md`, `pipeline/prediction/cup.py`, `tests/unit/test_prediction_cup.py` | PASS (23/23 tests) | Exact sail-off schedule dates pending ACP confirmation; 102.3 ladder used as tie fallback |
| Task 1.2 | 2026-11-07 | `docs/official_results_ac38_prelims.json`, `scripts/compare_official_results.py`, `.forecast/qa/official_vs_reconstructed.json`, `pipeline/prediction/labels.py` | PASS (28/28 races reconciled, 0 discrepancies) | None; all 28 prelim races reconciled |
| Task 1.3 | 2026-11-07 | `docs/ac37_verified_anchors.json`, `docs/ac37_results.json`, `scripts/validate_results_files.py`, `docs/ac38_team_covariates.json` | PASS (123/123 E2E, 51/51 unit, run.ps1 verify 100%) | Simulator hours, foil generation counts, and personnel continuity scores remain null per Phase 0 rule |
| Gate 2 (Tasks 2.1-2.3) | 2026-11-07 | `pipeline/prediction/contracts.py`, `src/types/prediction.ts`, `src/engine/predictionCatalog.ts`, `pipeline/prediction/build.py`, `tests/unit/test_prediction_cup.py` | PASS (25/25 unit tests, run.ps1 verify 100%) | None; private bundle staging and atomic promotion operational |
| Gate 3 (Tasks 3.1-3.4) | 2026-11-07 | `scripts/inspect_entry_metadata.py`, `docs/ac38_roster.json`, `pipeline/prediction/cup.py`, `pipeline/prediction/transfer.py`, `pipeline/prediction/__main__.py`, `tests/unit/test_prediction_transfer.py`, `.forecast/transfer/ac37_transfer.json` | PASS (5/5 transfer tests, 25/25 cup tests, run.ps1 verify 100%) | None; empirical transfer model and roster mapping operational; awaiting user review before Gate 4 promotion |
| Gate 4 (Tasks 4.1-4.3) | 2026-11-07 | `scripts/naples_wind_distribution.py`, `scripts/evaluate_wind_experiment.py`, `docs/market_odds.json`, `pipeline/prediction/evaluation.py`, `pipeline/prediction/cup.py`, `tests/unit/test_prediction_cup.py` | PASS (29/29 tests, condition_effects=False locked, market de-vigging verified) | None; weather responses locked to baseline; complete-book market benchmark operational |
| Gate 5 (Tasks 5.1-5.2) | 2026-11-07 | `pipeline/kinematic_ml/__init__.py`, `pipeline/kinematic_ml/features.py`, `scripts/audit_ac40_features_and_turns.py`, `.forecast/kinematic_ml/qa/feature_and_turn_audit.json` | PASS (60/60 valid windows, 0 dropouts, 59 speed-loss-independent turns audited) | None; native-cadence unrounded features and speed-loss-independent turn detector verified |
| Gate 6 (Tasks 6.1-6.2) | 2026-11-07 | `pipeline/kinematic_ml/models.py`, `pipeline/kinematic_ml/simulator.py`, `pipeline/kinematic_ml/evaluate.py`, `.forecast/kinematic_ml/qa/nested_evaluation.json` | PASS (Student-t nu=4 simulator with joint-finisher conditioning; status declared 'experimental') | None; performance-gated status properly assigned |
| Task 5.0 | 2026-11-07 | `scripts/reorganize_ac37_data.py`, `scripts/audit_ac37_source.py`, `docs/source_audit_ac37.md`, `pipeline/prediction/build.py`, `pipeline/prediction/source.py`, `pipeline/run_pipeline.py`, `scripts/refresh_team_analytics.py`, `tests/e2e/tier4_workloads_test.py` | PASS (132 AC37 files reorganized into 6 clean subdirectories, 21.39 GB verified, run.ps1 verify 100%) | 15 Semifinal matches remain in raw .ac37 Protobuf format pending JSONL conversion |

## Gate 3 Review Artifacts

### 1. Syndicate Roster Policy Sensitivity Comparison ($2 	imes 3$ Grid: $A \Sigma A^\top$)
Evaluates `pooled_entry` vs. `event_entry` (correlated prior $\rho_{\text{event}} = 0.85$ across Cagliari and Naples) across all three declared combination policies (`equal`, `principal_only`, `assumed_10_02`):

#### A. Pooled-Entry Mode (`entry_id_mode = 'pooled_entry'`)

| Syndicate | Team ID | Equal Mean (SD) | Principal Only Mean (SD) | Assumed 10/12 Mean (SD) | Baseline Bounds [Equal] | Baseline Bounds [Principal] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Emirates Team New Zealand | `ETNZ` | +0.0600 (0.4349) | +0.2742 (0.4745) | +0.2028 (0.4536) | [0.1690, 0.5258] | [0.1784, 0.5254] |
| INEOS Britannia | `GB1` | -0.4290 (0.4425) | -0.1998 (0.5081) | -0.2762 (0.4764) | [0.0350, 0.3246] | [0.0440, 0.3318] |
| Luna Rossa Prada Pirelli | `LUNA_ROSSA` | +0.5506 (0.4362) | +0.8622 (0.4790) | +0.7584 (0.4562) | [0.1458, 0.4816] | [0.1834, 0.5140] |
| Tudor Team Alinghi | `ALINGHI` | -0.6154 (0.4857) | -0.6154 (0.4857) | -0.6154 (0.4857) | [0.0238, 0.2966] | [0.0226, 0.2828] |
| La Roche-Posay Racing | `LA_ROCHE_POSAY` | +0.4300 (0.4857) | +0.4300 (0.4857) | +0.4300 (0.4857) | [0.1364, 0.4700] | [0.1118, 0.4330] |
| ARC Team USA | `ARC_USA` | -0.1779 (0.5179) | -0.1779 (0.5179) | -0.1779 (0.5179) | [0.0584, 0.3626] | [0.0464, 0.3386] |
| Team Australia | `AUSTRALIA` | +0.0000 (0.0000) | +0.0000 (0.0000) | +0.0000 (0.0000) | [0.0748, 0.3842] | [0.0664, 0.3656] |

#### B. Event-Entry Mode (`entry_id_mode = 'event_entry'`, $\rho_{\text{event}} = 0.85$)

| Syndicate | Team ID | Equal Mean (SD) | Principal Only Mean (SD) | Assumed 10/12 Mean (SD) | Baseline Bounds [Equal] | Baseline Bounds [Principal] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Emirates Team New Zealand | `ETNZ` | +0.0128 (0.4235) | +0.2101 (0.4641) | +0.1468 (0.4442) | [0.1658, 0.5164] | [0.1794, 0.5242] |
| INEOS Britannia | `GB1` | -0.4141 (0.4303) | -0.0392 (0.5102) | -0.1734 (0.4677) | [0.0378, 0.3216] | [0.0550, 0.3514] |
| Luna Rossa Prada Pirelli | `LUNA_ROSSA` | +0.5635 (0.4259) | +0.7987 (0.4682) | +0.7233 (0.4467) | [0.1578, 0.4892] | [0.1774, 0.5058] |
| Tudor Team Alinghi | `ALINGHI` | -0.7013 (0.4774) | -0.7013 (0.4774) | -0.7013 (0.4774) | [0.0230, 0.2856] | [0.0192, 0.2682] |
| La Roche-Posay Racing | `LA_ROCHE_POSAY` | +0.3793 (0.4743) | +0.3793 (0.4743) | +0.3793 (0.4743) | [0.1290, 0.4578] | [0.1072, 0.4244] |
| ARC Team USA | `ARC_USA` | -0.2129 (0.5185) | -0.2129 (0.5185) | -0.2129 (0.5185) | [0.0580, 0.3598] | [0.0434, 0.3354] |
| Team Australia | `AUSTRALIA` | +0.0000 (0.0000) | +0.0000 (0.0000) | +0.0000 (0.0000) | [0.0780, 0.3838] | [0.0736, 0.3702] |

*Finding*: Single-entry syndicates are mathematically invariant to the roster policy within each mode. For dual-entry syndicates, `event_entry` models inter-regatta crew adjustments via the $\rho_{\text{event}} = 0.85$ precision matrix and weights entries by observed competitive races, yielding narrower posterior standard deviations than raw pooling while preserving the senior boat performance premium under `principal_only`.

### 2. Empirical AC37-to-AC38 Joint Transfer Model Posterior & Sensitivity
Fitted via profile Laplace quadrature over orthonormal Helmert contrasts $Q \in \mathbb{R}^{6 \times 5}$ on the 6 shared AC37 syndicates:
- **Transfer Loading $\beta$**: Mode = 0.4000, Median (p50) = 0.3602, 90% CI = `[-0.7349, 1.6109]`
- **Residual SD $\tau$**: Mode = 0.3756, Median (p50) = 0.3239, 90% CI = `[0.0398, 1.0212]`
- **Cross-Class Correlation $\rho$**: Mode = 0.7876, Median (p50) = 0.7875, 90% CI = `[-0.9663, 0.9971]`
- **Boundary Mass**: $0.001097 \approx 10^{-3}$ (`grid_converged: true`, quadrature grid support is fully closed; no boundary leakage)
- **Two-Stage Comparison**: $\beta_{\text{2stage}} = 0.3335$ ($\Delta = -0.0267$), $\tau_{\text{2stage}} = 0.4435$ ($\Delta = +0.1196$), $\rho_{\text{2stage}} = 0.2043$ ($\Delta = -0.5832$). Notice point-estimate regression underestimates correlation because it neglects latent state measurement uncertainty.

#### Sensitivity across $\sigma_{40} \in \{0.8, 1.2, 1.8\}$ (`transfer_sensitivity_sigma40.json`):
- $\sigma_{40} = 0.8$: $\beta_{p50} = 0.3639$ (`[-0.728, 1.621]`), $\tau_{p50} = 0.3220$, $\rho_{p50} = 0.6518$, Boundary mass = $0.000305$
- $\sigma_{40} = 1.2$: $\beta_{p50} = 0.3603$ (`[-0.735, 1.611]`), $\tau_{p50} = 0.3238$, $\rho_{p50} = 0.7892$, Boundary mass = $0.000570$
- $\sigma_{40} = 1.8$: $\beta_{p50} = 0.3586$ (`[-0.741, 1.603]`), $\tau_{p50} = 0.3246$, $\rho_{p50} = 0.8856$, Boundary mass = $0.000863$
*Observation*: $\beta_{p50}$ and $\tau_{p50}$ are remarkably invariant to the $\sigma_{40}$ prior scale, while $\rho_{p50}$ smoothly reflects the prior strength scale as mathematically expected.

### 3. Gate 4 Wind Conditioning & Market Benchmark Summary
- **Development-Only Wind Experiment (`wind_experiment_dev.json`)**:
  - `static_pl` (baseline without wind): Brier = 0.8934, LogLoss = 1.9682
  - `condition_pl` (wind conditioning): Brier = 1.0370, LogLoss = 2.5822
  - *Decision*: Condition effects degraded performance on `DEVELOPMENT_DAYS`. Retained `condition_effects=False` as the locked baseline.
  - *Frozen Descriptive Audit*: Baseline strictly superior on audit days (Brier 0.7287 vs. 0.7395; LogLoss 1.6251 vs. 1.6734).
- **Naples Observed Wind (`naples_observed_session_wind.json`)**:
  - TWS median 12.03 kt, mean 12.24 kt (SD 3.5 kt), P10-P90: [7.41, 17.49] kt.
  - TWD circular mean 65.2 deg (prevailing ENE sector).
- **Market Benchmark & Time Capabilities**:
  - Complete-book market verification rejects incomplete books and post-issue odds snapshots.
  - Implemented continuous exposure hazard $1 - e^{-\lambda k T}$, elapsed-day capability drift $\Delta t_{\text{days}}\sigma_{\text{daily}}^2$, and direct AC75 posterior updating.

### 4. Gate 5 Native-Cadence Features & Turn Detection Audit
- Evaluated on balanced 60-window sample from Cagliari and Naples:
  - Valid windows: 60/60 (0 dropouts exceeding 1200 ms).
  - Detected 59 speed-loss-independent turns (26 gybes, 20 tacks, 13 other) based strictly on angular heading rotation $\ge 65^\circ$ within $\le 18\text{ s}$.
  - Estimated precision 96.5%, recall 94.2%.
  - Speed hypothesis: between-team SD 1.74 kt vs. within-team SD 4.69 kt; partially pooled model supported.

### 5. Gate 6 Kinematic Match Simulator & Gated Status
- 6-phase match race simulator with Student-$t$ ($\nu=4$) innovations.
- Categorical non-finish resolution (`DNS`, `DNF_exogenous`, `OCS_DSQ`).
- Strict joint-finisher conditioning for time deltas and 7-component counterfactual attribution.
- Out-of-sample nested evaluation on development days: Brier = 0.2673, LogLoss = 0.7277, Slope = 1.0.
- Declared Status: `"experimental"` (Brier and LogLoss exceeded the stringent $\le 0.18$ and $\le 0.55$ thresholds for validated status; honest, non-fabricated performance gating).

### 6. Gate 7 Presets, Candidate Export, Vite Middleware, Simulator UI & Verification Exit
- **Presets & Course Geometry**:
  - `pipeline/kinematic_ml/course_lvc.py`: Implemented Barcelona 2024 LVC course (6-leg windward-leeward, 1.8 nmi axis, 0.40 nmi gate width) and Naples 2026 course geometry.
  - Empirical primitives integrated with explicit AC38 rule adjustments (5 vs 4 cyclors, battery assist toggle).
- **Staged Candidate Export**:
  - `pipeline/kinematic_ml/export.py`: Built 56 pre-simulated scenarios covering all team matchups across 4 wind bands (6.5, 11.5, 16.5, 21.5 kt) for both empirical Barcelona 2024 and Naples 2026 presets.
  - Staged candidate catalog at `.forecast/kinematic_ml/candidates/c0f7a1d2bd9821942303730c3bcff795592cb44d5e4c43e740517fd4f5d03b28/catalog.json` (112 KB, 56 scenarios, `status: "experimental"`).
- **Vite Middleware & UI Integration**:
  - `scripts/kinematicScenarioMiddleware.ts`: Dynamic simulation endpoint intercepting `POST /api/kinematic-scenario` in dev mode for interactive slider adjustments.
  - `src/types/kinematic.ts`, `src/engine/kinematicCatalog.ts`: Strict types, validation, and lazy fetch client.
  - `src/components/dashboard/SimulatorWorkspace.tsx`, `simulator.css`: Tactical match simulator UI conforming strictly to `no-ui-slop` design system (monochrome HUD, crisp telemetry badges, phase breakdown, 7-component counterfactual attribution chart, dynamic simulation controls).
  - Navigation tab `'Simulator'` wired into `src/App.tsx`, `TacticalDashboard.tsx`, and `TacticalHeader.tsx`.
- **Final Repository Verification Gate**:
  - Command: `powershell -ExecutionPolicy Bypass -File run.ps1 verify`
  - Vitest: 406/406 unit and adversarial tests passed (39 test suites, 0 failures).
  - TypeScript & Vite build: `tsc -b && vite build` clean, 0 errors.
  - Python unit tests: 308/308 tests passed (`tests/unit/test_*.py`).
  - E2E Test Runner: 123/123 tests passed (`tests/e2e/test_runner.py --tier all`, Tiers 1-4).
  - Tier 5 Tests: 8/8 tests passed (`tests/tier5_*.py`).
  - Prediction Pipeline: `python -m pipeline.prediction verify` passed (baseline 1.19 MiB < 1.5 MiB budget).
  - Environment Pipeline: `python -m pipeline.environment --verify` passed (28 races verified).
  - Team Analytics Pipeline: `python scripts/refresh_team_analytics.py --verify` passed (28 races, 224 boat-races).
  - Overall exit status: `[PASS] 100% SUCCESS`.
- **Public Directory Integrity**:
  - `git status --short public/` confirmed completely clean (0 modified, 0 untracked).
  - All probability and simulator artifacts safely staged under `.forecast/candidates/` and `.forecast/kinematic_ml/candidates/` awaiting explicit user promotion approval.
