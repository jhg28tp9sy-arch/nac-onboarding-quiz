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
from utils.scoring import grade, spreadsheet_value

ROOT = Path(__file__).resolve().parent
PAGES = {
    "directory": ("Staff Directory", "Reference", "Look up coworkers, job titles, and departments."),
    "role_recall": ("Role Recall", "Beginner", "Match coworkers to their job titles and learn which teams they work on."),
    "name_recall": ("Name Recall", "Intermediate", "Match faces to names, then see each coworker’s job title and department."),
    "mastery_exam": ("Mastery Exam", "Advanced", "Recall each coworker’s name and job title from their portrait."),
}

st.set_page_config(page_title="NAC Connect", page_icon=str(ROOT / "assets/logo.png"), layout="wide")
st.markdown("""
<style>
.stApp {
    --nac-navy: #003c69;
    --nac-orange: #c75b23;
    --nac-peach: #ffcfb7;
    --nac-mist: #f2f5f7;
    --nac-ink: #18334a;
    --nac-line: #d8e1e9;
    --nac-display: Futura, "Century Gothic", "Trebuchet MS", system-ui, sans-serif;
    background: #fbfcfd;
}
.block-container { max-width: 68rem; padding: 3.75rem clamp(1rem, 4vw, 3rem) 4rem; }
.nac-brand {
    display:flex; justify-content:space-between; align-items:center; gap:.75rem;
    min-height:4.75rem; padding:.7rem clamp(1rem, 4vw, 2rem);
    color:#fff; background:var(--nac-navy); border-radius:.8rem;
}
.nac-brand img { display:block; width:9.5rem; max-width:48%; height:auto; }
.nac-brand span {
    font:700 .85rem/1.25 var(--nac-display); text-align:right;
    letter-spacing:.045em;
}
.nac-hero {
    background:linear-gradient(110deg, #fff 50%, #fff1e9 100%);
    border:1px solid var(--nac-line); border-left:.3rem solid var(--nac-orange);
    border-radius:.8rem; padding:clamp(1.7rem, 4vw, 3.2rem); margin:.7rem 0 .9rem;
}
.stApp .nac-hero h1, .stApp .nac-heading {
    color:var(--nac-navy); font-family:var(--nac-display);
    letter-spacing:-.04em; line-height:1.08; margin:0; padding:0; font-weight:750;
}
.stApp .nac-hero h1 { font-size:clamp(2.65rem,7vw,4.8rem); }
.nac-hero p {
    max-width:37rem; color:var(--nac-ink);
    font:clamp(1.05rem,2vw,1.24rem)/1.65 Georgia, serif; margin:.85rem 0 0;
}
.stApp .nac-heading { font-size:clamp(1.9rem,6vw,3rem); margin:.35rem 0; }
.stApp .nac-question-title { font-size:clamp(1.3rem,4.75vw,2rem); text-align:center; }
.nac-prompt { color:var(--nac-navy); text-align:center; font-size:1.25rem; margin:.15rem 0; }
.nac-card { text-align:center; padding:.35rem .25rem; }
.stApp .nac-card h2 {
    color:var(--nac-navy); font:700 1.28rem/1.25 var(--nac-display);
    overflow-wrap:anywhere; margin:.35rem 0; padding:0;
}
.nac-card p { margin:.35rem 0; line-height:1.45; }
.nac-level { color:var(--nac-navy); font-weight:700; font-size:.88rem; }
.nac-activity { text-align:left; min-height:6.75rem; }
.nac-activity .nac-level { color:#84411c; }
.st-key-activity_grid [class*="st-key-activity_"]:not(.st-key-activity_grid),
.st-key-directory_grid [class*="st-key-profile_"], .st-key-sign_in [data-testid="stForm"] {
    background:#fff;
}
.nac-placeholder {
    display:grid; place-items:center; min-height:12rem; aspect-ratio:4/5;
    max-width:220px; margin:auto; color:var(--nac-navy); background:var(--nac-mist);
    border-radius:.75rem; text-align:center;
}
.nac-bio { white-space:pre-wrap; overflow-wrap:anywhere; text-align:center; }
.nac-person {
    display:grid; grid-template-columns:3.7rem minmax(0,1fr);
    column-gap:.85rem; align-items:center; color:var(--nac-ink);
}
.nac-person img, .nac-person-placeholder {
    display:block; width:100%; aspect-ratio:4/5; object-fit:cover;
    border-radius:.45rem; background:var(--nac-mist);
}
.stApp .nac-person h2 {
    color:var(--nac-navy); font:700 1.18rem/1.2 var(--nac-display);
    margin:0; padding:0; overflow-wrap:anywhere;
}
.nac-person p { margin:.25rem 0 0; overflow-wrap:anywhere; }
.nac-person .nac-level { margin-top:.35rem; }
.nac-person-copy { min-width:0; }
.nac-chart-path { color:var(--nac-navy); font-weight:650; font-size:.95rem; }
.nac-chart-branch {
    border-left:.2rem solid var(--nac-orange); color:var(--nac-navy);
    padding:.35rem .8rem; font:700 1.1rem/1.3 var(--nac-display);
}
.st-key-org_chart [class*="st-key-org_person_"] { background:#fff; }
.st-key-sign_in { max-width:28rem; margin:1rem auto 0; }
.st-key-sign_in .nac-heading { text-align:center; margin-bottom:.75rem; }
.nac-feedback { color:var(--nac-ink); font-size:.95rem; margin:0; }
[data-testid="stImage"] { margin-inline:auto; max-width:100%; }
[data-testid="stImage"] img { border-radius:.75rem; max-width:100%; height:auto; }
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button { min-height:3rem; border-radius:.65rem; font-weight:650; }
.st-key-quiz_content button { padding:.65rem .9rem; }
.st-key-quiz_content button p { overflow-wrap:anywhere; }
.st-key-review_cards [data-testid="stText"] { white-space:pre-wrap; overflow-wrap:anywhere; }
button:focus-visible {
    outline:2px solid var(--nac-navy) !important; outline-offset:3px;
    box-shadow:0 0 0 3px var(--nac-peach);
}
@media (max-width: 650px) {
    .block-container { padding:2.5rem 1rem max(2rem, env(safe-area-inset-bottom)); }
    .nac-brand { min-height:3.5rem; padding:.55rem .8rem; }
    .nac-brand img { width:7rem; }
    .nac-brand span { font-size:.75rem; }
    .nac-hero { padding:1.4rem 1rem; }
    .stApp .nac-hero h1 { font-size:clamp(2.25rem,9vw,2.9rem); }
    .nac-hero p { margin-top:.55rem; }
    .stApp .nac-heading { margin:.15rem 0 .35rem; }
    .nac-card { padding:.15rem 0; }
    .stApp .nac-card h2 { font-size:1.12rem; }
    .st-key-activity_grid [data-testid="stHorizontalBlock"],
    .st-key-org_chart [data-testid="stHorizontalBlock"],
    .st-key-directory_filters [data-testid="stHorizontalBlock"] { flex-direction:column; }
    .st-key-activity_grid [data-testid="stColumn"],
    .st-key-org_chart [data-testid="stColumn"],
    .st-key-directory_filters [data-testid="stColumn"] { width:100% !important; flex:auto !important; }
    .st-key-directory_grid [data-testid="stHorizontalBlock"] {
        flex-direction:column;
    }
    .st-key-directory_grid [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        width:100% !important; flex:auto !important;
    }
    .nac-person { grid-template-columns:3.4rem minmax(0,1fr); row-gap:.6rem; }
    .nac-person-copy { display:contents; }
    .nac-person h2 { grid-column:2; grid-row:1; }
    .nac-person img, .nac-person-placeholder { grid-column:1; grid-row:1; }
    .nac-person p { grid-column:1 / -1; margin:0; }
    .nac-person .nac-level { margin-top:0; }
    .nac-activity { min-height:0; }
    .st-key-quiz_content [data-testid="stHorizontalBlock"] { display:flex; }
    .st-key-quiz_content [data-testid="stColumn"]:is(:first-child,:last-child) { display:none; }
    .st-key-quiz_content [data-testid="stColumn"]:nth-child(2) { width:100% !important; flex:1 1 100%; }
    .st-key-quiz_content [data-testid="stImage"] { width:min(42vw,9rem) !important; }
    .st-key-directory_filters input, .st-key-quiz_content input, .st-key-sign_in input,
    [data-testid="stSelectbox"] [role="combobox"] { font-size:1rem; }
    .st-key-review_cards [data-testid="stHorizontalBlock"] { flex-direction:column; }
    .st-key-review_cards [data-testid="stColumn"] { width:100% !important; flex:auto !important; }
    .st-key-result_metrics [data-testid="stHorizontalBlock"] { gap:.5rem; }
    .st-key-result_metrics [data-testid="stColumn"] { min-width:0; }
    .st-key-result_metrics [data-testid="stMetricValue"] { font-size:1.35rem; }
    .st-key-result_metrics [data-testid="stMetricLabel"] { min-width:0; }
}
</style>
""", unsafe_allow_html=True)

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

    with st.container(key="sign_in"):
        heading("NAC Connect")
        with st.form("staff_sign_in", clear_on_submit=True, border=True):
            st.write("Sign in to explore the staff directory and start your onboarding quizzes.")
            supplied = st.text_input("Access password", type="password", max_chars=256)
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            if hmac.compare_digest(supplied.encode(), password.encode()):
                st.session_state.staff_access = marker
                st.rerun()
            st.error("Incorrect password.")
    st.stop()


