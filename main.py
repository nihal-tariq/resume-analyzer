import os
import streamlit as st
import pdfplumber
import docx
from dotenv import load_dotenv
from fpdf import FPDF
from io import BytesIO
from groq import Groq
from pathlib import Path
import re
import unicodedata

# Load API key
load_dotenv(dotenv_path=Path('.') / '.env')
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="AI Resume Assistant", layout="centered")

# ----------------------------- FILE PROCESSING ----------------------------- #

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def generate_pdf(content):
    # Normalize to ASCII: remove fancy quotes, dashes, etc.
    content_ascii = unicodedata.normalize('NFKD', content).encode('ascii', 'ignore').decode('ascii')

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in content_ascii.split('\n'):
        pdf.multi_cell(0, 10, line)

    pdf_output = pdf.output(dest='S').encode('latin1')
    return BytesIO(pdf_output)

# ----------------------------- PROMPT FUNCTIONS ----------------------------- #

def get_resume_analysis_prompt(resume_text, job_description):
    return f"""
You are a professional resume reviewer. Analyze the resume below and:
1. Suggest specific improvements (format, content, clarity).
2. Provide a match rating (0–100) based on the job description.
3. Highlight missing skills or qualifications.

Resume:
{resume_text}

Job Description:
{job_description}
"""

def get_resume_gen_prompt(user_info, job_role):
    return f"""
Create a professional resume based on the following profile, tailored to the job role of {job_role}. 
Use a clean format with sections: Summary, Skills, Experience, and Education.

User Profile:
{user_info}
"""

def call_groq_chat(prompt):
    chat_completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return chat_completion.choices[0].message.content

# ----------------------------- UI: STREAMLIT ----------------------------- #

st.title("🧠 AI Resume Analyzer & Generator")
st.markdown("Enhance your CV or generate one tailored to a job.")

tab1, tab2 = st.tabs(["📄 Analyze Resume", "🛠️ Generate Resume"])

with tab1:
    uploaded_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])
    job_description = st.text_area("Paste the Job Description here")

    if uploaded_file and job_description:
        if st.button("Analyze Now"):
            if uploaded_file.name.endswith(".pdf"):
                resume_text = extract_text_from_pdf(uploaded_file)
            else:
                resume_text = extract_text_from_docx(uploaded_file)

            prompt = get_resume_analysis_prompt(resume_text, job_description)
            with st.spinner("Analyzing your resume..."):
                analysis = call_groq_chat(prompt)

            # Store in session state
            st.session_state.resume_text = resume_text
            st.session_state.job_description = job_description
            st.session_state.analysis = analysis
            st.session_state.chat_history = []

    # Show the results if available in session state
    if "analysis" in st.session_state:
        st.markdown("### 🧾 Review Output")
        st.markdown(st.session_state.analysis)

        match = re.search(r"(\d{1,3})\s?/?100", st.session_state.analysis)
        if match:
            score = int(match.group(1))
            st.progress(score / 100)
            st.success(f"Resume Match Score: {score}/100")

        pdf_buffer = generate_pdf(st.session_state.analysis)
        st.download_button(
            label="📅 Download Feedback as PDF",
            data=pdf_buffer,
            file_name="resume_feedback.pdf",
            mime="application/pdf"
        )

        # --- Chat with LLM ---
        st.markdown("---")
        st.subheader("💬 Chat About Your Resume")

        user_input = st.text_input("Ask anything about your resume:", key="chat_input")
        if st.button("Send", key="send_button"):
            if user_input:
                chat_prompt = f"""
You are a resume expert AI. The user has uploaded the following resume and job description:

Resume:
{st.session_state.resume_text}

Job Description:
{st.session_state.job_description}

Resume Review:
{st.session_state.analysis}

User Question:
{user_input}

Respond with specific and helpful feedback.
"""
                response = call_groq_chat(chat_prompt)
                st.session_state.chat_history.append((user_input, response))

        if "chat_history" in st.session_state:
            for i, (q, a) in enumerate(reversed(st.session_state.chat_history), 1):
                with st.expander(f"Q{i}: {q}"):
                    st.markdown(f"**Bot:** {a}")

# ----------------------------- GENERATE RESUME ----------------------------- #

with tab2:
    st.subheader("Create Your Resume 🧑‍💼")
    name = st.text_input("Full Name")
    email = st.text_input("Email Address")
    phone = st.text_input("Phone Number")
    skills = st.text_area("Skills (comma-separated)")
    experience = st.text_area("Work Experience")
    education = st.text_area("Education")
    job_role = st.text_input("Job Role You're Targeting")

    if st.button("Generate Resume"):
        user_info = f"""
Name: {name}
Email: {email}
Phone: {phone}
Skills: {skills}
Experience: {experience}
Education: {education}
"""
        prompt = get_resume_gen_prompt(user_info, job_role)
        with st.spinner("Generating your resume..."):
            resume_output = call_groq_chat(prompt)

        st.markdown("### ✨ Your Generated Resume")
        st.markdown(resume_output)

        pdf_buffer = generate_pdf(resume_output)
        st.download_button(
            label="📄 Download Resume as PDF",
            data=pdf_buffer,
            file_name="generated_resume.pdf",
            mime="application/pdf"
        )
