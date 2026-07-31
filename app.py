"""
Student Results Analyzer
-------------------------
A Streamlit app that lets a course lecturer upload student results
(CSV/Excel) with CA, Practical, Exam and Total scores (practical scores
optional), view a detailed 8-section performance analysis (with an
AI-written narrative from a local Ollama model), and download a full PDF
report.
"""

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from modules import data_utils, analysis_utils, ollama_utils, pdf_utils


def safe_boxplot(ax, data, labels):
    """Compatible with both old (`labels=`) and new (`tick_labels=`) matplotlib APIs."""
    try:
        ax.boxplot(data, tick_labels=labels)
    except TypeError:
        ax.boxplot(data, labels=labels)

st.set_page_config(page_title="Student Results Analyzer", layout="wide", page_icon="📊")

# Moderate, consistent chart size for on-screen display
CHART_SIZE = (4, 2.8)
CHART_SIZE_SQUARE = (3.4, 3.0)

# ----------------------------- Sidebar config ------------------------------
st.sidebar.title("⚙️ Settings")

ollama_host = st.sidebar.text_input("Ollama host", value="http://localhost:11434")
ollama_model = st.sidebar.text_input("Ollama model", value="llama3.2:1b")

st.sidebar.markdown("---")
pass_mark = st.sidebar.number_input("Pass mark (out of 100)", min_value=0, max_value=100, value=40)
borderline_margin = st.sidebar.number_input("Borderline margin (points above pass mark)", min_value=1, max_value=20, value=5)
z_threshold = st.sidebar.slider("CA vs Exam inconsistency sensitivity (z-score)", 0.5, 2.0, 1.0, 0.1)

st.sidebar.markdown("**Grade boundaries**")
grade_a = st.sidebar.number_input("A ≥", min_value=0, max_value=100, value=70)
grade_b = st.sidebar.number_input("B ≥", min_value=0, max_value=100, value=60)
grade_c = st.sidebar.number_input("C ≥", min_value=0, max_value=100, value=50)
grade_d = st.sidebar.number_input("D ≥", min_value=0, max_value=100, value=45)

boundaries = [
    ("A", grade_a, 100),
    ("B", grade_b, grade_a - 0.001),
    ("C", grade_c, grade_b - 0.001),
    ("D", grade_d, grade_c - 0.001),
    ("F", 0, grade_d - 0.001),
]

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ Ollama must be reachable from wherever this app runs. On Streamlit "
    "Community Cloud, Ollama will NOT be available unless 'Ollama host' "
    "points at a remote server you control running Ollama."
)

# ----------------------------- Header --------------------------------------
st.title("📊 Student Results Analyzer")
st.write(
    "Upload a CSV or Excel file with student results (CA, Practical, Exam, Total — "
    "or CA, Exam, Total if there's no practical component) for a full 8-section "
    "performance analysis and a downloadable PDF report."
)
st.caption(
    "Covers: Overall Performance · Student-Level Insights · Assessment Breakdown · "
    "Correlation Analysis · Risk & Intervention · Trends & Patterns · Insights for "
    "Lecturer · Insights for Students."
)

uploaded_file = st.file_uploader("Upload results file", type=["csv", "xlsx", "xls"])

if uploaded_file is None:
    st.info("👆 Upload a file to get started.")
    st.stop()

# ----------------------------- Load & detect columns ------------------------
try:
    df_raw = data_utils.load_file(uploaded_file)
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

st.subheader("Preview of uploaded data")
st.dataframe(df_raw.head(10), use_container_width=True)

guess = data_utils.detect_columns(df_raw)
columns = list(df_raw.columns)
none_option = "— None —"
options = [none_option] + columns


def col_index(guessed_col):
    return options.index(guessed_col) if guessed_col in options else 0


st.subheader("Confirm column mapping")
st.caption("Auto-detected where possible — adjust any that look wrong.")

c1, c2, c3 = st.columns(3)
with c1:
    name_col = st.selectbox("Student name / ID column", options, index=col_index(guess["name"]))
    course_col = st.selectbox("Course column (optional)", options, index=col_index(guess["course"]))
with c2:
    ca_col = st.selectbox("CA score column", options, index=col_index(guess["ca"]))
    practical_col = st.selectbox("Practical score column (optional)", options, index=col_index(guess["practical"]))
with c3:
    exam_col = st.selectbox("Exam score column", options, index=col_index(guess["exam"]))
    total_col_choice = st.selectbox("Total score column (optional — computed if none)", options, index=col_index(guess["total"]))

attendance_col = st.selectbox("Attendance column (optional)", options, index=col_index(guess.get("attendance")))

