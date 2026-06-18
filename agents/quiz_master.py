import asyncio
import json
import logging
import os
import re
import sys
from dotenv import load_dotenv
from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config
from band.runtime.types import SessionConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.llm_helper import get_llm

logging.basicConfig(level=logging.INFO, format="[QUIZMASTER] %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

# Load configuration from environment variables
ROOM_ID = os.getenv("BAND_ROOM_ID", "paste-your-band-room-id-here")
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def update_state(key, value):
    try:
        with open("shared_state.json", "r") as f:
            state = json.load(f)
        state[key] = value
        with open("shared_state.json", "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"State update error: {e}")

def read_state():
    try:
        with open("shared_state.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"State read error: {e}")
        return {}

def fallback_quiz(topic):
    clean_topic = topic or "the study topic"
    return [
        {
            "question": f"What is the best description of {clean_topic}?",
            "options": [
                f"A) A core concept related to {clean_topic}",
                "B) An unrelated historical date",
                "C) A random list of facts",
                "D) A type of file format",
            ],
            "answer": "A",
        },
        {
            "question": f"Why is understanding {clean_topic} useful?",
            "options": [
                "A) It helps connect ideas and solve related problems",
                "B) It removes the need to practice",
                "C) It is only useful for memorizing definitions",
                "D) It has no practical use",
            ],
            "answer": "A",
        },
        {
            "question": f"What should you do when learning {clean_topic}?",
            "options": [
                "A) Break it into smaller ideas and test yourself",
                "B) Skip examples",
                "C) Memorize without understanding",
                "D) Avoid review questions",
            ],
            "answer": "A",
        },
    ]

def extract_json(text, topic=""):
    """Try to extract a JSON array from LLM response text."""
    try:
        return json.loads(text)
    except:
        pass
    # Try to find JSON array inside the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return fallback_quiz(topic)

async def main():
    agent_id, api_key = load_agent_config("quiz_master")

    state = read_state()
    provider = state.get("provider", "groq")
    model_to_use = state.get("model", MODEL_NAME)
    llm = get_llm(provider, model_to_use, temperature=0.3)

    system_prompt = (
        "You are a Quiz Master Agent. Create exactly 3 MCQ questions from study notes.\n"
        "Return ONLY a valid JSON array, no extra text. Format:\n"
        '[{"question": "Q?", "options": ["A) x", "B) y", "C) z", "D) w"], "answer": "A"}, ...]'
    )

    adapter = LangGraphAdapter(llm=llm, custom_section=system_prompt)
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        session_config=SessionConfig(enable_context_hydration=False),
    )

    async def handle_message(message):
        content = message.content if hasattr(message, "content") else str(message)

        if "CREATE_QUIZ:" in content:
            # Notes are in shared_state.json - read from there (avoids large Band messages causing 413 errors)
            state = read_state()
            notes = state.get("simple_notes") or state.get("notes", "")
            if not notes:
                logger.warning("Received CREATE_QUIZ signal but no notes found in state file.")
                return
            logger.info("Creating quiz from state file notes...")
            update_state("status", "creating_quiz")

            edu_level = state.get("education_level", "College / University")
            logger.info(f"Target education level for quiz: {edu_level}")

            try:
                provider = state.get("provider", "groq")
                model_to_use = state.get("model", MODEL_NAME)
                logger.info(f"Using provider: {provider}, model: {model_to_use}")
                llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=500)

                previous_quizzes = state.get("previous_quizzes", [])
                avoid_questions = []
                for old_quiz in previous_quizzes:
                    for q in old_quiz:
                        if isinstance(q, dict) and q.get("question"):
                            avoid_questions.append(q.get("question"))
                
                avoid_prompt = ""
                if avoid_questions:
                    avoid_prompt = f"\n\nIMPORTANT: Do NOT repeat or include any of these previous questions:\n" + "\n".join(f"- {q}" for q in avoid_questions)

                response = llm_call.invoke(
                    f"Create exactly 3 MCQ questions as JSON only.\n"
                    f"Level: {edu_level}\n"
                    f"Notes:\n{notes[:900]}{avoid_prompt[:400]}"
                )
                quiz = extract_json(response.content, state.get("topic", ""))
                update_state("quiz", quiz)
                update_state("status", "quiz_ready")
                logger.info(f"Quiz created with {len(quiz)} questions. Notifying Evaluator...")

                try:
                    from band.runtime.tools import AgentTools
                    tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                    await tools.get_participants()
                    await tools.send_message(
                        content="QUIZ_READY: 3 questions created. Waiting for student answers.",
                        mentions=["@Evaluator"]
                    )
                except Exception as ex:
                    logger.error(f"Failed to send message to Band room: {ex}")
            except Exception as e:
                logger.error(f"LLM error: {e}")
                update_state("status", "error")

        elif "EVALUATION_DONE:" in content:
            if "[REMEDIAL_REQUIRED]" in content:
                logger.info("Evaluation indicates student needs remedial help. Generating 2 simpler review questions...")
                update_state("status", "creating_remedial")

                state = read_state()
                notes = state.get("simple_notes") or state.get("notes", "")
                edu_level = state.get("education_level", "College / University")

                try:
                    provider = state.get("provider", "groq")
                    model_to_use = state.get("model", MODEL_NAME)
                    logger.info(f"Using provider: {provider}, model: {model_to_use}")
                    llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=500)

                    response = llm_call.invoke(
                        f"Based on the following study notes and student performance evaluation, "
                        f"generate EXACTLY 2 simpler review MCQ questions. Focus on the concepts the student struggled with.\n\n"
                        f"Study Notes:\n{notes[:900]}\n\n"
                        f"Evaluation Feedback:\n{content[:500]}\n\n"
                        f"Target Education Level: {edu_level}\n\n"
                        f"Return ONLY a valid JSON array of exactly 2 questions. No extra text, no markdown wrapper. Format exactly like this:\n"
                        f'[{"question": "What is X?", "options": ["A) First", "B) Second", "C) Third", "D) Fourth"], "answer": "A"}, ...]'
                    )
                    quiz = extract_json(response.content, state.get("topic", ""))
                    update_state("quiz", quiz)
                    update_state("student_answers", {})
                    update_state("status", "quiz_ready")
                    logger.info(f"Remedial quiz created with {len(quiz)} questions.")

                    try:
                        from band.runtime.tools import AgentTools
                        tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                        await tools.get_participants()
                        await tools.send_message(
                            content="REMEDIAL_QUIZ_READY: 2 simpler review questions created. Please go to the Quiz tab to review.",
                            mentions=["@Evaluator"]
                        )
                    except Exception as ex:
                        logger.error(f"Failed to send message to Band room: {ex}")
                except Exception as e:
                    logger.error(f"LLM error during remedial generation: {e}")
                    update_state("status", "error")

    agent.on_message = handle_message

    async def watch_state():
        last_status = ""
        while True:
            try:
                state = read_state()
                if state.get("status") == "simplified" and last_status != "simplified":
                    last_status = "simplified"
                    notes = state.get("simple_notes", "")
                    edu_level = state.get("education_level", "College / University")
                    if notes:
                        logger.info(f"Picked up simplified notes. Creating quiz for level: {edu_level}")
                        update_state("status", "creating_quiz")

                        provider = state.get("provider", "groq")
                        model_to_use = state.get("model", MODEL_NAME)
                        logger.info(f"Using provider: {provider}, model: {model_to_use}")
                        llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=500)

                        previous_quizzes = state.get("previous_quizzes", [])
                        avoid_questions = []
                        for old_quiz in previous_quizzes:
                            for q in old_quiz:
                                if isinstance(q, dict) and q.get("question"):
                                    avoid_questions.append(q.get("question"))
                        
                        avoid_prompt = ""
                        if avoid_questions:
                            avoid_prompt = f"\n\nIMPORTANT: Do NOT repeat or include any of these previous questions:\n" + "\n".join(f"- {q}" for q in avoid_questions)

                        response = llm_call.invoke(
                            f"Create exactly 3 MCQ questions as JSON only.\n"
                            f"Level: {edu_level}\n"
                            f"Notes:\n{notes[:900]}{avoid_prompt[:400]}"
                        )
                        quiz = extract_json(response.content, state.get("topic", ""))
                        update_state("quiz", quiz)
                        update_state("status", "quiz_ready")

                        # Wait for agent runtime to connect before sending message
                        while True:
                            try:
                                _ = agent.runtime.link
                                break
                            except RuntimeError:
                                await asyncio.sleep(0.2)

                        try:
                            from band.runtime.tools import AgentTools
                            tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                            await tools.get_participants()
                            await tools.send_message(
                                content="QUIZ_READY: Questions created. Waiting for answers.",
                                mentions=["@Evaluator"]
                            )
                        except Exception as ex:
                            logger.error(f"Failed to send message to Band room: {ex}")
                        logger.info("Quiz ready. Evaluator notified via Band.")
                
                elif state.get("status") == "remedial_requested" and last_status != "remedial_requested":
                    last_status = "remedial_requested"
                    evaluation = state.get("evaluation", "")
                    notes = state.get("simple_notes") or state.get("notes", "")
                    edu_level = state.get("education_level", "College / University")

                    logger.info("State indicates remedial quiz requested. Generating 2 review questions...")
                    update_state("status", "creating_quiz")

                    try:
                        provider = state.get("provider", "groq")
                        model_to_use = state.get("model", MODEL_NAME)
                        logger.info(f"Using provider: {provider}, model: {model_to_use}")
                        llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=500)

                        response = llm_call.invoke(
                            f"Based on the following study notes and student performance evaluation, "
                            f"generate EXACTLY 2 simpler review MCQ questions. Focus on the concepts the student struggled with.\n\n"
                            f"Study Notes:\n{notes[:900]}\n\n"
                            f"Evaluation Feedback:\n{evaluation[:500]}\n\n"
                            f"Target Education Level: {edu_level}\n\n"
                            f"Return ONLY a valid JSON array of exactly 2 questions. No extra text, no markdown wrapper. Format exactly like this:\n"
                            f'[{"question": "What is X?", "options": ["A) First", "B) Second", "C) Third", "D) Fourth"], "answer": "A"}, ...]'
                        )
                        quiz = extract_json(response.content, state.get("topic", ""))
                        update_state("quiz", quiz)
                        update_state("student_answers", {})
                        update_state("status", "quiz_ready")

                        # Wait for agent runtime to connect before sending message
                        while True:
                            try:
                                _ = agent.runtime.link
                                break
                            except RuntimeError:
                                await asyncio.sleep(0.2)

                        try:
                            from band.runtime.tools import AgentTools
                            tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                            await tools.get_participants()
                            await tools.send_message(
                                content="REMEDIAL_QUIZ_READY: 2 simpler review questions created. Please go to the Quiz tab to review.",
                                mentions=["@Evaluator"]
                            )
                        except Exception as ex:
                            logger.error(f"Failed to send message to Band room: {ex}")
                        logger.info("Remedial quiz ready and posted to Band.")
                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        update_state("status", "error")

                elif state.get("status") not in ["simplified", "remedial_requested"]:
                    last_status = state.get("status", "")
            except Exception as e:
                logger.error(f"Watch state error: {e}")
            await asyncio.sleep(0.5)

    logger.info("QuizMaster Agent started and listening...")
    await asyncio.gather(agent.run(), watch_state())

if __name__ == "__main__":
    asyncio.run(main())
