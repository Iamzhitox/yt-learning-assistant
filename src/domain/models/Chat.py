from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID


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


class Chat(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    chat_id: UUID = Field(index=True, unique=True)
    title: str | None = None
    pruned_history_summary: str | None = None
    messages_count: int = 0

    messages: list[Message] = Relationship(back_populates="chat")
    preferences: list[ChatPreference] = Relationship(back_populates="chat")
