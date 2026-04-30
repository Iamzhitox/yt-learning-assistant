from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from src.infrastructure.config import LLM_PROVIDER, GENERATION_MODEL
from src.domain.prompts.supervisor_prompt_en import SUPERVISOR_PROMPT_EN

AGENTS = ["analyst", "teacher"]

SUPERVISOR_ROUTING_PROMPT = SUPERVISOR_PROMPT_EN


def get_supervisor_llm() -> BaseChatModel:
    return init_chat_model(model_provider=LLM_PROVIDER, model=GENERATION_MODEL)
