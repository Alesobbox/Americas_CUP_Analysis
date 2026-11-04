# Part VI How the application turns evidence into an interface

## Chapter 20 Shared context and the meaning of a screen

**Learning objectives.** Explain which state belongs to the whole application; trace a selected boat to the values displayed beside the course; distinguish a retrospective aggregate from an instantaneous reading; identify the protections against a result arriving for the wrong race.

### Begin with one race and one clock

A useful first model of the application is a desk with several documents about one race. The Replay view is the animated chart on the desk. Analysis is the retrospective dossier. Compare places two boats at the same moment beside one another. Reports provides canonical tables and the underlying files. Forecast asks three separate questions about outcomes. Changing the document does not create a different race or an independent replay clock.

`App` owns the selected replay, current frame, playback state, primary boat A, comparison boat B, visibility filter, active workspace and course-display settings. It passes these down as values and callbacks. The five views are conditional children of `TacticalDashboard`, which receives the same replay and frame. Replay and Compare therefore agree about time because they receive one parent-owned frame, not because they happen to synchronize separate clocks. Forecast's live card receives that same playhead. Its pre-race conditions and Cup assumptions have different meanings and do not advance with the replay. [src/App.tsx:L24-L53] [src/components/dashboard/TacticalDashboard.tsx:L76-L113]

This distinction matters when explaining the project. “The selected boat is ITA G at 240 seconds after the gun” is a context for a replay reading. “ITA G has a downwind course-VMG index near 110 on its eligible matching completed legs” is a retrospective comparison over exported intervals. A single selection connects the two; it does not make their denominators equal. Selecting a different playhead changes instantaneous SOG. It does not recalculate a historical all-leg index from the fragment currently visible on the course.

The initial boat choice is a temporary convenience. Competitors are sorted by team code and the first two supply A and B. This is not an inferred favorite, a forecast ranking or a performance recommendation. Changing race clears the old frame and replay, pauses playback, resets review intervals and visibility, then chooses defaults from the newly loaded competitor list. Selecting A later does not silently choose a new B. An explicit comparison selection enables B's highlighting. [src/App.tsx:L68-L85] [src/App.tsx:L120-L139] [src/App.tsx:L189-L202]

The visibility filter is another kind of state. It can restrict the course and telemetry traces to one boat, but the race leaderboard continues to represent the complete replay field. Trail scope is independent: “Highlighted boats” selects trails for A plus explicitly highlighted B, while “No trails” removes track history without removing the yachts. Do not infer that an absent trail means absent telemetry, disqualification or a smaller forecast field. [src/components/dashboard/TacticalDashboard.tsx:L87-L108] [src/components/canvas/boatPresentation.ts:L62-L66] [src/components/canvas/DynamicVesselLayer.ts:L549-L613]

### From wall time to a replay frame

The replay clock uses browser animation callbacks. Let t be replay time in milliseconds, delta_w the elapsed browser wall time since the preceding callback, and s the chosen playback-speed multiplier. While playing, the engine updates

`t_new = min(window_end, t_old + s * delta_w)`.

The first callback establishes the wall-time reference rather than inventing an initial elapsed interval. Pausing cancels the scheduled callback and clears that reference. A seek clamps its input into the exported replay window and emits a new frame immediately. These are clock-adapter operations; they do not reconstruct a race from raw telemetry. [src/engine/ReplayEngine.ts:L25-L36]

To sample a frame, the engine finds the greatest exported timestamp t_i no later than the requested t, using binary search. Between t_i and the next timestamp t_j, its interpolation fraction is

`f = clamp((t - t_i)/(t_j - t_i), 0, 1)`.

At a repeated endpoint, f is zero. Linear channels use `a + f(b-a)`; bearings take the shortest circular route. The browser is smoothing an already synchronized export. It is not recovering a newly measured observation at every animation frame. The raw timestamp-coverage rules that decide historical availability remain Python's responsibility. [src/engine/ReplayEngine.ts:L37-L53] [src/engine/interpolate.ts:L3-L15]

