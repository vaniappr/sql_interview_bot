"""SQL Practice Buddy — an InterviewMaster-style chatbot for practicing SQL,
either against a built-in banking + retail database, or against your own
Kaggle dataset (CSV / zip of CSVs)."""

import os
import sqlite3

import streamlit as st

from dataset_loader import CUSTOM_DB_PATH, load_dataset
from dynamic_questions import generate_questions
from grader import DEFAULT_DB_PATH, grade
from llm import interviewer_feedback
from questions import QUESTIONS as FINCOMMERCE_QUESTIONS

FINCOMMERCE = "fincommerce"
CUSTOM = "custom"


def list_tables(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def fetch_table(db_path, table_name, limit=100):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return columns, rows
    finally:
        conn.close()


def go_home():
    st.session_state.page = "home"


def start_interview(db_key):
    st.session_state.active_db = db_key
    st.session_state.current_q = (
        FINCOMMERCE_QUESTIONS[0]["id"] if db_key == FINCOMMERCE else st.session_state.custom_questions[0]["id"]
    )
    st.session_state.score = {"correct": 0, "total": 0}
    st.session_state.page = "interview"


if not DEFAULT_DB_PATH.exists():
    from db.build_db import build
    build()

st.set_page_config(page_title="SQL Practice Buddy", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; max-width: 1100px; }

    h1 { font-weight: 700; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 600; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        transition: box-shadow 0.15s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    }

    div[data-testid="stForm"] {
        border: 1px solid #E5E7E5;
        border-radius: 14px;
        padding: 1.5rem 1.5rem 0.5rem;
        background-color: #FAFBFA;
    }

    .stButton > button, .stFormSubmitButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.2rem;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background-color: #2D6A4F;
        border-color: #2D6A4F;
    }

    [data-testid="stMetricValue"] { color: #2D6A4F; font-weight: 700; }

    [data-testid="stExpander"] {
        border-radius: 10px;
        border: 1px solid #E5E7E5;
    }

    section[data-testid="stSidebar"] {
        background-color: #F4F6F5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "score" not in st.session_state:
    st.session_state.score = {"correct": 0, "total": 0}
if "custom_questions" not in st.session_state:
    st.session_state.custom_questions = None
if "custom_schema" not in st.session_state:
    st.session_state.custom_schema = None
if "current_q" not in st.session_state:
    st.session_state.current_q = None
if "active_db" not in st.session_state:
    st.session_state.active_db = None
if "page" not in st.session_state:
    st.session_state.page = "home"


# ---------------------------------------------------------------- Home page
if st.session_state.page == "home":
    st.title("SQL Practice Buddy")
    st.write("Choose a database to start your interview:")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("FinCommerce (built-in)")
            st.caption(
                "A fictional bank + retail business: customers, accounts, "
                "transactions, loans, cards, products, orders."
            )
            st.markdown(f"**{len(FINCOMMERCE_QUESTIONS)} questions** ready to go.")
            if st.button("Start interview ▶", key="start_fincommerce", type="primary"):
                start_interview(FINCOMMERCE)
                st.rerun()

    with col2:
        with st.container(border=True):
            st.subheader("Your dataset")
            if st.session_state.custom_questions:
                st.caption("Loaded from your uploaded CSV/zip.")
                for t in st.session_state.custom_schema:
                    st.markdown(f"- **{t.name}** ({t.row_count} rows)")
                st.markdown(f"**{len(st.session_state.custom_questions)} questions** ready to go.")
                if st.button("Start interview ▶", key="start_custom", type="primary"):
                    start_interview(CUSTOM)
                    st.rerun()
                st.divider()

            with st.expander("Upload a new dataset (Kaggle CSV/zip)", expanded=not st.session_state.custom_questions):
                has_key = bool(os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
                if not has_key:
                    st.warning(
                        "Tailored, storyline-based question generation needs GROQ_API_KEY "
                        "or ANTHROPIC_API_KEY set — add one to use this."
                    )

                uploaded = st.file_uploader(
                    "Upload CSV file(s) or a .zip of CSVs", type=["csv", "zip"], accept_multiple_files=True
                )

                st.caption("Tell us the industry, so the storyline fits.")
                industry = st.selectbox(
                    "Target industry",
                    ["Finance", "Retail", "Healthcare", "SaaS", "Logistics", "Other"],
                    key="profile_industry",
                )

                st.caption("How many questions of each difficulty?")
                diff_cols = st.columns(3)
                with diff_cols[0]:
                    n_easy = st.number_input("Easy", min_value=0, max_value=10, value=3, key="n_easy")
                with diff_cols[1]:
                    n_medium = st.number_input("Medium", min_value=0, max_value=10, value=3, key="n_medium")
                with diff_cols[2]:
                    n_hard = st.number_input("Hard", min_value=0, max_value=10, value=2, key="n_hard")
                counts = {"Easy": n_easy, "Medium": n_medium, "Hard": n_hard}

                if st.button(
                    "Load dataset & generate questions",
                    disabled=not has_key or not uploaded or not sum(counts.values()),
                ):
                    profile = {"industry": industry}
                    with st.spinner("Loading dataset into SQLite..."):
                        summaries = load_dataset(uploaded)
                        st.session_state.custom_schema = summaries
                    with st.spinner("Generating your tailored interview storyline..."):
                        qs = generate_questions(summaries, counts=counts, profile=profile)
                    if not qs:
                        st.error("Couldn't generate any valid questions from this dataset.")
                    else:
                        st.session_state.custom_questions = qs
                        st.success(f"Loaded {len(summaries)} table(s), generated {len(qs)} question(s).")
                        st.rerun()

    st.stop()


# ----------------------------------------------------------- Interview page
if st.session_state.active_db == CUSTOM:
    active_questions = st.session_state.custom_questions
    db_path = CUSTOM_DB_PATH
    db_label = "your uploaded dataset"
else:
    active_questions = FINCOMMERCE_QUESTIONS
    db_path = DEFAULT_DB_PATH
    db_label = "FinCommerce"

if not active_questions:
    go_home()
    st.rerun()

st.title("SQL Practice Buddy")
st.button("Home", on_click=go_home)

with st.sidebar:
    st.subheader(f"Database: {db_label}")
    if st.session_state.active_db == CUSTOM:
        for t in st.session_state.custom_schema:
            cols = ", ".join(c for c, _ in t.columns)
            st.markdown(f"- **{t.name}** ({t.row_count} rows): {cols}")
    else:
        st.markdown(
            "- **branches** (branch_id, branch_name, city, region)\n"
            "- **customers** (customer_id, name, segment, branch_id)\n"
            "- **accounts** (account_id, customer_id, branch_id, account_type, balance)\n"
            "- **transactions** (transaction_id, account_id, txn_date, txn_type, amount)\n"
            "- **loans** (loan_id, customer_id, branch_id, loan_type, principal, status)\n"
            "- **cards** (card_id, account_id, card_type, credit_limit)\n"
            "- **products** (product_id, product_name, category, unit_price)\n"
            "- **orders** (order_id, customer_id, card_id, order_date, status)\n"
            "- **order_items** (order_item_id, order_id, product_id, quantity, unit_price)"
        )

    st.divider()
    st.metric("Score", f"{st.session_state.score['correct']} / {st.session_state.score['total']}")
    st.divider()
    st.subheader("Jump to question")
    for q in active_questions:
        label = f"#{q['id']} [{q['difficulty']}] {q['topic']}"
        if st.button(label, key=f"jump_{st.session_state.active_db}_{q['id']}"):
            st.session_state.current_q = q["id"]

if st.session_state.current_q not in [q["id"] for q in active_questions]:
    st.session_state.current_q = active_questions[0]["id"]

question = next(q for q in active_questions if q["id"] == st.session_state.current_q)

with st.expander("Browse table data", expanded=False):
    tables = list_tables(db_path)
    chosen_table = st.selectbox("Table", tables, key=f"browse_table_{st.session_state.active_db}")
    if chosen_table:
        columns, rows = fetch_table(db_path, chosen_table)
        st.caption(f"Showing up to 100 rows of `{chosen_table}`")
        st.dataframe([dict(zip(columns, row)) for row in rows], width="stretch")

st.subheader(f"Question {question['id']} — {question['difficulty']} · {question['topic']}")
st.write(question["prompt"])

with st.form(key=f"answer_form_{st.session_state.active_db}_{question['id']}"):
    candidate_sql = st.text_area("Your SQL query", height=160, placeholder="SELECT ...")
    candidate_explanation = st.text_area(
        "Briefly explain your approach (optional, but the interviewer will ask anyway)",
        height=80,
    )
    submitted = st.form_submit_button("Submit answer", type="primary")

if submitted:
    if not candidate_sql.strip():
        st.warning("Write a query before submitting.")
    else:
        result = grade(candidate_sql, question["solution"], question["ordered"], db_path=db_path)

        submission_sig = (st.session_state.active_db, question["id"], candidate_sql)
        if st.session_state.get("last_scored_sig") != submission_sig:
            st.session_state.score["total"] += 1
            if result.correct:
                st.session_state.score["correct"] += 1
            st.session_state.last_scored_sig = submission_sig

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Your result**")
            if result.error:
                st.error(result.error)
            elif not result.candidate_rows:
                st.caption("Query returned 0 rows.")
            else:
                st.dataframe(
                    [dict(zip(result.candidate_columns, row)) for row in result.candidate_rows],
                    width="stretch",
                )
        with col2:
            st.markdown("**Expected result**")
            if not result.expected_rows:
                st.caption("Expected result has 0 rows.")
            else:
                st.dataframe(
                    [dict(zip(result.expected_columns, row)) for row in result.expected_rows],
                    width="stretch",
                )

        if result.correct:
            st.success("Correct!")
        elif result.error:
            st.error("Your query errored — see message above.")
        else:
            st.warning("Not quite - results don't match.")

        with st.spinner("Interviewer is reviewing your answer..."):
            feedback = interviewer_feedback(
                question["prompt"], candidate_sql, candidate_explanation, result.correct
            )
        st.markdown("**Interviewer feedback**")
        st.info(feedback)

st.divider()
idx = active_questions.index(question)
is_last = idx == len(active_questions) - 1
cols = st.columns(2)
with cols[0]:
    if idx > 0 and st.button("Previous question"):
        st.session_state.current_q = active_questions[idx - 1]["id"]
        st.rerun()
with cols[1]:
    if is_last:
        st.button("Back to Home", on_click=go_home, key="home_at_end")
    elif st.button("Next question ➡"):
        st.session_state.current_q = active_questions[idx + 1]["id"]
        st.rerun()
