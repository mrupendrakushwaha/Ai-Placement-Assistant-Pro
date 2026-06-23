import streamlit as st
import pdfplumber
import requests
import re
from groq import Groq
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

st.set_page_config(page_title="AI Placement Assistant Pro", page_icon="🎯", layout="wide")

st.markdown(
    "<h1 style='text-align:center;'>🎯 AI Placement Assistant Pro</h1>",
    unsafe_allow_html=True
)
st.write("Upload Resume PDF and get a professional placement report.")

# Initialize Groq client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

uploaded_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
github_username = st.text_input("GitHub Username")

if uploaded_file and st.button("🚀Analyze Resume🚀"):
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
- Use bold headings and colour blue
- Use bullet points
- No paragraphs
- Each reason on separate line
- Add blank line after every section
- Professional PDF format
- Do not use ** symbols.
- Format headings like: ATS Score (without brackets)
"""

    with st.spinner("Analyzing..."):
        try:
            chat_completion = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2048
            )
            report = chat_completion.choices[0].message.content
            report = report.replace("* ", "\n• ")
            
            # Remove bold markdown formatting
            report = re.sub(r"\*\*(.*?)\*\*", r"\1", report)
            
            # Remove extra stars
            report = report.replace("*", "")
        except Exception as e:
            st.error(f"❌ Error generating report: {str(e)}")
            st.stop()

    st.subheader("📊 Professional Placement Report")
    st.markdown(report)

    # PDF GENERATION
    pdf_file = "AI_Placement_Report.pdf"
    pdf = SimpleDocTemplate(pdf_file)
    styles = getSampleStyleSheet()
    
    # Custom styles banayein
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#0066CC',  # Blue color
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    story = []

    story.append(
        Paragraph(
            "<b>AI Placement Assistant Pro</b>",
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

    for line in report.split("\n"):
        line = line.strip()

        if not line:
            story.append(Spacer(1, 8))
            continue

        # Headings detect karo - headings mein typically "Score", "Skills", "Readiness", etc ho
        is_heading = (
            "Score" in line or 
            "Strengths" in line or 
            "Skills" in line or 
            "Package" in line or 
            "Readiness" in line or 
            "Questions" in line or 
            "Roadmap" in line or
            "Reasoning" in line or
            line.isupper()
        )

        # Bullet points
        if line.startswith("•"):
            story.append(
                Paragraph(
                    line,
                    styles["BodyText"]
                )
            )

        # Headings ko bold aur blue banao
        elif is_heading:
            story.append(
                Paragraph(
                    f"<b><font color='#0066CC'>{line}</font></b>",
                    heading_style
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
