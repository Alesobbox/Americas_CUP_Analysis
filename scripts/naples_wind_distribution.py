"""Extract and summarize observed race-session wind distribution for Naples September 2026."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def circular_mean_deg(angles_deg):
    if not angles_deg:
        return 0.0
    rads = np.radians(angles_deg)
    sin_sum = np.sum(np.sin(rads))
    cos_sum = np.sum(np.cos(rads))
    mean_rad = math.atan2(sin_sum, cos_sum)
    return float(np.degrees(mean_rad) % 360.0)


def extract_naples_wind():
    ac38_dir = ROOT / "Data" / "AC38"
    naples_files = sorted(list(ac38_dir.glob("26 09 *.jsonl")))
    print(f"Found {len(naples_files)} Naples session files...")

    all_tws_kt = []
    all_twd_deg = []
    session_summaries = {}

    for f in naples_files:
        session_tws = []
        session_twd = []
        official_wind_id = None
        
        with f.open("r", encoding="utf-8", errors="ignore") as fp:
            for line_idx, line in enumerate(fp):
                if line_idx > 80000:
                    break
                try:
                    obj = json.loads(line)
                    session = obj.get("session")
                    if session and not official_wind_id:
                        official_wind_id = session.get("official_wind_asset_id")

                    tel = obj.get("telemetry")
                    if not tel:
                        continue
                    aid = tel.get("asset_id")
                    
                    # If official wind asset is available, prefer it; otherwise sample all wind
                    if "true_wind_speed" in tel:
                        val = tel["true_wind_speed"].get("value")
                        if val is not None:
                            spd_kt = float(val) * 1.943844
                            if 0.0 <= spd_kt <= 45.0:
                                if official_wind_id is None or aid == official_wind_id:
                                    session_tws.append(spd_kt)
                    if "true_wind_direction" in tel:
                        val = tel["true_wind_direction"].get("value")
                        if val is not None:
                            deg = float(val) % 360.0
                            if official_wind_id is None or aid == official_wind_id:
                                session_twd.append(deg)
                except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                    continue

        if session_tws:
            tws_arr = np.array(session_tws)
            all_tws_kt.extend(session_tws)
            all_twd_deg.extend(session_twd)
            session_summaries[f.name] = {
                "tws_samples": len(session_tws),
                "tws_mean_kt": round(float(np.mean(tws_arr)), 2),
                "tws_sd_kt": round(float(np.std(tws_arr)), 2),
                "tws_p50_kt": round(float(np.percentile(tws_arr, 50)), 2),
                "twd_mean_deg": round(circular_mean_deg(session_twd), 1) if session_twd else None,
            }

    if not all_tws_kt:
        print("No wind records found!")
        return

    tws_all = np.array(all_tws_kt)
    out = {
        "schema_version": "naples-observed-wind-1",
        "description": "Observed September 2026 Race-Session Wind Distribution (Weather-Selected Sample; Not May-July Climatology)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sessions_count": len(naples_files),
        "total_tws_samples": len(all_tws_kt),
        "tws_kt": {
            "mean": round(float(np.mean(tws_all)), 2),
            "sd": round(float(np.std(tws_all)), 2),
            "p10": round(float(np.percentile(tws_all, 10)), 2),
            "p25": round(float(np.percentile(tws_all, 25)), 2),
            "p50": round(float(np.percentile(tws_all, 50)), 2),
            "p75": round(float(np.percentile(tws_all, 75)), 2),
            "p90": round(float(np.percentile(tws_all, 90)), 2),
        },
        "twd_deg": {
            "circular_mean": round(circular_mean_deg(all_twd_deg), 1),
            "prevailing_sector": "ENE (070-090)" if 60 <= circular_mean_deg(all_twd_deg) <= 100 else "Other"
        },
        "session_breakdown": session_summaries
    }

    out_dir = ROOT / ".forecast" / "wind"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "naples_observed_session_wind.json"
    out_file.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Naples wind distribution written to: {out_file}")
    print(f"  TWS mean: {out['tws_kt']['mean']} kt (SD: {out['tws_kt']['sd']} kt)")
    print(f"  TWS P10-P90: [{out['tws_kt']['p10']}, {out['tws_kt']['p90']}] kt, median: {out['tws_kt']['p50']} kt")
    print(f"  TWD circular mean: {out['twd_deg']['circular_mean']} deg")


if __name__ == "__main__":
    extract_naples_wind()
