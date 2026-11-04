# Part I What problem does this project solve

## 1 Three questions that must remain separate

### Learning objectives

After this chapter, explain who can use the dashboard, distinguish replay from retrospective comparison and prediction, and trace a displayed claim to the kind of evidence that could support it.

### Begin with the decision

A sailing analyst asks several different questions. What happened near the third gate? Where did this boat differ from the other boats? What should we expect before the next race, or before the next America's Cup? All three questions involve the same boat names, but they need different inputs and different standards of proof. This repository is useful because it brings them together while retaining their evidence boundaries. Its central achievement is an inspectable route from source records to a replay, historical metrics, and conditional forecasts. That route is more defensible than treating every displayed number as a sensor reading or an official result.

The intended user is an analyst, sailor, coach, researcher, or developer who wants to inspect a race and formulate better questions. Replay supports temporal and spatial inspection. Analysis summarizes selected boats and comparable legs. Compare shows two boats at a shared instant. Reports exposes canonical summaries and source artifacts. Forecast presents three distinct model outputs and their availability. These responsibilities appear in the current project guidance and are connected through application state. They do not imply that a tactical action has a known causal effect, or that a winning forecast has established predictive value. [PROJECT.md:L1-L21] [src/App.tsx:L1-L90]

Observing a past race starts from records that already exist. A reconstructed gate crossing may use samples either side of the crossing. A retrospective leg mean may use the whole completed leg. Neither is a causal live feature merely because the dashboard can move its playhead backward. Comparing performance goes one step further: it selects windows, eligible peers, and denominators. Predicting requires an explicit information cutoff, a target, a model, and independent evaluation. Reusing future finish information as a live feature would answer the wrong question perfectly.

### The ownership boundary

Python owns source ingestion, reconstruction, historical formulas, tactical exports, and forecasting calculations. The browser loads versioned exported quantities. It also performs instantaneous replay interpolation and geometry: positioning boats between frames, calculating separations, projecting into screen coordinates, and detecting modeled contact. It must not rebuild historical performance scores from rounded replay arrays. Those arrays preserve compatibility and sometimes hold or interpolate values across source outages; historical analysis has stronger source-coverage rules. [pipeline/historical_analysis.py:L145-L210] [docs/architecture.md:L3-L7]

An useful mental experiment is to disconnect the browser from Python after exports exist. Replay and historical analysis can still display their published evidence when local assets are served. Creating a new exact forecast scenario needs the local generation service and its runtime. A PDF or this HTML study pack needs neither. The ability to inspect a static artifact is separate from the ability to regenerate it.

### Worked example using synthetic data

Suppose a boat is 100 m behind in reconstructed progress and the leader moves at 10 m/s. The continuous replay estimate is 100 / 10 = 10 s. At a later checkpoint, recorded crossings occur at 12:00:00 and 12:00:13, yielding a 13 s split. Both values can be correct because they answer different questions. The first is a moving estimate using current speed; the second compares actual checkpoint timestamps. Calling the first an observed time loss would confuse an estimator with an event measurement.

A third number, 0.30 probability of winning, is neither of these. It is a model's distribution over future outcomes given its information and assumptions. It requires scoring across multiple independent outcomes to evaluate. It cannot be checked by comparing it with a single 13 s gap.

### What would change if the assumptions failed

If source identity were wrong, a geometrically accurate track could be attributed to the wrong boat. If reconstruction were wrong, historical windows and labels could be wrong together. If a forecasting assumption were wrong, software could produce a valid probability distribution for a poorly specified world. Separate evidence layers allow these failures to be investigated without assuming every other layer is invalid.

### Common mistakes and self test

Do not equate a smooth replay with continuous measurement; a higher radar dimension with intrinsic ability; or a published probability with calibration. Explain aloud why passing all geometry tests cannot establish forecasting value. A satisfactory answer names different targets and evaluation evidence, not simply different files.

Read `PROJECT.md`, then the first sections of `docs/architecture.md`, then one historical detail's definitions and provenance. Locate the producing Python function before opening the React component. This reading order follows the direction of responsibility rather than the directory hierarchy.

## 2 Sailing and coordinate conventions

### Learning objectives

Interpret the course diagram, distinguish heading from course over ground, derive a compass-direction vector, and explain why fast sailing can have modest progress toward a gate.

### A race is a sequence of directed legs

The start line joins two source-identified marks. At the gun, boats must satisfy racing rules about which side of the line they occupy; the software reconstructs bow crossings and preserves conflicts with source start state. A leg runs from the start or a previous gate to the next gate. A gate comprises two marks that boats pass between or round according to the course. The repository obtains the ordered sequence from session metadata. Cagliari sessions include six-leg courses; the original Naples fleet benchmark has four legs. A program that hard-codes four legs can declare a boat finished at an intermediate gate. The current reconstruction checks the final sequence. [pipeline/reconstruction.py:L268-L302] [pipeline/reconstruction.py:L489-L548]

Wind direction means the direction the wind comes from. If true wind direction is north, an upwind leg points approximately north. A sailboat cannot normally sail directly into that wind. It alternates slanting courses, turning its bow through the wind in a tack. Downwind it may alternate broad courses and turn its stern through the wind in a gybe. Port and starboard describe sides of the boat; in this code's signed TWA convention, stable negative TWA is classified port and positive TWA starboard. A negative sign alone does not encode a rules ruling.

The course diagram should be read as a schematic: start/bottom gate below, top gate above, alternating directed legs, and a wind-from arrow entering from above. The race boundary restricts the racing area; the safety boundary is a separate polygon. A modeled Keep Clear envelope is attached to a vessel. These three boundaries have different purposes and must not be substituted.

### Heading and motion

Let east be x and north be y. Compass bearing theta is measured clockwise from north. A unit vector pointing along that bearing is u(theta) = (sin(theta), cos(theta)), with degrees converted to radians before calling trigonometric functions. This order differs from the usual mathematical convention (cos(theta), sin(theta)) measured counterclockwise from the positive x axis. Confusing them rotates or mirrors a result.

Heading describes the direction the bow points. Course over ground, COG, describes the direction of ground-relative motion. SOG is the magnitude of that motion. Current, leeway, and turning can make heading and COG differ. The code uses heading to project the GNSS antenna to the bow and orient modeled hulls. It uses COG to project velocity for VMG and start closing speed. Swapping them changes the physical question. [pipeline/reconstruction.py:L103-L114] [pipeline/historical_analysis.py:L70-L79]

The true wind angle is the signed shortest angular difference from heading to wind-from direction: TWA = wrap(TWD - heading) into [-180, 180). A value near zero means wind near the bow, while magnitude near 180 degrees means wind near the stern. The replay preserves signed TWA. Historical distributions use absolute TWA and stable-side medians to avoid cancellation. Equal time at -45 and +45 degrees has mean signed angle zero but is not head-to-wind sailing.

### Worked example using synthetic data

A boat travels at 20 kt with COG 60 degrees. Its velocity components are east = 20 sin(60) = 17.321 kt and north = 20 cos(60) = 10 kt. With a course axis of 0 degrees, upwind course VMG is 10 kt. If local wind comes from 30 degrees, upwind wind VMG is 20 cos(60 - 30) = 17.321 kt. The boat is moving much more directly into its local wind than along the configured northward course axis. Neither number is an error.

If heading is 50 degrees while COG is 60 degrees, using heading would yield 20 cos(50) = 12.856 kt along north. That is the projection of a hypothetical heading-aligned velocity, not the measured ground-track velocity. SOG/COG must remain paired for this metric.

