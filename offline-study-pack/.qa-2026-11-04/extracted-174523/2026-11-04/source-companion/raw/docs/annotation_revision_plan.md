# Annotation-led revision plan

Prepared 2 November 2026. This is an implementation plan, based on the six browser annotations, current source, published exports, and three independent read-only agent audits. No application changes were made during this planning pass.

Execution completed 3 November 2026. All six annotation acceptance checks and the release gate passed; see [final verification](annotation_revision_verification.md). Findings and numbers below retain the pre-change planning snapshot. The explicitly deferred metric/AC75/rule research remains outside this implementation release.

## Intended result

A white, readable Analysis workspace; a clean replay with four useful boat KPIs; an interactive, evidence-driven circular performance chart; Reports built from the same canonical metrics as Analysis; and a Cup forecast that separates assumptions, unresolved tournament paths and numerical simulation error. Preserve the five navigation views, course layout, team identity, replay compatibility and complete data provenance.

The user's white-surface request supersedes the dark Analysis palette in docs/design-system.md. The request to remove permanent Heel and Current placeholders supersedes the earlier rule requiring those placeholders in the main replay UI. Keep the source-channel explanation in technical evidence, without retaining useless operational cards.

## 1. Findings mapped to all six annotations

| Annotation | Current finding | Planned response |
| --- | --- | --- |
| 1. Artifact library | 437 downloads exist. The current-race filter includes 325 global objects, so Naples displays 329 rows, including 293 retained forecast artifacts. | Retain the reproducibility archive, but make race reports and useful exports the primary workflow. Put technical and retained versions in a collapsed, searchable explorer. |
| 2. Blue Analysis page | Analysis inherits dark global `--bg-*` and pale `--text-*` variables; the light dashboard uses separate `--tac-*` variables. | Apply a complete scoped light palette across Analysis, including charts, controls, text, tables and disclosures. |
| 3. More precise graph | All 1,038 available indexes recompute correctly. The graph is static, does not expose per-leg evidence and compresses small differences near 100. | Add genuine axis/leg interactions, explicit support and scope, exact evidence, a focused detail view, and honest scaling. Separate usability improvements from new metric research. |
| 4. Remove Heel | A permanent unavailable Heel card is hardcoded into the boat banner. | Remove the card and rebalance the four measured KPI channels. |
| 5. Remove unavailable Current | Current and a divider are hardcoded into the wind HUD. | Remove both, leaving a compact wind HUD. Keep real missing-sample handling for supported channels. |
| 6. Probability ranges | The displayed envelope already combines unresolved-rule bounds with nine transfer assumptions. It is not a confidence interval. | Explain and separate those layers, publish their evidence, fix missing-team provenance and improve the actual model only when supported. |

### Two data issues the implementation must address

Reports currently uses legacy replay summary values, whereas Analysis uses source-covered historical metrics. For retired Naples GBR B, Reports shows 936.9 m and 0.9 kt while the canonical racing metrics are unavailable. For match-final ITA B, Reports shows 19,069.3 m while Analysis has 12,769.8969 m with partial coverage over 847.085 seconds. Reports must consume the canonical analysis values and their definitions; preserving the replay JSON does not require showing its legacy summaries as equivalent metrics.

Thirteen of the 173 profiles with six available dimensions do not cover all course legs. In the match final, missing leg-5 crossing evidence prevents a complete leg-6 interval; the radar compares common legs 1-4 of a six-leg course. The interface must make this scope visible. Missing crossings may be repaired only when source evidence supports a reconstruction correction.

## 2. Team and file ownership

Use three workers plus the orchestrator. Each worker implements and tests its own workstream; the orchestrator owns product integration and final verification. Do not give two agents the same shared stylesheet or component.

| Owner | Responsibility | Primary owned files |
| --- | --- | --- |
| Agent A: visual consistency and replay clarity | White Analysis theme; remove Heel/Current; responsive and contrast checks | New scoped Analysis stylesheet; BoatPerformanceCard.tsx; TacticalMapOverlay.tsx; their standard/adversarial tests |
| Agent B: performance analytics and interaction | Metric scope/evidence contract; interactive radar; independent arithmetic checks | pipeline/historical_analysis.py; src/types/analysis.ts; src/engine/analysisCatalog.ts; BoatPerformanceRadar.tsx; AnalysisModal.tsx; a new scoped radar stylesheet; performance/component tests; refresh helper if needed |
| Agent C: forecast evidence and correctness | Cup uncertainty decomposition, mapping/lineage corrections, scenario inspection | pipeline/prediction/cup.py, build.py, contracts.py; src/types/prediction.ts; predictionCatalog.ts; ForecastWorkspace.tsx; scoped forecast styles; Cup/forecast tests |
| Orchestrator | Canonical Reports, artifact classification, shared imports, integration, documentation, publishing and regression gate | ReportsWorkspace.tsx; scripts/build_artifact_inventory.py; TacticalDashboard.tsx; shared stylesheet imports; browser harnesses; repository docs; public artifact publication |

