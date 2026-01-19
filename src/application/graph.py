# region IMPORTS
import asyncio
from typing import TypedDict, NotRequired
from urllib.parse import urlparse, parse_qs

from langgraph.graph import StateGraph, START, END
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

from src.domain.models import YoutubePlaylist
from src.domain.exceptions import (
    InvalidPlaylistUrlError,
    InvalidEmbeddingModelError,
    PlaylistDocumentsNotFoundError,
    EmptyPlaylistDocumentsError,
    VectorStoreInitializationError,
    LLMInitializationError,
    PlaylistLoadError,
    TranscriptLoadError,
    VectorStoreWriteError,
    LLMStreamError,
    RetrieverError,
)
from src.application.services import YouTubePlaylistLoader
from src.infrastructure.adapters.embeddings import init_embeddings
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


# region STATE DEF
class State(TypedDict):
    query_llm: BaseChatModel
    query: NotRequired[str]
    playlist_id: NotRequired[str]
    vector_store: Chroma
    retriever: NotRequired[BaseRetriever]
    yt_playlist: NotRequired[YoutubePlaylist]
    yt_playlist_service: NotRequired[YouTubePlaylistLoader]
    llm_chain: Runnable
    retrieved_chunks: NotRequired[list[Document]]
    ai_answer: NotRequired[str]


# region HELPERS


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


def seconds_to_hms(seconds):
    if seconds is None:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# region NODES
def get_playlist_id(state: State):
    yt_playlist_url = input(
        f"{'='*50}\n\nChoose a playlist for the model to learn from:\n\n{'='*50}\n\n- "
    )
    yt_playlist_id = get_playlist_id_from_url(yt_playlist_url)
    print("\n\n")

    return {"playlist_id": yt_playlist_id}


def init_retriever(state: State):
    vector_store = state.get("vector_store")
    llm = state.get("query_llm")
    playlist_id = state.get("playlist_id") or ""

    retriever = get_similarity_retriever(
        vector_store=vector_store, playlist_id=playlist_id
    )
    retriever = get_ensemble_retriever(
        llm=llm, vector_store=vector_store, retriever=retriever, playlist_id=playlist_id
    )

    return {"retriever": retriever}


def get_playlist_details(state: State):
    playlist_id = state.get("playlist_id") or ""

    try:
        yt_service = YouTubePlaylistLoader(playlist_id=playlist_id)
        yt_service.load_playlist_details()
        yt_service.load_video_details()
    except Exception as e:
        raise PlaylistLoadError(playlist_id, e) from e

    return {"yt_playlist_service": yt_service}


def should_load_or_save(state: State) -> str:
    vector_store = state.get("vector_store")
    playlist_id = state.get("playlist_id") or ""

    if playlist_exist(vector_store=vector_store, playlist_id=playlist_id):
        return "load_existing"
    return "load_new"


def should_save_to_db(state: State) -> str:
    vector_store = state.get("vector_store")
    playlist_id = state.get("playlist_id") or ""

    if playlist_exist(vector_store=vector_store, playlist_id=playlist_id):
        return "skip_save"
    return "save_to_db"


async def get_video_transcripts(state: State):
    yt_service = state.get("yt_playlist_service")
    playlist_id = state.get("playlist_id") or ""

    if yt_service:
        try:
            await yt_service.load_transcript_videos()
        except Exception as e:
            raise TranscriptLoadError(playlist_id, e) from e

    return {"yt_playlist_service": yt_service}


def build_playlist(state: State):
    yt_service = state.get("yt_playlist_service")
    if yt_service:
        yt_playlist = yt_service.build()
        return {"yt_playlist": yt_playlist}


def save_transcripts_in_vector_db(state: State):
    vector_store = state.get("vector_store")
    playlist = state.get("yt_playlist")
    playlist_id = state.get("playlist_id") or ""

    if playlist:
        try:
            for video in playlist.videos:
                vector_store.add_documents(video.transcript)
        except Exception as e:
            raise VectorStoreWriteError(playlist_id, e) from e


def get_query(state: State):
    playlist = state.get("yt_playlist")
    playlist_title = playlist.title if playlist else ""

    msg = "Ready! Ask me a question about"
    human_question = input(f"{'='*40}\n\n{msg} \"{playlist_title}\":\n\n{'='*40}\n\n- ")

    return {"query": human_question}


def get_relevant_chunks(state: State):
    retriever = state.get("retriever")
    question = state.get("query", "")

    if not retriever:
        return {"retrieved_chunks": []}

    try:
        relevant_chunks = retriever.invoke(question)
    except Exception as e:
        raise RetrieverError(question, e) from e

    return {"retrieved_chunks": relevant_chunks}


def ask_answer_llm(state: State):
    relevant_lines = state.get("retrieved_chunks")
    chain_llm = state.get("llm_chain")
    full_answer = ""

    print("\n\n\n", end="", flush=True)
    if relevant_lines:
        try:
            for chunk in chain_llm.stream(
                {
                    "question": state.get("query"),
                    "playlist_title": state.get("yt_playlist.title"),
                    "playlist_author": state.get("yt_playlist.author"),
                    "playlist_description": state.get("yt_playlist.description"),
                    "playlist_thumbnail_url": state.get("yt_playlist.thumbnail_url"),
                    "chunks_data": format_chunks_for_prompt(relevant_lines),
                }
            ):
                print(chunk.content, end="", flush=True)
                full_answer += chunk.content
            print()
        except Exception as e:
            raise LLMStreamError(e) from e

    return {"ai_answer": full_answer}


# region ROUTER
def graph_router(graph: StateGraph) -> StateGraph:
    graph.add_node("ask_playlist_id", get_playlist_id)
    graph.add_node("set_retriever", init_retriever)
    graph.add_node("load_playlist_details", get_playlist_details)
    graph.add_node("save_transcripts", get_video_transcripts)
    graph.add_node("build_playlist", build_playlist)
    graph.add_node("save_transcripts_in_vector_db", save_transcripts_in_vector_db)
    graph.add_node("get_human_question", get_query)
    graph.add_node("get_relevant_lines", get_relevant_chunks)
    graph.add_node("gen_ai_answer", ask_answer_llm)

    graph.add_edge(START, "ask_playlist_id")
    graph.add_edge("ask_playlist_id", "load_playlist_details")

    graph.add_conditional_edges(
        "load_playlist_details",
        should_load_or_save,
        {
            "load_existing": "build_playlist",
            "load_new": "save_transcripts",
        },
    )

    graph.add_edge("save_transcripts", "build_playlist")

    graph.add_conditional_edges(
        "build_playlist",
        should_save_to_db,
        {
            "skip_save": "set_retriever",
            "save_to_db": "save_transcripts_in_vector_db",
        },
    )

    graph.add_edge("save_transcripts_in_vector_db", "set_retriever")

    graph.add_edge("set_retriever", "get_human_question")
    graph.add_edge("get_human_question", "get_relevant_lines")
    graph.add_edge("get_relevant_lines", "gen_ai_answer")
    graph.add_edge("gen_ai_answer", END)

    return graph


# region RUNNER
async def main():
    vector_store = init_vector_db()
    query_llm = get_query_model()
    llm_chain = get_llm_chain()

    initial_state: State = {
        "query_llm": query_llm,
        "vector_store": vector_store,
        "llm_chain": llm_chain,
    }

    graph = StateGraph(State)
    graph = graph_router(graph)

    compiled_graph = graph.compile()
    result = await compiled_graph.ainvoke(initial_state)


if __name__ == "__main__":
    asyncio.run(main())