One knot is 1852 m per hour, or 1852 / 3600 = 0.514444 m/s. A 20 kt boat moves about 10.289 m/s, or 1.029 m per 100 ms replay step. The AC40 bow is projected 12.963 m ahead of the transom GNSS origin, an offset large enough to change a start-crossing timestamp materially.

### Nonfinish states and interpretation

DNS means did not start, DNF means no completed finish in the reconstruction, RET means retired, and OCS concerns being on the course side at the start. These are not interchangeable. The compact replay may display DNF at the end because it lacks a separately timed transition. A zero legacy elapsed field is not a zero-duration race. Historical result/elapsed fields become null when a valid finish is absent.

If the course axis did not correspond to the intended direction of alternate legs, the parity-based VMG signs would be misleading. If the wind instrument had a directional bias, wind VMG and TWA would change while course VMG would not. These are useful diagnostic separations.

Self-test: why can two boats with equal SOG have different VMG? Why can a boat win while having lower average SOG? Answer with route, direction, timing, and eligibility rather than a claim about hull quality. Read `docs/data_schema.md`, the three short angle/VMG helpers in `pipeline/ingest.py`, and the two historical VMG functions before reading larger analytics routines.

# Part II What information actually exists

## 3 The archive and the evidence ladder

### Learning objectives

State the current observation population, distinguish scheduled from replayed entrants, and identify which uncertainty survives even after every source byte is known.

### Current population

The compact current export review contains 28 sessions and 224 replayed boat-races. There are nine Cagliari sessions dated 22-24 May 2026 and nineteen Naples sessions dated 22-27 September 2026. Twenty-six are fleet sessions and two are match sessions. Every exported class is AC40. The archive therefore does not directly supply matched AC75 race observations for learning a measured AC40-to-AC75 transfer correlation. The source audit records 227 source competitor entries: three GBR B practice entries on 22 September have no replay telemetry and do not become historical boat-races. The Cagliari replay total is 63, Naples 161. The historical source audit's Naples 164 is the source-entry count, not the replay total. [docs/source_audit.md:L3-L7] [pipeline/historical_analysis.py:L956-L1008]

The raw archive size recorded in the audit and repository instructions is 6,866,006,601 bytes across 28 files. This pack reuses that streaming audit rather than rescanning gigabytes to reproduce every raw statistic. The current review independently checks the exported catalog and details through `scripts/analysis_snapshot.py`. Raw-size and fine-cadence claims remain dated audit evidence; current exported counts are current snapshot evidence. Source identity hashes in the pack help determine whether the reviewed implementation and artifact set have changed.

One subtle identifier deserves attention: `26_09_25_nap_ipr_race_3` carries exported date 2026-09-26. A filename-like ID is a stable key, not an authoritative date parser. The catalog/date fields own the displayed date. This is a metadata naming discrepancy worth retaining in the reading notes, not silently correcting in a study report.

### Frames are not independent races

The PR1 benchmark has 19,488 100 ms frames for each included boat. Nine boats times 19,488 states is a large number of synchronized observations, but they share one race, weather episode, course, and interacting field. Neighboring states are strongly autocorrelated. A model trained on random frames and tested on other frames from the same race can learn race-specific information instead of generalizable performance. The historical index therefore counts one boat-race at a time and separates fleet and match cohorts.

Even 224 boat-races are not 224 independent environmental experiments: several boats share each session, some sessions share a day, and a team repeats across events. The useful sample size for a claim about a new race or day is governed by those independent units. More frames can improve precision about a trajectory within a race without increasing the number of independent race outcomes for validation.

### Evidence ladder

Measured observations are timestamped GNSS, heading, SOG, COG, and local or official wind messages. Calculated quantities include projection, TWA, VMG, signed boundary distance, and leg means. Interpolated states estimate values between timestamps; held states extend an endpoint. Reconstructed events combine recorded timing with geometry and classification rules. Model estimates include future ranking distributions or tournament outcomes. Assumptions include cross-class transfer and unresolved tournament mechanisms. Unavailable values express insufficient source support for a defined quantity.

This ladder is not a simple ranking from good to bad. A calculated Euclidean distance from sound positions may be reliable; an inconsistent measured message can be unreliable. The point is to name the transformation and its support. Quality `derived` is a source-coverage classification, not a causal-validity or sensor-accuracy certificate. Quality `source_timing` indicates a recorded leg-time field, not independent official verification.

### Worked example using synthetic data

A 100 s leg has 96 s of valid source support. A mean speed can be `derived` because 96 / 100 = 96%, above the 95% threshold. A second boat has 94 s and the same numerical mean; its quality is `partial`, making it ineligible for a performance peer comparison. The difference in score availability follows a rule, not a finding that the second boat sailed worse. Neither boat's 1000 nominal 100 ms frames supplies 1000 independent leg observations.

A useful evidence sentence has four components: value, scope, transformation, and limitation. For example: 'FRA's PR1 upwind course-VMG index is 110.319 over matched legs 1 and 3, using source-covered historical metrics and other eligible boats; changing conditions and routes remain uncontrolled.' Each component prevents a different overclaim.

### Failure implications and reading route

If a raw file changes while its old audit remains in use, the audit is no longer a complete description of that source. If a detail is missing from the catalog, the index builder skips it; a directory file count alone does not establish history membership. If a source competitor lacks telemetry, including it as a zero-speed observed boat would corrupt denominators. These are reasons to inspect the catalog, detail IDs, and source provenance together.

Self-test: can the raw archive have more entrant records than historical observations? Can the same boat produce a valid completed-leg comparison but an unavailable whole-race result? Explain both using explicit denominators. Read `docs/source_audit.md`, run `scripts/analysis_snapshot.py`, then read `build_historical_index` and its catalog-membership checks. Do not begin by opening raw JSONL in an editor.

## 4 Time synchronization and the meaning of missing data

### Learning objectives

Reconstruct a scalar and an angle on a regular timeline, distinguish measurement time from record arrival, and explain why historical coverage cannot be inferred from smooth replay columns.

### A shared clock is a convenience

Raw streams have different cadences. In the original two-source audit, GNSS and heading commonly arrive every 50 ms, while SOG, COG, and local wind commonly arrive every 200-250 ms. Official wind is approximately one observation per second. The replay grid is 100 ms. Consequently, a 10 Hz replay column is not a native 10 Hz sensor stream. It is a synchronized representation built from independently timestamped channels. The original PR1 source window was 12:07:00-12:39:28.700 UTC on 22 September, with 19,488 exported frames. The match final window was 14:17:00-14:42:00 UTC on 27 September, with 15,001 frames. [docs/source_audit.md:L13-L22]

Ingestion sorts each stream by timestamp and overwrites duplicate timestamps with the latest incoming value among duplicates. Sorting resolves temporal order but does not recover when a message first became available to a real observer. The expanded source audit found messages out of timestamp order by up to 5,850 ms. A replay analysis can be causal by measurement timestamp while still lacking arrival-time causality. If a late message is inserted with an earlier timestamp, a regenerated historical snapshot can change. [pipeline/ingest.py:L98-L133]

For scalar readings (t0, v0), (t1, v1), linear interpolation at t uses u = (t - t0)/(t1 - t0) and v(t) = v0 + u(v1 - v0). Position uses that calculation separately on projected x and y. Angles use delta = ((v1 - v0 + 180) mod 360) - 180, then angle(t) = (v0 + u delta) mod 360. A shortest-arc method expresses the assumption that the smaller rotation is the relevant path between observations. It cannot reveal an unobserved full turn.

### Worked example using synthetic data

A speed stream reports 10 kt at 0 s and 14 kt at 0.25 s. At 0.1 s, u = 0.4, so interpolated speed is 10 + 0.4 times 4 = 11.6 kt. At 0.2 s it is 13.2 kt. Both are estimates between measured endpoints.