New scoped stylesheets avoid concurrent edits to workspaces.css. Agents send requested shared changes to the orchestrator. Agent B owns AnalysisModal integration; Agent A supplies a stylesheet and selectors rather than editing that component. Only the orchestrator publishes public/data and its indexes/inventory; workers produce isolated candidates.

## 3. Execution sequence and dependencies

### Stage 0: freeze contracts and capture the baseline

The orchestrator records existing uncommitted changes and hashes, without resetting anyone's work. Capture the six annotated states at 1096x704 and the existing desktop/mobile widths. Record current metric definitions, inventory classifications, Cup artifact references and field availability.

Freeze the response to each annotation, schema additions, labels and file ownership before implementation. Preserve Python ownership of every numerical score, ratio, aggregate, eligibility rule and availability decision. TypeScript may select and draw an exported observation; it may not silently recompute a new metric.

Deliverable: contract checklist with selected boat/race/leg behavior, white surfaces, report metric sources, download categories and Cup uncertainty labels. Exit condition: every worker has a concrete input/output contract and non-overlapping files.

### Stage 1: parallel work

Agents A, B and C work concurrently. The orchestrator implements Reports and the inventory contract. Fast cosmetic work does not wait for model research; forecast presentation does wait for its evidence contract. Keep source reads bounded, reuse docs/source_audit.md, and avoid full raw re-ingestion for UI-only changes.

### Stage 2: integrate candidate data and components

Agent B's schema/evidence additions precede radar integration. Agent C's published per-scenario records precede the new Cup inspection UI. Reports' canonical data binding and inventory metadata precede the new default download filter. The scoped light theme must be present before final chart/forecast visual review.

Publish immutable forecast objects and model/source references before switching the active index. Retain older immutable objects. Refresh the inventory after every published output family is complete. Build a fresh production preview and compare its data hashes with public/data.

### Stage 3: independent review and final gate

Cross-review numerical and interaction changes, then run focused tests, run.ps1 verify, the dashboard browser suite and tests/browser/forecast.mjs --real. The current verification script does not replace the dedicated forecast browser checks. Close all six annotation acceptance checks before delivery.

## 4. Agent A: white surfaces and useful replay indicators

Implement a light token bridge scoped to `.tactical-dashboard-root .analysis-modal`, including panel/card/input/hover/active surfaces, primary/secondary/muted text, borders, plot grid and selected states. Set color-scheme:light. Handle legacy --text-white references inside this scope so pale text does not remain on white. Preserve team colours while ensuring plotted marks, labels and selection outlines remain distinguishable. Do not invert the whole application or alter map imagery.

Check Race Report and Historical View: header, tabs, selectors, classification, scalar cards, history charts, wind plots, radar, debrief, definitions, errors and loading states. Update design-system.md so future components do not reintroduce the dark palette.

Remove Heel from BoatPerformanceCard and Current plus its divider from TacticalMapOverlay. Keep SOG, course-axis replay VMG, TWA and TWS, along with their genuine missing-sample reasons. Remove unused spacing/columns and obsolete assertions requiring permanent unavailable cards. Do not remove supported data guards or change the replay schema.

Acceptance: white Analysis surfaces and readable dark text throughout; exactly four boat KPI channels; no Heel/Current placeholder or empty divider; unchanged navigation, map geometry, playback and selection behavior.

## 5. Agent B: a precise and usable performance chart

### Preserve correct arithmetic while exposing its meaning

Do not change performance-1 merely to create a more impressive chart. All current axis indexes match their per-leg formula. A concrete example to include in a hand-check test is Naples ITA G downwind course VMG: its aggregate index is 109.9671, formed from leg indexes 127.0241 with six peers and 92.9101 with four peers. Dividing its aggregate displayed raw means gives 108.0853, which is a different calculation. The interface must make that distinction inspectable.

Type and validate the existing `leg_evidence` fields rather than discarding them. Show the selected leg, own value, peer mean, index, actual peer names/count, coverage and observation count. Add expected-versus-supported course legs, minimum peer count and explicit excluded-leg reasons where needed. Export additional peer raw values, coverage and interval boundaries from Python if they are needed to reproduce the comparison.

