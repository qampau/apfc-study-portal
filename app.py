import os
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from groq import Groq

st.set_page_config(
    page_title="UPSC APFC Master Portal",
    page_icon="🏛️",
    layout="wide"
)

# -------------------------------------------------------------
# 1. USER AUTHENTICATION
# -------------------------------------------------------------
USERS = {
    "admin": "apfc2026",
    "ajay": "upscpass123"
}

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("## 🏛️ UPSC APFC Executive Portal — Login")
    st.caption("Secure Portal for Bare Acts, Question Banks, and Notes")

    col1, _ = st.columns([1, 1.5])
    with col1:
        with st.form("login_form"):
            user = st.text_input("Username").strip()
            pwd = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Sign In", type="primary"):
                if user in USERS and USERS[user] == pwd:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")
    return False

if not check_auth():
    st.stop()

# -------------------------------------------------------------
# 2. LOGGED-IN PORTAL
# -------------------------------------------------------------
GROQ_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

h1, h2 = st.columns([4, 1])
with h1:
    st.title(f"🏛️ Welcome, {st.session_state.user.title()}")
    st.caption("UPSC APFC Online Study Management Portal")
with h2:
    st.write("")
    if st.button("🚪 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

tab_materials, tab_ai = st.tabs(["📚 Study Materials Vault", "⚡ AI Notes & Test Drills"])

# -------------------------------------------------------------
# TAB 1: STUDY MATERIAL VAULT
# -------------------------------------------------------------
with tab_materials:
    st.subheader("📚 Reference Materials & Bare Acts")
    materials_dir = "study_materials"
    os.makedirs(materials_dir, exist_ok=True)

    uploaded_file = st.file_uploader("Upload New PDF Document", type=["pdf"])
    if uploaded_file:
        file_path = os.path.join(materials_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved: {uploaded_file.name}")
        st.rerun()

    pdf_files = [f for f in os.listdir(materials_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        st.info("Upload your bare act or study note PDFs above to access them anywhere.")
    else:
        selected_pdf = st.selectbox("Select Document", sorted(pdf_files))
        if selected_pdf:
            path = os.path.join(materials_dir, selected_pdf)
            c1, c2 = st.columns([1, 2.5])
            with c1:
                with open(path, "rb") as f:
                    st.download_button("📥 Download PDF", f, file_name=selected_pdf, mime="application/pdf")
            with c2:
                with st.expander("🔍 Preview Extracted Text (First 5 Pages)", expanded=True):
                    try:
                        reader = PdfReader(path)
                        text = ""
                        for i in range(min(5, len(reader.pages))):
                            text += f"--- Page {i+1} ---\n" + (reader.pages[i].extract_text() or "") + "\n\n"
                        st.text_area("Content", text, height=350)
                    except Exception as e:
                        st.error(f"Error reading PDF: {e}")

# -------------------------------------------------------------
# TAB 2: GROQ AI ASSISTANT
# -------------------------------------------------------------
with tab_ai:
    st.subheader("⚡ Groq LPU Assistant (Llama 3.3 70B)")
    topic = st.text_input("Enter Topic / Provision", placeholder="e.g. Section 7A EPF Act 1952 vs Section 14B damages")
    
    b1, b2 = st.columns(2)
    with b1:
        gen_notes = st.button("📝 Synthesize Revision Notes", type="primary")
    with b2:
        gen_mcq = st.button("🎯 Generate Practice MCQs")

    if gen_notes or gen_mcq:
        if not topic.strip():
            st.warning("Please enter a topic.")
        elif not GROQ_KEY:
            st.error("GROQ_API_KEY is missing in Secrets.")
        else:
            client = Groq(api_key=GROQ_KEY)
            prompt = (
                f"Act as an expert UPSC APFC legal scholar. Provide high-yield statutory revision notes under 350 words on: '{topic}'. Include relevant bare act sections and key limits."
                if gen_notes else
                f"Act as a UPSC APFC test setter. Generate 3 difficult multiple-choice questions on: '{topic}'. Include 4 options, the correct answer, and an in-depth explanation."
            )
            with st.spinner("Generating with Llama 3.3 70B..."):
                try:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=900
                    )
                    st.markdown(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"API Error: {e}")
