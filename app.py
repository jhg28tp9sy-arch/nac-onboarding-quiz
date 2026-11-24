import base64
import hmac
import html
import io
import json
import os
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from utils.quiz import Attempt, FIELDS, make_questions
from utils.roster import csv_text, load, portrait
from utils.scoring import grade, normalize, spreadsheet_value

ROOT = Path(__file__).resolve().parent
PAGES = {
    "directory": ("Staff Directory", "Reference", "Look up coworkers, job titles, and reporting lines."),
    "role_recall": ("Role Recall", "Beginner", "Match coworkers to their job titles and learn which teams they work on."),
    "name_recall": ("Name Recall", "Intermediate", "Match faces to names, then see each coworker’s job title and department."),
    "mastery_exam": ("Mastery Exam", "Advanced", "Recall each coworker’s name and job title from their portrait."),
}
STAFF_FILTERS = ("staff_query", "staff_department", "staff_sort", "staff_page")

st.set_page_config(page_title="NAC Connect", page_icon=str(ROOT / "assets/logo.png"), layout="wide")
stylesheet = (ROOT / "assets/nac.css").read_text(encoding="utf-8")
st.markdown(f"<style>{stylesheet}</style>", unsafe_allow_html=True)

st.session_state.setdefault("page", "home")
st.session_state.setdefault("attempts", {})


def go(page):
    st.session_state.page = page


