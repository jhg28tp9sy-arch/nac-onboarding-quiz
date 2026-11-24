import hashlib
import hmac
import os
from dataclasses import asdict

import pandas as pd
import streamlit as st

from utils.roster import FIELDS, FLAGS, csv_text, load, validate


def roster_manager(root):
    st.title("Roster manager")
    password = os.getenv("NAC_ADMIN_PASSWORD", "")
    if len(password) < 16:
        st.error("Configure a local administrator password of at least 16 characters.")
        return
    marker = st.session_state.get("roster_admin")
    expected = hmac.digest(password.encode(), b"nac-connect-admin", "sha256")
    if marker is None or not hmac.compare_digest(marker, expected):
        with st.form("roster-login", clear_on_submit=True):
            supplied = st.text_input("Administrator password", type="password", autocomplete="off")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            if hmac.compare_digest(supplied.encode(), password.encode()):
                st.session_state.roster_admin = expected
                st.rerun()
            st.error("Invalid password.")
        return
    if st.button("Sign out"):
        for key in ("roster_admin", "roster_upload"):
            st.session_state.pop(key, None)
        st.rerun()

    path = root / "data/staff.csv"
    photos = root / "assets/staff"
    upload = st.file_uploader("Import roster CSV", type="csv", key="roster_upload")
    source = path.read_bytes() if path.exists() else csv_text(FIELDS, []).encode()
    if upload is not None:
        source = upload.getvalue()
    try:
        records, errors, warnings = load(source.decode("utf-8-sig"), photos)
    except UnicodeError:
        st.error("Upload a UTF-8 CSV.")
        return
    for error in errors:
        st.error(error)
    for warning in warnings:
        st.warning(warning)
    if errors:
        st.caption("Fix the displayed CSV errors and import the corrected file.")
        return

    columns = {key: pd.Series([getattr(record, key) for record in records],
                              dtype="bool" if key in FLAGS else "string") for key in FIELDS}
    source_warnings = set(warnings)
    draft_key = "roster_draft_" + hashlib.sha256(source).hexdigest()
    edited = st.data_editor(pd.DataFrame(columns), num_rows="dynamic", hide_index=True,
                            width="stretch", key=draft_key,
                            column_config={key: st.column_config.CheckboxColumn(default=False)
                                           for key in FLAGS})
    st.caption("Add or delete rows in the table. Keep existing IDs stable. "
               "Place approved image files in assets/staff and enter their filenames.")
    parsed, errors, warnings = validate(edited.fillna("").to_dict("records"), photos)
    for error in errors:
        st.error(error)
    for warning in sorted(set(warnings) - source_warnings):
        st.warning(warning)
    if not errors:
        st.download_button("Export validated roster CSV", csv_text(FIELDS, map(asdict, parsed)),
                           "staff.csv", "text/csv")
        st.caption("To apply the roster, replace data/staff.csv with the exported file.")
