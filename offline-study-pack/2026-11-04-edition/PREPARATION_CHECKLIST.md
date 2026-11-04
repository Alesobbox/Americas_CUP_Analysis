# Offline Study Pack — Mountain Departure & Preparation Checklist

> **Pack Directory**: `offline-study-pack/2026-11-04-edition/`
> **Frozen Snapshot**: `2026-11-04` | **Git Commit**: `f956f8a14feb3d6bfa483b91ea10384f3bcb84d4` (`main`, dirty working tree with per-file SHA-256 provenance in [`evidence/repository_snapshot_provenance.json`](evidence/repository_snapshot_provenance.json))

---

## 1. What to Open First (Laptop vs. Tablet / Phone)

### On Your Laptop (Full Study Environment)
1. **Start Here**: Open [`START_HERE.html`](START_HERE.html) in any browser (`file://` works directly with Wi-Fi off).
2. **15-Minute Mental Model**: Open [`02_Field_Guide.pdf`](02_Field_Guide.pdf) (or [`02_Field_Guide.html`](02_Field_Guide.html)) to see the entire system on one page, the formula reference sheet, the three forecasting targets, and the troubleshooting decision tree.
3. **Deep Conceptual Mastery**: Read [`01_Repository_Explained.pdf`](01_Repository_Explained.pdf) alongside the searchable [`01_Repository_Explained.html`](01_Repository_Explained.html) and the 209-file [`source-companion/index.html`](source-companion/index.html).
4. **Active Self-Testing (Closed-Book First!)**: Work through the 36 exercises in [`04_Workbook.pdf`](04_Workbook.pdf) before checking [`04_Workbook_Solutions.pdf`](04_Workbook_Solutions.pdf).
5. **Interactive Experimentation**: Open [`examples/interactive_sailing_and_forecast_lab.html`](examples/interactive_sailing_and_forecast_lab.html) and [`study-materials/flashcards_viewer.html`](study-materials/flashcards_viewer.html) directly in your browser.

### On Your Phone or E-Ink Tablet (Trail / Hut Reading)
Copy these five zero-dependency files to your tablet/phone reader:
- [`01_Repository_Explained.pdf`](01_Repository_Explained.pdf) — Complete 9-Part Textbook & Case Studies
- [`02_Field_Guide.pdf`](02_Field_Guide.pdf) — Condensed 8–12 Page Companion
- [`04_Workbook.pdf`](04_Workbook.pdf) — 36 Exercises Across 3 Difficulty Tiers
- [`04_Workbook_Solutions.pdf`](04_Workbook_Solutions.pdf) — Step-by-Step Mathematical Derivations & Answer Key
- [`study-materials/06_Audio_Narration_Script.html`](study-materials/06_Audio_Narration_Script.html) — Spoken-Word Rehearsal Script (compatible with iOS/Android system text-to-speech)

---

## 2. Capability Matrix: What Works Without Installing Anything vs. What Needs a Runtime

