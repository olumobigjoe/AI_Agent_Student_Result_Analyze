# Student Results Analyzer

A Streamlit app for course lecturers to upload student results (CSV/Excel),
get an automatic statistical + AI-written performance analysis (via a local
Ollama model), and download a full PDF report.

## Features
- Upload CSV or Excel (.csv, .xlsx, .xls)
- Works with either **CA + Practical + Exam + Total** or **CA + Exam + Total**
  (auto-detects columns, lets you fix the mapping if it guesses wrong)
- Optional "Course" and "Attendance" columns — filter to one course, and fold
  attendance into the correlation analysis if present
- Full **8-section analysis framework**:
  1. **Overall Performance** — mean, median, mode, std dev, pass/fail rate, grade bands
  2. **Student-Level Insights** — full ranking, top/bottom performers, deviation from class average
  3. **Assessment Breakdown** — CA vs Exam comparison, box plot of spread/outliers, flags inconsistent performers (high CA/low exam or vice versa) using z-scores
  4. **Correlation Analysis** — correlation matrix, heatmap, CA-vs-Exam scatter plot, strongest predictor of the total
  5. **Risk & Intervention Analysis** — flags failing/borderline students with suggested interventions
  6. **Trends & Patterns** — auto-detects repeated assessment columns (e.g. CA1/CA2/CA3) and plots a trend line; clearly states "not applicable" otherwise
  7. **Insights for Lecturer** — grading skew interpretation, per-component difficulty (% of max mark achieved)
  8. **Insights for Students** — plain-language, data-derived advice on what most affects the final grade
- Sends all of the above to a local **Ollama** model (`llama3.2:1b` by
  default) to generate a written narrative analysis organized into the same
  8 sections
- Moderate, consistently-sized charts (both on-screen and in the PDF —
  nothing oversized)
- One-click **PDF report** download combining every section's charts,
  tables, and the narrative

## 1. Install Ollama and the model (one-time, on the machine that will run the app)

```bash
# Install Ollama: https://ollama.com/download
ollama pull llama3.2:1b
ollama serve      # starts the Ollama server on http://localhost:11434
```

## 2. Install Python dependencies

```bash
cd student_analyzer
pip install -r requirements.txt
```

## 3. Run the app

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## 4. Using the app
1. Upload your CSV/Excel file (there's a `sample_data.csv` included to try it out).
2. Confirm/correct the column mapping (name, CA, practical, exam, total, course).
3. If your file has multiple courses in one sheet, pick the course to filter to.
4. Review the stats, charts, top/bottom performers.
5. Click **"Generate AI Analysis"** for the written narrative.
6. Click **"Generate PDF Report"** and download it.

## Expected file format
Any of these column naming styles are auto-detected (case-insensitive, partial match):

| Role      | Recognized header examples                          |
|-----------|-------------------------------------------------------|
| Name/ID   | "Student Name", "Name", "Matric No", "Student ID"    |
| Course    | "Course", "Course Code", "Subject"                    |
| CA        | "CA Score", "CA", "Continuous Assessment"             |
| Practical | "Practical Score", "Practical", "Lab Score" (optional)|
| Exam      | "Exam Score", "Exam", "Final Exam"                    |
| Total     | "Total", "Grand Total" (computed automatically if missing) |

If a Total column isn't present, it's computed as CA + Practical + Exam
(whichever of those are present).

## ⚠️ Important: deploying to Streamlit Community Cloud
Streamlit Community Cloud only hosts the Streamlit app itself — it cannot run
Ollama alongside it (no persistent background processes, no GPU/model
storage). Your options:

1. **Run everything locally / on your own server or campus machine**: install
   Ollama + this app on the same machine (or same private network) — this is
   the simplest and free option, and is what this app is set up for by default.
2. **Point at a remote Ollama server**: run Ollama on a VM/server you control
   (with a public or VPN-restricted address), then in the app's sidebar set
   "Ollama host" to that server's URL, e.g. `http://your-server-ip:11434`.
   Make sure the port is firewalled to only your app's IP if it's public.
3. The rest of the app (upload, stats, charts, PDF export) works fine on
   Streamlit Cloud on its own — only the "Generate AI Analysis" button needs
   Ollama to be reachable. Everything else will still work even if Ollama is
   unreachable; you'll just see an error for that one button.

## Project structure
```
student_analyzer/
├── app.py                  # Streamlit app (UI + orchestration)
├── requirements.txt
├── sample_data.csv         # Example file to try the app with
└── modules/
    ├── data_utils.py       # File loading + column auto-detection
    ├── analysis_utils.py   # Stats, grading, correlations
    ├── ollama_utils.py     # Prompt building + Ollama API calls
    └── pdf_utils.py        # PDF report generation (reportlab)
```

## Customization ideas
- Change default grade boundaries/pass mark in the sidebar (persists per session)
- Swap `llama3.2:1b` for a larger local model if your machine can handle it —
  bigger models generally give richer, more nuanced narrative analysis
- Add a "compile all courses into one PDF" loop in `app.py` if a single file
  covers many courses and you want one combined report per semester
