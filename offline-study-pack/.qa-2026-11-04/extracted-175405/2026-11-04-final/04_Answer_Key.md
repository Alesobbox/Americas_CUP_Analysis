# Workbook answer key

These solutions show reasoning and the scope of each answer. Synthetic examples teach a mechanism; they are not new repository observations or validation results.

## Foundations

### 1 Units and dimensions

One knot is 1852/3600 m/s, so 10 × 3600/1852 = 19.4384449 kt. VMG is length/time while duration is time. Adding them has no physical meaning; multiplying compatible speed and time gives distance. The code uses a finite conversion coefficient, so last decimals can reflect that convention.

### 2 Reading the archive

A session is one exported source race/session, a boat-race is one boat observed in one session, and scheduled entries count the complete scheduled fields. Three scheduled observations have no replay telemetry. PR1 frames are repeated measurements of the same evolving race. They share one winner and common conditions. Counting each as an independent outcome creates pseudoreplication.

### 3 Speed and progress

VMG is the dot product with a unit course direction: 20 cos 30° = 17.3205 kt, versus 20 cos 60° = 10 kt. The first currently makes more progress along that axis. This says nothing sufficient about intrinsic ability: leg direction, position, wind, selected maneuver and course constraints differ. Heading is not necessarily velocity direction.

### 4 Missing is not zero

Unavailable means the defined quantity lacks an eligible window or support; zero means the defined eligible observations yield zero speed. Preserve null and its reason for the retired boat. Do not insert zero into the peer mean or CSV. The second value can be descriptive if the source and window really support it, although performance ratio eligibility can require positive peer values.

### 5 Evidence ladder

GNSS position is a source observation subject to sensor limitations. The regular-grid halfway position is interpolated. Crossing time is reconstructed from geometry/source timing. Expected finish is a model expectation conditional on inputs and conventions. A transfer loading is an assumption varied by scenario, not a measured cross-class correlation. Availability and provenance should travel with each field.

### 6 A result is not a ruling

Under the chosen yacht polygons, heading, position interpolation and tolerance, geometric envelopes overlap. You cannot infer an official penalty, right of way, fault, collision damage or the umpire decision. Sensor error and time sampling also matter. The physical contact computation is separate from enhanced on-screen display size.

## Geometry and time

### 7 Angular wraparound

The signed delta is ((10 - 350 + 180) mod 360) - 180 = 20°. The midpoint is (350 + 0.5×20) mod 360 = 0°. Arithmetic averaging gives 180°, pointing in the opposite direction. At exactly 180° a tie convention is required; do not assume the data can identify which path was physically taken.

### 8 Projection

With K_lon=84374.839 m/degree and K_lat=111047.746 m/degree, x=168.749678 m east and y=111.047746 m north. This is a local metric approximation around the race origin, not degrees interpreted as metres. Moving to another venue requires its origin and coefficients; a filename is not a projection definition.

### 9 Crossing fractions

Write boat position (-2,0)+t(4,0) and gate position (0,-5)+u(0,10). Equality yields t=0.5 and u=0.5, so crossing is halfway through the second and the line. This strict stationary-segment example omits the repository endpoint tolerance, sampled moving marks and event separation logic.

### 10 Gate tolerance

Parameter u is dimensionless. Extending from 0 to -0.20 is 20% of the gate length, or 20 m beyond one endpoint; 1 to 1.20 is 20 m beyond the other. It is not 0.20 m. Consequences should be tested near endpoints, especially when marks move or position uncertainty is large.

### 11 Smooth missingness

No. Resampling creates a regular visual path but does not insert independent source observations. The original gap exceeds the historical coverage threshold. A historical metric can remain unavailable even when the replay looks continuous. Inspect source timestamps and coverage metadata rather than counting regularized frames.

### 12 Publication clocks

No: although its observation precedes 10:00, it was unavailable to the predictor until 10:05. Information availability must precede the prediction cutoff. A historical reanalysis downloaded later also cannot be silently treated as a contemporaneously issued forecast. Store and check distinct observation, issue and available-at times.

## Historical metrics

### 13 Mean of leg ratios