name_col = None if name_col == none_option else name_col
course_col = None if course_col == none_option else course_col
ca_col = None if ca_col == none_option else ca_col
practical_col = None if practical_col == none_option else practical_col
exam_col = None if exam_col == none_option else exam_col
total_col_choice = None if total_col_choice == none_option else total_col_choice
attendance_col = None if attendance_col == none_option else attendance_col

if name_col is None or (ca_col is None and exam_col is None):
    st.warning("Please make sure at least a student name column and a CA or Exam column are selected.")
    st.stop()

numeric_cols = [c for c in [ca_col, practical_col, exam_col, total_col_choice, attendance_col] if c]
df = data_utils.coerce_numeric(df_raw, numeric_cols)
df, total_col = data_utils.compute_total_if_missing(df, ca_col, practical_col, exam_col, total_col_choice)

if total_col is None:
    st.error("Could not determine or compute a Total score. Please check your column selections.")
    st.stop()

# ----------------------------- Course filter --------------------------------
selected_course = "All Students"
if course_col:
    courses = ["All Students"] + sorted(df[course_col].dropna().unique().tolist())
    selected_course = st.selectbox("Filter by course", courses)
    if selected_course != "All Students":
        df = df[df[course_col] == selected_course]

course_label = selected_course if selected_course != "All Students" else (course_col or "Uploaded Dataset")

score_cols = {}
if ca_col:
    score_cols["CA"] = ca_col
if practical_col:
    score_cols["Practical"] = practical_col
if exam_col:
    score_cols["Exam"] = exam_col

# ----------------------------- Max marks for difficulty analysis -----------
with st.expander("⚙️ Set maximum obtainable marks per component (for difficulty analysis)"):
    max_marks = {}
    for label, col in score_cols.items():
        default_max = float(df[col].max()) if col in df.columns and df[col].notna().any() else 100.0
        max_marks[label] = st.number_input(f"Max marks for {label}", min_value=1.0, value=round(default_max, 1), key=f"max_{label}")

# ============================================================================
# ANALYSIS
# ============================================================================
st.markdown("---")
st.header(f"📈 Analysis: {course_label}")

# --- 1. Overall Performance ---
st.subheader("1️⃣ Overall Performance")
stats_df = analysis_utils.component_stats(df, score_cols)
pass_summary = analysis_utils.pass_fail_summary(df, total_col, pass_mark)
grade_df = analysis_utils.grade_distribution(df, total_col, boundaries)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Students", pass_summary["total_students"])
m2.metric("Passed", pass_summary["passed"])
m3.metric("Failed", pass_summary["failed"])
m4.metric("Pass Rate", f"{pass_summary['pass_rate']}%")

st.dataframe(stats_df, use_container_width=True)

col_a, col_b, col_c = st.columns(3)
with col_a:
    fig, ax = plt.subplots(figsize=CHART_SIZE_SQUARE)
    ax.pie([pass_summary["passed"], pass_summary["failed"]], labels=["Passed", "Failed"],
           autopct="%1.0f%%", startangle=90, colors=["#27ae60", "#c0392b"], textprops={"fontsize": 8})
    ax.set_title("Pass vs Fail", fontsize=10)
    st.pyplot(fig, use_container_width=False)
with col_b:
    fig2, ax2 = plt.subplots(figsize=CHART_SIZE_SQUARE)
    non_zero = grade_df[grade_df["Number of Students"] > 0]
    if not non_zero.empty:
        ax2.pie(non_zero["Number of Students"], labels=non_zero["Grade"], autopct="%1.0f%%",
                startangle=90, textprops={"fontsize": 8})
        ax2.set_title("Grade Distribution", fontsize=10)
    st.pyplot(fig2, use_container_width=False)
with col_c:
    fig3, ax3 = plt.subplots(figsize=CHART_SIZE)
    df[total_col].dropna().hist(bins=12, ax=ax3, color="#2980b9", edgecolor="white")
    ax3.set_title("Score Distribution", fontsize=10)
    ax3.tick_params(labelsize=7)
    st.pyplot(fig3, use_container_width=False)

st.dataframe(grade_df, use_container_width=True)

# --- 2. Student-Level Insights ---
st.subheader("2️⃣ Student-Level Insights")
rank_df = analysis_utils.rank_students(df, name_col, total_col)
top_df, bottom_df = analysis_utils.top_bottom_performers(df, name_col, total_col, n=5)

col_d, col_e = st.columns(2)
with col_d:
    st.markdown("**🏆 Top Performers**")
    st.dataframe(top_df, use_container_width=True)
with col_e:
    st.markdown("**⚠️ May Need Support**")
    st.dataframe(bottom_df, use_container_width=True)

st.markdown("**Full Ranking with Deviation from Class Average**")
st.dataframe(rank_df, use_container_width=True)

