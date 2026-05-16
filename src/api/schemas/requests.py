from pydantic import BaseModel, Field


class IngestPlaylistRequest(BaseModel):
    url: str = Field(
        description="Full YouTube playlist URL. Both long and short forms are accepted.",
        examples=["https://www.youtube.com/playlist?list=PLxyz123"],
    )


class ChatStreamRequest(BaseModel):
    message: str = Field(
        description="The user's question or instruction for the learning assistant.",
        examples=["Explain the concept of gradient descent from the videos"],
    )
    chat_id: str | None = Field(
        default=None,
        description=(
            "UUID of an existing chat session to continue. "
            "Omit (or pass null) to start a new session — the server generates a UUID "
            "and returns it in the X-Chat-Id response header."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    playlist_id: str = Field(
        description="YouTube playlist ID that scopes the knowledge base for this conversation.",
        examples=["PLxyz123"],
    )
