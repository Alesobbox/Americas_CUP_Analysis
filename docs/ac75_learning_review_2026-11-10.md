# AC75 learning pipeline review — 2026-11-10

Scope: current pipeline/kinematic_ml/, its AC75 tests and artifacts, and simulator service/UI integration. This was a review, not an implementation repair. Source files were not changed by this review; the production frontend build regenerated ignored dist output.

## Verdict

There is substantial, useful engineering progress since the previous review. Real native AC75 data has been normalized, several foundation defects were corrected, and an actual small neural-network implementation exists.

The staged candidate is nevertheless a synthetic demonstration, not a model trained on the AC37 archive. Its metadata incorrectly claims authentic telemetry training and chronological validation. The race simulator, evaluator, service, and frontend do not yet implement the agreed end-to-end design. Do not accept the all-complete progress flags as evidence.

## Independently checked

| Check | Current result |
|---|---|
| AC75 focused Python suite | 63 tests passed |
| Legacy kinematic Python suite | 9 tests passed |
| Simulator workspace frontend tests | 6 tests passed |
| Production frontend build | Passed; bundle-size advisory remains |
| Public-data preservation | 506 files match recorded root; zero mismatches |
| Scoped quality scan | 83/100; zero errors, 23 warnings, zero automatically fixable findings |
| Native partitions | All 100 manifest-listed Parquet partitions exist |
| Native row counts | Parquet footers sum to 75,982,066 rows, matching manifest |
| Catalog integration probe | HTTP 200 array returned; workspace's scenarios.find access fails |

Tests prove the behavior they exercise. They do not prove that the installed model used real telemetry or that real race forecasts were evaluated. Some tests explicitly accept the synthetic/fixed-assumption paths identified below.

## What is genuinely better

1. Real JSONL competitor lists now resolve through session assets into canonical AC37 identities. The 100 JSONL attempts have canonical teams; the 15 remaining unknown-team attempts are unsupported binary sources.
2. Strict UTF-8 rejection and actual byte offsets replaced silent byte replacement. A bounded corruption probe now retained the correct next offset.
3. Cross-batch sorting now uses a global merge; the prior globally-disordered output bug is fixed.
4. Native normalization was actually executed. This is no longer just source code marked as a generated dataset.
5. The attempt/outcome join improved: 73 of 82 outcome rows link to attempt families; nine Match outcomes correctly lack telemetry. The saved ledger currently marks zero winners independently verified.
6. The final reservation now contains five dates and nine families, with the stopped/resailed family represented.
7. Explicit motion/event predictor allowlists now exist.
8. There is a real 2x32 SiLU Torch network, optimizer/early-stopping code, numeric NPZ export and a NumPy forward pass.
9. Completion-assumed scope is represented separately from unsupported unconditional completion probabilities in parts of the code.
10. Maintainability improved enough for the scoped quality scan to pass its current threshold. Numerical correctness and predictive evidence still require separate review.

## Blocking findings

### R1 [P1] The installed model is trained on synthetic observations

Owner: pipeline/kinematic_ml/export_ac75.py:67–95; misleading description at :182–184.

The exporter loads a native manifest but does not use its rows for training. It constructs 1,000 random observations with SOG = 12 + 1.1 * TWS + Gaussian noise. All angles/domain features are fixed, with team IDs assigned cyclically.

It also fabricates route templates (:104–123), constructs an unfitted maneuver model and fixed start model (:126–128), and creates an empty empirical residual library. The saved candidate then claims fitting on authentic 2024 telemetry and isolated chronological folds.

Required improvement:

- Keep synthetic fixtures exclusively in tests or explicitly named demonstration commands.
- Train through a sealed real feature dataset and frozen experiment registration.
- Make export consume already trained, authenticated artifacts; export must not secretly train a substitute fixture.
- Bind model metadata to actual dataset/split/configuration IDs and derive descriptions from executed evidence.
- Reclassify or replace the current candidate and inaccurate completion records.

Acceptance: removing/changing real training inputs affects the training identity and fitted result; absent real training evidence prevents an authentic-trained candidate from being exported.

### R2 [P1] The learned catalog is incompatible with the workspace

Owners: scripts/kinematicScenarioMiddleware.ts:92; src/components/dashboard/SimulatorWorkspace.tsx:39.

The learned catalog is a JSON array. The middleware returns that array directly. The workspace calls cat.scenarios.find and still expects the legacy schema.

An in-memory call to the actual catalog middleware returned status 200, catalogIsArray=true, and no scenarios field. Executing the workspace's default-selection access produced: Cannot read properties of undefined (reading 'find').

Required improvement: define and validate one catalog envelope, update the client and workspace to the actual v2 discriminated result, and test the actual exported catalog through the middleware/client rather than only invented fixtures.

