# AC37 AC75 Experimental Simulator — Delivery Package & Acceptance Verification

**Document Version**: 1.0.0  
**Delivery Date**: 2026-11-10  
**Candidate Identifier**: `ac75_251f5a5d764e`  
**Status**: Experimental / Gate C Final Acceptance Complete  

---

## 1. Executive Summary & Delivery Overview

This delivery package establishes an authoritative, reproducible, and cryptographically verified experimental AC37 AC75 kinematic simulator built upon real America's Cup 37 telemetry data while preserving real-data ingestion and modeling improvements.

The simulator incorporates causal 5-second steady-state motion fitting, speed-ratio models, speed-independent log-normal maneuver durations, empirical start delays, observed route templates, and contemporaneous paired residual bootstrapping.

### Gate C Verification Results Matrix

| Gate C Requirement | Command / Check | Result | Detail |
|---|---|---|---|
| **Criterion 1: Numerical Invariance** | `.\.venv\Scripts\python.exe -m unittest tests\unit\test_ac75_numerical_invariance.py` | **PASS** | Saved, direct, and service results produce identical canonical numerical content across all fields (diff = 0.0) |
| **Criterion 2: AC75 Unit Tests** | `.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_ac75_*.py"` | **PASS** | 120 tests run, 0 errors, 0 failures (12.77s) |
| **Criterion 3: Kinematic Unit Tests** | `.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -p "test_kinematic*.py"` | **PASS** | 9 tests run, 0 errors, 0 failures (2.74s) |
| **Criterion 4: Frontend Workspace Test** | `npm.cmd test -- src/components/dashboard/SimulatorWorkspace.test.ts` | **PASS** | 10 tests passed (249ms) |
| **Criterion 5: Production Frontend Build** | `npm.cmd run build` | **PASS** | `tsc -b && vite build` succeeded with 0 errors |
| **Criterion 6: AI UI Slop Scan** | `aislop scan --changes --json` | **RECORDED** | Score: 72 ("Needs Work" due to legacy repo scripts); `SimulatorWorkspace.tsx` clean with 0 errors |
| **Criterion 7: Repository Verification** | `powershell -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 verify` | **PASS** | 28 races verified, 224 boat-races, 3,455 snapshots, 54 Vitest files (638 tests) pass, 184 python tests pass, 123 E2E tests pass (100% success) |
| **Criterion 8: Browser Integration Test** | `node tests/browser/simulator.mjs` | **PASS** | All 4 Playwright browser checks passed cleanly (navigation, stale notice, simulation run, competitor reversal) |

---

## 2. Staged Authenticated Candidate Identity & Manifest

The private candidate bundle is staged under `.forecast/ac75_learning/candidates/ac75_251f5a5d764e/` and pointed to atomically by `.forecast/ac75_learning/latest_candidate.json`.

### Candidate Identity & Cryptographic Hashes

- **Candidate ID**: `ac75_251f5a5d764e`
- **Schema Version**: `ac75-model-1`
- **Selected Motion Predictor**: `regularized_spline_polar` (selected under 1-SE rule over 13 eligible dates)
- **Manifest Path**: `.forecast/ac75_learning/candidates/ac75_251f5a5d764e/candidate_manifest.json`
- **Manifest SHA-256**: `b485b4509ca8076ca08067b5e5bdf52b175624732eda0aacc0e14b98e473ca49`
- **Config SHA-256**: `666df1c75bfecc8e81e80292d83a636baa9f7e62bf71e4e8bd5e3bf2b2d0c6cd`
- **Sealed Dataset Manifest SHA-256**: `fc4bd7405d872a588b784d7689ee838da5636694ab6d7137594b0ef2cc42173c`
- **Evaluation Report SHA-256**: `99fab6cdc43a59da4f190b6ec52cfd7ff76806fc8341af8f675915ab9989358e`

### Mandatory Artifact Inventory & Content Hashes

