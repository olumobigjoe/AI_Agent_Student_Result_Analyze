"""
pdf_utils.py
Builds a downloadable PDF report combining stats tables, moderately-sized
charts, and the AI-generated narrative analysis, organized into the full
8-section analysis framework.
"""

import io
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)

# Moderate, consistent chart sizing (inches) and PDF embed width
CHART_FIGSIZE = (4.2, 3.0)
CHART_FIGSIZE_SQUARE = (3.6, 3.2)
PDF_IMG_WIDTH = 9 * cm
PDF_IMG_WIDTH_SMALL = 7.5 * cm


def _df_to_table(df, col_widths=None):
    data = [list(df.columns)] + df.astype(str).values.tolist()
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _fig_to_image(fig, width=PDF_IMG_WIDTH):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    aspect = fig.get_size_inches()[1] / fig.get_size_inches()[0]
    return Image(buf, width=width, height=width * aspect)


def _grade_pie_chart(grade_df):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE_SQUARE)
    non_zero = grade_df[grade_df["Number of Students"] > 0]
    if non_zero.empty:
        ax.text(0.5, 0.5, "No data", ha="center")
    else:
        ax.pie(non_zero["Number of Students"], labels=non_zero["Grade"], autopct="%1.0f%%", startangle=90,
               textprops={"fontsize": 8})
        ax.set_title("Grade Distribution", fontsize=10)
    return fig


def _pass_fail_pie_chart(pass_summary):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE_SQUARE)
    values = [pass_summary["passed"], pass_summary["failed"]]
    labels = ["Passed", "Failed"]
    ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90, colors=["#27ae60", "#c0392b"],
           textprops={"fontsize": 8})
    ax.set_title("Pass vs Fail", fontsize=10)
    return fig


def _score_hist_chart(df, total_col):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    df[total_col].dropna().hist(bins=12, ax=ax, color="#2980b9", edgecolor="white")
    ax.set_xlabel("Total Score", fontsize=8)
    ax.set_ylabel("No. of Students", fontsize=8)
    ax.set_title("Score Distribution", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.3)
    return fig


def _component_bar_chart(component_df):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    ax.bar(component_df["Component"], component_df["Avg Score"], color="#27ae60")
    ax.set_ylabel("Average Score", fontsize=8)
    ax.set_title("Average Score by Component", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.3)
    return fig


def _safe_boxplot(ax, data, labels):
    """Compatible with both old (`labels=`) and new (`tick_labels=`) matplotlib APIs."""
    try:
        ax.boxplot(data, tick_labels=labels)
    except TypeError:
        ax.boxplot(data, labels=labels)


def _box_plot_chart(df, score_cols: dict, total_col):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    labels, data = [], []
    for label, col in score_cols.items():
        if col and col in df.columns:
            labels.append(label)
            data.append(df[col].dropna())
    if total_col in df.columns:
        labels.append("Total")
        data.append(df[total_col].dropna())
    if not data:
        ax.text(0.5, 0.5, "No data", ha="center")
    else:
        _safe_boxplot(ax, data, labels)
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", alpha=0.3)
    return fig


def _scatter_chart(df, x_col, y_col, x_label, y_label):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    sub = df[[x_col, y_col]].dropna()
    ax.scatter(sub[x_col], sub[y_col], alpha=0.7, color="#8e44ad", s=18)
    ax.set_xlabel(x_label, fontsize=8)
    ax.set_ylabel(y_label, fontsize=8)
    ax.set_title(f"{x_label} vs {y_label}", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)
    return fig


