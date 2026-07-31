"""
ollama_utils.py
Talks to a running Ollama server to generate a structured narrative analysis
of a student results dataset using a local model (e.g. llama3.2:1b).
"""

import requests


def build_prompt(course_name: str, sections: dict) -> str:
    """
    sections: a dict of pre-formatted text blocks keyed by section name,
    e.g. {"overall": "...", "student_level": "...", ...}. Missing/empty
    keys are simply omitted from the prompt.
    """

    def block(title, key):
        content = sections.get(key)
        if not content:
            return ""
        return f"\n{title}:\n{content}\n"

    prompt = f"""You are an academic data analyst helping a course lecturer understand their
students' performance in "{course_name}".

Your objectives:
1. Analyze overall student performance.
2. Identify patterns, strengths, and weaknesses.
3. Provide actionable insights for improving learning outcomes.
4. Note which visualization best supports each finding (histogram, bar chart,
   pie chart, scatter plot, box plot, heatmap, or line chart — these charts
   are already shown to the lecturer alongside your analysis).

Base your analysis strictly on the data given below — do not invent numbers.
Organize your response with clear headings and bullet points, and include
interpretation, not just numbers. Make recommendations practical and specific.

{block("1. OVERALL PERFORMANCE (mean, median, mode, std dev, pass/fail, grade bands)", "overall")}
{block("2. STUDENT-LEVEL INSIGHTS (ranking, top/struggling students, deviation from average)", "student_level")}
{block("3. ASSESSMENT BREAKDOWN (CA vs Exam comparison, inconsistent performers)", "assessment_breakdown")}
{block("4. CORRELATION ANALYSIS (relationships between components)", "correlation")}
{block("5. RISK & INTERVENTION ANALYSIS (at-risk / borderline students)", "risk")}
{block("6. TRENDS & PATTERNS (only if multiple assessments over time exist)", "trends")}
{block("7. INSIGHTS FOR LECTURER (assessment difficulty, grading skew)", "lecturer")}

Write your response in these sections, in this order:
- Overall Performance
- Student-Level Insights
- Assessment Breakdown
- Correlation Analysis
- Risk & Intervention Analysis
- Trends & Patterns (only include if trend data was provided above; otherwise skip it)
- Insights for Lecturer
- Insights for Students

Keep each section concise (3-6 bullet points), professional, and specific to the numbers given."""
    return prompt


def generate_analysis(prompt: str, model: str = "llama3.2:1b", host: str = "http://localhost:11434",
                       timeout: int = 180, num_predict: int = 1024) -> str:
    """
    Sends a prompt to the Ollama /api/generate endpoint and returns the generated text.
    Raises a RuntimeError with a helpful message if Ollama isn't reachable.
    """
    url = f"{host.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict},
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to Ollama at {host}. Make sure Ollama is running "
            f"('ollama serve') and that the model '{model}' is pulled "
            f"('ollama pull {model}')."
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            "Ollama took too long to respond. Try a smaller dataset summary, "
            "a smaller model, or increase the timeout."
        ) from e
    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}") from e
