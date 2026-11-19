# Regatta Replay interface system

## Purpose and user

This is a race analysis workstation for sailors, coaches, and data analysts. The recurring task is to inspect the course at a selected time, compare boats, then examine the evidence behind a reconstructed result. The course and its moving boats are the first visual anchor; the clock, selected boat, and race state come next. Analysis must stay legible at desktop and phone widths. Measured telemetry and reconstructed events must never look interchangeable.

## Design direction

The interface uses a calm white shell, clear typography, generous section spacing, and deliberately composed workspaces. The course, boat geometry, team liveries, traces, and event marks provide the product identity. Chrome stays neutral. Replay and Compare retain practical control density; the race library and report introductions have more breathing room. Playback, view mode, and scale mode live beside the content they affect.

Use real race content rather than decorative feature grids, synthetic sailing photography, gradient backgrounds, glass effects, glowing marks, or invented activity. Each view has a dominant subject: the course, race report, boat pair, or export collection.

## Tokens

`src/index.css` owns the canonical semantic palette and the light color scheme. Tactical and historical compatibility variables map into these roles during migration. Analysis uses `analysis-light.css` to bridge legacy consumers. New components use semantic variables instead of inventing a separate theme. Map imagery and team identity colors remain independent.

| Role | Value | Use |
| --- | --- | --- |
| App canvas | `#ffffff` | Main page and shell |
| Surface | `#ffffff` | Toolbar and playback |
| Panel | `#ffffff` | Analysis dock and modal |
| Quiet surface | `#f7f8f8` | Preview tiles, controls, secondary grouping |
| Selected surface | `#eaf1fb` | Selected rows and subtle control emphasis |
| Hairline | `#dadce0` | Necessary 1 px separation |
| Action | `#1967d2` | Links, primary actions and current navigation |
| Focus | `#174ea6` | Visible keyboard outline |
| Primary text | `#202124` | Data and headings |
| Secondary/muted text | `#5f6368` | Supporting copy and readable metadata |
| Caution | `#8a5300` | Consequential limitations with text |
| Error | `#b3261e` | Actionable failures |
| Offline water | `#edf4f6` | Grid course surface |

Boat/team colors identify competitors and remain separate from interface status colors. The existing VMG trail categories retain their own stable mapping. `src/components/canvas/renderPalette.ts` supplies the neutral Canvas 2D/MapLibre palette. Light team traces receive a quiet contrasting under-stroke; labels use neutral ink. Course and safety boundaries remain distinct.

## Type, density, and geometry

Use the self-hosted DM Sans variable font for interface text, headings, and measurements. `public/fonts/dm-sans-variable.ttf` includes optical-size and weight axes; `public/fonts/OFL.txt` and `README.md` retain its license and upstream source. The preload in `index.html` and `font-display: swap` avoid a third-party font dependency. `--font-technical` is available for actual technical identifiers. Legacy `--font-mono` maps to DM Sans, with tabular figures applied to changing/aligned measurements.

Use a small type hierarchy: roughly 32 px workspace headings, 20 px section headings, 16 px explanatory copy, 14 px operational labels/tables, and 12 px secondary metadata. The clock and selected measurements have stronger emphasis. Use weights 400, 500, and 600. Reflow long text before reducing its size. Canvas course labels use 12 px DM Sans and high-contrast surfaces. Measurements retain their units, justified display precision, and genuine unavailable states.

Use a 4 px spacing unit with 8, 12, 16, 24, 32, 48, and 64 px steps. Major visual surfaces use approximately 24 px corners on desktop and 16 px on smaller screens; supporting controls use smaller corners. Keep tables and simple rows open. Do not nest framed cards to express a basic hierarchy. Reserve shadows for overlays and elevated navigation. Touch targets are at least 44 px where practical; focus remains visible.

Use short local transitions for controls and disclosures. The shared reduced-motion rule disables nonessential animation. Recorded wind arrows show direction without decorative drift. Playback and the linked playhead update directly.

## Workspace composition

- The header separates product/navigation from race context and conditions. The four main views and their shortcuts remain stable.
- Replay gives the course priority, with map controls in a separate row above the scene, playback immediately below it, and the full fleet beside it on wide screens. Selected-boat values, synchronized telemetry, events, notes, and tactical evidence remain reachable.
- The race library uses lightweight race-aware course artwork and text search; previews do not require browser downloads of every replay.
- Inline Analysis is a page, while genuine dialog mode retains its own dialog semantics. Classification, performance, leg evidence, and debrief keep distinct hierarchy.
- Compare separates per-boat values from geometric or other pairwise measurements and preserves signed B-minus-A meaning.
- Reports leads with canonical metrics and current-race downloads, with the complete technical archive still searchable.

On phones, put race context, course, playback, and selected-boat context before secondary evidence. Tables may scroll where necessary; the document must not. Expanded content, long names, loading, errors, and unavailable values receive the same visual care as the normal populated state.

## Information and behavior

- The course has visual priority; toolbar controls must leave the start line, marks, and boats visible.
- Selected states use an action-colored edge or rule plus a tonal change. Color alone must not carry a state.
- Tables align numbers right and use one unit per column. Availability and provenance appear next to results.
- Distinct user actions use native buttons and selects with visible focus rings. Keyboard access and reduced-motion preferences are required.
- On narrow screens, the course and playback remain available before secondary analysis; dense rows may scroll or reshape without shrinking text below legibility.
- Evidence text can be selected and copied. Limit `user-select: none` to surfaces where dragging would otherwise select text.
- Icon-only controls have accessible names. Essential actions and states remain available without hover.
- Modals retain focus, close with Escape, and return focus to their opener. Sticky controls must not cover focus, map attribution, or the last action.

## Visual authority

The Google Store-inspired visual system (referencing clean light typography, open whitespace, and high-contrast data ink) is the current visual authority. Existing data provenance, replay compatibility, and metric/availability rules continue to govern displayed results. The project-specific tokens above are deliberate implementation choices.

## Change log

- 2026-11-03: Adopted the approved Google Store-inspired composition, shared light tokens, self-hosted DM Sans, pale course rendering, readable labels, and distinct workspace layouts. Added a staged verification record.
- 2026-11-03: Applied the user-requested white Analysis palette, removed permanent Heel/Current placeholders and retained source-channel limits in technical evidence.
- 2026-10-13: Adopted the America's Cup Naples tactical dashboard reference composition across the header, left-rail timeline, central map overlays, race status leaderboard, middle performance quadrant, and bottom multi-strip telemetry workspace.
- 2026-10-12: Codified the instrument interface for the seven-part redesign and clarified the meaning of semantic colors, density, and provenance.