@st.cache_data(show_spinner=False, max_entries=256)
def photo_bytes(path, modified_ns, thumbnail=False):
    image = portrait(path)
    if image is None:
        return None
    if thumbnail:
        image.thumbnail((160, 200))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue()


def roster_photo(record, root, *, thumbnail=False):
    filename = Path(record.photo)
    path = (root / filename).resolve()
    valid = (filename.name == record.photo and path.parent == root.resolve()
             and filename.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    try:
        return photo_bytes(str(path), path.stat().st_mtime_ns, thumbnail) if valid else None
    except OSError:
        return None


def display_photo(record, root, *, width=220):
    image = roster_photo(record, root)
    if image is None:
        st.markdown('<div class="nac-placeholder">Photo unavailable</div>', unsafe_allow_html=True)
    else:
        st.image(image, width=width)


def person_card(record, photo_root):
    name, role, department = map(html.escape, (record.name, record.role, record.department))
    image = roster_photo(record, photo_root, thumbnail=True)
    if image:
        encoded = base64.b64encode(image).decode()
        photo = f'<img alt="" src="data:image/jpeg;base64,{encoded}">'
    else:
        photo = '<span class="nac-person-placeholder" aria-hidden="true"></span>'
    st.markdown(
        f'<div class="nac-person">{photo}<div class="nac-person-copy">'
        f'<h2>{name}</h2><p>{role}</p><p class="nac-level">{department}</p></div></div>',
        unsafe_allow_html=True,
    )
    if record.bio:
        st.markdown(f'<p class="nac-bio">{html.escape(record.bio)}</p>', unsafe_allow_html=True)


def home():
    st.markdown('<div class="nac-hero"><h1>NAC Connect</h1>'
                '<p>Get to know your coworkers at the National Ability Center. '
                'Explore the directory, then practice matching names and faces to job titles.</p></div>',
                unsafe_allow_html=True)
    with st.container(key="activity_grid"):
        activities = list(PAGES.items())
        for offset in range(0, len(activities), 2):
            for (page, (title, level, description)), column in zip(activities[offset:offset + 2], st.columns(2)):
                with column, st.container(border=True, key=f"activity_{page}"):
                    st.markdown(f'<div class="nac-card nac-activity"><span class="nac-level">{level}</span>'
                                f'<h2>{title}</h2><p>{description}</p></div>', unsafe_allow_html=True)
                    st.button(f"Open {title}", key=page, width="stretch", on_click=go, args=(page,),
                              type="primary" if page == "role_recall" else "secondary")
    if os.getenv("NAC_LOCAL_ADMIN") == "1":
        st.button("Roster manager", on_click=go, args=("admin",))
    st.button("Sign out", on_click=st.session_state.clear)


def page_slice(items, key, size=12):
    if len(items) <= size:
        return items
    pages = (len(items) + size - 1) // size
    active = st.selectbox("Page", range(1, pages + 1), key=f"{key}-{pages}",
                          format_func=lambda p: f"{p} of {pages}")
    offset = (active - 1) * size
    return items[offset:offset + size]


def search_staff(active, photo_root):
    with st.container(key="directory_filters"):
        search, filter_column, order = st.columns([2, 1, 1])
    query = search.text_input("Search by name, role, or department").casefold().strip()
    departments = sorted({record.department for record in active}, key=str.casefold)
    selected = filter_column.selectbox("Department", [None, *departments],
                                        format_func=lambda item: item or "All departments")
    sorting = order.selectbox("Sort by name", ["A to Z", "Z to A"])
    matches = [record for record in active if (selected is None or record.department == selected)
               and any(query in value.casefold() for value in
                       (record.name, record.role, record.department))]
    matches.sort(key=lambda record: record.name.casefold(), reverse=sorting == "Z to A")
    st.caption(f"{len(matches)} {'profile' if len(matches) == 1 else 'profiles'}")
    if not matches:
        st.info("No staff match your search.")
    visible = page_slice(matches, "directory-page")
    with st.container(key="directory_grid"):
        for offset in range(0, len(visible), 3):
            for record, column in zip(visible[offset:offset + 3], st.columns(3)):
                with column, st.container(border=True, key=f"profile_{record.id}"):
                    person_card(record, photo_root)


@st.cache_data(show_spinner=False)
def read_chart(path, modified_ns):
    return json.loads(path.read_text(encoding="utf-8"))


def select_chart_person(person_id):
    st.session_state.chart_focus = person_id
    st.session_state.chart_person_picker = person_id


def jump_to_chart_person():
    st.session_state.chart_focus = st.session_state.chart_person_picker


def org_chart(active, photo_root):
    chart_path = ROOT / "data/reporting.json"
    chart = read_chart(chart_path, chart_path.stat().st_mtime_ns)
    staff = {record.id: record for record in active}
    managers = chart["manager_by_employee"]
    ordered = sorted(staff, key=lambda person_id: staff[person_id].name.casefold())
    root = chart["root"] if chart["root"] in staff else ordered[0]
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

    direct = [staff[employee] for employee in ordered if managers.get(employee) == person.id]
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
        else:
            st.caption("No direct reports listed in this directory.")
        people_with_reports = {managers.get(employee) for employee in ordered}
        for offset in range(0, len(direct), 2):
            for record, column in zip(direct[offset:offset + 2], st.columns(2)):
                action = "reports" if record.id in people_with_reports else "profile"
                with column, st.container(border=True, key=f"org_person_{record.id}"):
                    person_card(record, photo_root)
                    st.button(f"View {record.name}’s {action}", key=f"open_chart_{record.id}",
                              width="stretch", on_click=select_chart_person, args=(record.id,))


def directory(staff, photo_root):
    heading("Staff Directory")
    active = [record for record in staff if record.active]
    if not active:
        st.info("The staff directory will open when the approved roster is added.")
        return
    view = st.radio("Directory view", ["Org chart", "Find staff"], horizontal=True)
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
        st.subheader("Photographic answer key")
        missed_only = st.checkbox("Show only missed or flagged answers")
    else:
        st.metric("Final score", f"{total - len(missed)} / {total}")
        st.subheader("Missed questions")
        missed_only = True
        if not missed:
            st.success("You got every answer right.")

    review = [(question, row) for question, row in zip(attempt.questions, rows)
              if not missed_only or question.staff.id in missed]
    visible = page_slice(review, f"{mode}-review", size=8)
    with st.container(key="review_cards"):
        for question, row in visible:
            with st.container(border=True):
                photo, details = st.columns([1, 2], vertical_alignment="center")
                with photo:
                    display_photo(question.staff, photo_root, width=120)
                with details:
                    st.text(question.staff.name)
                    if mastery:
                        st.text(question.staff.role)
                        st.text(f"Name: {row['submitted_name'] or 'Blank'} · {row['name_status']}")
                        st.text(f"Role: {row['submitted_role'] or 'Blank'} · {row['role_status']}")
                    else:
                        st.text(f"Your answer: {row['submitted_answer']}")
                        st.text(f"Correct answer: {row['correct_answer']}")

    export = ({"mode": "staff", **row} for row in rows)
    st.download_button("Download results CSV", csv_text(
        ["mode", *rows[0]], ({key: spreadsheet_value(value) for key, value in row.items()}
                             for row in export)
    ), f"nac-{mode}.csv", "text/csv")
    if missed and not mastery:
        st.button("Retry missed questions", on_click=restart, args=(missed,))
    st.button("Restart quiz", on_click=restart)


def quiz(mode, staff, photo_root):
    title, level, description = PAGES[mode]
    heading(title)
    key = mode
    mastery = mode == "mastery_exam"

    def restart(ids=None):
        questions = make_questions(mode, staff, photo_root, ids=ids)
        st.session_state.attempts[key] = Attempt(questions) if questions else None

    attempt = st.session_state.attempts.get(key)
    if attempt is None:
        st.markdown(f"**{level}** · {description}")
        available = make_questions(mode, staff, photo_root)
        if not available:
            message = "This quiz opens when the roster includes eligible staff with valid photos."
            if not mastery:
                message += " Multiple-choice quizzes also need four distinct answer choices."
            st.info(message)
            return
        st.caption(f"{len(available)} questions. "
                   "Progress lasts for this browser session.")
        st.button("Start exam" if mastery else "Start quiz", type="primary", on_click=restart)
        return
    if attempt.finished:
        results(mode, attempt, staff, photo_root, restart)
        return

    index = attempt.index
    question = attempt.questions[index]
    total = len(attempt.questions)
    st.progress(len(attempt.answers) / total, text=f"Question {index + 1} of {total}")
    with st.container(key="quiz_content"):
        _, center, _ = st.columns([1, 4, 1])
    with center:
        display_photo(question.staff, photo_root, width=240)
        if mastery:
            name_key, role_key = f"exam-name-{index}", f"exam-role-{index}"
            with st.form(f"exam-{index}", clear_on_submit=True):
                st.text_input("Name", max_chars=150, autocomplete="off", key=name_key)
                st.text_input("Job title", max_chars=200, autocomplete="off", key=role_key)
                st.form_submit_button(
                    "Submit exam" if index + 1 == total else "Save and continue",
                    type="primary", width="stretch", on_click=submit_exam_answer,
                    args=(attempt, index, name_key, role_key),
                )
            return

        if mode == "role_recall":
            st.markdown(f'<h2 class="nac-heading nac-question-title">{html.escape(question.staff.name)}</h2>',
                        unsafe_allow_html=True)
        prompt = "What is their job title?" if mode == "role_recall" else "Who is this?"
        st.markdown(f'<p class="nac-prompt">{prompt}</p>', unsafe_allow_html=True)
        answered = index in attempt.answers
        for option_index, option in enumerate(question.options):
            st.button(option, key=f"option-{mode}-{index}-{option_index}", width="stretch",
                      disabled=answered, on_click=attempt.submit, args=(index, option))
        score = sum(score_choice(mode, attempt.questions[i], answer[0])
                    for i, answer in attempt.answers.items())
        st.caption(f"Running score · {score} / {len(attempt.answers)}")
        if answered:
            if score_choice(mode, question, attempt.answers[index][0]):
                st.success("Correct.")
            else:
                st.error(f"Correct answer: {getattr(question.staff, FIELDS[mode])}")
            context = (question.staff.department if mode == "role_recall"
                       else f"{question.staff.role} · {question.staff.department}")
            st.markdown(f'<p class="nac-feedback">{html.escape(context)}</p>', unsafe_allow_html=True)
            st.button("See results" if index + 1 == total else "Next question", type="primary",
                      width="stretch", on_click=attempt.advance, args=(index,))


@st.cache_data(show_spinner=False, max_entries=8)
def read_roster(path, photo_root, roster_mtime, photos_mtime):
    return load(path.read_text(encoding="utf-8-sig"), photo_root)


brand()
require_app_password()

page = st.session_state.page
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
exam = st.session_state.attempts.get("mastery_exam")
if page == "mastery_exam" and exam and not exam.finished:
    st.button("Exit exam", on_click=go, args=("home",))
else:
    if page != "home":
        st.button("Home", on_click=go, args=("home",))

if page == "directory":
    directory(staff, photo_root)
elif page in PAGES:
    quiz(page, staff, photo_root)
else:
    home()