Acceptance: the real installed candidate opens successfully; malformed/legacy/unavailable catalogs render explicit states rather than crashing.

### R3 [P1] Evaluation does not measure the agreed race forecast

Owner: pipeline/kinematic_ml/evaluate_ac75.py:105–124, :148–174, :179–243.

The evaluator scores SOG, not simulated race margins or race-win outcomes. Baseline CRPS uses fixed speed standard deviations of 1.8/1.6 m/s. NN log-speed scale is passed to a speed-space Gaussian score, mixing distributions and units.

Inner validation is a row-level 80/20 slice, ignoring the split manager's chronological inner groups. Scaling is fit before that slice. Selection uses a fixed 0.05 “standard error” when date evidence is missing; a probe selected the neural candidate with zero scored dates.

No completed real experiment registration, comparison predictions, consumed-holdout ledger, or evaluation report is present in the planned artifact root. The progress record's evaluation_complete flag is unsupported.

Required improvement: connect real windows to family IDs, enforce chronological inner training/calibration, evaluate matched physical and race targets, implement the registered CRPS and day-level selection rule, and save unrounded predictions/evidence.

Acceptance: actual held-out race predictions are scored; fewer than five scored development dates trigger the registered fallback; future-target changes cannot affect fitted artifacts.

### R4 [P1] Inference still replaces learned behavior with fixed assumptions

Owner: pipeline/kinematic_ml/inference.py:132–222.

The learned entry point:

- Hardcodes four 1,500 m legs and ignores course_id.
- Creates synthetic default routes when support is absent.
- Samples routes once before the trial loop.
- Does not query the fitted maneuver model.
- Ignores the neural predictive scale.
- Applies fixed 4% speed noise and fixed cross-boat correlation.
- Indexes a time-series residual sequence across Monte Carlo trials rather than along each simulated race's calendar time.
- Floors predicted speed at 2 m/s.

A deterministic probe changed course_id entirely while preserving exactly the same 600-second result.

Required improvement: resolve real installed geometry/policy/events/scales before simulation; sample supported trial-level behavior; apply residuals on the common within-race clock; abstain when required support is absent.

Acceptance: changing actual course length changes elapsed time; changing fitted event/scale parameters changes the appropriate outputs; missing routes/residual support cannot silently become a plausible numeric scenario.

### R5 [P1] Route compass rotation is reversed

Owner: pipeline/kinematic_ml/routes.py:188–204.

The coordinate rotation uses the opposite sign for the compass convention. A northbound segment requested at 90 degrees is transformed westward, with COG 270 degrees, instead of eastward.

Required improvement: reconcile the coordinate and bearing conventions and recompute COG/heading/TWA from transformed geometry.

Acceptance: cardinal-direction fixtures for 0/90/180/270 degrees, arbitrary rotation, inverse transformation, gate placement and boundary containment.

### R6 [P1] Uncertainty metadata describes evidence that does not exist

Owner: pipeline/kinematic_ml/uncertainty.py:61–88; inference.py:204–222.

When paired empirical blocks are absent, the sampler generates an AR(1) process with fixed rho 0.85 and assumed correlation. The exported candidate has no empirical blocks, so it uses that path.

The variance ledger nevertheless describes empirical paired residuals, calibration across three seeds and out-of-fold spread. The exported fit uses seed 2027 only.

Required improvement: eliminate hidden statistical fallback assumptions. Fit and persist chronological residual blocks/calibration or return an explicitly assumed sensitivity/unsupported result. Generate the ledger from actual installed components.

Acceptance: no residual artifact means no claim of empirically learned dependence; one-seed training cannot report three-seed calibration.

### R7 [P1] Maneuver labels still leak future information; censoring is ignored in fitting

Owners: pipeline/kinematic_ml/maneuvers.py:75–79, :152–156; events.py:48–89.

If no earlier wind exists, the turn detector reads the first future wind sample. Changing only wind at 30 seconds changed the classification of a turn during 0–8 seconds.

Missing pre-turn speed falls back to the first later speed. A probe inferred entry speed from post-turn observations and declared immediate recovery.

Event fitting reads the censoring flag but never uses it. Switching all event labels from uncensored to censored leaves the fitted prediction unchanged. Wind/rotation/speed coefficients and residual scale remain fixed.

Recovery also differs from the registered reference/95%/two-second-hold/30-second contract.

Required improvement: use supported past-only onset inputs, preserve missingness, apply the agreed recovery/transition definitions, and fit a real censored-duration likelihood.

Acceptance: future-only mutations cannot change prior features; missing entry data stays unavailable; censoring changes the likelihood and fitted uncertainty appropriately.

### R8 [P1] Cache reuse can silently retain stale training data

Owner: pipeline/kinematic_ml/dataset.py:253–269.

