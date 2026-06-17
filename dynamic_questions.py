"""Generates interview questions for a user-uploaded dataset.

If GROQ_API_KEY (free tier) or ANTHROPIC_API_KEY is set, asks an LLM to
write questions + reference SQL against the actual schema, then validates
every generated solution by executing it (dropping any that error). Without
either key, falls back to a handful of heuristic template questions built
directly from column types.
"""

import json
import os
import re

from grader import grade
from dataset_loader import CUSTOM_DB_PATH, TableSummary

GEN_SYSTEM_PROMPT = """You are writing SQL interview questions for a candidate, \
based on a real dataset whose schema is provided. Write questions that are \
answerable using only the given tables/columns and valid SQLite syntax. \
Follow these difficulty bars strictly:
- Easy: a single filter, a single aggregate, or a simple GROUP BY with COUNT.
- Medium: must require at least two of: GROUP BY combined with HAVING, a join \
across two tables, a multi-column GROUP BY, or a derived/computed column \
(e.g. ratios, percentages). A plain "average of one column" is NOT medium.
- Hard: must require a window function (ROW_NUMBER/RANK/running total), a \
correlated or scalar subquery (e.g. "above the average"), a multi-table join \
combined with aggregation, or a CTE chaining multiple steps.
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


def _llm_generate(summaries: list[TableSummary], counts: dict):
    breakdown = ", ".join(f"{n} {d}" for d, n in counts.items() if n)
    user_msg = (
        f"Dataset schema:\n\n{_schema_text(summaries)}\n\n"
        f"Write exactly: {breakdown} interview questions, as a single JSON array "
        "per the instructions (the \"difficulty\" field on each element must match)."
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


def _column_kinds(t: TableSummary):
    numeric_cols = [
        c for c, dt in t.columns
        if ("int" in dt or "float" in dt) and not c.endswith("id") and c != "id"
    ]
    text_cols = [c for c, dt in t.columns if "object" in dt or "category" in dt or "str" in dt]
    return numeric_cols, text_cols


def _build_pools(summaries: list[TableSummary]):
    """Builds per-difficulty pools of candidate questions across all tables."""
    pools = {"Easy": [], "Medium": [], "Hard": []}

    for t in summaries:
        numeric_cols, text_cols = _column_kinds(t)

        pools["Easy"].append({
            "difficulty": "Easy",
            "topic": "Row count",
            "prompt": f"How many rows are in the `{t.name}` table?",
            "solution": f"SELECT COUNT(*) AS row_count FROM {t.name}",
            "ordered": False,
        })

        if text_cols:
            col = text_cols[0]
            pools["Easy"].append({
                "difficulty": "Easy",
                "topic": "Grouping",
                "prompt": f"For the `{t.name}` table, count rows grouped by `{col}`.",
                "solution": f"SELECT {col}, COUNT(*) AS cnt FROM {t.name} GROUP BY {col}",
                "ordered": False,
            })

        if numeric_cols:
            col = numeric_cols[0]
            pools["Easy"].append({
                "difficulty": "Easy",
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

        # --- Medium: GROUP BY + HAVING, or grouped aggregate with sort, or
        # a multi-column GROUP BY when enough columns exist.
        if text_cols and numeric_cols:
            tcol, ncol = text_cols[0], numeric_cols[0]
            pools["Medium"].append({
                "difficulty": "Medium",
                "topic": "Group + Having",
                "prompt": (
                    f"For `{t.name}`, group by `{tcol}` and compute the total `{ncol}` "
                    f"(as total_{ncol}) per group, but only include groups where the total "
                    f"exceeds the overall average total per group. Order by total_{ncol} descending."
                ),
                "solution": f"""
                    WITH grouped AS (
                        SELECT {tcol}, SUM({ncol}) AS total_{ncol}
                        FROM {t.name}
                        GROUP BY {tcol}
                    )
                    SELECT {tcol}, total_{ncol}
                    FROM grouped
                    WHERE total_{ncol} > (SELECT AVG(total_{ncol}) FROM grouped)
                    ORDER BY total_{ncol} DESC
                """,
                "ordered": True,
            })

        if len(text_cols) >= 2 and numeric_cols:
            tcol1, tcol2, ncol = text_cols[0], text_cols[1], numeric_cols[0]
            pools["Medium"].append({
                "difficulty": "Medium",
                "topic": "Multi-column grouping",
                "prompt": (
                    f"For `{t.name}`, group by both `{tcol1}` and `{tcol2}`, and return the "
                    f"count of rows and average `{ncol}` (as avg_{ncol}) per combination."
                ),
                "solution": (
                    f"SELECT {tcol1}, {tcol2}, COUNT(*) AS cnt, AVG({ncol}) AS avg_{ncol} "
                    f"FROM {t.name} GROUP BY {tcol1}, {tcol2}"
                ),
                "ordered": False,
            })

        if len(numeric_cols) >= 2:
            ncol1, ncol2 = numeric_cols[0], numeric_cols[1]
            pools["Medium"].append({
                "difficulty": "Medium",
                "topic": "Derived column",
                "prompt": (
                    f"For `{t.name}`, return every row's `{ncol1}`, `{ncol2}`, and the ratio "
                    f"{ncol1}/{ncol2} (as ratio), rounded to 2 decimals. Exclude rows where "
                    f"{ncol2} is 0."
                ),
                "solution": (
                    f"SELECT {ncol1}, {ncol2}, ROUND(CAST({ncol1} AS REAL) / {ncol2}, 2) AS ratio "
                    f"FROM {t.name} WHERE {ncol2} != 0"
                ),
                "ordered": False,
            })

        # --- Hard: window function (top row per group) and above-average
        # filter via correlated/scalar subquery.
        if text_cols and numeric_cols:
            tcol, ncol = text_cols[0], numeric_cols[0]
            pools["Hard"].append({
                "difficulty": "Hard",
                "topic": "Window function",
                "prompt": (
                    f"For each `{tcol}` group in `{t.name}`, find the single row with the "
                    f"highest `{ncol}`. Return {tcol} and {ncol} for that top row per group."
                ),
                "solution": f"""
                    WITH ranked AS (
                        SELECT {tcol}, {ncol},
                               ROW_NUMBER() OVER (PARTITION BY {tcol} ORDER BY {ncol} DESC) AS rn
                        FROM {t.name}
                    )
                    SELECT {tcol}, {ncol} FROM ranked WHERE rn = 1
                """,
                "ordered": False,
            })

            pools["Hard"].append({
                "difficulty": "Hard",
                "topic": "Correlated subquery",
                "prompt": (
                    f"For each `{tcol}` group in `{t.name}`, find rows where `{ncol}` is "
                    f"above that group's own average `{ncol}`. Return {tcol} and {ncol}."
                ),
                "solution": f"""
                    SELECT t1.{tcol}, t1.{ncol}
                    FROM {t.name} t1
                    WHERE t1.{ncol} > (
                        SELECT AVG(t2.{ncol}) FROM {t.name} t2 WHERE t2.{tcol} = t1.{tcol}
                    )
                """,
                "ordered": False,
            })

        if numeric_cols:
            ncol = numeric_cols[0]
            pools["Hard"].append({
                "difficulty": "Hard",
                "topic": "Running total",
                "prompt": (
                    f"List every row's `{ncol}` from `{t.name}` along with a running total "
                    f"(cumulative sum of {ncol}) computed in row order, as running_total."
                ),
                "solution": (
                    f"SELECT {ncol}, SUM({ncol}) OVER (ORDER BY rowid) AS running_total "
                    f"FROM {t.name}"
                ),
                "ordered": True,
            })

    return pools


def _heuristic_generate(summaries: list[TableSummary], counts: dict):
    """Offline fallback: builds candidate questions per difficulty from
    column types, then trims each pool down to the requested count."""
    pools = _build_pools(summaries)
    selected = []
    for difficulty, count in counts.items():
        selected.extend(pools.get(difficulty, [])[:count])
    return selected


def generate_questions(summaries: list[TableSummary], counts: dict) -> list[dict]:
    """Returns a validated list of question dicts (same shape as
    questions.QUESTIONS) for the dataset currently loaded at CUSTOM_DB_PATH.

    `counts` maps difficulty -> desired number of questions, e.g.
    {"Easy": 3, "Medium": 3, "Hard": 2}.
    """
    if not any(counts.values()):
        return []

    if os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        try:
            raw = _llm_generate(summaries, counts)
        except Exception:
            raw = _heuristic_generate(summaries, counts)
    else:
        raw = _heuristic_generate(summaries, counts)

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
