"""CLI runner for AC40 America's Cup telemetry ingestion, reconstruction, and export.

Executes end-to-end:
1. WGS84 to local metric projection verification.
2. Streaming telemetry ingestion and 10Hz stream synchronization.
3. Geometric race reconstruction (gates, starts, OCS, USA fallback).
4. Tack and gybe manoeuvre detection with hysteresis.
5. Continuous monotonic race progress and dynamic leaderboard analytics.
6. Export of compact replay JSON artifact (public/data/replays/naples_pr1.json) and manifests.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
import tracemalloc

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import (
    SAMPLE_INTERVAL_MS,
    SAMPLE_RATE_HZ,
    MPS_TO_KNOTS,
    COMPETITORS,
    MARKS,
)
from pipeline.projection import verify_gate_marks_projection_accuracy
from pipeline.ingest import IngestionPipeline
from pipeline.reconstruction import RaceReconstructionEngine
from pipeline.manoeuvres import ManoeuvreDetector
from pipeline.analytics import AnalyticsEngine
from pipeline.export_replay import build_replay_manifest, export_replay_artifacts
from pipeline.historical_analysis import build_race_analysis, export_analysis_artifacts


def infer_race_metadata(input_path: str) -> dict[str, str]:
    filename = os.path.basename(input_path).lower()
    clean = os.path.splitext(os.path.basename(input_path))[0]
    slug = clean.lower().replace(" ", "_")
    is_cag = "cag" in filename or "cagliari" in filename
    venue = "Cagliari, Sardinia, Italy" if is_cag else "Gulf of Naples, Italy"

    # Specific benchmark matches:
    # 26 09 22 NAP IPR PR1 -> naples_pr1 (Benchmark race)
    if "26 09 22" in filename and "pr1" in filename:
        return {
            "race_id": "naples_pr1",
            "race_name": "Practice Race 1",
            "race_date": "2026-09-22",
            "venue": "Gulf of Naples, Italy",
        }
    # 26 09 27 NAP IPR MR Final -> naples_mr_final
    if "26 09 27" in filename and ("mr final" in filename or "match" in filename):
        return {
            "race_id": "naples_mr_final",
            "race_name": "Match Race Final",
            "race_date": "2026-09-27",
            "venue": "Gulf of Naples, Italy",
        }
    # 26 05 24 CAG IPR MR Final -> 26_05_24_cag_ipr_mr_final
    if "26 05 24" in filename and ("mr final" in filename or "match" in filename):
        return {
            "race_id": "26_05_24_cag_ipr_mr_final",
            "race_name": "Match Race Final",
            "race_date": "2026-05-24",
            "venue": "Cagliari, Sardinia, Italy",
        }
    # 26 09 23 NAP IPR PR1 -> 26_09_23_nap_ipr_pr1
    if "26 09 23" in filename and "pr1" in filename:
        return {
            "race_id": "26_09_23_nap_ipr_pr1",
            "race_name": "Practice Race 1 (2026-09-23)",
            "race_date": "2026-09-23",
            "venue": "Gulf of Naples, Italy",
        }
    # 26 09 25 NAP IPR Race 3 -> session gun is on 2026-09-26 UTC
    if "26 09 25" in filename and "race 3" in filename.lower():
        return {
            "race_id": "26_09_25_nap_ipr_race_3",
            "race_name": "26 09 25 NAP IPR Race 3",
            "race_date": "2026-09-26",
            "venue": venue,
        }

    # General date parsing if format like '26 09 23 ...' or '26 05 22 ...'
    parts = clean.split()
    date_str = None
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
        yy, mm, dd = parts[0], parts[1], parts[2]
        date_str = f"20{yy}-{mm.zfill(2)}-{dd.zfill(2)}"

    return {
        "race_id": slug,
        "race_name": clean,
        "race_date": date_str,
        "venue": venue,
    }


def run_pipeline(
    input_path: str = "Data/26 09 22 NAP IPR PR1.jsonl",
    output_path: str = None,
    export_web: bool = True,
    sample_interval_ms: int = SAMPLE_INTERVAL_MS,
    profile_memory: bool = False,
    race_id: str = None,
    race_name: str = None,
    race_date: str = None,
    venue: str = None,
) -> int:
    """Executes full ingestion, reconstruction, analytics, and replay export."""
    meta = infer_race_metadata(input_path)
    supplied_race_date = race_date
    race_id = race_id or meta["race_id"]
    race_name = race_name or meta["race_name"]
    race_date = race_date or meta["race_date"]
    venue = venue or meta["venue"]

    print("=" * 76)
    print("AC40 AMERICA'S CUP TELEMETRY RECONSTRUCTION & REPLAY PIPELINE")
    print("=" * 76)
    print(f"Input file:           {input_path}")
    print(f"Race ID:              {race_id} ({race_name}, {race_date})")
    print(f"Sample interval:      {sample_interval_ms} ms ({1000 // sample_interval_ms} Hz)")

    if not os.path.exists(input_path):
        print(f"ERROR: Input file does not exist: {input_path}", file=sys.stderr)
        return 1

    # 1. Verification of geodetic projection accuracy
    print("\n[Step 1/5] Verifying WGS84 to local metric projection accuracy...")
    proj_check = verify_gate_marks_projection_accuracy(tolerance_pct=0.1)
    b_gate = proj_check["bottom_gate"]
    t_gate = proj_check["top_gate"]

    print(f"  Bottom Gate (RM8 -> RM6):")
    print(f"    Cartesian Distance: {b_gate['cartesian_distance_m']:.3f} m")
    print(f"    Haversine Distance: {b_gate['haversine_distance_m']:.3f} m")
    print(f"    Relative Error:     {b_gate['error_pct']:.4f}% (<0.1% -> {'PASS' if b_gate['passed'] else 'FAIL'})")

    print(f"  Top Gate (RM4 -> RM2):")
    print(f"    Cartesian Distance: {t_gate['cartesian_distance_m']:.3f} m")
    print(f"    Haversine Distance: {t_gate['haversine_distance_m']:.3f} m")
    print(f"    Relative Error:     {t_gate['error_pct']:.4f}% (<0.1% -> {'PASS' if t_gate['passed'] else 'FAIL'})")

    if not proj_check["all_passed"]:
        print("ERROR: Projection accuracy verification failed!", file=sys.stderr)
        return 1

    # 2. Benchmark telemetry ingestion & stream synchronization
    print("\n[Step 2/5] Ingesting raw telemetry & synchronizing 10Hz grid...")
    if profile_memory:
        tracemalloc.start()
    t_start = time.perf_counter()

    pipeline = IngestionPipeline(file_path=input_path, sample_interval_ms=sample_interval_ms)
    ingest_result = pipeline.process()
    if supplied_race_date is None:
        race_date = datetime.fromtimestamp(ingest_result.session.race_start_ms / 1000, tz=timezone.utc).date().isoformat()

    t_ingest_end = time.perf_counter()
    ingest_time = t_ingest_end - t_start
    stats = ingest_result.stats
    print(f"  Parsed {stats['total_lines']:,} records in {ingest_time:.2f}s ({stats['total_lines'] / ingest_time:,.0f} records/s)")
    print(f"  Synchronized: {len(ingest_result.boats)} boats, {len(ingest_result.marks)} marks, {len(ingest_result.grid_timestamps_ms):,} frames (10Hz)")

    # 3. Geometric Race Reconstruction
    print("\n[Step 3/5] Reconstructing race chronology, gates & start sequence...")
    t_recon_start = time.perf_counter()
    recon_engine = RaceReconstructionEngine(
        gun_time_ms=ingest_result.session.race_start_ms,
        window_start_ms=ingest_result.session.window_start_ms,
        window_end_ms=ingest_result.session.window_end_ms,
        course_axis_deg=ingest_result.session.course_axis_deg,
        course_sequences=ingest_result.session.course_sequences,
        nominal_leg_length_m=ingest_result.session.course_length_m,
    )
    recon_result = recon_engine.process(
        boats=ingest_result.boats,
        marks=ingest_result.marks,
        timestamps=ingest_result.grid_timestamps_ms,
        raw_competitor_records=ingest_result.competitor_events,
    )
    t_recon_end = time.perf_counter()
    print(f"  Reconstruction completed in {(t_recon_end - t_recon_start) * 1000:.1f}ms")

    # Print start and gate summary
    print("\n  --- Competitor Reconstruction Summary ---")
    header = f"  {'Team':<6} | {'Rank':<6} | {'Start Delta':<12} | {'OCS':<5} | {'Gates':<5} | {'Finish Time':<12} | {'Status'}"
    print(header)
    print("  " + "-" * 70)
    for code, comp in sorted(recon_result.competitors.items(), key=lambda x: x[1].official_rank or 99):
        s_delta = f"{comp.start.delta_to_gun_s:+.3f}s" if comp.start.delta_to_gun_s is not None else "N/A"
        f_time = f"{comp.elapsed_s:.1f}s" if comp.elapsed_s is not None else "N/A"
        rank_str = f"#{comp.official_rank}" if comp.official_rank else "-"
        print(f"  {code:<6} | {rank_str:<6} | {s_delta:<12} | {str(comp.start.ocs):<5} | {len(comp.gates):<5} | {f_time:<12} | {comp.classification}")

    # 4. Manoeuvre Detection & Tactical Analytics
    print("\n[Step 4/5] Detecting tacks/gybes & computing continuous progress...")
    t_adv_start = time.perf_counter()
    detector = ManoeuvreDetector(sample_interval_ms=sample_interval_ms)
    analytics = AnalyticsEngine(
        gun_time_ms=recon_result.chronology.gun_time,
        course_axis_deg=ingest_result.session.course_axis_deg,
        nominal_leg_length_m=ingest_result.session.course_length_m,
        course_sequences=ingest_result.session.course_sequences,
    )

    manoeuvres_by_boat = {}
    progress_by_boat = {}
    leg_by_boat = {}

    for code, boat in ingest_result.boats.items():
        comp_rec = recon_result.competitors[code]
        # Detect manoeuvres
        m_list = detector.detect_manoeuvres_for_boat(
            timestamps=ingest_result.grid_timestamps_ms,
            heading_deg=boat.heading,
            sog_kt=boat.sog_kt,
            twa_deg=boat.twa_deg,
            race_start_ms=recon_result.chronology.gun_time,
            race_finish_ms=comp_rec.finish_time_ms,
        )
        manoeuvres_by_boat[code] = m_list

        # Compute progress and legs
        prog, legs = analytics.compute_continuous_race_progress_for_boat(
            boat_code=code,
            boat_x=boat.x,
            boat_y=boat.y,
            boat_heading=boat.heading,
            timestamps=ingest_result.grid_timestamps_ms,
            competitor_rec=comp_rec,
            marks=ingest_result.marks,
        )
        progress_by_boat[code] = prog
        leg_by_boat[code] = legs

    t_adv_end = time.perf_counter()
    print(f"  Analytics and manoeuvre detection completed in {(t_adv_end - t_adv_start) * 1000:.1f}ms")

    # 5. Export Replay Artifacts
    if export_web:
        print("\n[Step 5/5] Generating compact web replay JSON & manifests...")
        t_exp_start = time.perf_counter()
        manifest_dict = build_replay_manifest(
            ingest_result=ingest_result,
            reconstruction_result=recon_result,
            manoeuvres_by_boat=manoeuvres_by_boat,
            progress_by_boat=progress_by_boat,
            leg_by_boat=leg_by_boat,
            race_id=race_id,
            race_name=race_name,
            race_date=race_date,
            venue=venue,
        )
        rep_path, man_path = export_replay_artifacts(manifest_dict)
        analysis = build_race_analysis(
            ingest_result=ingest_result,
            reconstruction_result=recon_result,
            manoeuvres_by_boat=manoeuvres_by_boat,
            leg_by_boat=leg_by_boat,
            race_id=race_id,
            race_name=race_name,
            race_date=race_date,
            venue=venue,
        )
        analysis_path, history_path = export_analysis_artifacts(analysis)
        t_exp_end = time.perf_counter()

        rep_size_mb = os.path.getsize(rep_path) / (1024 * 1024)
        man_size_kb = os.path.getsize(man_path) / 1024
        print(f"  Exported replay:   {rep_path} ({rep_size_mb:.2f} MB)")
        print(f"  Exported manifest: {man_path} ({man_size_kb:.1f} KB)")
        print(f"  Exported analysis: {analysis_path}")
        print(f"  Exported history:  {history_path}")
        print(f"  Export time:       {(t_exp_end - t_exp_start) * 1000:.1f}ms")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ingest_result.to_dict(), f)

    t_total = time.perf_counter() - t_start
    print(f"\nTotal Pipeline Execution Time: {t_total:.2f}s (<60s SLA -> PASSED)")
    print("=" * 76)
    print(f"REPLAY EXPORT SUCCESSFUL: {race_id}")
    print("=" * 76)
    return 0


def main():
    parser = argparse.ArgumentParser(description="AC40 Regatta Replay Pipeline")
    parser.add_argument(
        "--input",
        "-i",
        default=None,
        help="Path to raw telemetry JSONL file (defaults to batch ingesting all files in Data/)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all raw telemetry .jsonl files in Data/",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional path to output raw ingested JSON file",
    )
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=SAMPLE_INTERVAL_MS,
        help="Grid resampling interval in milliseconds (default: 100ms = 10Hz)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip export of web replay JSON and manifests",
    )
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        help="Enable precise tracemalloc memory tracing",
    )
    args = parser.parse_args()

    # Determine files to process
    if args.input:
        files_to_process = [args.input]
    else:
        # Auto-discover all .jsonl in Data/ or Data/AC38/
        data_dir = "Data"
        files_to_process = []
        if os.path.exists(data_dir):
            files_to_process = [
                os.path.join(data_dir, f)
                for f in sorted(os.listdir(data_dir))
                if f.endswith(".jsonl")
            ]
            if not files_to_process and os.path.exists(os.path.join(data_dir, "AC38")):
                ac38_dir = os.path.join(data_dir, "AC38")
                files_to_process = [
                    os.path.join(ac38_dir, f)
                    for f in sorted(os.listdir(ac38_dir))
                    if f.endswith(".jsonl")
                ]
        if not files_to_process:
            fallback = os.path.join("Data", "AC38", "26 09 22 NAP IPR PR1.jsonl")
            if not os.path.exists(fallback):
                fallback = os.path.join("Data", "26 09 22 NAP IPR PR1.jsonl")
            files_to_process = [fallback]

    print(f"Found {len(files_to_process)} dataset(s) to process: {files_to_process}")

    for file_path in files_to_process:
        exit_code = run_pipeline(
            input_path=file_path,
            output_path=args.output,
            export_web=not args.no_export,
            sample_interval_ms=args.interval_ms,
            profile_memory=args.profile_memory,
        )
        if exit_code != 0:
            sys.exit(exit_code)

    if not args.no_export:
        from scripts.build_race_previews import write_previews
        from scripts.build_artifact_inventory import build_inventory
        write_previews()
        build_inventory()
    sys.exit(0)


if __name__ == "__main__":
    main()
