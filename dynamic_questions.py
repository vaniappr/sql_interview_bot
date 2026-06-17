"""Generates interview questions for a user-uploaded dataset.

If ANTHROPIC_API_KEY is set, asks Claude to write questions + reference SQL
against the actual schema, then validates every generated solution by
executing it (dropping any that error). Without an API key, falls back to a
handful of heuristic template questions built directly from column types.
"""

import json
import os
import re

from grader import grade
from dataset_loader import CUSTOM_DB_PATH, TableSummary

GEN_SYSTEM_PROMPT = """You are writing SQL interview questions for a candidate, \
based on a real dataset whose schema is provided. Write questions that are \
answerable using only the given tables/columns and valid SQLite syntax. \
Mix difficulties (Easy/Medium/Hard) and topics (filtering, aggregation, \
joins if multiple tables exist, window functions, subqueries). \
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


def _llm_generate(summaries: list[TableSummary], n: int):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_msg = (
        f"Dataset schema:\n\n{_schema_text(summaries)}\n\n"
        f"Write {n} interview questions as a JSON array per the instructions."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=GEN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _heuristic_generate(summaries: list[TableSummary]):
    """Offline fallback: builds a few generic questions per table using
    detected column types, no LLM required."""
    questions = []
    for t in summaries:
        numeric_cols = [
            c for c, dt in t.columns
            if ("int" in dt or "float" in dt) and not c.endswith("id") and c != "id"
        ]
        text_cols = [c for c, dt in t.columns if "object" in dt or "category" in dt or "str" in dt]

        questions.append({
            "difficulty": "Easy",
            "topic": "Row count",
            "prompt": f"How many rows are in the `{t.name}` table?",
            "solution": f"SELECT COUNT(*) AS row_count FROM {t.name}",
            "ordered": False,
        })

        if text_cols:
            col = text_cols[0]
            questions.append({
                "difficulty": "Easy",
                "topic": "Grouping",
                "prompt": f"For the `{t.name}` table, count rows grouped by `{col}`.",
                "solution": f"SELECT {col}, COUNT(*) AS cnt FROM {t.name} GROUP BY {col}",
                "ordered": False,
            })

        if numeric_cols:
            col = numeric_cols[0]
            questions.append({
                "difficulty": "Medium",
                "topic": "Aggregation",
                "prompt": (
                    f"Find the average, minimum, and maximum of `{col}` in `{t.name}` "
                    "(name them avg_val, min_val, max_val)."
                ),
                "solution": (
                    f"SELECT AVG({col}) AS avg_val, MIN({col}) AS min_val, MAX({col}) AS max_val "
                    f"FROM {t.name}"
                ),
                "ordered": False,
            })
            questions.append({
                "difficulty": "Medium",
                "topic": "Sorting",
                "prompt": f"List the top 5 rows from `{t.name}` ordered by `{col}` descending.",
                "solution": f"SELECT * FROM {t.name} ORDER BY {col} DESC LIMIT 5",
                "ordered": True,
            })

    return questions


def generate_questions(summaries: list[TableSummary], n: int = 8) -> list[dict]:
    """Returns a validated list of question dicts (same shape as
    questions.QUESTIONS) for the dataset currently loaded at CUSTOM_DB_PATH."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            raw = _llm_generate(summaries, n)
        except Exception:
            raw = _heuristic_generate(summaries)
    else:
        raw = _heuristic_generate(summaries)

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
