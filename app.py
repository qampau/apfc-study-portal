import os
import json
import time
import sqlite3
from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.express as px
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------
# PAGE CONFIGURATION & STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="UPSC APFC Master Portal",
    page_icon="🏛️",
    layout="wide"
)

st.markdown("""
<style>
    .clock-badge {
        font-family: 'Courier New', Courier, monospace;
        background: linear-gradient(135deg, #0f172a, #1e293b);
        color: #38bdf8;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 1.05rem;
        display: inline-block;
        border: 1px solid #334155;
    }
    .auto-badge {
        background: linear-gradient(135deg, #064e3b, #047857);
        color: #6ee7b7;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
        border: 1px solid #059669;
    }
</style>
""", unsafe_allow_html=True)

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
    st.caption("Secure Online Cockpit for Bare Acts, Question Banks, and Notes")

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
# 2. DATABASE INITIALIZATION
# -------------------------------------------------------------
def get_db():
    conn = sqlite3.connect("apfc_portal.db", timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS test_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            test_type TEXT DEFAULT 'Sectional',
            topic TEXT,
            total_questions INTEGER,
            attempted INTEGER,
            correct INTEGER,
            incorrect INTEGER,
            score REAL,
            accuracy REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS mistake_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            topic TEXT,
            question TEXT UNIQUE,
            options_json TEXT,
            correct_index INTEGER,
            user_wrong_index INTEGER,
            explanation TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            title TEXT,
            content TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_targets (
            target_date TEXT PRIMARY KEY,
            mcqs_done INTEGER DEFAULT 0,
            reading_done INTEGER DEFAULT 0,
            revision_done INTEGER DEFAULT 0,
            notes_done INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS syllabus_tracker (
            unit TEXT PRIMARY KEY,
            status TEXT DEFAULT 'Pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------------------------------------------------
# 3. LIVE IST CLOCK & EXAM COUNTDOWN
# -------------------------------------------------------------
st_autorefresh(interval=1000, key="ist_clock_ticker")

GROQ_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
MODEL_REASONING = "llama-3.3-70b-versatile"
MODEL_FAST = "llama-3.1-8b-instant"

current_ist_time = datetime.now().strftime("%I:%M:%S %p")
EXAM_DATE = date(2026, 12, 20)
days_left = (EXAM_DATE - date.today()).days

tb1, tb2, tb3, tb4 = st.columns([3, 1.4, 1.3, 1.5])
with tb1:
    st.markdown(f"### 🏛️ UPSC APFC Executive Portal")
    st.caption(f"Logged in as **{st.session_state.user.title()}** | EPFO Recruitment Hub")
with tb2:
    st.markdown(f"**Live IST Time**  \n<span class='clock-badge'>⏰ {current_ist_time}</span>", unsafe_allow_html=True)
with tb3:
    st.metric("🎯 Exam Target", f"⏳ {max(0, days_left)} Days", help="Target Date: 20 Dec 2026")
with tb4:
    if st.button("🚪 Log Out", key="logout_btn", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

# -------------------------------------------------------------
# 4. NAVIGATION
# -------------------------------------------------------------
NAV_OPTIONS = [
    "🏠 Executive Cockpit",
    "⚡ Practice Hall",
    "📕 Mistake Vault",
    "🧠 Auto-Notes Synthesizer",
    "📚 Study Materials Vault",
    "📋 Statutory Checklist",
    "📈 Analytics & Scores"
]

if "active_nav" not in st.session_state:
    st.session_state.active_nav = NAV_OPTIONS[0]

active_tab = st.radio(
    "Navigation Menu",
    NAV_OPTIONS,
    index=NAV_OPTIONS.index(st.session_state.active_nav),
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state.active_nav = active_tab
st.divider()

APFC_TOPICS = [
    "Labour Laws & Industrial Relations",
    "Social Security in India (EPFO/ESIC)",
    "General Accounting Principles",
    "Auditing Principles & Vouching",
    "Indian Freedom Struggle & Culture",
    "Indian Polity & Governance",
    "Basic Economics & Development",
    "Insurance & Basic Commerce"
]

# -------------------------------------------------------------
# 5. GROQ AI ENGINE WITH STATIC FALLBACK
# -------------------------------------------------------------
FALLBACK_QUESTIONS = [
    {
        "id": 1,
        "question": "Under the Employees' Provident Funds and MP Act, 1952, which authority is empowered under Section 7A to assess defaulted employer contributions?",
        "options": ["Assistant Labour Commissioner", "Assistant Provident Fund Commissioner", "Welfare Commissioner", "Presiding Officer, CGIT"],
        "correct_index": 1,
        "explanation": "Section 7A vests the APFC/RPFC with quasi-judicial powers identical to a Civil Court under CPC 1908 to assess dues."
    },
    {
        "id": 2,
        "question": "What is the continuous service threshold for payment of gratuity to working journalists under Section 53 of the Code on Social Security, 2020?",
        "options": ["1 year", "3 years", "5 years", "10 years"],
        "correct_index": 1,
        "explanation": "Section 53 of the Code on Social Security reduces the service threshold to 3 years specifically for working journalists."
    },
    {
        "id": 3,
        "question": "Which accounting convention requires that anticipation should not be made for profits, but provision must be made for all prospective losses?",
        "options": ["Matching Convention", "Conservatism / Prudence", "Materiality Convention", "Consistency Convention"],
        "correct_index": 1,
        "explanation": "The Prudence / Conservatism convention ensures that liabilities and probable losses are recorded upon reasonable anticipation."
    }
]

def generate_questions(topic: str, num_q: int, focus: str = ""):
    if not GROQ_KEY:
        return FALLBACK_QUESTIONS[:num_q]

    prompt = f"""
    You are an austere UPSC APFC question setter. Generate {num_q} high-difficulty MCQs on: '{topic}'. Focus: '{focus}'.
    Respond strictly with valid raw JSON format:
    {{
      "questions": [
        {{
          "id": 1,
          "question": "Statutory conceptual question",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "correct_index": 0,
          "explanation": "Legal rationale citing specific act and sections"
        }}
      ]
    }}
    """
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_KEY)
        try:
            resp = client.chat.completions.create(
                model=MODEL_REASONING,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1500
            )
        except Exception:
            resp = client.chat.completions.create(
                model=MODEL_FAST,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1500
            )
        data = json.loads(resp.choices[0].message.content)
        qs = data.get("questions", data)
        return qs if isinstance(qs, list) and len(qs) > 0 else FALLBACK_QUESTIONS[:num_q]
    except Exception:
        return FALLBACK_QUESTIONS[:num_q]

# -------------------------------------------------------------
# TAB 1: EXECUTIVE COCKPIT
# -------------------------------------------------------------
if st.session_state.active_nav == "🏠 Executive Cockpit":
    conn = get_db()
    df_tests = pd.read_sql_query("SELECT * FROM test_history ORDER BY id DESC", conn)
    mistake_count = conn.execute("SELECT COUNT(*) as c FROM mistake_vault").fetchone()["c"]
    notes_count = conn.execute("SELECT COUNT(*) as c FROM study_notes").fetchone()["c"]
    today_str = date.today().isoformat()
    t_row = conn.execute("SELECT * FROM daily_targets WHERE target_date = ?", (today_str,)).fetchone()
    mastered_count = conn.execute("SELECT COUNT(*) as c FROM syllabus_tracker WHERE status = 'Mastered'").fetchone()["c"]
    conn.close()

    total_syllabus_units = 16
    syll_ratio = min(1.0, mastered_count / total_syllabus_units)
    avg_accuracy = (df_tests["accuracy"].mean() / 100.0) if not df_tests.empty else 0.0
    mock_volume_factor = min(1.0, len(df_tests) / 10.0)
    readiness_pct = int(((syll_ratio * 0.45) + (avg_accuracy * 0.40) + (mock_volume_factor * 0.15)) * 100)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 APFC Readiness Index", f"{readiness_pct}%", delta=f"{len(df_tests)} tests taken")
    c2.metric("📕 Mistakes In Vault", f"{mistake_count}", delta="- Review Needed" if mistake_count > 0 else "Clean!", delta_color="inverse")
    c3.metric("📝 Synthesized Notes", f"{notes_count} Stored")
    c4.metric("🏆 Average Test Accuracy", f"{avg_accuracy * 100:.1f}%")

    st.divider()

    col_left, col_right = st.columns([1.8, 1.2])
    with col_left:
        st.markdown("#### ⚡ Rapid Drill Launcher")
        st.caption("Pick a domain to immediately draft and launch MCQs.")
        
        qd1, qd2, qd3 = st.columns([2, 1, 1])
        with qd1:
            fast_topic = st.selectbox("Domain", APFC_TOPICS, key="quick_topic")
        with qd2:
            fast_q = st.selectbox("Count", [3, 5, 10], index=0, key="quick_count")
        with qd3:
            st.write("")
            st.write("")
            if st.button("🚀 Start Drill", type="primary", use_container_width=True):
                with st.spinner("Generating statutory questions..."):
                    qs = generate_questions(fast_topic, fast_q)
                    st.session_state.questions = qs
                    st.session_state.topic = fast_topic
                    st.session_state.user_answers = {}
                    st.session_state.test_active = True
                    st.session_state.active_nav = "⚡ Practice Hall"
                    st.rerun()

        st.markdown("#### ⚖️ Statutory Quick Reference")
        with st.expander("📌 EPF & MP Act, 1952 Key Anchors"):
            st.markdown("""
            - **Section 1(3)**: Applicable to establishments with 20 or more employees.
            - **Section 7A**: Quasi-judicial inquiry to assess defaulted contributions.
            - **Section 8B-8G**: Modes of recovery through Attachment of bank accounts/property.
            - **Section 14B**: Power to recover damages up to 25% per annum for delayed remittances.
            """)
        with st.expander("📌 Code on Social Security, 2020 Essentials"):
            st.markdown("""
            - **Aggregators & Gig Workers**: Mandates 1-2% of turnover (capped at 5% of payout to workers).
            - **Gratuity for Fixed Term Employees**: Payable pro-rata on completing 1 year of continuous service.
            - **Crèche Mandate**: Mandatory for establishments with 50 or more workers.
            """)

    with col_right:
        st.markdown("#### 🎯 Daily Goal & Study Tracker")
        m_val = bool(t_row["mcqs_done"]) if t_row else False
        r_val = bool(t_row["reading_done"]) if t_row else False
        rev_val = bool(t_row["revision_done"]) if t_row else False
        n_val = bool(t_row["notes_done"]) if t_row else False

        g1 = st.checkbox("Practice 20 Statutory MCQs", value=m_val, key="chk_m")
        g2 = st.checkbox("Read 1 Bare Act Chapter", value=r_val, key="chk_r")
        g3 = st.checkbox("Review 5 Vault Mistakes", value=rev_val, key="chk_rev")
        g4 = st.checkbox("Synthesize 1 Revision Note", value=n_val, key="chk_n")

        tasks_done = sum([g1, g2, g3, g4])
        st.progress(tasks_done / 4.0)
        st.caption(f"Progress: **{tasks_done} of 4 Daily Tasks Completed**")

        if st.button("💾 Log Daily Progress", use_container_width=True):
            conn = get_db()
            conn.execute("""
                INSERT INTO daily_targets (target_date, mcqs_done, reading_done, revision_done, notes_done)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(target_date) DO UPDATE SET
                    mcqs_done = excluded.mcqs_done,
                    reading_done = excluded.reading_done,
                    revision_done = excluded.revision_done,
                    notes_done = excluded.notes_done
            """, (today_str, int(g1), int(g2), int(g3), int(g4)))
            conn.commit()
            conn.close()
            st.success("Daily targets saved!")
            st.rerun()

# -------------------------------------------------------------
# TAB 2: PRACTICE HALL
# -------------------------------------------------------------
elif st.session_state.active_nav == "⚡ Practice Hall":
    st.subheader("⚡ UPSC APFC Test Simulation")

    if "test_active" not in st.session_state:
        st.session_state.test_active = False

    if not st.session_state.test_active and "test_submitted" not in st.session_state:
        c1, c2 = st.columns(2)
        with c1:
            sel_topic = st.selectbox("Subject Domain", APFC_TOPICS, key="hall_topic")
            focus = st.text_input("Specific Provision / Act (Optional)", placeholder="e.g. Gratuity forfeiture or Wages definition", key="hall_focus")
        with c2:
            num_q = st.select_slider("Question Count", options=[3, 5, 10], value=5, key="hall_num")

        if st.button("🚀 Start Sectional Drill", type="primary", key="hall_btn_start"):
            with st.spinner("Generating questions with precision..."):
                qs = generate_questions(sel_topic, num_q, focus)
                st.session_state.questions = qs
                st.session_state.topic = sel_topic
                st.session_state.user_answers = {}
                st.session_state.test_active = True
                st.rerun()

    if st.session_state.get("test_active", False):
        st.markdown(f"### 📝 {st.session_state.topic}")
        with st.form("exam_form"):
            for i, q in enumerate(st.session_state.questions):
                st.markdown(f"**Q{i+1}. {q['question']}**")
                choice = st.radio(
                    label=f"q_{i}",
                    options=["Not Attempted"] + q["options"],
                    index=0,
                    key=f"ans_choice_{i}",
                    label_visibility="collapsed"
                )
                if choice != "Not Attempted":
                    st.session_state.user_answers[i] = q["options"].index(choice)
                else:
                    st.session_state.user_answers.pop(i, None)
                st.divider()

            if st.form_submit_button("🏁 Submit Test Paper", type="primary"):
                st.session_state.test_active = False
                st.session_state.test_submitted = True
                st.rerun()

    if st.session_state.get("test_submitted", False):
        st.header("🎯 Scorecard & Solutions")
        qs = st.session_state.questions
        ans = st.session_state.user_answers

        correct, incorrect = 0, 0
        mistakes = []

        for i, q in enumerate(qs):
            pick = ans.get(i)
            if pick is not None:
                if pick == q["correct_index"]:
                    correct += 1
                else:
                    incorrect += 1
                    mistakes.append((
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        st.session_state.topic,
                        q["question"],
                        json.dumps(q["options"]),
                        q["correct_index"],
                        pick,
                        q.get("explanation", "")
                    ))

        attempted = len(ans)
        score = (correct * 2.5) - (incorrect * 0.833)
        acc = (correct / attempted * 100) if attempted > 0 else 0.0

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Net Marks", f"{score:.2f} / {len(qs)*2.5:.1f}")
        r2.metric("Accuracy", f"{acc:.1f}%")
        r3.metric("Correct / Incorrect", f"{correct} / {incorrect}")
        r4.metric("Unattempted", len(qs) - attempted)

        conn = get_db()
        conn.execute("""
            INSERT INTO test_history (timestamp, test_type, topic, total_questions, attempted, correct, incorrect, score, accuracy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M"), "Sectional", st.session_state.topic, len(qs), attempted, correct, incorrect, score, acc))
        
        for m in mistakes:
            conn.execute("INSERT OR IGNORE INTO mistake_vault (timestamp, topic, question, options_json, correct_index, user_wrong_index, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)", m)
        conn.commit()
        conn.close()

        st.subheader("📖 Solutions & Statutory Rationales")
        for i, q in enumerate(qs):
            pick = ans.get(i)
            is_corr = pick == q["correct_index"]
            badge = "⚪ Unattempted" if pick is None else ("🟢 Correct" if is_corr else "🔴 Incorrect")
            with st.expander(f"Q{i+1}: {q['question'][:80]}... — {badge}"):
                for idx, opt in enumerate(q["options"]):
                    pfx = "• "
                    if idx == q["correct_index"]: pfx = "✅ "
                    elif pick == idx: pfx = "❌ Your Answer: "
                    st.write(f"{pfx} {opt}")
                st.info(f"**Rationale:** {q.get('explanation', '')}")

        if st.button("Take Another Drill"):
            del st.session_state.test_submitted
            del st.session_state.questions
            st.rerun()

# -------------------------------------------------------------
# TAB 3: MISTAKE VAULT
# -------------------------------------------------------------
elif st.session_state.active_nav == "📕 Mistake Vault":
    st.subheader("📕 Mistake Vault & Active Recall")
    conn = get_db()
    mistakes = conn.execute("SELECT * FROM mistake_vault ORDER BY id DESC").fetchall()
    conn.close()

    if not mistakes:
        st.success("🎉 Your Mistake Vault is completely clean!")
    else:
        st.write(f"Total Logged Mistakes: **{len(mistakes)}**")
        if st.button("🧹 Clear All Stored Mistakes"):
            conn = get_db()
            conn.execute("DELETE FROM mistake_vault")
            conn.commit()
            conn.close()
            st.rerun()

        for m in mistakes:
            opts = json.loads(m["options_json"])
            with st.expander(f"📌 [{m['topic']}] {m['question'][:80]}..."):
                st.write(f"**Question:** {m['question']}")
                for idx, opt in enumerate(opts):
                    pfx = "• "
                    if idx == m["correct_index"]: pfx = "✅ Correct: "
                    elif idx == m["user_wrong_index"]: pfx = "❌ Your Answer: "
                    st.write(f"{pfx} {opt}")
                st.info(f"**Statutory Rationale:** {m['explanation']}")
                if st.button("Mark as Mastered", key=f"del_m_{m['id']}"):
                    conn = get_db()
                    conn.execute("DELETE FROM mistake_vault WHERE id = ?", (m["id"],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# -------------------------------------------------------------
# TAB 4: AUTO-NOTES SYNTHESIZER
# -------------------------------------------------------------
elif st.session_state.active_nav == "🧠 Auto-Notes Synthesizer":
    st.subheader("🧠 Open-Source Auto-Notes Synthesizer")
    st.caption("Synthesizes statutory revision notes using Groq LPU acceleration.")

    note_topic = st.text_input("Enter Act, Provision, or Doctrine", placeholder="e.g. Section 7A & 14B EPF Act 1952")

    if st.button("⚡ Synthesize Revision Notes", type="primary"):
        if note_topic.strip() and GROQ_KEY:
            from groq import Groq
            client = Groq(api_key=GROQ_KEY)
            prompt = f"""
            Act as an expert UPSC APFC author. Provide high-yield statutory revision notes on: '{note_topic}'.
            Format using concise Markdown bullets under 350 words:
            - 📌 Core Statutory Definitions & Scope
            - 🔢 Key Thresholds & Statutory Limits (Wages, Staff, Time)
            - ⚠️ Penal Provisions & Adjudication Powers (APFC authority)
            - 🎯 High-Yield UPSC Traps & Precedents
            """

            st.markdown("### 📝 Live Revision Notes")
            placeholder = st.empty()
            accumulated_text = ""

            try:
                try:
                    stream = client.chat.completions.create(
                        model=MODEL_FAST,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=800,
                        stream=True
                    )
                except Exception:
                    stream = client.chat.completions.create(
                        model=MODEL_REASONING,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=800,
                        stream=True
                    )

                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    accumulated_text += delta
                    placeholder.markdown(accumulated_text + "▌")

                placeholder.markdown(accumulated_text)

                conn = get_db()
                conn.execute("INSERT INTO study_notes (timestamp, title, content) VALUES (?, ?, ?)",
                             (datetime.now().strftime("%Y-%m-%d %H:%M"), note_topic, accumulated_text))
                conn.commit()
                conn.close()
                st.success("✅ Notes generated and saved!")
            except Exception as e:
                placeholder.empty()
                st.error(f"Generation error: {e}")

    st.divider()
    conn = get_db()
    saved = conn.execute("SELECT * FROM study_notes ORDER BY id DESC").fetchall()
    conn.close()
    if saved:
        st.markdown("#### 📚 Saved Statutory Notes")
        for s in saved:
            with st.expander(f"📌 {s['title']} ({s['timestamp']})"):
                st.markdown(s["content"])
                if st.button("Delete Note", key=f"del_sn_{s['id']}"):
                    conn = get_db()
                    conn.execute("DELETE FROM study_notes WHERE id = ?", (s["id"],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# -------------------------------------------------------------
# TAB 5: STUDY MATERIALS VAULT (PDFs)
# -------------------------------------------------------------
elif st.session_state.active_nav == "📚 Study Materials Vault":
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
# TAB 6: STATUTORY CHECKLIST
# -------------------------------------------------------------
elif st.session_state.active_nav == "📋 Statutory Checklist":
    st.subheader("📋 APFC Statutory Mastery Tracker")
    CHECKLIST_UNITS = [
        "Code on Wages, 2019 (Floor Wage & Deductions)",
        "Industrial Relations Code, 2020 (Bargaining Council & Standing Orders)",
        "Code on Social Security, 2020 (EPF, ESI, Gratuity, Aggregators)",
        "OSHWC Code, 2020 (Safety Committees & Working Hours)",
        "EPF Scheme 1952 & Excluded Employee Rules",
        "EPS-95 Pension Calculation & Higher Pension Options",
        "Payment of Gratuity Act, 1972 (Section 4 & Forfeiture)",
        "Maternity Benefit Act, 1961 (Crèche & 26 Weeks Mandate)",
        "Unorganised Workers' Social Security Act, 2008",
        "Accounting Concepts (Matching, Accrual, Conservatism)",
        "Capital vs Revenue Expenditures & Receipts",
        "Depreciation Accounting & Trial Balance Errors",
        "Auditing: Vouching, Verification, Auditor Disqualifications",
        "Indian Freedom Struggle (1857-1947 Major Acts)",
        "Indian Polity: Executive Powers & Constitutional Bodies",
        "Basic Economics & Inflation Indicators"
    ]

    conn = get_db()
    for item in CHECKLIST_UNITS:
        c_name, c_act = st.columns([3, 1])
        c_name.write(f"• **{item}**")
        row = conn.execute("SELECT status FROM syllabus_tracker WHERE unit = ?", (item,)).fetchone()
        cur_status = row["status"] if row else "Pending"
        new_status = c_act.selectbox(
            "Status",
            ["Pending", "Reading", "Mastered"],
            index=["Pending", "Reading", "Mastered"].index(cur_status),
            key=f"syl_unit_{item}",
            label_visibility="collapsed"
        )
        if new_status != cur_status:
            conn.execute("INSERT OR REPLACE INTO syllabus_tracker (unit, status) VALUES (?, ?)", (item, new_status))
            conn.commit()
    conn.close()

# -------------------------------------------------------------
# TAB 7: ANALYTICS & SCORES
# -------------------------------------------------------------
elif st.session_state.active_nav == "📈 Analytics & Scores":
    st.subheader("📈 Performance Diagnostics")
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM test_history ORDER BY id DESC", conn)
    conn.close()

    if df.empty:
        st.info("No test records found. Complete a practice drill to generate analytics.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tests Completed", len(df))
        k2.metric("Mean Score", f"{df['score'].mean():.2f}")
        k3.metric("Average Accuracy", f"{df['accuracy'].mean():.1f}%")
        k4.metric("Negative Marks Lost", f"{df['incorrect'].sum() * 0.833:.1f}")

        st.divider()
        fig = px.line(df, x="timestamp", y="score", markers=True, title="Score Trajectory Over Time")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["timestamp", "test_type", "topic", "total_questions", "score", "accuracy"]], use_container_width=True)
