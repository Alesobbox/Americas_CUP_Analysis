# Part V How forecasting works

## 13 Three targets three different questions

### Learning objectives

After this chapter you should be able to name the random variable in each forecast card, explain why the same boat can have a reasonable pre-race expectation and no live forecast, and distinguish a conditional Cup scenario from a calibrated prediction. You should also be able to trace a published number to its complete scheduled field, model card, and source manifest.

### Begin with the question rather than the algorithm

A replay asks what the archive records about an already sailed race. A forecast asks what outcomes a model considered possible using information available at a specified cutoff. Moving the replay slider into the past does not, by itself, turn retrospective analysis into a causal forecast. A later crossing, an interpolated position supported by a future fix, or a result published after the gun can make a historical display more complete while making a purported historical forecast invalid.

The current Forecast workspace presents three targets. The first is the chance that each entry becomes the first valid on-water finisher of the selected race, conditional on the causal state at a checkpoint. This target includes a possible no-finisher outcome. The second is the expected finishing position before the race, using the entire scheduled field and assigning every nonfinisher rank N. The third is the 2027 AC75 America's Cup trophy winner across an event format. These targets differ in time horizon, class, information, denominator, and evidence quality. They cannot be inferred from one another by relabeling a percentage.

| Output | Random quantity | Information boundary | Current central limitation |
| --- | --- | --- | --- |
| Live race win | Indicator that entry i is first valid on-water finisher | Causal checkpoint plus modeled publication delay | Entire scheduled field and legal phase must be resolved enough to simulate |
| Before the start | R_i in {1,...,N}, with nonfinish scored N | Earlier-day training and pre-gun available conditions | Numerical expectation is provisional, with source-reconstructed completion evidence |
| Cup outcome | Indicator that team i wins the AC75 trophy | Pinned AC40 ranking model, configured rules and transfer assumptions | Unresolved rule paths and unvalidated cross-class transfer produce scenario bounds |

Python owns these calculations. TypeScript selects and verifies already exported artifacts. The browser is allowed to choose which checkpoint or exact scenario to show; it is not allowed to fit a ranking model or invent a probability for a missing entry. This ownership makes model lineage inspectable and protects the distinction between interface state and statistical evidence. [pipeline/prediction/build.py:L133-L225] [pipeline/prediction/contracts.py:L206-L286]

### The scheduled field is part of the estimand

Let N be the number of scheduled entries. The reviewed archive has 227 scheduled boat-races and 224 replayed boat-races. Exactly three practice entries have no legacy replay track: GBR B in the second, third, and fourth Naples practice sessions of 22 September. Forecast headers bind both `boat_ids`, the complete scheduled field, and `replay_boat_ids`, the replay subset. Missing XY telemetry must not remove a competitor from the denominator. Otherwise the remaining boats receive inflated win probabilities merely because a feed failed.

An absence can have different consequences before and during a race. Before the start, an earlier fitted model can express uncertain performance for a scheduled entry. During the race, missing information about that entry's current legal phase can prevent a coherent joint race forecast. The archive therefore contains a legitimate combination: a numerical pre-race expectation, a visible source-only scheduled entrant, and unavailable live probabilities. This is not a contradiction. The two calculations condition on different information.

The current `26_09_22_nap_ipr_pr2` publication illustrates this. Its field contains nine entries but the replay subset contains eight. The pre-race block is `estimated`. Its 121 live checkpoints comprise 100 `gate_ambiguous` and 21 `unavailable` states, with no usable live numerical checkpoint. A reader should not replace those unavailable values by the pre-race probabilities. That would silently change the question. These are actual published counts, saved in the pack's forecast evidence summary.

### Worked example synthetic field with a missing track

Suppose A, B, and C are scheduled. Before the gun a symmetric model assigns each a one-third conditional win chance if all finish. During the race A and B have visible tracks, while C's track disappears. Renormalizing the visible pair to one-half each asserts that C cannot win. The observation only says that C's state is unknown. A careful model can integrate uncertainty over C if it has a validated missing-state model. This repository suppresses joint output when a required state or legal phase is unresolved. That is an explicit availability policy, not evidence that C's true chance is zero.

### Current method status

| Method or component | Reviewed status and role |
| --- | --- |
| Correlated leg-time Monte Carlo | Selected for current baseline race publications, with `provisional_low_evidence` promotion status |
| Ridge Plackett-Luce | Implemented ranking reference, input to Cup mapping, and current exact custom pre-race scenario model |
| Uniform order | Implemented reference and coherent small tail-mixture component |
| Race-equal empirical order | Implemented diagnostic comparator, not current publication model |
| Conditional ranking response | Implemented experimental comparator; custom scenario publication retains zero wind response |
| Constant-velocity Kalman state | Active causal state estimator, subject to age, uncertainty and phase gates |
| Positive delay mixture | Implemented fitter with strict label/promotion requirements; not enabled in current leg-time publication |
| Foundation models GRU TCN SVR HMM | Research-plan alternatives; no claim that they produced current publications |
| AC75 transfer and Cup engine | Active conditional scenario analysis; no established AC75 calibration |

This table is more reliable than a phrase such as the project uses machine learning. Different parts of the system use different statistical models for different reasons. Selection is not proof of general predictive superiority. A reference can remain appropriate for a scenario while a more complex candidate is provisionally selected for live physical-state conditioning. [pipeline/prediction/build.py:L228-L267] [pipeline/prediction/build.py:L387-L416] [pipeline/prediction/models.py:L668-L702]

### If an assumption fails

If the scheduled roster is incomplete, an unconditional winner vector is not well defined for the intended field. If the legal finishing target differs from an official scoring target, a model can correctly predict its own target while appearing wrong against a different result table. If AC40 strength does not transfer to AC75, an internally reproducible Cup scenario can still be practically misleading. Always state the target and conditioning assumptions before defending the calculation.

### Common mistakes and self-test

A probability marked estimated is not a measured frequency. Expected position 2.4 is not a prediction that a boat can physically finish between second and third. A conditional scenario envelope is not a collection of seven independently calibrated confidence intervals. Try explaining, in three sentences, why a nine-entry race with eight tracks cannot be reduced to an eight-entry forecast. Then explain why a Cup card can display intervals while its `probabilities` fields remain null.

Source-reading route: start with `build_race`, compare `simulate_race` and `simulate_order_reference`, inspect `scheduled_entries` in a current race header, then read the availability validator. [pipeline/prediction/build.py:L133-L225] [pipeline/prediction/simulation.py:L177-L226] [pipeline/prediction/simulation.py:L414-L428]

## 14 Causal clocks and state estimation

### Learning objectives

You should be able to distinguish observation time, bucket closure, modeled availability, state time, publication time, and training cutoff. You should understand why a forward filter is appropriate for historical forecasting and why a smooth replay is not automatically an admissible predictor. You should also be able to describe the uncertainty represented by the position ellipse and the limits of its certification.

### A model of what could have been known

The archive has source event timestamps but no actual receipt clock. The implemented contract is therefore event-time reconstruction with modeled latency. It does not reconstruct a measured end-to-end network delay. Source telemetry is reduced to the last observed sample for each asset, channel and one-second bucket. Its original timestamp and ordinal are retained. The bucket cannot be consumed before its second closes. The model then adds a six-second reorder/publication buffer.