A heading stream reports 359 degrees and 1 degree at those same times. The shortest delta is +2 degrees. The midpoint is 0 degrees after wrapping, not 180. An arithmetic mean would rotate the boat through south and could invent a turn-rate spike, manoeuvre, or contact orientation. A circular mean for an entire set of headings instead averages sin and cos components and reconstructs their direction with atan2.

Now change the speed timestamps to 0 and 20 s. The resampler still draws a straight bridge. At 10 s its 12 kt value looks ordinary, but the source has not supported that interval. The historical calculation rejects interior timestamps of source gaps longer than two seconds; no amount of numerical smoothness makes the 20 s bridge measured.

### Held and absent streams

The current replay resamplers hold the first reading before its timestamp, hold the last reading after its timestamp, and fill a wholly absent scalar or angular stream with zero. A single reading becomes a constant stream. These are concrete current behaviors, not recommendations. They preserve existing replay compatibility but can make absence look like stillness, northward direction, or zero wind. Historical analysis retains source first/last times and all gaps over 2000 ms before resampling, and rejects unsupported intervals. [pipeline/ingest.py:L136-L235] [pipeline/ingest.py:L697-L712] [pipeline/historical_analysis.py:L160-L179]

The original PR1 audit provides a consequential real example. GBR B's streams stop at 12:23:37.150, while the export runs to 12:39:28.700. Late positions and speeds are held for 15 min 51.55 s. A stationary-looking boat at that location is not evidence that it remained there. USA has an internal 19.05 s gap, NZL G 74.60 s, ITA G 10.85 s, and NZL B 13.90 s. No tracked match-final boat stream had an internal gap over two seconds in that audit. [docs/source_audit.md:L24-L30]

Historical samples require supported endpoints and midpoint, finite state, and plausible SOG between 0 and 80 kt. Coverage seconds sum the accepted intervals; source gaps are excluded rather than assigned zero speed. A partially observed leg can therefore have an available mean but quality `partial`. Missingness changes the eligible population. If high-speed periods were preferentially missing, the remaining mean could be biased even when calculated correctly.

### Failure implications and self test

If a gap contains an actual tack, linear interpolation can suppress it. If it bridges opposite sides of a start line, it can imply a precise crossing unsupported by observations. If an absent wind channel becomes zero, a naive consumer can invent a north wind. The proposed improvement is explicit per-field measured/interpolated/held/unavailable state in replay, with bounded gap policies. That improvement is not implemented merely because historical analysis has coverage checks.

Self-test: why do repeated adjacent values fail to identify an outage? Name measurement rounding, genuinely stable values, interpolation, and held endpoints. Read the three resamplers, then `coverage`, then `_source_valid` and `_samples_between`. This order makes clear why replay compatibility and analytical eligibility differ.

# Part III How raw data becomes a replay

## 5 Identity projection and export

### Learning objectives

Trace a raw asset into a replay boat, convert WGS84 coordinates into local metres, and identify the metadata required to reverse that conversion.

### Identity precedes arithmetic

The source contains session messages, competitor state snapshots, and telemetry observations. An asset ID is the stable routing key; human labels are presentation. Session assets supply competitor identity and dynamic mark membership. Known competitors and class rules still depend on configuration and identity helpers. An unknown future class or asset family needs deliberate ingestion support; a catalog automatically showing successfully exported races does not imply arbitrary raw files can be understood without configuration. [pipeline/ingest.py:L44-L48] [pipeline/ingest.py:L474-L497] [pipeline/ingest.py:L566-L591]

The streaming parser routes one telemetry channel at a time, collects relevant boat and mark series, records boundary changes, and retains competitor state snapshots for reconstruction. It does not load the entire archive as one enormous JSON object. Each file's source SHA-256 is updated while streaming. A study reader should follow the session and a few routed fields rather than print millions of records.

Source competitor records are often cumulative snapshots. Counting every appearance of the same penalty as a new incident would multiply one event. Similarly, a source `classification` field may remain unspecified while timing fields contain enough information for reconstructed ranks. The labels in output must preserve that distinction.

### Local metric coordinates

Raw latitude and longitude are WGS84 degrees. Local x is east and y north. With origin (lat0, lon0) and coefficients in metres per degree,

x = (longitude - lon0) times k_lon

y = (latitude - lat0) times k_lat.

The projection helpers implement this affine local approximation and its inverse. The coefficients represent local WGS84 curvature at the chosen origin; they should not be replaced with one global metres-per-degree constant. At local course scales, this gives convenient metre geometry while preserving a reversible mapping for Map mode. Projection validation compares gate-pair Euclidean distances against a Haversine reference. It checks numerical plausibility at known distances; it does not prove the whole Earth is flat or that raw GNSS is error-free. [pipeline/projection.py:L20-L50] [pipeline/projection.py:L84-L149]

### Worked example using synthetic data

Take a simplified origin at 40 degrees north and 14 degrees east, k_lat = 111,000 m/degree and k_lon = 85,000 m/degree. A point at latitude 40.001, longitude 14.002 becomes x = 0.002 times 85,000 = 170 m, y = 0.001 times 111,000 = 111 m. Its distance from the origin is sqrt(170 squared + 111 squared) = approximately 203.1 m. These illustrative coefficients are not a replacement for a race's exported coefficients.

To invert, longitude = lon0 + x/k_lon and latitude = lat0 + y/k_lat. Knowing only x and y is insufficient; the origin and coefficients are part of the artifact contract. Feeding raw degrees into metre-space contact or camera geometry would produce physically meaningless dimensions.

### Marks move and boundaries change

Gate marks have source IDs, target coordinates, and sometimes measured position streams. Ingestion resamples moving marks; without telemetry it falls back to a static target. Course sequences name port and starboard assets for each gate. The current renderer can therefore handle RM3/RM7 starts in Cagliari and varying Naples pairs. It must not infer a gate by choosing whichever two symbols look nearest on screen. [pipeline/ingest.py:L805-L834] [docs/data_schema.md:L29-L35]

Session messages can update race and safety polygons. The exporter preserves boundary timelines so analytical exposure can use the polygon active at a timestamp. A single final boundary drawn over all earlier frames would rewrite the context of earlier positions. This is an instance of a broader principle: metadata can be time-dependent evidence too.

The export is column-oriented: a shared timestamp array and parallel x, y, heading, COG, SOG, wind, leg, and progress columns. This is efficient for animation and avoids repeating timestamps in every object. Array-length integrity matters because a one-index shift associates a plausible value with the wrong time. Replay schema is separate from historical schema 2.0/method historical-2, and additive performance/tactical/debrief extensions have their own versions. Schema changes, method changes, and additions answer different compatibility questions.

### Failure implications and reading route

If identity fails, every later value may be numerically correct but attached to the wrong team. If the projection origin fails, boats and marks can be translated or distorted relative to the map. If a static mark fallback is treated as a measured position, crossing precision is overstated. Improving source-state flags is a better response than hiding these distinctions behind extra decimal places.

Self-test: identify the inputs needed to put a replay point back on a geographic map. Explain why a correct position transform does not validate a finish classification. Read `identity.py`, selected parsing routes in `ingest.py`, `projection.py`, then `export_replay.py` and `src/types/replay.ts` together. Verify one field's unit across producer and consumer.

## 6 Crossings progress manoeuvres and contact

### Learning objectives

Derive a crossing time, distinguish directed crossing detection from a race ruling, and explain why monotonic progress and detected manoeuvres are designed summaries rather than new measurements.

### Bow crossings