| Artifact Key | File Path | SHA-256 Digest |
|---|---|---|
| `weights_pt` | `model_weights.pt` | `502e7689839669815d95022143664f41a4e72da6ac8ea6ff5bcf9c123081fb2e` |
| `weights_npz` | `model_weights.npz` | `4791a10d36abd43e744e1394d44a59f2c83b2a646adbf529f442ea1a9df5d842` |
| `model_json` | `model_weights.json` | `e0c7cb4e191587d119e25a052755a6ec0fb98c1716c1cc98979b2305028dfc40` |
| `empirical_polar_json` | `empirical_polar.json` | `07d8779aea7fee1f04e09429370c7392f971dc1f94ea7058a57a42e742e3c982` |
| `spline_polar_json` | `spline_polar.json` | `77ba4e96d93eab9751b7b068355a93bd0c201c44fb41b48ceed8aebff1d574a8` |
| `maneuver_model_json` | `maneuver_model.json` | `c20560790df5fb9ccb8c604aa0f40c8285160166aad853efb8081c37978aa67b` |
| `start_model_json` | `start_model.json` | `cb00e83217a16b25dbdddf584de09b0d46a6060f92ffa47bad3ebe7498766e81` |
| `route_templates_json` | `route_templates.json` | `f330efb3e4108bd87fb1e60a1413ec67323d53587e872b34c161c8b38817708e` |
| `residual_blocks_npz` | `residual_blocks.npz` | `ae90270b52a49fc4c1d723a44bd4e8edbde55ea4c3a5f64291b01d3007ee624e` |
| `scenarios_catalog` | `scenarios_catalog.json` | `1ae1f4f02eb8614f8481d8f0b1c31556f0cb7f64f08ae7c8addc90d1e405c94a` |

### Code Hashes of Owning Numerical Modules

The candidate ID is cryptographically derived from the owning code hashes, excluding absolute paths and timestamps:
- `baselines.py`: `6ddb0027daff63bd4d33dc055ba0e7de0b43126c9ee0e08317d695fcf07bf132`
- `contracts.py`: `176c99d6c860898b315611fdb52287642fe6a34fd521e7d6c5de6985891b6f5f`
- `course_lvc.py`: `d03b0a229579caa8b78d3b8e7b2345524fc6ce0d3f603259e46c8ea58116da26`
- `events.py`: `1fe0f0d6bd2667cced562d4f98f000fcdd9eb0baa29dde7009d2842455deda8f`
- `inference.py`: `6fe1073c6a7521d6f3918aa73a593e8dd301b87f5878a2fd916626308ad05617`
- `neural.py`: `71b914add8687de6007e6a414ce83dae1142f1a707149a737571b3d054ff5f34`
- `routes.py`: `0b2b2df8ebd818f1c08ff6dcd61d4df7bba58780bfbe3df6b1f82e021c469c4d`
- `uncertainty.py`: `5f47126fc2edae731aade35bb46c888c2d8f069d183d53c600f58cf4ef326d2e`

---

## 3. Population, Evidence, and Exposure Report

### Separation of Qualified vs Exploratory Evidence
- **Qualified Evaluation Evidence**:
  - Requires supported timed finishes for both competitors in the same valid attempt.
  - Winner status tied directly to on-water finishing margin.
  - Pre-race inputs evaluated strictly at the race gun timestamp under registered latency; whole-race averages and invented weather are rejected.
  - 13 common eligible racing dates met qualification standards for cross-validation evaluation.
- **Exploratory Elements**:
  - Rule sliders (e.g. AC38 rule adjustments) and uncalibrated custom wind scenarios remain strictly segregated under separate model modes (`barcelona_2024_empirical_with_ac38_rules`).
  - Pre-cached catalog scenarios are marked with status `experimental` and status notice callouts.

### Isolation of Repaired Candidate vs Prior Candidate Contamination
Prior candidates suffered from unauthenticated date-based filtering and potential holdout leakage from the September 28 stopped-attempt race (`ac37_lvc_final_r3_att1_stopped`).

