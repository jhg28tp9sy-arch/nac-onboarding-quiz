import unittest

from utils.scoring import grade, spreadsheet_value


class ScoringTests(unittest.TestCase):
    def test_formatting_and_review(self):
        self.assertEqual(grade("  ADVENTURE  Program-Manager! ", "Adventure Program Manager"), "Correct")
        self.assertEqual(grade("Ally Rigny", "Ally Rigney"), "Review")
        self.assertEqual(grade("Ally Rigny", "Ally Rigney", ["Ally Rigny"]), "Incorrect")
        self.assertEqual(grade("", "Ally Rigney"), "Incorrect")
        self.assertEqual(grade("Something else", "Adventure Program Manager"), "Incorrect")

    def test_spreadsheet_formula_is_escaped(self):
        self.assertEqual(spreadsheet_value(" =1+1"), "' =1+1")
        self.assertEqual(spreadsheet_value("Ally Rigney"), "Ally Rigney")