For transom GNSS point (x, y), heading h, and bow offset b = 12.963 m for AC40, the reconstructed bow is (x + b sin(h), y + b cos(h)). A crossing calculation solves the intersection between adjacent bow positions P0 + u(P1 - P0) and gate line A + s(B - A). The trajectory fraction u estimates the crossing time t0 + u(t1 - t0). Parallel lines with near-zero determinant are rejected. Direction must agree with the required upwind/downwind course direction. The current routine uses gate marks at the earlier frame, not an exact swept intersection of two moving segments. [pipeline/reconstruction.py:L103-L151] [pipeline/reconstruction.py:L318-L355]

There is also a material geometric tolerance: u must be in [0,1], but gate parameter s is allowed in [-0.20,1.20]. The 0.20 is a dimensionless fraction of line length. For a 200 m gate, it accepts crossings up to 40 m beyond each endpoint in the geometric helper. The concise reconstruction document's phrase 'segments intersect' omits this extension. A reader should trust the explicit executable condition and treat the tolerance as a reconstruction assumption, not an official gate-validity rule. Consecutive geometric crossings must be at least 60 s apart; start detection begins no earlier than 30 s before the gun. [pipeline/reconstruction.py:L122-L147] [pipeline/reconstruction.py:L315-L355]

### Worked example using synthetic data

Let a horizontal gate run from A = (0,0) to B = (100,0). A bow moves from (30,-2) at t0 to (30,3) 100 ms later. Solving -2 + 5u = 0 gives u = 0.4; x = 30 gives s = 0.3. The crossing time is t0 + 40 ms. The PORT half is chosen because s < 0.5. That label is a geometric nearest-half choice, not proof of a legally chosen rounding side.

A bow moving from (110,-2) to (110,3) yields s = 1.1. It lies beyond the strict gate segment but passes the current helper's tolerance. The example demonstrates why a function name is insufficient evidence for its exact contract.

If those positions are the endpoints of a 20 s source outage, solving the same equations still yields a precise number. The arithmetic is well defined while the event evidence is weak. Historical coverage may prevent derived leg metrics from treating the interval as measured, but reconstruction currently uses synchronized arrays. This residual difference should be investigated before claiming official timing precision.

### Timings and classification

Reconstruction prefers supplied leg timing records, adds geometric mark-choice information, and uses geometric fallbacks where timings are missing. A valid finish requires the final course gate. It sorts finish timestamps into ranked classifications. DNF ordering and the historical GBR B OCS/RET special case are reconstruction logic. The raw parser checks a top-level `started` field; historical analysis separately inspects nested `start_state.started` and flags a conflict when all nested states are false but a crossing exists. PR1 USA is the concrete example. The conflict should be adjudicated, not erased by choosing the more convenient source. [pipeline/reconstruction.py:L211-L250] [pipeline/reconstruction.py:L423-L446] [pipeline/historical_analysis.py:L743-L759]

### Monotonic progress

Instantaneous leg progress projects the bow onto the alternating course direction from a gate midpoint, clamps it to a nominal leg distance, and adds completed nominal legs. A running maximum prevents apparent progress decreasing during turns or excursions. This is useful for stable replay ordering but is not distance sailed or signed physical velocity. A boat temporarily moving backward can retain its previous progress. The leader gap is a difference between these constructed progress values, not Euclidean separation. [pipeline/analytics.py:L130-L176]

### Manoeuvres and contacts

The detector requires stable TWA sign transition, at least 50 degrees heading change, peak turn rate of at least 5 degrees/s, at least 2.5 kt entry-to-minimum speed loss, and 8 s minimum separation. Tacks cross near the bow wind direction; gybes cross near the stern. Its search uses 60 samples each side, with entry speed reaching five samples farther back. An efficient low-loss tack can be absent from the event population precisely because it fails the loss threshold. The legacy detector computes a 90% recovery convention, whereas historical analysis recomputes 95% recovery and null when not recovered in its window. Read field ownership before comparing those outputs. [pipeline/manoeuvres.py:L53-L68] [pipeline/manoeuvres.py:L114-L206] [pipeline/historical_analysis.py:L289-L313]

Contacts use overlapping modeled metre-space polygons, including Keep Clear envelopes. Enlargement in the display is separate from physical contact geometry. A geometric overlap establishes only overlap under those polygons, sampled positions, and orientation assumptions. It does not establish a collision, penalty, protest, right-of-way breach, or umpire decision.

Self-test: name three ways a visually convincing crossing can be misleading. Then explain why removing monotonic progress would change replay ordering without changing sailed distance. Read the intersection helper, directed crossing loop, progress routine, detector thresholds, and contact detector in that order. Look for thresholds and fallbacks, not only happy-path equations.

# Part IV What the historical metrics mean

## 7 Speed VMG distance and route geometry

### Learning objectives

Derive the three VMG conventions, calculate a time-weighted mean and percentile, and state why a geometric route ratio is not polar efficiency.

### Start with the denominator

A historical scalar is not just a value. Its definition specifies formula, unit, window, denominator, and source. Its instance adds quality and coverage seconds. The same label at race and leg scope can use different weighting. The canonical definitions are exported from Python. The browser displays them rather than reconstructing them. [pipeline/historical_analysis.py:L31-L62]

An active race window begins at the maximum of reconstructed start crossing, gun, and replay start. It ends at the minimum of finish when available, source window end, and replay end. OCS, retirement, or absent start makes the window unavailable. Completed legs use exact preceding/current crossing timestamps; endpoints need not land on the 100 ms grid. The sample iterator inserts exact endpoints and weights each resulting interval by its actual duration. A 37 ms clipped interval receives 0.037 s weight, not one full frame vote. [pipeline/historical_analysis.py:L194-L210]

Within a leg, define accepted interval durations w_i seconds and midpoint SOG v_i knots. Mean SOG is sum(w_i v_i) / sum(w_i). The denominator is valid seconds. It is not elapsed leg seconds if coverage is incomplete. Acceptable coverage C = sum(w_i) is compared with total elapsed leg duration T. Quality is `derived` when C >= 0.95T, otherwise `partial`. This quality threshold is an eligibility convention, not a standard error or confidence interval.

### Three VMG quantities

The retained replay field `vmg` is SOG times cos(COG minus configured course axis). It is a signed fixed-axis trace. A northbound upwind leg and southbound downwind leg can cancel if averaged together. Such an average is not an overall performance score.

Historical leg-directed course VMG changes target bearing with leg parity. For odd legs bearing a is the course axis; for even legs it is a + 180 degrees. Course VMG = SOG cos(COG - a_leg). The target direction is positive on each active leg. Historical wind VMG instead projects onto local boat wind-from bearing d, positive upwind and sign-reversed downwind. Wind VMG = SOG cos(COG - d) on odd legs, and its negative on even legs. It requires supported local TWD in addition to ordinary state support. [pipeline/historical_analysis.py:L70-L79] [pipeline/historical_analysis.py:L230-L280]

These definitions can diverge under a wind shift. Course VMG answers how rapidly ground motion advances along the configured leg direction. Wind VMG answers how directly ground motion points into or away from the local reported wind. Neither incorporates a measured polar target because no such target exists here. A higher wind VMG is not automatically evidence of more efficient foil settings or sail trim.

### Worked example using synthetic data

For 2 s a boat has 10 kt SOG and for 1 s 16 kt. Mean = (2 times 10 + 1 times 16) / 3 = 12 kt. An unweighted mean of the two values would be 13 kt, answering a sample-count question rather than a duration question. For the same accepted intervals, course VMG values of 8 and 12 kt give mean (16 + 12)/3 = 9.333 kt.

