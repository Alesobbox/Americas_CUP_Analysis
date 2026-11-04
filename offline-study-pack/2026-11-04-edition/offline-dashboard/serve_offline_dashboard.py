#!/usr/bin/env python3
"""
Zero-Dependency Offline HTTP Server for the Built AC40 Regatta Replay Dashboard.
Serves the repository's `dist/` and `public/data/` directories at http://127.0.0.1:8080
so browser `fetch()` calls work offline without `file://` CORS restrictions.

Usage:
    python offline-dashboard/serve_offline_dashboard.py [--port 8080]
"""
import argparse
import http.server
import socketserver
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACK_ROOT.parent.parent
DIST_DIR = REPO_ROOT / "dist"
PUBLIC_DIR = REPO_ROOT / "public"


class OfflineDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if clean.startswith("data/") and (PUBLIC_DIR / clean).exists():
            return str(PUBLIC_DIR / clean)
        if DIST_DIR.exists():
            candidate = DIST_DIR / (clean or "index.html")
            if candidate.exists():
                return str(candidate)
            return str(DIST_DIR / "index.html")
        return str(PACK_ROOT / (clean or "START_HERE.html"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve AC40 Offline Dashboard")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with socketserver.TCPServer(("127.0.0.1", args.port), OfflineDashboardHandler) as httpd:
        print(f"Serving Offline AC40 Dashboard at http://127.0.0.1:{args.port}")
        print("TIP: Switch Replay view to 'Grid Mode' (Course-Up or North-Up) when offline without map tiles.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