For a sample recorded at 12:00:03.750, bucket closure is 12:00:04.000 and modeled availability is 12:00:10.000. A state checkpoint at 12:00:04 may use that closed bucket and is published at 12:00:10. A checkpoint at 12:00:03.500 may not use it, despite the sample lying in the same second. This prevents a future sample within a bucket from rewriting an earlier subsecond forecast. The six-second delay is a declared approximation. Passing its implementation tests does not establish that it matches the original broadcaster's actual receipt behavior. [pipeline/prediction/source.py:L1-L19] [pipeline/prediction/source.py:L80-L129]

The source reader also measures out-of-order timestamps. A source stream whose disorder exceeds the modeled buffer fails the live reorder contract. That gate is conceptually different from an individual boat's telemetry gap. Disorder concerns when samples can be ordered consistently; a gap concerns how long a boat has gone unobserved. Both can invalidate a causal checkpoint for different reasons.

Training uses a stricter chronological boundary. `before_day` requires both a row's race date to precede the training day and its recorded result or evidence availability to precede that day's UTC midnight. A race sailed earlier but whose outcome was available later is excluded until usable. For reviewed audit days, baseline fits are frozen before 26 September; the second audit day does not train on the first audit day. This is a deliberate frozen-candidate test, not rolling within-day adaptation. [pipeline/prediction/labels.py:L194-L196] [pipeline/prediction/build.py:L248-L260]

### Constant velocity means a local approximation

The filter state is the four-dimensional vector x = (east position, north position, east velocity, north velocity). Positions are metres in a local projection, velocities are metres per second, and time increments are seconds. With time increment dt, the transition predicts position by adding velocity times dt and leaves velocity unchanged in expectation. A process-noise covariance allows acceleration and model mismatch.

```
mean_next = F(dt) mean_now
P_next = F(dt) P_now F(dt)^T + Q(dt)
F(dt) = [[I, dt I], [0, I]]
Q(dt) = q [[dt^3 I / 3, dt^2 I / 2],
            [dt^2 I / 2, dt I]]
```

The parameter q controls how quickly uncertainty grows when motion departs from constant velocity. The measurement variance r describes position-observation noise in square metres. They have different jobs. Raising r makes the filter trust an individual fix less; raising q makes its motion prediction less persistent. Neither creates evidence about a future tack. Earlier-date observations fit the parameters. The update uses the Joseph covariance form, a numerically stable expression that helps preserve positive covariance under finite precision. [pipeline/prediction/state.py:L8-L38]

A filter moves forward from past observations. A smoother can use future observations to revise a past state. Smoothing is useful for reconstructing a past race, but a future-dependent smoothed state cannot be used as if known at the forecast cutoff. This implementation stores forward-filter states and queries only the latest state whose bucket was closed by the checkpoint. A subsequent projection carries that state to the checkpoint time. Thus a small source age can still coexist with a nonzero uncertainty radius.

### The ellipse is conditional on a model

The reported radius is the major-axis radius of a nominal 95 percent two-dimensional position ellipse:

```
radius_95_m = sqrt(5.991 * largest_eigenvalue(P_position))
```

The constant 5.991 is the 95 percent chi-square threshold for two dimensions under the Gaussian model. It is not a universal guarantee that 95 percent of every real turn or outage lies inside the ellipse. The source code separately evaluates hidden-block errors against raw observations. Its certification checks steady, turn, recovery-proxy and gate strata, with nonoverlapping masks and earlier-date parameter fitting. A horizon passes only if it has at least 50 masks across two dates, at least 90 percent ellipse containment, and median position error below one tenth of the current leg length. Only a contiguous passing prefix is certified. A failed five-second horizon cannot be skipped in order to claim a passing ten-second horizon. [pipeline/prediction/state.py:L77-L87] [pipeline/prediction/state.py:L248-L313]

This distinction is worth rehearsing. A nominal ellipse comes from a probability model. Empirical containment comes from a particular test population. An outage certificate permits a bounded operational use in particular strata. None establishes exact uncertainty calibration across future regattas.

### Phase is not just position

The model requires a valid start and a complete, increasing gate chain. It does not promote a boat into the next leg merely because its projected XY position crosses a line. That crossing could be a turn, an offset mark, a stale endpoint, or a noisy extrapolation. A predicted state near a gate can be `gate_ambiguous` even if the boat is clearly visible on the replay.

Current source constructs course axes from the previous and next gate midpoints. It projects position onto that axis, obtains remaining fraction, and combines boat-position covariance with mark variance. The mark variance increases with fix age. The reviewed source allows mark fixes up to 30,000 ms old. This differs from the documentation sentence describing a two-second current cap. The executable threshold is 30 seconds in this snapshot. This is a documentation discrepancy and a useful review question: the cap itself is an engineering policy, while empirical support for such mark holds must be established separately. Do not quote the older two-second statement as current executable behavior. [pipeline/prediction/state.py:L164-L206]

Boat position is fresh through two seconds; beyond that it is estimated, with age limits controlled by the relevant outage certificate. A separate radius gate suppresses a state if the major radius exceeds the smaller of 50 metres and ten percent of leg length. Forecast headers also declare a maximum published-state age for frontend selection. The UI's latest-checkpoint rule, the raw position-age gate, and the mark-fix gate are three different rules. Combining them into one generic freshness number loses important information.

### Worked example synthetic gap near a gate

Suppose a 1,000 m leg has 40 m remaining along its axis. The boat's extrapolated 95 percent radius is 35 m and the gate midpoint's allowance is 8 m. Their combined geometric ambiguity reaches 43 m, more than the apparent distance to the gate. A predicted crossing is not robust enough to establish phase. The safe result is an ambiguous checkpoint. On the same leg, a boat 400 m from the gate with the same uncertainty may pass this particular phase gate, but it still needs an age certificate and a valid source gate chain.

If a boat is moving 10 m/s east at a cutoff and no new fix arrives for three seconds, constant-velocity prediction adds 30 m east. It does not infer a new heading or tactical choice. Process covariance grows throughout the gap. If the boat actually tacks, the error can be much larger than a naive distance equals speed times elapsed calculation suggests. That is why turn and gate strata are not allowed to inherit the steady-motion certificate.

### If an assumption fails

If actual source delivery exceeds the modeled latency, a historical replay experiment can overstate real operational availability even while obeying its declared event-time reconstruction. If missing telemetry is more likely during extreme manoeuvres, artificial masks in intact tracks may underrepresent natural outage difficulty. If mark positions are stale during course movement, an apparently precise boat state can still have the wrong course geometry. These are empirical questions that need receipt logs, outage labels and moving-mark comparisons, not merely extra Monte Carlo draws.

### Common mistakes and self-test

Do not call COG a measured heading: COG is direction of ground motion. Do not call the ellipse a boat's physical footprint. Do not treat all time channels as interchangeable UTC timestamps with the same meaning. Explain why a sample at 3.750 seconds cannot support a state published from a 3.500-second cutoff. Then describe the two independent reasons a projected boat can be unavailable: its location may be too uncertain, or its legal gate phase may be unresolved.

Source-reading route: follow `read_source` bucket fields, `CausalRace.position`, `CausalRace.features`, and `certify_outages`, in that order. Then inspect the model card's actual certificate rather than assuming every listed candidate horizon is certified. [pipeline/prediction/source.py:L80-L129] [pipeline/prediction/state.py:L72-L206] [pipeline/prediction/build.py:L85-L100]

