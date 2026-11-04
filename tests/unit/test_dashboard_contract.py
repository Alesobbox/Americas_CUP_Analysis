"""Keep the maintained source tree and published data tied to the dashboard."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DashboardSourceContractTests(unittest.TestCase):
    def test_every_frontend_module_is_reachable_from_the_entry_point(self):
        sources = {path.resolve() for path in (ROOT / "src").rglob("*")
                   if path.suffix in (".ts", ".tsx", ".css")
                   and not path.name.endswith((".test.ts", ".d.ts"))}
        seen = set()

        def visit(path):
            if path in seen:
                return
            seen.add(path)
            text = path.read_text(encoding="utf-8")
            for relative in re.findall(r'''(?:from\s*|import\s*)['"]([^'"]+)['"]''', text):
                if not relative.startswith("."):
                    continue
                base = path.parent / relative
                candidates = [base, *(Path(str(base) + suffix) for suffix in (".ts", ".tsx", ".css"))]
                target = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
                if target in sources:
                    visit(target)

        visit((ROOT / "src/main.tsx").resolve())
        self.assertEqual(sources - seen, set(), "Unused production modules must be removed or connected to the dashboard")

    def test_published_data_has_only_documented_output_families(self):
        data = ROOT / "public/data"
        self.assertEqual({path.name for path in data.iterdir() if path.is_file()},
                         {"manifests.json", "artifacts.json"})
        self.assertEqual({path.name for path in data.iterdir() if path.is_dir()},
                         {"analysis", "replays", "predictions", "environment", "presentation"})


if __name__ == "__main__":
    unittest.main()
