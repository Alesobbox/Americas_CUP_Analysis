# Verification and practical limits

Review date: 4 November 2026, Europe/Rome. The reviewed source is a selected first-party snapshot of a dirty working tree based on commit f956f8a14feb3d6bfa483b91ea10384f3bcb84d4. The actual included bytes, sizes and SHA-256 values are recorded in evidence/snapshot.json. The public artifact manifest separately hashes actual bytes of all506 existing data files. Raw telemetry was not rehashed; the existing source audit was reused.

## Fresh repository checks

The prescribed run.ps1 verify gate passed:406 frontend tests in39 files, production build,291 Python units,123 replay checks, eight generated-data checks, public forecast/schema/hash/budget verification, environment integrity and team-analytics integrity. These four counted test groups total828 cases. The66 focused preflight checks overlap that total and are not additional independent evidence. Full logs are in verification/.

Fresh dashboard browser verification passed18 groups with zero application exceptions or failed application requests. Forecast browser verification passed19 groups, including real published archive fields and Cup evidence plus synthetic job/recovery fixtures. It did not create a new real forecast publication. Five current workspace screenshots were captured with external requests blocked and no page exceptions. Earlier real-generation and additional browser-suite results in repository documentation remain dated historical claims.

## Pack checks

Every PDF is rendered to page images with the bundled PDFium renderer; page images and contact sheets are inspected for clipping, missing glyphs, table readability and page breaks. Structural checks cover searchable text, embedded font subsets, bookmarks, contents links, page bounds and link annotations. The source companion uses stable relative line anchors; citations are checked against frozen source ranges. The pack's HTML is checked for local link/anchor integrity and tested in a fresh browser with network access blocked after ZIP extraction into another directory. Exact results are in verification/pack-checks.json and verification/offline-browser.json.

The numerical lab passes its assertions. Nine additional arithmetic checks against owning Python helpers and actual historical fields are recorded in evidence/data_metrics_review.json. Independent semantic review corrected the FRA example to matched legs1 and3 with six peers, distinguished derived TWA from source measurements, and kept causal forecast preparation separate from retrospective historical metrics.

## Limitations

Software checks establish implementation consistency, not predictive calibration, independently verified official results or causal tactical effects. The current live descriptive audit covers seven races over two days; completion labels are source reconstructed; pre-race audit scores do not uniformly improve over the reference. Cup structural bounds and AC40-to-AC75 transfer assumptions remain explicit.

The study pack is standalone. The optional dashboard was measured at266,118,514 built bytes and is not bundled. New forecast generation requires the prepared Python service/dataset; static HTML cannot provide it. No audio was generated. Narration is included as text. PDF source links may require viewer permission to open local files; identical readable citations and HTML source links are provided.

The source companion is selective and not a Git clone or operational backup. It excludes raw telemetry, dependency directories, caches, credentials and large generated arrays. Existing notices are preserved; no top-level repository license grant was found or invented. Authoring dependencies are declared in the pack's separate manifests and are unnecessary for reading. The quality scan applies to study tools only, with frozen copied source excluded. Missing optional scanner engines/audit capability are disclosed in its JSON report.


## Final delivery checks

The main textbook has77 pages,48 bookmarks and374 link annotations. The field guide has11 pages; workbook and separate answer key have eight pages each. All PDF pages were rendered and visually reviewed through full-document contact sheets, with dense pages and diagrams additionally checked at readable scale. Embedded fonts, searchable text, page bounds and missing-glyph checks pass. All213 frozen source files and506 public artifacts remain unchanged.

The study-tool scan scores93/100 with no errors or fixable warnings. Its single remaining warning incorrectly treats self.links initialized inside a parser constructor as a mutable function default; no function argument has that default. Optional Ruff/Knip/dependency-audit coverage is unavailable as disclosed by the scan; no application configuration was changed to hide findings.
