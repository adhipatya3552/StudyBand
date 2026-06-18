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

logging.basicConfig(level=logging.INFO, format="[SIMPLIFIER] %(message)s")
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
    agent_id, api_key = load_agent_config("simplifier")

    state = read_state()
    provider = state.get("provider", "groq")
    model_to_use = state.get("model", MODEL_NAME)
    llm = get_llm(provider, model_to_use, temperature=0.4)

    system_prompt = (
        "You are a Simplifier Agent. Rewrite study notes to match the student's education level. "
        "Be friendly, clear, and concise."
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

        if "SIMPLIFY_NOTES:" in content:
            # Notes are in shared_state.json - read from there (avoids large Band messages causing 413 errors)
            state = read_state()
            notes = state.get("notes", "")
            if not notes:
                logger.warning("Received SIMPLIFY_NOTES signal but no notes found in state file.")
                return
            logger.info("Received simplification signal. Reading notes from state file...")
            update_state("status", "simplifying")

            edu_level = state.get("education_level", "College / University")
            logger.info(f"Target education level for simplification: {edu_level}")

            try:
                provider = state.get("provider", "groq")
                model_to_use = state.get("model", MODEL_NAME)
                logger.info(f"Using provider: {provider}, model: {model_to_use}")
                llm_call = get_llm(provider, model_to_use, temperature=0.4, max_tokens=600)
                response = llm_call.invoke(
                    f"Simplify these study notes for a student studying at this level: '{edu_level}'.\n"
                    f"Be concise. Aim for ~400 tokens output max:\n\n{notes[:2000]}"
                )
                simple_notes = response.content
                update_state("simple_notes", simple_notes)
                update_state("status", "simplified")
                logger.info("Simplification done. Sending signal to QuizMaster...")

                # Send a short signal - actual notes are in shared_state.json
                try:
                    from band.runtime.tools import AgentTools
                    tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                    await tools.get_participants()
                    await tools.send_message(
                        content="CREATE_QUIZ: ready — simplified notes saved to shared_state.json",
                        mentions=["@QuizMaster"]
                    )
                except Exception as ex:
                    logger.error(f"Failed to send signal to Band room: {ex}")
            except Exception as e:
                logger.error(f"LLM error: {e}")
                update_state("status", "error")

    agent.on_message = handle_message

    # Watch state file as backup trigger
    async def watch_state():
        last_status = ""
        while True:
            try:
                state = read_state()
                if state.get("status") == "researched" and last_status != "researched":
                    last_status = "researched"
                    notes = state.get("notes", "")
                    edu_level = state.get("education_level", "College / University")
                    if notes:
                        logger.info(f"Picked up researched notes from state file. Simplification level: {edu_level}")
                        update_state("status", "simplifying")

                        provider = state.get("provider", "groq")
                        model_to_use = state.get("model", MODEL_NAME)
                        logger.info(f"Using provider: {provider}, model: {model_to_use}")
                        llm_call = get_llm(provider, model_to_use, temperature=0.4, max_tokens=600)
                        response = llm_call.invoke(
                            f"Simplify these study notes for a student studying at this level: '{edu_level}'.\n"
                            f"Be concise. Aim for ~400 tokens output max:\n\n{notes[:2000]}"
                        )
                        simple_notes = response.content
                        update_state("simple_notes", simple_notes)
                        update_state("status", "simplified")

                        # Wait for agent runtime to connect before sending message
                        while True:
                            try:
                                _ = agent.runtime.link
                                break
                            except RuntimeError:
                                await asyncio.sleep(0.2)

                        # Send a short signal - actual notes are in shared_state.json
                        try:
                            from band.runtime.tools import AgentTools
                            tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                            await tools.get_participants()
                            await tools.send_message(
                                content="CREATE_QUIZ: ready — simplified notes saved to shared_state.json",
                                mentions=["@QuizMaster"]
                            )
                        except Exception as ex:
                            logger.error(f"Failed to send signal to Band room: {ex}")
                        logger.info("Simplified. Passed to QuizMaster via Band.")
                elif state.get("status") != "researched":
                    last_status = state.get("status", "")
            except Exception as e:
                logger.error(f"Watch state error: {e}")
            await asyncio.sleep(0.5)

    logger.info("Simplifier Agent started and listening...")
    await asyncio.gather(agent.run(), watch_state())

if __name__ == "__main__":
    asyncio.run(main())
