# Regatta Replay interface system

## Purpose and user

This is a race analysis workstation for sailors, coaches, and data analysts. The recurring task is to inspect the course at a selected time, compare boats, then examine the evidence behind a reconstructed result. The course and its moving boats are the first visual anchor; the clock, selected boat, and race state come next. Analysis must stay legible at desktop and phone widths. Measured telemetry and reconstructed events must never look interchangeable.

## Design direction

The interface should resemble a precise instrument used beside a race course: dense, stable, and readable. The course, boat liveries, traces, and event marks provide the product identity. Chrome stays neutral so it does not compete with them. Playback, view mode, and scale mode live beside the course they affect.

## Tokens

| Role | Value | Use |
| --- | --- | --- |
| App canvas | `#0a0f18` | Main background |
| Surface | `#101722` | Toolbar and playback |
| Panel | `#111827` | Analysis dock and modal |
| Raised/control | `#17212f` | Controls and selected rows |
| Hairline | `#2b3745` | 1 px separation |
| Strong border | `#405265` | Active and focused boundaries |
| Primary text | `#edf2f7` | Data and headings |
| Secondary text | `#b2c0cd` | Labels and supporting copy |
| Muted text | `#8d9daa` | Metadata that remains readable |
| Cyan | `#06b6d4` | Selected telemetry, navigation, focus |
| Amber | `#f59e0b` | Wind, mark, and caution information |
| Red | `#ef4444` | Active contact or critical failure only |

Boat/team colors identify competitors and remain separate from interface status colors. Use existing semantic CSS variables; new components must consume those variables instead of inventing raw colors.

## Type, density, and geometry

Use Chakra Petch for compact UI labels and JetBrains Mono for clocks, telemetry, distances, and tables. The numeric font must use tabular figures. Body labels are 12–14 px, section labels 11–12 px, and the main clock 24 px. Use a 4 px spacing unit; common gaps are 4, 8, 12, and 16 px. Controls are at least 30 px high on desktop and have a 44 px touch target on mobile. Use 1 px borders and radii of 2–4 px. Reserve larger radii for dialogs. Avoid decorative shadows, glass blur, gradient fills, and glowing text.

## Information and behavior

- The course has visual priority; toolbar controls must leave the start line, marks, and boats visible.
- Selected states use a cyan edge or rule plus a tonal change. Color alone must not carry a state.
- Tables align numbers right and use one unit per column. Availability and provenance appear next to results.
- Distinct user actions use native buttons and selects with visible focus rings. Keyboard access and reduced-motion preferences are required.
- On narrow screens, the course and playback remain available before secondary analysis; dense rows may scroll or reshape without shrinking text below legibility.

## Visual authority

The user-supplied 1586 × 992 reference ("Dashboard tattico della Coppa America a Napoli.png") governs the layout composition, high-density 3-band structure, marine chrome palette, and telemetry workspace. While preserving strict data provenance and telemetry truth (real 9-boat roster, honest unavailable states for unmeasured channels), the visual design embraces the approved silver America's Cup mark, venue flag badge, 4-card analytics quadrant.

## Change log

- 2026-10-13: Adopted the America's Cup Naples tactical dashboard reference composition across the header, left-rail timeline, central map overlays, race status leaderboard, middle performance quadrant, and bottom multi-strip telemetry workspace.
- 2026-10-12: Codified the instrument interface for the seven-part redesign and clarified the meaning of semantic colors, density, and provenance.

