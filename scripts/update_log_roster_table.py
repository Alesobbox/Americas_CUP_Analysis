"""Format 2x3 roster sensitivity tables into docs/precision_upgrade_log.md."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
doc = json.loads((root / ".forecast" / "qa" / "roster_sensitivity_2x3.json").read_text(encoding="utf-8"))

names = {
    "ETNZ": "Emirates Team New Zealand",
    "GB1": "INEOS Britannia",
    "LUNA_ROSSA": "Luna Rossa Prada Pirelli",
    "ALINGHI": "Tudor Team Alinghi",
    "LA_ROCHE_POSAY": "La Roche-Posay Racing",
    "ARC_USA": "ARC Team USA",
    "AUSTRALIA": "Team Australia"
}

lines = []
lines.append("### 1. Syndicate Roster Policy Sensitivity Comparison ($2 \\times 3$ Grid: $A \\Sigma A^\\top$)")
lines.append("Evaluates `pooled_entry` vs. `event_entry` (correlated prior $\\rho_{\\text{event}} = 0.85$ across Cagliari and Naples) across all three declared combination policies (`equal`, `principal_only`, `assumed_10_02`):\n")

lines.append("#### A. Pooled-Entry Mode (`entry_id_mode = 'pooled_entry'`)\n")
lines.append("| Syndicate | Team ID | Equal Mean (SD) | Principal Only Mean (SD) | Assumed 10/12 Mean (SD) | Baseline Bounds [Equal] | Baseline Bounds [Principal] |")
lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
for team in ["ETNZ", "GB1", "LUNA_ROSSA", "ALINGHI", "LA_ROCHE_POSAY", "ARC_USA", "AUSTRALIA"]:
    eq = doc["pooled_entry"]["equal"]["teams"][team]
    pr = doc["pooled_entry"]["principal_only"]["teams"][team]
    as10 = doc["pooled_entry"]["assumed_10_02"]["teams"][team]
    lines.append(f"| {names[team]} | `{team}` | {eq['mean']:+.4f} ({eq['sd']:.4f}) | {pr['mean']:+.4f} ({pr['sd']:.4f}) | {as10['mean']:+.4f} ({as10['sd']:.4f}) | [{eq['lower']:.4f}, {eq['upper']:.4f}] | [{pr['lower']:.4f}, {pr['upper']:.4f}] |")

lines.append("\n#### B. Event-Entry Mode (`entry_id_mode = 'event_entry'`, $\\rho_{\\text{event}} = 0.85$)\n")
lines.append("| Syndicate | Team ID | Equal Mean (SD) | Principal Only Mean (SD) | Assumed 10/12 Mean (SD) | Baseline Bounds [Equal] | Baseline Bounds [Principal] |")
lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
for team in ["ETNZ", "GB1", "LUNA_ROSSA", "ALINGHI", "LA_ROCHE_POSAY", "ARC_USA", "AUSTRALIA"]:
    eq = doc["event_entry"]["equal"]["teams"][team]
    pr = doc["event_entry"]["principal_only"]["teams"][team]
    as10 = doc["event_entry"]["assumed_10_02"]["teams"][team]
    lines.append(f"| {names[team]} | `{team}` | {eq['mean']:+.4f} ({eq['sd']:.4f}) | {pr['mean']:+.4f} ({pr['sd']:.4f}) | {as10['mean']:+.4f} ({as10['sd']:.4f}) | [{eq['lower']:.4f}, {eq['upper']:.4f}] | [{pr['lower']:.4f}, {pr['upper']:.4f}] |")

lines.append("\n*Finding*: Single-entry syndicates are mathematically invariant to the roster policy within each mode. For dual-entry syndicates, `event_entry` models inter-regatta crew adjustments via the $\\rho_{\\text{event}} = 0.85$ precision matrix and weights entries by observed competitive races, yielding narrower posterior standard deviations than raw pooling while preserving the senior boat performance premium under `principal_only`.")

table_text = "\n".join(lines)

log_path = root / "docs" / "precision_upgrade_log.md"
content = log_path.read_text(encoding="utf-8")
sec1_header = "### 1. Syndicate Roster Policy Sensitivity Comparison ($A \\Sigma A^\\top$)"
sec2_header = "### 2. Empirical AC37-to-AC38 Joint Transfer Model Posterior"

if sec1_header in content and sec2_header in content:
    pre = content.split(sec1_header)[0]
    post = content.split(sec2_header)[1]
    new_content = pre + table_text + "\n\n" + sec2_header + post
    log_path.write_text(new_content, encoding="utf-8")
    print("Successfully updated docs/precision_upgrade_log.md with 2x3 grid!")
else:
    print("Could not find section headers in log file.")
