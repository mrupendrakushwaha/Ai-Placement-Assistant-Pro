import re
import io
import streamlit as st
import pdfplumber
import requests
import google.generativeai as genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4

st.set_page_config(page_title="AI Placement Assistant Pro", page_icon="🎯", layout="wide")

st.title("🎯 AI Placement Assistant Pro")
st.write("Upload Resume PDF and get a professional placement report.")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-lite")

uploaded_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
github_username = st.text_input("GitHub Username")

# Approximate maximum characters to include in PDF to keep it within 4 pages.
# This is an approximation — ReportLab layout depends on fonts, spacing, and content.
MAX_PDF_CHARS = 12000


def md_to_reportlab_html(text_line: str) -> str:
    """Convert simple Markdown in a line to ReportLab-friendly tags.
    - **bold** -> <b>bold</b>
    - `code` -> <font face="Courier">code</font>
    - list markers (-, *, 1.) -> bullet symbol '• '
    """
    # Convert markdown bold **text** to ReportLab bold tags <b>text</b>
    text_line = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text_line)
    # Convert inline code `x` to <font face="Courier">x</font>
    text_line = re.sub(r"`([^`]+?)`", r"<font face=\"Courier\">\1</font>", text_line)
    # Convert starting bullets like "- " or "* " or numbered lists "1. " to a visible bullet character
    text_line = re.sub(r"^\s*(-|\*|\d+\.)\s+", u'• ', text_line)
    return text_line


def split_into_sections(report_text: str):
    """Split report into sections by headings.
    A heading is detected when a line ends with ':' or is fully bold (wrapped in ** or <b>..</b>).
    Returns list of section strings (heading + its lines).
    """
    lines = report_text.splitlines()
    sections = []
    current = []

    def is_heading(line: str) -> bool:
        l = line.strip()
        if not l:
            return False
        # markdown-style bold
        if re.match(r"^\*\*.*\*\*$", l):
            return True
        # ReportLab bold tag
        if l.startswith("<b>") and l.endswith("</b>"):
            return True
        # ends with colon
        if l.endswith(":"):
            return True
        return False

    for line in lines:
        if is_heading(line):
            # start new section
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return sections


if uploaded_file and st.button("Analyze Resume"):
    # Extract text from uploaded resume
    resume_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                resume_text += txt + "\n"

    repos_count, followers, following = 0, 0, 0
    if github_username:
        try:
            user = requests.get(f"https://api.github.com/users/{github_username}").json()
            repos_count = user.get("public_repos", 0)
            followers = user.get("followers", 0)
            following = user.get("following", 0)
        except Exception:
            pass

    prompt = f"""
Analyze this resume and GitHub profile.

Resume:
{resume_text}

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
"""

    with st.spinner("Analyzing..."):
        report = model.generate_content(prompt).text

    st.subheader("📊 Professional Placement Report")
    st.markdown(report)

    # Build PDF in-memory and ensure headings are bold and output is limited to ~4 pages
    pdf_buffer = io.BytesIO()
    pdf_doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    body_style = styles["BodyText"]

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles.get("Heading2", body_style),
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        spaceBefore=8,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        fontSize=10,
        leading=12,
        spaceBefore=2,
        spaceAfter=2,
    )

    story = [Paragraph("AI Placement Assistant Pro", title_style), Spacer(1, 12)]

    # Convert markdown bold to <b>..</b> in the full report to make heading detection easier
    report_for_processing = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", report)

    # Split into logical sections and keep whole sections when truncating
    sections = split_into_sections(report_for_processing)

    accumulated = ""
    truncated = False
    for sec in sections:
        # if adding this section would exceed budget, stop (preserve whole sections)
        if len(accumulated) + len(sec) > MAX_PDF_CHARS:
            truncated = True
            break
        accumulated += sec + "\n\n"

    if not accumulated:
        # fallback: use a truncated prefix of the report
        if len(report_for_processing) > MAX_PDF_CHARS:
            accumulated = report_for_processing[:MAX_PDF_CHARS]
            truncated = True
        else:
            accumulated = report_for_processing

    # Build story from accumulated content
    for raw_line in accumulated.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        html_line = md_to_reportlab_html(line)
        plain_for_check = re.sub(r"<.*?>", "", html_line).strip()
        if plain_for_check.endswith(":") or (html_line.startswith("<b>") and html_line.endswith("</b>")):
            if not html_line.startswith("<b>"):
                html_line = f"<b>{html_line}</b>"
            story.append(Paragraph(html_line, heading_style))
        else:
            if html_line.startswith(u'• '):
                story.append(Paragraph(html_line, bullet_style))
            else:
                story.append(Paragraph(html_line, body_style))

    if truncated:
        story.append(Spacer(1, 8))
        story.append(Paragraph("[Output truncated to fit in 4 pages]", ParagraphStyle("Note", parent=body_style, fontSize=9, leading=11, textColor="grey")))

    pdf_doc.build(story)
    pdf_buffer.seek(0)

    # Provide download
    st.download_button("📥 Download PDF Report", data=pdf_buffer, file_name="AI_Placement_Report.pdf", mime="application/pdf")