**Worked example using deliberately synthetic data.** Suppose the synchronized export contains x positions 100 m at 1,000 ms and 102 m at 1,100 ms. At a display time of 1,025 ms, f = 25/100 = 0.25, giving x = 100 + 0.25(2) = 100.5 m. Headings of 359 and 1 degrees interpolate through 0 degrees, not through 180 degrees. At 4-times playback, a 16 ms browser interval advances the replay by 64 ms. None of these arithmetic steps increases the number of independent source observations.

The sampled `leg` field deserves care. `sampleBoat` linearly interpolates the exported leg numbers and rounds to the nearest integer. At the display level, the leg can therefore change around the middle of a replay interval. A reconstructed crossing timestamp in the event feed remains the appropriate reference for a historical checkpoint. Do not use the precise instant a rounded display label changes as an independent crossing measurement. [src/engine/interpolate.ts:L12-L15]

### Loading only the required evidence

The catalog is small routing metadata. Loading a race fetches its replay file and checks the race ID, competitor list, timestamps and required column lengths. It does not validate every scientific assumption in the export. Catalog parsing accepts both the present grouped `regattas` structure and an older flat `races` form; path restrictions confine the replay files to the expected family. This is an explicit compatibility path, not evidence that old and new schemas are identical. [src/engine/catalog.ts:L8-L46]

Documentation describes lazy analysis loading, but the executable detail is more specific: `App` fetches one analysis detail whenever the selected replay changes, even while Replay is open. That detail supplies tactical insights, events and Reports. Opening Analysis additionally loads the historical index and uses its own per-race detail cache. The application avoids loading all replay arrays up front, but “only after opening Analysis” would be an inaccurate description of current behavior. [src/App.tsx:L87-L94] [src/components/modals/AnalysisModal.tsx:L270-L298]

Race changes abort the preceding replay request. Each asynchronous continuation checks whether its controller was aborted before publishing state. The selected-race analysis request has the same check and clears its previous value first. Analysis clears an old detail while a new one loads, caches successful details by race ID, and exposes a loading or error state. These protections implement a simple invariant: a response about race X must not overwrite a screen that has moved to race Y. The use of an ID guard in Reports provides another barrier: a detail is accepted only if `analysisDetail.race.id === replay.id`. [src/App.tsx:L87-L94] [src/App.tsx:L120-L139] [src/components/modals/AnalysisModal.tsx:L278-L298] [src/components/dashboard/ReportsWorkspace.tsx:L39-L64]

There is a tradeoff in error presentation. `App` deliberately swallows failure of the optional analysis-detail request, preserving replay operation. Reports then says that matching historical analysis is unavailable or still loading; it does not borrow a legacy average to fill the cell. Analysis's own loader can show a specific detail error. A future improvement could preserve the optional-load failure reason for Reports and tactical panels. This is an operational diagnosis, not a claim that the current screen fabricates a value. [src/App.tsx:L89-L93] [src/components/dashboard/ReportsWorkspace.tsx:L19-L22] [src/components/dashboard/ReportsWorkspace.tsx:L43-L69]

### Journey one Selecting a boat

1. Click a course label, a fleet row or a selected-boat control. Course labels call `onSelectBoat(label.id)`; the fleet table retains every competitor.
2. The callback in `App` updates `selectedId`. If a one-boat visibility filter is active, its ID follows the new A, keeping the selection visible. The callback does not replace `comparisonId`.
3. `TacticalDashboard` resolves A from the current replay's competitors, passes its ID to the KPI card, telemetry workspace and course, and passes the actual competitor record to Compare.
4. The KPI card and comparison receive the current frame. Historical panels resolve the same boat ID inside the matching analysis export. Forecast can select the same A, but probabilities still use their own complete field.
5. Follow the value to its evidence: instantaneous x, y, SOG and angles come from sampled replay columns; a historical mean or performance index comes from the analysis detail. The fact that the UI highlights both in blue does not merge their evidence classes. [src/components/canvas/CourseCanvas.tsx:L486-L510] [src/components/canvas/CourseCanvas.tsx:L579-L581] [src/App.tsx:L180-L205] [src/components/dashboard/TacticalDashboard.tsx:L76-L113]

**If an assumption failed.** A stale race response without cancellation could make a valid-looking number belong to the wrong field. A shared selection that silently replaced B would make comparisons change meaning after every A click. Current abort guards and explicit A/B callbacks address these engineering risks; they cannot establish that a source boat's identity mapping is historically correct.

