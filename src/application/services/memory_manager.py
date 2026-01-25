import uuid
from uuid import UUID
from typing import List
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from src.domain.models import Chat
from sqlmodel import Session, select
from langchain_classic.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from src.application.graph.state import ContextDict

from src.infrastructure.config import (
    ENGINE,
    MAX_MSG_SUMMARY,
    LLM_PROVIDER,
    QUERY_MODEL,
)

from src.domain.prompts import HUMAN_PROMPT, SUMMARY_PROMPT


class MemoryState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    vector_memories: List[str]
    chat_summary: str
    chat_id: str


class MemoryManager:

    def __init__(self, checkpointer, chat_id: str | None = None):
        self.checkpointer = checkpointer
        self.config = None

        if chat_id:
            self.chat_id = chat_id
            self.chat_instance = self._get_chat(chat_id)
            self.new_chat = False
        else:
            self.chat_instance = self._create_new_chat()
            self.chat_id = str(self.chat_instance.chat_id)
            self.new_chat = True

        self.config = {"configurable": {"thread_id": self.chat_id}}

    def is_new_chat(self):
        return self.new_chat or False

    def _create_new_chat(self) -> Chat:
        new_chat_id = uuid.uuid4()
        new_chat = Chat(chat_id=new_chat_id)
        with Session(ENGINE) as session:
            session.add(new_chat)
            session.commit()
            session.refresh(new_chat)

        return new_chat

    def _get_chat(self, chat_id: str):
        with Session(ENGINE) as session:
            query = select(Chat).where(Chat.chat_id == UUID(chat_id))
            chat = session.exec(query).first()

        return chat

    def _gen_summary(self, prev_messages):
        if self.chat_instance:
            current_summary = self.chat_instance.pruned_history_summary or ""
            chain_summary = self._get_summarization_chain()
            response = chain_summary.invoke(
                {"previous_summary": current_summary, "messages": prev_messages}
            )

            return response.content

    def _get_summarization_chain(self):
        llm = init_chat_model(model_provider=LLM_PROVIDER, model=QUERY_MODEL)
        template = ChatPromptTemplate.from_messages([SUMMARY_PROMPT, HUMAN_PROMPT])

        return template | llm

    def _save_changes(self):
        with Session(ENGINE) as session:
            session.add(self.chat_instance)
            session.commit()

    def get_chat_id(self):
        return self.chat_id

    async def update_chat(self):
        state = await self.checkpointer.aget(self.config)
        messages = state.get("messages", []) if state else []

        if len(messages) > MAX_MSG_SUMMARY:
            old_messages = messages[:-MAX_MSG_SUMMARY]
            formatted_messages = self._format_messages_for_summary(old_messages)
            new_summary = self._gen_summary(formatted_messages)
            if self.chat_instance:
                self.chat_instance.pruned_history_summary = new_summary

        if self.chat_instance:
            self.chat_instance.messages_count = len(messages)
            self._save_changes()

    def _format_messages_for_summary(self, messages) -> str:
        formatted_msgs = ""
        for message in messages:
            role = "Human" if message.type == "human" else "AI"
            formatted_msgs += f"[{role}]: {message.content}\n\n"
        return formatted_msgs

    async def get_context(self) -> ContextDict:
        state = await self.checkpointer.aget(self.config)
        messages = state.get("messages", []) if state else []
        last_messages = messages[-MAX_MSG_SUMMARY:] if messages else []

        if self.chat_instance:
            return {
                "summary": self.chat_instance.pruned_history_summary,
                "last_messages": self._format_messages_for_summary(last_messages),
            }

        return {"summary": "", "last_messages": ""}