Audit the 13 incomplete-scope profiles. The match-final profile must visibly say that only four of six course legs contribute. Keep unsupported intervals unavailable; never infer a missing crossing just to complete the chart.

### User interaction

1. Select race and boat using the existing controls.
2. Choose All comparable legs or a specific completed leg.
3. Activate a circular-chart axis using mouse, touch, Enter or Space.
4. Highlight that axis and open its pinned evidence panel, including its per-leg comparisons and peer list.
5. Review the contributing leg in Replay at the correct race, boat and exported interval.

Selecting a single leg can display its already-exported index directly. Arbitrary multi-leg aggregation, relative deltas or selected-opponent comparisons require explicit Python exports. Two boats' existing indexes use different self-excluded peer baselines; do not overlay them as if they shared an identical reference population.

Clear stale axis/leg selections when race or boat changes. Provide keyboard focus and selected-state semantics. Hover cannot be the only way to inspect a value.

### Visual precision and interpretation

Show readable numeric scores near activated axes and a focused dot/leg-comparison view where 99, 100 and 101 are unambiguous. Keep a clearly labelled full-range circular chart with baseline 100. Use a stable common domain across a race/comparison scope; do not independently autoscale each boat. Scores above the default drawing range must remain distinguishable through an expanded shared domain or explicit overflow treatment. None currently exceeds 150, so clipping is a future regression case, not today's data error.

Preserve full exported arithmetic in evidence with sensible display rounding. Label VMG as leg-directed course VMG, rather than implying a polar target. Replace claims about stronger measured ability with descriptive relative observed performance. Label the six-axis overall number as a heuristic profile summary, with its supported scope; its equal weights are not validated estimates of yacht or crew ability.

A later numerical method may use same-time, same-leg, source-valid comparison windows and observed condition evidence. Any change to weighting, baseline, eligibility, aggregation or overall availability requires a new method version, such as performance-2, refreshed artifacts and race-level evaluation. Missing polar/target data and correlated frames do not justify invented efficiency percentages or confidence intervals. This research is separate from the first usability release.

Acceptance: exact exported aggregate and single-leg values; visible changing peer populations; reproducible ITA G example; four-of-six-leg scope visible; proper zero/null handling; operational axis and Replay interactions on keyboard/touch; no misleading scaling or unsupported ability claims.

## 6. Orchestrator: professional Reports and a quiet technical archive

The data archive is important for audit, reproducibility, exports and older immutable forecast references. Its current 329-row default is not essential to everyday professional use.

Replace the legacy summary binding with canonical historical metrics, quality, coverage, reconstruction/source conflicts and unavailable reasons. Do not silently fall back to differently defined replay summary numbers when analysis is missing. Reuse the race-matched detail already loaded by the dashboard where possible.

Make the primary workflow Race report and exports. Offer concise, friendly actions for race summary, boat/leg performance, full analysis and replay data. Add analyst-ready CSV exports from Python's canonical metrics, with race/boat/leg IDs, value, unit, window, quality, coverage, peer support and method/source references. Place them in the existing analysis output family. Do not compute those metrics again in the browser.

Retain a collapsed Technical data and provenance explorer with search and explicit filters for current race, archive catalogs, supporting evidence and retained versions. Keep every file discoverable and the full inventory downloadable. Paths, hashes, source responses and model internals belong in evidence disclosure rather than occupying the primary report table.

Classify inventory entries in the producer using artifact kind, current/retained status and scope; avoid making React guess these from filenames. Additive metadata or a versioned schema must have a backward-compatible reader. The default list must exclude retained forecast history and raw source responses. Validate entries against actual paths, file sizes and current forecast references.

Acceptance: same named metric agrees between Analysis and Reports in value/window/quality; retired GBR B does not acquire a fictitious racing average; current-race report shows a small set of useful exports; all existing and newly published objects remain available in the technical explorer; new CSVs reconcile with their source analysis JSON.

## 7. Agent C: make Cup uncertainty intelligible and correct

### What the current numbers mean

Pre-change snapshot (2 November 2026): the active baseline uses 5,000 trials. Exactly 1,718 paths are unresolved and 3,282 are resolved. Conservative [0,1] allocation of each unresolved path gives every team's baseline interval a width of 34.36 percentage points. The nine transfer assumptions then widen the combined envelope. For ETNZ, baseline bounds are 17.04-51.40%, while the combined envelope is 13.84-67.08%.

The grid is transfer loading {0,0.5,1} crossed with residual-uncertainty multiplier {0.5,1,2}. These are assumptions, not fitted cross-class correlations or posterior weights. The displayed Transfer scenarios range already includes unresolved-rule uncertainty. Its endpoints may arise from different scenarios. Marginal bound endpoints must not be normalized to sum to one.