**Common mistakes.** Treating a default alphabetical selection as a ranking; equating “visible boats” with scheduled entrants; treating smooth motion as source sampling frequency; expecting the historical report to change as the playhead moves.

**Self-test.** Explain why pausing Replay also stops Compare's moment-to-moment readings. Which object would you inspect to prove that a historical value belongs to the selected race? Why can a displayed leg transition differ slightly from an exported event time?

**Source-reading route.** Read `App` state and callbacks, `TacticalDashboard` workspace wiring, `ReplayEngine`, `interpolate`, then the catalog validators. The compact route is [src/App.tsx:L24-L53], [src/App.tsx:L120-L155], [src/components/dashboard/TacticalDashboard.tsx:L76-L113], [src/engine/ReplayEngine.ts:L25-L84], [src/engine/catalog.ts:L27-L46].

## Chapter 21 Drawing metres on a screen

**Learning objectives.** Derive the Grid transform; explain how Map mode aligns a Canvas overlay; distinguish physical geometry, enlarged display geometry and screen-space labels; explain which parts remain useful when tiles cannot load.

### A boat has a position before it has a pixel

The exported replay uses local projected coordinates in metres. This is the world in which distances, boundaries and contact polygons make sense. A screen position adds a camera choice: its center, rotation, scale and pixel dimensions. Moving the camera changes a boat's pixels but should not change its physical separation from another boat. Enlarging a boat for visibility should not change whether the metre-space envelopes overlap.

Grid mode applies this idea directly. Write world coordinates as p = (x,y), camera center as c = (c_x,c_y), screen width and height as W,H, scale k in pixels per metre, and rotation angle theta in radians. Define dx = x-c_x and dy = y-c_y. The implemented transform is

`X = W/2 + k(cos(theta) dx - sin(theta) dy)`

`Y = H/2 - k(sin(theta) dx + cos(theta) dy)`.

The minus sign in the second equation converts north/up into a screen coordinate that grows downward. The origin of screen coordinates is the upper left. In North mode theta = 0; in Course mode it is the exported course-axis angle. The inverse first removes the screen translation and scale, reverses the screen-y sign, then applies the inverse rotation. [src/components/canvas/ViewportMatrix.ts:L3-L22]

**Worked example using deliberately synthetic coordinates.** Let W = 800 px, H = 600 px, camera center = (1000,2000) m and k = 0.2 px/m. A boat at (1100,2050) m has dx = 100 m, dy = 50 m. With theta = 0, X = 400+20 = 420 px and Y = 300-10 = 290 px. At theta = 90 degrees, X = 400-10 = 390 px and Y = 300-20 = 280 px. In either view, its displacement from the center has length sqrt(100^2+50^2) = 111.80 m, represented by 22.36 px. Rotation changes direction, not length.

The same inverse transform supports panning and hit testing. Dragging converts the original and current pointer positions to world coordinates and shifts the center by their difference. Selection finds a nearby vessel and uses a threshold corresponding to a pixel radius divided by viewport scale. The clickable target is a usability choice; it is not the hull or contact envelope. [src/components/canvas/CourseCanvas.tsx:L402-L438] [src/components/canvas/CourseCanvas.tsx:L445-L482]

Fitting the course is also geometry. `fitViewport` rotates the polygon at unit scale, measures its screen-aligned extents and chooses the smaller of the width and height scale limits, with padding. `fitViewportWithBottomClearance` fits into the available region above an overlay and shifts the center accordingly. A full-course fit can make an actual AC40 extremely small. This is the reason, inferred from the code and visual requirement, for an explicit enhanced rendering mode. It is not evidence that larger screen yachts are more capable or more dangerous. [src/components/canvas/ViewportMatrix.ts:L24-L47]

### Map mode and three anchors

Map mode adds a geographic surface supplied by MapLibre. The browser converts local metres back to longitude and latitude with the race's origin and projection coefficients:

`longitude = origin_longitude + x/k_lon`

`latitude = origin_latitude + y/k_lat`.