## 15 Ranking strength and the meaning of expected position

### Learning objectives

You should be able to derive a simple Plackett-Luce order probability, explain shrinkage and posterior parameter uncertainty, and calculate an expected tied-N rank. You should understand why rank sums can exceed the familiar permutation sum, why unseen entrants need uncertainty, and why source-reconstructed noncompletion is not a mechanical reliability label.

### Ranking is about relative worth

A Plackett-Luce model gives each entry a positive worth w_i. It selects first place in proportion to worth, removes that entry, and repeats among the remaining entries. Writing w_i = exp(theta_i) makes theta_i an unconstrained log-worth. For a complete order A then B then C,

```
P(A,B,C) = w_A/(w_A+w_B+w_C) * w_B/(w_B+w_C)
```

Only differences in log-worth matter. Adding the same constant to every theta multiplies every worth by the same factor and cancels from every selection ratio. The implementation centers fitted entry effects to zero. A discrimination scale multiplies relative effects before probabilities or orders are sampled. The current fit uses scale 1.8, with strength prior standard deviation 1.2 and half weight for eligible practice rows. These are model settings, not measurements of intrinsic crew ability. A doc sentence describing calibration of these settings should not be confused with empirically established probability calibration; the published model card explicitly disclaims the latter. [pipeline/prediction/models.py:L46-L153] [pipeline/prediction/build.py:L79-L82]

The fitted objective combines the negative log-likelihood of valid finisher orders and a quadratic ridge penalty. The ridge term discourages unsupported extreme strengths. It also makes the Hessian invertible. The inverse Hessian supplies a local Gaussian, or Laplace, approximation to parameter uncertainty. This is an approximation near the fitted optimum. It is not a nonparametric confidence guarantee and does not account for every possible model mismatch.

Practices can contribute only when their rows meet the fit's validity and competitive eligibility rules. The configured practice weight is 0.5, not a universal assertion that every practice is half as informative as a competitive race. It is an explicit modeling choice. The fit excludes invalid orders and does not append nonfinishers to a finisher order as weak finishers. A boat may retire after completing a valid timed leg: that earlier physical interval can still train the leg-time model without pretending that its final result was a finish.

### A complete numerical order example

This example is synthetic and fixes known worths to isolate the arithmetic. Let w_A = 4, w_B = 2 and w_C = 1, with all three guaranteed to finish. A's chance of first is 4/7, about 0.5714. The chance of order A,B,C is (4/7)(2/3) = 8/21, about 0.3810. A's chance of beating B in the pairwise comparison is 4/(4+2) = 2/3. The full three-entry winner probability and the pairwise probability answer different questions.

Expected rank can be found by counting rivals ahead. If all finish,

```
E[R_i] = 1 + sum over j != i of w_j/(w_i+w_j)
```

For A this is 1 + 2/6 + 1/5 = 1.5333. This expected value averages many complete orders; it is not the rank obtained by simply sorting estimated worths. The difference matters when comparing two closely matched entries. A model can rank A above B while giving both a wide range of possible finishing places.

### Nonfinish is part of the target

Let s_i be entry i's probability of completing. Under fixed worths and independent completion events, a hand-checkable benchmark is

```
E[R_i] = N(1-s_i) + s_i [1 + sum over j != i of s_j w_j/(w_i+w_j)]
```

The first term scores i as N if it does not finish. The bracket scores it among finishers if it does finish. A rival only counts ahead if that rival also finishes. This exact benchmark appears in `analytic_plackett_luce_expected_ranks`; it validates a particular mathematical model, not every possible dependence structure. The actual simulation also samples common posterior failure risks, so unconditional independence need not hold after those risks are integrated out. [pipeline/prediction/simulation.py:L141-L174]

Using N = 3, the same worths, and s_A = 0.9, s_B = 0.8, s_C = 0.7 gives

```
E[R_A] = 3(0.1) + 0.9[1 + 0.8(2/6) + 0.7(1/5)] = 1.5660
E[R_B] = 3(0.2) + 0.8[1 + 0.9(4/6) + 0.7(1/3)] = 2.0667
E[R_C] = 3(0.3) + 0.7[1 + 0.9(4/5) + 0.8(2/3)] = 2.4773
```

The sum is approximately 6.1100 rather than 6. Nothing has gone wrong. When multiple entries fail, all are scored N. If M entries fail, the realized rank sum is N(N+1)/2 + M(M-1)/2. With three entries and two failures, the ranks are 1,3,3 and sum to 7. In expectation, the excess reflects the chance of multiple failures. For the independent synthetic example the expected excess is 0.1100. A check that forces every expected-rank vector to sum to N(N+1)/2 would reject valid tied-N results.

The same rule explains an actual published example. The Naples match pre-race expectations are 1.3850819 for the entry labelled ITA B in that session and 1.6226181 for NZL B. Their sum is about 3.0077. In a two-entry field, both nonfinishers score 2, so the small excess over 3 is compatible with some both-nonfinish probability. These are model outputs, not observations of fractional finishes. Asset identifiers must be interpreted using the selected session's identity mapping; the same identifier is not a timeless team label.

### Completion evidence has two tiers

The implementation separates independent reviewed completion records from source reconstructions. An independent reviewed started record must establish completion or an exogenous failure. Unknown and time-rule-censored reviewed outcomes block the pooled denominator because no approved exposure treatment is supplied. Source reconstruction is different: a started entry without a valid finish can count as a noncompletion of the first-valid-on-water-finisher target, with its source cause retained as retired, disqualified or unresolved. It does not claim that every noncompletion is an exogenous technical breakdown.

The field name `scheduled_audited` is therefore potentially misleading when read alone. Current model cards also expose `evidence_tier`, `source_records`, `source_failure_types` and `unresolved_audited_starters`. The pinned late-September card used by the current Cup publication contains 81 scheduled records, all 81 source-reconstructed, with 77 ascertained starters, four DNS events and two started noncompletion events. Its stored source failure types are one disqualified and one unresolved. These counts describe the earlier training population; they are not a claim that the entire archive has only two noncompletions. [pipeline/prediction/models.py:L427-L515] [pipeline/prediction/labels.py:L79-L116]

With the Jeffreys Beta(0.5,0.5) prior, the DNS posterior mean in that card is (4+0.5)/(81+1) = 0.0548780. The started noncompletion posterior mean is (2+0.5)/(77+1) = 0.0320513. These are pooled probabilities. A Beta prior regularizes small counts; it does not independently validate the source labels or identify their causes. The simulator samples risks from these posterior distributions rather than treating the means as known constants. Conditional on a sampled shared risk, entry failures can be independent; unconditionally, common risk uncertainty induces dependence. [pipeline/prediction/models.py:L486-L541]

For live forecasting, an observed start excludes DNS for that entry. Observed survival also updates uncertainty about the common failure parameter without counting a partial race as a complete success. This is a subtle distinction: surviving half a course is information, but it is not one additional full-course success in the historical denominator.

### Unknown entries and contrast uncertainty

