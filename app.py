import re
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

# Approximate maximum characters to include in PDF to keep it within ~4 pages.
# Adjust this constant if you need slightly more or less content.
MAX_PDF_CHARS = 14000


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


if uploaded_file and st.button("Analyze Resume"):
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

    # Prepare PDF with A4 size and margins; render headings bold and limit output roughly to 4 pages
    pdf_file = "AI_Placement_Report.pdf"
    pdf_doc = SimpleDocTemplate(pdf_file, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    body_style = styles["BodyText"]

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles.get("Heading2", body_style),
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceBefore=8,
        spaceAfter=4,
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

    # Truncate report to MAX_PDF_CHARS to keep PDF within ~4 pages
    if len(report) > MAX_PDF_CHARS:
        cut_at = report.rfind('\n', 0, MAX_PDF_CHARS)
        if cut_at == -1:
            truncated_report = report[:MAX_PDF_CHARS]
        else:
            truncated_report = report[:cut_at]
        truncated_report += "\n\n[Output truncated to fit in PDF]"
    else:
        truncated_report = report

    # Convert lines to Paragraphs. Detect headings and make them bold.
    for raw_line in truncated_report.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        html_line = md_to_reportlab_html(line)
        # Remove tags for plain check
        plain_for_check = re.sub(r"<.*?>", "", html_line).strip()
        # Decide if this is a heading: ends with ':' or fully bold
        if plain_for_check.endswith(":") or (html_line.startswith("<b>") and html_line.endswith("</b>")):
            if not html_line.startswith("<b>"):
                html_line = f"<b>{html_line}</b>"
            story.append(Paragraph(html_line, heading_style))
        else:
            if html_line.startswith(u'• '):
                story.append(Paragraph(html_line, bullet_style))
            else:
                story.append(Paragraph(html_line, body_style))

    pdf_doc.build(story)

    with open(pdf_file, "rb") as f:
        st.download_button("📥 Download PDF Report", f, "AI_Placement_Report.pdf", "application/pdf")