Time-weighted quantiles sort values, sum durations, and select the first value whose cumulative duration reaches the chosen fraction of total weight. In this tiny example the 10th percentile is 8 kt and the 90th percentile is 12 kt. The code uses an observed-value step quantile, not interpolation between quantile ranks. Percentile differences can therefore reflect implementation convention when samples are few. [pipeline/historical_analysis.py:L120-L130]

Suppose projected path segments have lengths 30, 40, and 50 m: sailed distance is 120 m. The straight endpoint distance is 90 m, so route ratio = 90/120 = 0.75. The straight chord may cut outside legal boundaries, point directly into the wind, or ignore required marks. It is a geometric reference only. Calling the remaining 25% avoidable wasted distance is unsupported.

### Distances and whole-race aggregation

Distance sums supported projected GNSS segment lengths, clipped at crossing boundaries. It is not computed by multiplying mean sensor SOG by elapsed time; those sources can differ through smoothing, noise, and missingness. Route ratio requires valid endpoints, positive path, direct distance no greater than path within tolerance, and derived-quality path. Missing endpoints produce null rather than a conveniently favorable ratio.

Whole-race means weight leg means by their valid coverage seconds. By contrast, performance indexes average matched-leg ratios with equal leg votes. A long downwind leg contributes more seconds to race mean SOG but no more than another comparable leg to a dimension index. Different aggregations serve different questions; one should not be used to recompute the other. A whole-race metric for a nonfinisher remains partial even if completed legs are well covered. [pipeline/historical_analysis.py:L264-L285] [pipeline/historical_analysis.py:L810-L820]

Absolute TWA distributions and stable port/starboard medians use supported wind seconds. Stable allocation excludes ±3 s around detected manoeuvres and |TWA| <= 15 degrees. Port time plus starboard time can be less than elapsed time because exclusions are intentional. No missing seconds are silently assigned to the other tack.

If missing data were concentrated during slow turns, the observed mean would be optimistic. If course axis were wrong, leg VMG would be systematically wrong while SOG remained intact. Self-test: derive all three VMG quantities for SOG 20 kt, COG 180 degrees, course axis 0, local wind 350, downwind leg. Explain the sign change. Read definitions, `_leg_metrics`, and race aggregation; compare the same scalar in a detail and its summary CSV.

## 8 Starts checkpoints and mark approaches

### Learning objectives

Calculate signed start distance and along-line fraction, distinguish checkpoint splits from continuous estimates, and identify which mark-approach quantities remain unavailable by design.

### A start is an instant and an event

At the gun the historical analysis samples the boat's supported GNSS, heading, COG, and SOG and the actual sequence-zero mark pair. The bow offset uses heading. Let port mark A and starboard mark B define d = B - A with length L. The normalized along-line fraction is f = ((bow - A) dot d)/L squared. The unit normal n is chosen perpendicular to the line and oriented toward the configured course axis. Signed distance is (bow - A) dot n, positive on the course side. Fraction zero is port, one starboard; the fraction is not clamped, so -0.1 means beyond port and 1.1 beyond starboard. A zero-length line raises an error rather than returning invented geometry. [pipeline/historical_analysis.py:L106-L117]

Gun closing speed is ground velocity dot n, converted back to knots. Positive means toward the course side. It does not mean the boat will cross legally, nor that it will retain that speed. Start delta is crossing timestamp minus gun timestamp; negative is before gun. Start order ranks valid reconstructed crossings and excludes OCS. A source start-state conflict can coexist with a geometric start observation and should be reported.

### Worked example using synthetic data

Take port A = (0,0), starboard B = (100,0), course axis north. Then n = (0,1). A bow at (25,-5) has f = 0.25 and signed distance -5 m: it is behind the line, a quarter of the way from port. If its SOG is 20 kt with COG 60 degrees, closing speed is 20 cos(60) = 10 kt. The simplest constant-velocity arrival estimate would be 5 / (10 times 0.514444) = 0.972 s. That estimate is not the reconstructed crossing time, which instead uses actual subsequent positions.

At (125,2), f = 1.25 and distance +2 m. Clamping f to one would hide the fact that this bow is beyond an endpoint. This is why the raw fraction is analytically useful even when a UI diagram must fit within a fixed panel.

### Checkpoint arithmetic

For checkpoint j let t_bj be boat b's completed crossing time and m_j the earliest valid crossing time. Split s_bj = (t_bj - m_j)/1000 seconds. A positive split is later than the earliest crossing. Split change is s_bj - s_b,j-1; positive means the delay grew. Rank change is current checkpoint rank minus previous checkpoint rank; positive means a numerically worse rank. The first completed gate has no previous comparison and therefore null change. [pipeline/historical_analysis.py:L861-L879]

These differences compare event times, not a continuous race-progress model. The earliest crossing boat at gate 2 need not be the same boat as at gate 1, and the boats may cross under different wind. A split growing by 8 s is an observed relative timing change, not proof that a particular tack cost 8 s. A pairwise progress gap divided by leader speed can disagree with these splits for sound reasons.

A limited edge case deserves thought: the current checkpoint rank map is keyed by timestamp. Equal timestamps are mapped through an enumerated sorted list, rather than a documented competition/dense-tie rank policy. No claim here relies on a tie occurring in the current artifacts. It is a testable boundary-policy question before treating all possible tied checkpoint ranks as resolved.

### Actual PR1 example

In the reviewed detail FRA's gun bow distance is -4.979608 m, along-line fraction 0.678562, SOG 33.551249 kt, and closing component 14.194847 kt. Its reconstructed crossing timestamp is 1790079000436 ms, 0.436 s after the gun, second in start order. The first-leg endpoint is 1790079233827 ms, so elapsed leg time is (1790079233827 - 1790079000436)/1000 = 233.391 s. The first checkpoint split is 0 s and rank 1. These are actual exported numbers, not a synthetic fixture. Their precision describes the calculation and timestamp format; it is not independent proof of millisecond timing accuracy. [public/data/analysis/naples_pr1.json:L1-L1]

Mark approach is sampled 20 s before the selected gate crossing using that mark's moving position at the same time. It reports distance and absolute angular difference between COG and bearing to the mark. Entry and exit SOG are observations at crossing minus/plus 5 s. There is no stable rounding-start and rounding-end definition, so rounding time remains null. FRA's first gate has approach distance 254.51 m, approach angle 14.82 degrees, entry SOG 30.35 kt, exit SOG 26.75 kt, and unavailable rounding duration. Those speeds do not define a lost-time integral. [pipeline/historical_analysis.py:L316-L338]

If a mark moved during a gap, using a static target could bias approach angle. If gate timing were inconsistent, leg durations could be non-increasing and become ineligible downstream. If the boat were held at the gun, visually readable start geometry would need a source-support check. Self-test: explain how a boat could start later yet lead at the first gate without invoking a defect. Read `start_line_geometry`, gun metrics, `_gate_analysis`, and checkpoint deltas. Inspect the corresponding debrief timestamp only after the timing semantics are clear.

## 9 Manoeuvre and boundary metrics

### Learning objectives

Explain the selected event population behind retention, calculate recovery under the historical convention, and distinguish sampled boundary exposure from a rule violation.

### Detection selects the population

Historical manoeuvre counts and loss distributions reuse detected tacks and gybes. Count is the number of selected events, not an independently annotated inventory of every turn. Speed loss is entry SOG minus minimum SOG, in knots. Median loss and median recovery have event denominators; race SOG has a seconds denominator. Pooling them without naming these units obscures the question.

