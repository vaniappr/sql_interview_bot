"""Generates interview questions for a user-uploaded dataset.

Tailoring to the target industry, and the storyline that ties the question
set together, both require an LLM, so this needs GROQ_API_KEY (free tier) or
ANTHROPIC_API_KEY to be set. Every generated solution is executed against
the real dataset and validated before being shown (broken questions are
silently dropped).
"""

import json
import os
import re

from grader import grade
from dataset_loader import CUSTOM_DB_PATH, TableSummary

GEN_SYSTEM_PROMPT = """You are writing a SQL interview question set for a candidate, \
based on a real dataset whose schema is provided, tailored to a specific \
candidate profile. Write questions that are answerable using only the given \
tables/columns and valid SQLite syntax (the grading engine is SQLite, so \
every "solution" must be valid, runnable SQLite SQL regardless of which SQL \
dialect the candidate is targeting).

Follow these difficulty bars strictly:
- Easy: a single filter, a single aggregate, or a simple GROUP BY with COUNT.
- Medium: must require at least two of: GROUP BY combined with HAVING, a join \
across two tables, a multi-column GROUP BY, or a derived/computed column \
(e.g. ratios, percentages). A plain "average of one column" is NOT medium.
- Hard: must require a window function (ROW_NUMBER/RANK/running total), a \
correlated or scalar subquery (e.g. "above the average"), a multi-table join \
combined with aggregation, or a CTE chaining multiple steps.

Across the question set as a whole, aim for broad topic coverage rather than \
clustering on a few favorites. Topics to draw from: SELECT/filtering (WHERE, \
IN, BETWEEN, LIKE, NULL checks), CASE statements, aggregations (COUNT, SUM, \
AVG, MIN, MAX), GROUP BY with HAVING, joins (INNER/LEFT/RIGHT/FULL), window \
functions (running totals, partitioned aggregates), date functions, string \
functions, CTEs, data-cleaning patterns (COALESCE, NULLIF, dedup via \
ROW_NUMBER), ranking functions (ROW_NUMBER, RANK, DENSE_RANK, NTILE), and \
classic interview patterns such as top-N-per-group, running totals, and \
next/previous-row comparisons (e.g. LAG/LEAD for retention-style questions). \
Map each topic to whichever difficulty it naturally fits (e.g. a single \
aggregate is Easy, a window function is Hard) — never bend a difficulty bar \
just to force a topic in. If the dataset's schema genuinely can't support a \
topic (e.g. there's no date/timestamp column, so date functions are out, or \
no natural second table, so joins are out), skip that topic rather than \
inventing an unanswerable or out-of-scope question; favor depth on the \
topics the data does support over checking every box. With a small question \
count, you won't fit every topic — prioritize variety over completeness.

Tailor every question to the candidate's target industry: phrase questions \
the way an interviewer at a company in that industry would phrase them, \
using terminology and scenarios that feel native to that industry.

Critically, the whole set must read as ONE coherent storyline, not a random \
grab-bag: invent a short scenario (e.g. "you've just joined the analytics \
team at a {industry} company and your first task is...") and have each \
question build on that same scenario and dataset context, roughly in a \
logical order an interviewer would walk through (start broad/exploratory, \
then narrow in, then dig into edge cases or efficiency). Reference the \
shared scenario in each prompt's wording so it doesn't feel like \
disconnected questions.

Respond with ONLY a JSON array, no prose, no markdown fences. Each element: \
{"difficulty": "Easy|Medium|Hard", "topic": "...", "prompt": "...", \
"solution": "<valid SQLite SELECT statement>", "ordered": true|false}. \
"ordered" should be true only if the prompt asks for a specific sort order."""


def _schema_text(summaries: list[TableSummary]) -> str:
    parts = []
    for t in summaries:
        cols = ", ".join(f"{c} ({dt})" for c, dt in t.columns)
        parts.append(f"Table {t.name} ({t.row_count} rows): {cols}\nSample rows: {t.sample_rows}")
    return "\n\n".join(parts)


def _profile_text(profile: dict) -> str:
    return f"Target industry: {profile.get('industry')}"


def _llm_generate(summaries: list[TableSummary], counts: dict, profile: dict):
    breakdown = ", ".join(f"{n} {d}" for d, n in counts.items() if n)
    user_msg = (
        f"Candidate profile:\n{_profile_text(profile)}\n\n"
        f"Dataset schema:\n\n{_schema_text(summaries)}\n\n"
        f"Write exactly: {breakdown} interview questions, as a single JSON array "
        "per the instructions (the \"difficulty\" field on each element must match), "
        "all part of one coherent storyline tailored to this candidate profile."
    )

    if os.environ.get("GROQ_API_KEY"):
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=3000,
            messages=[
                {"role": "system", "content": GEN_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        text = response.choices[0].message.content.strip()
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            system=GEN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()

    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def generate_questions(summaries: list[TableSummary], counts: dict, profile: dict) -> list[dict]:
    """Returns a validated list of question dicts (same shape as
    questions.QUESTIONS) for the dataset currently loaded at CUSTOM_DB_PATH,
    tailored to `profile` and written as one coherent storyline.

    `counts` maps difficulty -> desired number of questions, e.g.
    {"Easy": 3, "Medium": 3, "Hard": 2}.

    `profile` carries the candidate-facing tailoring field: industry.

    Requires GROQ_API_KEY or ANTHROPIC_API_KEY to be set — personalization
    and the storyline both need an LLM, there is no offline fallback.
    """
    if not any(counts.values()):
        return []

    if not (os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError(
            "Tailored, storyline-based question generation requires GROQ_API_KEY "
            "or ANTHROPIC_API_KEY to be set."
        )

    raw = _llm_generate(summaries, counts, profile)

    validated = []
    for i, q in enumerate(raw, start=1):
        try:
            result = grade(q["solution"], q["solution"], q.get("ordered", False), db_path=CUSTOM_DB_PATH)
        except Exception:
            continue
        if result.error:
            continue
        validated.append({
            "id": i,
            "difficulty": q.get("difficulty", "Medium"),
            "topic": q.get("topic", "General"),
            "prompt": q["prompt"],
            "solution": q["solution"],
            "ordered": q.get("ordered", False),
        })

    return validated
