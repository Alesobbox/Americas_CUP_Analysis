# Google Store-inspired UI redesign plan

Status: approved plan, implemented 3 November 2026. See [implementation and verification](ui_redesign_verification.md) for the delivered interface, checks, and data reconciliation. The original design specifications below distinguish proposed project values from observed reference-site details.

## 1. Design objective

Give the project the visual discipline of the exact [Google Store Italy homepage](https://store.google.com/it/?hl=it) supplied by the user: clear hierarchy, confident typography, generous space, excellent imagery, carefully composed surfaces, and consistent interactions. Make the sailing archive itself supply the identity: real course geometry, boats, team colors, tracks, and evidence.

The intended experience is a calm, polished race-analysis product. A sailor should immediately see the race, a coach should quickly compare boats, and an analyst should be able to inspect and copy the evidence. Every screen needs an intentional composition appropriate to its task.

Keep Replay as the default and retain Replay, Analysis, Compare, Reports, and Forecast as the five main destinations. Improve the race picker into a visual library within the existing workflow. A new compulsory landing page would add a step to every replay visit and is outside the recommended scope.

The new reference becomes the visual authority when implementation begins. Rewrite the older Naples-reference composition in `docs/design-system.md` at that stage. Existing data and interaction contracts remain binding.

## 2. Evidence used

### Current project

Read `PROJECT.md`, `docs/dashboard_contract.md`, `docs/design-system.md`, `docs/architecture.md`, and relevant sections of the historical, forecasting, and source-audit documents. Inspect the screen composition, styling, and existing browser checks. Capture all five workspaces at 1440 px width and Replay at 390 px width using the current local application, with Grid selected for a deterministic preview.

The compact archive snapshot currently reports **28 races and 224 replayed boat-races**. Keep these distinct from any scheduled-entry denominator used by forecasting. The current working tree already contains substantial ongoing changes; implementation must start from those changes and preserve them.

### Reference website

Inspect the same Italian homepage with the tracking parameter removed, at 1440 × 1000 and 390 × 844, including its scrolled state. The observed page has a white shell, a large image/video hero, rounded major surfaces, plain navigation, and large sans-serif headings. Product imagery sits on pale tiles with names and supporting information below. Sections vary in scale and spacing. The scrolled header becomes a floating rounded bar with a restrained shadow. Mobile uses a dedicated crop and reorganized navigation. Its computed font stack includes Google Sans Flex.

The numerical design specifications below are **proposed project values**, not a claim that they are Google's exact tokens. The website can change; preserve reference screenshots with the implementation brief.

### Current gaps to resolve

| Current evidence | Consequence | Planned change |
| --- | --- | --- |
| `src/index.css` defines dark global tokens and Chakra Petch; `dashboard.css` defines a light palette and Inter; Analysis bridges legacy tokens locally. | Screens inherit competing visual rules. | Establish one light semantic system and migrate existing aliases deliberately. |
| `docs/design-system.md` specifies 2–4 px radii and an earlier dense Naples composition; current dashboard cards use 10 px radii. | Documentation cannot reliably guide implementation. | Replace the visual specification with the decisions in this plan. |
| Header combines branding, venue, navigation, race, boat filter, export, settings, and weather. | Too many elements compete in the first horizontal band. | Separate navigation from race context and place controls near their subject. |
| Replay uses a 240 px timeline, flexible map, 340 px standings, then several full-width sections. | The course receives limited space; playback occupies an entire side panel. | Use a dominant map with transport directly beneath and a compact fleet rail. |
| Labels frequently use 9–11 px text; some mobile captions reach 8 px. | Small type makes a complex product feel harder to use. | Introduce a narrow, readable type scale and stronger editing. |
| Compare contains a dark metric block inside the light workspace. | The product's surfaces and emphasis change unexpectedly. | Use aligned comparison rows in the shared light system. |
| Inline Analysis retains a modal-style title and close control. | The page reads as an embedded dialog. | Give inline Analysis proper page structure and semantics. |
| Forecast gives three different questions equal narrow card columns. | Long evidence and uncertainty explanations are cramped. | Create local forecast subnavigation with visible readiness for each question. |
| Mobile largely stacks complete desktop panels. | Primary playback context becomes separated by a long page. | Compose a phone workflow explicitly. |
| Root `user-select: none` prevents copying. | Evidence and measurements are inconvenient to reuse. | Restrict selection suppression to draggable surfaces. |

## 3. Art direction and rules against a generic appearance

### Product identity

Use the existing product name and approved brand assets in a simpler treatment. Let a real course silhouette, a precise boat drawing, a selected track, or a leg interval provide visual interest. Keep the interface predominantly neutral so team identity and quantitative marks remain clear.

Define three recognizable details and use them consistently: race-aware course thumbnails; a small, precise team-color marker paired with a text code; and a clear playhead treatment repeated across the map, transport, events, and telemetry. These details should feel native to this project.

### Composition rules

1. Give each workspace one dominant subject: course, race report, boat comparison, export collection, or forecast question.
2. Reserve large rounded surfaces for substantial visual or interactive regions. Use rows, spacing, and type for secondary information.
3. Keep controls compact in operational areas; use more generous spacing in the race browser and report introductions.
4. Use one strong action per local context. In Replay it is Play; in the race browser it is Open race; in a download row it is Download.
5. Keep descriptive text next to the evidence it explains. Shorten repetitive explanations without removing their meaning.
6. Review populated, partial, unavailable, and failure states as part of the design.

### Explicit rejection criteria

Reject decorative gradient blobs, glass panels, glow effects, animated background particles, fake activity, invented statistics, synthetic sailing photography, and generic feature grids. Reject repeated tiny uppercase labels above every heading, large meaningless icons, indiscriminate pills, and identical card treatments across the whole product.

Avoid promotional phrases such as “unlock insights” and “the future of racing.” Use direct labels: “Race analysis,” “Compare boats,” “Source coverage,” and “Download CSV.” Choose one interface language for this pass; the Italian reference does not require translating the English product.

The craft review must examine typography, alignment, image crops, empty space, chart labeling, control states, and copy individually. A distinctive logo cannot compensate for a generic layout.

## 4. Proposed visual system

### Palette

| Semantic role | Proposed value | Application |
| --- | --- | --- |
| Main canvas | `#FFFFFF` | Most page area and the navigation shell. |
| Quiet surface | `#F7F8F8` | Race thumbnails, secondary sections, lightweight groups. |
| Selected surface | `#EAF1FB` | Selected row or active control background. |
| Primary text | `#202124` | Headings, data, and primary labels. |
| Secondary text | `#5F6368` | Supporting copy and metadata; verify on each actual surface. |
| Divider | `#DADCE0` | Table rules and necessary control outlines. |
| Action | `#1967D2` | Primary actions, links, selected navigation. |
| Focus | `#174EA6` | Visible keyboard outline, separate from hover. |
| Caution | `#8A5300` | A consequential data limitation with a text explanation. |
| Error | `#B3261E` | Failed loads and actionable failures. |
| Grid water | `#EDF4F6` | Calm offline course surface, tuned against team colors. |

These are starting tokens. Verify contrast before adopting them. Keep measured-data identity, availability status, and competitor identity as separate roles. Do not recolor team identities to match the shell. Yellow and other light team colors need a contrasting outline or halo when rendered on pale water.

Use one canonical token file, with temporary aliases for `--tac-*` and legacy variables. Set the application color scheme explicitly to light. Give canvas drawing code a shared semantic palette without moving metric logic into rendering. Remove obsolete aliases only after their consumers have migrated.

### Typography

Use **DM Sans** as the proposed single family for interface text and headings. It supplies a rounded, restrained character suited to this direction. Self-host the required font files with their license, use `font-display: swap`, and check the actual loaded font in the browser. The [official Google Fonts repository includes its OFL license](https://github.com/google/fonts/blob/main/ofl/dmsans/OFL.txt).

| Text role | Desktop proposal | Phone proposal |
| --- | --- | --- |
| Race-library feature title | 44–48 px / 1.08 | 30–32 px / 1.12 |
| Workspace title | 32 px / 1.15 | 26 px / 1.2 |
| Section title | 20 px / 1.3 | 20 px / 1.3 |
| Body and explanatory text | 16 px / 1.5 | 16 px / 1.5 |
| Operational label or table | 14 px / 1.4 | 14 px / 1.4 |
| Secondary metadata | 12 px / 1.4 | 12 px / 1.4 |
| Clock or selected measurement | 24–32 px, tabular | 24–28 px, tabular |

Use weights 400, 500, and 600. Use tabular figures for measurements and aligned values. Reserve a mono fallback for technical identifiers where it improves reading. Keep long body copy out of monospace. Test decimal alignment, degree signs, negative values, nonfinish labels, long names, and changing clocks.

Format values at a precision justified by the exported metric and its unit. Keep original values and definitions available through evidence and downloads. Never shorten a missing-data reason into a misleading zero or suggest greater measurement precision through decorative decimals.

### Space and geometry

- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 px.
- Desktop outer gutters: 32 px, reduced to 24 px on smaller laptops and 16 px on phones.
- Report reading width: roughly 1200 px, centered; operational map layouts may use the available width up to a deliberate 1800 px maximum.
- Major course and race-library surfaces: 24 px radius on desktop, 16 px on smaller layouts.
- Supporting surfaces: 12–16 px radius where grouping needs a surface.
- Controls: 8–12 px radius; selected major actions may use fully rounded ends.
- Table rows: 44–48 px minimum before multiline content; do not add a rounded box to each row.
- Main controls: 40 px visible height on desktop, effective touch targets at least 44 × 44 px on phones.
- Shadows: overlays and an elevated sticky header only. Normal content separates through space and surface tone.

Never nest several framed cards to express a simple hierarchy. Keep separators quiet and allow the larger page grid to do the organizing.

### Icons and visual assets

Standardize the existing SVG icons into one consistent drawing language: nominal 20–24 px artwork, approximately 1.75–2 px strokes, matching optical weight, and consistent alignment. Reuse recognizable controls for play, pause, layers, download, settings, and fullscreen. Give icon-only controls accessible names and explanatory tooltips; essential states remain visible without hover.

The current public asset folder has no photographic library. Plan around real course artwork and the existing boat geometry first. Any later photography needs an approved source, recorded usage rights, and intentional desktop/phone crops. Keep asset provenance in the project. Do not hotlink reference-store artwork or use invented sailing scenes to fill a visual gap.

### Motion and interaction

Use 120–180 ms for local hover and disclosure transitions, up to about 220 ms for a drawer. Keep playback updates direct. Avoid layout-changing hover effects, bouncing controls, scroll reveals, and animated numerical counting. Respect reduced motion. Keep focus visible and ensure hover does not reveal the only path to an action.

## 5. Shared shell and navigation

Create a restrained 64 px desktop navigation row with the product mark/name at left, the five text destinations centrally, and a quiet race-library action and settings at right. Use an underline plus text treatment for the current destination. Avoid a separate filled pill for every destination.

Below it, use a race-context row: readable race title, venue/date/type, selected boat, and the compact condition summary appropriate to the view. Keep the full race identifier available in details. Put recorded wind and historical environment estimates in clearly labeled groups. Move sea and temperature detail into a Conditions disclosure when space is limited.

Place visible-boat filtering beside the course and telemetry it affects. Reports owns the prominent download actions. A secondary export shortcut may remain in a quiet menu if current users depend on it. Keep settings reachable and expose map-layer choices near the map.

On phones, use a compact brand/race row and a five-item navigation row with adequate touch targets. Move the full race title and change action into the next short context block. Keep labels readable at 320 px; reflow controls when needed. Avoid a header that becomes several tightly packed toolbars.

Preserve navigation shortcuts, URL entry points, race and boat state, and the distinction between a selected boat and the visible-boat filter.

## 6. Screen-by-screen design

### A. Replay

At desktop width, use this composition:

```text
Product / five views / Race library / Settings
Race title and context                     Conditions

Large course viewport                    Fleet standings
                                         Selected boat detail
Playback, clock, seek bar, speed

Synchronized telemetry                   Events and notes
Compact tactical summary + expandable evidence
```

The left course column expands with the window; the fleet rail is approximately 300–320 px. The map and playback form one visual unit. Remove the permanent timeline sidebar. Preserve event filters, event navigation, and all seek actions through the transport and events area.

At 1440 × 1000, aim for a course height around 540–600 px. At 1280 × 720, reduce it to roughly 360–400 px so race context, course, selected boat, and playback remain usable together. Derive the layout from available height and measured content rather than fixing every stage at 480 px.

Integrate the selected boat's speed, VMG, angle, and wind into a compact area beside the course or immediately beneath it. Use aligned values with units and small contextual traces only when they help. Avoid repeating the same measurement in several equal-emphasis blocks.

The transport contains Play/Pause, ±5 s, gun-relative time, seek bar with event markers, and playback speed. Event markers and the event list use the same exported feed. Preserve prestart, active race, reached events, and finish behavior. Seeking must continue to update every linked view consistently.

Keep the fleet complete even when filtering the map. Use readable team codes, selected-row emphasis, right-aligned values, and explicit unavailable samples. Put lower-priority fleet columns behind a column control or horizontal table scroll on small screens; never shrink the table into 8 px text.

Expose Events with a visible count/current event and a clear seek action. Keep Notes reachable. Expose Layers with an indication of its current settings. Retain orientation, follow mode, trails, true/enhanced scale, safety borders, zoom, reset, fullscreen, Map, and Grid. Verify fullscreen entry/exit and the availability of camera and playback controls in that state.

Use a pale, low-contrast offline water grid. In Map mode, tune the basemap through the existing style configuration while preserving geographic legibility and attribution. Course boundaries, marks, and labels need a deliberate hierarchy. Test boats and tracks over both water and land. Leave clear space for mark labels, the scale, attribution, and controls.

Telemetry gets aligned plot areas, shared time axes where appropriate, clear units, restrained gridlines, readable labels, and consistent playhead treatment. Keep the initial trace selection compatible with current behavior; use emphasis and direct identification to help users follow a selected boat without silently hiding the rest. Retain legitimate gaps. Keep tactical summaries short, with timestamps, availability, and supporting evidence still accessible.

### B. Race library / existing race picker

Turn the current picker into a roomy browser with a concise heading, venue/date grouping, text search, the active race, and race-aware course previews. Use a larger selected-race preview plus a practical list or grid of other races. Read the title, date, and venue from the current catalog. Obtain fleet/match type and replayed boat count from a compact preview/analysis index, or add optional backward-compatible catalog fields. Current `RaceListing` does not expose those two fields. Missing metadata needs an explicit unknown fallback and must never trigger a full replay download for every library item.

Generate lightweight thumbnails from existing course metadata or a separate bounded export. Show actual tracks only when supported by the source and label the depicted time/scope. Label simplified previews as schematic. Do not download all replay files to draw the library. A race without a thumbnail gets a clear text-first fallback.

Place race information beneath preview artwork, with one Open race action. Keep frequent use efficient: search, grouped dates, keyboard operation, selected-race recognition, and focus return after closing. Avoid promotional hero copy or a carousel that hides the archive.

### C. Analysis

Make Analysis a full workspace with a page title, race identity, boat selector, and the existing Race Report / Historical View subnavigation. Use a centered readable width and natural page scrolling. Remove modal close affordances and modal semantics in inline mode; keep a real dialog wrapper wherever dialog mode is still required.

Order the Race Report by the user's questions: reconstructed classification, selected-boat performance, per-leg evidence, manoeuvres/debrief, and source limitations. Use a compact prominent limitation summary, then attach each consequential reason to its affected result. Avoid repeating long generic warning blocks before every section.

Keep the six-axis radar as an overview with the peer baseline visible. Put its evidence and focused leg plot beside it on desktop and immediately below on phones. Preserve axis selection, all-leg/single-leg scope, matched/expected legs, exclusions, coverage, absolute values, and interval review links. Missing axes remain missing. Identify the overall profile as heuristic.

Use typography and spacing for debrief items. Each item should show the observed difference, comparison context, and Open interval action. Avoid adding a tactical-causation headline unsupported by the export.

Historical View uses clear cohort and scope controls, an aligned metric table, and selected-detail charts. Keep fleet and match cohorts separate. Count boat-races in historical denominators. Make units, formulas, windows, denominator, quality, and source coverage discoverable from the metric being inspected.

### D. Compare

Create a balanced two-boat header: A at left and B at right, with full names and persistent team markers. Keep both selectors in equivalent positions. Use aligned A value / metric and unit / B value rows for genuine per-boat values such as SOG and VMG, retaining their existing signed differences. Present physical separation, closure, along-leg offset, lateral offset, and cumulative progress difference as a separate compact pairwise section, each with one correctly labeled value. Do not invent individual A/B measurements for quantities that describe the pair.

Explain B−A once near the delta column. Preserve the distinct meanings of physical separation, along-leg offset, cumulative race progress, closure, SOG, and VMG. Do not color every positive delta green; a geometric or directional sign does not necessarily mean better performance.

Put shared playback directly above the linked telemetry. Use the same cursor and time language as Replay. Keep missing B, identical selection, and unavailable measurements explicit. A compact course view is optional for a later iteration; the first pass can achieve the visual result with the existing instantaneous comparisons and traces.

### E. Forecast

Replace the three narrow equal card columns with local subnavigation for **Live race**, **Before the start**, and **America's Cup 2027**. Show all three question names and readiness summaries before selection. Keep the main five-view navigation and shortcuts unchanged.

- Live race: lead with the forecast time, state age, and exact win target. Use a full-width ranked table or horizontal probability chart when values are available. Keep playhead controls here and clearly show unavailable checkpoints.
- Before the start: lead with the selected conditions and expected-position target. Keep nonfinish scored N visible. Use a readable field table; never imply the expectations must sum to ordinary finishing ranks. Unsupported custom scenarios retain their reason and do not borrow a nearby artifact.
- America's Cup 2027: give uncertainty room. Use horizontal range marks with an accessible table, a readable scenario chooser, and distinct labels for pinned baseline rule bounds, the selected transfer assumption, and the overall outer envelope. Keep unresolved mass/stages, mapping, cutoff, actual draws, numerical error, and endpoint attribution inspectable.

Do not link the Cup scenario's conditioning to the live playhead. Preserve the separate AC40 and AC75 contexts. Unavailable output gets a designed explanation and a useful evidence action. Keep calibration status and uncertainty interpretation accurate. Avoid gauges, confidence scores, or center-point summaries that the artifacts do not support.

### F. Reports

Use a clear report title and race context, then the canonical summary table. Make selected-boat evidence easy to find without losing the full field. Use readable metric values and attach partial/unavailable reasons locally.

Keep at most six curated current-race exports near the top. Present them as compact rows with name, purpose, format, size, and Download. This makes the varying file names and metadata easier to scan than a wall of identical cards.

Retain the collapsed searchable Technical data and provenance explorer, including status/scope, every published output, archive indexes, and retained forecast versions. Preserve canonical Analysis/Reports agreement and the full artifact inventory. A quieter presentation must still make the archive discoverable.

## 7. Responsive behavior

| Width | Composition |
| --- | --- |
| 1200 px and above | Course plus fleet rail; generous workspace headers; side-by-side evidence where useful. |
| 768–1199 px | Course takes the main width; fleet becomes a compact section or drawer; evidence pairs stack when labels need space. |
| 320–767 px | Brand/context, five views, course, transport, selected boat, then fleet/telemetry/events. Secondary evidence uses clear disclosures. |

On a 390 × 844 phone, aim to show race context, a useful 300–340 px course, playback, and selected-boat context within the initial screen or a short scroll. Adjust for browser controls and safe areas. Do not pin several large bars over the map.

Reserve horizontal scroll for genuinely wide data tables. Keep the document itself within the viewport. Test drawers, long options, expanded evidence, and error messages at 320 px and at 200% browser zoom. Ensure sticky elements cannot cover keyboard focus, attribution, the last table row, or the last action.

## 8. Component and file plan

| Work package | Current owners | Planned work |
| --- | --- | --- |
| State and entry points | `src/App.tsx` | Preserve race/boat/playhead ownership, links, loading, cancellation and error behavior; keep presentation changes local. |
| Shell | `TacticalHeader.tsx`, `TacticalDashboard.tsx` | Recompose navigation, context, view headers, and responsive regions. |
| Foundation | `src/index.css`, `src/app.css`, `dashboard.css`, `workspaces.css` | Introduce shared tokens/type/layout, remove competing roots, migrate aliases, reformat touched CSS. |
| Transport and events | `RaceTimelinePanel.tsx`, `EventsNotesPanel.tsx` | Reuse current behavior in a horizontal transport and an accessible events section. |
| Course and fleet | `CourseCanvas.tsx`, `mapStyle.ts`, `StaticCourseLayer.ts`, `DynamicVesselLayer.ts`, `TacticalMapOverlay.tsx`, `RaceStatusLeaderboard.tsx` | Tune palette, labels, clearance and chrome; preserve geometry and hit testing. |
| Selected boat and telemetry | `BoatPerformanceCard.tsx`, `TelemetryWorkspace.tsx`, `TacticalInsightsPanel.tsx` | Integrate measurement hierarchy, standardize plot chrome and evidence disclosure. |
| Race library | `modals/RacePickerModal.tsx`, `src/engine/catalog.ts`, optional compact preview export | Add the visual browser with bounded lightweight previews, metadata fallbacks, and legacy-compatible catalog behavior. |
| Analysis | `modals/AnalysisModal.tsx`, `BoatPerformanceRadar.tsx`, `TeamDebrief.tsx`, `analysis-light.css`, `performance-radar.css` | Separate page/dialog framing, simplify section hierarchy, preserve evidence interactions. |
| Compare | `panels/ComparisonPanel.tsx` and dashboard composition | Build an aligned A/B layout and consistent surfaces. |
| Forecast | `ForecastWorkspace.tsx`, `forecast.css`, `cupEvidence.css` | Local question navigation, readable ranges, preserved readiness and evidence. |
| Reports | `ReportsWorkspace.tsx`, `reports.css` | Report hierarchy, compact export rows, intact technical explorer. |
| Documentation and checks | `docs/design-system.md`, `docs/dashboard_contract.md`, verification docs and `tests/browser/` | Publish the new visual authority, update intentional interaction changes, preserve behavior assertions. |

Dashboard filenames in this table live under `src/components/dashboard/` unless another path is shown. Canvas filenames live under `src/components/canvas/`. Add a small shared presentation layer for buttons, field labels, disclosures, view headers, status text, and metric rows as reuse becomes concrete. Avoid a broad framework migration or replacement of the renderer.

## 9. Data, performance, and compatibility requirements

Python continues owning historical metrics and forecast computations. The interface reads exports. Never recompute a historical mean, coverage rule, radar index, or probability for visual convenience.

Keep source measurements, interpolated samples, reconstructed results, estimated quantities, and unavailable values distinguishable. Keep sea/temperature estimates separate from recorded wind and prediction inputs. Retain virtual-contact language that describes geometry rather than official rulings.

Preserve A/B independence; full fleet ranking under map filters; race-change reset rules; per-race notes; playhead gating; stale-insight expiry; replay interval links; cancellation of stale loads; legacy replay/catalog compatibility; Map/Grid parity; true/enhanced geometry; moving marks; OSM attribution; and offline Grid's zero tile requests.

Load only the artifacts needed for the selected race and open evidence. Keep race thumbnails small, and lazy-load below-the-fold artwork. Avoid making header/layout work run on every replay tick unnecessarily. Test font swaps and growing values for layout shifts. Preserve the existing production worker setup and confirm its emitted URL loads.

A presentation-only implementation should not regenerate raw telemetry or forecast artifacts. First record their current hashes/inventory. If lightweight preview exports are added, version their small contract, keep them separate from metric data, and include them in the published inventory as appropriate. Any actual formula change needs its own Python/artifact/documentation review.

## 10. Implementation stages and acceptance gates

### Stage 1 — Baseline, source audit, and contract

Deliver a bounded current-screen inventory, workflow/state matrix, reference captures, and archived before screenshots. Reuse `docs/source_audit.md` unless source files changed. Use `scripts/analysis_snapshot.py` for counts. Record existing working changes and representative artifact hashes. Identify any baseline verification failures separately from redesign work.

Acceptance: every current feature has a destination in the new layout; new visual authority and unchanged data contracts are explicit. No telemetry arrays enter the design brief.

### Stage 2 — Visual direction and specimen

Produce one detailed desktop Replay composition, one phone Replay composition, and a compact specimen containing a button, selector, table, chart, disclosure, loading state, unavailable value, and error. Resolve the font, palette, density, map styling, and major radii here. Use real race content in all previews.

Acceptance: compare against the supplied Store at matching widths for hierarchy, space, type, and surface restraint. Inspect real longest labels and team-color contrast. The direction is reviewable before broad screen work.

### Stage 3 — Pipeline impact, artifacts, and shared foundation

Confirm the pipeline impact is limited to any explicitly chosen preview asset. Define its source, scope, size and fallback before generating it. Establish tokens, fonts, controls, the shell, page headers, and migration aliases. Update `docs/design-system.md` to remove conflicting visual rules.

Acceptance: all five current views render coherently with the shared foundation; focus, copying, font loading and layout work. Existing data bytes remain unchanged apart from approved new presentation assets.

### Stage 4 — Replay and race browser

Implement the map/rail/transport structure, fleet presentation, selected-boat values, telemetry hierarchy, event disclosure, and race library. Refine the phone layout at the same time.

Acceptance: fleet and match races work at large and short desktop heights and on phones; playback, selection, layers, events, notes, and race switching retain their behavior. The course is the strongest visual element.

### Stage 5 — Remaining workspaces

Complete Analysis page semantics and evidence layout, aligned Compare, forecast question navigation and uncertainty presentation, and Reports exports/provenance. Keep shared state and temporal boundaries intact.

Acceptance: all five views feel related while giving their own task a clear hierarchy. All historical formulas, forecast definitions and downloads remain traceable.

### Stage 6 — Focused verification and visual refinement

Run the existing focused component/engine tests relevant to changed behavior, then the dashboard, annotation, and real-artifact forecast browser suites. Update tests for intentional layout/accessible-name changes while retaining their substantive assertions. Test the production build as well as the development preview.

Review screenshots side by side. Correct spacing, wrapping, font fallback, empty plot areas, label collisions, drawer overflow, sticky occlusion, and missing-data presentation. Use deterministic Grid captures for stable visual comparisons; verify Map separately with live tiles, worker loading, attribution and failures.

Acceptance: no unexplained visual or interaction regression; no same-origin missing assets; all relevant failures resolved or explicitly traced to the existing environment/baseline.

### Stage 7 — Full repository gate and handoff

Run `.\run.ps1 verify` directly, complete the required browser checks, and publish the updated contract and verification evidence. Reconcile generated-data hashes and artifact inventory. Remove obsolete styling after checking its remaining consumers.

Acceptance: record exactly which checks passed, along with final screenshots and remaining known limitations. Do not infer forecast reliability from successful software tests.

A realistic planning allowance is roughly 10–16 working days for one experienced front-end developer, including visual iteration and verification. This is a scope estimate, not a delivery commitment; the baseline and evidence interactions can change it.

## 11. Verification matrix

### Representative content

- Nine-boat Naples fleet, two-boat match, and Cagliari course geometry.
- Prestart, gun, active racing, reached finish, and unfinished/retired boats.
- Long team/race names, missing samples, sparse coverage, stale tactical insights, and missing radar axes.
- Same A/B, no usable B measurement, interval review, race change during loading, and disabled local storage.
- Available and unavailable live forecasts, unsupported pre-race conditions, wide Cup bounds, retained forecast versions, and empty archive search.
- Initial loading, recoverable fetch failure, missing thumbnail, and download failure where applicable.

### Layout and accessibility

Capture all five workspaces at 1440 × 1000 and 390 × 844. Give Replay additional coverage at 1586 × 992, 1280 × 720, 1024 × 768, 768 px width, 320 px width, and a wide desktop. Check 200% zoom, keyboard-only use, reduced motion, touch disclosures, dialog focus return, screen-reader names, and copying evidence.

Target at least 4.5:1 contrast for normal text and 3:1 for large text and meaningful control/graphic boundaries. Verify with actual rendered colors. Pair status and team color with labels or geometry. Provide accessible table alternatives for quantitative plots. Do not announce every playback frame to assistive technology.

### Functional and technical

Retain all-28-race loading coverage in the existing browser suite. Verify shared state and keyboard shortcuts, independent A/B selection, complete fleet ranking under filters, temporal event gating, analysis interval links, canonical report metrics, complete downloads, correct forecast artifact selection, and missing-data recovery. Verify fullscreen entry/exit, camera behavior, and transport access; preserve the distinction between per-boat and pairwise comparisons.

Confirm offline Grid requests no tiles, Map attribution remains visible, the production MapLibre worker responds successfully, and the redesigned shell introduces no application request/console failures. Compare load/request counts and playback responsiveness to the captured baseline; investigate regressions before adding more assets.

## 12. Definition of done

The redesign is ready when the first screen has a clear focal point; text is comfortably readable; controls and evidence are easy to find; every page uses the same typography and semantic surfaces; and phone use feels deliberately composed.

Review the product without its logo: real course geometry, team identity, telemetry, and the handling of race evidence should still make it recognizable. Reject any screen that feels like a generic analytics template with sailing labels added.

Deliver the updated visual specification, all five finished workspaces, the race browser, populated/partial/error states, responsive screenshots, preserved feature/evidence coverage, and the recorded verification results. The resulting quality comes from repeated precise editing of real screens.