Historical recovery searches supported SOG around the event to locate a minimum, then finds the first sampled SOG at least 95% of entry speed before event timestamp plus 15 s. Recovery is measured from that local minimum. This is a discrete sampled threshold time, not a fitted acceleration curve. If no qualifying reading is reached, recovery is null with a reason. Acceleration is (0.95 times entry - local minimum)/recovery seconds, in kt/s, when a positive recovery exists. An event within 5 s of a gate is flagged ambiguous rounding. [pipeline/historical_analysis.py:L289-L313]

The detector's legacy recovery field uses 90% and a different timeout representation; historical recovery is recomputed. Thus importing a field because its name contains `recovery_time_s` without checking the producing path can mix conventions. The coexistence is compatibility, not two interchangeable estimates of a single defined metric.

### Worked example using synthetic data

Entry speed 30 kt and minimum 24 kt imply loss 6 kt and retention 100 times 24/30 = 80%. The historical recovery target is 28.5 kt. Suppose the local minimum occurs at 10.0 s and valid SOG first reaches 28.5 at 14.0 s. Recovery is 4 s and the threshold-based acceleration is (28.5 - 24)/4 = 1.125 kt/s. A 90% target would be 27 kt and could be reached earlier. Without specifying the target, two recovery numbers cannot be compared.

An event with entry 30, minimum 29 has retention 96.667%, but its 1 kt loss fails the detector's 2.5 kt requirement. It is not in the selected retention population. Concluding that all real manoeuvres retain only 80% because observed detector events do would be selection bias. Good low-loss manoeuvres can be systematically absent.

### Retention eligibility and coverage

Performance retention requires reconstructed, non-rounding events with finite entry/minimum speeds, loss at least 2.5 kt, and fully supported SOG, heading, and local TWD across the detector support window. That support is 65 samples before and 60 after the event. At 100 ms cadence this is [-6.5,+6.0] s, 12.5 s total. At 200 ms it is [-13,+12] s, 25 s. It must lie within a completed leg. It is not sufficient that only the event timestamp is covered. [pipeline/historical_analysis.py:L476-L527]

Overlapping support windows merge before coverage seconds are added. Two isolated default-cadence windows give 25 s support; two such windows overlapping by 4 s give 21 s, not 25. `sample_count` still counts two events. Each boat's events are averaged within a leg before it enters a peer mean. A boat with ten events does not get ten votes against a boat with one event.

### Boundary exposure

The signed distance is the minimum Euclidean distance from the boat center to the active race polygon's edges, positive inside and negative outside. Inside/outside uses a ray-crossing polygon test. The historical scalar `boundary_nearest_m` is the minimum signed value over valid active samples; a negative minimum indicates that at least some sampled positions were outside. Buffer time counts 0 <= distance <= 25 m; outside time counts distance < 0. It uses center position, not bow, hull, safety polygon, or Keep Clear envelope. [pipeline/historical_analysis.py:L82-L103] [pipeline/historical_analysis.py:L821-L855]

For synthetic signed distances +10, +30, -2, -4 each lasting 0.1 s, buffer exposure is 0.1 s, outside exposure 0.2 s, and nearest signed value -4 m. These are sampled exposures. They do not integrate exact continuous entry/exit geometry. Outside periods lasting at least 1 s become replay-linked intervals; a shorter episode can contribute outside seconds without becoming a linkable period.

Boundary coverage requires usable state and a race polygon at the relevant time. Missing intervals terminate the currently accumulated outside episode instead of claiming continuity through unobserved time. This avoids one form of overstatement but does not propagate GNSS uncertainty into a probability of being outside. A position 0.1 m outside is not automatically conclusive under metre-scale sensor uncertainty.

### Tradeoffs and self test

A conservative retention support window excludes more questionable events but leaves fewer comparisons. A permissive detector may count more genuine turns while admitting wind shifts or roundings; a strict detector can miss smooth turns. These are measurable precision/recall tradeoffs requiring independent annotation. Software thresholds alone cannot establish detector accuracy.

Self-test: can two boats have identical median selected-event loss but different tack counts, coverage, and intrinsic skill? Yes; list the selection, maneuver-entry conditions, and contextual differences. Read the detector first, `_event_analysis` second, `_retention_by_leg` third, then boundary sampling. Keep every denominator attached to its unit.

## 10 Peer indexes and what 110 supports

### Learning objectives

Recalculate a dimension index, distinguish equal-leg mean ratios from aggregate-value ratios, and give an accurate verbal interpretation of a score of 110.

### A descriptive comparison on matched legs

The six profile dimensions are upwind course VMG, downwind course VMG, upwind SOG, downwind SOG, tack retention, and gybe retention. The first four use covered historical leg metrics. Retention uses the selected-event population described in Chapter 9. Every dimension is higher-is-better under its definition, but that does not mean maximizing SOG independently of route always maximizes winning probability.

Let v_bj be selected boat b's qualifying value on completed leg j. Let P_bj be the other eligible boats with a positive qualifying value on exactly that leg. The peer baseline m_bj is sum(v_pj for p in P_bj) / number of peers. The leg index is I_bj = 100 v_bj / m_bj. The dimension index is I_b = sum(I_bj)/number of matched legs. Each peer has one vote on a given leg; each matched leg has one vote in the dimension. This is a mean of ratios. [pipeline/historical_analysis.py:L531-L609]

The selected boat is explicitly excluded from its baseline. Including it would pull the baseline toward its own value and compress differences. Peer membership can change between legs because source support and completion change. A dimension's `peer_count` is the number of distinct contributing other boats across its matched legs, not necessarily the number on every leg. Inspect `leg_evidence` for the exact denominator.

Eligibility excludes OCS, RET, DNS/nonstarting boats, missing start crossings, and source-state conflicts. A directional leg must be completed with positive finite metric, quality derived, and source coverage at least 95% of its elapsed interval. A DNF may contribute valid completed legs. A missing whole-race finish does not retroactively erase a sound earlier leg. Fleet and match peers are confined to the same race; no archive strength model is fitted in this comparison. [pipeline/historical_analysis.py:L425-L472]

### Worked example using synthetic data

On leg 1 a selected boat has 22 kt against peer mean 20, giving 110. On leg 3 it has 18 against 15, giving 120. The equal-leg dimension is (110 + 120)/2 = 115. The displayed raw selected mean is (22 + 18)/2 = 20 and peer mean (20 + 15)/2 = 17.5. Their ratio times 100 is 114.286, not 115. That difference is expected: average(v/m) generally differs from average(v)/average(m).

If leg 1 lasted 100 s and leg 3 300 s, the dimension would still be 115. A duration-weighted ratio would answer another question. The repository deliberately defines this profile with equal completed-leg votes. An inferred rationale is that each comparable leg is treated as one opportunity rather than allowing a long leg to dominate. That is an interpretation of the rule, not evidence of the author's historical motivation.

For the peer mean, suppose selected value is 24 and other values are 20 and 22. Correct baseline is 21 and index 114.286. Including the selected boat gives baseline 22 and index 109.091. The selected boat would partly benchmark itself, which is why exclusion matters.

### Actual PR1 arithmetic

FRA's leg 1 upwind course VMG is 18.7345278 kt and other-boats mean 15.7411106, giving 119.016556. Leg 3 values are 14.9440212 and 14.7054982, giving 101.621998. Their arithmetic mean is 110.319277. The dimension raw means are 16.8392745 kt and 15.2233044 kt. Both legs have six eligible peers; covered seconds sum to 548.027 and `sample_count` is two completed legs. This actual evidence is preserved in `evidence/data_metrics_review.json` under the FRA PR1 dimension. [public/data/analysis/naples_pr1.json:L1-L1]

