import asyncio
import json
import logging
import os
import sys
from dotenv import load_dotenv
from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config
from band.runtime.types import SessionConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.llm_helper import get_llm

logging.basicConfig(level=logging.INFO, format="[EVALUATOR] %(message)s")
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

async def main():
    agent_id, api_key = load_agent_config("evaluator")

    state = read_state()
    provider = state.get("provider", "groq")
    model_to_use = state.get("model", MODEL_NAME)
    llm = get_llm(provider, model_to_use, temperature=0.3)

    system_prompt = (
        "You are an Evaluator Agent. Check each quiz answer, give a score (e.g. '4 out of 5'), "
        "explain wrong answers briefly, and end with encouragement. "
        "If score < 80%, append [REMEDIAL_REQUIRED] at the end. If >= 80%, append [PASSED]."
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

        if "EVALUATE_ANSWERS:" in content:
            try:
                data_str = content.replace("EVALUATE_ANSWERS:", "").strip()
                data = json.loads(data_str)
                quiz = data.get("quiz", [])
                answers = data.get("answers", {})
                logger.info("Evaluating student answers...")
                update_state("status", "evaluating")

                state = read_state()
                edu_level = state.get("education_level", "College / University")

                prompt = (
                    f"Quiz Questions:\n{json.dumps(quiz, indent=2)}\n\n"
                    f"Student's Answers:\n{json.dumps(answers, indent=2)}\n\n"
                    f"Target Education Level: {edu_level}\n\n"
                    f"Evaluate the answers and give feedback."
                )
                provider = state.get("provider", "groq")
                model_to_use = state.get("model", MODEL_NAME)
                logger.info(f"Using provider: {provider}, model: {model_to_use}")
                llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=600)
                response = llm_call.invoke(prompt)
                evaluation = response.content

                needs_remedial = "[REMEDIAL_REQUIRED]" in evaluation
                update_state("evaluation", evaluation)
                update_state("needs_remedial", needs_remedial)
                if needs_remedial:
                    update_state("status", "remedial_requested")
                else:
                    update_state("status", "evaluated")

                try:
                    from band.runtime.tools import AgentTools
                    tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                    await tools.get_participants()
                    await tools.send_message(
                        content=f"EVALUATION_DONE:\n{evaluation}",
                        mentions=["@QuizMaster"]
                    )
                except Exception as ex:
                    logger.error(f"Failed to send message to Band room: {ex}")
                logger.info("Evaluation complete!")
            except Exception as e:
                logger.error(f"Evaluation error: {e}")
                update_state("status", "error")

    agent.on_message = handle_message

    # Watch state file for answers submitted from Streamlit UI
    async def watch_state():
        last_status = ""
        while True:
            try:
                state = read_state()
                if state.get("status") == "evaluating" and last_status != "evaluating":
                    last_status = "evaluating"
                    quiz = state.get("quiz", [])
                    answers = state.get("student_answers", {})
                    edu_level = state.get("education_level", "College / University")

                    if quiz and answers:
                        logger.info(f"Picked up answers from UI. Evaluating for level: {edu_level}")

                        prompt = (
                            f"Quiz Questions:\n{json.dumps(quiz, indent=2)}\n\n"
                            f"Student's Answers:\n{json.dumps(answers, indent=2)}\n\n"
                            f"Target Education Level: {edu_level}\n\n"
                            f"Evaluate the answers and give feedback."
                        )
                        provider = state.get("provider", "groq")
                        model_to_use = state.get("model", MODEL_NAME)
                        logger.info(f"Using provider: {provider}, model: {model_to_use}")
                        llm_call = get_llm(provider, model_to_use, temperature=0.3, max_tokens=600)
                        response = llm_call.invoke(prompt)
                        evaluation = response.content

                        needs_remedial = "[REMEDIAL_REQUIRED]" in evaluation
                        update_state("evaluation", evaluation)
                        update_state("needs_remedial", needs_remedial)
                        if needs_remedial:
                            update_state("status", "remedial_requested")
                        else:
                            update_state("status", "evaluated")

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
                                content=f"EVALUATION_DONE:\n{evaluation}",
                                mentions=["@QuizMaster"]
                            )
                        except Exception as ex:
                            logger.error(f"Failed to send message to Band room: {ex}")
                        logger.info("Evaluation done and posted to Band room.")
                elif state.get("status") != "evaluating":
                    last_status = state.get("status", "")
            except Exception as e:
                logger.error(f"Watch state error: {e}")
            await asyncio.sleep(0.5)

    logger.info("Evaluator Agent started and listening...")
    await asyncio.gather(agent.run(), watch_state())

if __name__ == "__main__":
    asyncio.run(main())