Documentation says final Cup scenarios use 100,000 draws, but the current build relies on the helper's 5,000 default. Make the budget explicit and correct the documentation. More draws address numerical simulation error; they cannot remove unresolved-rule or transfer uncertainty.

### Correctness and lineage before display changes

Preserve observed-versus-missing strength provenance. The public mapping currently emits a numerical zero for an unobserved Australian team, while the simulator detects missing history by absent keys. That bypasses part of the missing-team prior treatment. Test and correct this public mapping path, distinguishing an estimated zero from no estimate. Audit the source model used to build Cup strength: the artifact must identify the exact model reference and training cutoff rather than implicitly inheriting the last loop model.

Do not replace unresolved paths with an arbitrary lottery, a midpoint or a point probability conditional only on resolved paths. A missing-rule branch stays unresolved until evidence or a conservative feasible-path treatment justifies more information.

### Evidence export and interface

Export baseline scenario ID; every scenario's parameters, actual trials, seed, model/input hashes and conditioning assumptions; resolved/unresolved counts/fractions; per-team bounds; separate Monte Carlo error; unresolved reasons and first unresolved stage; and the scenarios producing each envelope endpoint. Keep overlapping reason counts separate from mutually exclusive first-unresolved-stage counts.

Show Baseline assumptions: rule bounds and All tested assumptions: outer envelope as separate concepts. Add an existing-style scenario selector and expandable sensitivity table. The selected scenario remains an interval whenever its rules remain unresolved. Explain that the present nine scenarios do not span every uncertainty: reliability is conditioned on completed/scored races, weather response is zero, and AC75 transfer calibration is not established.

Profile which rule clauses create unresolved paths. Where authoritative sources and a feasible branch budget permit, propagate only permitted outcomes and feasible champions; otherwise retain conservative bounds. Do not require narrower bounds as a pass criterion. Further genuine reduction depends on clarified rules, verified outcomes, AC75 target data and transfer validation. These evidence-acquisition tasks form a later research release, not a promise of immediate precision.

Acceptance: public missing-team handling is tested; exact model/cutoff/seed/trial lineage is exported; counts reconcile; bounds reconstruct from scenario records; extrema IDs are correct; baseline belongs to the grid; structural uncertainty and simulation error are distinct; unresolved point estimates stay null; all three original forecast targets remain separate; content-addressed publication is atomic.

## 8. Verification and release checklist

- Independent Python checks for every available ratio, per-leg eligibility, varying peer populations, missing crossings, partial profiles and the public Cup mapping path.
- Frontend checks for real axis activation, keyboard/touch parity, race/boat/leg stale-state reset, exported evidence validation, independent null/zero handling and Reports/Analysis consistency.
- Forecast tests for scenario decomposition, lineage, count reconciliation, baseline membership, endpoint attribution and unresolved/null behavior. Keep hypothetical pre-race, live race and whole-Cup outputs distinct.
- Browser matrix: 1096x704, 1586x992, 1280x720 and 390x844; fleet and match races, both Analysis tabs, Reports filters, all forecast cards, missing-data recovery and actual production artifacts.
- At 1096 px, explicitly check the 1100 px header breakpoint versus the 800 px map breakpoint, open dropdowns, toolbar clearance, chart/evidence visibility and scrolling. Navigation changes and Escape/outside-click must not leave menus obscuring the analysis.
- Visual checks: white surfaces, legible plot/grid/text colours, no permanent Heel/Current, readable chart values, visible focus, internal table scrolling and no document overflow.
- Focused tests first; then run.ps1 verify; dashboard browser suite; dedicated forecast browser suite with real artifacts; inventory/URL/byte checks; public-to-production hashes; preservation of replay arrays and race/boat-race totals.

## 9. Efficiency and completion rules

Use the existing 28-session exports and compact summaries first. The source archive is 6.87 GB; no UI/theme/download-filter change should trigger a raw rebuild. Reuse existing per-leg evidence for the first chart release. If only performance metadata changes, implement a targeted refresh path instead of rescanning raw wind. Recompute models only when inputs or model logic change, with a fixed seed and explicit numerical budget. Save bounded failure excerpts rather than full logs or telemetry arrays.

Workers report changed files, checks run, unresolved assumptions and candidate artifacts. Review code-to-export-to-visible behavior, not completion claims. Publish once through the orchestrator and rerun only checks affected by subsequent changes. Completion means all six annotations satisfy their acceptance checks, the original data and navigation remain compatible, and remaining model uncertainty is honestly explained. It does not mean forcing narrow probability ranges or manufacturing missing measurements.
