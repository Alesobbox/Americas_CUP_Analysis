"""Session-scoped identity. Physical hull UUIDs are never global crew IDs."""
from __future__ import annotations


def resolve_identity(asset_id: str, assets: dict, *, timestamp_ms: int | None = None,
                     fallback=None) -> dict:
    asset = assets.get(asset_id, {})
    code = (asset.get("abbreviation") or getattr(fallback, "code", None) or asset_id).strip()
    name = (asset.get("official_name") or asset.get("name") or
            getattr(fallback, "official_name", None) or code).strip()
    return {"asset_id": asset_id, "entry_id": code, "name": name,
            "color": asset.get("colour_code") or getattr(fallback, "color", "#9ca3af"),
            "effective_from_ms": timestamp_ms, "source": "session" if asset else "legacy_catalog"}
