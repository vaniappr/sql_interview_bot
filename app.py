"""SQL Interview Bot — an InterviewMaster-style chatbot for practicing SQL,
either against a built-in banking + retail database, or against your own
Kaggle dataset (CSV / zip of CSVs)."""

import streamlit as st

from dataset_loader import CUSTOM_DB_PATH, load_dataset
from dynamic_questions import generate_questions
from grader import DEFAULT_DB_PATH, grade
from llm import interviewer_feedback
from questions import QUESTIONS as FINCOMMERCE_QUESTIONS

if not DEFAULT_DB_PATH.exists():
    from db.build_db import build
    build()

st.set_page_config(page_title="SQL Interview Bot", page_icon="🗄️", layout="wide")
st.title("🗄️ SQL Interview Bot")

if "score" not in st.session_state:
    st.session_state.score = {"correct": 0, "total": 0}
if "history" not in st.session_state:
    st.session_state.history = []
if "custom_questions" not in st.session_state:
    st.session_state.custom_questions = None
if "custom_schema" not in st.session_state:
    st.session_state.custom_schema = None
if "current_q" not in st.session_state:
    st.session_state.current_q = FINCOMMERCE_QUESTIONS[0]["id"]
if "mode" not in st.session_state:
    st.session_state.mode = "FinCommerce (built-in)"

with st.sidebar:
    mode = st.radio(
        "Dataset",
        ["FinCommerce (built-in)", "Upload your own (Kaggle CSV/zip)"],
        key="mode",
    )

    if mode == "Upload your own (Kaggle CSV/zip)":
        uploaded = st.file_uploader(
            "Upload CSV file(s) or a .zip of CSVs", type=["csv", "zip"], accept_multiple_files=True
        )
        n_questions = st.slider("Number of questions to generate", 3, 12, 8)
        if st.button("Load dataset & generate questions", disabled=not uploaded):
            with st.spinner("Loading dataset into SQLite..."):
                summaries = load_dataset(uploaded)
                st.session_state.custom_schema = summaries
            with st.spinner("Generating interview questions for your schema..."):
                qs = generate_questions(summaries, n=n_questions)
            if not qs:
                st.error("Couldn't generate any valid questions from this dataset.")
            else:
                st.session_state.custom_questions = qs
                st.session_state.current_q = qs[0]["id"]
                st.session_state.score = {"correct": 0, "total": 0}
                st.success(f"Loaded {len(summaries)} table(s), generated {len(qs)} question(s).")

        if st.session_state.custom_schema:
            st.divider()
            st.subheader("Schema")
            for t in st.session_state.custom_schema:
                cols = ", ".join(c for c, _ in t.columns)
                st.markdown(f"- **{t.name}** ({t.row_count} rows): {cols}")
    else:
        st.divider()
        st.subheader("Schema")
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

# Resolve active question list + db path for the selected mode
if mode == "Upload your own (Kaggle CSV/zip)":
    active_questions = st.session_state.custom_questions
    db_path = CUSTOM_DB_PATH
else:
    active_questions = FINCOMMERCE_QUESTIONS
    db_path = DEFAULT_DB_PATH

if not active_questions:
    st.info("Upload a dataset and click **Load dataset & generate questions** in the sidebar to begin.")
    st.stop()

with st.sidebar:
    st.divider()
    st.subheader("Jump to question")
    for q in active_questions:
        label = f"#{q['id']} [{q['difficulty']}] {q['topic']}"
        if st.button(label, key=f"jump_{mode}_{q['id']}"):
            st.session_state.current_q = q["id"]

if st.session_state.current_q not in [q["id"] for q in active_questions]:
    st.session_state.current_q = active_questions[0]["id"]

question = next(q for q in active_questions if q["id"] == st.session_state.current_q)

st.caption(
    "Practicing against the FinCommerce sample database."
    if mode == "FinCommerce (built-in)"
    else "Practicing against your uploaded dataset."
)
st.subheader(f"Question {question['id']} — {question['difficulty']} · {question['topic']}")
st.write(question["prompt"])

with st.form(key=f"answer_form_{mode}_{question['id']}"):
    candidate_sql = st.text_area("Your SQL query", height=160, placeholder="SELECT ...")
    candidate_explanation = st.text_area(
        "Briefly explain your approach (optional, but the interviewer will ask anyway)",
        height=80,
    )
    submitted = st.form_submit_button("Submit answer")

if submitted:
    if not candidate_sql.strip():
        st.warning("Write a query before submitting.")
    else:
        result = grade(candidate_sql, question["solution"], question["ordered"], db_path=db_path)
        st.session_state.score["total"] += 1
        if result.correct:
            st.session_state.score["correct"] += 1

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Your result**")
            if result.error:
                st.error(result.error)
            else:
                st.dataframe([dict(zip(result.candidate_columns, row)) for row in result.candidate_rows])
        with col2:
            st.markdown("**Expected result**")
            st.dataframe([dict(zip(result.expected_columns, row)) for row in result.expected_rows])

        if result.correct:
            st.success("Correct! ✅")
        elif result.error:
            st.error("Your query errored — see message above.")
        else:
            st.warning("Not quite — results don't match. ❌")

        with st.spinner("Interviewer is reviewing your answer..."):
            feedback = interviewer_feedback(
                question["prompt"], candidate_sql, candidate_explanation, result.correct
            )
        st.markdown("**Interviewer feedback**")
        st.info(feedback)

        st.session_state.history.append({
            "question_id": question["id"],
            "sql": candidate_sql,
            "correct": result.correct,
        })

st.divider()
idx = active_questions.index(question)
cols = st.columns(2)
with cols[0]:
    if idx > 0 and st.button("⬅ Previous question"):
        st.session_state.current_q = active_questions[idx - 1]["id"]
        st.rerun()
with cols[1]:
    if idx < len(active_questions) - 1 and st.button("Next question ➡"):
        st.session_state.current_q = active_questions[idx + 1]["id"]
        st.rerun()
