"""
analysis_utils.py
Computes descriptive statistics, grade distributions, pass/fail rates,
student-level rankings and deviations, CA-vs-exam consistency checks,
correlation analysis, risk/intervention flags, grading-skew and assessment
difficulty diagnostics, and trend-over-time data.
"""

import numpy as np
import pandas as pd

DEFAULT_GRADE_BOUNDARIES = [
    ("A", 70, 100),
    ("B", 60, 69.999),
    ("C", 50, 59.999),
    ("D", 45, 49.999),
    ("F", 0, 44.999),
]


# ---------------------------------------------------------------------------
# 1. Overall Performance
# ---------------------------------------------------------------------------

def assign_grade(score, boundaries=DEFAULT_GRADE_BOUNDARIES):
    if pd.isna(score):
        return "N/A"
    for label, low, high in boundaries:
        if low <= score <= high:
            return label
    return "N/A"


def _mode_of(series: pd.Series):
    m = series.mode()
    if m.empty:
        return np.nan
    return round(float(m.iloc[0]), 2)


def component_stats(df: pd.DataFrame, score_cols: dict) -> pd.DataFrame:
    """score_cols: dict like {'CA': 'CA Score', 'Practical': 'Practical Score', ...}"""
    rows = []
    for label, col in score_cols.items():
        if col is None or col not in df.columns:
            continue
        series = df[col].dropna()
        if series.empty:
            continue
        rows.append({
            "Component": label,
            "Mean": round(series.mean(), 2),
            "Median": round(series.median(), 2),
            "Mode": _mode_of(series),
            "Std Dev": round(series.std(), 2),
            "Min": round(series.min(), 2),
            "Max": round(series.max(), 2),
            "Count": int(series.count()),
        })
    return pd.DataFrame(rows)


def pass_fail_summary(df: pd.DataFrame, total_col: str, pass_mark: float) -> dict:
    valid = df[total_col].dropna()
    total_students = len(valid)
    passed = int((valid >= pass_mark).sum())
    failed = total_students - passed
    pass_rate = round((passed / total_students) * 100, 1) if total_students else 0.0
    return {
        "total_students": total_students,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
    }


def grade_distribution(df: pd.DataFrame, total_col: str, boundaries=DEFAULT_GRADE_BOUNDARIES) -> pd.DataFrame:
    grades = df[total_col].apply(lambda x: assign_grade(x, boundaries))
    counts = grades.value_counts().reindex([b[0] for b in boundaries], fill_value=0)
    dist = counts.reset_index()
    dist.columns = ["Grade", "Number of Students"]
    return dist


# ---------------------------------------------------------------------------
# 2. Student-Level Insights
# ---------------------------------------------------------------------------

def rank_students(df: pd.DataFrame, name_col: str, total_col: str) -> pd.DataFrame:
    """Full ranking of every student with their deviation from the class average."""
    valid = df[[name_col, total_col]].dropna().copy()
    class_avg = valid[total_col].mean()
    valid = valid.sort_values(total_col, ascending=False).reset_index(drop=True)
    valid.insert(0, "Rank", range(1, len(valid) + 1))
    valid["Deviation from Avg"] = round(valid[total_col] - class_avg, 2)
    return valid


def top_bottom_performers(df: pd.DataFrame, name_col: str, total_col: str, n: int = 5):
    ranked = df[[name_col, total_col]].dropna().sort_values(total_col, ascending=False)
    top = ranked.head(n).reset_index(drop=True)
    bottom = ranked.tail(n).sort_values(total_col).reset_index(drop=True)
    return top, bottom


# ---------------------------------------------------------------------------
# 3. Assessment Breakdown (CA vs Exam consistency)
# ---------------------------------------------------------------------------

def ca_vs_exam_consistency(df: pd.DataFrame, name_col: str, ca_col: str, exam_col: str,
                            z_threshold: float = 1.0) -> pd.DataFrame:
    """
    Flags students whose relative standing (z-score) in CA differs sharply
    from their relative standing in the exam — i.e. inconsistent performers.
    Uses z-scores so it's fair even if CA and exam are marked out of
    different maximums.
    """
    if not ca_col or not exam_col:
        return pd.DataFrame()

    sub = df[[name_col, ca_col, exam_col]].dropna().copy()
    if sub.empty or sub[ca_col].std() == 0 or sub[exam_col].std() == 0:
        return pd.DataFrame()

    z_ca = (sub[ca_col] - sub[ca_col].mean()) / sub[ca_col].std()
    z_exam = (sub[exam_col] - sub[exam_col].mean()) / sub[exam_col].std()
    sub["Diff (z-CA minus z-Exam)"] = round(z_ca - z_exam, 2)

    def label(diff):
        if diff >= z_threshold:
            return "High CA, Low Exam"
        elif diff <= -z_threshold:
            return "Low CA, High Exam"
        return None

    sub["Flag"] = sub["Diff (z-CA minus z-Exam)"].apply(label)
    flagged = sub[sub["Flag"].notna()].copy()
    flagged = flagged.reindex(flagged["Diff (z-CA minus z-Exam)"].abs().sort_values(ascending=False).index)
    return flagged.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Correlation Analysis
