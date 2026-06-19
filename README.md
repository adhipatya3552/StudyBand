# StudyBand 🎓 — Multi-Agent AI Study System

<div align="center">

![StudyBand Logo](https://img.shields.io/badge/StudyBand-Multi--Agent%20Study%20System-blueviolet?style=for-the-badge&logo=education&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-FF4B4B?style=for-the-badge&logo=streamlit)
![Band.ai](https://img.shields.io/badge/Band.ai-Orchestration-000000?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-Llama%203.3%2070B-orange?style=for-the-badge)
![AI/ML API](https://img.shields.io/badge/AI/ML%20API-Model%20Hub-blue?style=for-the-badge)
[![Render](https://img.shields.io/badge/Render-Deployed-brightgreen?style=for-the-badge&logo=render)](https://studyband-multi-agent-ai-study-system.onrender.com)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A collaborative multi-agent educational workspace powered by Band.ai, Groq, and the AI/ML API. Four specialized AI agents work together to help students learn any topic — from raw notes research to interactive testing and real-time remedial feedback loops.**

🚀 **Live Demo:** [https://studyband-multi-agent-ai-study-system.onrender.com](https://studyband-multi-agent-ai-study-system.onrender.com)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Core Features](#-core-features)
- [How It Works & The Handoff Flow](#-how-it-works--the-handoff-flow)
- [Multi-Agent Architecture](#-multi-agent-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [The Quiz Feedback Loop (Remedial Mode)](#-the-quiz-feedback-loop-remedial-mode)
- [License](#-license)

---

## 📖 Overview

**StudyBand** shifts study materials from passive reading to active learning. Instead of using a single LLM prompt wrapper, StudyBand utilizes **four independent AI agents** registered on **Band.ai** that communicate inside a secure Band room. 

When a student inputs a topic (e.g., *Recursion* or *Photosynthesis*) and chooses their target education level (from Middle School to Professional), the agents activate in sequence:
1. **🔍 Researcher** creates detailed, structured academic notes.
2. **✏️ Simplifier** translates technical explanations into analogies and simple language.
3. **❓ Quiz Master** generates interactive multiple-choice questions.
4. **✅ Evaluator** grades answers, gives constructive feedback, and triggers remedial review if the student struggles.

---

## ✨ Core Features

| Feature | Description |
|---------|-------------|
| 🤖 **Band.ai Coordination** | Agents communicate live via Band rooms using `@mention` handoffs, serving as a real coordination layer. |
| 🎛️ **Dual Provider Switcher** | Swap AI backends on-the-fly: **Groq** (for ultra-low latency) or **AI/ML API** (accessing Llama 3.3, Claude 3.5/4.5, DeepSeek, and GPT-4o). |
| 🎓 **Educational Targeting** | Adjusts complexity, vocabulary, and concepts automatically for Middle School, High School, College, or Professional levels. |
| 🔄 **Intelligent Feedback Loop** | The Evaluator dynamically signals the Quiz Master if a student scores below 80%. The Quiz Master then automatically creates **exactly 2 simpler review questions** on the weak topics. |
| 📂 **Shared State Sync** | Local processes synchronize via a lightweight state machine ([shared_state.json](file:///d:/Builds/new/study-band/shared_state.json)), updating the Streamlit UI reactively. |
| ⚡ **Zero-Friction Reset** | Re-run or clear sessions instantly to study new subjects in a clean environment. |

---

## 🏗️ Multi-Agent Architecture

The orchestration flows between a web UI, a local state coordinator, and the Band.ai cloud:

```
                  ┌──────────────────────────────┐
                  │        STREAMLIT UI          │
                  │   📚 Study  ❓ Quiz  🏆 Results│
                  └──────────────────────────────┘
                    │  ▲                    │  ▲
         Starts Topic  │ Updates State      │  │ Polls Score
                    ▼  │                    ▼  │
            ┌──────────────────────────────────┐
            │        shared_state.json         │
            │   (Central Status Coordinator)   │
            └──────────────────────────────────┘
              │  ▲        │  ▲        │  ▲        │  ▲
       Polls  │  │ Writes │  │ Writes │  │ Writes │  │ Writes
       Topic  ▼  │        ▼  │        ▼  │        ▼  │
┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  RESEARCHER    │ │   SIMPLIFIER   │ │  QUIZ MASTER   │ │   EVALUATOR    │
│  (local agent) │ │ (local agent)  │ │ (local agent)  │ │ (local agent)  │
└────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘
        │  ▲               │  ▲               │  ▲               │  ▲
        │  │               │  │               │  │               │  │
        ▼  │               ▼  │               ▼  │               ▼  │
┌─────────────────────────────────────────────────────────────────────────┐
│                           BAND.AI CLOUD ROOM                            │
│                                                                         │
│ @Simplifier ──▶ @QuizMaster ──▶ @Evaluator ──▶ @QuizMaster (Remedial)   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ How It Works & The Handoff Flow

### Step 1: Study Request
The student selects a topic (e.g. "Binary Trees") and an education level on the UI, and clicks **Start Studying**. The UI resets the state file and sets status to `"starting"`.

### Step 2: Handoff sequence on Band.ai
1. **Researcher Agent** detects `"starting"`, queries the selected model (via Groq or AI/ML API) to create exhaustive study notes, saves them to state, and broadcasts a message to the Band Room:
   `SIMPLIFY_NOTES: <notes>` mentioning `@Simplifier`.
2. **Simplifier Agent** receives the message, simplifies the notes to match the student's target education level, updates the state, and sends:
   `CREATE_QUIZ: <simplified_notes>` mentioning `@QuizMaster`.
3. **Quiz Master Agent** receives the simplified notes, compiles a 5-question multiple-choice quiz, saves it to state, and sends:
   `QUIZ_READY: 5 questions created.` mentioning `@Evaluator`.
4. **Evaluator Agent** waits for the student's answers from the UI, grades them, writes the teacher's evaluation to the state, and sends:
   `EVALUATION_DONE: <feedback>` mentioning `@QuizMaster`.

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit (Python) with custom premium layout and micro-animations.
* **Orchestration Layer:** [Band.ai SDK](https://app.band.ai) (running `LangGraphAdapter` and `AgentTools`).
* **LLM Engine:**
  * **Groq API** (Llama-3.3-70b-versatile, Llama-3.1-8b-instant, Mixtral-8x7b).
  * **AI/ML API** (Claude 3.5 Sonnet, Claude 4.5 Sonnet, Llama 3.3 Turbo, DeepSeek Chat, GPT-4o Mini).
* **State Management:** Local JSON filesystem syncing.

---

## 📁 Project Structure

```
study-band/
├── .env.example            # Environment variables template
├── agent_config.yaml.example # Band.ai agent credentials template
├── requirements.txt        # PIP dependencies
├── run_agents.py           # Process runner for all 4 agents
├── app.py                  # Streamlit frontend & state loader
├── shared_state.json       # Live state communication file
├── LICENSE                 # MIT License file
└── agents/
    ├── llm_helper.py       # Dual provider (Groq / AI/ML API) helper
    ├── researcher.py       # Structures academic concepts
    ├── simplifier.py       # Lowers reading level / adds analogies
    ├── quiz_master.py      # Creates questions & handles remedial tasks
    └── evaluator.py        # Validates answers and checks scores
```

---

## 🚀 Getting Started

### 1. Clone & Setup Virtual Environment
First, clone the repository and set up a Python virtual environment:
```bash
# Clone the repository
git clone https://github.com/adhipatya3552/StudyBand.git
cd StudyBand

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (Command Prompt):
venv\Scripts\activate.bat
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

# Install the dependencies inside the virtual environment
pip install -r requirements.txt
```

### 2. Configure Environment
1. Copy the configuration templates:
   ```bash
   cp .env.example .env
   cp agent_config.yaml.example agent_config.yaml
   ```
2. Edit `.env` and fill in your keys:
   - `GROQ_API_KEY`: Get from [console.groq.com](https://console.groq.com)
   - `BAND_ROOM_ID`: Create a room in Band.ai and copy the UUID from the URL
   - `AIMLAPI_API_KEY`: (Optional) Get from [aimlapi.com](https://aimlapi.com)

3. Edit `agent_config.yaml` and paste the credentials for your 4 External Agents registered on [app.band.ai/agents](https://app.band.ai/agents).

### 3. Running the System
Open **two separate terminal windows** and ensure the virtual environment is activated in both terminals:

* **Terminal 1 (Start the agents):**
  ```bash
  # Activate venv if not already done, then run:
  python run_agents.py
  ```
* **Terminal 2 (Start the Web UI):**
  ```bash
  # Activate venv if not already done, then run:
  streamlit run app.py
  ```

Your browser will automatically open to `http://localhost:8501`.

---

## 🔄 The Quiz Feedback Loop (Remedial Mode)

StudyBand includes a **real agent-to-agent collaboration loop** to help struggling students:

1. When a student submits answers, the **Evaluator** checks the score.
2. If the grade is below **80%** (e.g. 3/5 or lower), the Evaluator appends `[REMEDIAL_REQUIRED]` to the feedback.
3. The **Quiz Master** detects the tag, interrupts the normal flow, and generates **exactly 2 simpler review questions** focusing specifically on the concepts the student got wrong.
4. The UI displays an alert banner in the **Results** tab. The student can switch back to the **Quiz** tab to complete their review questions, which will then be graded again by the **Evaluator**.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](file:///d:/Builds/new/study-band/LICENSE) file for details.
