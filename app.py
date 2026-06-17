import streamlit as st

st.set_page_config(page_title="Workout AI Log", layout="wide")

st.title("Workout AI Log")

tab_log, tab_dashboard = st.tabs(["Log workout", "Dashboard"])

with tab_log:
    raw_note = st.text_area("Paste workout note", height=300)

    if st.button("Parse workout"):
        st.write("Parser coming next.")
        st.code(raw_note)

with tab_dashboard:
    st.write("Dashboard coming next.")