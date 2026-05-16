from urllib.parse import urlparse, parse_qs
from src.domain.models.youtube import YoutubePlaylist
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langchain_chroma import Chroma
from langchain.chat_models import init_chat_model
from langchain_classic.retrievers import EnsembleRetriever, MultiQueryRetriever
from langchain_community.retrievers import BM25Retriever
from src.application.services import YouTubePlaylistLoader
from src.domain.exceptions import (
    InvalidPlaylistUrlError,
    InvalidEmbeddingModelError,
    PlaylistDocumentsNotFoundError,
    EmptyPlaylistDocumentsError,
    VectorStoreInitializationError,
    LLMInitializationError,
)
from src.infrastructure.extensions.embeddings import init_embeddings
from langchain_core.callbacks import BaseCallbackHandler
from src.infrastructure.config import (
    PERSIST_DIR,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LLM_PROVIDER,
    QUERY_MODEL,
    SEARCH_K,
    SEARCH_TYPE,
    DISPLAY_OBSERVATIONS,
)
from src.domain.exceptions import (
    PlaylistLoadError,
    TranscriptLoadError,
    VectorStoreWriteError,
)
from chromadb.api.types import Where


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


def scope_filter(playlist_id: str, video_ids: list[str] = []) -> Where:
    if not video_ids:
        return {"playlist_id": playlist_id}

    if len(video_ids) == 1:
        return {"$and": [{"playlist_id": playlist_id}, {"video_id": video_ids[0]}]}

    return {
        "$and": [
            {"playlist_id": playlist_id},
            {"$or": [{"video_id": video_id} for video_id in video_ids]},
        ]
    }


def gen_retriever(vector_store: Chroma, playlist_id: str, video_ids: list[str] = []):
    llm = get_query_model()

    base_retriever = get_similarity_retriever(
        vector_store=vector_store, playlist_id=playlist_id, video_ids=video_ids
    )
    retriever = get_ensemble_retriever(
        llm=llm,
        vector_store=vector_store,
        retriever=base_retriever,
        playlist_id=playlist_id,
        video_ids=video_ids,
    )

    return retriever


def get_similarity_retriever(
    vector_store: Chroma, playlist_id: str, video_ids: list[str] = []
) -> BaseRetriever:
    retriever_filter = scope_filter(playlist_id, video_ids)
    return vector_store.as_retriever(
        search_type=SEARCH_TYPE,
        search_kwargs={"k": SEARCH_K, "filter": retriever_filter},
    )


def get_ensemble_retriever(
    llm: BaseChatModel,
    vector_store: Chroma,
    retriever: BaseRetriever,
    playlist_id: str,
    video_ids: list[str] = [],
) -> BaseRetriever:
    retriever_filter = scope_filter(playlist_id, video_ids)
    docs = vector_store.get(where=retriever_filter)["documents"]

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


async def get_playlist_details(
    yt_service: YouTubePlaylistLoader, playlist_id: str, is_loaded: bool
):
    try:
        yt_service.load_playlist_details()
        yt_service.load_video_details()
    except Exception as e:
        raise PlaylistLoadError(playlist_id, e) from e

    if not is_loaded:
        try:
            await yt_service.load_transcript_videos()
        except Exception as e:
            raise TranscriptLoadError(playlist_id, e) from e

    return yt_service.build()


def save_transcripts(vector_store: Chroma, playlist: YoutubePlaylist, playlist_id: str):
    if playlist:
        try:
            for video in playlist.videos:
                vector_store.add_documents(video.transcript)
        except Exception as e:
            raise VectorStoreWriteError(playlist_id, e) from e


# ANSI escape codes used to color observation logs so they're visually distinct from LLM responses in the console.
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


class AgentTracer(BaseCallbackHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        name = serialized.get("name", "?")
        print(f"{_CYAN}{_DIM}\n[tool call] {name}  →  {input_str}{_RESET}")

    def on_tool_end(self, output, **kwargs):
        preview = str(output)[:300]
        print(f"{_GREEN}{_DIM}[tool result] {preview}{'...' if len(str(output)) > 300 else ''}{_RESET}")

    def on_chain_start(self, serialized, inputs, **kwargs):
        if not serialized:
            return
        name = serialized.get("name", "")
        if name in ("agent_manager", "agent_analyst", "agent_teacher"):
            print(f"{_YELLOW}{_DIM}\n[node] {name}{_RESET}")


def get_callbacks() -> list:
    return [AgentTracer()] if DISPLAY_OBSERVATIONS else []