# ---------------------------------------------------------------------------

def correlation_matrix(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    valid_cols = [c for c in cols if c and c in df.columns]
    if len(valid_cols) < 2:
        return pd.DataFrame()
    return df[valid_cols].corr().round(2)


def component_contribution(df: pd.DataFrame, score_cols: dict, total_col: str) -> pd.DataFrame:
    rows = []
    total_mean = df[total_col].mean() if total_col in df.columns else np.nan
    for label, col in score_cols.items():
        if col is None or col not in df.columns:
            continue
        comp_mean = df[col].mean()
        pct = round((comp_mean / total_mean) * 100, 1) if total_mean else np.nan
        rows.append({"Component": label, "Avg Score": round(comp_mean, 2), "% of Total": pct})
    return pd.DataFrame(rows)


def strongest_correlation(corr_df: pd.DataFrame, total_col: str):
    """Returns (column, r-value) of the component most correlated with the total, excluding itself."""
    if corr_df.empty or total_col not in corr_df.columns:
        return None, None
    series = corr_df[total_col].drop(labels=[total_col], errors="ignore")
    if series.empty:
        return None, None
    best_col = series.abs().idxmax()
    return best_col, series[best_col]


# ---------------------------------------------------------------------------
# 5. Risk & Intervention Analysis
# ---------------------------------------------------------------------------

def risk_intervention_table(df: pd.DataFrame, name_col: str, total_col: str,
                             pass_mark: float, borderline_margin: float = 5.0) -> pd.DataFrame:
    """Flags failing and borderline students, with a suggested intervention."""
    sub = df[[name_col, total_col]].dropna().copy()

    def categorize(score):
        if score < pass_mark:
            return "Fail"
        elif score < pass_mark + borderline_margin:
            return "Borderline"
        return "Safe"

    sub["Status"] = sub[total_col].apply(categorize)
    at_risk = sub[sub["Status"] != "Safe"].sort_values(total_col).reset_index(drop=True)

    def suggestion(status):
        if status == "Fail":
            return "Recommend remedial classes, one-on-one review of fundamentals, and a resit plan."
        return "Monitor closely; targeted revision on weak topics could push this student to a clear pass."

    at_risk["Suggested Intervention"] = at_risk["Status"].apply(suggestion)
    return at_risk


# ---------------------------------------------------------------------------
# 6. Trends & Patterns (only if repeated-assessment columns exist)
# ---------------------------------------------------------------------------

def trend_summary(df: pd.DataFrame, trend_cols: list) -> pd.DataFrame:
    """Class average for each sequential assessment column, in order."""
    rows = []
    for c in trend_cols:
        series = df[c].dropna()
        if series.empty:
            continue
        rows.append({"Assessment": c, "Class Average": round(series.mean(), 2)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. Insights for Lecturer (difficulty & grading skew)
# ---------------------------------------------------------------------------

def grading_skew(df: pd.DataFrame, total_col: str) -> dict:
    series = df[total_col].dropna()
    if len(series) < 3:
        return {"skew": 0.0, "interpretation": "Not enough data to assess grading skew."}
    skew = round(float(series.skew()), 2)
    if skew > 0.5:
        interpretation = (
            "Scores are right-skewed — most students scored on the lower end with a few high "
            "outliers. This can indicate a difficult assessment or a stricter grading standard."
        )
    elif skew < -0.5:
        interpretation = (
            "Scores are left-skewed — most students scored on the higher end with a few low "
            "outliers. This can indicate an easier assessment or a more lenient grading standard."
        )
    else:
        interpretation = "Scores are roughly symmetric, suggesting balanced grading and assessment difficulty."
    return {"skew": skew, "interpretation": interpretation}


def component_difficulty(df: pd.DataFrame, score_cols: dict, max_marks: dict) -> pd.DataFrame:
    """
    Estimates how 'hard' each component was, using % of the maximum
    achievable mark actually scored on average. Lower % = harder / stricter.
    """
    rows = []
    for label, col in score_cols.items():
        if col is None or col not in df.columns:
            continue
        max_mark = max_marks.get(label)
        series = df[col].dropna()
        if series.empty or not max_mark:
            continue
        pct_achieved = round((series.mean() / max_mark) * 100, 1)
        rows.append({"Component": label, "Avg % Achieved": pct_achieved})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 8. Insights for Students (rule-based, derived from the above)
# ---------------------------------------------------------------------------

def student_advice(strongest_corr_col, corr_value, component_df: pd.DataFrame) -> list:
    advice = []
    if strongest_corr_col and corr_value is not None:
        advice.append(
            f"'{strongest_corr_col}' shows the strongest relationship with the final total "
            f"(r = {corr_value}). Prioritizing consistent effort here is likely to have the "
            f"biggest impact on overall results."
        )
    if not component_df.empty:
        weakest = component_df.loc[component_df["Avg Score"].idxmin()]
        advice.append(
            f"Class-wide, '{weakest['Component']}' had the lowest average score — students "
            f"should pay extra attention to this component when preparing."
        )
    advice.append(
        "Consistency across CA and exams tends to matter more than a single stand-out score — "
        "steady preparation throughout the term outperforms last-minute cramming."
    )
    return advice
