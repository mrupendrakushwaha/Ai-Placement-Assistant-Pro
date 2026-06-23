import streamlit as st
import pdfplumber
import requests
import google.generativeai as genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="AI Placement Assistant Pro", page_icon="🎯", layout="wide")

st.title("🎯 AI Placement Assistant Pro")
st.write("Upload Resume PDF and get a professional placement report.")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-lite")

uploaded_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
candidate_name = st.text_input("Candidate Name")
github_username = st.text_input("GitHub Username")

if uploaded_file and st.button("Analyze Resume"):
    resume_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                resume_text += txt + "\n"

    repos_count, followers, following = 0, 0, 0
    try:
        user = requests.get(f"https://api.github.com/users/{github_username}").json()
        repos_count = user.get("public_repos", 0)
        followers = user.get("followers", 0)
        following = user.get("following", 0)
    except:
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
IMPORTANT:

Do not use markdown.
Do not use **.
Do not use #.

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
        report = model.generate_content(prompt).text

    st.subheader("📊 Professional Placement Report")
    st.markdown(report)

    from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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
    report = report.replace("**", "")
    report = report.replace("* ", "• ")
    report = report.replace("*", "")

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

    for line in report.split("\n"):

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
