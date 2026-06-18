import os
import logging
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

def get_llm(provider: str, model: str, temperature: float = 0.5, max_tokens: int = None):
    """
    Dynamically returns a LangChain chat model based on the provider and model name.
    Supported providers: 'groq', 'aimlapi'

    Args:
        max_tokens: Cap on tokens to generate. Critical for Groq free tier (6,000 TPM).
                    Set this on every direct .invoke() call to avoid 429 rate-limit errors
                    when multiple agents fire simultaneously.
    """
    provider = (provider or "groq").strip().lower()
    model = model.strip()
    
    if provider == "aimlapi":
        api_key = os.getenv("AIMLAPI_API_KEY")
        if not api_key or api_key == "your_aimlapi_key_here":
            logger.error("AIMLAPI_API_KEY is not set or is a placeholder in .env!")
            raise ValueError("AIMLAPI_API_KEY is not set in .env")
        logger.info(f"Instantiating ChatOpenAI via AIML API with model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.aimlapi.com/v1",
            temperature=temperature,
            max_tokens=max_tokens or 2048,
        )
    else:
        # Default to Groq provider
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "gsk_your_key_here":
            logger.error("GROQ_API_KEY is not set or is a placeholder in .env!")
            raise ValueError("GROQ_API_KEY is not set in .env")
        logger.info(f"Instantiating ChatGroq with model: {model}")
        kwargs = dict(model=model, api_key=api_key, temperature=temperature)
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatGroq(**kwargs)