# --- 3. Assessment Breakdown ---
st.subheader("3️⃣ Assessment Breakdown")
component_df = analysis_utils.component_contribution(df, score_cols, total_col)
if not component_df.empty:
    col_f, col_g = st.columns(2)
    with col_f:
        st.dataframe(component_df, use_container_width=True)
    with col_g:
        fig4, ax4 = plt.subplots(figsize=CHART_SIZE)
        ax4.bar(component_df["Component"], component_df["Avg Score"], color="#27ae60")
        ax4.set_title("Average Score by Component", fontsize=10)
        ax4.tick_params(labelsize=7)
        st.pyplot(fig4, use_container_width=False)

fig5, ax5 = plt.subplots(figsize=CHART_SIZE)
box_labels, box_data = [], []
for label, col in score_cols.items():
    box_labels.append(label)
    box_data.append(df[col].dropna())
box_labels.append("Total")
box_data.append(df[total_col].dropna())
safe_boxplot(ax5, box_data, box_labels)
ax5.set_title("Score Spread & Outliers", fontsize=10)
ax5.tick_params(labelsize=7)
st.pyplot(fig5, use_container_width=False)

consistency_df = analysis_utils.ca_vs_exam_consistency(df, name_col, ca_col, exam_col, z_threshold=z_threshold)
if not consistency_df.empty:
    st.markdown("**Inconsistent Performers (CA vs Exam)**")
    st.dataframe(consistency_df, use_container_width=True)
elif ca_col and exam_col:
    st.caption("No students showed a strong CA/Exam inconsistency at the current sensitivity setting.")

# --- 4. Correlation Analysis ---
st.subheader("4️⃣ Correlation Analysis")
corr_cols = list(score_cols.values()) + [total_col]
if attendance_col:
    corr_cols.append(attendance_col)
corr_df = analysis_utils.correlation_matrix(df, corr_cols)