An unseen entry receives a draw from the population prior rather than a fixed zero effect with certainty. For seen entries, correlated posterior draws preserve information about pairwise contrasts. The sampler centers seen-entry shifts on their zero-sum subspace. Centering removes an arbitrary common shift while retaining pairwise differences. The contrast variance is Var(theta_i - theta_j) = Sigma_ii + Sigma_jj - 2 Sigma_ij. Ignoring covariance can distort how uncertain a matchup is even if both individual marginal variances look plausible. [pipeline/prediction/models.py:L155-L192]

### If an assumption fails

If the finish-order process violates Plackett-Luce's relative-worth assumptions, an exact PL calculation is still mathematically correct for its assumed model but can be empirically poor. If completion differs strongly by crew, class or condition, one pooled Beta process may be inadequate. If practice and competition represent different effort or rules, a fixed half weight may transfer the wrong information. These are reasons to test alternatives on separate days, not reasons to silently reinterpret the fitted effects as intrinsic skill.

### Common mistakes and self-test

Do not equate higher log-worth with a measured faster boat in metres per second. Do not score a DNF as ordinary last among known finishers while claiming tied-N semantics. Do not interpret `available=True` in a completion model as independent audit approval. Explain why N = 4 with ranks 1,2,4,4 sums to 11, and derive the one-unit excess from M = 2. Then explain why adding an unseen entry changes other entries' expected positions even if it has no telemetry history.

Source-reading route: read `StrengthModel.fit`, `sample_log_worth`, `CompletionModel.fit`, `_ranks_and_winners`, and the analytic rank benchmark. Compare the model card's evidence tier with the variable names in the producer. [pipeline/prediction/models.py:L46-L217] [pipeline/prediction/models.py:L427-L541] [pipeline/prediction/simulation.py:L141-L174]

## 16 Simulating a race with shared uncertainty

### Learning objectives

You should be able to describe one Monte Carlo trial as a coherent possible race, explain why correlated factors matter, and separate physical gate-time uncertainty from outcome randomness. You should be able to identify where current simulation is deliberately simplified and why a small uniform-reference mixture must operate on a joint outcome distribution.

### A race is a joint outcome

Independently guessing a win percentage for each boat can produce incoherent outputs: probabilities that do not sum properly, rankings that imply mutually incompatible races, or a boat that simultaneously receives high win probability and an impossible rank distribution. This implementation samples complete races and derives multiple summaries from the same draws. Each draw provides gate times, completion or noncompletion, a winner or no-finisher state, and tied-N ranks. Race-win probability is the fraction of draws won, while expected position is the average of the corresponding ranks.

The model does not simulate detailed future XY tracks or decide a future tacking policy. It simulates positive times for course segments. Leg distances and categories come from the causal known course. A vectorized queue advances boats through those segments. With tactical interaction coefficients pooled to zero, the implementation can evaluate boats in a vectorized manner without treating opponents' future simulated arrivals as observed information. This is an engineering simplification with an explicit statistical boundary, not a claim to model every tactical interaction. [pipeline/prediction/simulation.py:L177-L226] [pipeline/prediction/simulation.py:L319-L342]

### The leg-time model

For duration T in seconds and positive segment distance D in metres, the reference fits log duration using an intercept, log relative distance, log relative wind speed, entry effects, and segment-kind effects. Distances and winds are divided by training reference values before taking logarithms, so the predictors are dimensionless.

```
log median(T_i,k) = b0 + bD log(D_k/D_ref)
                   + bW log(W_k/W_ref) + crew_i + kind_k
```

The distance coefficient has a ridge prior centered at one: doubling length initially tends to double time. Other nonintercept effects are pooled toward zero, with stronger shrinkage on wind. A lognormal residual keeps sampled times positive. The fitted median is not the arithmetic mean: if log T has variance sigma squared, then E[T] = median(T) times exp(sigma squared / 2). Confusing these can make a seemingly unbiased median systematically low as a mean-time prediction. [pipeline/prediction/models.py:L581-L657]

The first interval runs from the gun to the first course gate and already includes start loss. Full observed durations already include manoeuvre and performance losses. Adding an extra generic start penalty or tack penalty would double-count some of that loss. The positive-delay mixture is disabled unless independently reviewed labels and held-out promotion evidence exist. It is not legitimate to interpret the disabled mixture as a measured foil-loss detector.

### Persistent and shared factors

A conceptual version of the sampled log residual is

```
residual_i,k = crew_form_i + shared_race
               + shared_weather(at entry time and median exit time)
               + innovation_i,k
```

Crew form is sampled once per boat for a trial and persists across its legs. A common race factor affects all boats. The weather process is evaluated at each boat's own simulated calendar time, so nearby boats can share conditions without pretending that the same leg number occurs simultaneously. Innovations supply remaining entry/leg variation. Earlier synchronized residual moments estimate factor magnitudes, with shrinkage and variance caps. The innovation autoregression coefficient is currently pooled to zero without certified out-of-fold lag evidence. These dependence estimates are provisional in-sample residual summaries; they are not a fully validated environmental model. [pipeline/prediction/models.py:L610-L643] [pipeline/prediction/simulation.py:L237-L257] [pipeline/prediction/simulation.py:L300-L342]

A simple covariance calculation explains why this matters. Let two synthetic log times be 100-second baseline times multiplied by exp(U+e_A) and exp(U+e_B), with independent zero-mean terms. If Var(U) = 0.04 and Var(e_A) = Var(e_B) = 0.01, each log time has variance 0.05 and their covariance is 0.04, giving correlation 0.8. Yet their log-time difference is e_A-e_B, with variance 0.02. Treating their full 0.05 variances as independent would assign difference variance 0.10 and greatly exaggerate relative uncertainty. A common slow-weather factor changes absolute time while largely cancelling in the gap.

Correlation can also persist within one boat across legs. If a crew is slower today than its historical mean, a persistent form factor makes several slow legs plausible together. Resampling form independently every leg would average that uncertainty away. Conversely, making every shock perfectly persistent would exaggerate long-run variation. The implemented decomposition is one proposed compromise, with empirical limitations made explicit.

### Conditioning on progress and survival

The current partial segment uses its remaining fraction and an uncertainty term projected along the course axis. An observed pace ratio updates the same persistent crew-form factor. It does not add a second ability effect on top of the one already fitted into leg times. Future full segments retain their ordinary generative prior. The boundary identity between zero remaining progress and a full future segment is a useful software invariant: moving the cutoff across a segment boundary should not invent an unrelated prior.

Failure exposure is normalized to the race. Under a constant exposure hazard with full-race failure probability q and survived fraction h, the remaining failure probability is 1 - (1-q)^(1-h). For q = 0.10 and h = 0.5, this gives 1 - sqrt(0.9), about 0.05132, rather than the original 0.10. A transition-weighted hazard is implemented as an alternative shape. The shape and multiplier are assumptions unless separately validated. Timing limits, where supplied, are separate rules applied to simulated arrivals, not a mechanical-failure cause. [pipeline/prediction/simulation.py:L22-L51] [pipeline/prediction/simulation.py:L258-L299]

### No finisher is a real internal category

The winner is the earliest finite valid finish. A trailing nonfinisher does not erase another boat's valid win. The internal no-finisher state occurs only when every scheduled entry has an infinite or otherwise nonfinite finish time. Thus the sum of boat win probabilities plus no-finisher probability is one. If the boat probabilities alone sum below one, the missing mass can be a modeled all-fail event, not a normalization error. Rounding six decimal places can add a very small additional display discrepancy, which is bounded by export validation tolerances.

