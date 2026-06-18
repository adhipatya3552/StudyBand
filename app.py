import streamlit as st
import json
import time
import os
import re
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="StudyBand 🎓",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
STATE_FILE = "shared_state.json"

# Auto-create shared_state.json if it doesn't exist (needed for fresh Streamlit Cloud deploys)
_DEFAULT_STATE = {
    "status": "idle", "topic": "", "notes": "", "simple_notes": "",
    "quiz": [], "evaluation": "", "student_answers": {},
    "education_level": "High School (Grades 9-12)",
    "provider": "groq", "model": "llama-3.1-8b-instant",
    "needs_remedial": False, "previous_quizzes": []
}
if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as _f:
        json.dump(_DEFAULT_STATE, _f, indent=2)

def markdown_to_html(md_text):
    if not md_text:
        return ""
    html = md_text
    # Escape HTML special characters
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert headers
    html = re.sub(r'(?m)^###\s+(.*?)\s*$', r'<h3 style="margin-top: 15px; margin-bottom: 5px; color: #1e4620;">\1</h3>', html)
    html = re.sub(r'(?m)^##\s+(.*?)\s*$', r'<h2 style="margin-top: 20px; margin-bottom: 8px; color: #1e4620;">\1</h2>', html)
    html = re.sub(r'(?m)^#\s+(.*?)\s*$', r'<h1 style="margin-top: 25px; margin-bottom: 10px; color: #1e4620;">\1</h1>', html)
    # Convert bold
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    # Convert bullet points
    html = re.sub(r'(?m)^\*\s+(.*?)\s*$', r'<div style="margin-left: 15px; margin-bottom: 5px;">• \1</div>', html)
    # Convert code blocks
    html = re.sub(r'```python\s*(.*?)\s*```', r'<pre style="background: #f1f8e9; padding: 10px; border-radius: 4px; font-family: monospace;"><code>\1</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'```\s*(.*?)\s*```', r'<pre style="background: #f1f8e9; padding: 10px; border-radius: 4px; font-family: monospace;"><code>\1</code></pre>', html, flags=re.DOTALL)
    # Convert inline code
    html = re.sub(r'`(.*?)`', r'<code style="background: #f1f8e9; padding: 2px 4px; border-radius: 3px; font-family: monospace;">\1</code>', html)
    # Paragraph formatting
    paragraphs = html.split('\n\n')
    formatted = []
    for p in paragraphs:
        p_clean = p.strip()
        if p_clean:
            if p_clean.startswith('<div style="margin-left:'):
                formatted.append(p_clean.replace('\n', ''))
            elif p_clean.startswith('<h'):
                formatted.append(p_clean.replace('\n', '<br>'))
            else:
                p_clean_br = p_clean.replace("\n", "<br>")
                formatted.append(f'<p style="margin-bottom: 10px; line-height: 1.5;">{p_clean_br}</p>')

    return '\n'.join(formatted)

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "status": "idle", "topic": "", "notes": "",
            "simple_notes": "", "quiz": [], "evaluation": "",
            "student_answers": {}, "education_level": "College / University",
            "provider": "groq", "model": "llama-3.3-70b-versatile"
        }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def reset_state():
    current_state = load_state()
    provider = current_state.get("provider", "groq")
    model = current_state.get("model", "llama-3.3-70b-versatile")
    save_state({
        "status": "idle", "topic": "", "notes": "",
        "simple_notes": "", "quiz": [], "evaluation": "",
        "student_answers": {}, "education_level": "College / University",
        "provider": provider,
        "model": model
    })

STATUS_MAP = {
    "idle": ("⏸️ Idle", 0),
    "starting": ("🔄 Starting...", 5),
    "researching": ("🔍 Researcher working...", 20),
    "researched": ("✅ Research done", 40),
    "simplifying": ("✏️ Simplifier working...", 55),
    "simplified": ("✅ Notes simplified", 65),
    "remedial_requested": ("🔄 Review quiz requested...", 70),
    "creating_remedial": ("❓ Quiz Master generating review...", 80),
    "creating_quiz": ("❓ Quiz Master working...", 80),
    "quiz_ready": ("✅ Quiz ready!", 90),
    "evaluating": ("📊 Evaluator checking answers...", 95),
    "evaluated": ("🏆 Done!", 100),
    "error": ("❌ Error occurred", 0),
}

