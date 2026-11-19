"""Subcommand CLI implementation for the environment-2 acquisition and export pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters_grid import has_copernicus_credentials
from .cache import acquire_all_tasks, verify_cache_offline
from .contracts import read_environment_artifact, resolve_env_cache_dir, validate_environment_v2
from .exporter import export_all_environments
from .inventory import build_environment_inventory
from .providers import probe_all_venues
from .registry import build_provider_audit


def verify_all_environment_artifacts(root: Path) -> dict[str, Any]:
    """Verify offline cache, exported sessions, public replays, boats, and bundles."""
    env_dir = resolve_env_cache_dir(root)
    pub_dir = root / "public" / "data" / "environment"
    cache_stats = verify_cache_offline(root)

    pub_files = sorted(p for p in pub_dir.glob("*.json") if p.is_file())
    v2_pub = 0
    v1_pub = 0
    boat_files_checked = 0
    bundle_files_checked = 0
    for fp in pub_files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        read_environment_artifact(doc)
        if doc.get("schema_version") == "environment-2":
            validate_environment_v2(doc)
            v2_pub += 1
            brel = doc.get("bundle_relpath")
            if brel and not (pub_dir / brel).is_file():
                raise ValueError(f"Missing bundle artifact {brel} for {fp.name}")
            if brel:
                bundle_files_checked += 1
            bo_rel = doc.get("boats_relpath")
            if bo_rel and not (pub_dir / bo_rel).is_file():
                raise ValueError(f"Missing boat environment artifact {bo_rel} for {fp.name}")
            if bo_rel:
                boat_files_checked += 1
        else:
            v1_pub += 1

    sess_dir = env_dir / "sessions"
    sess_count = 0
    if sess_dir.is_dir():
        for sp in sorted(sess_dir.glob("*.json")):
            sdoc = json.loads(sp.read_text(encoding="utf-8"))
            validate_environment_v2(sdoc)
            sess_count += 1

    return {
        "status": "pass",
        "cache": cache_stats,
        "public_v2": v2_pub,
        "public_v1": v1_pub,
        "bundles_checked": bundle_files_checked,
        "boat_files_checked": boat_files_checked,
        "sessions_v2_verified": sess_count,
    }


def _cmd_inventory(root: Path, _args: argparse.Namespace) -> dict[str, Any]:
    inv = build_environment_inventory(root, write=True)
    audit_path = resolve_env_cache_dir(root) / "provider_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = audit_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(build_provider_audit(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(audit_path)
    return {"status": "pass", "counts": inv["counts"]}


def _cmd_probe(_root: Path, _args: argparse.Namespace) -> dict[str, Any]:
    res = probe_all_venues()
    res["copernicus_credentials_configured"] = has_copernicus_credentials()
    return res


def _cmd_acquire(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    inv_path = resolve_env_cache_dir(root) / "inventory.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8")) if inv_path.is_file() else build_environment_inventory(root, write=True)
    manifest = acquire_all_tasks(root, inv, force=bool(args.force))
    return {
        "status": "pass" if manifest["unavailable_tasks"] == 0 else "partial",
        "total_tasks": manifest["total_tasks"],
        "available_tasks": manifest["available_tasks"],
        "fallback_tasks": manifest["fallback_tasks"],
        "unavailable_tasks": manifest["unavailable_tasks"],
    }


def _cmd_export(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    res = export_all_environments(root, verify_cache=not bool(args.skip_verify), write=True)
    if (root / "public" / "data" / "analysis" / "index.json").is_file():
        from scripts.build_artifact_inventory import build_inventory

        build_inventory(root.resolve())
    return res


def _cmd_verify(root: Path, _args: argparse.Namespace) -> dict[str, Any]:
    return verify_all_environment_artifacts(root)


ENV_SUBCOMMANDS = {
    "inventory": _cmd_inventory,
    "probe": _cmd_probe,
    "acquire": _cmd_acquire,
    "export": _cmd_export,
    "verify": _cmd_verify,
}


def run_env_cli(argv: list[str] | None = None) -> int:
    """Dispatch Packet 1-4 subcommands cleanly."""
    parser = argparse.ArgumentParser(prog="python -m pipeline.environment")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ENV_SUBCOMMANDS:
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
        p.add_argument("--all-sources", action="store_true")
        p.add_argument("--all-venues", action="store_true")
        if name == "acquire":
            p.add_argument("--force", action="store_true")
        if name == "export":
            p.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args(argv)
    handler = ENV_SUBCOMMANDS[args.command]
    result = handler(args.root, args)
    print(json.dumps(result, indent=2))
    if result.get("status") == "partial":
        return 0
    return 0 if result.get("status", "pass") != "fail" else 1
