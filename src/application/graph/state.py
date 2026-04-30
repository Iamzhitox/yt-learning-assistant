from typing import TypedDict, NotRequired, Annotated
from langgraph.graph.message import add_messages


class ContextDict(TypedDict):
    summary: str | None
    last_messages: str


class PlaylistMetadata(TypedDict):
    title: str
    author: str
    description: str


class State(TypedDict):
    messages: Annotated[list, add_messages]
    query: NotRequired[str]
    playlist_id: NotRequired[str]
    context: NotRequired[ContextDict]
    playlist_metadata: NotRequired[PlaylistMetadata]
    agent_output: NotRequired[str]
