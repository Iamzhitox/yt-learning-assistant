from typing import TypedDict, NotRequired

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_chroma import Chroma

from src.domain.models import YoutubePlaylist
from src.application.services import YouTubePlaylistLoader


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
