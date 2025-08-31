# app.py
# -----------------------------
# Simplified Law Summarizer (Gemini API Version, Structured Points + Glossary)
# - Input: manual text OR PDF upload
# - Process: send to Gemini generative AI for structured summary
# - Output: bullet point summary + glossary + copy + download PDF
# - UI: Streamlit
#
# Run:
#   pip install -r requirements.txt
#   streamlit run app.py
# -----------------------------

import io
import os
import re
import streamlit as st
from dotenv import load_dotenv
import requests
from PyPDF2 import PdfReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

# -----------------------------
# Load environment variables / secrets
# -----------------------------
load_dotenv()

# Try Streamlit Secrets first, fallback to .env
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="Simplified Law Summarizer", page_icon="⚖️", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def extract_text_from_pdf(uploaded_file):
    """Extract raw text from uploaded PDF file"""
    pdf = PdfReader(uploaded_file)
    text = ""
    for page in pdf.pages:
        text += page.extract_text() or ""
    return text.strip()

def call_gemini_api(prompt: str) -> str:
    """Send text to Gemini API and return structured summary with glossary"""
    if not api_key:
        return "⚠️ API key not found. Please set GEMINI_API_KEY in Streamlit Secrets (deployment) or in a .env file (local)."

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {"parts": [{"text": (
                    "You are a legal simplifier assistant.\n\n"
                    "Task: Summarize the following legal text in **clear bullet points**.\n"
                    "Requirements:\n"
                    "1. Use short, simple sentences in plain English.\n"
                    "2. Highlight important legal terms or phrases using **bold**.\n"
                    "3. Limit summary to 5–7 key points.\n"
                    "4. At the end, add a section called 'Glossary' explaining difficult legal words in simple terms.\n\n"
                    f"Legal text:\n{prompt}"
                )}]}
            ]
        }
        resp = requests.post(api_url, headers=headers, json=data, timeout=60)

        if resp.status_code == 200:
            out = resp.json()
            return out["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"❌ API Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"❌ API call failed: {e}"

def clean_summary(summary: str) -> str:
    """Remove Markdown bold (**text**) and clean text"""
    summary = re.sub(r'\*\*(.*?)\*\*', r'\1', summary)
    summary = re.sub(r'^\*\s+', '', summary, flags=re.MULTILINE)
    return summary

def generate_pdf(summary: str) -> bytes:
    """Generate PDF with proper bullets and wrapped text"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    normal_style.fontName = "Helvetica"
    normal_style.fontSize = 11
    normal_style.leading = 14

    summary_clean = clean_summary(summary)
    lines = summary_clean.splitlines()
    story = []

    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 5))
            continue
        if line.startswith("-") or line.startswith("*"):
            line = line[1:].strip()
            item = ListItem(Paragraph(line, normal_style))
            story.append(ListFlowable([item], bulletType='bullet', start='bullet'))
        else:
            story.append(Paragraph(line, normal_style))
            story.append(Spacer(1, 5))

    doc.build(story)
    buffer.seek(0)
    return buffer

# -----------------------------
# UI Layout
# -----------------------------
st.title("⚖️ Simplified Law Summarizer")
st.caption("Enter legal text or upload a PDF. The AI will generate a structured summary with key points and a glossary.")

tab1, tab2 = st.tabs(["✍️ Manual Input", "📄 Upload PDF"])

with tab1:
    manual_text = st.text_area("Enter legal text here:", height=200)

with tab2:
    uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"])
    pdf_text = ""
    if uploaded_pdf:
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        st.success("✅ PDF uploaded and text extracted.")

# Final input text (either manual or PDF)
input_text = manual_text if manual_text.strip() else pdf_text

# -----------------------------
# Generate Summary
# -----------------------------
if st.button("Generate Summary", type="primary", use_container_width=True):
    if not input_text.strip():
        st.warning("Please enter text or upload a PDF first.")
    else:
        with st.spinner("Generating structured summary..."):
            summary = call_gemini_api(input_text)

        st.subheader("📝 Simplified Summary")
        st.markdown(summary)  # markdown to keep bold & bullet formatting

        # Cleaned summary for copy & PDF
        cleaned_summary = clean_summary(summary)

        # --- Streamlit-native Copy & Download buttons ---
        st.subheader("📋 Copy & Download Summary")

        # Scrollable summary box
        st.text_area(
            "Copy-ready summary (scrollable)",
            value=cleaned_summary,
            height=200,
            key="summary_area"
        )

        # Copy as .txt
        st.download_button(
            label="⬇ Download txt file",
            data=cleaned_summary,
            file_name="summary.txt",
            mime="text/plain"
        )

        # Download PDF
        pdf_file = generate_pdf(summary)
        st.download_button(
            "⬇ Download Summary as PDF",
            data=pdf_file,
            file_name="simplified_summary.pdf",
            mime="application/pdf"
        )
