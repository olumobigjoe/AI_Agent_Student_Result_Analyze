# 📊 Student Results Analyzer — AI Edition (Powered by Ollama)

A Streamlit web app that lets course lecturers upload student results (CSV/Excel), get a full statistical performance analysis, and receive a **locally-generated AI narrative** — written by a local LLM via [Ollama](https://ollama.com) — summarizing class performance and recommending next steps. Everything compiles into one downloadable PDF report.

No cloud AI calls. No API keys. No student data ever leaves your machine.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![Ollama](https://img.shields.io/badge/AI-Ollama%20%2F%20Llama%203.2-purple)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **Flexible file upload** — accepts `.csv`, `.xlsx`, and `.xls`
- **Two grading layouts supported** — CA + Practical + Exam + Total, or CA + Exam + Total
- **Smart column detection** — auto-detects Name, CA, Practical, Exam, Total, and Course columns
- **Multi-course support** — filter one file down to a single course if it holds several
- **Full statistical breakdown** — mean, median, std dev, min/max, pass/fail rate, grade distribution, correlations, top/bottom performers, component contribution
- **🤖 AI-generated narrative analysis** — a local model (default `llama3.2:1b`) reads the computed stats and writes a professional, human-readable summary with strengths, weaknesses, and recommendations — fully offline, fully private
- **One-click PDF report** — every chart, table, and the AI narrative compiled into a polished, shareable PDF

## 🧠 Why local AI (Ollama) instead of a cloud API?

- **Privacy** — student performance data never leaves the lecturer's machine or institution network
- **Zero cost per report** — no per-token API billing
- **Works offline** — once the model is pulled, no internet connection is required to generate analysis
- **Swappable** — drop in any Ollama model (`llama3.2:1b`, `llama3.1`, `mistral`, etc.) depending on the hardware available

## 🖥️ How it works

1. Upload a results file (a `sample_data.csv` is included to try it instantly)
2. Confirm the auto-detected column mapping
3. Review the generated stats, charts, and top/bottom performers
4. Click **"Generate AI Analysis"** — the app sends only the summary statistics (never raw student rows) to your local Ollama model
5. Click **"Generate PDF Report"** and download the finished report

## 🚀 Getting Started

### 1. Install and start Ollama (one-time)
```bash
# Install from https://ollama.com/download
ollama pull llama3.2:1b
ollama serve
```

### 2. Clone the repo and install dependencies
```bash
git clone https://github.com/<your-username>/student-results-analyzer-ai.git
cd student-results-analyzer-ai
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## 📂 Project Structure
```
student_analyzer/
├── app.py                  # Streamlit app (UI + orchestration)
├── requirements.txt
├── sample_data.csv          # Example dataset to try the app with
└── modules/
    ├── data_utils.py        # File loading + column auto-detection
    ├── analysis_utils.py    # Stats, grading, correlations
    ├── ollama_utils.py      # Prompt building + Ollama API calls
    └── pdf_utils.py         # PDF report generation (ReportLab)
```

## 📋 Expected Column Names

| Role | Recognized header examples |
|---|---|
| Name/ID | `Student Name`, `Name`, `Matric No`, `Student ID` |
| Course (optional) | `Course`, `Course Code`, `Subject` |
| CA | `CA Score`, `CA`, `Continuous Assessment` |
| Practical (optional) | `Practical Score`, `Practical`, `Lab Score` |
| Exam | `Exam Score`, `Exam`, `Final Exam` |
| Total (optional) | `Total`, `Grand Total` — computed automatically if missing |

## ⚠️ Deployment Note

Streamlit Community Cloud cannot run Ollama alongside the app (no persistent background processes). Options:
1. **Run both locally** on the lecturer's machine or a campus server (simplest, default setup)
2. **Point at a remote Ollama server** — set the "Ollama host" field in the sidebar to a server you control running Ollama, e.g. `http://your-server-ip:11434`

Everything except the AI-narrative button works fine on Streamlit Cloud on its own.

## 🛠️ Built With
- [Streamlit](https://streamlit.io/) — web app framework
- [Ollama](https://ollama.com/) + [Llama 3.2](https://ai.meta.com/llama/) — local AI narrative generation
- [pandas](https://pandas.pydata.org/) / [NumPy](https://numpy.org/) — data processing
- [Matplotlib](https://matplotlib.org/) — charts
- [ReportLab](https://www.reportlab.com/) — PDF generation

## 🗺️ Roadmap Ideas
- [ ] Batch AI-narrated reports across all courses in one upload
- [ ] Semester-over-semester trend tracking
- [ ] Model picker in the UI (swap `llama3.2:1b` for larger local models)
- [ ] Export to Excel in addition to PDF

## 🤝 Contributing
Issues and pull requests are welcome — open an issue first to discuss any significant changes.

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