The order returned is longitude first, latitude second, matching MapLibre and GeoJSON conventions. Swapping the two is not a harmless formatting change: it maps the course to another place. The coefficients are exported by the pipeline; the browser does not choose a new geographic origin. [src/utils/geoProjection.ts:L44-L77]

To align Canvas with the map camera, `computeAffineScreenTransform` samples the projected screen location of three world anchors: (0,0), (D,0), and (0,D), with D normally 1000 m. Their differences give the two columns of a 2-by-2 matrix A, while the origin anchor supplies translation b. Thus `screen = A * world + b`. A point uses both A and b; a displacement vector uses only A. The determinant supports the inverse transform. A nearly singular transform returns a defensive fallback rather than dividing by an unstable determinant. [src/utils/geoProjection.ts:L80-L174]

This affine approximation is appropriate to the flat, unpitched course overlay used here. A comment in the helper asserts subpixel accuracy; that should be read within the tested geometry and camera assumptions, not as a universal theorem about arbitrary map pitches or global geographic spans. The map is created with pitch zero. Source and stress tests of the transform are more relevant evidence than repeating the comment as a general guarantee. [src/components/canvas/CourseCanvas.tsx:L185-L197] [src/utils/geoProjectionStress.test.ts:L1-L24]

The camera has a continuity requirement when switching Map and Grid. On entry to Map after a camera has been established, the code converts the current metric center back to geographic coordinates and derives the map zoom adjustment from the ratio of desired pixels per metre to actual map scale. It adds `log2(desired_scale/current_scale)` to map zoom. A doubling of scale therefore adds one zoom unit. This avoids restoring an old Map zoom that no longer represents the user's Grid zoom. Map movement, rotation and resize resample the transform and update the shared viewport. [src/components/canvas/CourseCanvas.tsx:L170-L255]

### Physical size and enhanced size

The AC40 model specifies a total length of 13.178 m, including a forward extent of 12.963 m and 0.215 m aft, plus a foil half-span of 5.415 m. Enhanced rendering has a minimum 22 px total length. If k is the camera scale, the yacht render scale is

`k_render = max(k, 22/13.178)` for this AC40 enhanced display,

while True mode uses `k_render = k`. The minimum is approximately 1.66945 px/m. At k = 0.1 px/m, the true model length is 1.3178 px; enhanced mode makes it 22 px. These are the repository's modeled display dimensions, not measurements of every asset in the archive. [src/components/canvas/boatModels.ts:L22-L35] [src/components/canvas/boatModels.ts:L208-L230]

The hull, foils and displayed safety borders share the same render scale. `projectSafetyBorderToScreen` scales each border displacement from the vessel anchor consistently with the yacht model. The contact detector continues to transform metre-space envelopes using the boat heading and test their overlap. It does not receive the enhanced pixel scale as a physical input. Hence changing Enhanced to True can change how close the vessels look without changing a contact result. A virtual contact remains a modeled geometric overlap, not an umpire's ruling. [src/components/canvas/DynamicVesselLayer.ts:L360-L372] [src/components/canvas/DynamicVesselLayer.ts:L438-L476] [src/engine/contactDetector.ts:L71-L118] [src/engine/contactDetector.ts:L309-L369]

Labels constitute a third space. A label is a rectangular screen object attached to a vessel anchor by a leader line. The layout function tries candidate offsets, penalizes overlap with previously placed labels, course labels, vessel anchors and a reserved HUD region, then uses a grid fallback for crowded fleets. Primary A receives higher placement priority than other boats. Only label rectangles move; world positions do not. This solves readability by displacing text rather than by moving the evidence. As a greedy finite-candidate procedure, it should not be interpreted as proving a globally optimal label layout for every conceivable viewport. [src/components/canvas/boatPresentation.ts:L13-L59] [src/components/canvas/CourseCanvas.tsx:L486-L510]

### What remains offline

In Grid mode the map is not mounted. The static layer draws the water background, world-anchored grid and active boundary polygons; the dynamic layer adds yachts, marks, tracks and course geometry. It has no need to request map tiles. In Map mode a tile failure can activate the Grid fallback and display a visible “Map tiles offline” status. Geographic imagery and course evidence have different availability: losing a geographic background does not erase exported coordinates. [src/components/canvas/CourseCanvas.tsx:L170-L172] [src/components/canvas/CourseCanvas.tsx:L257-L268] [src/components/canvas/CourseCanvas.tsx:L543-L586]

