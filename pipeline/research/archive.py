"""Publish coherent AC38 statistical, wind and timing research artifacts."""

import json
import logging
from pathlib import Path
from pipeline.historical_analysis import build_historical_index
from pipeline.polar.reference import HeldOutReference
from .polar_experiments import experiment_input_hash, run_polar_experiments
from .timing_research import build_timing_research
from .wind_forecast import run_wind_forecast
from .wind_forecast_io import load_wind_records

LOGGER = logging.getLogger(__name__)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, separators=(",", ":"), allow_nan=False)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(content, encoding="utf8")
    temporary.replace(path)


def _experiments(details, data):
    path = data / "research" / "polar_experiments.json"
    if path.is_file():
        report = json.loads(path.read_text(encoding="utf8"))
        if report.get("input_sha256") == experiment_input_hash(details, data):
            return report
    report = run_polar_experiments(details, data)
    _write(path, report)
    return report


def _timing(details, data):
    reference = HeldOutReference(details)
    counts = {
        "races": len(details),
        "boats": 0,
        "complete_ledgers": 0,
        "turn_candidates": 0,
        "complete_horizons": 0,
        "censored_horizons": 0,
    }
    for rid, detail in details.items():
        replay = json.loads((data / "replays" / (rid + ".json")).read_text(encoding="utf8"))
        report = build_timing_research(detail, replay, reference)
        detail["timing_research"] = report
        for boat in report["boats"]:
            counts["boats"] += 1
            counts["complete_ledgers"] += int(boat["ledger"].get("complete_finish", False))
            counts["turn_candidates"] += len(boat["turns"])
            for event in boat["turns"]:
                for horizon in event.get("horizons", []):
                    key = "censored_horizons" if horizon["right_censored"] else "complete_horizons"
                    counts[key] += 1
    return {
        "schema_version": "timing-research-summary-1",
        "counts": counts,
        "scope": "Observed checkpoint accounting and reference-dependent progress deficits; no causal attribution",
    }


def refresh_research(details, root):
    root, data = Path(root), Path(root) / "public" / "data"
    LOGGER.info("Rebuilding sample-level polar and refitted uncertainty")
    index = build_historical_index(
        str(data / "manifests.json"), str(data / "analysis"), update_details=True
    )
    details = {
        rid: json.loads((data / "analysis" / (rid + ".json")).read_text(encoding="utf8"))
        for rid in details
    }
    LOGGER.info("Evaluating AC38 model, wind-source and environmental comparisons")
    index["polar_research"] = _experiments(details, data)
    LOGGER.info("Evaluating chronological wind forecasts")
    wind = run_wind_forecast(load_wind_records(details, root))
    index["wind_forecast_model"] = {key: value for key, value in wind.items() if key != "per_race"}
    _write(data / "research" / "wind_forecast.json", wind)
    LOGGER.info("Rebuilding exact timing ledgers and supported manoeuvre references")
    index["timing_research"] = _timing(details, data)
    _write(data / "research" / "timing_summary.json", index["timing_research"])
    for rid, detail in details.items():
        detail["wind_forecast"] = wind["per_race"].get(rid)
        _write(data / "analysis" / (rid + ".json"), detail)
    from .provenance import receipt_for

    index["research_provenance"] = receipt_for(details, data)
    _write(data / "research" / "receipt.json", index["research_provenance"])
    _write(data / "analysis" / "index.json", index)
    from scripts.build_artifact_inventory import build_inventory

    build_inventory(root)
    LOGGER.info("Research refresh complete: %s", index["timing_research"]["counts"])
    return index
