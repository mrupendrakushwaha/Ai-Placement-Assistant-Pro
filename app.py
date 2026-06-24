import streamlit as st
import pdfplumber
import requests
import time
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="AI Placement Assistant Pro", page_icon="🎯", layout="wide")

st.title("🎯 AI Placement Assistant Pro")
st.write("Upload Resume PDF and get a professional placement report.")

# Prefer secret from Streamlit secrets, fall back to environment variable
GROQ_API_KEY = None
try:
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
except Exception:
    GROQ_API_KEY = None
if not GROQ_API_KEY:
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.warning("GROQ_API_KEY not found. Please add GROQ_API_KEY to Streamlit secrets or set as environment variable.")

# Default model - check Groq console for available models and limits
DEFAULT_GROQ_MODEL = "llama3-70b-8192"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_with_groq(prompt, model=DEFAULT_GROQ_MODEL, max_tokens=1500, temperature=0.2, timeout=60, retries=3):
    """
    Simple helper to call Groq's OpenAI-compatible chat completions endpoint.
    Falls back gracefully and retries on transient errors (like 429).
    """
    if not GROQ_API_KEY:
        return ""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that strictly follows instructions."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    delay = 1
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 429:
                # rate limited - backoff
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            # OpenAI-compatible response shape used by Groq
            return data.get("choices", [])[0].get("message", {}).get("content", "").strip()
        except requests.exceptions.RequestException as e:
            # on last attempt, show error
            if attempt == retries:
                st.error(f"API request failed: {e}")
                return ""
            time.sleep(delay)
            delay *= 2
        except Exception as e:
            st.error(f"Failed to parse response: {e}")
            return ""

    return ""


uploaded_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
github_username = st.text_input("GitHub Username")


def extract_text_from_pdf(uploaded_file):
    text = ""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    text += txt + "\n"
    except Exception as e:
        st.error(f"Failed to read PDF: {e}")
    return text


# If resume is very large, we summarize first to stay within token limits

def summarize_resume_if_needed(resume_text, token_threshold=3500):
    # crude token estimate: 1 token ~ 4 chars
    est_tokens = max(1, len(resume_text) // 4)
    if est_tokens <= token_threshold:
        return resume_text

    summary_prompt = (
        "Summarize the following resume keeping only the key points (education, skills, experience, projects) "
        "in concise bullet points so it can be used for further analysis:\n\n"
        f"{resume_text}"
    )
    summary = generate_with_groq(summary_prompt, max_tokens=800, temperature=0.1)
    if summary:
        return summary
    return resume_text[:token_threshold * 4]


if uploaded_file and st.button("Analyze Resume"):
    resume_text = extract_text_from_pdf(uploaded_file)
    if not resume_text:
        st.error("Could not extract text from the uploaded PDF. Please try a different file.")
        st.stop()

    # Extract candidate name from the top of the resume
    name_prompt = f"""From this resume, extract ONLY the candidate's full name from the top of the resume.\nReturn only the name, nothing else.\n\nResume:\n{resume_text[:1000]}\n"""

    candidate_name = generate_with_groq(name_prompt, max_tokens=60, temperature=0.0)
    candidate_name = candidate_name.strip() if candidate_name else "Candidate"

    # Fetch GitHub stats (best-effort)
    repos_count, followers, following = 0, 0, 0
    if github_username:
        try:
            user = requests.get(f"https://api.github.com/users/{github_username}").json()
            repos_count = user.get("public_repos", 0)
            followers = user.get("followers", 0)
            following = user.get("following", 0)
        except Exception:
            pass

    # Make resume concise if needed before sending to model
    short_resume = summarize_resume_if_needed(resume_text)

    prompt = f"""
Analyze this resume and GitHub profile.

Resume:
{short_resume}

GitHub:
{github_username}

GitHub Stats:
Repos: {repos_count}
Followers: {followers}
Following: {following}

Create a professional report.
Use bold headings.
Add Reasoning section.
Use bullet points only.
No paragraphs.
Sections:
ATS Score, GitHub Score, Placement Readiness,
Top 5 Strengths, Top 5 Missing Skills,
Expected Package, Interview Readiness,
Top 10 HR Questions, Top 10 AI/ML Questions,
3 Month Roadmap.
IMPORTANT:

Do not use markdown.
Do not use **.
Do not use #.
Max Output 4 Page

Format:

ATS Score

Score:
7/10

Reasoning:
• Point 1
• Point 2
• Point 3

GitHub Score

Score:
2/10

Reasoning:
• Point 1
• Point 2

Top 5 Strengths

• Strength 1
• Strength 2

Top 5 Missing Skills

• Skill 1
• Skill 2
"""

    with st.spinner("Analyzing..."):
        # adjust max_tokens based on how long you expect the result to be
        report = generate_with_groq(prompt, model=DEFAULT_GROQ_MODEL, max_tokens=2000, temperature=0.1)

    if not report:
        st.error("Failed to generate report from Groq API.")
        st.stop()

    st.subheader("📊 Professional Placement Report")
    st.markdown(report)

    pdf_file = "AI_Placement_Report.pdf"

    pdf = SimpleDocTemplate(pdf_file)

    styles = getSampleStyleSheet()

    story = []

    # Title
    story.append(
        Paragraph(
            "<font color='darkblue'><b>AI Placement Assistant Pro</b></font>",
            styles["Title"]
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "<b>Professional Placement Analysis Report</b>",
            styles["Heading2"]
        )
    )

    story.append(Spacer(1, 15))

    story.append(
        Paragraph(
            f"<b>Candidate Name:</b> {candidate_name}<br/>"
            f"<b>GitHub Username:</b> {github_username}",
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 15))

    # Clean Report
    report_clean = report.replace("**", "")
    report_clean = report_clean.replace("* ", "• ")
    report_clean = report_clean.replace("*", "")

    sections = [
        "ATS Score",
        "GitHub Score",
        "Placement Readiness",
        "Top 5 Strengths",
        "Top 5 Missing Skills",
        "Expected Package",
        "Interview Readiness",
        "Top 10 HR Questions",
        "Top 10 AI/ML Questions",
        "3 Month Roadmap"
    ]

    for line in report_clean.split("\n"):

        line = line.strip()

        if not line:
            story.append(Spacer(1, 4))
            continue

        # Main Headings
        if any(line.startswith(sec) for sec in sections):

            story.append(Spacer(1, 8))

            story.append(
                Paragraph(
                    f"<font color='blue'><b>{line}</b></font>",
                    styles["Heading2"]
                )
            )

        # Sub Headings
        elif line.endswith(":"):

            story.append(
                Paragraph(
                    f"<b>{line}</b>",
                    styles["Heading3"]
                )
            )

        # Bullet Points
        elif line.startswith("•"):

            story.append(
                Paragraph(
                    f"&#8226; {line[1:].strip()}",
                    styles["BodyText"]
                )
            )

        else:

            story.append(
                Paragraph(
                    line,
                    styles["BodyText"]
                )
            )

    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "<font color='darkblue'><b>Created by Mr. Upendra Kushwaha</b></font>",
            styles["Heading3"]
        )
    )

    pdf.build(story)

    with open(pdf_file, "rb") as f:
        st.download_button("📥 Download PDF Report", f, "AI_Placement_Report.pdf", "application/pdf")
