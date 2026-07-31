"""
data_utils.py
Handles reading CSV/Excel files, auto-detecting which columns represent
student name/ID, CA score, practical score, exam score, total, course, and
attendance, plus detecting repeated-assessment columns for trend analysis.
"""

import re
import pandas as pd


NAME_HINTS = ["name", "student", "matric", "reg no", "regno", "id number", "student id"]
CA_HINTS = ["ca", "continuous assessment", "c.a", "test score", "coursework"]
PRACTICAL_HINTS = ["practical", "prac", "lab score", "lab"]
EXAM_HINTS = ["exam", "examination", "final exam"]
TOTAL_HINTS = ["total", "grand total", "overall"]
COURSE_HINTS = ["course", "subject", "class"]
ATTENDANCE_HINTS = ["attendance", "attend"]

TREND_PATTERN = re.compile(r"(ca|test|quiz|assessment|exam)\s*[\-_]?\s*(\d+)", re.IGNORECASE)


def load_file(uploaded_file):
    """Load a CSV or Excel file into a pandas DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Unsupported file type. Please upload a .csv, .xlsx, or .xls file.")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find_column(columns, hints):
    lower_map = {c: c.lower() for c in columns}
    for c, lc in lower_map.items():
        for h in hints:
            if h in lc:
                return c
    return None


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Guess which columns correspond to name, ca, practical, exam, total,
    course, attendance. Returns a dict of role -> column name (or None).
    """
    columns = list(df.columns)

    guess = {
        "name": _find_column(columns, NAME_HINTS),
        "ca": _find_column(columns, CA_HINTS),
        "practical": _find_column(columns, PRACTICAL_HINTS),
        "exam": _find_column(columns, EXAM_HINTS),
        "total": _find_column(columns, TOTAL_HINTS),
        "course": _find_column(columns, COURSE_HINTS),
        "attendance": _find_column(columns, ATTENDANCE_HINTS),
    }

    if guess["name"] is None:
        used = {v for v in guess.values() if v}
        for c in columns:
            if c in used:
                continue
            if not pd.api.types.is_numeric_dtype(df[c]):
                guess["name"] = c
                break

    return guess


def coerce_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def compute_total_if_missing(df: pd.DataFrame, ca_col, practical_col, exam_col, total_col):
    df = df.copy()
    if total_col and total_col in df.columns:
        return df, total_col

    component_cols = [c for c in [ca_col, practical_col, exam_col] if c]
    if not component_cols:
        return df, None

    df["Computed Total"] = df[component_cols].sum(axis=1, skipna=True)
    return df, "Computed Total"


def detect_trend_columns(df: pd.DataFrame):
    """
    Look for repeated-assessment columns like 'CA1', 'CA2', 'Test 1', 'Test 2',
    'Quiz1', 'Quiz2' that suggest performance over time. Returns an ordered
    list of column names (earliest first) for the largest matching group, or
    None if fewer than 2 such columns are found.
    """
    groups = {}
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        m = TREND_PATTERN.search(c)
        if m:
            base = m.group(1).lower()
            num = int(m.group(2))
            groups.setdefault(base, []).append((num, c))

    best = None
    for base, items in groups.items():
        if len(items) >= 2:
            items.sort(key=lambda x: x[0])
            if best is None or len(items) > len(best):
                best = items

    if best:
        return [c for _, c in best]
    return None
