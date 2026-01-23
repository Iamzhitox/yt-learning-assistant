from urllib.parse import urlparse, parse_qs

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_chroma import Chroma
from langchain_classic.chat_models import init_chat_model
from langchain_classic.retrievers import EnsembleRetriever, MultiQueryRetriever
from langchain_community.retrievers import BM25Retriever

from src.domain.exceptions import (
    InvalidPlaylistUrlError,
    InvalidEmbeddingModelError,
    PlaylistDocumentsNotFoundError,
    EmptyPlaylistDocumentsError,
    VectorStoreInitializationError,
    LLMInitializationError,
)
from src.infrastructure.extensions.embeddings import init_embeddings
from src.infrastructure.config import (
    PERSIST_DIR,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LLM_PROVIDER,
    QUERY_MODEL,
    GENERATION_MODEL,
    SEARCH_K,
    SEARCH_TYPE,
)
from src.prompts import SYSTEM_PROMPT, HUMAN_PROMPT


def get_playlist_id_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    if "list" in query_params:
        playlist_id = query_params["list"][0]
        return playlist_id

    raise InvalidPlaylistUrlError(url)


def playlist_exist(vector_store: Chroma, playlist_id: str) -> bool:
    try:
        results = vector_store.get(where={"playlist_id": playlist_id})
        ids = results.get("ids", [])
        return ids is not None and len(ids) > 0
    except Exception as e:
        print(f"Error checking playlist existence: {e}")
        return False


def init_vector_db() -> Chroma:
    embedding_model = init_embeddings(
        provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL
    )

    if not isinstance(embedding_model, Embeddings):
        raise InvalidEmbeddingModelError(type(embedding_model))

    try:
        vector_store = Chroma(
            persist_directory=PERSIST_DIR, embedding_function=embedding_model
        )
        return vector_store
    except Exception as e:
        raise VectorStoreInitializationError(PERSIST_DIR, e) from e


def get_similarity_retriever(vector_store: Chroma, playlist_id: str) -> BaseRetriever:
    return vector_store.as_retriever(
        search_type=SEARCH_TYPE,
        search_kwargs={"k": SEARCH_K, "filter": {"playlist_id": playlist_id}},
    )


def get_ensemble_retriever(
    llm: BaseChatModel, vector_store: Chroma, retriever: BaseRetriever, playlist_id: str
) -> BaseRetriever:

    docs = vector_store.get(where={"playlist_id": playlist_id})["documents"]

    if not docs or len(docs) == 0:
        raise PlaylistDocumentsNotFoundError(playlist_id)

    docs = [doc for doc in docs if doc and doc.strip()]

    if len(docs) == 0:
        raise EmptyPlaylistDocumentsError(playlist_id)

    bm25_retriever = BM25Retriever.from_texts(docs)
    bm25_retriever.k = SEARCH_K

    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, retriever], weights=[0.4, 0.6]
    )

    return MultiQueryRetriever.from_llm(retriever=ensemble_retriever, llm=llm)


def get_query_model() -> BaseChatModel:
    try:
        return init_chat_model(model_provider=LLM_PROVIDER, model=QUERY_MODEL)
    except Exception as e:
        raise LLMInitializationError(LLM_PROVIDER, QUERY_MODEL, e) from e


def get_llm_chain() -> Runnable:
    try:
        llm = init_chat_model(model_provider=LLM_PROVIDER, model=GENERATION_MODEL)
    except Exception as e:
        raise LLMInitializationError(LLM_PROVIDER, GENERATION_MODEL, e) from e

    template = ChatPromptTemplate.from_messages([SYSTEM_PROMPT, HUMAN_PROMPT])
    return template | llm


def format_chunks_for_prompt(relevant_chunks: list[Document]) -> str:
    formatted_chunks = ""
    for idx, chunk in enumerate(relevant_chunks):
        formatted_chunks += f"{"" if idx == 0 else '\n'}- '{chunk.metadata.get("video_title")}' (ID: {chunk.metadata.get("video_id")}) - ({seconds_to_hms(chunk.metadata.get("start_seconds"))}): '{chunk.page_content}'"
    return formatted_chunks


def seconds_to_hms(seconds: float | int | None) -> str:
    if seconds is None:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
