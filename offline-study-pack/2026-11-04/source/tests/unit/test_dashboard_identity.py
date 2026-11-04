import unittest
from pipeline.config import COMPETITORS
from pipeline.ingest import session_competitor_identity

class DashboardIdentityTests(unittest.TestCase):
    def test_session_identity_overrides_reused_asset_id(self):
        asset_id = "130ac4af-df5a-4568-af62-9d9395df9e9e"
        source = {asset_id: {"abbreviation": "ITA B", "official_name": " Luna Rossa ", "colour_code": "#00f0fd"}}
        result = session_competitor_identity(asset_id, source)
        self.assertEqual((result.code, result.name, result.color), ("ITA B", "Luna Rossa", "#00f0fd"))
        self.assertEqual(result.uuid, asset_id)
        self.assertEqual(COMPETITORS[asset_id].code, "ITA G")

    def test_legacy_input_without_session_asset_remains_compatible(self):
        asset_id = next(iter(COMPETITORS))
        result = session_competitor_identity(asset_id, {})
        self.assertEqual(result.code, COMPETITORS[asset_id].code)

if __name__ == "__main__":
    unittest.main()
