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
- Use bold headings
- Use bullet points
- No paragraphs
- Each reason on separate line
- Add blank line after every section
- Professional PDF format
"""

    with st.spinner("Analyzing..."):
        report = model.generate_content(prompt).text
        report = report.replace("* ", "\n• ")

    st.subheader("📊 Professional Placement Report")
    st.markdown(report)

    # PDF GENERATION
    pdf_file = "AI_Placement_Report.pdf"
    pdf = SimpleDocTemplate(pdf_file)
    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            "AI Placement Assistant Pro",
            styles["Title"]
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Professional Placement Analysis Report",
            styles["Heading2"]
        )
    )
    story.append(Spacer(1, 10))

    for line in report.split("\n"):
        line = line.strip()

        if not line:
            continue

        # Bold Headings
        if "**" in line:
            title = line.replace("**", "")
            story.append(
                Paragraph(
                    f"<b>{title}</b>",
                    styles["Heading2"]
                )
            )
            story.append(Spacer(1, 5))

        # Bullet Points
        elif line.startswith("•"):
            story.append(
                Paragraph(
                    line,
                    styles["BodyText"]
                )
            )

        # Normal Text
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
            "<b>Created by Mr. Upendra Kushwaha</b>",
            styles["Heading3"]
        )
    )

    pdf.build(story)

    with open(pdf_file, "rb") as pdf_download:
        st.download_button(
            "📥 Download PDF Report",
            data=pdf_download,
            file_name="AI_Placement_Report.pdf",
            mime="application/pdf"
        )