# ─────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1a1a2e; }
    .agent-card {
        background: #f8f9fa;
        border-left: 4px solid #4CAF50;
        padding: 10px 15px;
        border-radius: 6px;
        margin: 6px 0;
        font-size: 0.9rem;
        color: #2e3033 !important;
    }
    .agent-card, .agent-card * {
        color: #2e3033 !important;
    }
    .agent-card.active { border-left-color: #2196F3; background: #e3f2fd; }
    .agent-card.done { border-left-color: #4CAF50; background: #e8f5e9; }
    .quiz-box {
        background: #fff3e0;
        border: 1px solid #ff9800;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        color: #3e2723 !important;
    }
    .quiz-box, .quiz-box * {
        color: #3e2723 !important;
    }
    .result-box {
        background: #e8f5e9;
        border: 1px solid #4CAF50;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
        color: #1e4620 !important;
    }
    .result-box, .result-box * {
        color: #1e4620 !important;
    }
    pre, pre *, code, code * {
        background-color: #1e1e2f !important;
        color: #f8f9fa !important;
        font-family: monospace !important;
    }
    pre {
        padding: 12px !important;
        border-radius: 6px !important;
        border: 1px solid #2a2a40 !important;
        margin: 10px 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# SIDEBAR — Agent Status
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 Agent Pipeline")
    st.caption("Built with Band.ai + Groq")
    st.divider()

    state = load_state()
    status = state.get("status", "idle")
    label, progress_val = STATUS_MAP.get(status, ("Unknown", 0))

    st.progress(progress_val / 100)
    st.markdown(f"**Status:** {label}")
    st.caption("ℹ️ *Status shows the current active step in the multi-agent pipeline. 'Idle' means the agents are waiting for you to input a topic in the 'Study' tab and click 'Start Studying'.*")
    st.markdown(f"**Level:** {state.get('education_level', 'College / University')}")
    st.divider()

    # Provider & Model Selection dropdowns
    st.markdown("### ⚙️ LLM Configuration")
    providers = ["Groq", "AI/ML API"]
    current_provider = state.get("provider", "groq").upper()
    if current_provider == "AIMLAPI":
        current_provider_label = "AI/ML API"
    else:
        current_provider_label = "Groq"

    selected_provider_label = st.selectbox(
        "Select AI Provider",
        options=providers,
        index=providers.index(current_provider_label) if current_provider_label in providers else 0,
        help="Select the LLM provider (Groq or AI/ML API) to power the agents."
    )
    selected_provider = "aimlapi" if selected_provider_label == "AI/ML API" else "groq"

    # Define model choices based on provider
    if selected_provider == "aimlapi":
        model_options = {
            "Llama 3.3 70B (AI/ML API - Turbo)": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Llama 3.1 Nemotron 70B (AI/ML API)": "nvidia/Llama-3.1-Nemotron-70B-Instruct",
            "Llama 3.1 8B (AI/ML API - Turbo)": "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            "DeepSeek Chat V3 (AI/ML API)": "deepseek/deepseek-chat",
            "GPT-4o Mini (AI/ML API)": "gpt-4o-mini",
            "Claude 3.5 Sonnet (AI/ML API)": "anthropic/claude-3-5-sonnet",
            "Claude 4.5 Sonnet (AI/ML API)": "anthropic/claude-sonnet-4.5"
        }
        default_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        
        # Check API Key
        aimlapi_key = os.getenv("AIMLAPI_API_KEY")
        if not aimlapi_key or aimlapi_key == "your_aimlapi_key_here":
            st.warning("⚠️ `AIMLAPI_API_KEY` not found or placeholder in `.env` file. Please set it to use this provider.")
    else:
        model_options = {
            "Llama 3.3 70B (Versatile)": "llama-3.3-70b-versatile",
            "Llama 3.1 8B (Instant)": "llama-3.1-8b-instant"
        }
        default_model = "llama-3.3-70b-versatile"
        
        # Check API Key
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key or groq_key == "gsk_your_key_here":
            st.warning("⚠️ `GROQ_API_KEY` not found or placeholder in `.env` file.")

    current_model = state.get("model", default_model)
    # Ensure current_model is a valid option for the selected provider, otherwise fallback to default
    if current_model not in model_options.values():
        current_model = default_model

    default_index = list(model_options.values()).index(current_model)

    selected_model_label = st.selectbox(
        "Select AI Model",
        options=list(model_options.keys()),
        index=default_index,
        help="Select the LLM model to be used by all agents in the pipeline."
    )
    selected_model = model_options[selected_model_label]

    # Save state if either has changed
    if selected_provider != state.get("provider", "groq") or selected_model != state.get("model"):
        state["provider"] = selected_provider
        state["model"] = selected_model
        save_state(state)
        st.success(f"Config updated to {selected_provider_label} - {selected_model_label}")
        time.sleep(1)
        st.rerun()

    st.divider()

    completed = progress_val

    agents_info = [
        ("🔍 Researcher", "Gathers & structures topic notes", 40),
        ("✏️ Simplifier", "Rewrites in student-friendly language", 65),
        ("❓ Quiz Master", "Creates 5 MCQ questions", 90),
        ("✅ Evaluator", "Scores your answers & gives feedback", 100),
    ]

    for name, desc, threshold in agents_info:
        card_class = "done" if completed >= threshold else ("active" if completed >= threshold - 30 else "")
        icon = "✅" if completed >= threshold else ("⏳" if completed >= threshold - 30 else "⏸️")
        st.markdown(
            f'<div class="agent-card {card_class}">'
            f'<b>{name}</b><br><small>{desc}</small>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    if st.button("🔄 Reset Everything", use_container_width=True):
        reset_state()
        if "answers" in st.session_state:
            del st.session_state["answers"]
        st.rerun()

# ─────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────
st.markdown('<h1 style="font-size: 3.5rem; font-weight: 800; background: linear-gradient(90deg, #6441A5 0%, #2A0845 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 10px 0; padding-bottom: 5px;">🎓 StudyBand</h1>', unsafe_allow_html=True)
st.markdown("**AI-powered multi-agent study system** — 4 agents collaborate through Band.ai to help you master any topic.")
st.divider()

# Initialize session state for programmatic tab selection
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Study"

# Render horizontal navigation buttons to act as tabs
nav_col1, nav_col2, nav_col3 = st.columns(3)
with nav_col1:
    study_active = "primary" if st.session_state["active_tab"] == "Study" else "secondary"
    if st.button("📚 Study", type=study_active, use_container_width=True):
        st.session_state["active_tab"] = "Study"
        st.rerun()

with nav_col2:
    quiz_active = "primary" if st.session_state["active_tab"] == "Quiz" else "secondary"
    if st.button("❓ Quiz", type=quiz_active, use_container_width=True):
        st.session_state["active_tab"] = "Quiz"
        st.rerun()

with nav_col3:
    results_active = "primary" if st.session_state["active_tab"] == "Results" else "secondary"
    if st.button("🏆 Results", type=results_active, use_container_width=True):
        st.session_state["active_tab"] = "Results"
        st.rerun()

st.divider()

# ──────────── ACTIVE TAB: STUDY ────────────
if st.session_state["active_tab"] == "Study":
    state = load_state()
    status = state.get("status", "idle")

    if status in ["idle", "error"]:
        st.subheader("What do you want to study today?")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            topic = st.text_input(
                "Enter a topic",
                placeholder="e.g. Photosynthesis, Binary Trees, Newton's Laws, Recursion...",
                label_visibility="collapsed",
            )
        with col2:
            edu_level = st.selectbox(
                "Education Level",
                options=[
                    "Middle School (Grades 6-8)",
                    "High School (Grades 9-12)",
                    "College / University",
                    "Professional / Lifelong Learner"
                ],
                index=2,
                label_visibility="collapsed",
            )
        with col3:
            start = st.button("🚀 Start Studying", type="primary", use_container_width=True)

        if start:
            if topic.strip():
                reset_state()
                new_state = load_state()
                new_state["topic"] = topic.strip()
                new_state["education_level"] = edu_level
                new_state["status"] = "starting"
                save_state(new_state)
                st.success(f"✅ Agents are now working on: **{topic}** ({edu_level})")
                st.info("The Researcher agent will pick this up in a few seconds. This page will auto-refresh.")
                time.sleep(2)
                st.rerun()
            else:
                st.warning("Please enter a topic first!")

    else:
        topic = state.get("topic", "")
        if topic:
            st.subheader(f"📖 Topic: {topic}")

        # Show notes
        simple_notes = state.get("simple_notes", "")
        raw_notes = state.get("notes", "")

        if simple_notes:
            st.success("✅ Simplified notes ready!")
            with st.expander("📝 Simplified Study Notes (Easy to Read)", expanded=True):
                st.write(simple_notes)
            with st.expander("📖 Full Research Notes (Detailed)"):
                st.write(raw_notes)

            st.write("")
            if status in ["quiz_ready", "evaluated"]:
                col_quiz, col_new = st.columns(2)
                with col_quiz:
                    if st.button("👉 Go to Quiz to test your knowledge!", type="primary", use_container_width=True):
                        st.session_state["active_tab"] = "Quiz"
                        st.rerun()
                with col_new:
                    if st.button("📚 Study New Topic", use_container_width=True):
                        reset_state()
                        if "answers" in st.session_state:
                            del st.session_state["answers"]
                        st.session_state["active_tab"] = "Study"
                        st.rerun()
            else:
                if st.button("📚 Study New Topic", use_container_width=True):
                    reset_state()
                    if "answers" in st.session_state:
                        del st.session_state["answers"]
                    st.session_state["active_tab"] = "Study"
                    st.rerun()

        elif raw_notes:
            st.info("✏️ Simplifier agent is rewriting the notes...")
            with st.expander("📖 Research Notes (Full Version)"):
                st.write(raw_notes)

        elif status in ["starting", "researching"]:
            with st.spinner("🔍 Researcher agent is gathering information about your topic..."):
                time.sleep(1)
            st.rerun()

# ──────────── ACTIVE TAB: QUIZ ────────────
elif st.session_state["active_tab"] == "Quiz":
    state = load_state()
    quiz = state.get("quiz", [])
    status = state.get("status", "idle")

    if status == "evaluating":
        st.success("📝 **Answers submitted successfully!** The Evaluator agent is checking them. Please go to the **Results** tab to view your score.")
    elif status == "evaluated":
        st.success("🏆 **Evaluation complete!** You can check your score and detailed teacher feedback in the **Results** tab.")

    if not quiz:
        if status in ["idle"]:
            st.info("📚 First enter a topic in the Study tab to generate a quiz.")
        else:
            st.info("⏳ Quiz Master agent is creating questions... check back in a moment.")
            time.sleep(1)
            st.rerun()
    else:
        st.subheader(f"📝 Quiz — {state.get('topic', 'Your Topic')}")
        st.caption(f"{len(quiz)} questions | Answer all, then click Submit")
        st.divider()

        if "answers" not in st.session_state:
            st.session_state.answers = {}

        all_answered = True
        for i, q in enumerate(quiz):
            question_text = q.get("question", f"Question {i+1}")
            options = q.get("options", [])

            st.markdown(f'<div class="quiz-box"><b>Q{i+1}: {question_text}</b></div>', unsafe_allow_html=True)

            if options:
                selected = st.radio(
                    f"Question {i+1}",
                    options,
                    index=None,
                    key=f"q_{i}",
                    label_visibility="collapsed",
                )
                st.session_state.answers[str(i)] = selected
                if selected is None:
                    all_answered = False
            else:
                ans = st.text_input(f"Your answer for Q{i+1}", key=f"q_text_{i}")
                st.session_state.answers[str(i)] = ans
                if not ans:
                    all_answered = False

            st.write("")

        st.divider()
        col1, col2 = st.columns([1, 3])
        with col1:
            submit = st.button(
                "✅ Submit Answers",
                type="primary",
                use_container_width=True,
                disabled=not all_answered,
            )

        if submit:
            # Save answers and trigger evaluator
            cur_state = load_state()
            cur_state["student_answers"] = st.session_state.answers
            cur_state["status"] = "evaluating"
            save_state(cur_state)
            st.session_state["active_tab"] = "Results"
            st.success("Answers submitted! Evaluator agent is checking... Redirecting to Results.")
            time.sleep(1.5)
            st.rerun()

# ──────────── ACTIVE TAB: RESULTS ────────────
elif st.session_state["active_tab"] == "Results":
    state = load_state()
    evaluation = state.get("evaluation", "")
    status = state.get("status", "idle")

    if not evaluation:
        if status == "evaluating":
            with st.spinner("📊 Evaluator agent is checking your answers..."):
                time.sleep(1)
            st.rerun()
        elif status == "evaluated":
            # State saved but page not refreshed yet
            st.rerun()
        else:
            st.info("🎯 Complete the quiz and submit your answers to see your results here.")
    else:
        st.subheader("🏆 Your Results")
        st.markdown(f'<div class="result-box">{markdown_to_html(evaluation)}</div>', unsafe_allow_html=True)
        
        # Check if remedial review quiz is active
        if state.get("needs_remedial"):
            st.warning("⚠️ **Review Quiz Generated:** You scored below 80%! Our Quiz Master has automatically prepared 2 simpler review questions to help you review the concepts you missed. Go to the **Quiz** tab to complete them!")
            
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔁 Retake Quiz", use_container_width=True):
                cur_state = load_state()
                # Store the current quiz in a history list so the Quiz Master avoids these questions
                if "previous_quizzes" not in cur_state:
                    cur_state["previous_quizzes"] = []
                if cur_state.get("quiz"):
                    cur_state["previous_quizzes"].append(cur_state["quiz"])
                
                cur_state["quiz"] = []  # Clear current quiz so UI displays the loading spinner
                cur_state["status"] = "simplified"  # Trigger Quiz Master to generate new questions
                cur_state["evaluation"] = ""
                cur_state["student_answers"] = {}
                save_state(cur_state)
                if "answers" in st.session_state:
                    del st.session_state["answers"]
                st.session_state["active_tab"] = "Quiz"
                st.rerun()
        with col2:
            if st.button("📚 Study New Topic", use_container_width=True, type="primary"):
                reset_state()
                if "answers" in st.session_state:
                    del st.session_state["answers"]
                st.session_state["active_tab"] = "Study"
                st.rerun()

# ─────────────────────────────────────────
# AUTO-REFRESH while agents are working
# ─────────────────────────────────────────
state = load_state()
active_statuses = ["starting", "researching", "simplifying", "creating_quiz", "evaluating", "remedial_requested", "creating_remedial"]
if state.get("status") in active_statuses:
    time.sleep(1)
    st.rerun()
