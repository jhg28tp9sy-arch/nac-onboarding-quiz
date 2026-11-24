import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP))
        self.app.secrets["NAC_DEMO_PASSWORD"] = "example-test-password"
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
        self.assertTrue(any(item.value == "57 profiles" for item in self.app.caption))

    def test_directory_switches_to_fictional_demo(self):
        self.click("Open Staff Directory")
        self.assertFalse(any("Fictional demo" in item.value for item in self.app.info))
        self.click("Home")
        self.click("Try the fictional demo")
        self.click("Open Staff Directory")
        self.app.text_input[0].set_value("Equipment").run()
        self.assertTrue(any(item.value == "1 profile" for item in self.app.caption))

    def test_role_recall_feedback_and_retry(self):
        self.click("Try the fictional demo")
        self.click("Open Role Recall")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"][(True, "role_recall")]
        for index, question in enumerate(attempt.questions):
            correct = question.staff.role
            wrong = next(option for option in question.options if option != correct)
            self.click(wrong if index == 0 else correct)
            self.assertTrue(self.app.error if index == 0 else self.app.success)
            self.click("See results" if index + 1 == len(attempt.questions) else "Next question")
        self.assertEqual(self.app.metric[0].value, "5 / 6")
        self.click("Retry missed questions")
        self.assertEqual(len(self.app.session_state["attempts"][(True, "role_recall")].questions), 1)

    def test_mastery_withholds_answers_until_submission(self):
        self.click("Try the fictional demo")
        self.click("Open Mastery Exam")
        self.click("Start exam")
        questions = self.app.session_state["attempts"][(True, "mastery_exam")].questions
        for index, question in enumerate(questions):
            shown = " ".join(str(item.value) for item in self.app.markdown)
            self.assertNotIn(question.staff.name, shown)
            self.assertNotIn(question.staff.role, shown)
            self.app.text_input[0].set_value(question.staff.name)
            self.app.text_input[1].set_value(question.staff.role if index else "")
            self.click("Submit exam" if index + 1 == len(questions) else "Save and continue")
        self.assertEqual([metric.value for metric in self.app.metric], ["11 / 12", "6 / 6", "5 / 6"])

    def test_name_recall(self):
        self.click("Try the fictional demo")
        self.click("Open Name Recall")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"][(True, "name_recall")]
        for index, question in enumerate(attempt.questions):
            self.click(question.staff.name)
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
