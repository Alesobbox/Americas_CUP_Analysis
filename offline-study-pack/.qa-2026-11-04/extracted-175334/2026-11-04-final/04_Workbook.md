# Workbook for independent mastery

Use paper first. Each question states whether its numbers are actual repository evidence, synthetic data or a proposed research exercise. The separate answer key gives reasoning; do not open it until you have written an answer. Numerical examples deliberately simplify full producer behavior unless explicitly labelled actual.

## Foundations

### 1 Units and dimensions

Synthetic. Convert 10 m/s to knots and explain why a VMG cannot be added directly to a duration.

### 2 Reading the archive

Actual repository evidence. What do 28 sessions, 224 replayed boat-races and 227 scheduled entries count? Why are 19,488 PR1 frames not 19,488 independent winner observations?

### 3 Speed and progress

Synthetic. Two boats both sail at 20 kt; their velocities make 30° and 60° with the positive course axis. Calculate course-axis VMG. Can you rank their intrinsic abilities?

### 4 Missing is not zero

Actual behavior interpreted through a synthetic scenario. A retired boat has unavailable SOG mean; a second boat has 0 kt over a valid observed window. How should a comparison handle them?

### 5 Evidence ladder

Conceptual, based on actual contracts. Classify GNSS position, regular-grid halfway position, gate crossing time, expected finish and an AC75 transfer loading.

### 6 A result is not a ruling

Actual repository interpretation. A displayed Keep Clear overlap occurs. What can you defend?

## Geometry and time

### 7 Angular wraparound

Synthetic. Interpolate halfway between 350° and 10°. Derive the signed shortest angular change.

### 8 Projection

Synthetic using Naples coefficients. Latitude increases by 0.001° and longitude by 0.002°. Find east/north offsets.

### 9 Crossing fractions

Synthetic. Boat moves from (-2,0) to (2,0) in one second. Gate goes from (0,-5) to (0,5). Calculate path and gate parameters and crossing time.

### 10 Gate tolerance

Actual code parameter, synthetic gate. A 100 m gate accepts line parameter u in [-0.20,1.20]. What physical extension does that permit?

### 11 Smooth missingness

Synthetic. Two source positions are 10 seconds apart; replay shows 100 ms steps between them. Does the historical 2-second support threshold pass?

### 12 Publication clocks

Synthetic causal scenario. A weather observation is at 09:55, issued at 10:05, and the forecast is for 10:00. Can it be used?

## Historical metrics

### 13 Mean of leg ratios

Synthetic. Selected speeds are 20 and 30 kt; eligible peer means are 10 and 30 kt. Find the performance index and compare the ratio of aggregate means.

### 14 Excluding yourself

Synthetic. Boat A=20 kt, B=10 kt, C=30 kt on one eligible leg. Compute A and B indexes.

### 15 Coverage threshold

Actual rule, synthetic observations. In a 100 s completed leg, selected coverage is 95 s; peer coverage is 94.99 s. Should this peer comparison be admitted?

### 16 Retention weights

Synthetic. Selected event retentions are 80 and 80%. Peer B has two 50% events; peer C has one 85% event on the matched leg. Find the equal-boat peer mean and index.

### 17 A six axis profile

Actual case. ITA B in naples_mr_final has six available dimensions, four comparable legs of six and 847.085 covered seconds. What does six-axis completeness establish?

### 18 The meaning of 110

Conceptual, actual index definition. Explain an index 110 without saying the boat is 10% more talented or will win 10% more often.

## Forecasting

### 19 Plackett Luce first choice

Synthetic. Strengths are 2,1,1. Find the first boat win probability and probability of order A,B,C.

### 20 Expected position with nonfinish

Synthetic. Four scheduled boats. A has unconditional finish-position masses 0.2,0.3,0.1,0 and nonfinish mass 0.4, scored at N=4. Find expectation.

### 21 Proper scoring

Synthetic. Forecast(0.7,0.2,0.1), winner C. Calculate summed multiclass Brier and log loss.

### 22 Correlated differences

Synthetic. Two race-time errors each have variance 4 s² and correlation 0.75. Find the variance of their difference; compare independence.

### 23 Persistent series strength

Synthetic. A fair latent coin selects match probability 0.8 or 0.2 once for a two-race series. Find marginal win probability and probability of two wins.

### 24 Unresolved path bounds

Synthetic.100 trials: A wins 40 resolved, B25, C15, and 20 paths are unresolved. Derive team bounds and explain their sums.

## Debugging and critique

### 25 Monte Carlo versus structure

Actual budget with synthetic error calculation. What is worst-case 95% binomial half-width at 5,000 independent trials, and why does it not fix 34.46% unresolved paths?

### 26 Same wind predictions

Actual behavior. Supported 12,13 and 13.25 kt scenarios give the same expected positions. Is this necessarily a cache bug? What would you inspect?

### 27 Stale asynchronous result

Synthetic interface scenario. You select race A, then B, and A loads last. What invariant prevents B displaying A evidence?

### 28 Hash mismatch

Actual canonical contract, synthetic file. A JSON object is written canonically plus newline. Its byte SHA differs from canonical content SHA. Is it corrupted?

### 29 Offline backend

Conceptual operational scenario. The study HTML opens locally, but Generate forecast does nothing because there is no server. What was confused?

### 30 An apparent event

Synthetic scenario grounded in current interpolation behavior. A straight interpolated track crosses a gate during a 10-second GNSS gap. How would you describe it?

## Derivation and defense

### 31 Rank expectation identity

Synthetic derivation. For a complete ranking without nonfinish ties, derive E[rank_i] =1 + sum over j≠i P(j ahead of i). Why does the published nonfinish convention need care?

### 32 Weighting evidence

Synthetic. Day score differences are -0.10,-0.08,+0.04,+0.02, with 100,10,10,10 checkpoints. Compare pooled checkpoint and equal-day means.

### 33 Bounds across scenarios

Synthetic. Scenario X gives A=[.2,.4], B=[.3,.5]; Y gives A=[.1,.6], B=[.2,.4]. What is the outer envelope and can its extremes be one outcome?

### 34 What would identify transfer

Research design, not measured evidence. Propose a test of AC40-to-AC75 transfer that could fail.

### 35 Defend and critique one number

Actual repository exercise. Rehearse a two-minute explanation of FRA upwind performance 110.3193 in naples_pr1, then give the strongest limitation.

### 36 Explain the whole system

Oral synthesis, actual architecture. Explain the project to someone without sailing or forecasting knowledge in five minutes, including one falsifiable next step.
