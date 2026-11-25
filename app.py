import base64
import hmac
import html
import io
import json
import os
import unicodedata
from inspect import signature
from pathlib import Path
from uuid import uuid4

import streamlit as st
from PIL import Image
from streamlit import runtime
from streamlit.errors import StreamlitSecretNotFoundError

from utils.quiz import Attempt, FIELDS, Question, QuizResult, make_questions
from utils.results_log import COLUMNS, Learner, LoggedResult, ResultsStore, ResultsStoreError
from utils.roster import csv_text, load, photo_path, portrait
from utils.scoring import grade, normalize, spreadsheet_value

ROOT = Path(__file__).resolve().parent
PAGES = {
    "directory": ("Staff Directory", "Reference", "Look up coworkers, job titles, and reporting lines."),
    "role_recall": ("Role Recall", "Beginner", "Match coworkers to their job titles and learn which teams they work on."),
    "name_recall": ("Name Recall", "Intermediate", "Match faces to names, then see each coworker’s job title and department."),
    "mastery_exam": ("Mastery Exam", "Advanced", "Recall each coworker’s name and job title from their portrait."),
}
STAFF_FILTERS = ("staff_query", "staff_department", "staff_sort", "staff_page")
LIVE_SEARCH = {"type": "search", "live": "220ms"} if "live" in signature(st.text_input).parameters else {}

st.set_page_config(page_title="NAC Connect", page_icon=str(ROOT / "assets/logo.png"), layout="wide")
stylesheet = (ROOT / "assets/nac.css").read_text(encoding="utf-8")
st.html(f"<style>{stylesheet}</style>")

st.session_state.setdefault("page", "home")
st.session_state.setdefault("attempts", {})
st.session_state.setdefault("quiz_results", {})


def go(page):
    if page != "directory":
        st.session_state.pop("choose_learner_for", None)
    st.session_state.page = page


def heading(title):
    st.html(f'<h1 class="nac-heading">{html.escape(title)}</h1>')


def page_heading(title):
    with st.container(key="page_heading"):
        label, navigation = st.columns([3, 1])
        with label:
            heading(title)
        navigation.button("Home", on_click=go, args=("home",))


@st.cache_data(show_spinner=False)
def brand_image():
    buffer = io.BytesIO()
    with Image.open(ROOT / "assets/nac-wordmark.png") as wordmark:
        wordmark.thumbnail((320, 120), Image.Resampling.LANCZOS)
        wordmark.save(buffer, format="WEBP", lossless=True)
    return base64.b64encode(buffer.getvalue()).decode()


def brand():
    wordmark = brand_image()
    st.html('<div class="nac-brand"><img alt="National Ability Center" '
            f'src="data:image/webp;base64,{wordmark}"><span>Employee onboarding</span></div>')


def private_setting(key):
    try:
        value = st.secrets.get(key)
    except StreamlitSecretNotFoundError:
        value = None
    return value or os.getenv(key)


