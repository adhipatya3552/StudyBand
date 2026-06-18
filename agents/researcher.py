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

logging.basicConfig(level=logging.INFO, format="[RESEARCHER] %(message)s")
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
    agent_id, api_key = load_agent_config("researcher")

    state = read_state()
    provider = state.get("provider", "groq")
    model_to_use = state.get("model", MODEL_NAME)
    llm = get_llm(provider, model_to_use, temperature=0.5)

    system_prompt = (
        "You are a Researcher Agent. When given a topic, write concise study notes with: "
        "1) Overview, 2) 5 Key Concepts, 3) 3 examples, 4) Summary. "
        "Be brief and educational."
    )

    adapter = LangGraphAdapter(
        llm=llm,
        custom_section=system_prompt,
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        session_config=SessionConfig(enable_context_hydration=False),
    )

    async def handle_message(message):
        content = message.content if hasattr(message, "content") else str(message)

        if "STUDY_TOPIC:" in content:
            topic = content.replace("STUDY_TOPIC:", "").strip()
            logger.info(f"Received topic: {topic}")
            update_state("status", "researching")
            update_state("topic", topic)

            state = read_state()
            edu_level = state.get("education_level", "College / University")
            logger.info(f"Education level target: {edu_level}")

            try:
                provider = state.get("provider", "groq")
                model_to_use = state.get("model", MODEL_NAME)
                logger.info(f"Using provider: {provider}, model: {model_to_use}")
                llm_call = get_llm(provider, model_to_use, temperature=0.5, max_tokens=800)
                response = llm_call.invoke(
                    f"Create concise study notes about this topic: {topic}\n"
                    f"Target Education Level: {edu_level}\n"
                    f"Follow your system instructions for formatting. Be concise to stay within token limits."
                )
                notes = response.content
                update_state("notes", notes)
                update_state("status", "researched")
                logger.info("Research complete. Sending to Simplifier...")

                # Send a short signal - actual notes are in shared_state.json (avoids 413 token errors)
                try:
                    from band.runtime.tools import AgentTools
                    tools = AgentTools(room_id=ROOM_ID, rest=agent.runtime.link.rest)
                    await tools.get_participants()
                    await tools.send_message(
                        content="SIMPLIFY_NOTES: ready — notes saved to shared_state.json",
                        mentions=["@Simplifier"]
                    )
                except Exception as ex:
                    logger.error(f"Failed to send signal to Band room: {ex}")
            except Exception as e:
                logger.error(f"LLM error: {e}")
                update_state("status", "error")

    agent.on_message = handle_message

    # Also watch shared_state.json for new topics from Streamlit UI
    async def watch_state():
        last_status = ""
        while True:
            try:
                state = read_state()
                status = state.get("status")
                if status == "starting" and last_status != "starting":
                    last_status = "starting"
                    topic = state.get("topic")
                    edu_level = state.get("education_level", "College / University")
                    if topic:
                        logger.info(f"Picked up new topic from UI: {topic} at level {edu_level}")
                        update_state("status", "researching")

                        try:
                            provider = state.get("provider", "groq")
                            model_to_use = state.get("model", MODEL_NAME)
                            logger.info(f"Using provider: {provider}, model: {model_to_use}")
                            llm_call = get_llm(provider, model_to_use, temperature=0.5, max_tokens=800)
                            response = llm_call.invoke(
                                f"Create concise study notes about: {topic}\n"
                                f"Target Education Level: {edu_level}\n"
                                f"Include Overview, 5 Key Concepts, 3 examples, Summary. Be concise to stay within token limits."
                            )
                            notes = response.content
                            update_state("notes", notes)
                            update_state("status", "researched")

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
                                    content="SIMPLIFY_NOTES: ready — notes saved to shared_state.json",
                                    mentions=["@Simplifier"]
                                )
                            except Exception as ex:
                                logger.error(f"Failed to send signal to Band room: {ex}")
                            logger.info("Research done. Passed to Simplifier via Band.")
                        except Exception as inner_e:
                            logger.error(f"Error during research execution: {inner_e}")
                            update_state("status", "error")
                elif status != "starting":
                    last_status = status
            except Exception as e:
                logger.error(f"Watch state error: {e}")
            await asyncio.sleep(0.5)

    logger.info("Researcher Agent started and listening...")
    await asyncio.gather(agent.run(), watch_state())

if __name__ == "__main__":
    asyncio.run(main())
