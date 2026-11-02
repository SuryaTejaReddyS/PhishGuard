import random
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from pipeline import process_email, THRESHOLD
from store import get_by_status, review, stats, all_emails, reset

st.set_page_config(page_title="PhishGuard", layout="wide")
st.title("PhishGuard: real-time phishing detection")

TEMPLATES = [
    ("Account notice", "Hello, please review the activity on your account here: {url}"),
    ("Action required", "We noticed something unusual. Please confirm your details: {url}"),
    ("Your order", "Thanks for your purchase. Track your package here: {url}"),
    ("Security alert", "Sign-in attempt detected. Check it here: {url}"),
]
SENDERS = ["support@mail-service.com", "no-reply@notify.net", "info@updates.org", "team@alerts.io"]


@st.cache_data
def load_test():
    return pd.read_csv("data/test.csv")


def send_random(n=1):
    test = load_test()
    for _, row in test.sample(n).iterrows():
        subject, tmpl = random.choice(TEMPLATES)
        process_email(random.choice(SENDERS), subject, tmpl.format(url=row["url"]),
                      url=row["url"], true_label=int(row["label"]))


# ---------- sidebar ----------
s = stats()
st.sidebar.header("Live stats")
st.sidebar.metric("Delivered", s.get("delivered", 0))
st.sidebar.metric("Quarantined (waiting)", s.get("quarantined", 0))
st.sidebar.metric("Blocked (confirmed)", s.get("blocked", 0))
st.sidebar.metric("Released (overridden)", s.get("released", 0))
st.sidebar.caption(f"Quarantine threshold: {THRESHOLD}")

st.sidebar.divider()
auto = st.sidebar.checkbox("Auto-stream incoming emails (demo)")
if st.sidebar.button("Clear all data"):
    reset()
    st.rerun()

# ---------- simulator ----------
st.subheader("Incoming mail simulator")
c1, c2, c3 = st.columns([1, 1, 3])
if c1.button("Send 1 random email"):
    send_random(1)
    st.rerun()
if c2.button("Send 10 emails"):
    send_random(10)
    st.rerun()

with st.expander("Or send your own email"):
    with st.form("custom"):
        sender = st.text_input("Sender", "someone@example.com")
        subject = st.text_input("Subject", "Verify your account")
        body = st.text_area("Body (include a link)",
                            "Please login here: http://paypal.account-verify.xyz/signin")
        if st.form_submit_button("Process email"):
            out = process_email(sender, subject, body)
            st.write(f"Result: **{out['status']}** (score {out['score']:.2f}, {out['ms']:.1f} ms)")
            st.rerun()

st.divider()

# ---------- tabs ----------
tab1, tab2 = st.tabs(["Quarantine queue", "Full log"])

with tab1:
    queue = get_by_status("quarantined")
    if not queue:
        st.info("No emails waiting for review.")
    for e in queue:
        with st.expander(f"Score {e['score']:.2f}  |  {e['subject']}  |  {e['url'][:70]}"):
            st.write(f"**From:** {e['sender']}")
            st.write(f"**Body:** {e['body']}")
            st.write("**Why it was flagged:** " + e["reasons"])
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Confirm phishing", key=f"c{e['id']}"):
                review(e["id"], "confirm")
                st.rerun()
            if b2.button("Override: release", key=f"o{e['id']}"):
                review(e["id"], "override")
                st.rerun()

with tab2:
    log = pd.DataFrame(all_emails())
    if log.empty:
        st.info("Nothing processed yet.")
    else:
        cols = ["id", "created_at", "subject", "url", "score", "status",
                "reviewer_action", "true_label", "processing_ms"]
        st.dataframe(log[cols].iloc[::-1], use_container_width=True, hide_index=True)

# ---------- auto stream ----------
if auto:
    time.sleep(2)
    send_random(1)
    st.rerun()