Leg indexes are 100×20/10=200 and 100×30/30=100. Equal leg weighting gives 150. Aggregate selected mean is 25 and peer mean 20, giving 125. The published definition averages leg ratios; calculating 125 in the browser would change the definition. It is possible for both raw aggregate labels and index 150 to be correct.

### 14 Excluding yourself

A peers B,C have mean 20, so index 100. B peers A,C have mean 25, so index 40. Each boat has a different leave-one-out baseline. A baseline including A would be 20 here by coincidence, but including B would give 20 and index 50, a different result. Equal votes are per eligible peer boat, not per telemetry frame.

### 15 Coverage threshold

The selected boat reaches 95%, but the peer misses the 95% threshold. Exclude that peer for that leg. Do not round 94.99 to 95 before eligibility. If no eligible peer remains, the dimension can be unavailable, not zero or an invented 100. The tests explicitly protect this boundary.

### 16 Retention weights

Selected mean is 80%. Peer B contributes its mean 50% once and C contributes 85% once, so peer mean 67.5%. Index 100×80/67.5=118.5185. Pooling all peer events gives 61.6667%, incorrectly letting B vote twice. Actual eligibility additionally checks event type, whole source-supported search windows, completed leg and ambiguity.

### 17 A six axis profile

It establishes that each of the six definitions has at least sufficient eligible evidence for an index under its own rule. It does not establish full-course coverage, all legs, equal precision per dimension or a complete history. Report the 4/6 support and inspect excluded crossings. The source timing audit does not justify inventing the missing endpoints.

### 18 The meaning of 110

It means the equal-weight average of eligible same-leg selected/other-boat ratios, multiplied by 100, is 110 for that dimension and scope. For speed dimensions, this is a 10% average relative difference under that weighting. It is descriptive, peer-dependent and conditional on selected complete supported legs. It is not a causal crew effect, intrinsic ability, full-course guarantee, uncertainty interval or calibrated probability.

## Forecasting

### 19 Plackett Luce first choice

First choice A has probability 2/(2+1+1)=0.5. Given A first, B has 1/(1+1)=0.5. The complete order probability is 0.5×0.5×1=0.25. This simple ranking example assumes positive relative weights and no nonfinish complication; it does not reproduce the correlated race simulator.

### 20 Expected position with nonfinish

E[position]=1×0.2+2×0.3+3×0.1+4×0+4×0.4=2.7. Conditioning on finishing instead would give(0.2+0.6+0.3)/0.6=1.8333. The published scheduled-field convention includes nonfinish; silently conditioning would improve the apparent number by changing the target. Multiple nonfinishers can tie at N, so summed expectations need not obey rank-sum conservation.

### 21 Proper scoring

Brier=(0.7-0)²+(0.2-0)²+(0.1-1)²=0.49+0.04+0.81=1.34. Log loss=-ln 0.1=2.302585. These penalize confident error. State the summed multiclass convention because other sources average components. One outcome cannot establish calibration; a valid 10% event can occur.

### 22 Correlated differences

Var(TA-TB)=4+4-2×0.75×2×2=2 s². Under independence it would be 8 s². Shared environmental effects can cancel in pairwise differences. This alone does not specify the full simulator or imply all correlations are positive; it illustrates why independently perturbing each boat changes rank uncertainty.

### 23 Persistent series strength

Marginal win probability is 0.5×0.8+0.5×0.2=0.5. Two wins have probability 0.5×0.8²+0.5×0.2²=0.34. Replacing the persistent latent variable with independent marginal 0.5 wins gives 0.25. Learning and dependence across races matter even when marginals match. Re-sampling all uncertainty per match can make a series overconfident or structurally different.

### 24 Unresolved path bounds

A=[0.40,0.60], B=[0.25,0.45], C=[0.15,0.35]. Lower endpoints sum 0.80; uppers 1.40. Each upper assigns all unresolved mass to that team separately. The endpoints describe different completions of uncertainty and cannot jointly be a probability vector. Renormalizing changes the question and fabricates an allocation unsupported by the rules.

## Debugging and critique

### 25 Monte Carlo versus structure

1.96√(0.5×0.5/5000)=0.013859, or 1.386 percentage points. This approximates numerical sampling error in a specified event probability conditional on the model. The 34.46% unresolved mass comes from missing path resolution rules. More draws estimate that mass more precisely without deciding how to allocate it. A structural bound and a Monte Carlo interval measure different things.

