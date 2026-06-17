# SQL Interview Bot — FinCommerce

An "InterviewMaster"-style SQL practice chatbot. It asks SQL interview
questions against **FinCommerce**, a fictional business that's part bank
(accounts, transactions, loans, cards) and part retailer (products, orders),
so questions can span realistic multi-domain joins.

## Setup

```bash
cd sql-interview-bot
pip install -r requirements.txt
python db/build_db.py        # generates db/fincommerce.db with seeded data
streamlit run app.py
```

Optional: set an API key to get live, conversational interviewer feedback
(probing follow-up questions, critique of your approach), and to have
interview questions for uploaded datasets written by an LLM instead of the
offline heuristic generator. Without either key, the app still runs and
grades queries, just with canned feedback text and template-based questions.

- `GROQ_API_KEY` — free tier, runs Llama 3.3 on Groq. Get one at
  https://console.groq.com/keys (no credit card required). Checked first.
- `ANTHROPIC_API_KEY` — paid, runs Claude. Used only if `GROQ_API_KEY` isn't set.

## Using your own dataset (e.g. from Kaggle)

In the sidebar, switch to **"Upload your own (Kaggle CSV/zip)"**, then upload
either:

- one or more `.csv` files, or
- a `.zip` containing `.csv` files (e.g. a Kaggle dataset download)

Click **Load dataset & generate questions**. Each CSV becomes a table (named
after the file) in `db/custom.db`, and a question set is generated against
the real schema:

- With `GROQ_API_KEY` or `ANTHROPIC_API_KEY` set, the LLM writes the
  questions and reference SQL directly from your schema + sample rows;
  every generated solution is executed and validated before being shown,
  so broken questions are silently dropped.
- Without either key, a heuristic generator builds template questions
  (row counts, group-bys, aggregates, multi-column grouping, derived
  columns, window functions, correlated subqueries) per table — no LLM
  required.

You then interview against your own data exactly like the built-in
FinCommerce mode: write SQL, get graded against the reference solution, get
interviewer feedback.

## How it works

- `db/schema.sql` + `db/build_db.py` — defines and seeds the built-in
  FinCommerce SQLite database.
- `questions.py` — built-in FinCommerce question bank; each question has a
  reference solution SQL.
- `dataset_loader.py` — loads uploaded CSV/zip files into `db/custom.db`
  and produces a schema summary (columns, dtypes, sample rows) per table.
- `dynamic_questions.py` — generates (and validates) a question set for a
  custom dataset, via Groq/Claude or the offline heuristic fallback.
- `grader.py` — runs the candidate's query and the reference query against
  the same database (built-in or custom) and compares result sets.
- `llm.py` — sends the question, candidate SQL/explanation, and correctness
  to Groq or Claude for interviewer-style feedback (falls back to canned
  text if no API key is set).
- `app.py` — Streamlit UI: a home page to pick a database, then the
  interview flow (question, table browser, SQL answer box, grading,
  feedback).

## Adding built-in questions

Add an entry to `QUESTIONS` in `questions.py` with `prompt`, `solution` (SQL),
and `ordered` (whether row order matters for grading).