def require_app_password():
    try:
        password = st.secrets.get("NAC_ACCESS_PASSWORD") or st.secrets.get("NAC_DEMO_PASSWORD")
    except StreamlitSecretNotFoundError:
        password = None

    # Rotate the old test password even if it was saved in deployment secrets.
    if not isinstance(password, str) or not password.strip() or password == "wyser":
        password = "learnnac"

    marker = hmac.digest(password.encode(), b"nac-connect-session", "sha256")
    signed_in = st.session_state.get("staff_access")
    if signed_in is not None and hmac.compare_digest(signed_in, marker):
        return

    brand()
    with st.container(key="sign_in"):
        heading("NAC Connect")
        with st.form("staff_sign_in", clear_on_submit=True, border=True):
            st.write("Sign in to explore the staff directory and start your onboarding quizzes.")
            supplied = st.text_input("Access password", type="password", max_chars=256,
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            if hmac.compare_digest(supplied.encode(), password.encode()):
                st.session_state.staff_access = marker
                st.rerun()
            st.error("Incorrect password.")
    st.stop()


@st.cache_data(show_spinner=False, max_entries=256)
def portrait_bytes(path, modified_ns, thumbnail_width):
    image = portrait(path)
    if image is None:
        return None
    image.thumbnail((thumbnail_width, thumbnail_width * 5 // 4))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80, optimize=True)
    return buffer.getvalue()


def roster_photo(record, root, *, thumbnail_width):
    if not record.photo:
        return None
    filename = Path(record.photo)
    path = (root / filename).resolve()
    valid = (filename.name == record.photo and path.parent == root.resolve()
             and filename.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    try:
        return portrait_bytes(str(path), path.stat().st_mtime_ns, thumbnail_width) if valid else None
    except OSError:
        return None


def inline_portrait_url(image):
    return f"data:image/jpeg;base64,{base64.b64encode(image).decode()}"


def display_quiz_photo(record, root):
    image = roster_photo(record, root, thumbnail_width=360)
    if image is None:
        st.html('<div class="nac-placeholder">Photo unavailable</div>')
    else:
        st.html(f'<img class="nac-quiz-portrait" alt="Staff portrait" width="360" height="450" '
                f'src="{inline_portrait_url(image)}">')
    return image is not None


def thumbnail_markup(record, photo_root, *, in_chart=False):
    image = roster_photo(record, photo_root, thumbnail_width=112 if in_chart else 144)
    if image:
        if in_chart:
            # Use the same media store as st.image. Keep URLs relative for Streamlit's subpath hosting.
            media = runtime.get_instance().media_file_mgr
            source = media.add(image, "image/jpeg", f"org-chart:{record.id}").lstrip("/")
        else:
            source = inline_portrait_url(image)
        return f'<img alt="" loading="lazy" decoding="async" src="{html.escape(source, quote=True)}">'
    parts = record.name.split()
    initials = html.escape((parts[0][0] + parts[-1][0] if len(parts) > 1 else parts[0][0]).upper())
    return f'<span class="nac-person-placeholder" aria-hidden="true">{initials}</span>'


def person_card(record, photo_root):
    name, role, department = map(html.escape, (record.name, record.role, record.department))
    bio = f'<p class="nac-bio">{html.escape(record.bio)}</p>' if record.bio else ""
    st.html(
        f'<div class="nac-person">{thumbnail_markup(record, photo_root)}<div class="nac-person-copy">'
        f'<h2>{name}</h2><p>{role}</p><p class="nac-level">{department}</p></div></div>{bio}'
    )


def home():
    with st.container(key="home_intro"):
        intro, actions = st.columns([2.15, 1], vertical_alignment="center")
        intro.html('<div class="nac-hero"><h1>NAC Connect</h1>'
                   '<p>Get to know the people behind NAC. Learn names, job titles, and how teams fit together.</p></div>')
        with actions, st.container(key="study_card"):
            st.button("Open Staff Directory", key="directory", width="stretch",
                      type="primary", on_click=go, args=("directory",))
            if st.session_state.quiz_results:
                st.button("Quiz history", width="stretch", on_click=go, args=("quiz_history",))

    with st.container(key="activity_grid"):
        st.html('<h2 class="nac-section-title">Onboarding quizzes</h2>')
        quizzes = [(page, details) for page, details in PAGES.items() if page != "directory"]
        for (page, (title, level, description)), column in zip(quizzes, st.columns(3)):
            with column, st.container(border=True, key=f"activity_{page}"):
                attempt = st.session_state.attempts.get(page)
                action, progress = f"Open {title}", ""
                if attempt:
                    if attempt.finished:
                        action = f"Review {title}"
                        progress = "Ended early" if getattr(attempt, "ended_early", False) else "Completed this session"
                    else:
                        action = f"Resume {title}"
                        if attempt.answers:
                            status = "answered" if all(attempt.answers.values()) else "reviewed"
                            progress = f"{len(attempt.answers)} of {len(attempt.questions)} {status}"
                progress_markup = f'<p class="nac-activity-status">{progress}</p>' if progress else ""
                st.html(f'<div class="nac-activity"><span class="nac-level">{level}</span>'
                        f'<h3>{title}</h3><p>{description}</p>{progress_markup}</div>')
                st.button(action, key=page, width="stretch", on_click=go, args=(page,),
                          type="primary" if page == "role_recall" else "secondary")
    with st.container(key="home_utilities", horizontal=True):
        st.button("Results log", on_click=go, args=("results_log",))
        if os.getenv("NAC_LOCAL_ADMIN") == "1":
            st.button("Roster manager", on_click=go, args=("admin",))
        st.button("Sign out", type="tertiary", on_click=st.session_state.clear)


def set_learner(name, staff_id=None):
    st.session_state.quiz_learner = Learner(name, staff_id)
    if mode := st.session_state.pop("choose_learner_for", None):
        go(mode)


def choose_learner_profile(mode):
    st.session_state.choose_learner_for = mode
    st.session_state.directory_view = "Org chart"
    go("directory")


def cancel_learner_selection():
    go(st.session_state.pop("choose_learner_for", "home"))


def learner_form(mode, store):
    with st.container(border=True, key="learner_form"):
        st.subheader("Who’s taking this quiz?")
        st.caption("Your name and score go into the private results log." if store else
                   "Your name and score are available during this browser session.")
        st.button("Choose from org chart", width="stretch", on_click=choose_learner_profile, args=(mode,))
        with st.form("learner_name", border=False):
            first = st.text_input("First name", max_chars=48, autocomplete="given-name")
            last = st.text_input("Last name", max_chars=48, autocomplete="family-name")
            submitted = st.form_submit_button("Use this name", type="primary", width="stretch")
        if submitted:
            if first.strip() and last.strip():
                set_learner(" ".join(f"{first} {last}".split()))
                st.rerun()
            st.error("Enter your first and last name.")


def page_slice(items, key, size=12):
    pages = max(1, (len(items) + size - 1) // size)
    if pages == 1:
        return items, 1, pages
    if st.session_state.get(key, 1) > pages:
        st.session_state[key] = 1
    active = st.selectbox("Page", range(1, pages + 1), key=key,
                          format_func=lambda p: f"{p} of {pages}")
    offset = (active - 1) * size
    return items[offset:offset + size], active, pages


def set_page(key, page):
    st.session_state[key] = page


def page_controls(key, active, pages):
    if pages < 2:
        return
    with st.container(key="pagination"):
        previous, count, following = st.columns(3, vertical_alignment="center")
        previous.button("Previous", key=f"{key}-prev", width="stretch", disabled=active == 1,
                        on_click=set_page, args=(key, active - 1))
        count.html(f'<p class="nac-page-count" aria-live="polite">{active} of {pages}</p>')
        following.button("Next", key=f"{key}-next", width="stretch", disabled=active == pages,
                         on_click=set_page, args=(key, active + 1))


def clear_staff_filters():
    for key in STAFF_FILTERS:
        st.session_state.pop(key, None)


def open_search_result(person_id):
    st.session_state.staff_search = {
        key: st.session_state[key] for key in STAFF_FILTERS if key in st.session_state
    }
    select_chart_person(person_id)
    st.session_state.directory_view = "Org chart"


def return_to_search():
    st.session_state.directory_view = "Find staff"


def search_text(value):
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return normalize(plain.replace("‘", "'").replace("ʼ", "'"))


def search_staff(active, photo_root):
    for key, value in st.session_state.pop("staff_search", {}).items():
        st.session_state.setdefault(key, value)
    with st.container(key="directory_filters"):
        search, filter_column, order = st.columns([2, 1, 1])
    query = search.text_input("Search by name, role, or department", key="staff_query",
                              on_change=set_page, args=("staff_page", 1), **LIVE_SEARCH)
    departments = sorted({record.department for record in active}, key=str.casefold)
    selected = filter_column.selectbox("Department", [None, *departments], key="staff_department",
                                       format_func=lambda item: item or "All departments",
                                       on_change=set_page, args=("staff_page", 1))
    sorting = order.selectbox("Sort by name", ["A to Z", "Z to A"], key="staff_sort",
                              on_change=set_page, args=("staff_page", 1))
    terms = search_text(query).split()
    matches = []
    for record in active:
        haystack = search_text(f"{record.name} {record.role} {record.department}")
        if (selected is None or record.department == selected) and all(term in haystack for term in terms):
            matches.append(record)
    matches.sort(key=lambda record: record.name.casefold(), reverse=sorting == "Z to A")
    if query or selected or sorting != "A to Z":
        st.button("Clear filters", on_click=clear_staff_filters)
    st.caption(f"{len(matches)} {'profile' if len(matches) == 1 else 'profiles'}")
    if not matches:
        st.info("No staff match your search. Try a shorter name or clear the filters.")
        return
    visible, page, pages = page_slice(matches, "staff_page")
    with st.container(key="directory_grid"):
        for offset in range(0, len(visible), 3):
            row = visible[offset:offset + 3]
            for record, column in zip(row, st.columns(len(row))):
                with column, st.container(border=True, key=f"profile_{record.id}"):
                    person_card(record, photo_root)
                    st.button(f"View {record.name} in org chart", key=f"locate_{record.id}", width="stretch",
                              on_click=open_search_result, args=(record.id,))
    page_controls("staff_page", page, pages)


@st.cache_data(show_spinner=False)
def read_chart(path, modified_ns):
    chart = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(chart, dict) or not isinstance(chart.get("root"), str)
            or not isinstance(chart.get("manager_by_employee"), dict)
            or not isinstance(chart.get("unlinked"), dict)
            or not all(isinstance(manager, str) for manager in chart["manager_by_employee"].values())):
        raise ValueError("Invalid reporting data")
    return chart


def select_chart_person(person_id):
    st.session_state.chart_focus = person_id
    st.session_state.chart_query = ""


def open_chart_match(person_id):
    select_chart_person(person_id)
    st.session_state.chart_match_selected = True


@st.fragment
def chart_search(staff):
    if st.session_state.pop("chart_match_selected", False):
        st.rerun()
    with st.container(key="chart_search"):
        query = st.text_input("Search the org chart", key="chart_query", max_chars=100,
                              placeholder="First or last name", autocomplete="off", **LIVE_SEARCH)
        if not LIVE_SEARCH:
            st.caption("Press Enter to search.")
        text = search_text(query)
        parts = text.split()
        if not parts:
            return

        matches = []
        for record in staff:
            name = search_text(record.name)
            if all(part in name for part in parts):
                words = name.split()
                prefixes = all(any(word.startswith(part) for word in words) for part in parts)
                matches.append(((name != text, not prefixes, name), record))
        matches.sort(key=lambda match: match[0])

        if not matches:
            st.caption("No matching names. Try a shorter search.")
            return
        limit = 8
        if len(matches) > limit:
            st.caption(f"Showing {limit} of {len(matches)} matches. Type more to narrow the results.")
        for _, record in matches[:limit]:
            st.button(f"{record.name} · {record.role}", key=f"chart_match_{record.id}", width="stretch",
                      on_click=open_chart_match, args=(record.id,))


def report_branch(record, parent, children, photo_root, ancestors):
    name, title, team, manager = map(html.escape,
                                    (record.name, record.role, record.department, parent.name))
    ancestors = ancestors | {record.id}
    direct = [child for child in children.get(record.id, []) if child.id not in ancestors]
    nested = "".join(report_branch(child, record, children, photo_root, ancestors) for child in direct)
    reports = ""
    if nested:
        reports = (f'<div class="nac-org-count">Direct reports · {len(direct)}</div>'
                   f'<div class="nac-org-children">{nested}</div>')
    return (
        f'<details class="nac-org-node" id="staff-{html.escape(record.id)}">'
        f'<summary class="nac-org-summary">{thumbnail_markup(record, photo_root, in_chart=True)}'
        f'<span><strong>{name}</strong><small>{title}</small></span>'
        '<span class="nac-org-chevron" aria-hidden="true"></span></summary>'
        f'<div class="nac-org-body"><p>{team}</p><p>Reports to {manager}</p>{reports}</div></details>'
    )


def org_chart(active, photo_root):
    chart_path = ROOT / "data/reporting.json"
    try:
        chart = read_chart(chart_path, chart_path.stat().st_mtime_ns)
    except (OSError, ValueError):
        st.info("The org chart is unavailable. Use Find staff to browse the directory.")
        return
    staff = {record.id: record for record in active}
    managers = chart["manager_by_employee"]
    ordered = sorted(staff, key=lambda person_id: staff[person_id].name.casefold())
    root = chart["root"] if chart["root"] in staff else ordered[0]
    if st.session_state.get("staff_search"):
        st.button("Back to search results", on_click=return_to_search)
    focus = st.session_state.get("chart_focus")
    if focus not in staff:
        select_chart_person(root)
    chart_search([staff[person_id] for person_id in ordered])

    person = staff[st.session_state.chart_focus]
    parent = staff.get(managers.get(person.id))
    if parent or person.id != root:
        with st.container(key="chart_navigation", horizontal=True):
            if parent:
                st.button(f"Back to {parent.name}", on_click=select_chart_person, args=(parent.id,))
            if person.id != root and (parent is None or parent.id != root):
                st.button("Top of chart", on_click=select_chart_person, args=(root,))

    path = [person.name]
    seen = {person.id}
    node = parent
    while node and node.id not in seen:
        path.append(node.name)
        seen.add(node.id)
        node = staff.get(managers.get(node.id))
    if len(path) > 1:
        st.html(f'<p class="nac-chart-path">{html.escape(" / ".join(reversed(path)))}</p>')

    children = {}
    for employee in ordered:
        manager = managers.get(employee)
        if manager in staff:
            children.setdefault(manager, []).append(staff[employee])
    direct = [record for record in children.get(person.id, []) if record.id != person.id]
    with st.container(key="org_chart"):
        with st.container(border=True, key=f"org_person_{person.id}"):
            person_card(person, photo_root)
            if st.session_state.get("choose_learner_for"):
                st.button(f"Take quiz as {person.name}", type="primary", width="stretch",
                          on_click=set_learner, args=(person.name, person.id))
            issue = chart["unlinked"].get(person.id)
            if parent:
                st.caption(f"Reports to {parent.name}")
            elif issue == "supervisor_outside_directory":
                st.caption("Supervisor is outside this directory.")
            elif person.id != root:
                st.caption("No supervisor link is available for this profile.")
        if direct:
            st.html(f'<p class="nac-chart-branch">Direct reports · {len(direct)}</p>')
            st.caption("Select a name to expand their department, supervisor, and direct reports.")
            branches = "".join(report_branch(record, person, children, photo_root, {person.id})
                               for record in direct)
            st.html(f'<div class="nac-org-tree">{branches}</div>')
        else:
            st.caption("No direct reports listed in this directory.")


def directory(staff, photo_root):
    page_heading("Staff Directory")
    if st.session_state.get("choose_learner_for"):
        st.caption("Find your profile, then select the button below your name to return to the quiz.")
        st.button("Cancel profile selection", on_click=cancel_learner_selection)
    active = [record for record in staff if record.active]
    if not active:
        st.info("The staff directory will open when the approved roster is added.")
        return
    with st.container(key="directory_view_control"):
        view = st.radio("Directory view", ["Org chart", "Find staff"], horizontal=True, key="directory_view",
                        label_visibility="collapsed", width="stretch")
    if view == "Find staff":
        search_staff(active, photo_root)
    else:
        org_chart(active, photo_root)


def score_choice(mode, question, answer):
    return answer == getattr(question.staff, FIELDS[mode])


def submit_and_advance(attempt, index, *field_keys):
    if attempt.submit(index, *(st.session_state[key] for key in field_keys)):
        attempt.advance(index)


def attempt_review(attempt):
    for index, answer in sorted(attempt.answers.items()):
        yield attempt.questions[index], answer
    for question in getattr(attempt, "review_questions", ()):
        yield question, ()


def score_attempt(mode, attempt, staff):
    mastery = mode == "mastery_exam"
    rows, missed = [], set()
    names = [record.name for record in staff if record.active]
    roles = [record.role for record in staff if record.active]
    for question, answer in attempt_review(attempt):
        record = question.staff
        if mastery:
            name, role = answer or ("", "")
            row = {"correct_name": record.name, "correct_role": record.role,
                   "submitted_name": name, "submitted_role": role,
                   "name_status": grade(name, record.name, names) if answer else "Review only",
                   "role_status": grade(role, record.role, roles) if answer else "Review only"}
            correct = row["name_status"] == row["role_status"] == "Correct"
        else:
            choice = answer[0] if answer else ""
            correct = score_choice(mode, question, choice)
            row = {"staff_name": record.name, "submitted_answer": choice,
                   "correct_answer": getattr(record, FIELDS[mode]),
                   "status": ("Correct" if correct else "Incorrect") if answer else "Review only"}
        rows.append(row)
        if answer and not correct:
            missed.add(record.id)
    return QuizResult(attempt, rows, missed)


def logged_result(mode, result):
    attempt = result.attempt
    learner = getattr(attempt, "learner", None)
    if learner is None:
        return None
    answered = sum(bool(answer) for answer in attempt.answers.values())
    mastery = mode == "mastery_exam"
    names = sum(row["name_status"] == "Correct" for row in result.rows) if mastery else None
    titles = sum(row["role_status"] == "Correct" for row in result.rows) if mastery else None
    score = names + titles if mastery else answered - len(result.missed)
    status = "Ended early" if getattr(attempt, "ended_early", False) else "Completed" if answered else "Review only"
    return LoggedResult(attempt.log_id, learner.name, learner.staff_id, PAGES[mode][0],
                        "Missed questions" if getattr(attempt, "retry", None) else "Full quiz",
                        status, result.completed_at.isoformat(timespec="microseconds"), answered,
                        len(attempt.questions), score, answered * (2 if mastery else 1), names, titles)


def save_pending_results(store, pending):
    try:
        store.save(pending.values())
    except ResultsStoreError:
        return
    pending.clear()


def results_log(store):
    page_heading("Results log")
    password = private_setting("NAC_RESULTS_PASSWORD") or "moose25"
    if not isinstance(password, str) or not password.strip() or not store:
        st.info("The private results log is waiting for administrator setup.")
        return

    marker = hmac.digest(password.encode(), b"nac-connect-results-log", "sha256")
    access = st.session_state.get("results_access", b"")
    if not hmac.compare_digest(marker, access):
        with st.form("results_log_sign_in", border=True, clear_on_submit=True):
            supplied = st.text_input("Results log password", type="password", max_chars=256,
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Unlock results log", type="primary", width="stretch")
        if submitted:
            if hmac.compare_digest(supplied.encode(), password.encode()):
                st.session_state.results_access = marker
                st.rerun()
            st.error("Incorrect results log password.")
        return

    st.button("Lock results log", on_click=set_page, args=("results_access", b""))
    try:
        entries = store.read()
    except ResultsStoreError:
        st.error("The results database could not be reached. Try again in a moment.")
        st.button("Retry loading results")
        return
    if not entries:
        st.info("Results will appear here after the first named attempt ends.")
        return
    labels = {
        "participant": "Participant", "quiz": "Quiz", "result": "Score", "status": "Status",
        "attempt_type": "Attempt type",
        "completed_at_utc": "Recorded at (UTC)", "questions_answered": "Answered", "quiz_questions": "Questions",
        "names_correct": "Names correct", "titles_correct": "Titles correct", "staff_id": "Staff ID",
    }
    rows = [dict(zip(COLUMNS, entry)) for entry in entries]
    st.caption(f"{len(rows)} {'attempt' if len(rows) == 1 else 'attempts'} recorded. Participant names are self-reported.")
    display_rows = [{**row, "result": f"{row['score']} / {row['possible']}" if row["possible"] else "—"}
                    for row in rows]
    st.dataframe(display_rows, width="stretch", hide_index=True, column_order=list(labels), column_config=labels)
    csv_rows = ({key: spreadsheet_value(value) for key, value in row.items()} for row in rows)
    st.download_button("Download results log CSV", csv_text(COLUMNS, csv_rows), "nac-results-log.csv", "text/csv",
                       on_click="ignore")


def quiz_history(photo_root):
    page_heading("Quiz history")
    st.caption("Results are available while you stay signed in to this browser session.")
    modes = [mode for mode in PAGES if st.session_state.quiz_results.get(mode)]
    if not modes:
        st.info("Complete a quiz to see its results here.")
        return
    mode = st.selectbox("Quiz", modes, format_func=lambda key: PAGES[key][0])
    attempt = st.session_state.attempts.get(mode)
    if attempt and not attempt.finished:
        st.button(f"Resume {PAGES[mode][0]}", on_click=go, args=(mode,))
    results(mode, photo_root)


def results(mode, photo_root, restart=None):
    mastery = mode == "mastery_exam"
    history = st.session_state.quiz_results[mode]

    def attempt_label(index):
        label = f"Attempt {index + 1}"
        saved_attempt = history[index].attempt
        if getattr(saved_attempt, "ended_early", False):
            return f"{label} · Ended early"
        retry = getattr(saved_attempt, "retry", None)
        if retry is None:
            return label
        return f"{label} · {'Missed questions' if retry else 'Full quiz'}"

    scope = f"{st.session_state.page}-{mode}"
    if len(history) > 1:
        selected = st.selectbox("Attempt", range(len(history) - 1, -1, -1),
                                format_func=attempt_label, key=f"{scope}-attempt-{len(history)}")
    else:
        selected = 0
        st.caption(attempt_label(selected))
    result = history[selected]
    attempt, rows, missed = result.attempt, result.rows, result.missed
    ended_early = getattr(attempt, "ended_early", False)
    learner = getattr(attempt, "learner", None)
    recorded = result.completed_at.strftime("%b %d, %Y at %H:%M UTC")
    st.caption(f"{learner.name} · {recorded}" if learner else recorded)

    total = sum(bool(answer) for answer in attempt.answers.values())
    if ended_early:
        st.caption(f"{total} of {len(attempt.questions)} questions answered. Scores reflect submitted answers.")
    review_only = len(rows) - total
    if review_only:
        st.caption(f"{review_only} staff profiles are available for review alongside your scored answers.")
    if not total:
        st.info("There were no graded questions in this attempt.")
    elif mastery:
        name_score = sum(row["name_status"] == "Correct" for row in rows)
        role_score = sum(row["role_status"] == "Correct" for row in rows)
        score = f"{name_score + role_score} / {2 * total}"
        with st.container(key="mastery_scores"):
            overall, name_metric, role_metric = st.columns(3)
        overall.metric("Overall score", score)
        name_metric.metric("Name recall", f"{name_score} / {total}")
        role_metric.metric("Role recall", f"{role_score} / {total}")
        if any("Review" in (row["name_status"], row["role_status"]) for row in rows):
            st.info("Answers marked Needs review are flagged for manual confirmation.")
    else:
        score = f"{total - len(missed)} / {total}"
        with st.container(key="result_metrics"):
            st.metric("Score on answered questions" if ended_early else "Final score", score)
        if total and not missed and not ended_early:
            st.success("You got every answer right.")

    rows_for_export = ({"mode": "staff", **row} for row in rows)
    download = csv_text(
        ["mode", *rows[0]], ({key: spreadsheet_value(value) for key, value in row.items()}
                             for row in rows_for_export)
    )
    with st.container(key="result_actions"):
        export = st
        if restart is not None:
            retry = bool(missed) and not mastery
            columns = st.columns(3 if retry else 2)
            if retry:
                columns[0].button("Retry missed questions", type="primary", width="stretch",
                                  on_click=restart, args=(missed,))
            export = columns[-2]
            columns[-1].button("Restart quiz", width="stretch", on_click=restart)
        export.download_button("Download results CSV", download, f"nac-{mode}.csv", "text/csv",
                               width="stretch", on_click="ignore")

    if total and not ended_early and not missed and getattr(attempt, "retry", None) is False:
        show_certificate(mode, selected + 1, score, result.completed_at, scope, learner.name if learner else "")

    st.subheader("Photographic answer key" if mastery else "Review answers")
    review_key = f"{scope}-{selected}-review"
    page_key = f"{review_key}-page"
    filters = ["All answers", "Missed or flagged"]
    if review_only:
        filters.append("Review-only profiles")
    with st.container(key="answer_view"):
        view = st.radio("Show answers", filters, horizontal=True,
                        index=0 if mastery or not missed else 1, key=f"{review_key}-filter",
                        on_change=set_page, args=(page_key, 1), width="stretch")
    review = [(question, answer, row) for (question, answer), row in zip(attempt_review(attempt), rows)
              if view == "All answers"
              or (view == "Missed or flagged" and question.staff.id in missed)
              or (view == "Review-only profiles" and not answer)]
    if not review:
        st.info("No answers need review.")
        return
    visible, page, pages = page_slice(review, page_key, size=8)
    with st.container(key="review_cards"):
        for question, answer, row in visible:
            with st.container(border=True, key=f"review_{question.staff.id}"):
                person_card(question.staff, photo_root)
                if not answer:
                    st.caption("Review only")
                    continue
                if mastery:
                    details = [
                        ("Name you entered", row["submitted_name"] or "Blank", row["name_status"]),
                        ("Job title you entered", row["submitted_role"] or "Blank", row["role_status"]),
                    ]
                else:
                    details = [("Your answer", row["submitted_answer"], row["status"])]
                    if row["status"] != "Correct":
                        details.append(("Correct answer", row["correct_answer"], ""))
                review_markup = "".join(
                    f'<div><dt>{html.escape(label)}{answer_status(status) if status else ""}</dt>'
                    f'<dd>{html.escape(value)}</dd></div>' for label, value, status in details
                )
                st.html(f'<dl class="nac-review">{review_markup}</dl>')
    page_controls(page_key, page, pages)


def show_certificate(mode, attempt_number, score, completed_at, scope, learner_name):
    from utils.print_certificate import certificate_pdf

    awarded = completed_at.strftime("%b %d, %Y at %H:%M:%S %Z")
    names = st.session_state.setdefault("certificate_names", {})
    certificate_key = (mode, attempt_number)
    with st.container(border=True, key="completion_certificate"):
        st.subheader("Completion certificate")
        st.caption(f"Awarded {awarded}")
        with st.form(f"{scope}-{attempt_number}-certificate-name", border=False):
            learner = st.text_input("Name on certificate (optional)", value=names.get(certificate_key, learner_name),
                                    max_chars=100, autocomplete="off")
            if st.form_submit_button("Apply name"):
                names[certificate_key] = learner.strip()
        recipient = names.get(certificate_key, learner_name)
        if recipient:
            st.html(f'<p class="nac-certificate-recipient">PDF prepared for {html.escape(recipient)}</p>')
        pdf = certificate_pdf(title=PAGES[mode][0], attempt_number=attempt_number, score=score,
                              awarded=awarded, learner=recipient,
                              wordmark=ROOT / "assets/nac-wordmark.png")
        st.download_button("Download certificate (PDF)", pdf, f"nac-{mode}-attempt-{attempt_number}-certificate.pdf",
                           "application/pdf", width="stretch", on_click="ignore")


def close_quiz_options():
    st.session_state.pop("quiz_option", None)


@st.dialog("Quiz options", on_dismiss=close_quiz_options)
def quiz_options(mode, attempt, restart):
    action = st.session_state.quiz_option
    if action == "menu":
        st.caption("Pause keeps your submitted answers and your place in this session.")
        if st.button("Pause quiz", type="primary", width="stretch"):
            close_quiz_options()
            go("home")
            st.rerun()
        st.button("Restart quiz", width="stretch", on_click=set_page, args=("quiz_option", "restart"))
        st.button("End quiz", width="stretch", on_click=set_page, args=("quiz_option", "end"))
        return

    if action == "restart":
        st.write("Restart from the first question? This clears the answers in your current attempt.")
        if st.button("Confirm restart", type="primary", width="stretch"):
            retry_ids = ({question.staff.id for question in attempt.questions}
                         if getattr(attempt, "retry", None) else None)
            close_quiz_options()
            restart(retry_ids)
            st.rerun()
    else:
        message = ("End this attempt and review the answers you’ve submitted?" if attempt.answers
                   else "End this attempt and return Home?")
        st.write(message)
        if st.button("Confirm end", type="primary", width="stretch"):
            close_quiz_options()
            if attempt.answers:
                attempt.end()
            else:
                st.session_state.attempts.pop(mode, None)
                go("home")
            st.rerun()
    if st.button("Keep taking quiz", width="stretch"):
        close_quiz_options()
        st.rerun()


def quiz(mode, staff, photo_root, store):
    title, level, description = PAGES[mode]
    key = mode
    mastery = mode == "mastery_exam"

    def prepare_questions(ids=None):
        # A live Streamlit worker can rerun this script with the previous quiz module still loaded.
        quiz_staff = staff
        if mode == "name_recall" and not hasattr(Question, "review_only"):
            quiz_staff = [person for person in staff if photo_path(person, photo_root) is not None]
        available = make_questions(mode, quiz_staff, photo_root, ids=ids)
        if not mastery:
            return available, []
        questions, review_questions = [], []
        for question in available:
            review_only = getattr(question, "review_only", None)
            if review_only is None:
                review_only = photo_path(question.staff, photo_root) is None
            (review_questions if review_only else questions).append(question)
        review_questions.sort(key=lambda question: question.staff.name.casefold())
        return questions, review_questions

    def start_attempt(questions, review_questions, *, retry=False):
        learner = st.session_state.get("quiz_learner")
        if not learner or (not questions and not review_questions):
            st.session_state.attempts[key] = None
            return
        attempt = Attempt(questions, retry=retry)
        attempt.review_questions = review_questions
        attempt.learner = learner
        attempt.log_id = uuid4().hex
        st.session_state.attempts[key] = attempt

    def restart(ids=None):
        start_attempt(*prepare_questions(ids), retry=ids is not None)

    attempt = st.session_state.attempts.get(key)
    if attempt is None or attempt.finished:
        page_heading(title)
    if attempt is not None and attempt.finished:
        results(mode, photo_root, restart)
        return
    learner = getattr(attempt, "learner", None) or st.session_state.get("quiz_learner")
    if learner is None:
        if attempt is not None:
            page_heading(title)
        learner_form(mode, store)
        return
    if attempt is not None and getattr(attempt, "learner", None) is None:
        # Attach a learner to an in-progress attempt created before results logging was introduced.
        attempt.learner = learner
        attempt.log_id = uuid4().hex
    if attempt is None:
        questions, review_questions = prepare_questions()
        with st.container(key="quiz_learner"):
            st.caption(f"Taking this quiz as {learner.name}")
            st.button("Change quiz participant", on_click=set_page, args=("quiz_learner", None))
        with st.container(border=True, key="mastery_intro" if mastery else "quiz_intro"):
            if not questions and not review_questions:
                st.info("Name Recall opens when eligible staff have portraits." if mode == "name_recall"
                        else "This quiz opens when the roster includes eligible staff.")
                return
            if mastery:
                review_count = len(review_questions)
                portrait_count = len(questions)
                st.html(f'<p class="nac-mastery-count"><strong>{portrait_count}</strong> portrait questions</p>')
                if portrait_count:
                    st.write("Enter each person’s full name and job title. Scores and answers appear after submission.")
                if review_count:
                    st.caption(f"{review_count} staff profiles without portraits appear in the answer key for review.")
                start_label = "Start exam" if portrait_count else "Review staff"
            else:
                st.markdown(f"**{level} · {len(questions)} questions**")
                st.html(f'<p class="nac-intro">{html.escape(description)}</p>')
                st.write("Get feedback after each answer, then review and retry missed questions.")
                start_label = "Start quiz"
            st.caption("Progress is saved for this browser session.")
            st.button(start_label, type="primary", width="stretch", on_click=start_attempt,
                      args=(questions, review_questions))
        return
    index = attempt.index
    question = attempt.questions[index]
    total = len(attempt.questions)
    answered = index in attempt.answers
    score_markup = ""
    graded_count = sum(bool(answer) for answer in attempt.answers.values())
    if not mastery and graded_count:
        score = sum(score_choice(mode, attempt.questions[i], answer[0])
                    for i, answer in attempt.answers.items() if answer)
        score_markup = f'<span role="status">Score {score}/{graded_count}</span>'
    with st.container(border=True, key="quiz_content"):
        with st.container(key="quiz_header"):
            label, navigation = st.columns([3, 1])
            item = "Portrait" if mastery else "Question"
            label.html(f'<h1 class="nac-heading">{html.escape(title)}</h1>'
                       f'<p class="nac-quiz-facts"><span>{item} {index + 1} of {total}</span>{score_markup}</p>')
            navigation.button("Quiz options", on_click=set_page, args=("quiz_option", "menu"))
        st.progress(len(attempt.answers) / total)

        with st.container(key="quiz_layout"):
            portrait_column, response = st.columns([1, 2])
            with portrait_column:
                if mastery:
                    with st.container(key="mastery_portrait"):
                        has_photo = display_quiz_photo(question.staff, photo_root)
                else:
                    with st.container(key="quiz_identity"):
                        photo, prompt_column = st.columns([1, 2])
                        with photo:
                            has_photo = display_quiz_photo(question.staff, photo_root)
                        name = ""
                        if mode == "role_recall":
                            name = (f'<h2 class="nac-heading nac-question-title">'
                                    f'{html.escape(question.staff.name)}</h2>')
                        if mode == "role_recall" or has_photo:
                            prompt = "What is their job title?" if mode == "role_recall" else "Who is this?"
                            prompt_column.html(f'<div class="nac-quiz-prompt">{name}<p class="nac-prompt">{prompt}</p></div>')
            with response:
                if (mode != "role_recall" and not has_photo) or (not mastery and not question.options):
                    st.caption("This profile will appear in the answer review as an unscored item.")
                    st.button("See results" if index + 1 == total else "Continue", type="primary", width="stretch",
                              on_click=submit_and_advance, args=(attempt, index))
                elif mastery:
                    name_key, role_key = f"exam-name-{index}", f"exam-role-{index}"
                    with st.form(f"exam-{index}", clear_on_submit=True, border=False):
                        st.text_input("Name", max_chars=150, autocomplete="off", key=name_key)
                        st.text_input("Job title", max_chars=200, autocomplete="off", key=role_key)
                        st.form_submit_button("Submit exam" if index + 1 == total else "Save and continue",
                                              type="primary", width="stretch", on_click=submit_and_advance,
                                              args=(attempt, index, name_key, role_key))
                elif not answered:
                    with st.container(key="quiz_choices"):
                        for option_index, option in enumerate(question.options):
                            st.button(option, key=f"option-{mode}-{index}-{option_index}", width="stretch",
                                      on_click=attempt.submit, args=(index, option))
                else:
                    quiz_feedback(mode, question, attempt.answers[index][0])
                    st.button("See results" if index + 1 == total else "Next question", type="primary",
                              width="stretch", on_click=attempt.advance, args=(index,))
    if st.session_state.get("quiz_option"):
        quiz_options(mode, attempt, restart)


def answer_status(status):
    tone, label = {"Correct": ("correct", "Correct"), "Incorrect": ("incorrect", "Incorrect"),
                   "Review": ("review", "Needs review")}[status]
    return f'<span class="nac-answer-status" data-outcome="{tone}">{label}</span>'


def quiz_feedback(mode, question, answer):
    expected = getattr(question.staff, FIELDS[mode])
    correct = score_choice(mode, question, answer)
    status = "Correct" if correct else "Incorrect"
    context = question.staff.department if mode == "role_recall" else f"{question.staff.role} · {question.staff.department}"
    choice = "" if correct else f'<p>Selected <span>{html.escape(answer)}</span></p>'
    with st.container(key="quiz_feedback"):
        st.html(f'<div class="nac-feedback" role="status" aria-atomic="true" data-outcome="{status.lower()}">'
                f'{answer_status(status)}<strong>{html.escape(expected)}</strong>'
                f'<p>{html.escape(context)}</p>{choice}</div>')


@st.cache_data(show_spinner=False, max_entries=8)
def read_roster(path, photo_root, roster_mtime, photos_mtime):
    return load(path.read_text(encoding="utf-8-sig"), photo_root)


require_app_password()

database_url = private_setting("NAC_RESULTS_DATABASE_URL")
sqlite_path = private_setting("NAC_RESULTS_SQLITE_PATH")
store = ResultsStore(database_url, sqlite_path) if database_url or sqlite_path else None
page = st.session_state.page
current_attempt = st.session_state.attempts.get(page)
if current_attempt is None or current_attempt.finished:
    brand()

if page == "admin" and os.getenv("NAC_LOCAL_ADMIN") == "1":
    from utils.admin import roster_manager

    st.button("Home", on_click=go, args=("home",))
    roster_manager(ROOT)
    st.stop()

photo_root = ROOT / "assets/staff"
roster_path = ROOT / "data/staff.csv"
try:
    staff, errors, _ = read_roster(roster_path, photo_root, roster_path.stat().st_mtime_ns,
                                   photo_root.stat().st_mtime_ns)
except (OSError, UnicodeError):
    staff, errors = [], ["Unable to load roster."]
if errors:
    st.warning("The roster needs attention. Contact the roster administrator.")
    staff = []
pending = st.session_state.setdefault("pending_results", {})
new_results = False
for mode, attempt in st.session_state.attempts.items():
    if attempt is not None and attempt.finished:
        history = st.session_state.quiz_results.setdefault(mode, [])
        if not history or history[-1].attempt is not attempt:
            result = score_attempt(mode, attempt, staff)
            history.append(result)
            if store and (entry := logged_result(mode, result)):
                pending[entry.attempt_id] = entry
                new_results = True
if store and pending:
    if new_results or st.session_state.pop("retry_result_log", False):
        save_pending_results(store, pending)
    if pending:
        st.warning("A score is waiting to be saved to the results log. Keep this session open and retry saving.")
        st.button("Retry saving results", on_click=set_page, args=("retry_result_log", True))
if page == "directory":
    directory(staff, photo_root)
elif page == "quiz_history":
    quiz_history(photo_root)
elif page == "results_log":
    results_log(store)
elif page in PAGES:
    quiz(page, staff, photo_root, store)
else:
    home()