### 26 Same wind predictions

No. The current conservative wind reference has zero learned effect, so distinct supported input hashes may yield equal expectations. Inspect exact requested conditions, immutable path/model references and support status before blaming caching. If an old input is displayed under new conditions that is a stale-result issue; equal valid outputs alone do not establish it. Nonzero direction offsets remain unsupported.

### 27 Stale asynchronous result

The consumer must accept a response only when its request/race identity still matches the current selection, commonly with effect cleanup or an identity token. Clearing stale display state matters too. The current UI has several independent loading paths, so trace the specific component and artifact rather than assuming one global cache solves every race. Historical values remain producer-owned.

### 28 Hash mismatch

Not necessarily. Forecast content hashing sorts keys, uses compact separators and excludes the disk trailing newline; a byte hash covers the newline. Recompute according to the owning contract. The study manifest intentionally hashes actual bytes. A source reference also needs scope and current-file checks; matching metadata strings alone is insufficient.

### 29 Offline backend

Reading the study pack needs only a browser/PDF viewer. An application forecast request needs a local server/API plus prepared Python environment and feature dataset. A static publication can display existing objects but cannot execute a Python generator. Use the saved evidence to study; prepare and test the optional dashboard/backend before leaving if generation is required.

### 30 An apparent event

The reconstructed or visual path intersects the modeled line, but no direct source position inside the gap confirms the exact event. Check mark motion, endpoint tolerance, source crossing evidence, leg sequence and coverage status. Do not call it an official crossing or use smooth frames as ten independent observations. Sensitivity or an unavailable interval is more honest than false precision.

## Derivation and defense

### 31 Rank expectation identity

Rank_i=1+Σ I(j ahead of i), pointwise, so linearity gives the expectation identity without requiring independent pairwise events. With all nonfinishers scored at N, tied nonfinish scores are not necessarily one plus strict ahead count. Use the actual simulated score convention rather than importing complete-permutation identities. Linearity is general; the representation of rank is conditional.

### 32 Weighting evidence

Pooled mean=(-10-0.8+0.4+0.2)/130=-0.0784615. Equal-day mean=(-0.10-0.08+0.04+0.02)/4=-0.03. These estimate different weighted populations. Neither is a confidence interval. The repository first aggregates within race, then reports race/day summaries to avoid giving a long race arbitrary extra influence.

### 33 Bounds across scenarios

A envelope is[.1,.6] and B[.2,.5]. A maximum comes from Y, B maximum from X. Coordinatewise envelopes need not correspond to a single common scenario, much less a joint probability vector. Preserve endpoint attribution and distinguish the chosen scenario bounds from the outer assumption envelope. Do not normalize either into invented point probabilities.

### 34 What would identify transfer

Collect independently attributable AC75 race-days with mappings fixed before prediction. Compare no-transfer, fixed-loading and learned partial-pooling models in event-level holdouts. Fit weights only on training events. Predeclare a proper score and a negative-transfer threshold. Failure includes no held-out gain, benefit driven by one event or uncertainty spanning nearly all plausible loadings. AC40-only frames cannot identify cross-class correlation.

### 35 Defend and critique one number

A good defense names the selected FRA profile, upwind course-VMG dimension, eligible matching completed legs 1 and 3, six eligible peers, source coverage 548.027 s and leave-one-out peers. The raw selected aggregate 16.8393 kt and peer aggregate 15.2233 kt do not independently define the index, which averages leg ratios. Strong limitations include only two eligible upwind legs in one race, uncontrolled wind, routes and traffic, changing eligible peers, and descriptive rather than causal interpretation. Never translate 110.3193 into a win probability.

### 36 Explain the whole system

Start with recorded boat/course observations. Explain Python identity, projection, timeline, geometry and exports. Separate browser replay geometry from Python historical formulas and forecasting. Show one same-leg peer comparison and one missing value. Distinguish live win, pre-race scheduled-field expectation and multi-stage Cup bounds. Explain why tests protect implementation but small correlated race evidence limits prediction. Finish with an independent result audit or new-day baseline comparison with an explicit failure criterion.