The optional running dashboard still needs its JavaScript, fonts and data served locally. This study pack's HTML is a different product: it is authored to open as local files without that server. Opening a static textbook does not create a Vite service or a Python process.

**If an assumption failed.** A missing or wrong projection origin would misalign yachts with geography while a Grid view could still look internally plausible. A contact calculation that reused enhanced pixels would turn a display preference into false collisions. A stale camera zoom would cause a visible jump during view changes. Use round-trip transform tests, independent metre-space contact checks and browser continuity checks to distinguish these cases.

**Common mistakes.** Reading a label's rectangle as the yacht's exact location; measuring enhanced boat lengths against the grid; treating a missing map tile as missing telemetry; assuming a contact is an official penalty; quoting an affine helper's comment as a worldwide accuracy guarantee.

**Self-test.** Why is translation absent when transforming a velocity vector? At 0.1 px/m, what is an AC40's true displayed length? Which code would have to change before Enhanced mode could alter a physical contact? Explain why Grid can operate without an OSM tile request.

**Source-reading route.** Start with [src/components/canvas/ViewportMatrix.ts:L3-L47], then [src/utils/geoProjection.ts:L44-L174], [src/components/canvas/CourseCanvas.tsx:L170-L277], [src/components/canvas/boatModels.ts:L208-L230], [src/components/canvas/DynamicVesselLayer.ts:L360-L476], and [src/components/canvas/boatPresentation.ts:L13-L66].

## Chapter 22 Inspecting a claim and returning to its evidence

**Learning objectives.** Trace a scope change without recomputing a metric; follow a debrief item back to an exported time; explain why Reports keeps a missing metric unavailable; use an artifact index without confusing current and retained objects.

### The graph is a selector over an export

The performance chart can display all comparable legs or a selected leg. Its `performanceView` function implements that switch by selecting a Python-exported `leg_evidence` entry. If none exists, it returns null values and an exclusion reason. It does not average replay samples, reconstruct peer eligibility or divide the displayed aggregate raw means to manufacture an index. The difference rows calculate only a presentation difference, exported index minus 100. Their shared display scale is selected from the race's exported values. [src/components/dashboard/BoatPerformanceRadar.tsx:L18-L35] [src/components/dashboard/BoatPerformanceRadar.tsx:L49-L66]

This is the ownership boundary in a form the user can inspect. Python owns which boats and legs qualify and how their ratios are averaged. TypeScript owns which of those valid exported records is selected, how a null is explained and how the score is drawn. Display arithmetic such as “110 is 10 above 100” is not a second implementation of the performance formula.

### Journey two Changing leg scope

1. In Analysis, choose a race and boat, then select a dimension such as downwind course VMG.
2. Change the “Performance leg scope” control from all comparable legs to a numbered leg. The component stores scope alongside a context string containing the race and boat IDs.
3. `performanceView` finds that exact leg in each axis's exported evidence. A nonapplicable or excluded axis stays unavailable, even if another leg has a number.
4. The evidence panel shows own value, other-boats mean, exported index, peer count, coverage, observation count and matched leg. It explicitly warns that the all-leg aggregate is a mean of per-leg ratios; its arithmetic need not equal the ratio of aggregate raw means.
5. Expand the contributing leg to see named peers, intervals, exclusions and qualifying manoeuvre events. “Review leg” passes the exported start and end together with race and boat IDs to replay navigation. [src/components/dashboard/BoatPerformanceRadar.tsx:L36-L78] [src/components/dashboard/BoatPerformanceRadar.tsx:L105-L115]

**Worked example using deliberately synthetic export values.** Suppose one axis has leg indexes 120 and 100, giving all-comparable index 110. Selecting leg 2 must show 100, its own coverage and its peer list. If a tack-retention axis has no eligible event on that leg, it stays null. It must not inherit the all-leg retention score or become zero. The exercise is about selecting evidence; the production eligibility formula is explained in Part IV.