An accurate statement is: 'Across FRA's two qualifying matched upwind legs in PR1, its leg-directed course VMG averaged 10.319% above the other eligible boats' mean when each leg's ratio receives equal weight.' It does not mean FRA sailed 10.319% faster in every instant, has 10.319% better intrinsic ability, would win 10.319% more races, or would retain that advantage under AC75 equipment. It does not isolate crew, boat, wind, traffic, route, or tactics.

A generic 110 supports a 10% larger defined quantity relative to that explicit peer construction over that scope. For retention, it compares percentages through a ratio: selected 88% retention versus peer 80% produces index 110. It is an 8 percentage-point absolute retention difference and a 10% relative difference, not a 10 percentage-point retention advantage.

### Overall index and scope

Overall index is the equal-weight arithmetic mean of all six dimension indexes only when all six are available. It is a heuristic profile summary. Dropping missing dimensions would change the weighting between boats; the implementation instead returns null. All six available does not imply all course legs are represented. The match-final winner has six available dimensions from four of six matched legs. Scope explicitly records expected and matched legs, excluded reasons, minimum peer support, and covered seconds. [pipeline/historical_analysis.py:L623-L643]

The radar drawing uses a shared range and can expand beyond its initial scale. Visual limits do not cap exported arithmetic. A shape is a presentation, not the full evidence. The useful habit is to select an axis, inspect its matched legs and peers, then review the interval in Replay.

If weak peers become ineligible, a score can fall even if selected performance stays identical; if strong peers disappear, it can rise. That is a denominator change, not necessarily improvement. A small peer set gives fragile descriptive support. Self-test: design two sets of leg values with the same raw means but different mean-ratio indexes. Then explain why no confidence interval for intrinsic ability follows from this radar. Read `_performance_eligible`, `_performance_leg`, and `attach_performance_analysis`, followed by the exported per-peer evidence and Reports performance CSV.

## 11 Wind observations tactical insights and historical cohorts

### Learning objectives

Separate three wind contexts, reconstruct a trailing observation and conditional trend projection, and explain what the historical cohort summaries count.

### Three wind contexts

Boat-local true wind is a measured input used for TWA and wind-relative VMG. Official wind is a separate source asset used for shared recorded-wind summaries and tactical snapshots. Historical environment data such as sea height or air temperature is external model context, not additional measured yacht telemetry. It must not silently replace either wind source or imply forecast conditioning. [pipeline/ingest.py:L837-L871] [docs/environment_data.md:L1-L15]

Historical wind summaries use active-window official samples. Direction shift is shortest circular difference from the first active official reading, not from the whole-race circular mean. Boat-local direction is aligned at official sample times during valid active windows; deviations over 60 degrees are excluded as outliers. Fleet spread requires at least two valid active boats and measures the range of their local-minus-official deviations. It describes reported exposure differences, not the causal reason a boat gained. [pipeline/historical_analysis.py:L881-L918]

The event feed emits wind-shift events when a shortest circular change of at least 10 degrees from the last emitted reference occurs and at least 30 s have elapsed. These are descriptive events at selected official sample times. Tacks, gates, finish, and gun events have distinct source/quality codes. Missing crossings are omitted rather than given fake fallback timestamps. Event IDs and time ordering make them stable navigation targets. [pipeline/historical_analysis.py:L340-L423]

### Tactical snapshots are trailing calculations

Tactical insights is a separately versioned extension, tactical-1/schema 1.0. Every 10 s from gun through replay-window end it examines the preceding 120 s of independent raw official-wind observations. Each one-second grid instant takes the most recent source reading at or before it, with maximum age 2 s. A direction or speed window requires every grid instant covered, at least 60 source observations, and no actual source interval over 2 s. Availability is evaluated separately for direction and speed. [pipeline/tactical_insights.py:L12-L18] [pipeline/tactical_insights.py:L78-L98] [pipeline/tactical_insights.py:L133-L176]

Direction is unwrapped by shortest circular differences. Net change is last minus first. Rate is ordinary least-squares slope on one-second grid values, converted to degrees per minute. With grid times t_i, centered time x_i, and directions y_i, slope per second = sum(x_i(y_i - mean(y))) / sum(x_i squared). Positive change is clockwise veering; negative counterclockwise backing. Net endpoint change and fitted slope can have opposite signs in a curved or oscillating window. They summarize different aspects of a path.

### Worked example using synthetic data

Suppose a complete window increases steadily from 350 degrees to 352 over 120 s. After unwrapping, net change is +2 degrees and slope +1 degree/minute. A five-minute linear continuation would be +5 degrees. It passes the basic magnitude gates: net >=1, absolute slope >=0.2, and projected change <=30. It still needs both half-window slopes to agree in sign and magnitude, residual RMS within the limit, and no one-second jump greater than 3 degrees.

By contrast, readings of 359 then 1 represent +2 degrees, not -358. A window that rises then falls may have near-zero net change despite a large local trend; a linear continuation would be unjustified. A missing direction stream is unavailable, not a constant zero-degree wind. Speed endpoints can remain available independently.

The projection gates require matching nonzero signs in the two one-minute halves, half-window rates within max(0.25 degrees/minute, 50% of the full rate), residual RMS <= max(1 degree, 20% of net change), and one-second jumps <=3 degrees. These deterministic suppression rules do not constitute statistical validation. A displayed projection states the assumption that the recent trend persists; it has no calibrated probability or interval. In the current published archive no window passes the projection gates. Absence of a projection is the correct current result, not a broken prediction button. [pipeline/tactical_insights.py:L108-L130]

### Playhead and information availability

The browser chooses the latest matching-race snapshot at or before the playhead and expires it after 12 s. Rewinding must select earlier evidence, never retain a future snapshot. The underlying causality statement is measurement-time retrospective causality. Arrival-time information is not established: raw out-of-order records with earlier timestamps can revise an earlier historical snapshot after refresh. The extension states that limit explicitly. [pipeline/tactical_insights.py:L181-L188]

At the PR1 gun, the actual first tactical snapshot has 120 s direction and speed coverage with 117 source observations for each. Net direction change is -23.15 degrees, while fitted rate is +1.603 degrees/minute; projection is unavailable. This is an instructive actual example of net change and regression slope describing a non-linear recent history differently. A rate is not an endpoint-change divided by two unless the underlying path supports that equality.

### Historical cohorts and debriefs

The historical index groups by team code, boat class, and race type. Summary medians and ranges exclude partial/unavailable scalar observations and count one boat-race per available scalar. Completed-leg summaries remain leg-number-specific. Manoeuvre distributions use event counts and record originating race counts, so one can see that many events may come from few races. Event-level precision should not be sold as a large independent race sample. [pipeline/historical_analysis.py:L995-L1049]

Team debriefs choose up to three largest positive completed-leg duration deficits relative to eligible other boats, and up to two largest covered non-rounding detector speed reductions. They are review priorities. A leg deficit in seconds is not a causal decomposition of lost time; a speed reduction in knots is not seconds or metres lost. Replay links are invitations to inspect evidence, not verdicts. [pipeline/historical_analysis.py:L648-L688]

If missingness or eligibility tracks difficult conditions, the historical cohort can describe an easier subset. If trends are unstable, suppression protects interpretation but does not solve weather prediction. Self-test: explain why a 0-degree direction value is different from unavailable; why 100 manoeuvres from two races are not 100 independent races; and why the PR1 net change can disagree with slope. Read tactical window and slope functions, then index cohort aggregation, then the debrief selection routine.

## 12 Three complete evidence journeys

### Learning objectives

Follow a real observation through reconstruction, historical analysis, forecast availability, and UI interpretation. Distinguish a missing observation from a negative finding. These case studies use actual reviewed exports; their numerical values are not synthetic.

