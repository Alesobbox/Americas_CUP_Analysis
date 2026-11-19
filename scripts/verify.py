"""Cross-platform repository verification script (safe for CI and fresh clones)."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def _check_markdown_links() -> None:
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    broken: list[str] = []
    md_files = [ROOT / "README.md", ROOT / "PROJECT.md"]
    docs_dir = ROOT / "docs"
    if docs_dir.is_dir():
        md_files.extend(sorted(docs_dir.glob("*.md")))
    for md in md_files:
        if not md.is_file():
            continue
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
            for match in pattern.finditer(line):
                target = match.group(1).strip()
                if (
                    not target
                    or target.startswith("#")
                    or target.startswith(("http://", "https://", "mailto:"))
                ):
                    continue
                rel_path = target.split("#", 1)[0]
                if not rel_path:
                    continue
                resolved = (md.parent / rel_path).resolve()
                if not resolved.exists():
                    broken.append(f"{md.relative_to(ROOT)}:{lineno} -> {target}")
    if broken:
        raise AssertionError("Broken local markdown links:\n  " + "\n  ".join(broken))
    print(f"Markdown links OK across {len(md_files)} files")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AC40 Regatta Replay repository checks")
    parser.add_argument("--with-format", action="store_true", help="Check Prettier and Ruff formatting")
    args = parser.parse_args()

    npm = shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm not found in PATH")

    if args.with_format:
        _run([npm, "run", "format:check"])
        _run([sys.executable, "-m", "ruff", "check", "pipeline", "scripts", "tests"])

    _run([npm, "test"])
    _run([npm, "run", "build"])
    _run([sys.executable, "-m", "unittest", "discover", "-s", "tests/unit", "-p", "test_*.py"])

    has_full_replay = (ROOT / "public/data/replays/naples_pr1.json").is_file()
    tier = "all" if has_full_replay else "1"
    if has_full_replay:
        _run([sys.executable, "tests/e2e/test_runner.py", "--tier", "all"])
        _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "tier5_*.py"])
    else:
        for t in ("1", "2", "3"):
            _run([sys.executable, "tests/e2e/test_runner.py", "--tier", t])

    if (ROOT / ".cache/environment/cache/manifest.json").is_file() and has_full_replay:
        _run([sys.executable, "-m", "pipeline.environment", "verify"])

    if (ROOT / "public/data/analysis/index.json").is_file():
        _run([sys.executable, "scripts/refresh_team_analytics.py", "--verify"])

    _check_markdown_links()
    print(f"Verification complete (tier={tier}, full_archive={has_full_replay}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