Race/boat context protects the inspector from retaining a nonsensical scope when the selected yacht changes. `AnalysisModal` also keys the radar by race and boat. A useful diagnostic is to inspect the new context before blaming a formula when a leg selection disappears. [src/components/dashboard/BoatPerformanceRadar.tsx:L40-L44] [src/components/modals/AnalysisModal.tsx:L180-L184]

### Journey three Following a debrief replay link

A debrief item is a retrospective review priority, not a causal verdict. The producer has already chosen an observed leg-time deficit or detected speed-loss episode and exported its value, units, source, quality and timestamp. `TeamDebrief` prints those fields and sends `raceId` and `item.timestamp_ms` to `onOpenReplay`. It does not detect a new manoeuvre or infer “bad tactics” in the browser. [src/components/dashboard/TeamDebrief.tsx:L4-L20]

`App.openAnalysisReplay` resolves the race against the trusted catalog. It switches the active view to Replay and pauses the current engine. For the same race it seeks immediately. For another race it stores a pending seek and starts a race load; once the new engine exists, that pending timestamp is applied. A supported boat ID and interval can accompany a performance-leg review, in which case A and the visible filter are updated appropriately and the interval banner retains the exported limits. A simple debrief moment carries a timestamp only; it does not claim to supply a complete causal-analysis interval. [src/App.tsx:L98-L106] [src/App.tsx:L141-L155]

Seeking clamps to the replay window. Thus navigation cannot display data outside the available export merely because an item contains an extreme timestamp. The correct conclusion on returning to a debrief moment is “this is the recorded/reconstructed context worth inspecting.” It is not “the link proves this action cost exactly that much time.” Wind, traffic, timing, coverage and alternatives remain interpretation questions.

### Playhead-aware insights and events

Tactical insights select the latest exported snapshot no later than the playhead, using binary search. They reject a mismatched race, nonfinite time, a missing earlier snapshot or a stale snapshot. They also check that the snapshot window ends no later than the displayed time. Expiry uses the exported maximum age. The panel prints independent direction and speed coverage and reasons. This supports retrospective measurement-time causality while preserving the important limitation that original arrival-time ordering is unavailable. [src/components/dashboard/TacticalInsightsPanel.tsx:L4-L23] [src/components/dashboard/TacticalInsightsPanel.tsx:L27-L44]

Timeline and event-list behavior use the same optional historical event feed supplied through `analysisDetail`. Rewinding should change which result states and events have been reached, not reveal a future final classification as a current on-water fact. The shared frame timestamp is the reference. The historical Analysis report remains retrospective and can legitimately show the end-of-race result. A causal replay screen and a retrospective report should not be forced to have identical visibility rules.

### Journey four Opening a report artifact

Reports first accepts only matching historical analysis, then looks up each competitor's canonical metrics. It displays null values as unavailable with reasons. The replay's older `competitor.summary` is deliberately not a fallback. This avoids printing an apparently complete number with a different racing window, weighting or source-coverage rule. The output is a table of the canonical historical meanings, not merely whatever value happens to exist in the replay. [src/components/dashboard/ReportsWorkspace.tsx:L19-L25] [src/components/dashboard/ReportsWorkspace.tsx:L43-L69]

Separately, Reports loads `/data/artifacts.json`, checks its recognized schema and artifact fields, then separates curated current-race downloads from the complete explorer. The primary group selects `race_id`, `primary_download` and `status === current`; the technical explorer can search all published files and retained forecasts. Status metadata comes from the inventory producer, not from a browser guess based on filename recency. [src/components/dashboard/ReportsWorkspace.tsx:L8-L17] [src/components/dashboard/ReportsWorkspace.tsx:L44-L60]

Choosing a Download link retrieves the published object at its inventory URL. Choosing an Open workspace button navigates to the object's race and indicated view. These are distinct actions. The archive explorer retains old immutable versions so an old source reference remains meaningful, but a retained object is not automatically the active forecast. An analysis JSON contains metrics, definitions, coverage and optional extensions; the summary and performance CSVs reorganize canonical exported values for a spreadsheet. A replay JSON instead contains the large synchronized telemetry columns. [src/components/dashboard/ReportsWorkspace.tsx:L70-L83] [scripts/build_report_exports.py:L35-L71]

