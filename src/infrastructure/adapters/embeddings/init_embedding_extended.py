from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import Runnable
from langchain_classic.embeddings import init_embeddings as _init_embeddings

from langchain_voyageai import VoyageAIEmbeddings


def init_embeddings(model: str, *, provider: str | None = None, **kwargs) -> Embeddings | Runnable[Any, list[float]]:
    """
    Extended init_embeddings that supports Voyage AI provider.

    For provider="voyage", uses VoyageAIEmbeddings directly.
    For other providers, delegates to langchain_classic.embeddings.init_embeddings.
    """
    if provider and provider.lower() == "voyage":
        return VoyageAIEmbeddings(model=model, **kwargs)

    return _init_embeddings(model=model, provider=provider, **kwargs)
