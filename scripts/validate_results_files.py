"""Validate AC37 and AC38 results files against verified reference anchors."""
import json
from pathlib import Path
import sys


def validate_results():
    root = Path(__file__).resolve().parent.parent

    # 1. Load Anchors
    anchors_path = root / "docs" / "ac37_verified_anchors.json"
    if not anchors_path.exists():
        print(f"Error: {anchors_path} not found.", file=sys.stderr)
        sys.exit(1)
    anchors_doc = json.loads(anchors_path.read_text(encoding="utf-8"))
    if anchors_doc.get("schema_version") != "ac37-verified-anchors-1":
        print(f"Error: unexpected anchors schema {anchors_doc.get('schema_version')}", file=sys.stderr)
        sys.exit(1)
    anchors = anchors_doc["anchors"]

    # 2. Load AC37 results
    ac37_path = root / "docs" / "ac37_results.json"
    if not ac37_path.exists():
        print(f"Error: {ac37_path} not found.", file=sys.stderr)
        sys.exit(1)
    ac37_doc = json.loads(ac37_path.read_text(encoding="utf-8"))
    if ac37_doc.get("schema_version") != "ac37-results-1":
        print(f"Error: unexpected ac37 results schema {ac37_doc.get('schema_version')}", file=sys.stderr)
        sys.exit(1)

    # 3. Tally AC37 series wins
    series_wins = {}
    for r in ac37_doc.get("races", []):
        st = r["stage"]
        series_wins.setdefault(st, {})
        w = r["winner"]
        series_wins[st][w] = series_wins[st].get(w, 0) + 1

    # Verify against anchors
    for key, anchor in anchors.items():
        if key not in series_wins:
            print(f"Error: stage {key} missing from ac37_results.json", file=sys.stderr)
            sys.exit(1)
        wins = series_wins[key]
        score_a = wins.get(anchor["team_a"], 0)
        score_b = wins.get(anchor["team_b"], 0)
        if score_a != anchor["score_a"] or score_b != anchor["score_b"]:
            print(f"Error in {key}: expected {anchor['team_a']} {anchor['score_a']} - {anchor['score_b']} {anchor['team_b']}, got {score_a} - {score_b}", file=sys.stderr)
            sys.exit(1)
        actual_winner = anchor["team_a"] if score_a > score_b else anchor["team_b"]
        if actual_winner != anchor["winner"]:
            print(f"Error in {key}: winner mismatch: expected {anchor['winner']}, got {actual_winner}", file=sys.stderr)
            sys.exit(1)
        print(f"  [OK] {anchor['series']}: {anchor['team_a']} {score_a} - {score_b} {anchor['team_b']} (Winner: {anchor['winner']})")

    # 4. Check official AC38 prelims file
    prelims_path = root / "docs" / "official_results_ac38_prelims.json"
    if not prelims_path.exists():
        print(f"Error: {prelims_path} not found.", file=sys.stderr)
        sys.exit(1)
    prelims_doc = json.loads(prelims_path.read_text(encoding="utf-8"))
    if prelims_doc.get("schema_version") != "official-results-2":
        print(f"Error: unexpected prelims schema {prelims_doc.get('schema_version')}", file=sys.stderr)
        sys.exit(1)
    races = prelims_doc.get("races", [])
    if len(races) != 18:
        print(f"Error: expected 18 competitive prelim races, found {len(races)}", file=sys.stderr)
        sys.exit(1)
    print(f"  [OK] AC38 Prelims: 18 official race results verified")

    print("\nAll AC37 and AC38 results files verified successfully against anchors!")
    sys.exit(0)


if __name__ == "__main__":
    validate_results()
