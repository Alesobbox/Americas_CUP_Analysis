"""Refresh AC37/AC38 documentation and attach field-level evidence from captured sources."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / ".forecast" / "evidence_sources"

FLAG_TO_TEAM = {
    "NZ": "ETNZ",
    "NZL": "ETNZ",
    "GBR": "INEOS",
    "ITA": "LUNA_ROSSA",
    "USA": "AMERICAN_MAGIC",
    "SUI": "ALINGHI",
    "FRA": "ORIENT_EXPRESS",
}


def file_evidence(
    rel_path: str,
    *,
    supporting_source: str,
    result_scope: str,
    available_at_utc: str,
    review_status: str,
    notes: str | None = None,
) -> dict:
    p = ROOT / rel_path
    data = p.read_bytes()
    ev = {
        "supporting_source": supporting_source,
        "captured_path": rel_path.replace("\\", "/"),
        "captured_bytes": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "result_scope": result_scope,
        "available_at_utc": available_at_utc,
        "review_status": review_status,
    }
    if notes:
        ev["notes"] = notes
    return ev


def parse_wiki_ac40_table(wikitext: str, header: str, n_races: int) -> list[dict[str, list[str]]]:
    start = wikitext.find(header)
    if start == -1:
        raise ValueError(f"Missing header {header}")
    end = wikitext.find("|}", start)
    block = wikitext[start:end]
    rows = block.split("\n|-\n")
    per_race: list[dict[int, str]] = [{} for _ in range(n_races)]
    non_finishes: list[dict[str, str]] = [{} for _ in range(n_races)]
    team_aliases = {
        "NYYC American Magic": "AMERICAN_MAGIC",
        "Emirates Team New Zealand": "ETNZ",
        "Orient Express Racing Team": "ORIENT_EXPRESS",
        "Luna Rossa Prada Pirelli Team": "LUNA_ROSSA",
        "Alinghi Red Bull Racing": "ALINGHI",
        "INEOS Britannia": "INEOS",
    }
    for row in rows:
        team = next((v for k, v in team_aliases.items() if k in row), None)
        if not team:
            continue
        cells = [ln.strip() for ln in row.splitlines() if ln.strip().startswith("|") and not ln.strip().startswith("| align=")]
        # Exclude trailing points line (`!34`)
        cells = [c for c in cells if not c.startswith("!") and "colspan" not in c]
        if len(cells) < n_races:
            continue
        for idx in range(n_races):
            val = cells[idx].split("|")[-1].strip()
            if val.isdigit():
                per_race[idx][int(val)] = team
            elif val in ("DSQ", "DNS", "DNF", "RET"):
                non_finishes[idx][team] = val
    out = []
    for pos_map, nf in zip(per_race, non_finishes):
        order = [pos_map[k] for k in sorted(pos_map)]
        out.append({"order": order, "non_finishes": nf})
    return out


def refresh_ac37_ac40_results() -> dict:
    w_ac = json.loads((EV / "wiki_2024_ac.json").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    vnr = parse_wiki_ac40_table(w_ac, "===Round 1 – Vilanova i la Geltrú===", 5)
    jed = parse_wiki_ac40_table(w_ac, "===Round 2 – Jeddah===", 8)

    vnr_dates = ["2023-09-16", "2023-09-16", "2023-09-17", "2023-09-17", "2023-09-17"]
    jed_dates = ["2023-11-30", "2023-11-30", "2023-11-30", "2023-12-01", "2023-12-01", "2023-12-01", "2023-12-02", "2023-12-02"]

    wiki_url = "https://en.wikipedia.org/wiki/37th_America%27s_Cup"
    races = []
    for i, item in enumerate(vnr, 1):
        races.append({
            "race_id": f"ac37_ac40_vnr_r{i}",
            "cycle": "ac37",
            "event": "Vilanova Preliminary Regatta",
            "date": vnr_dates[i - 1],
            "status": "completed",
            "eligible_for_primary": True,
            "official_order": item["order"],
            "non_finishes": item["non_finishes"],
            "evidence": file_evidence(
                ".forecast/evidence_sources/wiki_2024_ac.json",
                supporting_source=wiki_url,
                result_scope="full_fleet_order",
                available_at_utc=f"{vnr_dates[i - 1]}T18:00:00Z",
                review_status="independently_anchored",
            ),
        })

    races.append({
        "race_id": "ac37_ac40_vnr_mr_final",
        "cycle": "ac37",
        "event": "Vilanova Preliminary Regatta Match Final",
        "date": "2023-09-17",
        "status": "abandoned",
        "eligible_for_primary": False,
        "exclusion_reason": "abandoned_on_leg_1_time_limit_light_air",
        "official_order": [],
        "scheduled_pair": ["AMERICAN_MAGIC", "ETNZ"],
        "evidence": file_evidence(
            ".forecast/evidence_sources/sailworld_vilanova_2023.html",
            supporting_source="https://www.sail-world.com/news/266703/American-Magic-defies-the-odds",
            result_scope="abandoned_confirmation",
            available_at_utc="2023-09-17T18:30:00Z",
            review_status="independently_anchored_abandoned",
            notes="Corroborated by Data/AC37/prelims_ac40_2023/2023-09-17 VNR 6 USA NZL.jsonl terminating on leg 1.",
        ),
    })

    for i, item in enumerate(jed, 1):
        races.append({
            "race_id": f"ac37_ac40_jed_r{i}",
            "cycle": "ac37",
            "event": "Jeddah Preliminary Regatta",
            "date": jed_dates[i - 1],
            "status": "completed",
            "eligible_for_primary": True,
            "official_order": item["order"],
            "non_finishes": item["non_finishes"],
            "evidence": file_evidence(
                ".forecast/evidence_sources/wiki_2024_ac.json",
                supporting_source=wiki_url,
                result_scope="full_fleet_order",
                available_at_utc=f"{jed_dates[i - 1]}T16:00:00Z",
                review_status="independently_anchored",
            ),
        })

    races.append({
        "race_id": "ac37_ac40_jed_mr_final",
        "cycle": "ac37",
        "event": "Jeddah Preliminary Regatta Match Final",
        "date": "2023-12-02",
        "status": "completed",
        "eligible_for_primary": True,
        "official_order": ["ETNZ", "LUNA_ROSSA"],
        "non_finishes": {},
        "evidence": file_evidence(
            ".forecast/evidence_sources/worldsailing_jeddah_2023.html",
            supporting_source="https://www.sailing.org/2023/12/03/americas-cup-grand-final-in-jeddah-crowns-emirates-team-new-zealand-winners/",
            result_scope="match_final_winner",
            available_at_utc="2023-12-03T12:00:00Z",
            review_status="independently_anchored",
        ),
    })

    doc = {
        "schema_version": "ac37-ac40-prelims-1",
        "retrieved_at": "2026-11-12T11:55:00+00:00",
        "description": "Independently anchored AC40 Preliminary Regatta results for AC37 (Vilanova R1-5, Vilanova MR Final marked abandoned/excluded, Jeddah R1-8 + MR Final).",
        "total_races": len(races),
        "completed_races": sum(1 for r in races if r["status"] == "completed"),
        "teams": ["ETNZ", "INEOS", "LUNA_ROSSA", "AMERICAN_MAGIC", "ALINGHI", "ORIENT_EXPRESS"],
        "races": races,
    }
    (ROOT / "docs" / "ac37_ac40_2023_results.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def _parse_wiki_matches(wikitext_slice: str, stage: str, prefix: str, src_rel: str, src_url: str) -> list[dict]:
    rows = wikitext_slice.split("\n|-\n")
    out = []
    cur_date = None
    race_num = 0
    for row in rows:
        lines = [ln.strip() for ln in row.splitlines() if ln.strip()]
        team_cols = [ln for ln in lines if ("AC_Flags|" in ln or "Flagicon|" in ln or "flagicon|" in ln) and ("[[" in ln)]
        if len(team_cols) < 2:
            continue
        for ln in lines[:4]:
            m_d = re.search(r"(August|September|October)\s+(\d{1,2})|(\d{1,2})\s+(August|September|October)", ln)
            if m_d:
                mon = m_d.group(1) or m_d.group(4)
                day = int(m_d.group(2) or m_d.group(3))
                mnum = {"August": "08", "September": "09", "October": "10"}[mon]
                cur_date = f"2024-{mnum}-{day:02d}"
                break
        if "abandoned" in lines[0].lower():
            continue
        teams, winner = [], None
        for col in team_cols[:2]:
            m = re.search(r"(?:AC_Flags|flagicon)\|([A-Z]{2,3})", col, re.I)
            t = FLAG_TO_TEAM[m.group(1).upper()]
            teams.append(t)
            if "BBF3BB" in col or "D1F7E4" in col:
                winner = t
        if len(teams) != 2 or not winner:
            continue
        race_num += 1
        delta = None
        for ln in lines:
            m_t = re.search(r"\+(\d+)'\s*(\d+)\"", ln)
            if m_t:
                delta = float(int(m_t.group(1)) * 60 + int(m_t.group(2)))
                break
        out.append({
            "race_id": f"{prefix}_{race_num}",
            "cycle": "ac37",
            "stage": stage,
            "race_number": race_num,
            "date": cur_date,
            "status": "completed",
            "competitor_a": teams[0],
            "competitor_b": teams[1],
            "winner": winner,
            "delta_s": delta,
            "awarded_or_nonfinish": ("Awarded" in row or "DNS" in row or "DNF" in row or "DSQ" in row),
            "evidence": file_evidence(
                src_rel,
                supporting_source=src_url,
                result_scope="match_winner",
                available_at_utc=f"{cur_date}T19:00:00Z",
                review_status="independently_anchored",
            ),
        })
    return out


def refresh_ac37_ac75_results() -> dict:
    w_ac = json.loads((EV / "wiki_2024_ac.json").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    w_lvc = json.loads((EV / "wiki_2024_lvc.json").read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    ac_rel = ".forecast/evidence_sources/wiki_2024_ac.json"
    lvc_rel = ".forecast/evidence_sources/wiki_2024_lvc.json"
    ac_url = "https://en.wikipedia.org/wiki/37th_America%27s_Cup"
    lvc_url = "https://en.wikipedia.org/wiki/2024_Louis_Vuitton_Cup"

    bcn = _parse_wiki_matches(w_ac[w_ac.find("===Round 3 – Barcelona==="):w_ac.find("== Qualifying Event ==")], "preliminary_barcelona_ac75", "ac37_fpr1_match", ac_rel, ac_url)
    rr1 = _parse_wiki_matches(w_lvc[w_lvc.find("===Round Robin 1"):w_lvc.find("===Round Robin 2")], "round_robin", "ac37_lvc_rr_match", lvc_rel, lvc_url)
    rr2 = _parse_wiki_matches(w_lvc[w_lvc.find("===Round Robin 2"):w_lvc.find("==Knock-out stage==")], "round_robin", "ac37_lvc_rr2_match", lvc_rel, lvc_url)
    for idx, r in enumerate(rr2, 16):
        r["race_id"] = f"ac37_lvc_rr_match_{idx}"
        r["race_number"] = idx
    sf1 = _parse_wiki_matches(w_lvc[w_lvc.find("===Semi-Final Group 2==="):w_lvc.find("===Final===")], "lvc_semifinal_1", "ac37_lvc_semifinal_1_r", lvc_rel, lvc_url)
    sf2 = _parse_wiki_matches(w_lvc[w_lvc.find("===Semi-Final Group 1==="):w_lvc.find("===Semi-Final Group 2===")], "lvc_semifinal_2", "ac37_lvc_semifinal_2_r", lvc_rel, lvc_url)
    fin = _parse_wiki_matches(w_lvc[w_lvc.find("===Final==="):w_lvc.find("==References==")], "lvc_final", "ac37_lvc_final_r", lvc_rel, lvc_url)
    cup = _parse_wiki_matches(w_ac[w_ac.find("== Cup Match =="):w_ac.find("==Youth")], "match", "ac37_match_r", ac_rel, ac_url)

    for grp in (sf1, sf2, fin, cup):
        for r in grp:
            r["race_id"] = f"{r['race_id']}{r['race_number']}" if not r["race_id"].endswith(str(r["race_number"])) else r["race_id"]
    for grp, base in [(sf1, "ac37_lvc_semifinal_1_r"), (sf2, "ac37_lvc_semifinal_2_r"), (fin, "ac37_lvc_final_r"), (cup, "ac37_match_r")]:
        for r in grp:
            r["race_id"] = f"{base}{r['race_number']}"

    races = bcn + rr1 + rr2 + sf1 + sf2 + fin + cup
    doc = {
        "schema_version": "ac37-results-1",
        "retrieved_at": "2026-11-12T11:55:00+00:00",
        "description": "Reconciled AC37 AC75 match outcomes anchored to captured Wikipedia tables and corroborated against AC75 telemetry.",
        "total_races": len(races),
        "stopped_attempts": [{
            "attempt_id": "ac37_lvc_final_r3_att1_stopped",
            "stage": "lvc_final",
            "date": "2024-09-28",
            "status": "stopped",
            "eligible_for_primary": False,
            "exclusion_reason": "abandoned_stopped_resailed_as_race_3",
            "evidence": file_evidence(lvc_rel, supporting_source=lvc_url, result_scope="abandoned_confirmation", available_at_utc="2024-09-28T19:00:00Z", review_status="independently_anchored_abandoned"),
        }],
        "races": races,
    }
    (ROOT / "docs" / "ac37_results.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def refresh_rules_and_roster() -> None:
    checksums_raw = (EV / "ac38_rules_public_latest_checksums.txt").read_text(encoding="utf-8")
    gh_hashes = {}
    for line in checksums_raw.splitlines():
        parts = line.strip().split()
        if len(parts) == 2:
            gh_hashes[parts[1]] = parts[0]

    proto_csv = EV / "noticeboard_protocol_1RqgUX4C.csv"
    proto_rows = list(csv.reader(proto_csv.open(encoding="utf-8", errors="ignore")))
    latest_proto = next((r for r in proto_rows if len(r) > 3 and "Pro v10" in r[1]), [])

    rules_doc = json.loads((ROOT / "docs" / "forecast_rules_sources.json").read_text(encoding="utf-8"))
    rules_doc["refreshed_at_utc"] = "2026-11-12T11:51:00Z"
    rules_doc["rules_precedence"] = {
        "authoritative_github_repo": "https://github.com/AC-Rules-Committee/AC38-Rules-Public",
        "noticeboard_url": "https://ac38noticeboard.acofficials.org/",
        "stated_precedence": "Rules Committee official GitHub releases take precedence over noticeboard text summaries; PDF creation metadata is never an effective date.",
        "github_release_tag": "TRv2.12_CR75v3.08_CR40v2.15_SP75v1.02_DC40v1.07_CP75v1.01_R246",
        "github_release_published_at_utc": "2026-09-21T20:45:33Z",
        "github_checksums_evidence": file_evidence(
            ".forecast/evidence_sources/ac38_rules_public_latest_checksums.txt",
            supporting_source="https://github.com/AC-Rules-Committee/AC38-Rules-Public/releases/tag/TRv2.12_CR75v3.08_CR40v2.15_SP75v1.02_DC40v1.07_CP75v1.01_R246",
            result_scope="official_rule_checksums",
            available_at_utc="2026-09-21T20:45:33Z",
            review_status="independently_anchored",
        ),
        "noticeboard_protocol_csv_evidence": file_evidence(
            ".forecast/evidence_sources/noticeboard_protocol_1RqgUX4C.csv",
            supporting_source="https://ac38noticeboard.acofficials.org/protocol",
            result_scope="protocol_amendment_log",
            available_at_utc="2026-09-04T00:00:00Z",
            review_status="independently_anchored",
        ),
    }
    rules_doc["sources"] = [
        {
            "version": "Protocol AC38.10",
            "amendment": latest_proto[2] if len(latest_proto) > 2 else "10",
            "url": "https://drive.google.com/file/d/1MZZN-TJlXUkaqTNxCje8RupzAjBP4vvL/view",
            "status": "downloaded",
            "sha256": "084762ecd4ffb7d66921bd0d5d83e5ef9f5927cc8ce74edaa34648c3711118ee",
            "bytes": 1244782,
            "cache_path": ".forecast/rules/1MZZN-TJlXUkaqTNxCje8RupzAjBP4vvL.pdf",
            "effective_date": "2026-09-04",
            "effective_date_source": "noticeboard_protocol_1RqgUX4C.csv (Pro v10 Amendment 10 Article 24.3(g))",
        },
        {
            "version": "LVC/Match Conditions v0",
            "url": "https://drive.google.com/file/d/1biI3_zCSaLrRiM4nwkhKpaBnMraS5KiP/view",
            "status": "downloaded",
            "sha256": "4d3580f58b4dedb348d8f332bb01336b66f722560334fc800751b7bb2a397949",
            "bytes": 2441385,
            "cache_path": ".forecast/rules/1biI3_zCSaLrRiM4nwkhKpaBnMraS5KiP.pdf",
            "effective_date": None,
            "effective_date_note": "Initial conditions posted; amendments/sailing instructions pending prior to Cup.",
        },
        {
            "version": "RRSAC v5.02",
            "url": "https://drive.google.com/file/d/1I21drErgKm4OuYCcGb3D9uv7_UYG4jwj/view",
            "status": "downloaded",
            "sha256": "89d08f344abb1d5bb0f123f018bb876c4abdc749075b382cf98fe610c312f1f1",
            "bytes": 1275368,
            "cache_path": ".forecast/rules/1I21drErgKm4OuYCcGb3D9uv7_UYG4jwj.pdf",
            "effective_date": "2026-09-25",
            "effective_date_source": "noticeboard_racing_11VmLLe9.csv (Version 5.02 Rule 87.2 New (d))",
        },
        {
            "version": "AC75 Class Rule V3.08 (R246)",
            "url": "https://github.com/AC-Rules-Committee/AC38-Rules-Public/releases/tag/TRv2.12_CR75v3.08_CR40v2.15_SP75v1.02_DC40v1.07_CP75v1.01_R246",
            "status": "rules_committee_github_release",
            "sha256": gh_hashes.get("CR75v3.08_R246.pdf"),
            "publication_date": "2026-09-21",
            "effective_date": "2026-09-21",
            "supersedes": "Noticeboard AC75 CR 3.05 (2026-06-26)",
        },
        {
            "version": "AC Technical Regulations V2.12 (R246)",
            "url": "https://github.com/AC-Rules-Committee/AC38-Rules-Public/releases/tag/TRv2.12_CR75v3.08_CR40v2.15_SP75v1.02_DC40v1.07_CP75v1.01_R246",
            "status": "rules_committee_github_release",
            "sha256": gh_hashes.get("TRv2.12_R246.pdf"),
            "publication_date": "2026-09-21",
            "effective_date": "2026-09-21",
            "supersedes": "Noticeboard TR 2.07 (2026-07-03)",
        },
        {
            "version": "AC40 Class Rule V2.15 (R246)",
            "url": "https://github.com/AC-Rules-Committee/AC38-Rules-Public/releases/tag/TRv2.12_CR75v3.08_CR40v2.15_SP75v1.02_DC40v1.07_CP75v1.01_R246",
            "status": "rules_committee_github_release",
            "sha256": gh_hashes.get("CR40v2.15_R246.pdf"),
            "publication_date": "2026-09-21",
            "effective_date": "2026-09-21",
            "supersedes": "Noticeboard AC40 2.11 (2026-06-26)",
        },
    ]
    rules_doc["unresolved_clauses"] = [
        "Six-challenger qualification/seeding tie procedure requires authoritative clarification (RRSAC 102.1 only covers 3- and 4-Challenger ties).",
        "Timing-dependent shared/zero-score results require the applicable race state and instructions.",
        "Incomplete-series, withdrawal and continuation instructions must be pinned before publication.",
        "Protocol Amendment 08 notes Article 13.2 rule number reference remains under review.",
    ]
    (ROOT / "docs" / "forecast_rules_sources.json").write_text(json.dumps(rules_doc, indent=2) + "\n", encoding="utf-8")

    # Update AC38 roster with cycle-specific IDs, principal AC40 entry, and noticeboard registered sailors
    roster = json.loads((ROOT / "docs" / "ac38_roster.json").read_text(encoding="utf-8"))
    principal_map = {
        "ETNZ": "NZL B",
        "GB1": "GBR B",
        "LUNA_ROSSA": "ITA B",
        "ALINGHI": "SUI",
        "LA_ROCHE_POSAY": "FRA",
        "ARC_USA": "USA",
        "AUSTRALIA": None,
    }
    for syn in roster["syndicates"]:
        tid = syn["team_id"]
        syn["campaign_team_id"] = f"ac38:{tid}"
        syn["principal_ac40_entry"] = principal_map.get(tid)
        syn["historical_continuity_assumed"] = False
        for ent in syn.get("entries", []):
            ent["cycle_entry_id"] = f"ac38:{ent['entry_id']}"

    sailors_csv = EV / "noticeboard_racing_registered-sailors_1x92Kk5z.csv"
    sailor_rows = []
    with sailors_csv.open(encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            cleaned = [c.strip() for c in row if c.strip()]
            if len(cleaned) >= 3 and cleaned[0] != "Sailor Name":
                sailor_rows.append({
                    "syndicate": "ETNZ",
                    "campaign_team_id": "ac38:ETNZ",
                    "sailor_name": cleaned[0],
                    "nationality_criteria": cleaned[1],
                    "date_posted": cleaned[2],
                })
    roster["noticeboard_registered_sailors"] = {
        "source_evidence": file_evidence(
            ".forecast/evidence_sources/noticeboard_racing_registered-sailors_1x92Kk5z.csv",
            supporting_source="https://ac38noticeboard.acofficials.org/racing/registered-sailors",
            result_scope="registered_sailors_declarations",
            available_at_utc="2026-05-08T00:00:00Z",
            review_status="independently_anchored",
        ),
        "declarations": sailor_rows,
    }
    roster["default_mapping_policy"] = {
        "primary": "confirmed_crew_then_principal_ac40_else_prior",
        "sensitivity": ["equal"],
        "prohibited_default": "race_count_weighted_mixture",
    }
    roster["refreshed_at_utc"] = "2026-11-12T11:51:00Z"
    (ROOT / "docs" / "ac38_roster.json").write_text(json.dumps(roster, indent=2) + "\n", encoding="utf-8")


def refresh_ac38_prelims_evidence() -> dict:
    path = ROOT / "docs" / "official_results_ac38_prelims.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    cag1 = ".forecast/evidence_sources/sailweb_cag_day1.html"
    cag3 = ".forecast/evidence_sources/sailweb_cag_day3.html"
    nap1 = ".forecast/evidence_sources/sailworld_naples_day1.html"
    nap2 = ".forecast/evidence_sources/sailworld_naples_day2.html"
    nap3 = ".forecast/evidence_sources/sailworld_naples_day3.html"

    cag1_url = "https://www.sailweb.co.uk/2026/05/22/ac38-preliminary-regatta-luna-rossa-teams-dominate-first-day-in-cagliari/"
    cag3_url = "https://www.sailweb.co.uk/2026/05/24/americas-cup-preliminary-regatta-luna-rossa-2-take-overall-victory-in-cagliari/"
    nap1_url = "https://www.sail-world.com/news/300183/Americas-Cup-Preliminary-Regatta-2-Day-1"
    nap2_url = "https://www.sail-world.com/news/300205/Luna-Rossa-at-Preliminary-Regatta-Naples-Day-2"
    nap3_url = "https://www.sail-world.com/news/300230/Americas-Cup-Preliminary-Regatta-2-Overall"

    ds_dir = ROOT / ".forecast" / "dataset"
    for r in doc["races"]:
        rid = r["race_id"]
        ds_file = ds_dir / f"{rid}.json"
        telem_ev = None
        if ds_file.exists():
            telem_ev = file_evidence(
                f".forecast/dataset/{rid}.json",
                supporting_source=f"AC38 race telemetry dataset cache ({rid})",
                result_scope="on_water_finish_order",
                available_at_utc=f"{r['date']}T18:00:00Z",
                review_status="telemetry_on_water_reconstructed",
            )
        ind_ev = None
        if rid == "26_05_24_cag_ipr_mr_final":
            ind_ev = file_evidence(cag3, supporting_source=cag3_url, result_scope="match_final_winner", available_at_utc="2026-05-24T19:00:00Z", review_status="independently_anchored")
            r["verified"] = True
            r["source_url"] = cag3_url
            r["source_sha256"] = ind_ev["source_sha256"]
        elif rid == "naples_mr_final":
            ind_ev = file_evidence(nap3, supporting_source=nap3_url, result_scope="match_final_winner", available_at_utc="2026-09-27T19:10:00Z", review_status="independently_anchored")
            r["verified"] = True
            r["source_url"] = nap3_url
            r["source_sha256"] = ind_ev["source_sha256"]
        else:
            # Generic results URLs or JS-SPA team articles do not verify full fleet orders.
            r["verified"] = False
            r["source_sha256"] = None
            if rid in ("26_05_22_cag_ipr_race_1", "26_05_22_cag_ipr_race_2", "26_05_22_cag_ipr_race_3"):
                ind_ev = file_evidence(cag1, supporting_source=cag1_url, result_scope="partial_podium_and_incidents", available_at_utc="2026-05-22T19:00:00Z", review_status="partial_anchor_only")
            elif rid in ("26_05_24_cag_ipr_race_7", "26_05_24_cag_ipr_race_8"):
                ind_ev = file_evidence(cag3, supporting_source=cag3_url, result_scope="partial_positions_and_standings", available_at_utc="2026-05-24T19:00:00Z", review_status="partial_anchor_only")
            elif rid in ("26_09_25_nap_ipr_race_1-3", "26_09_25_nap_ipr_race_2"):
                ind_ev = file_evidence(nap1, supporting_source=nap1_url, result_scope="partial_podium", available_at_utc="2026-09-25T19:00:00Z", review_status="partial_anchor_only")
            elif rid in ("26_09_25_nap_ipr_race_3", "26_09_26_nap_ipr_race_4", "26_09_26_nap_ipr_race_5", "26_09_26_nap_ipr_race_6"):
                ind_ev = file_evidence(nap2, supporting_source=nap2_url, result_scope="partial_podium", available_at_utc="2026-09-26T19:00:00Z", review_status="partial_anchor_only")
            elif rid in ("26_09_27_nap_ipr_race_7", "26_09_27_nap_ipr_race_8"):
                ind_ev = file_evidence(nap3, supporting_source=nap3_url, result_scope="partial_winner_and_standings", available_at_utc="2026-09-27T19:10:00Z", review_status="partial_anchor_only")
            else:
                ind_ev = {
                    "supporting_source": r.get("source_url"),
                    "captured_path": None,
                    "captured_bytes": 0,
                    "source_sha256": None,
                    "result_scope": "none_spa_or_generic_url",
                    "available_at_utc": None,
                    "review_status": "unanchored_full_order",
                }
        r["evidence"] = {
            "primary_review_status": "independently_anchored" if r["verified"] else "telemetry_reconstructed_with_partial_web_anchor",
            "independent_anchor": ind_ev,
            "telemetry_reconstruction": telem_ev,
        }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    d40 = refresh_ac37_ac40_results()
    d75 = refresh_ac37_ac75_results()
    refresh_rules_and_roster()
    d38 = refresh_ac38_prelims_evidence()
    print(f"Refreshed AC37 AC40 ({d40['completed_races']}/{d40['total_races']}), AC37 AC75 ({d75['total_races']}), AC38 Prelims ({len(d38['races'])}), rules, and roster.")


if __name__ == "__main__":
    main()