def _heatmap_chart(corr_df):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE_SQUARE)
    im = ax.imshow(corr_df.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_df.columns)))
    ax.set_yticks(range(len(corr_df.columns)))
    ax.set_xticklabels(corr_df.columns, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(corr_df.columns, fontsize=7)
    for i in range(len(corr_df.columns)):
        for j in range(len(corr_df.columns)):
            ax.text(j, i, corr_df.values[i, j], ha="center", va="center", fontsize=7)
    ax.set_title("Correlation Heatmap", fontsize=10)
    fig.colorbar(im, ax=ax, shrink=0.8)
    return fig


def _trend_line_chart(trend_df):
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    ax.plot(trend_df["Assessment"], trend_df["Class Average"], marker="o", color="#e67e22")
    ax.set_ylabel("Class Average", fontsize=8)
    ax.set_title("Performance Trend Over Time", fontsize=10)
    ax.tick_params(labelsize=7, axis="x", rotation=30)
    ax.tick_params(labelsize=7, axis="y")
    ax.grid(alpha=0.3)
    return fig


def generate_pdf_report(
    course_name: str,
    stats_df, pass_summary: dict, grade_df, top_df, bottom_df, component_df,
    rank_df=None, consistency_df=None, risk_df=None, corr_df=None,
    trend_df=None, skew_info=None, difficulty_df=None, student_advice_list=None,
    narrative_text: str = "", full_results_df=None, total_col: str = None,
    score_cols: dict = None, ca_col: str = None, exam_col: str = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectionHeader", fontSize=13, spaceAfter=6, spaceBefore=12,
                               textColor=colors.HexColor("#2c3e50"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="SubHeader", fontSize=10.5, spaceAfter=4, spaceBefore=8,
                               textColor=colors.HexColor("#34495e"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Body", fontSize=9.5, leading=13))
    styles.add(ParagraphStyle(name="BulletItem", fontSize=9.5, leading=13, leftIndent=10))

    story = []

    story.append(Paragraph("Student Performance Report", styles["Title"]))
    story.append(Paragraph(f"Course: {course_name}", styles["Heading2"]))
    story.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Objectives: analyze overall performance, identify patterns/strengths/weaknesses, "
        "provide actionable insights, and recommend suitable visualizations for each finding.",
        styles["Body"]
    ))
    story.append(Spacer(1, 0.5 * cm))

    # 1. Overall Performance
    story.append(Paragraph("1. Overall Performance", styles["SectionHeader"]))
    summary_line = (
        f"Total students: {pass_summary.get('total_students')} | "
        f"Passed: {pass_summary.get('passed')} | "
        f"Failed: {pass_summary.get('failed')} | "
        f"Pass rate: {pass_summary.get('pass_rate')}%"
    )
    story.append(Paragraph(summary_line, styles["Body"]))
    story.append(Spacer(1, 0.2 * cm))
    if stats_df is not None and not stats_df.empty:
        story.append(_df_to_table(stats_df))
        story.append(Spacer(1, 0.3 * cm))
    row_imgs = [_fig_to_image(_pass_fail_pie_chart(pass_summary), width=PDF_IMG_WIDTH_SMALL)]
    if grade_df is not None and not grade_df.empty:
        row_imgs.append(_fig_to_image(_grade_pie_chart(grade_df), width=PDF_IMG_WIDTH_SMALL))
    img_table = Table([row_imgs])
    img_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(img_table)
    story.append(Spacer(1, 0.2 * cm))
    if grade_df is not None and not grade_df.empty:
        story.append(_df_to_table(grade_df))
    story.append(_fig_to_image(_score_hist_chart(full_results_df, total_col)))
    story.append(Spacer(1, 0.3 * cm))

    # 2. Student-Level Insights
    story.append(Paragraph("2. Student-Level Insights", styles["SectionHeader"]))
    if top_df is not None and not top_df.empty:
        story.append(Paragraph("Top Performers", styles["SubHeader"]))
        story.append(_df_to_table(top_df))
    if bottom_df is not None and not bottom_df.empty:
        story.append(Paragraph("Students Who May Need Support", styles["SubHeader"]))
        story.append(_df_to_table(bottom_df))
    if rank_df is not None and not rank_df.empty:
        story.append(Paragraph("Deviation from Class Average (sample)", styles["SubHeader"]))
        sample = rank_df.head(10)
        story.append(_df_to_table(sample))
    story.append(Spacer(1, 0.3 * cm))

    # 3. Assessment Breakdown
    if component_df is not None and not component_df.empty:
        story.append(Paragraph("3. Assessment Breakdown", styles["SectionHeader"]))
        story.append(_df_to_table(component_df))
        story.append(_fig_to_image(_component_bar_chart(component_df)))
        if score_cols and total_col and full_results_df is not None:
            story.append(_fig_to_image(_box_plot_chart(full_results_df, score_cols, total_col)))
        if consistency_df is not None and not consistency_df.empty:
            story.append(Paragraph("Inconsistent Performers (CA vs Exam)", styles["SubHeader"]))
            story.append(_df_to_table(consistency_df))
        story.append(Spacer(1, 0.3 * cm))

    # 4. Correlation Analysis
    if corr_df is not None and not corr_df.empty:
        story.append(Paragraph("4. Correlation Analysis", styles["SectionHeader"]))
        story.append(_df_to_table(corr_df.reset_index().rename(columns={"index": ""})))
        story.append(_fig_to_image(_heatmap_chart(corr_df), width=PDF_IMG_WIDTH_SMALL))
        if ca_col and exam_col and full_results_df is not None and ca_col in full_results_df.columns and exam_col in full_results_df.columns:
            story.append(_fig_to_image(_scatter_chart(full_results_df, ca_col, exam_col, "CA", "Exam")))
        story.append(Spacer(1, 0.3 * cm))

    # 5. Risk & Intervention Analysis
    story.append(Paragraph("5. Risk & Intervention Analysis", styles["SectionHeader"]))
    if risk_df is not None and not risk_df.empty:
        story.append(_df_to_table(risk_df))
    else:
        story.append(Paragraph("No students currently fall below the borderline threshold.", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))

    # 6. Trends & Patterns
    story.append(Paragraph("6. Trends & Patterns", styles["SectionHeader"]))
    if trend_df is not None and not trend_df.empty:
        story.append(_df_to_table(trend_df))
        story.append(_fig_to_image(_trend_line_chart(trend_df)))
    else:
        story.append(Paragraph(
            "Not applicable — this dataset represents a single assessment period. "
            "Trend analysis requires multiple time points (e.g. CA1, CA2, CA3).",
            styles["Body"]
        ))
    story.append(Spacer(1, 0.3 * cm))

    # 7. Insights for Lecturer
    story.append(Paragraph("7. Insights for Lecturer", styles["SectionHeader"]))
    if skew_info:
        story.append(Paragraph(f"Grading skew: {skew_info.get('skew')}", styles["BulletItem"]))
        story.append(Paragraph(skew_info.get("interpretation", ""), styles["Body"]))
    if difficulty_df is not None and not difficulty_df.empty:
        story.append(Paragraph("Assessment Difficulty (avg % of max mark achieved)", styles["SubHeader"]))
        story.append(_df_to_table(difficulty_df))
    story.append(Spacer(1, 0.3 * cm))

    # 8. Insights for Students
    story.append(Paragraph("8. Insights for Students", styles["SectionHeader"]))
    if student_advice_list:
        for tip in student_advice_list:
            story.append(Paragraph(f"• {tip}", styles["BulletItem"]))
    story.append(Spacer(1, 0.3 * cm))

    # AI Narrative
    story.append(PageBreak())
    story.append(Paragraph("Detailed AI-Generated Analysis", styles["SectionHeader"]))
    for para in (narrative_text or "No AI analysis was generated for this report.").split("\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["Body"]))
            story.append(Spacer(1, 0.12 * cm))

    if full_results_df is not None:
        story.append(PageBreak())
        story.append(Paragraph("Full Student Results", styles["SectionHeader"]))
        story.append(_df_to_table(full_results_df.fillna("")))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