The repaired candidate `ac75_251f5a5d764e` implements centralized family-based isolation through `SplitRef`, `TrainingView`, and `EvidencePolicy`:
- **Sealed Steady Windows**: 16,128 total 5-second windows.
- **Reserved Holdout Windows Excluded**: 2,578 windows (covering Louis Vuitton Cup Final races `ac37_lvc_final_r3` through `ac37_lvc_final_r11`).
- **September 28 Stopped-Attempt Windows Excluded**: Exactly 539 windows excluded via link to canonical family `ac37_lvc_final_r3`.
- **Pure Development Windows**: Exactly 13,550 steady windows across 18 development racing days.

### Zero Reserved-Family Leakage Across All Components

Verified in `.forecast/ac75_learning/experiments/population_overlap_verification.json`:
1. **Steady Windows Motion Fitting**: 13,550 development windows, 0 reserved families.
2. **Inner Validation Split**: 12,390 train / 1,160 validation windows, 0 reserved families.
3. **Maneuver Duration Model**: 3,100 development maneuvers (683 right-censored), 0 reserved families.
4. **Start Behavior Model**: 90 development starts, 0 reserved families.
5. **Route Template Library**: 692 development templates, 0 reserved families.
6. **Paired Residuals Sampler**: 454 contemporaneous 30s paired blocks, 0 reserved families.

The exposed final block (`ac37_lvc_final_r3` through `ac37_lvc_final_r11`) remains strictly excluded from fitting and constitutes an isolated diagnostic benchmark.

---

## 4. Evaluation Scores and Model Selection

### Metric Methodology
- Internal simulation trials are evaluated directly to compute empirical margin Continuous Ranked Probability Score (CRPS) without Gaussian approximation.
- Evaluation runs across 12 expanding chronological folds, avoiding future lookahead.
- Model selection uses date-level race-margin CRPS, averaging races within each date and computing paired differences to the best model with standard error:
  $$\text{SE}_{\text{diff}} = \frac{\text{std}_{\text{ddof}=1}(\Delta)}{\sqrt{N_{\text{dates}}}}$$
- The 1-SE rule selects the simplest model whose mean difference is within its own standard error limit (hierarchy: `empirical` $\to$ `spline` $\to$ `neural`).

### Benchmark Results (13 Eligible Dates)

| Model Candidate | Complexity | Mean Date CRPS | Paired Diff to Best | Paired SE | Selection Status |
|---|---|---|---|---|---|
| `empirical_binned_polar` | 1 (Simplest) | 128.2179s | +34.1996s | 20.9490s | Rejected (Diff > 1 SE) |
| **`regularized_spline_polar`** | **2 (Intermediate)** | **96.3904s** | **+2.3721s** | **10.7311s** | **SELECTED (Diff $\le$ 1 SE)** |
| `neural_network_silu` (2x32) | 3 (Complex) | 94.0183s | 0.0000s | 0.0000s | Reference Best |

Because Spline's mean difference to Best (+2.3721s) is well within its own paired SE (10.7311s), the 1-SE parsimony rule selected `regularized_spline_polar` as the default motion predictor.

---

## 5. Serving Architecture & Numerical Invariance

### Canonical Normalization & Service Limits
- **Request Normalization**:
  - Competitors mapped to canonical AC37 IDs (e.g. `ac37:ETNZ`, `ac37:INEOS`).
  - True Wind Speed converted to SI units ($m/s$).
  - True Wind Direction normalized to $[0, 360)^\circ$.
  - Authoritative 64-character SHA-256 scenario hash computed.
- **Service Limits Enforced**:
  - Concurrency: At most 1 running simulation process (`MAX_CONCURRENT_INFERENCE = 1`).
  - Queue depth: At most 4 waiting requests (`MAX_QUEUED_REQUESTS = 4`); overflows reject with `QueueFullError`.
  - Payload cap: 2 KiB (`MAX_PAYLOAD_BYTES = 2048`); oversized payloads reject with `PayloadTooLargeError`.
  - Supported wind speed envelope: $[6.0, 24.0]$ kt.
  - Browser trial counts: Preview = 2,000 / Standard = 10,000.
  - Security: Loopback host verification (`localhost`, `127.0.0.1`, `[::1]`) and strict Same-Origin enforcement.

