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
OPENAI_API_KEY = None
try:
    GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
except Exception:
    GROQ_API_KEY = None
if not GROQ_API_KEY:
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# OpenAI key (fallback)
try:
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
except Exception:
    OPENAI_API_KEY = None
if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not GROQ_API_KEY and not OPENAI_API_KEY:
    st.warning("No LLM API key found. Please add GROQ_API_KEY or OPENAI_API_KEY to Streamlit secrets or set as environment variable.")

# Default model - check Groq console for available models and limits
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# OpenAI default
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


def generate_with_groq(prompt, model=DEFAULT_GROQ_MODEL, max_tokens=1500, temperature=0.2, timeout=60, retries=3):
    """
    Try Groq first (if key present), otherwise fallback to OpenAI (if key present).
    Returns the assistant content string or empty string on failure.
    """
    def call_groq():
        if not GROQ_API_KEY:
            return None, "no-groq-key"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        # Groq API does not support temperature parameter - remove it
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that strictly follows instructions."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens
        }
        delay = 1
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data.get("choices", [])[0].get("message", {}).get("content", "").strip(), None
            except requests.exceptions.RequestException as e:
                if attempt == retries:
                    return None, str(e)
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                return None, str(e)
        return None, "unknown-groq-error"

    def call_openai():
        if not OPENAI_API_KEY:
            return None, "no-openai-key"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": DEFAULT_OPENAI_MODEL,
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
                resp = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data.get("choices", [])[0].get("message", {}).get("content", "").strip(), None
            except requests.exceptions.RequestException as e:
                if attempt == retries:
                    return None, str(e)
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                return None, str(e)
        return None, "unknown-openai-error"

    # Try Groq first
    groq_resp, groq_err = call_groq()
    if groq_resp:
        return groq_resp

    # If Groq missing or failed, try OpenAI
    openai_resp, openai_err = call_openai()
    if openai_resp:
        return openai_resp

    # If both failed, show best error
    err_msg = groq_err if groq_err and groq_err != "no-groq-key" else openai_err
    if err_msg:
        st.error(f"LLM provider error: {err_msg}")
    else:
        st.error("No LLM provider available.")
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
    summary = generate_with_groq(summary_prompt, max_tokens=800)
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

    candidate_name = generate_with_groq(name_prompt, max_tokens=60)
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
        report = generate_with_groq(prompt, model=DEFAULT_GROQ_MODEL, max_tokens=2000)

    if not report:
        st.error("Failed to generate report from LLM providers.")
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
