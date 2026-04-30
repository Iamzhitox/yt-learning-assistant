from typing import cast
from langchain.embeddings import init_embeddings as _init_embeddings
from langchain.chat_models import BaseChatModel


def init_chat_model(
    model: str, *, provider: str | None = None, **kwargs
) -> BaseChatModel:
    """
    Extended init_chat_model that supports Voyage AI provider.

    For provider="voyage", uses VoyageAIEmbeddings directly.
    For other providers, delegates to langchain.embeddings.init_embeddings.
    """
    return cast(
        BaseChatModel, _init_embeddings(model=model, provider=provider, **kwargs)
    )