if not corr_df.empty:
    col_h, col_i = st.columns(2)
    with col_h:
        st.dataframe(corr_df, use_container_width=True)
    with col_i:
        fig6, ax6 = plt.subplots(figsize=CHART_SIZE_SQUARE)
        im = ax6.imshow(corr_df.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax6.set_xticks(range(len(corr_df.columns)))
        ax6.set_yticks(range(len(corr_df.columns)))
        ax6.set_xticklabels(corr_df.columns, rotation=45, ha="right", fontsize=7)
        ax6.set_yticklabels(corr_df.columns, fontsize=7)
        for i in range(len(corr_df.columns)):
            for j in range(len(corr_df.columns)):
                ax6.text(j, i, corr_df.values[i, j], ha="center", va="center", fontsize=7)
        fig6.colorbar(im, ax=ax6, shrink=0.8)
        ax6.set_title("Correlation Heatmap", fontsize=10)
        st.pyplot(fig6, use_container_width=False)

    if ca_col and exam_col:
        fig7, ax7 = plt.subplots(figsize=CHART_SIZE)
        sub = df[[ca_col, exam_col]].dropna()
        ax7.scatter(sub[ca_col], sub[exam_col], alpha=0.7, color="#8e44ad", s=18)
        ax7.set_xlabel("CA", fontsize=8)
        ax7.set_ylabel("Exam", fontsize=8)
        ax7.set_title("CA vs Exam", fontsize=10)
        ax7.tick_params(labelsize=7)
        st.pyplot(fig7, use_container_width=False)

    strongest_col, strongest_r = analysis_utils.strongest_correlation(corr_df, total_col)
    if strongest_col:
        st.caption(f"Strongest relationship with Total: **{strongest_col}** (r = {strongest_r:.2f})")
else:
    st.caption("Not enough numeric components to compute correlations.")

# --- 5. Risk & Intervention Analysis ---
st.subheader("5️⃣ Risk & Intervention Analysis")
risk_df = analysis_utils.risk_intervention_table(df, name_col, total_col, pass_mark, borderline_margin)
if not risk_df.empty:
    st.dataframe(risk_df, use_container_width=True)
else:
    st.caption("No students currently fall below the borderline threshold. 🎉")

# --- 6. Trends & Patterns ---
st.subheader("6️⃣ Trends & Patterns")
trend_cols = data_utils.detect_trend_columns(df_raw)
trend_df = None
if trend_cols:
    trend_df = analysis_utils.trend_summary(df, trend_cols)
    col_j, col_k = st.columns(2)
    with col_j:
        st.dataframe(trend_df, use_container_width=True)
    with col_k:
        fig8, ax8 = plt.subplots(figsize=CHART_SIZE)
        ax8.plot(trend_df["Assessment"], trend_df["Class Average"], marker="o", color="#e67e22")
        ax8.set_title("Performance Trend Over Time", fontsize=10)
        ax8.tick_params(labelsize=7, axis="x", rotation=30)
        st.pyplot(fig8, use_container_width=False)
else:
    st.caption(
        "Not applicable — this dataset represents a single assessment period. "
        "Trend analysis requires multiple time points (e.g. CA1, CA2, CA3)."
    )

# --- 7. Insights for Lecturer ---
st.subheader("7️⃣ Insights for Lecturer")
skew_info = analysis_utils.grading_skew(df, total_col)
st.write(f"**Grading skew:** {skew_info['skew']} — {skew_info['interpretation']}")

difficulty_df = analysis_utils.component_difficulty(df, score_cols, max_marks)
if not difficulty_df.empty:
    st.dataframe(difficulty_df, use_container_width=True)

# --- 8. Insights for Students ---
st.subheader("8️⃣ Insights for Students")
strongest_col, strongest_r = analysis_utils.strongest_correlation(corr_df, total_col) if not corr_df.empty else (None, None)
advice_list = analysis_utils.student_advice(strongest_col, strongest_r, component_df)
for tip in advice_list:
    st.markdown(f"- {tip}")

st.markdown("---")
st.subheader("Full Results Table")
st.dataframe(df, use_container_width=True)

# ----------------------------- AI Narrative ----------------------------------
st.markdown("---")
st.header("🤖 AI-Generated Detailed Analysis")

if "narrative_text" not in st.session_state:
    st.session_state.narrative_text = ""

if st.button("Generate AI Analysis", type="primary"):
    sections = {
        "overall": (
            f"{stats_df.to_string(index=False) if not stats_df.empty else 'N/A'}\n"
            f"Pass rate: {pass_summary['pass_rate']}% "
            f"({pass_summary['passed']} passed, {pass_summary['failed']} failed out of {pass_summary['total_students']})\n"
            f"Grade distribution:\n{grade_df.to_string(index=False)}"
        ),
        "student_level": (
            f"Top performers:\n{top_df.to_string(index=False)}\n\n"
            f"Students who may need support:\n{bottom_df.to_string(index=False)}"
        ),
        "assessment_breakdown": (
            f"{component_df.to_string(index=False) if not component_df.empty else 'N/A'}\n"
            + (f"\nInconsistent performers (CA vs Exam):\n{consistency_df.to_string(index=False)}"
               if not consistency_df.empty else "\nNo strongly inconsistent CA/Exam performers detected.")
        ),
        "correlation": corr_df.to_string() if not corr_df.empty else "N/A",
        "risk": risk_df.to_string(index=False) if not risk_df.empty else "No at-risk or borderline students.",
        "trends": trend_df.to_string(index=False) if trend_df is not None and not trend_df.empty else None,
        "lecturer": (
            f"Grading skew: {skew_info['skew']} ({skew_info['interpretation']})\n"
            + (f"Assessment difficulty (% of max mark achieved):\n{difficulty_df.to_string(index=False)}"
               if not difficulty_df.empty else "")
        ),
    }
    prompt = ollama_utils.build_prompt(course_label, sections)
    with st.spinner(f"Asking {ollama_model} to analyze the results..."):
        try:
            st.session_state.narrative_text = ollama_utils.generate_analysis(
                prompt, model=ollama_model, host=ollama_host
            )
        except RuntimeError as e:
            st.error(str(e))

if st.session_state.narrative_text:
    st.write(st.session_state.narrative_text)

# ----------------------------- PDF Export -------------------------------------
st.markdown("---")
st.header("📄 Export PDF Report")

if st.button("Generate PDF Report"):
    with st.spinner("Building PDF..."):
        pdf_bytes = pdf_utils.generate_pdf_report(
            course_name=course_label,
            stats_df=stats_df,
            pass_summary=pass_summary,
            grade_df=grade_df,
            top_df=top_df,
            bottom_df=bottom_df,
            component_df=component_df,
            rank_df=rank_df,
            consistency_df=consistency_df,
            risk_df=risk_df,
            corr_df=corr_df,
            trend_df=trend_df,
            skew_info=skew_info,
            difficulty_df=difficulty_df,
            student_advice_list=advice_list,
            narrative_text=st.session_state.narrative_text or "No AI analysis was generated for this report.",
            full_results_df=df[[c for c in [name_col, course_col] + list(score_cols.values()) + [total_col, attendance_col] if c]],
            total_col=total_col,
            score_cols=score_cols,
            ca_col=ca_col,
            exam_col=exam_col,
        )
    st.success("PDF ready!")
    st.download_button(
        label="⬇️ Download PDF Report",
        data=pdf_bytes,
        file_name=f"{course_label.replace(' ', '_')}_performance_report.pdf",
        mime="application/pdf",
    )
