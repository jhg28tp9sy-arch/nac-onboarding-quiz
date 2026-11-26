import html
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from utils.quiz import Attempt, make_questions
from utils.results_log import COLUMNS, Learner, ResultsStore

APP = Path(__file__).resolve().parents[1] / "app.py"


class AppTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("utils.quiz.make_questions", side_effect=lambda *args, **kwargs:
                                [question for question in make_questions(*args, **kwargs) if question.staff.photo][:6]))
        self.app = AppTest.from_file(str(APP))
        self.app.secrets["NAC_ACCESS_PASSWORD"] = "example-test-password"
        self.app.run()
        self.app.text_input[0].set_value("example-test-password")
        self.click("Sign in")
        self.app.session_state["quiz_learner"] = Learner("Jordan Avery")
        self.app.session_state["study_ids"] = []
        self.addCleanup(lambda: self.assertFalse(self.app.exception))

    def click(self, label):
        next(button for button in self.app.button if button.label == label).click().run()
        self.assertFalse(self.app.exception)

    def pause_quiz(self):
        self.click("Quiz options")
        self.click("Pause quiz")

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
        self.assertTrue(any(item.value == "107 profiles" for item in self.app.caption))

    def test_default_access_password_changed(self):
        self.click("Sign out")
        self.app.secrets.clear()
        self.app.text_input[0].set_value("wyser")
        self.click("Sign in")
        self.assertEqual(self.app.error[0].value, "Incorrect password.")
        self.app.secrets["NAC_ACCESS_PASSWORD"] = "wyser"
        self.app.text_input[0].set_value("learnnac")
        self.click("Sign in")
        self.assertTrue(any(button.label == "Open Staff Directory" for button in self.app.button))

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
        self.click("View Declan ODonnell in org chart")
        self.assertEqual(self.app.session_state["chart_focus"], "049")
        self.click("Back to search results")
        self.assertEqual(self.app.text_input(key="staff_query").value, "odonnell declan")
        self.click("Clear filters")
        self.assertEqual(self.app.selectbox(key="staff_page").value, 1)

    def test_org_chart_follows_paylocity_reporting_links(self):
        self.click("Open Staff Directory")
        self.assertTrue(any("Direct reports · 7" in item.value for item in self.app.html))
        chart = next(item.value for item in self.app.html if '<div class="nac-org-tree">' in item.value)
        self.assertIn('<details class="nac-org-node"', chart)
        self.assertEqual(chart.count('<details class="nac-org-node"'), 106)
        self.assertEqual(chart.count('loading="lazy" decoding="async" src="'), 54)
        self.assertNotIn('src="/', chart)
        self.assertNotIn("data:image/", chart)
        self.assertIn("Abe Rogers", chart)
        self.assertIn("Reports to Mike Schultz", chart)
        self.app.text_input(key="chart_query").set_value("dehm mall").run()
        self.app.button(key="chart_match_041").click().run()
        path = next(item.value for item in self.app.html if 'aria-label="Reporting path"' in item.value)
        self.assertIn('data-chart-focus="043">William Ford', path)
        self.assertIn('data-chart-focus="015">Andrew Ball', path)
        self.assertIn('aria-current="page">Mallory Dehm', path)
        self.assertEqual(self.app.text_input(key="chart_query").value, "")

    def test_org_chart_includes_supervisors_added_from_paylocity(self):
        self.click("Open Staff Directory")
        self.app.text_input(key="chart_query").set_value("tr sTon").run()
        self.app.button(key="chart_match_014").click().run()
        self.assertTrue(any(item.value == "Reports to Mike Benson" for item in self.app.caption))
        self.assertTrue(any('>Mike Benson</button>' in item.value for item in self.app.html))

    def test_study_list_from_staff_directory_and_chart(self):
        self.click("Open Staff Directory")
        self.app.radio[0].set_value("Find staff").run()
        self.app.text_input(key="staff_query").set_value("brad col").run()
        self.click("Save Colton Bradley")
        self.click("Home")
        self.click("My study list")
        self.assertTrue(any("Colton Bradley" in item.value for item in self.app.html))
        self.click("View Colton Bradley in org chart")
        self.assertEqual(self.app.session_state["chart_focus"], "001")
        self.click("Remove Colton Bradley from study list")
        self.click("Home")
        self.click("My study list")
        self.assertTrue(any("Save people" in message.value for message in self.app.info))

    def test_org_chart_search_handles_name_fragments_and_punctuation(self):
        self.click("Open Staff Directory")
        for query, employee in (("schul mi", "047"), ("O’DON", "049"), ("  Brád   Col  ", "001")):
            with self.subTest(query=query):
                self.app.text_input(key="chart_query").set_value(query).run()
                self.assertEqual(self.app.button(key=f"chart_match_{employee}").key, f"chart_match_{employee}")
        self.app.text_input(key="chart_query").set_value("zzzzzz").run()
        self.assertTrue(any("No matching names" in item.value for item in self.app.caption))

    def test_learner_can_choose_their_org_chart_profile(self):
        self.app.session_state["quiz_learner"] = None
        self.click("Open Name Recall")
        self.click("Choose from org chart")
        self.app.text_input(key="chart_query").set_value("brad col").run()
        self.app.button(key="chart_match_001").click().run()
        self.click("Take quiz as Colton Bradley")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"]["name_recall"]
        self.assertEqual(attempt.learner, Learner("Colton Bradley", "001"))

    def test_named_results_persist_and_require_a_separate_password(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        database = str(Path(folder) / "results.sqlite3")
        self.app.secrets["NAC_RESULTS_SQLITE_PATH"] = database
        self.app.secrets["NAC_RESULTS_PASSWORD"] = "private-log-test-password"
        self.app.session_state["quiz_learner"] = None
        self.click("Open Role Recall")
        self.app.text_input[0].set_value("  Riley ")
        self.click("Use this name")
        self.assertEqual(self.app.error[0].value, "Enter your first and last name.")
        self.app.text_input[1].set_value(" Morgan ")
        self.click("Use this name")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"]["role_recall"]
        self.click(attempt.questions[0].staff.role)
        self.click("Quiz options")
        self.click("End quiz")
        self.click("Confirm end")
        self.app.run()
        saved, = ResultsStore(sqlite_path=database).read()
        row = dict(zip(COLUMNS, saved))
        self.assertEqual((row["participant"], row["status"], row["score"], row["possible"]),
                         ("Riley Morgan", "Ended early", 1, 1))

        self.click("Home")
        self.click("Sign out")
        self.app.text_input[0].set_value("example-test-password")
        self.click("Sign in")
        self.click("Results log")
        self.assertFalse(self.app.dataframe)
        self.app.text_input[0].set_value("example-test-password")
        self.click("Unlock results log")
        self.assertFalse(self.app.dataframe)
        self.app.text_input[0].set_value("private-log-test-password")
        self.click("Unlock results log")
        self.assertEqual(self.app.dataframe[0].value.iloc[0]["participant"], "Riley Morgan")
        self.assertTrue(any(button.proto.label == "Download results log CSV"
                            for button in self.app.get("download_button")))
        self.click("Lock results log")
        self.assertFalse(self.app.dataframe)
        self.app.text_input[0].set_value("moose25")
        self.click("Unlock results log")
        self.assertFalse(self.app.dataframe)
        del self.app.secrets["NAC_RESULTS_PASSWORD"]
        self.app.text_input[0].set_value("moose25")
        self.click("Unlock results log")
        self.assertEqual(self.app.dataframe[0].value.iloc[0]["participant"], "Riley Morgan")

    def test_role_recall_feedback_and_retry(self):
        self.click("Open Role Recall")
        self.click("Start quiz")
        attempt = self.app.session_state["attempts"]["role_recall"]
        for index, question in enumerate(attempt.questions):
            correct = question.staff.role
            wrong = next(option for option in question.options if option != correct)
            self.click(wrong if index == 0 else correct)
            feedback = next(item.value for item in self.app.html if 'class="nac-feedback"' in item.value)
            outcome = "incorrect" if index == 0 else "correct"
            self.assertIn(f'data-outcome="{outcome}"', feedback)
            reveal = next(item.value for item in self.app.html if 'class="nac-quiz-prompt nac-answer-reveal"' in item.value)
            self.assertIn(html.escape(question.staff.name), reveal)
            self.assertIn(html.escape(correct), reveal)
            self.click("See results" if index + 1 == len(attempt.questions) else "Next question")
        self.assertEqual(self.app.metric[0].value, "5 / 6")
        self.assertFalse(any(item.value == "Completion certificate" for item in self.app.subheader))
        self.assertEqual(self.app.radio[0].value, "Missed or flagged")
        self.app.radio[0].set_value("All answers").run()
        self.assertEqual(sum('class="nac-review"' in item.value for item in self.app.html), 6)
        self.click("Retry missed questions")
        retry = self.app.session_state["attempts"]["role_recall"]
        self.assertEqual(len(retry.questions), 1)

        self.pause_quiz()
        self.click("Quiz history")
        self.assertEqual(self.app.metric[0].value, "5 / 6")
        self.assertTrue(any("Attempt 1 · Full quiz" == item.value for item in self.app.caption))
        self.assertFalse(any(button.label == "Retry missed questions" for button in self.app.button))
        self.click("Resume Role Recall")
        self.click(retry.questions[0].staff.role)
        self.click("See results")

        self.assertEqual(self.app.metric[0].value, "1 / 1")
        self.assertFalse(any(item.value == "Completion certificate" for item in self.app.subheader))
        self.assertEqual(self.app.selectbox[0].options, ["Attempt 2 · Missed questions", "Attempt 1 · Full quiz"])
        self.app.selectbox[0].set_value(0).run()
        self.assertEqual(self.app.metric[0].value, "5 / 6")
        self.assertEqual(self.app.radio[0].value, "Missed or flagged")
        self.assertTrue(any('data-outcome="incorrect">Incorrect' in item.value for item in self.app.html))
        self.assertEqual(len(self.app.session_state["quiz_results"]["role_recall"]), 2)

        self.click("Restart quiz")
        self.pause_quiz()
        self.click("Quiz history")
        self.assertEqual(self.app.selectbox[1].options, ["Attempt 2 · Missed questions", "Attempt 1 · Full quiz"])
        self.click("Home")
        self.click("Sign out")
        self.app.text_input[0].set_value("example-test-password")
        self.click("Sign in")
        self.assertFalse(any(button.label == "Quiz history" for button in self.app.button))

    def test_home_resumes_a_quiz_with_its_progress(self):
        self.click("Open Role Recall")
        self.click("Start quiz")
        self.pause_quiz()
        self.assertFalse(any("0 of 6 answered" in item.value for item in self.app.html))
        self.click("Resume Role Recall")
        attempt = self.app.session_state["attempts"]["role_recall"]
        self.click(attempt.questions[0].staff.role)
        self.click("Next question")
        self.pause_quiz()
        self.assertTrue(any("1 of 6 answered" in item.value for item in self.app.html))
        self.click("Resume Role Recall")
        self.assertEqual(self.app.session_state["attempts"]["role_recall"].index, 1)

    def test_active_quiz_can_cancel_restart_and_save_a_partial_result(self):
        self.click("Open Role Recall")
        self.click("Start quiz")
        first = self.app.session_state["attempts"]["role_recall"]
        self.click(first.questions[0].staff.role)
        self.click("Quiz options")
        self.click("Restart quiz")
        self.click("Keep taking quiz")
        self.assertEqual(len(first.answers), 1)
        self.assertTrue(any(button.label == "Next question" for button in self.app.button))

        self.click("Quiz options")
        self.click("Restart quiz")
        self.click("Confirm restart")
        restarted = self.app.session_state["attempts"]["role_recall"]
        self.assertEqual(restarted.index, 0)
        self.assertFalse(restarted.answers)
        self.assertFalse(self.app.session_state["quiz_results"])

        self.click(restarted.questions[0].staff.role)
        self.click("Quiz options")
        self.click("End quiz")
        self.click("Confirm end")
        self.assertEqual(self.app.metric[0].value, "1 / 1")
        self.assertEqual(self.app.metric[0].label, "Score on answered questions")
        self.assertFalse(any(item.value == "Completion certificate" for item in self.app.subheader))
        self.click("Home")
        self.click("Quiz history")
        self.assertTrue(any(item.value == "Attempt 1 · Ended early" for item in self.app.caption))
        self.assertEqual(self.app.metric[0].value, "1 / 1")

    def test_end_quiz_before_answering_returns_home(self):
        self.click("Open Name Recall")
        self.click("Start quiz")
        self.click("Quiz options")
        self.click("End quiz")
        self.click("Confirm end")
        self.assertTrue(any(button.label == "Open Name Recall" for button in self.app.button))
        self.assertFalse(self.app.session_state["quiz_results"])

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
        self.click("Home")
        self.click("Quiz history")
        self.assertEqual(self.app.selectbox[0].options, ["Mastery Exam"])
        self.assertEqual([metric.value for metric in self.app.metric], ["11 / 12", "6 / 6", "5 / 6"])
        self.assertFalse(any(item.value == "Completion certificate" for item in self.app.subheader))

    def test_perfect_mastery_earns_a_certificate(self):
        with patch("utils.quiz.make_questions", side_effect=lambda *args, **kwargs:
                   [question for question in make_questions(*args, **kwargs) if question.staff.photo][:1]):
            self.click("Open Mastery Exam")
            self.click("Start exam")
            question = self.app.session_state["attempts"]["mastery_exam"].questions[0]
            self.app.text_input[0].set_value(question.staff.name)
            self.app.text_input[1].set_value(question.staff.role)
            self.click("Submit exam")
        self.assertEqual(self.app.metric[0].value, "2 / 2")
        self.assertTrue(any(item.value == "Completion certificate" for item in self.app.subheader))
        self.assertTrue(any(button.proto.label == "Download certificate (PDF)"
                            for button in self.app.get("download_button")))
        _, pdf, preview = self.app.session_state["certificate_artwork"]
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(preview.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_mastery_missing_photo_appears_only_in_the_answer_key(self):
        def sample_with_and_without_portrait(*args, **kwargs):
            questions = make_questions(*args, **kwargs)
            return [next(q for q in questions if q.review_only), next(q for q in questions if not q.review_only)]

        with patch("utils.quiz.make_questions", side_effect=sample_with_and_without_portrait):
            self.click("Open Mastery Exam")
            self.click("Start exam")
            attempt = self.app.session_state["attempts"]["mastery_exam"]
            self.assertEqual(len(attempt.questions), 1)
            self.assertEqual(len(attempt.review_questions), 1)
            person = attempt.review_questions[0].staff
            self.assertFalse(any(html.escape(person.name) in item.value for item in self.app.html))
            self.app.text_input[0].set_value(attempt.questions[0].staff.name)
            self.app.text_input[1].set_value(attempt.questions[0].staff.role)
            self.click("Submit exam")
        self.assertEqual([metric.value for metric in self.app.metric], ["2 / 2", "1 / 1", "1 / 1"])
        self.app.radio[0].set_value("Review-only profiles").run()
        self.assertTrue(any(html.escape(person.name) in item.value for item in self.app.html))
        self.assertTrue(any(item.value == "Review only" for item in self.app.caption))
        self.assertEqual(len(self.app.session_state["quiz_results"]["mastery_exam"][0].rows), 2)

    def test_mastery_starts_with_the_previous_quiz_module_loaded(self):
        legacy_question = namedtuple("LegacyQuestion", ["staff", "options"])

        def legacy_questions(*args, **kwargs):
            questions = make_questions(*args, **kwargs)
            return [legacy_question(question.staff, question.options) for question in
                    (next(q for q in questions if q.review_only), next(q for q in questions if not q.review_only))]

        def legacy_attempt(questions, *, retry):
            attempt = Attempt(questions, retry=retry)
            del attempt.review_questions
            return attempt

        with patch.multiple("utils.quiz", Attempt=legacy_attempt, make_questions=legacy_questions):
            self.click("Open Mastery Exam")
            self.click("Start exam")
            attempt = self.app.session_state["attempts"]["mastery_exam"]
            question, = attempt.questions
            pending_review, = attempt.review_questions
            self.app.text_input[0].set_value(question.staff.name)
            self.app.text_input[1].set_value(question.staff.role)
            self.click("Submit exam")
            self.assertEqual([metric.value for metric in self.app.metric], ["2 / 2", "1 / 1", "1 / 1"])
            self.app.radio[0].set_value("Review-only profiles").run()
            self.assertTrue(any(pending_review.staff.name in item.value for item in self.app.html))
            self.click("Restart quiz")
            self.assertTrue(any(button.label == "Submit exam" for button in self.app.button))

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
        self.assertTrue(any(item.value == "Completion certificate" for item in self.app.subheader))
        awarded = next(item.value for item in self.app.caption if item.value.startswith("Awarded "))
        self.assertTrue(awarded.endswith(" UTC"))
        self.click("Home")
        self.click("Quiz history")
        self.assertEqual(self.app.selectbox[0].options, ["Name Recall"])
        self.assertTrue(any(item.value == awarded for item in self.app.caption))

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
