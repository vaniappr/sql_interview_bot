# SQL Interview Bot

I built this to practice SQL the way you'd actually get interviewed on it —
not flashcards, but real queries against a real-ish database, with feedback
on whether my answer (and my reasoning) actually held up. Sharing it in case
it's useful for anyone else prepping for data/analytics interviews.

It quizzes you against **FinCommerce**, a fictional company that's part bank
(accounts, transactions, loans, cards) and part retailer (products, orders).
Mixing both domains in one schema means questions can require realistic
multi-table joins instead of toy single-table examples. You can also upload
your own dataset (e.g. anything from Kaggle) and it'll generate a question
set against your actual schema.

## What it does

- Asks you SQL interview questions across Easy / Medium / Hard difficulty.
- Runs your query for real, compares the result set against a reference
  solution, and tells you if you're right.
- Gives interviewer-style feedback on your query and your explanation
  (what's solid, what's inefficient, a follow-up question to think about).
- Lets you browse the underlying tables so you're not guessing at the schema.
- Lets you upload your own CSV/zip dataset and practice against it instead.

## Getting started

```bash
cd sql-interview-bot
pip install -r requirements.txt
streamlit run app.py
```

That's it — the database is created automatically the first time the app
runs, no manual setup script needed.

### Optional: enable live interviewer feedback

By default the app still works fully offline (queries are graded for real,
feedback is just template text). Add an API key if you want actual
conversational feedback, and to have your uploaded-dataset questions written
by an LLM instead of the built-in templates:

- `GROQ_API_KEY` — free, no credit card required. Grab one at
  https://console.groq.com/keys. Used first if set.
- `ANTHROPIC_API_KEY` — paid, used only as a fallback if Groq isn't set.

## Using your own dataset

In the app, open **"Upload a new dataset"** and upload:

- one or more `.csv` files, or
- a `.zip` of CSVs (e.g. a straight Kaggle download)

Pick how many Easy/Medium/Hard questions you want, then click **Load dataset
& generate questions**. Each CSV becomes a table, and:

- with an API key set, an LLM writes questions + reference SQL straight from
  your schema and sample rows — every solution is executed and validated
  before being shown, so anything broken just gets dropped silently;
- without a key, a built-in template generator covers the same ground
  (counts, group-bys, aggregates, derived columns, window functions,
  correlated subqueries) with no LLM required.

From there it's the same flow as the built-in database: write SQL, get
graded, get feedback.

## How it's put together

- `db/schema.sql` + `db/build_db.py` — defines and seeds the built-in
  FinCommerce database.
- `questions.py` — the built-in question bank, each with a reference SQL
  solution.
- `dataset_loader.py` — loads uploaded CSV/zip files into a SQLite database
  and summarizes each table's columns/types/sample rows.
- `dynamic_questions.py` — builds (and validates) a question set for a
  custom dataset, via LLM or the offline template fallback.
- `grader.py` — runs your query and the reference query against the same
  database and compares the results.
- `llm.py` — turns your query, your explanation, and the correctness check
  into interviewer-style feedback (or canned feedback offline).
- `app.py` — the Streamlit app itself: pick a database, work through
  questions, browse tables, write SQL, get graded.

## Adding your own built-in questions

Add an entry to `QUESTIONS` in `questions.py` with a `prompt`, a `solution`
(SQL), and `ordered` (whether row order matters for grading).