Cache reuse checks only source byte count. A temporary-fixture probe changed a heading from 10 to 90 without changing file length, updated the inventory source hash, and rebuilt; the output still contained the old heading 10.

The reuse path also trusts claimed Parquet hashes without authenticating actual bytes or parser/configuration versions.

Required improvement: bind caches to actual source content, parser/schema/unit/configuration hashes, and validate derived output bytes before reuse.

Acceptance: same-size source edits, parser changes and corrupted Parquet invalidate or fail the cache.

### R9 [P1] Native causal and revision provenance remains incomplete

Owners: pipeline/kinematic_ml/dataset.py:36; source.py:219.

The native schema retains 15 telemetry fields but omits availability time/basis, sequence/correlation IDs, source hash and metadata revision/event records. Session, competitor and target events are not persisted by this writer.

Causal joins over telemetry alone cannot reconstruct when a revised gun, course, identity or state was knowable.

Required improvement: persist native event/revision evidence and its availability alongside telemetry; join it as of issue time.

Acceptance: later metadata corrections cannot alter an earlier feature snapshot; required provenance survives normalization and sealing.

## Additional important improvements

### R10 [P2] Global sorting is correct but not bounded-memory

The merge initializes an iterator for every chunk; each iterator materializes a full Parquet batch as a Python dictionary. Memory therefore scales with chunk count.

With batch size 500, a probe grew from 3.34 MB at 10,000 rows to 15.62 MB at 50,000 rows.

Use bounded-fan-in merge passes and small per-input buffers. Add a scaling test that verifies the claimed memory bound.

### R11 [P2] Outcome verification still needs field-level isolation

Current saved winners are honestly unverified. However, labels.py:289 can use a winner-only anchor to mark fallback candidate margin/wind/default completion status verified.

Verify each field independently. A winner-only source cannot authenticate wind, elapsed margin or completion cause.

### R12 [P2] Probability and numerical-error semantics are wrong

inference.py:231–264 assigns ties to no_winner. Identical deterministic finishers produce P(A)=0, P(B)=0, no_winner=1 even though both finish.

It computes the standard error of the margin in seconds and stores it inside probabilities as mc_error.

Handle ties under the registered convention; keep no-finisher probability distinct. Compute probability numerical error from win indicators and retain units on timing numerical error.

### R13 [P2] Models, scenario IDs and caches are not immutable

The candidate ID is constant ac75_learned_v1 and files are overwritten in place. Scenario IDs omit wind/course/model content; 15 saved scenarios have only five unique IDs.

Interactive loading does not authenticate recorded manifest/weight hashes.

Use content-derived identities, complete normalized keys, verified references and atomic pointer-only promotion.

### R14 [P1/P2] Saved and interactive paths/service/UI remain disconnected

The middleware still uses spawnSync, unbounded request bodies, legacy partial cache matching and a separate reconstructed model path. The new worker/job/Origin/peer protection is absent.

The UI retains legacy result fields, draft-control labels, interval naming and attribution semantics.

Implement the specified asynchronous pinned-model service and one v2 client contract. Add real saved/direct/service parity, stale-response and request-validation tests.

### R15 [P2] Completion status and documentation overstate execution

The CLI still exposes only environment verification, preservation verification, inventory and progress. The planned dataset/labels/train/evaluate/export/simulate workflow is not connected.

Many tasks marked artifact_complete list Python/test source files rather than generated training/evaluation objects. T15/T19/T20 have no check receipts; one artifact is only the text “run.ps1 verify passed 100%.”

Restore task statuses based on verified deliverables. Code existence, generated data, executed training, completed evaluation and passing application checks are separate facts.

The audit document also retains fixed category byte totals and inconsistent GB/GiB labeling rather than fully deriving its report from the manifest.

## Recommended repair order

1. Reclassify the current candidate as synthetic/demo and correct its metadata/progress claims. Keep it out of authentic AC75 comparisons.
2. Finish sealed data/metadata provenance, cache validation and family-ID adapters. Preserve the successful real normalization and identity work.
3. Build real steady/event/route artifacts from authorized training groups and freeze experiment registration.
4. Repair future-data/censoring/domain handling and fit the empirical/spline/NN pipelines on the same eligible populations and race weights.
5. Fit supported uncertainty and real event/start components. Fix rotation, requested geometry and probability units.
6. Run actual chronological component and full-race evaluation; preserve predictions and expose coverage, holdout history and limitations.
7. Export immutable selected artifacts through one loader/inference path.
8. Connect and test the real v2 catalog/UI and bounded asynchronous service. Repeat focused and repository-wide checks after those changes.

Do not start by expanding the network, adding a Transformer, or tuning more synthetic examples. The highest-return work is connecting the real archive to honest fitted models, evaluated race predictions and the actual application.

