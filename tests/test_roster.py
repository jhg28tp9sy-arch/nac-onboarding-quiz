import unittest
from pathlib import Path

from utils.roster import FIELDS, csv_text, load

ROOT = Path(__file__).resolve().parents[1]


class RosterTests(unittest.TestCase):
    def test_rosters_are_separate(self):
        production = (ROOT / "data/staff.csv").read_text(encoding="utf-8")
        records, errors, _ = load(production, ROOT / "assets/staff")
        self.assertFalse(errors)
        self.assertEqual(records, [])
        self.assertEqual(load(csv_text(FIELDS, []), ROOT / "assets/staff"), ([], [], []))
        demo = (ROOT / "data/demo_staff.csv").read_text()
        records, errors, warnings = load(demo, ROOT / "assets/demo", demo=True)
        self.assertEqual(len(records), 6)
        self.assertFalse(errors or warnings)
        self.assertFalse(load(demo, ROOT / "assets/demo")[0])

    def test_detects_duplicate_ids_and_profiles(self):
        base = dict(zip(FIELDS, ("pike", "Morgan Pike", "Workshop Lead", "Programs", "", "",
                                 "true", "true", "true", "true")))
        data = csv_text(FIELDS, [base, {**base, "id": "PIKE"}, {**base, "id": "copy"}])
        records, errors, warnings = load(data, ROOT / "assets/staff")
        self.assertEqual([record.role for record in records], ["Workshop Lead"])
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 1)

    def test_rejects_malformed_csv(self):
        self.assertTrue(load("id,name\n1", ROOT / "assets/staff")[1])
        self.assertTrue(load(",".join(FIELDS) + "\n1,Short", ROOT / "assets/staff")[1])