**If an assumption failed.** If a graph recomputed indexes from its rounded means, it could disagree with the exported mean of ratios. If Reports substituted a replay average, a gap could quietly change the denominator. If an artifact explorer hid all retained versions, a historical forecast reference could become impossible to trace. The current selector/export boundary and inventory status system address these risks.

**Common mistakes.** Treating an unavailable leg as zero; reading a debrief item as proof of tactical causation; assuming all displayed timestamps are measured gate crossings; opening a retained forecast and calling it current; using a CSV without carrying along its unit and reason columns.

**Self-test.** Explain what changes when a leg scope changes, and name three things that do not get recalculated. What does a debrief link prove? Why is it safer for Reports to show “Unavailable” than to use `summary.avg_speed_kt`? Which artifact metadata tells you that an object is retained?

**Source-reading route.** Read [src/components/dashboard/BoatPerformanceRadar.tsx:L18-L25], [src/components/dashboard/BoatPerformanceRadar.tsx:L105-L115], [src/components/dashboard/TeamDebrief.tsx:L4-L20], [src/App.tsx:L141-L155], [src/components/dashboard/TacticalInsightsPanel.tsx:L4-L23], and [src/components/dashboard/ReportsWorkspace.tsx:L39-L83].

## Chapter 23 Exact forecast requests and the boundary of static hosting

**Learning objectives.** Trace an exact custom request from a form to Python and back; distinguish browser cancellation from server termination; explain the workspace publication lock; recognize integrity checks and recoverable failure states.

### A published answer and a request to calculate one

The Forecast workspace normally reads immutable JSON. The index points to the active race forecast and Cup publication and can list exact pre-race condition presets. A browser can display these with static hosting. Creating a new exact custom scenario requires a local service, a prepared forecasting dataset and an appropriate Python environment. The model is not trained in the browser. [src/components/dashboard/ForecastWorkspace.tsx:L136-L161] [scripts/forecastScenarios.ts:L91-L99]

Inputs are exact numbers: race ID, true-wind speed in knots and direction offset in degrees. The form accepts wind speeds from 0 to 80 kt and offsets from -180 to +180 degrees as numeric domain checks. The current service additionally rejects every nonzero direction offset because a direction response has not passed validation. A visible “Use 0 degrees offset” action requires the user to change that condition; the service does not silently rewrite it. Passing these syntax/range checks is not the same as having sufficient historical support. A valid exact request can produce an explicit unavailable artifact. [src/components/dashboard/ForecastWorkspace.tsx:L119-L124] [src/components/dashboard/ForecastWorkspace.tsx:L209-L210] [scripts/forecastScenarios.ts:L70-L78]

### Journey five Requesting an exact custom forecast

1. Select the pre-race question, choose entered conditions, and enter a speed and zero direction offset. The browser checks the local service's readiness and searches the index for an exact preset.
2. On Generate, `ForecastWorkspace` snapshots the current race and input values, creates an abort controller, and records a generation key containing race/speed/offset. A change of conditions clears a running display belonging to the old key and aborts its browser request lifecycle.
3. `prepareScenario` POSTs JSON to `/api/forecast-scenarios`. Every returned job must have a valid ID/status, the identical input triple and, on completion, an immutable `scenarios/<64 hex>.json` path.
4. While queued or running, the client reports progress and polls the job every 750 ms. Aborting cancels the timer/fetch cycle. A failed job returns a reason suitable for retry.
5. On completion the browser reloads the index, finds the exact preset again and requires its path to equal the completed job's path. It then loads and validates that object with the intended race, class, field, model/source references, pre-race scope and exact conditions. Only after those checks does it publish the result into the current keyed display. [src/components/dashboard/ForecastWorkspace.tsx:L126-L183] [src/engine/forecastScenarios.ts:L20-L42]

**Worked example using synthetic requests.** Imagine a request for race R at 13.25 kt and 0 degrees. A completed job for 13 kt is invalid even if it looks close. A completed job for the right wind but a different race is also invalid. If the user changes the input to 14 kt while the 13.25 kt job runs, the old completion must not appear as the answer to 14 kt. The key, abort guards and fresh-index equality check exist to preserve this semantic invariant. They do not imply that 13.25 kt necessarily produces different expected positions from 13 kt: the active zero-effect wind reference can yield identical expectations at supported speeds.

