from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID


class Playlist(SQLModel, table=True):
    playlist_id: str = Field(primary_key=True)
    title: str
    author: str
    description: str = Field(default="")
    thumbnail_url: str = Field(default="")
    videos_qty: int = Field(default=0)
    indexed_at: datetime | None = Field(default=None)
    status: str = Field(default="indexing")

    chats: list["Chat"] = Relationship(back_populates="playlist")
    videos: list["Video"] = Relationship(back_populates="playlist")


class Video(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    video_id: str = Field(index=True)
    playlist_id: str = Field(foreign_key="playlist.playlist_id", index=True)
    title: str
    thumbnail_url: str = Field(default="")
    duration_seconds: int = Field(default=0)
    position: int = Field(default=0)

    playlist: "Playlist" = Relationship(back_populates="videos")


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(index=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)
    role: str
    content: str

    chat: "Chat" = Relationship(back_populates="messages")


class ChatPreference(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)
    preference: str

    chat: "Chat" = Relationship(back_populates="preferences")


class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    artifact_id: str = Field(index=True)
    chat_id: int = Field(foreign_key="chat.id", index=True)
    type: str
    data: str
    filename: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chat: "Chat" = Relationship(back_populates="artifacts")


class Chat(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    chat_id: UUID = Field(index=True, unique=True)
    title: str | None = None
    pruned_history_summary: str | None = None
    messages_count: int = 0
    playlist_id: str | None = Field(
        default=None, foreign_key="playlist.playlist_id", index=True
    )

    messages: list[Message] = Relationship(back_populates="chat")
    preferences: list[ChatPreference] = Relationship(back_populates="chat")
    playlist: Playlist | None = Relationship(back_populates="chats")
    artifacts: list[Artifact] = Relationship(back_populates="chat")
