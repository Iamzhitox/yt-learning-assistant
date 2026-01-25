from typing import TypedDict, NotRequired
from langchain_core.documents import Document
from src.domain.models import YoutubePlaylist


class ContextDict(TypedDict):
    summary: str | None
    last_messages: str


class State(TypedDict):
    query: NotRequired[str]
    playlist_id: NotRequired[str]
    yt_playlist: NotRequired[YoutubePlaylist]
    retrieved_chunks: NotRequired[list[Document]]
    ai_answer: NotRequired[str]
    context: NotRequired[ContextDict]
