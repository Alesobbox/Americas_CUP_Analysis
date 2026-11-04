# Appendix Visual reading companion

## A1 Two computational paths from the source archive

![Branched source dataflow](assets/fig01_dataflow.png)

This conceptual diagram describes current responsibilities. The branches share raw source evidence, while the forecasting branch constructs causal features with information cutoffs. Historical peer indexes are retrospective outputs; they are not the pipeline input for live forecasting. Python owns historical and forecasting arithmetic. The browser reads those exports and handles instantaneous replay geometry and presentation. Boxes group substantial modules and do not imply that one command always executes every box. Sources: [pipeline/run_pipeline.py:L1-L110] [pipeline/historical_analysis.py:L691-L718] [pipeline/prediction/build.py:L1-L90] [PROJECT.md:L5-L21].

## A2 Sailing course and direction conventions

![Synthetic labelled course](assets/fig02_course.png)

Synthetic north-up course schematic, not a recovered course from a specific race. Orange mark pairs identify gates. Blue and teal paths illustrate upwind tacks and downwind gybes; the arrows show direction of travel. Wind FROM north blows toward the course from its upper side. The race boundary, safety boundary and gate line have distinct meanings. Real sessions supply moving marks, course sequences and time-dependent boundaries. The current historical analysis evaluates boat-center exposure to the active race polygon; geometric contact envelopes are a separate model. Sources: [pipeline/reconstruction.py:L268-L302] [pipeline/historical_analysis.py:L82-L117] [docs/data_schema.md:L29-L35].

## A3 Interpolation crossing geometry and source gaps

![Synthetic angular crossing and gap panels](assets/fig03_geometry.png)

All three panels use deliberately simplified synthetic numbers. Left: the shortest arc from 350 to 10 degrees has change +20 degrees and midpoint 0, while an arithmetic mean incorrectly gives 180. Center: bow positions (30,-2) and (30,+3) cross a stationary gate at trajectory fraction 0.4 and gate fraction 0.3; over 100 ms, the interpolated crossing is 40 ms after the earlier sample. The implementation additionally allows a dimensionless 20% line extension and samples moving marks. Right: regular visual states are estimates between source readings; they do not establish measurement coverage inside a ten-second outage. Historical analysis rejects source gaps longer than two seconds. Sources: [pipeline/ingest.py:L136-L235] [pipeline/reconstruction.py:L117-L151] [pipeline/reconstruction.py:L324-L355] [pipeline/historical_analysis.py:L160-L179].

## A4 Mean of ratios and ratio of means

![Synthetic peer index arithmetic](assets/fig04_peer_index.png)

Synthetic values reproduce a meaningful repository test. On two matched legs, selected values 20 and 30 kt against peer means 10 and 30 give leg indexes 200 and 100, whose equal-leg mean is 150. The displayed raw means are 25 and 20 kt; their ratio times 100 gives 125, answering a different question. An index of 110 supports a 10% mean relative difference under the explicit weighting and scope, not intrinsic ability or a win probability. Sources: [pipeline/historical_analysis.py:L531-L609] [tests/unit/test_performance_analysis.py:L53-L65].

## A5 Bounds and persistent uncertainty

![Synthetic unresolved paths and series dependence](assets/fig05_uncertainty.png)

Synthetic left panel: 40 A wins, 25 B wins, 15 C wins and 20 unresolved paths produce coordinatewise bounds A [0.40,0.60], B [0.25,0.45], C [0.15,0.35]. Upper endpoints assign the same unresolved mass to different teams separately; they cannot form a joint probability vector. Synthetic right panel: select p=0.8 or p=0.2 with equal chance once per series. Each race has marginal win probability 0.5, but two wins have probability 0.34 rather than 0.25 from independent marginal draws. This illustrates persistent latent uncertainty, not the complete tournament adapter. Sources: [pipeline/prediction/cup.py:L1-L100] [pipeline/prediction/simulation.py:L1-L90].

## A6 Replay with interpretation markers

![Annotated Replay screenshot](assets/replay_annotated.png)

Actual captured interface from this review, with explanatory numbers added in margins and a new lower banner. The original screenshot content is retained. Marker 1 identifies Grid, which can render without remote map tiles. Marker 2 identifies the selected FRA at the shared playhead. Marker 3 connects the estimated lead margin and signed replay VMG with their interpretation limits. The screenshot's smooth paths do not certify continuous source measurement. Source: current captured Replay workspace; [src/components/dashboard/TacticalDashboard.tsx:L1-L90] [docs/derived_metrics.md:L3-L15].

## A7 Analysis with source limitations visible

![Annotated Analysis screenshot](assets/analysis_annotated.png)

Actual captured Analysis workspace. Marker 1 identifies the selected race. Marker 2 points to the calculated-result disclaimer and expandable source limitations. Marker 3 identifies retrospective classification and exported metrics. This screenshot is an entry view, not evidence that all profile dimensions or all course legs are available. Follow the selected boat's scope and per-leg evidence before interpreting its profile. Sources: current captured Analysis workspace; [src/components/modals/AnalysisModal.tsx:L1-L90] [pipeline/historical_analysis.py:L743-L759].

## A8 Compare with different geometrical questions

![Annotated Compare screenshot](assets/compare_annotated.png)

Actual captured Compare workspace at the shared playhead. Marker 1 identifies explicit A and B selections. Marker 2 connects spatial separation, cumulative race-progress delta and along-leg offset: these are different quantities and can disagree without a defect. Marker 3 connects positive closure to approaching boats. GBR B's held late stream means the picture cannot establish continued measured motion or stillness. Sources: current captured Compare workspace; [src/components/panels/ComparisonPanel.tsx:L1-L20] [docs/source_audit.md:L24-L30].

## A9 Reports with provenance alongside canonical values

![Annotated Reports screenshot](assets/reports_annotated.png)

Actual captured Reports workspace. Marker 1 identifies the result/timing disclaimer. Marker 2 highlights the presence of units, quality and covered seconds beside canonical historical metrics. Marker 3 preserves USA's source start-state conflict beside its calculated result. A file download supplies inspectable evidence; its existence does not mean every field inside is available or independently verified. Sources: current captured Reports workspace; [src/components/dashboard/ReportsWorkspace.tsx:L1-L86] [pipeline/historical_analysis.py:L755-L759].

## A10 Forecast with separate targets and support metadata

![Annotated Forecast screenshot](assets/forecast_annotated.png)

Actual captured Forecast workspace, showing current live output at the recorded playhead. Marker 1 identifies the three prediction targets. Marker 2 identifies the shared playhead and its publication-time contract. Marker 3 connects estimated-state status and source age to support information. Numerical availability does not establish calibration. The screenshot is one published checkpoint, not an empirical validation result. Sources: current captured Forecast workspace; [src/components/dashboard/ForecastWorkspace.tsx:L1-L90] [pipeline/prediction/contracts.py:L151-L197].