The simulator uses a fixed 0.0001 mixture with a legally valid uniform-order reference. This regularizes extreme tails while respecting completion and fixed observed order. The same mixture changes winner probabilities, no-finisher mass, expected ranks and sampled outcomes. Adding epsilon independently to displayed probabilities would break this coherence. Terminal impossibilities remain exact when legally known; the mixture is not permission to assign positive chance to an entry already definitively retired. [pipeline/prediction/simulation.py:L141-L151] [pipeline/prediction/simulation.py:L367-L411]

### Numerical error is the smallest uncertainty category

For n independent simulation trials and a probability p, the Monte Carlo standard error is approximately sqrt(p(1-p)/n). The implementation reports the conservative normal-approximation half-width 1.96 sqrt(0.25/n), using the worst case p = 0.5. With 20,000 live draws this is about 0.00693, or 0.693 percentage points. With 100,000 draws it is about 0.00310. These figures describe finite-draw integration noise under the model. They exclude uncertainty about the model, labels, transfer, legal rules and input availability. Doubling decimal precision cannot reduce those other uncertainties.

### If an assumption fails

If tactical interactions substantially alter gate times, a zero interaction coefficient can miss mechanisms such as covering or mark contention. If dependence moments are estimated from too few synchronized races, apparent correlations can be noise. If remaining along-course distance is a poor proxy near a gate, a positive gate-time distribution can still have the wrong median. Resolve these with targeted held-out residual and outcome tests, not an attractive simulated track animation.

### Common mistakes and self-test

Do not call the simulator a full sailing physics engine. Do not add a detected-manoeuvre loss to a duration that already contains manoeuvres. Do not interpret a 0.7 percentage-point Monte Carlo interval as the entire uncertainty in a 60 percent race-win estimate. Explain how a common weather factor can increase uncertainty in absolute finishing time while reducing uncertainty in the difference between two boats. Then explain why a single trailing DNF must not create a no-finisher outcome.

Source-reading route: inspect the median-time fit, factor variance construction, random-array allocation, calendar-time weather function, partial-leg scaling, and joint outcome mixture. [pipeline/prediction/models.py:L550-L657] [pipeline/prediction/simulation.py:L237-L411]

## 17 Evaluation without false confidence

### Learning objectives

You should be able to calculate a Brier score and a log loss, explain chronological evaluation and paired coverage, and distinguish provisional promotion from calibration. You should be able to state the current numerical result with its exact baseline and evaluation population, including the weaker pre-race finding.

### A prediction needs a test population

Software tests establish properties such as deterministic replay, correct mass, valid schemas and safe publication. They do not establish that probabilities predict real outcomes better than a simpler model. A simulator can satisfy every probability identity and still assign the wrong distribution to future races. Empirical evaluation requires outcomes unavailable when predictions were made, a predeclared comparison, and an honest count of independent evidence.

The current procedure uses expanding earlier-day fits on development dates 23 May, 24 May and 25 September 2026. The audit dates are 26 and 27 September. Audit fits remain frozen before 26 September. Practice rows are excluded from scoring, although eligible earlier practice orders may contribute to the configured strength fit. The primary targets use the complete scheduled field and no-finisher outcome. Separate diagnostic comparisons condition on retrospectively observed finishers and are explicitly not unconditional promotion evidence. [pipeline/prediction/evaluation.py:L9-L11] [pipeline/prediction/backtest.py:L15-L82]

The distinction between a diagnostic and a primary score is essential. A model evaluated only among eventual finishers is handed information about which entries will complete. That can be useful for studying ranking conditional on completion. It does not answer the practical pre-race question, where future completion is unknown. Mixing the two populations can make an apparently impressive improvement largely a change in the target.

### Scores and intermediate arithmetic

For a winner vector p and one-hot realized outcome y, the multiclass Brier score is sum_i (p_i-y_i)^2. Smaller is better. The implementation sums over categories; it does not average by the number of categories. Log loss is -log p_winner. A confidently wrong probability is heavily penalized. If a possible winner gets zero probability, its log loss is infinite, which is one reason to regularize valid tails coherently before scoring rather than patching the score afterward.

For a synthetic three-outcome forecast p = (0.6,0.3,0.1) with A winning, the Brier score is (0.6-1)^2 + 0.3^2 + 0.1^2 = 0.16 + 0.09 + 0.01 = 0.26. Log loss is -log(0.6), about 0.510826. If C wins, the same forecast has Brier 0.6^2 + 0.3^2 + (0.1-1)^2 = 1.26 and log loss about 2.302585. The distribution is judged against what happened, not against whether its most likely entry looked plausible.

For expected rank, normalized MSE averages squared rank error after dividing by N-1. A rank error of two places in a nine-entry fleet is scaled by eight; a one-place error in a match is scaled by one. The rank probability score compares cumulative probabilities at each threshold 1 through N-1, then normalizes by N-1. Two distributions can share the same expected rank while having different cumulative distributions, so expected-rank MSE alone does not evaluate the full uncertainty distribution. [pipeline/prediction/evaluation.py:L14-L43]

### Frames do not buy independent evidence

The aggregate first averages all eligible checkpoints within a race. It then computes both equal-race and equal-day averages. A long race does not become more important merely because it has more checkpoints. Equal-day averaging also prevents a day with more races from automatically dominating the summary. It does not make the days statistically independent in a strong scientific sense: boats, crews, venue and conditions can still persist across days. The field `independent_days` is a grouped evidence count, not proof of complete independence.

Paired coverage signatures ensure that candidate and reference use identical races and checkpoints for a metric. A model cannot win merely by declining to predict hard checkpoints while its reference is scored there. Fully resolved terminal checkpoints are excluded from predictive scores so that a long post-finish recording tail does not dilute loss with repeated already-known outcomes. Terminal correctness is tested separately. [pipeline/prediction/evaluation.py:L46-L87] [pipeline/prediction/backtest.py:L83-L113]

A further nuance is the candidate procedure's fallback: if the correlated simulator is unavailable at an otherwise eligible checkpoint, the backtest uses the reference for that candidate row. The scored object is therefore the operational candidate-with-fallback procedure. It is not solely the subset where the complex simulator produced its own prediction. A future evaluation should report both operational coverage and model-only coverage to clarify the source of any gain. This does not invalidate the paired comparison; it defines what was actually compared.

### Current exact results

The pack saves the current `.forecast/backtest.json` so these values can be checked offline. They are existing evaluation artifacts inspected for this book, not a newly executed backtest. The report generation does not retrain the forecast. Do not confuse these results with older ablation values in the prose documentation, which differ slightly and describe separate diagnostic comparisons.

| Population | Candidate race-equal Brier | Reference race-equal Brier | Independent grouping |
| --- | --- | --- | --- |
| Live development | 0.45240196 | 0.83553410 | 8 races on 3 dates |
| Live descriptive audit | 0.50109523 | 0.75890232 | 7 races on 2 dates |
| Pre-race descriptive audit | 0.80243198 | 0.76892734 | 7 races on 2 dates |

