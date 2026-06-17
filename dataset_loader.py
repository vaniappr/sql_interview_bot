"""Loads user-supplied Kaggle datasets (CSV files, or a zip of CSVs) into a
fresh SQLite database so the interview bot can quiz against them."""

import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CUSTOM_DB_PATH = Path(__file__).parent / "db" / "custom.db"


@dataclass
class TableSummary:
    name: str
    columns: list  # list of (column_name, dtype_str)
    sample_rows: list  # list of dicts
    row_count: int


def _sanitize_table_name(filename: str) -> str:
    stem = Path(filename).stem
    name = re.sub(r"[^a-zA-Z0-9_]", "_", stem).strip("_").lower()
    if not name or name[0].isdigit():
        name = f"t_{name}"
    return name


def _extract_csv_files(uploaded_files):
    """Returns list of (table_name, file-like object) for each CSV found,
    unzipping any .zip uploads."""
    csv_entries = []
    for f in uploaded_files:
        if f.name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(f.getvalue())) as z:
                for member in z.namelist():
                    if member.lower().endswith(".csv") and not member.startswith("__MACOSX"):
                        with z.open(member) as csv_file:
                            csv_entries.append((_sanitize_table_name(member), io.BytesIO(csv_file.read())))
        elif f.name.lower().endswith(".csv"):
            csv_entries.append((_sanitize_table_name(f.name), io.BytesIO(f.getvalue())))
    return csv_entries


def load_dataset(uploaded_files) -> list[TableSummary]:
    """Loads uploaded CSV/zip files into db/custom.db, replacing any prior
    custom dataset. Returns a schema summary used to drive question
    generation."""
    if CUSTOM_DB_PATH.exists():
        CUSTOM_DB_PATH.unlink()

    csv_entries = _extract_csv_files(uploaded_files)
    if not csv_entries:
        raise ValueError("No CSV files found in upload (accepts .csv or .zip of .csv files).")

    conn = sqlite3.connect(CUSTOM_DB_PATH)
    summaries = []
    used_names = set()
    try:
        for table_name, csv_file in csv_entries:
            base_name = table_name
            suffix = 1
            while table_name in used_names:
                table_name = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(table_name)

            df = pd.read_csv(csv_file)
            df.columns = [re.sub(r"[^a-zA-Z0-9_]", "_", str(c)).strip("_").lower() or f"col_{i}"
                          for i, c in enumerate(df.columns)]
            df.to_sql(table_name, conn, index=False, if_exists="replace")

            columns = [(c, str(t)) for c, t in zip(df.columns, df.dtypes)]
            sample_rows = df.head(3).to_dict(orient="records")
            summaries.append(TableSummary(table_name, columns, sample_rows, len(df)))
        conn.commit()
    finally:
        conn.close()

    return summaries
