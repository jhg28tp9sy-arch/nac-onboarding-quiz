import unittest
from pathlib import Path

from utils.roster import FIELDS, csv_text, load

ROOT = Path(__file__).resolve().parents[1]


class RosterTests(unittest.TestCase):
    def test_staff_roster_is_valid(self):
        production = (ROOT / "data/staff.csv").read_text(encoding="utf-8")
        records, errors, warnings = load(production, ROOT / "assets/staff")
        self.assertTrue(records)
        self.assertFalse(errors)
        self.assertEqual(len(warnings), sum(not record.photo for record in records))
        self.assertEqual(load(csv_text(FIELDS, []), ROOT / "assets/staff"), ([], [], []))

    def test_corrections_and_duplicates(self):
        base = dict(zip(FIELDS, ("ally", "Ally Rigney", "Old title", "Programs", "", "",
                                 "true", "true", "true", "true")))
        data = csv_text(FIELDS, [base, {**base, "id": "lyn", "name": "Lyn Example"},
                                 {**base, "id": "ALLY"}, {**base, "id": "copy"}])
        records, errors, warnings = load(data, ROOT / "assets/staff")
        self.assertEqual([record.role for record in records], ["Adventure Program Manager"])
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 2)

    def test_rejects_malformed_csv(self):
        self.assertTrue(load("id,name\n1", ROOT / "assets/staff")[1])
        self.assertTrue(load(",".join(FIELDS) + "\n1,Short", ROOT / "assets/staff")[1])