The live reference is the joint Plackett-Luce reference with the same scheduled-field/completion framework and a conservative live state extension. The candidate is the correlated leg-time simulation procedure. On the seven-race audit, relative live Brier reduction is 1 - 0.50109523/0.75890232 = 0.3397105, about 33.97 percent. Audit race-equal log loss is 1.11632249 for the candidate and 1.72690091 for the reference. These are preliminary chronological results across only two audit dates, with source-reconstructed outcome and completion evidence. They do not establish future production performance or calibrated probabilities.

The audit is heterogeneous. Candidate daily Brier is about 0.7152 on 26 September and 0.2156 on 27 September. Their equal-day average is about 0.4654, whereas the equal-race average is about 0.5011 because the dates contain different numbers of races. This is a concrete example of why the weighting rule belongs beside the score.

The pre-race result is weaker. Candidate audit normalized MSE is 0.11098385 versus reference 0.10695272; normalized RPS is 0.18012605 versus 0.17822320. Both are worse, though within the procedure's absolute 0.02 guard budgets. Pre-race Brier and log loss are also worse. Promotion does not require every pre-race score to improve. It requires live log-loss improvement and practical Brier guardrails under race/day averages, while separately checking rank MSE/RPS budgets. The code labels the whole result `provisional_low_evidence`. Describing it as a broad improvement of all three forecasting targets would be unsupported. [pipeline/prediction/backtest.py:L114-L145] [pipeline/prediction/evaluation.py:L90-L130]

### Why available does not mean calibrated

Calibration asks whether events assigned probability p occur about fraction p in an appropriate repeated population. A model may improve average Brier or log loss while still being too confident in some ranges. Two audit dates do not support detailed reliability diagrams across boats, winds and progress bands. The current cards use identity calibration and explicitly state that empirical calibration is unestablished. Identity here means the system reports its model probabilities directly; it is not evidence that the identity map has been empirically confirmed.

Promotion gates are operational choices. Their tolerances protect against selected regressions under a small evaluation population. Passing them is not a significance test, a guarantee of positive expected value, or an estimate of accuracy against independently official classifications. Synthetic tests for the gates prove that their Boolean logic works on defined examples; only new eligible races can increase the empirical evidence base.

### Leakage and pseudoreplication thought experiment

Imagine fitting and testing on randomly split telemetry frames. Two adjacent frames share almost the same course, crew, position and outcome. A model could memorize race identity indirectly and appear excellent on held-out frames from the same race. That experiment estimates interpolation within known races, not forecasting a new race. Now imagine using a later finish classification to remove a competitor from every earlier winner denominator. The predictor has learned future completion. Both mistakes can improve scores while reducing practical validity.

The repository counters these risks with day-based cutoffs, explicit availability timestamps, source-prefix tests, complete fields, and paired aggregation. Remaining risks include imperfect source labels, modeling receipt latency, choosing settings after seeing diagnostic data, and inferring natural-outage performance from artificial masks. A careful reviewer asks which of these were controlled prospectively and which remain assumptions.

### If an assumption fails

If later race days differ in crew composition or telemetry quality, the small audit's improvement may not transfer. If the reference is weak in a particular progress band, an aggregate gain may hide regressions elsewhere. If source classifications do not match an independently reviewed target, an internally consistent score can still measure the wrong task. The right next step is a frozen future-race evaluation with explicit abstention coverage and independent label review, not a larger random sample of the same frames.

### Common mistakes and self-test

Do not quote the older roughly 45 percent diagnostic reduction as the current seven-race audit result. Do not translate lower Brier into percent of races correctly predicted. Do not say promotion proves calibration. Calculate the relative improvement from the live audit table and then state, in one sentence, its exact population and baseline. Explain how a model can pass pre-race guardrails while having worse pre-race scores.

Source-reading route: start with `scores`, `aggregate`, `guardrails`, and `promotion`; then follow the primary and diagnostic branches in `run_backtest`. Compare `diagnostic_scope` and `calibration` with the saved evaluation snapshot. [pipeline/prediction/evaluation.py:L14-L130] [pipeline/prediction/backtest.py:L15-L145]

## 18 Cup scenarios transfer and unresolved paths

### Learning objectives

You should be able to explain the tournament adapter, distinguish persistent team uncertainty from race noise, derive why a transfer loading is not a measured correlation, and calculate conservative rule bounds. You should know why interval endpoints can come from different scenarios and why normalizing them is invalid.

### A configured event format rather than a verified future

The Cup engine translates sampled race outcomes into an event winner. It includes seven entrants, six fleet races, Challenger-only qualification, up to three complete round robins, two repechages with initial points, semifinals, a Challenger final and the Cup Match. Defender ETNZ is automatically in the Cup Match, while a Challenger must survive qualification. The asymmetry of the format alone changes trophy probabilities even when per-race teams are symmetric.

This chapter explains the rules configured in the reviewed repository and the pinned document versions recorded there. It does not independently certify that those documents remain the latest external rules on the day you read this. The source manifest records Protocol AC38.10, LVC/Match Conditions v0, and RRSAC v5.02 with hashes. The configured seven-boat fleet points are 10,9,8,7,6,5,4. Overall carry points are 3,2.5,2,1.5,1,0.5,0; Challenger carry is 2.5,2,1.5,1,0.5,0. Earlier plans contained different scoring details, so use the actual adapter and current pinned evidence, not an unqualified recollection of the plan. [pipeline/prediction/cup.py:L92-L155]

The engine separates observed fixed outcomes from future sampled continuations. Known results and official selections override simulated values. A first-to-seven series is not artificially capped at 13 races when zero points, shared results or penalties could extend it. A large safety budget prevents an infinite computation; exhaustion marks a path unresolved instead of silently inventing a tournament winner. These are software semantics for incomplete legal information, not official adjudications. [pipeline/prediction/cup.py:L348-L394]

The top Challenger's default semifinal opponent policy uses observable simulated round-robin win fraction, followed by pre-tournament predicted matchup strength and stable team-name tie handling. It does not inspect the hidden latent ability draws to choose the easiest true opponent. This avoids granting a simulated decision-maker information it could not observe. A policy tie is distinct from an official standings tie: the former defines a modeled decision rule, while the latter requires an authoritative competition rule.

### From AC40 entry effects to AC75 team capability

The mapping averages observed entry effects within a Cup team. For example, the reviewed model has NZL B effect 0.23418897 and NZL G effect -0.08539237, giving ETNZ mapped mean (0.23418897-0.08539237)/2 = 0.07439830. That arithmetic is reproducible. Its interpretation as useful organizational information for an AC75 campaign is an assumption. Crew changes, boat design, foils, control systems, energy constraints and differing competition can all weaken transfer.

Australia is included even though the archive supplies no mapped AC40 entry. It receives a population prior rather than a fixed known-zero effect. A present effect of zero and an absent effect are different: the former is an observed estimate centered at zero, while the latter is missing history. The current mapping preserves that distinction. [pipeline/prediction/cup.py:L508-L541]

For an observed team the transfer construction is

```
theta_AC75 = rho * mapped_AC40_effect + independent_AC75_effect
independent_AC75_effect ~ Normal(0, (sigma_multiplier * pooled_scale)^2)
```