def heading(title):
    st.markdown(f'<h1 class="nac-heading">{html.escape(title)}</h1>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def brand_image():
    return base64.b64encode((ROOT / "assets/nac-wordmark.png").read_bytes()).decode()


def brand():
    wordmark = brand_image()
    st.markdown('<div class="nac-brand"><img alt="National Ability Center" '
                f'src="data:image/png;base64,{wordmark}"><span>Employee onboarding</span></div>',
                unsafe_allow_html=True)


def require_app_password():
    try:
        password = st.secrets.get("NAC_ACCESS_PASSWORD") or st.secrets.get("NAC_DEMO_PASSWORD")
    except StreamlitSecretNotFoundError:
        password = None

    if not isinstance(password, str) or not password.strip():
        password = "wyser"  # Public test password. Set NAC_ACCESS_PASSWORD to override it.

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
def photo_bytes(path, modified_ns, thumbnail_width=0):
    image = portrait(path)
    if image is None:
        return None
    if thumbnail_width:
        image.thumbnail((thumbnail_width, thumbnail_width * 5 // 4))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80 if thumbnail_width else 85, optimize=True)
    return buffer.getvalue()


def roster_photo(record, root, *, thumbnail_width=0):
    filename = Path(record.photo)
    path = (root / filename).resolve()
    valid = (filename.name == record.photo and path.parent == root.resolve()
             and filename.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    try:
        return photo_bytes(str(path), path.stat().st_mtime_ns, thumbnail_width) if valid else None
    except OSError:
        return None


def display_photo(record, root, *, width=220):
    image = roster_photo(record, root)
    if image is None:
        st.markdown('<div class="nac-placeholder">Photo unavailable</div>', unsafe_allow_html=True)
    else:
        st.image(image, width=width)


def thumbnail_markup(record, photo_root, width=160):
    image = roster_photo(record, photo_root, thumbnail_width=width)
    if image:
        encoded = base64.b64encode(image).decode()
        return f'<img alt="" loading="lazy" decoding="async" src="data:image/jpeg;base64,{encoded}">'
    return '<span class="nac-person-placeholder" aria-hidden="true"></span>'


def person_card(record, photo_root):
    name, role, department = map(html.escape, (record.name, record.role, record.department))
    st.markdown(
        f'<div class="nac-person">{thumbnail_markup(record, photo_root)}<div class="nac-person-copy">'
        f'<h2>{name}</h2><p>{role}</p><p class="nac-level">{department}</p></div></div>',
        unsafe_allow_html=True,
    )
    if record.bio:
        st.markdown(f'<p class="nac-bio">{html.escape(record.bio)}</p>', unsafe_allow_html=True)


def home():
    with st.container(key="home_intro"):
        st.markdown('<div class="nac-hero"><h1>NAC Connect</h1>'
                    '<p>Get to know the people behind NAC. Learn names, job titles, and how teams fit together.</p></div>',
                    unsafe_allow_html=True)
        with st.container(key="study_card"):
            st.button("Open Staff Directory", key="directory", width="stretch",
                      type="primary", on_click=go, args=("directory",))

    st.markdown('<h2 class="nac-section-title">Onboarding quizzes</h2>', unsafe_allow_html=True)
    with st.container(key="activity_grid"):
        quizzes = [(page, details) for page, details in PAGES.items() if page != "directory"]
        for (page, (title, level, description)), column in zip(quizzes, st.columns(3)):
            with column, st.container(border=True, key=f"activity_{page}"):
                attempt = st.session_state.attempts.get(page)
                action, progress = f"Open {title}", ""
                if attempt:
                    if attempt.finished:
                        action, progress = f"Review {title}", "Completed this session"
                    else:
                        action = f"Resume {title}"
                        progress = f"{len(attempt.answers)} of {len(attempt.questions)} answered"
                progress_markup = f'<p class="nac-activity-status">{progress}</p>' if progress else ""
                st.markdown(f'<div class="nac-card nac-activity"><span class="nac-level">{level}</span>'
                            f'<h3>{title}</h3><p>{description}</p>{progress_markup}</div>',
                            unsafe_allow_html=True)
                st.button(action, key=page, width="stretch", on_click=go, args=(page,),
                          type="primary" if page == "role_recall" else "secondary")
    if os.getenv("NAC_LOCAL_ADMIN") == "1":
        st.button("Roster manager", on_click=go, args=("admin",))
    st.button("Sign out", type="tertiary", on_click=st.session_state.clear)


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
        count.markdown(f'<p class="nac-page-count">{active} of {pages}</p>', unsafe_allow_html=True)
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


def search_staff(active, photo_root):
    for key, value in st.session_state.pop("staff_search", {}).items():
        st.session_state.setdefault(key, value)
    with st.container(key="directory_filters"):
        search, filter_column, order = st.columns([2, 1, 1])
    query = search.text_input("Search by name, role, or department", key="staff_query",
                              on_change=set_page, args=("staff_page", 1))
    departments = sorted({record.department for record in active}, key=str.casefold)
    selected = filter_column.selectbox("Department", [None, *departments], key="staff_department",
                                       format_func=lambda item: item or "All departments",
                                       on_change=set_page, args=("staff_page", 1))
    sorting = order.selectbox("Sort by name", ["A to Z", "Z to A"], key="staff_sort",
                              on_change=set_page, args=("staff_page", 1))
    terms = normalize(query).split()
    matches = []
    for record in active:
        haystack = normalize(f"{record.name} {record.role} {record.department}")
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
            for record, column in zip(visible[offset:offset + 3], st.columns(3)):
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
    st.session_state.chart_person_picker = person_id


def jump_to_chart_person():
    st.session_state.chart_focus = st.session_state.chart_person_picker


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
        f'<summary class="nac-org-summary">{thumbnail_markup(record, photo_root, width=120)}'
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
    else:
        st.session_state.setdefault("chart_person_picker", focus)
    st.selectbox("Jump to an employee", ordered, key="chart_person_picker",
                 format_func=lambda person_id: staff[person_id].name, on_change=jump_to_chart_person)

    person = staff[st.session_state.chart_focus]
    parent = staff.get(managers.get(person.id))
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
        st.markdown(f'<p class="nac-chart-path">{html.escape(" / ".join(reversed(path)))}</p>',
                    unsafe_allow_html=True)

    children = {}
    for employee in ordered:
        manager = managers.get(employee)
        if manager in staff:
            children.setdefault(manager, []).append(staff[employee])
    direct = [record for record in children.get(person.id, []) if record.id != person.id]
    with st.container(key="org_chart"):
        with st.container(border=True, key=f"org_person_{person.id}"):
            person_card(person, photo_root)
            issue = chart["unlinked"].get(person.id)
            if parent:
                st.caption(f"Reports to {parent.name}")
            elif issue == "supervisor_outside_directory":
                st.caption("Supervisor is outside this directory.")
            elif person.id != root:
                st.caption("No supervisor link is available for this profile.")
        if direct:
            st.markdown(f'<p class="nac-chart-branch">Direct reports · {len(direct)}</p>',
                        unsafe_allow_html=True)
            st.caption("Select a name to expand their department, supervisor, and direct reports.")
            branches = "".join(report_branch(record, person, children, photo_root, {person.id})
                               for record in direct)
            st.html(f'<div class="nac-org-tree">{branches}</div>')
        else:
            st.caption("No direct reports listed in this directory.")


def directory(staff, photo_root):
    heading("Staff Directory")
    active = [record for record in staff if record.active]
    if not active:
        st.info("The staff directory will open when the approved roster is added.")
        return
    with st.container(key="directory_view_control"):
        view = st.radio("Directory view", ["Org chart", "Find staff"], horizontal=True, key="directory_view")
    if view == "Find staff":
        search_staff(active, photo_root)
    else:
        org_chart(active, photo_root)


def score_choice(mode, question, answer):
    return answer == getattr(question.staff, FIELDS[mode])


def submit_exam_answer(attempt, index, name_key, role_key):
    if attempt.submit(index, st.session_state[name_key], st.session_state[role_key]):
        attempt.advance(index)


def results(mode, attempt, staff, photo_root, restart):
    mastery = mode == "mastery_exam"
    rows, missed = [], set()
    names = [record.name for record in staff if record.active]
    roles = [record.role for record in staff if record.active]
    for index, question in enumerate(attempt.questions):
        record = question.staff
        answer = attempt.answers[index]
        if mastery:
            row = {"correct_name": record.name, "correct_role": record.role,
                   "submitted_name": answer[0], "submitted_role": answer[1],
                   "name_status": grade(answer[0], record.name, names),
                   "role_status": grade(answer[1], record.role, roles)}
            correct = row["name_status"] == row["role_status"] == "Correct"
        else:
            correct = score_choice(mode, question, answer[0])
            row = {"staff_name": record.name, "submitted_answer": answer[0],
                   "correct_answer": getattr(record, FIELDS[mode]),
                   "status": "Correct" if correct else "Incorrect"}
        rows.append(row)
        if not correct:
            missed.add(record.id)

    total = len(rows)
    if mastery:
        name_score = sum(row["name_status"] == "Correct" for row in rows)
        role_score = sum(row["role_status"] == "Correct" for row in rows)
        with st.container(key="result_metrics"):
            overall, name_metric, role_metric = st.columns(3)
        overall.metric("Overall score", f"{name_score + role_score} / {2 * total}")
        name_metric.metric("Name recall", f"{name_score} / {total}")
        role_metric.metric("Role recall", f"{role_score} / {total}")
        if any("Review" in (row["name_status"], row["role_status"]) for row in rows):
            st.info("Answers marked Review need manual confirmation and have not earned credit.")
    else:
        with st.container(key="result_metrics"):
            st.metric("Final score", f"{total - len(missed)} / {total}")
        if not missed:
            st.success("You got every answer right.")

    rows_for_export = ({"mode": "staff", **row} for row in rows)
    download = csv_text(
        ["mode", *rows[0]], ({key: spreadsheet_value(value) for key, value in row.items()}
                             for row in rows_for_export)
    )
    with st.container(key="result_actions"):
        columns = st.columns(3 if missed and not mastery else 2)
        retry = missed and not mastery
        if retry:
            columns[0].button("Retry missed questions", type="primary", width="stretch",
                              on_click=restart, args=(missed,))
        columns[-2].download_button("Download results CSV", download, f"nac-{mode}.csv", "text/csv",
                                    width="stretch", on_click="ignore")
        columns[-1].button("Restart quiz", width="stretch", on_click=restart)

    st.subheader("Photographic answer key" if mastery else "Review answers")
    page_key = f"{mode}-review-page"
    view = st.radio("Show answers", ["All answers", "Missed or flagged"], horizontal=True,
                    index=0 if mastery or not missed else 1, key=f"{mode}-review-filter",
                    on_change=set_page, args=(page_key, 1))
    review = [(question, row) for question, row in zip(attempt.questions, rows)
              if view == "All answers" or question.staff.id in missed]
    if not review:
        st.info("No answers need review.")
        return
    visible, page, pages = page_slice(review, page_key, size=8)
    with st.container(key="review_cards"):
        for question, row in visible:
            with st.container(border=True):
                person_card(question.staff, photo_root)
                if mastery:
                    details = [
                        (f"Name · {row['name_status']}", row["submitted_name"] or "Blank"),
                        (f"Job title · {row['role_status']}", row["submitted_role"] or "Blank"),
                    ]
                else:
                    details = [
                        (f"Your answer · {row['status']}", row["submitted_answer"]),
                        ("Correct answer", row["correct_answer"]),
                    ]
                review_markup = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
                                        for label, value in details)
                st.markdown(f'<dl class="nac-review">{review_markup}</dl>', unsafe_allow_html=True)
    page_controls(page_key, page, pages)


def quiz(mode, staff, photo_root):
    title, level, description = PAGES[mode]
    key = mode
    mastery = mode == "mastery_exam"

    def restart(ids=None):
        questions = make_questions(mode, staff, photo_root, ids=ids)
        st.session_state.attempts[key] = Attempt(questions) if questions else None

    attempt = st.session_state.attempts.get(key)
    if attempt is None:
        heading(title)
        available = make_questions(mode, staff, photo_root)
        with st.container(key="quiz_intro"):
            if not available:
                message = "This quiz opens when the roster includes eligible staff with valid photos."
                if not mastery:
                    message += " Multiple-choice quizzes also need four distinct answer choices."
                st.info(message)
                return
            st.markdown(f"**{level} · {len(available)} questions**")
            st.markdown(f'<div class="nac-intro"><p>{html.escape(description)}</p></div>',
                        unsafe_allow_html=True)
            if mastery:
                st.write("Enter a full name and job title for each portrait. The answer key opens after submission.")
            else:
                st.write("Get feedback after each answer, then review and retry missed questions.")
            st.caption("Progress is saved for this browser session.")
            st.button("Start exam" if mastery else "Start quiz", type="primary", width="stretch", on_click=restart)
        return
    if attempt.finished:
        heading(title)
        results(mode, attempt, staff, photo_root, restart)
        return

    index = attempt.index
    question = attempt.questions[index]
    total = len(attempt.questions)
    answered = index in attempt.answers
    score_markup = ""
    if not mastery and attempt.answers:
        score = sum(score_choice(mode, attempt.questions[i], answer[0])
                    for i, answer in attempt.answers.items())
        score_markup = f'<span role="status">Score {score}/{len(attempt.answers)}</span>'
    with st.container(border=True, key="quiz_content"):
        with st.container(key="quiz_header"):
            label, navigation = st.columns([3, 1], vertical_alignment="center")
            label.markdown(f'<h1 class="nac-heading">{html.escape(title)}</h1>'
                           f'<p class="nac-quiz-facts"><span>Question {index + 1} of {total}</span>'
                           f'{score_markup}</p>', unsafe_allow_html=True)
            navigation.button("Pause exam" if mastery else "Home", type="tertiary", on_click=go, args=("home",))
        st.progress(len(attempt.answers) / total)

        with st.container(key="quiz_layout"):
            portrait_column, response = st.columns([1, 2], vertical_alignment="center")
            with portrait_column:
                if mastery:
                    display_photo(question.staff, photo_root, width=216)
                else:
                    with st.container(key="quiz_identity"):
                        photo, prompt_column = st.columns([1, 2], vertical_alignment="center")
                        with photo:
                            display_photo(question.staff, photo_root, width=180)
                        with prompt_column:
                            if mode == "role_recall":
                                st.markdown(f'<h2 class="nac-heading nac-question-title">'
                                            f'{html.escape(question.staff.name)}</h2>', unsafe_allow_html=True)
                            prompt = "What is their job title?" if mode == "role_recall" else "Who is this?"
                            st.markdown(f'<p class="nac-prompt">{prompt}</p>', unsafe_allow_html=True)
            with response:
                if mastery:
                    name_key, role_key = f"exam-name-{index}", f"exam-role-{index}"
                    with st.form(f"exam-{index}", clear_on_submit=True, border=False):
                        st.text_input("Name", max_chars=150, autocomplete="off", key=name_key)
                        st.text_input("Job title", max_chars=200, autocomplete="off", key=role_key)
                        st.form_submit_button("Submit exam" if index + 1 == total else "Save and continue",
                                              type="primary", width="stretch", on_click=submit_exam_answer,
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


def quiz_feedback(mode, question, answer):
    with st.container(key="quiz_feedback"):
        if score_choice(mode, question, answer):
            st.success("Correct.")
        else:
            expected = getattr(question.staff, FIELDS[mode])
            st.error(f"The correct answer is {expected}.")
            st.caption(f"You chose {answer}.")
        context = (question.staff.department if mode == "role_recall"
                   else f"{question.staff.role} · {question.staff.department}")
        st.markdown(f'<p class="nac-feedback">{html.escape(context)}</p>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=8)
def read_roster(path, photo_root, roster_mtime, photos_mtime):
    return load(path.read_text(encoding="utf-8-sig"), photo_root)


require_app_password()

page = st.session_state.page
current_attempt = st.session_state.attempts.get(page)
if current_attempt is None or current_attempt.finished:
    brand()
    if page != "home":
        st.button("Home", type="tertiary", on_click=go, args=("home",))

if page == "admin" and os.getenv("NAC_LOCAL_ADMIN") == "1":
    from utils.admin import roster_manager

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
if page == "directory":
    directory(staff, photo_root)
elif page in PAGES:
    quiz(page, staff, photo_root)
else:
    home()