### A single publisher in a shared workspace

The server route is restricted to localhost-style hosts and same-origin requests. It rejects unexpected keys, unsafe race IDs, invalid numeric values, unsupported direction offsets, overly large bodies, missing index data and races absent from the publication index. If the same exact job is already running, it returns that job. A competing input receives a busy response rather than starting another writer. An already published exact preset can be reused. [scripts/forecastScenarios.ts:L141-L188]

In-memory job ownership alone would be insufficient if a development server and a preview server shared the repository. The middleware therefore acquires `.forecast/scenario-generation.lock` using exclusive file creation. Its record contains a token and server process ID. Before Python may publish, the parent writes the child's process ID durably and acknowledges a start handshake through standard input. If the server disappears while a publisher child remains alive, another service must not steal that lock. Recovery requires both server and publisher to have exited; release checks the token so one job cannot remove another job's lock. [scripts/forecastScenarios.ts:L24-L67] [scripts/forecastScenarios.ts:L81-L107]

The Python child uses separate validated arguments with `shell: false`. A ten-minute timeout and a child watchdog limit a stuck operation. Error output is bounded and translated into user-facing distinctions such as stale local forecasting data, inability to start the service or timeout. This design makes the operation concrete and recoverable without exposing internal implementation text in every product message. It is software-operation evidence, not empirical forecast validation. [scripts/forecastScenarios.ts:L91-L127]

Canceling a browser request does not, by itself, prove that an already launched Python publisher has stopped. The workspace lock remains the authority for competing generation. The UI can abandon its old waiting state while the server continues safely. A retry may attach to the same running exact input, reuse a completed publication, or receive a busy response for another input. This explains why deleting lock files manually is a poor first troubleshooting step: a living child may still own publication.

### Reading bytes rather than trusting a name

`predictionCatalog.readJson` recognizes a content hash in an immutable filename, obtains the response as text and strips one optional platform newline. It hashes the exact UTF-8 canonical body rather than parsing and reserializing JSON, because Python escaping and serialization choices would otherwise change bytes. A mismatch makes the forecast unavailable. The parsed header is then checked against expected model, source and scenario references and the selected race context. A valid hash proves identity with the named content, not truth of its assumptions or calibration. [src/engine/predictionCatalog.ts:L14-L43] [src/engine/predictionCatalog.ts:L70-L124]

Generated JSON is served independently of Vite's watched public-file inventory. The middleware reads each request with closed file handles, uses JSON responses for missing files, rejects traversal, and disables caching for the index and generated objects. It is wired into both development and local preview. The Vite watcher excludes forecast/environment folders to avoid Windows handles blocking atomic publication replacement. A plain static server has none of this generation service, although it can still serve already copied public objects. [scripts/forecastArtifacts.ts:L7-L78] [vite.config.ts:L1-L18]

**If an assumption failed.** A nearby-preset fallback could answer a question the user never asked. A stale response could label old conditions as new. An untracked publisher child could race another publication after the server dies. Hashing reserialized JSON could reject correct bytes or miss the intended identity contract. The exact-match, keyed-display, child-ownership and byte-hash checks each address a separate failure mode.

**Common mistakes.** Treating job completion as forecast accuracy; expecting static HTML to start Python; assuming changing the form cancels the server process; deleting a lock while its child is alive; interpreting a hash as a certificate of scientific validity; treating unsupported direction as zero without an explicit input change.

**Self-test.** Name the checks between a completed job and a visible expected position. Why does the lock record a child process as well as the server? What can work on static hosting? Why do two supported wind speeds sometimes give identical positions? What evidence would you need before claiming that exact scenario generation improves prediction?

**Source-reading route.** Follow [src/components/dashboard/ForecastWorkspace.tsx:L119-L183], [src/engine/forecastScenarios.ts:L6-L42], [scripts/forecastScenarios.ts:L24-L127], [scripts/forecastScenarios.ts:L141-L196], [src/engine/predictionCatalog.ts:L14-L43], and [scripts/forecastArtifacts.ts:L66-L78]. For test interpretation, compare the executable service cases in `forecastScenarioService.test.ts` with browser interaction tests and with source-text wiring checks; they answer different questions.