For an unobserved team, the base AC40-like effect is itself sampled from a population distribution. One theta is drawn per team per tournament trial and held persistent through all races. Standard scenarios use rho in {0,0.5,1} and sigma multiplier in {0.5,1,2}, with pooled scale 0.5, match concentration 1 and hazard multiplier 1. These are nine actually evaluated assumptions. They are not nine equally probable worlds. The envelope does not cover an uncomputed full grid of every possible weather, concentration and hazard setting. [pipeline/prediction/cup.py:L157-L159] [pipeline/prediction/cup.py:L185-L217]

### Loading is not correlation

Suppose across a hypothetical population theta_40 has standard deviation s, and independent AC75 residual has standard deviation t. Then theta_75 = rho theta_40 + residual gives

```
Corr(theta_40, theta_75) = rho*s / sqrt(rho^2*s^2 + t^2)
```

Even with rho = 1, positive residual variance makes the correlation less than one. If s = t = 0.5 and rho = 0.5, correlation is 0.25/sqrt(0.0625+0.25) = about 0.4472, not 0.5. This synthetic population derivation explains the parameter's meaning; the repository has not measured such a cross-class population correlation. For observed teams the current simulation treats mapped means as inputs rather than sampling a full estimated joint cross-class posterior, which further limits any literal correlation interpretation.

Match concentration c changes per-race sensitivity to a strength difference through logistic(c times difference). Increasing c reduces match noise conditional on the same capability difference. Increasing persistent AC75 residual variance changes how uncertain the capability itself is. These are different mechanisms. Calling both stronger AC75 performance would hide whether the assumed uncertainty sits between teams or within repeated races.

### Why series uncertainty persists

With known per-race win probability p and independent decisive races conditional on p, a first-to-seven series win chance equals the probability of at least seven wins in thirteen Bernoulli trials:

```
f(p) = sum from k=7 to 13 of choose(13,k) p^k (1-p)^(13-k)
```

For uncertain but persistent p, the series chance is E[f(p)], not f(E[p]). In a synthetic 50/50 mixture with p either 0.5 or 0.9, persistent uncertainty gives 0.5 f(0.5)+0.5 f(0.9) = 0.74995036. Redrawing the latent regime independently every race produces effective p = 0.7 and f(0.7) = 0.93762479. The second calculation averages away the risk that a supposedly favored team is actually in its weaker regime throughout the series. The repository deliberately uses the persistent construction. These values are hand-checkable binomial arithmetic, not observed America's Cup frequencies.

This also explains a symmetry subtlety. With identical known strengths, complete symmetric rules and no failures, ETNZ's direct place in the final gives it one-half trophy probability, while each of six symmetric Challengers has one-twelfth. With uncertain persistent strengths, surviving Challenger selection can favor an unusually strong latent team, so the same equality need not hold. Forcing the equality under all uncertainty configurations would erase the selection effect rather than validate the model.

### What the current public Cup object says

The active index references `cup/5cae98e1c3856cd6885831d0b876d6ae048d0d005d5fc373ab7d0651a8f9a6b5.json`. The publication is method `cup-ac38-conditional-2`, status `estimated`, with a `cup-scenarios-1` evidence extension. Unconditional `probabilities` and `win_prob_by_team` remain null. The saved study-pack copy is small enough to inspect without telemetry. It pins a chronological model trained before 26 September 2026, the source manifest, mapping, simulation inputs and generation-code hashes.

All nine scenarios use 5,000 trials and seed 2027. The named baseline is `rho0.5_sigma1_c1_k1`. Its 3,277 resolved trials and 1,723 unresolved trials give unresolved fraction 0.3446. The first unresolved stage is Challenger round-robin standings. Every unresolved path is retained conservatively rather than assigned an invented tie lottery. Reliability conditions on completed, scored races; failures and timing stoppages are not sampled in this public scenario family. Configured weather response slopes are zero. Thus these are conditional rank-based continuations, not AC75 speed predictions or forecasts of committee raceability decisions.

For ETNZ, 843 of 5,000 trials are resolved wins. Lower bound is 843/5000 = 0.1686. The upper bound gives every unresolved trial to ETNZ as a conservative possibility: (843+1723)/5000 = 0.5132. Luna Rossa's corresponding baseline interval is [0.1660,0.5106]. These are outer rule bounds under one transfer scenario. They are not Bayesian credible intervals or calibrated uncertainty intervals. [pipeline/prediction/cup.py:L395-L448]

### Why the bounds cannot be normalized

For each team, lower counts resolved wins and upper adds all unresolved paths. The lower bounds sum to 3277/5000 = 0.6554. The seven upper bounds sum to 0.6554 + 7(0.3446) = 3.0676. They are not mutually exclusive probability masses. Their widths record ignorance about legal continuation. Dividing lower bounds by 0.6554 instead estimates a conditional distribution among resolved trials and discards unresolved cases, which may be systematically different. Dividing upper bounds by their sum invents an allocation rule. Neither transformation answers the original uncertain-rule question.

The implementation is especially conservative: once any unresolved standings tie affects a trial, it discards the provisional stable-order winner and allows the entire unresolved path [0,1] for every team. It does not enumerate a tight feasible champion set and claim that every team is legally reachable in that path. The bounds are defensible outer bounds precisely because they retain more possibilities than might ultimately be feasible. Narrower bounds require authoritative completion rules or a proven feasible-path analysis; a preference for a more decisive chart is not evidence.

The transfer envelope adds another layer. For each team it takes the smallest lower bound and largest upper bound across the nine generated scenarios. ETNZ's lower endpoint comes from `rho1_sigma2_c1_k1`; its upper comes from `rho0_sigma0.5_c1_k1`. Those endpoints need not occur together in one world. The envelope is not a simultaneous probability vector or a confidence region with known coverage. Scenario IDs beside extrema make that distinction auditable. [pipeline/prediction/cup.py:L582-L631]

### Monte Carlo noise and structural ignorance

At 5,000 trials the reported worst-case 95 percent integration half-width is 0.0138593, about 1.386 percentage points. The baseline unresolved fraction is 34.46 percentage points. Running more trials shrinks finite simulation noise; it cannot resolve missing official tie rules, validate AC40 transfer, or measure AC75 reliability. First-unresolved-stage counts are mutually exclusive. Overlapping reason counts may refer to the same trial and must not be summed. The current baseline happens to have one reason, but the schema supports multiple reasons.

### If an assumption fails

If transfer is weak, scenarios with high rho can overstate the relevance of AC40 history. If the official tie policy is supplied, outer bounds may tighten substantially without changing a single boat's capability assumption. If AC75 failures depend on design, conditional completed-race scenarios can differ greatly from unconditional trophy forecasts. If opponent choice responds differently to public results, sensitivity should compare legal observable policies. These changes belong in separately versioned inputs and publications, not undocumented edits to a favored percentage.

### Common mistakes and self-test

Do not read rho as an observed cross-class correlation. Do not average the nine scenarios using equal weights and call the result a consensus forecast. Do not equate a nonzero lower bound with guaranteed future success. Recalculate ETNZ's baseline bounds from 843,1723,5000. Then explain why both the lower and upper endpoints across all teams can fail to sum to one without a bug. Finally, explain why a 1.386-point Monte Carlo half-width does not make the 34.46-point rule ambiguity disappear.

Source-reading route: inspect `CupScenario`, `CupRules`, persistent theta construction, standings ties, series continuation, and bounds; then compare mapping provenance, baseline record, extrema IDs and conditioning in the saved publication. [pipeline/prediction/cup.py:L44-L155] [pipeline/prediction/cup.py:L185-L263] [pipeline/prediction/cup.py:L348-L448] [pipeline/prediction/cup.py:L508-L657]