| Deliverable / Feature | Works via Direct `file://` Double-Click (Zero Install)? | Works Without Wi-Fi? | Runtime Required (If Any) |
|---|---|---|---|
| **All 4 PDFs** (`01_Repository_Explained.pdf`, `02_Field_Guide.pdf`, `04_Workbook.pdf`, `04_Workbook_Solutions.pdf`) | **Yes (100%)** | **Yes** | Any PDF viewer |
| **All Searchable HTML Editions** (`01..06`, `START_HERE.html`, `MANIFEST.html`) | **Yes (100%)** | **Yes** | Any modern web browser |
| **Interactive HTML Sandbox & 64 Flashcards** (`interactive_sailing_and_forecast_lab.html`, `flashcards_viewer.html`) | **Yes (100%)** | **Yes** | Any modern web browser |
| **Pre-Rendered Study Notebook** (`examples/05_Interactive_Study_Notebook.html`) | **Yes (100%)** | **Yes** | Any modern web browser |
| **209-File Browsable Source Companion** (`source-companion/index.html` with `#L1..#LN` anchors) | **Yes (100%)** | **Yes** | Any modern web browser |
| **3 Executable Verification Scripts** (`examples/01_*.py`, `02_*.py`, `03_*.py`) | No (CLI scripts) | **Yes** | `python` (Python 3.10+ standard library only) |
| **Optional Built React Dashboard — Grid Mode & Static Forecasts** (`offline-dashboard/serve_offline_dashboard.py`) | No (Browsers block `fetch()` under `file://` CORS) | **Yes (in Grid Mode)** | `python offline-dashboard/serve_offline_dashboard.py` (`http://127.0.0.1:8080`) |
| **Optional Live Forecast Scenario Generation** (`POST /api/forecast-scenarios`) | No | **Yes (locally)** | `npm run dev` or `npm run preview` (Node + Python `server_bridge.py`) |
| **MapLibre Background Vector Map Tiles** (Map Mode satellite/street basemap) | No | **No (Requires internet tile server)** | Use **Grid Mode** (`Course-Up` / `North-Up`) when offline! |

---

## 3. Archive & Disk Size Accounting

- **Study Pack Sizes**: Exact uncompressed byte count, file count, and compressed `.zip` size are recorded in [`MANIFEST.json`](MANIFEST.json) and [`MANIFEST.html`](MANIFEST.html).
- **Optional Full Repository Static Data Footprint**:
  - Built frontend bundle (`dist/`): `2,412,191` bytes (`2.41 MB`).
  - Published static data (`public/data/`, 505 files): `263,706,323` bytes (`263.71 MB`, mostly the 28 full 10 Hz `replay.json` files).
  - Raw telemetry archive (`Data/*.jsonl`, 28 files): `6,866,006,601` bytes (`6.87 GB` / `6.39 GiB`) — deliberately **excluded** from the portable study pack (bounded excerpts and full SHA-256 digests are included in [`evidence/analysis_index.json`](evidence/analysis_index.json)).
  - Zero-dependency launcher [`offline-dashboard/serve_offline_dashboard.py`](offline-dashboard/serve_offline_dashboard.py) serves the repository's `dist/` and `public/data/` locally on port `8080` without Node or internet access.

---

## 4. Before-Departure Verification Checklist

- [ ] **1. Extract the ZIP Archive Now**: Extract `AC40_Regatta_Replay_Offline_Study_Pack_2026-11-04.zip` to a local folder on your laptop before turning off Wi-Fi; do not rely on reading linked HTML files from inside an unextracted ZIP previewer.
- [ ] **2. Turn Off Wi-Fi (Airplane Mode Test)**: Disable Wi-Fi and open [`START_HERE.html`](START_HERE.html). Click into [`01_Repository_Explained.html`](01_Repository_Explained.html), test the sidebar search box (e.g., type `12.963` or `RRSAC 102.1`), and click a [`source-companion/index.html`](source-companion/index.html) line link (`#L228`).
- [ ] **3. Verify PDF Bookmarks & Rendering**: Open [`01_Repository_Explained.pdf`](01_Repository_Explained.pdf) and [`02_Field_Guide.pdf`](02_Field_Guide.pdf) in your PDF viewer and confirm the left-hand Bookmarks/Outline tree navigates to Parts I–IX.
- [ ] **4. Run the Three Standard-Library Verification Scripts (Optional, 5 Seconds)**:
  ```powershell
  python examples/01_verify_projection_and_bow_crossing.py
  python examples/02_reconcile_performance_index.py
  python examples/03_plackett_luce_and_cup_bounds.py
  ```
- [ ] **5. Copy PDFs to Secondary Device**: Transfer `01_Repository_Explained.pdf`, `02_Field_Guide.pdf`, `04_Workbook.pdf`, and `04_Workbook_Solutions.pdf` to your tablet or phone as a backup.