### Case A PR1 fleet richness and source conflict

`naples_pr1` is Practice Race 1 at Naples on 22 September 2026. It has nine replayed boats, 19,488 synchronized frames, four course legs, six modeled contact incidents, and 1,722 active official-wind samples in historical analysis. The compact review finds 28 pairwise historical records, representing eligible overlapping boat pairs, not all nine choose two combinations. GBR B has no valid active racing window and is absent from eligible pairwise comparisons. FRA, NZL G, ITA B, USA, ITA G, and GBR G have reconstructed ranked results. NZL B and SUI are DNF with three completed legs; GBR B is RET with none.

Begin with FRA's supported motion. Ingestion projects measured GNSS and synchronizes it with heading, SOG, COG, and wind. Reconstruction places the bow forward of GNSS, uses source timing and fallback geometry, and obtains start crossing 0.436 s after the gun. Leg 1 ends 233.391 s after that crossing. Historical analysis integrates accepted intervals and yields distance 3216.7044 m, mean SOG 26.73817 kt, course VMG 18.73453 kt, wind VMG 16.15098 kt, and geometric route ratio 0.701979. All those leg scalars have derived quality and 233.391 s source coverage, except elapsed time's reconstructed quality. The unequal VMG values are expected because configured course direction and local wind direction differ.

Next follow the performance comparison. FRA's leg 1 course VMG divided by its six-peer mean gives 119.01656. Leg 3 gives 101.62200. Equal weighting yields the 110.31928 upwind index. That score is available because these completed legs and peers pass coverage and source-state checks. FRA's overall performance scope matches all four expected legs with 1059.119 source-covered seconds. Its reconstructed elapsed result is 1059.555 s from the gun. These two durations differ because scope sums source-covered active intervals and the result is gun-to-finish timing; neither should overwrite the other.

The UI journey is: choose PR1 in the library, select FRA, open Analysis, select the upwind VMG dimension, expand legs 1 and 3, inspect peers, and review a leg interval in Replay. Reports' summary and performance CSVs expose the same canonical metrics. A prose claim about FRA should survive comparison with that evidence table. A separate Compare view can show physical separation or continuous progress at an instant, but those values cannot replace the historical leg denominator.

PR1 also demonstrates disagreement between evidence layers. USA has four reconstructed completed legs and a derived whole-race SOG around 26.72399 kt. Yet all nested source start states are false while a crossing is reconstructed. Historical analysis preserves the source conflict and performance excludes USA both as subject and peer. The correct conclusion is not that every USA number is false, nor that the conflict is harmless because the line appears crossed. It is that a source-state adjudication is needed before making a clean performance comparison. [pipeline/historical_analysis.py:L755-L759] [pipeline/historical_analysis.py:L425-L430]

GBR B's late replay track is held after the source ends and its active metrics are unavailable. NZL B and SUI can still contribute supported completed legs, although their race metrics remain partial and no finish elapsed time exists. Six virtual contacts are geometric incident records, not six official infringements.

The forecast artifact offers a separate lesson. Its pre-race output is `estimated`. Its live publication has 198 states: 84 estimated and 114 gate-ambiguous. Of the latter, 113 carry `start_not_validated` and one `position_uncertainty_exceeds_gate`. Availability changes are evidence gates, not necessarily loading errors. A static available number at one time must not be carried forward through later gate ambiguity. The header labels identity calibration and experimental source timings, so even estimated live probabilities are not established calibrated probabilities. The exact current artifact path is retained in the bounded case companion.

### Case B Match-final winner and incomplete comparison scope

`naples_mr_final` is the Naples match final on 27 September. It contains ITA B and NZL B, six course legs, 15,001 frames, zero modeled contacts, one historical pair record, and 1,284 active official-wind samples. The source audit found no internal boat-stream gaps over two seconds in the original inspected streams. Nevertheless, source timing completeness is a different condition from continuous sensor coverage.

ITA B is reconstructed RANK_1 with gun-to-finish elapsed 1252.050 s. Its first leg lasts 256.620 s, with mean SOG 25.57288 kt, course VMG 18.25831 kt, wind VMG 18.15258 kt, and distance 3388.4459 m. The first crossing is 0.530 s after the gun. The close course/wind VMGs here indicate similar target axes during the accepted interval; they do not prove identical wind everywhere.

ITA B's upwind index is 101.62943, the equal-leg mean of 102.81711 on leg 1 and 100.44175 on leg 3. There is exactly one peer, NZL B. All six performance dimensions are available, but scope matches only legs 1-4 of six and 847.085 covered seconds. Leg 5 is excluded for missing/incomplete crossing and leg 6 for missing previous crossing. A recorded final-gate timestamp can support a finish while an absent intermediate checkpoint prevents forming a completed leg interval. This is why winner status and complete analytical coverage are separate claims.

The UI journey is to select the match final and ITA B, open its profile, read scope before interpreting the radar, then inspect excluded leg reasons. Switching to a single leg changes the evidence scope. It does not fabricate missing leg 5 by subtracting an estimated time from the finish. A two-boat peer baseline is transparent but context-specific; it cannot establish superiority over the entire fleet or intrinsic talent.

The actual live forecast has 136 published states: 133 estimated and three unavailable. The unavailable reason says the first received finish is not a globally resolved first finisher. This correctly distinguishes local information about a finish from global resolution of the winner. The pre-race expected positions are approximately 1.38508 for ITA B and 1.62262 for NZL B under nonfinish score N. They do not sum to exactly 3 because this score includes nonfinish probability; they are not simply a probability vector dressed as ranks. The forecasting chapters derive that convention.

### Case C A window that ends before its gun

`26_09_23_nap_ipr_pr1` is a Naples practice session dated 23 September. It contains nine replayed boats and 5,411 frames. Exported window end is 1790165761000 ms and gun is 1790166120000 ms. The difference is (1790166120000 - 1790165761000)/1000 = 359 s. The observed replay ends 5 min 59 s before the source gun. There is no post-gun race interval in these records.

Historical analysis accordingly has no completed legs, no valid active performance, no pair records, and no active wind summary. Tactical insights has an empty snapshot grid with an explicit reason. Every boat's eleven summary metrics reported by the snapshot tool are unavailable. A UI that displays an empty chart with a reason is communicating the evidence accurately. Filling the chart with zeros would falsely suggest nine boats raced without speed or distance.

The reconstructed status labels include RET and DNF, but the key scientific conclusion is limited observation, not a complete account of the event after the window ends. The source does not let this pack decide what happened later. A pre-race forecast can nevertheless be estimated from prior history: the publication contains pre-race expectations while its live state list is empty. Prediction before an event and observation of the event are different data problems.

The user journey is to select the session, notice the replay window relative to the gun, open Analysis to read missing reasons, and open Forecast to distinguish prior expectation from absent live evidence. In Reports, an artifact's existence means an export was produced, not that every quantity inside it is available. Do not count this session's thousands of prestart frames as a successfully observed race outcome for model evaluation.

### What to carry across all three cases

Richness is multidimensional: track continuity, checkpoint completeness, source-state consistency, field membership, and model support can vary independently. A fixed rule saying 'use the richest race' hides these differences. Instead, begin each claim by naming target and window; follow the source and transformation; read coverage and exclusion reasons; state what would change the conclusion.

Self-test: defend these three statements without a running dashboard. FRA has a strong observed PR1 upwind comparison; ITA B's match win does not imply six-leg profile coverage; the pregun session has a prior forecast but no observed race performance. Then challenge each statement with the strongest relevant limitation. Use `evidence/data_metrics_review.json`, selected source modules, and the relevant exported field names as the reading route. No complete telemetry array is needed to make the argument.