## 19 Exact scenarios immutable publications and offline limits

### Learning objectives

You should be able to follow an exact wind request from support checking to a new immutable object, explain why supported wind speeds can produce identical values, and distinguish object identity from factual truth. You should know what a static study pack can provide without a server and what generating a new forecast requires.

### Exact means the requested input

A preset is not permission to borrow the nearest weather scenario. A request for 12 knots and zero offset must either find that exact artifact or generate an artifact explicitly labelled with those inputs. A request for 12 knots and 17 degrees cannot display the zero-degree result as if it answered the request. The local service currently rejects nonzero direction offsets because no validated direction-response model has been promoted. The Python support function additionally checks finite inputs and earlier competitive observations: at least two dates and three races with recorded winds within two knots of the requested speed. [pipeline/prediction/weather.py:L40-L54] [scripts/forecastScenarios.ts:L71-L77]

Support and response are different. Support says the requested condition has enough declared nearby training evidence for this operational rule. It does not prove that the model has learned a weather effect. The exact custom exporter deliberately retains the conservative joint Plackett-Luce reference with empty wind-effect coefficients and seed 42. As a result, two supported speeds for the same race can produce identical expected positions. Their scenario hashes and input labels differ because the requested conditions differ, while the current model's numerical response is zero. This is honest if the card discloses it. It is misleading only if described as a measured sensitivity to wind.

Baseline race artifacts currently select `correlated_mc`; custom pre-race scenarios explicitly select `joint_pl_reference`. Therefore a custom zero-offset scenario can also differ from the recorded-conditions baseline for reasons other than the requested wind. It is a different declared model path, not an isolated one-variable counterfactual experiment. To study a causal wind effect, hold the model family, field and randomization fixed and validate a conditional response on held-out data. The existing scenario controls do not establish that causal effect. [pipeline/prediction/build.py:L387-L437]

A synthetic support example makes the distinction clear. Suppose earlier competitive races at 11,12,13 knots span three races and two dates. A 12-knot request meets the declared speed-neighborhood rule. If all entry-specific wind coefficients are zero, changing the request to another supported speed leaves relative worth unchanged. Softmax or PL order probabilities therefore remain unchanged. Nothing in the support check can manufacture a nonzero response coefficient.

### Publication is a transaction

The prediction directory contains an index, immutable content-addressed race and Cup objects, model cards and source manifests. The index is a small routing document; it is not the entire evidence. A reader holding an older index can still retrieve its immutable references. Builds write immutable objects first, validate the staged graph, and replace the index last. A failure before the final index replacement leaves the previous publication usable. The stable `cup_2027.json` alias is convenient, while the index's hashed Cup path identifies the pinned publication.

A canonical JSON representation sorts keys, removes unnecessary whitespace and rejects nonfinite numbers. Its SHA-256 is the content identity. `atomic_json` writes canonical bytes plus a newline to a unique temporary file in the destination directory, flushes them, synchronizes the file, then atomically replaces the target with bounded retries for transient Windows readers. The object filename's digest is a canonical-content digest; a manifest's raw-file SHA can differ because the stored trailing newline is part of raw bytes. When checking an object, use the same hash definition as its producer. This pack records both provenance and ordinary raw file hashes where appropriate. [pipeline/prediction/contracts.py:L16-L45]

`verify_public` checks actual parsed contents against referenced hashes, model/source lineage, complete scheduled and replay fields, class and scope, exact scenario conditions, probability validity and payload budgets. It does not merely check that a claimed digest has 64 characters. This catches an edited model card whose name still claims the old digest. It also catches an index pointing to a race artifact for the wrong field or a scenario whose metadata does not match its preset. The checks establish integrity and contract consistency. A cryptographic hash cannot establish that the source was truthful, the official interpretation correct, or the model calibrated. [pipeline/prediction/contracts.py:L206-L286]

### Local generation has an operating boundary

The local development and preview servers install a same-origin loopback scenario endpoint. It validates a catalog race ID and bounded inputs, launches Python with fixed arguments without shell interpretation, and returns progress for polling. A workspace lock prevents concurrent publishers. The child PID is recorded before a startup handshake lets the exporter run. Recovery checks both owner and child liveness. A ten-minute watchdog bounds an abandoned child. These mechanisms protect an existing publication from operational collisions; they do not create the required dataset or Python libraries. [scripts/forecastScenarios.ts:L15-L65] [scripts/forecastScenarios.ts:L81-L127]

The scenario exporter writes only a pre-race object with empty live arrays, adds that exact condition to the matching race's presets, validates the staged index and publishes the index last. It preserves the race baseline and Cup references. The browser's input matching and cancellation prevent an old completed request from being displayed under newly edited wind conditions. Canceling polling is not the same as proving the server child stopped; publication locking and the child watchdog cover the server lifecycle separately. [pipeline/prediction/build.py:L404-L437] [src/engine/forecastScenarios.ts:L16-L40]

Static hosting can read previously exported JSON. It cannot execute Python or serve an operating endpoint merely by opening a file. New generation requires the local dataset/cache, source provenance checks, an appropriate Python 3.12 environment with NumPy, SciPy and PyArrow, and the local service. Optional machine-learning packages and downloaded foundation-model weights are not needed for the current core verification path. The study pack's PDFs, HTML, evidence excerpts and synthetic examples remain useful without any of those dependencies.

The forecast artifact middleware reads current files directly and closes their handles before replying. It returns JSON errors for missing objects rather than the application's HTML fallback. This matters because a frontend receiving a 200 HTML page where JSON was expected can otherwise misdiagnose a missing publication. Browser raw-body hash checking also depends on preserving bytes through middleware. A visible loading spinner, a JSON error, a scope mismatch and an unavailable forecast are distinct states with different remedies. [scripts/forecastArtifacts.ts:L21-L55]

### If an assumption fails

If a copied index omits a referenced immutable object, hashes cannot restore it; the pack or installation needs the actual bytes. If a dataset cache has changed, generation should fail rather than reuse an unsealed table. If two server processes publish without a common lock, individually atomic file replacement is insufficient to coordinate their multi-object transactions. If an input edit leaves the old scenario visible, the user may attribute its numbers to the wrong condition even though each artifact is internally valid. Integrity, transactionality and interface freshness need separate checks.

### Common mistakes and self-test

Do not call support validation a learned weather response. Do not assume a static HTML study book supplies a forecasting backend. Do not treat a matching hash as proof of scientific validity. Describe the steps that make a newly generated 12-knot scenario reviewable before it becomes an index entry. Then explain why comparing that scenario with the baseline may change more than wind alone. Finally, explain why raw-file SHA and canonical-object SHA can differ without tampering.

Source-reading route: read `condition_support`, `export_pre_race_scenario`, `canonical`, `atomic_json`, and `verify_public`; then follow the local runner handshake and frontend exact-input validation. [pipeline/prediction/weather.py:L40-L54] [pipeline/prediction/build.py:L387-L437] [pipeline/prediction/contracts.py:L16-L45] [scripts/forecastScenarios.ts:L81-L127] [src/engine/forecastScenarios.ts:L16-L40]
