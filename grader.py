"""Executes a candidate SQL query against the interview database and grades
it against a reference solution by comparing result sets."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "db" / "fincommerce.db"


@dataclass
class GradeResult:
    correct: bool
    error: str | None
    candidate_rows: list
    candidate_columns: list
    expected_rows: list
    expected_columns: list


def _run(conn, sql: str):
    cur = conn.execute(sql)
    columns = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    return columns, rows


def grade(candidate_sql: str, solution_sql: str, ordered: bool, db_path: Path = DEFAULT_DB_PATH) -> GradeResult:
    conn = sqlite3.connect(db_path)
    try:
        try:
            cand_cols, cand_rows = _run(conn, candidate_sql)
        except sqlite3.Error as e:
            return GradeResult(False, str(e), [], [], [], [])

        exp_cols, exp_rows = _run(conn, solution_sql)

        if ordered:
            correct = cand_rows == exp_rows
        else:
            correct = sorted(map(str, cand_rows)) == sorted(map(str, exp_rows))

        return GradeResult(correct, None, cand_rows, cand_cols, exp_rows, exp_cols)
    finally:
        conn.close()