### Numerical Invariance Verification
Verified across all 30 pre-cached scenarios in `tests/unit/test_ac75_numerical_invariance.py`:
- `saved`: Scenario loaded from `scenarios_catalog.json`.
- `direct`: Output of `predict_scenario(bundle, req)` executed directly on reloaded candidate bundle.
- `service`: Output of `service.simulate(req)` processed through exact catalog matching.

All three sources produce mathematically identical floating-point values for win probabilities, delta T, margin intervals, and variance attributions (maximum absolute difference = 0.0).

---

## 6. Resumable Repair Commands & Reproduction Receipts Guide

The repair pipeline is fully orchestratable via thin CLI commands that dispatch to owning numerical modules and record cryptographic receipts:

```bash
# 1. Prepare: Verify frozen family registry and sealed dataset merkle root
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml repair --phase prepare

# 2. Evaluate: Run expanding chronological cross-validation and 1-SE model selection
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml repair --phase evaluate

# 3. Train: Fit models on authenticated development view and export candidate bundle
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml repair --phase train

# 4. Verify: Verify all experiment ledger receipts and artifact merkle roots
.\.venv\Scripts\python.exe -m pipeline.kinematic_ml repair --phase verify
```

### Reproduction Receipts Ledger
Recorded in `.forecast/ac75_learning/experiments/repair_experiment_v1_receipts.json`:
- `prepare`: Merkle root `48c293e43146c65d6ec4b627312d7bf3dfaf0c44a98745d4f76cdf0b6368d09b`, 506 files verified, exit code 0.
- `evaluate`: 12 folds evaluated, `regularized_spline_polar` selected (+2.3721s vs 10.7311s SE), exit code 0.
- `train`: Candidate `ac75_251f5a5d764e` created with 692 route templates, 454 paired residual blocks, exit code 0.
- `verify`: 506 files verified, 0 mismatches, exit code 0.

---

## 7. Independent-Validation Protocol for Future Unreleased Regatta Data

To independently evaluate candidate `ac75_251f5a5d764e` against newly released AC37 Match Finals or AC38 regatta telemetry without data leakage or contamination:

1. **Raw Ingestion & Chronological Split**:
   - Ingest raw unreleased JSON telemetry through `pipeline.ingest`.
   - Compute content hash of newly added attempt files.
   - Register new family ID in `frozen_evaluation_families.json` with role `unreleased_test`.
2. **Evidence Qualification**:
   - Filter using `EvidenceQualifier`:
     - Discard uncompleted attempts or single-finisher races without supported physical targets.
     - Sample wind speed and direction at the exact race gun timestamp (latency $\le 30s$).
     - Reject cases where pre-race environmental context is missing or synthesized.
3. **Out-of-Sample Trial Evaluation**:
   - Load installed bundle `ac75_251f5a5d764e` using `load_staged_ac75_bundle()`.
   - For each qualified race, execute simulation trials under pinned seed (2027) and standard trial count (10,000):
     ```python
     result = predict_scenario(bundle, req, return_trials=True)
     ```
4. **Scoring & Verification**:
   - Compute empirical margin CRPS against actual physical on-water delta T:
     $$\text{CRPS}(F, y) = \frac{1}{M}\sum_{m=1}^M |x_m - y| - \frac{1}{2M^2}\sum_{m=1}^M\sum_{k=1}^M |x_m - x_k|$$
   - Compute winner Brier score and log-loss against official match results.
   - Confirm 50%, 80%, and 95% empirical interval coverage rates.
5. **Integrity Invalidation Criteria**:
   - Any modification to `model_weights.*`, `spline_polar.json`, `route_templates.json`, or `residual_blocks.npz` invalidates candidate `ac75_251f5a5d764e`.
   - Re-fitting on unreleased data without creating a new content-addressed candidate ID violates the single-lineage integrity contract.
