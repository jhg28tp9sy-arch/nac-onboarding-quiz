import json
import unittest
from dataclasses import replace
from pathlib import Path
from random import Random

from utils.quiz import Attempt, make_questions
from utils.roster import load

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "assets/staff"
ROSTER, _, _ = load((ROOT / "data/staff.csv").read_text(encoding="utf-8"), PHOTOS)
STAFF = ROSTER[:6]


class QuizTests(unittest.TestCase):
    def test_choices_and_order(self):
        first = make_questions("role_recall", STAFF, PHOTOS, rng=Random(1))
        second = make_questions("role_recall", STAFF, PHOTOS, rng=Random(2))
        self.assertNotEqual([q.staff.id for q in first], [q.staff.id for q in second])
        self.assertEqual(len(first), 6)
        for question in first:
            self.assertEqual(len(set(question.options)), 4)
            self.assertIn(question.staff.role, question.options)
        self.assertGreater(len({q.options.index(q.staff.role) for q in first}), 1)

    def test_eligibility_and_retry(self):
        staff = [replace(STAFF[0], photo="missing.png"),
                 replace(STAFF[1], active=False), replace(STAFF[2], name_recall=False), *STAFF[3:]]
        questions = make_questions("name_recall", staff, PHOTOS)
        self.assertEqual({q.staff.id for q in questions}, {STAFF[0].id, *(s.id for s in STAFF[3:])})
        self.assertEqual(len(make_questions("name_recall", staff, PHOTOS, ids={STAFF[3].id})), 1)
        self.assertTrue(all(not q.options for q in make_questions("mastery_exam", staff, PHOTOS)))

    def test_all_quizzes_cover_the_full_org_chart(self):
        chart = json.loads((ROOT / "data/reporting.json").read_text(encoding="utf-8"))
        chart_ids = {chart["root"], *chart["manager_by_employee"], *chart["unlinked"]}
        self.assertEqual(len(chart_ids), 107)
        for mode in ("role_recall", "name_recall", "mastery_exam"):
            with self.subTest(mode=mode):
                questions = make_questions(mode, ROSTER, PHOTOS, rng=Random(1))
                self.assertEqual({question.staff.id for question in questions}, chart_ids)
                self.assertEqual(len(questions), len(chart_ids))
                if mode != "mastery_exam":
                    self.assertTrue(all(len(question.options) == 4 for question in questions))

    def test_name_recall_title_clue_does_not_include_same_title_distractors(self):
        person = replace(STAFF[0], photo="")
        same_title = replace(STAFF[1], role=person.role, department=person.department)
        staff = [person, same_title, *STAFF[2:]]
        question, = make_questions("name_recall", staff, PHOTOS, ids={person.id}, rng=Random(1))
        self.assertEqual(len(question.options), 4)
        self.assertIn(person.name, question.options)
        self.assertNotIn(same_title.name, question.options)

    def test_duplicate_events_do_not_change_progress(self):
        attempt = Attempt(make_questions("mastery_exam", STAFF[:2], PHOTOS))
        self.assertFalse(attempt.advance(0))
        self.assertTrue(attempt.submit(0, "Given Name", "A Role"))
        self.assertFalse(attempt.submit(0, "Replacement", "New role"))
        self.assertTrue(attempt.advance(0))
        self.assertFalse(attempt.advance(0))
        self.assertFalse(attempt.submit(0, "Late", "Answer"))
        self.assertTrue(attempt.submit(1, "", ""))
        self.assertTrue(attempt.advance(1))
        self.assertTrue(attempt.finished)
