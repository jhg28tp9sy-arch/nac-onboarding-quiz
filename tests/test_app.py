import html
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from utils.quiz import LIMITS

APP = Path(__file__).resolve().parents[1] / "app.py"


class AppTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(LIMITS, dict.fromkeys(LIMITS, 6)))
        self.app = AppTest.from_file(str(APP))
        self.app.secrets["NAC_ACCESS_PASSWORD"] = "example-test-password"
        self.app.run()
        self.app.text_input[0].set_value("example-test-password")
        self.click("Sign in")
        self.addCleanup(lambda: self.assertFalse(self.app.exception))

    def click(self, label):
        next(button for button in self.app.button if button.label == label).click().run()
        self.assertFalse(self.app.exception)

    def test_production_directory_requires_access_password(self):
        self.click("Sign out")
        self.assertFalse(any(button.label == "Open Staff Directory" for button in self.app.button))
        self.app.text_input[0].set_value("wrong-password")
        self.click("Sign in")
        self.assertEqual(self.app.error[0].value, "Incorrect password.")
        self.app.text_input[0].set_value("example-test-password")
        self.click("Sign in")
        self.click("Open Staff Directory")
        self.app.radio[0].set_value("Find staff").run()
        self.assertTrue(any(item.value == "57 profiles" for item in self.app.caption))

    def test_directory_searches_real_staff_by_name(self):
        self.click("Open Staff Directory")
        self.app.radio[0].set_value("Find staff").run()
        self.app.text_input[0].set_value("Colton Bradley").run()
        self.assertTrue(any(item.value == "1 profile" for item in self.app.caption))

    def test_search_returns_to_the_same_results_from_the_org_chart(self):
        self.click("Open Staff Directory")
        self.app.radio[0].set_value("Find staff").run()
        self.click("Next")
        self.assertEqual(self.app.selectbox(key="staff_page").value, 2)
        self.app.text_input(key="staff_query").set_value("odonnell declan").run()
        self.assertTrue(any(item.value == "1 profile" for item in self.app.caption))
        self.click("View Declan O’Donnell in org chart")
        self.assertEqual(self.app.selectbox(key="chart_person_picker").value, "049")
        self.click("Back to search results")
        self.assertEqual(self.app.text_input(key="staff_query").value, "odonnell declan")
        self.click("Clear filters")
        self.assertEqual(self.app.selectbox(key="staff_page").value, 1)

    def test_org_chart_follows_paylocity_reporting_links(self):
        self.click("Open Staff Directory")
        self.assertTrue(any("Direct reports · 7" in item.value for item in self.app.html))
        chart = next(item.value for item in self.app.html if '<div class="nac-org-tree">' in item.value)
        self.assertIn('<details class="nac-org-node"', chart)
        self.assertIn("Abe Rogers", chart)
        self.assertIn("Reports to Mike Schultz", chart)
        self.app.selectbox(key="chart_person_picker").set_value("041").run()
        self.assertTrue(any("Willie Ford / Mike Schultz / Andrew Ball / Mallory Dehm" in item.value
                            for item in self.app.html))
        self.click("Back to Andrew Ball")
        self.click("Top of chart")
        self.assertTrue(any("Direct reports · 7" in item.value for item in self.app.html))

    def test_org_chart_lists_profiles_without_inventing_supervisors(self):
        self.click("Open Staff Directory")
        self.app.selectbox[0].set_value("014").run()
        self.assertTrue(any(item.value == "Supervisor is outside this directory."
                            for item in self.app.caption))
        self.app.selectbox[0].set_value("025").run()
        self.assertTrue(any(item.value == "No supervisor link is available for this profile."
                            for item in self.app.caption))

    def test_role_recall_feedback_and_retry(self):
        self.click("Open Role Recall")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"]["role_recall"]
        for index, question in enumerate(attempt.questions):
            correct = question.staff.role
            wrong = next(option for option in question.options if option != correct)
            self.click(wrong if index == 0 else correct)
            self.assertTrue(self.app.error if index == 0 else self.app.success)
            self.click("See results" if index + 1 == len(attempt.questions) else "Next question")
        self.assertEqual(self.app.metric[0].value, "5 / 6")
        self.assertEqual(self.app.radio[0].value, "Missed or flagged")
        self.app.radio[0].set_value("All answers").run()
        self.assertEqual(sum('class="nac-review"' in item.value for item in self.app.html), 6)
        self.click("Retry missed questions")
        self.assertEqual(len(self.app.session_state["attempts"]["role_recall"].questions), 1)

    def test_home_resumes_a_quiz_with_its_progress(self):
        self.click("Open Role Recall")
        self.click("Start quiz")
        self.click("Home")
        self.assertFalse(any("0 of 6 answered" in item.value for item in self.app.html))
        self.click("Resume Role Recall")
        attempt = self.app.session_state["attempts"]["role_recall"]
        self.click(attempt.questions[0].staff.role)
        self.click("Next question")
        self.click("Home")
        self.assertTrue(any("1 of 6 answered" in item.value for item in self.app.html))
        self.click("Resume Role Recall")
        self.assertEqual(self.app.session_state["attempts"]["role_recall"].index, 1)

    def test_mastery_withholds_answers_until_submission(self):
        self.click("Open Mastery Exam")
        self.click("Start exam")
        questions = self.app.session_state["attempts"]["mastery_exam"].questions
        for index, question in enumerate(questions):
            shown = " ".join(str(item.value) for item in (*self.app.markdown, *self.app.html))
            self.assertNotIn(question.staff.name, shown)
            self.assertNotIn(question.staff.role, shown)
            self.app.text_input[0].set_value(question.staff.name)
            self.app.text_input[1].set_value(question.staff.role if index else "")
            self.click("Submit exam" if index + 1 == len(questions) else "Save and continue")
        self.assertEqual([metric.value for metric in self.app.metric], ["11 / 12", "6 / 6", "5 / 6"])

    def test_name_recall(self):
        self.click("Open Name Recall")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"]["name_recall"]
        for index, question in enumerate(attempt.questions):
            self.click(question.staff.name)
            self.assertTrue(any(question.staff.role in html.unescape(item.value)
                                for item in self.app.html))
            self.click("See results" if index + 1 == len(attempt.questions) else "Next question")
        self.assertEqual(self.app.metric[0].value, "6 / 6")

    def test_local_admin_requires_password(self):
        self.assertFalse(any(button.label == "Roster manager" for button in self.app.button))
        password = "local-test-password"
        with patch.dict("os.environ", NAC_LOCAL_ADMIN="1", NAC_ADMIN_PASSWORD=password):
            self.app.run()
            self.click("Roster manager")
            self.assertFalse(self.app.get("download_button"))
            self.app.text_input[0].set_value("incorrect")
            self.click("Sign in")
            self.assertEqual(self.app.error[0].value, "Invalid password.")
            self.app.text_input[0].set_value(password)
            self.click("Sign in")
            self.assertTrue(self.app.get("download_button"))
