import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from sqlmodel import Session, select

from src.api.dependencies import get_checkpointer
from src.api.schemas import ArtifactResponse, ChatHistoryResponse, ChatMessage
from src.domain.models import Artifact, Chat
from src.infrastructure.config import ENGINE, ENGINE_SESSION_KWARGS

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get(
    "/{chat_id}/history",
    response_model=ChatHistoryResponse,
    summary="Get conversation history",
    description=(
        "Returns the message history and rolling summary for a chat session. "
        "Messages come from the active LangGraph checkpoint (up to 6 messages in the sliding window). "
        "Older turns are compressed into the `summary` field by the memory manager. "
        "Use this endpoint on page load to restore the conversation UI."
    ),
    responses={
        404: {"description": "No chat session found with the given ID."},
    },
)
async def get_chat_history(chat_id: str, checkpointer=Depends(get_checkpointer)):
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        chat = session.exec(select(Chat).where(Chat.chat_id == UUID(chat_id))).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    config = {"configurable": {"thread_id": chat_id}}
    checkpoint = await checkpointer.aget(config)
    messages = checkpoint.get("channel_values", {}).get("messages", []) if checkpoint else []

    chat_messages = []
    for msg in messages:
        role = "human" if isinstance(msg, HumanMessage) else "ai"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        chat_messages.append(ChatMessage(role=role, content=content))

    return ChatHistoryResponse(
        chat_id=chat_id,
        messages=chat_messages,
        summary=chat.pruned_history_summary,
    )


@router.get(
    "/{chat_id}/artifacts",
    response_model=list[ArtifactResponse],
    summary="Get artifacts for a chat session",
    description=(
        "Returns all artifacts generated during a chat session: quizzes, citation lists, and PDF exams. "
        "Use this endpoint on page load to restore the Dashboard panel without replaying the conversation. "
        "Artifacts are ordered by creation time (oldest first)."
    ),
    responses={
        404: {"description": "No chat session found with the given ID."},
    },
)
def get_chat_artifacts(chat_id: str):
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        chat = session.exec(select(Chat).where(Chat.chat_id == UUID(chat_id))).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        artifacts = list(
            session.exec(select(Artifact).where(Artifact.chat_id == chat.id)).all()
        )

    result = []
    for artifact in artifacts:
        try:
            data = json.loads(artifact.data)
        except (json.JSONDecodeError, TypeError):
            data = {}
        result.append(
            ArtifactResponse(
                artifact_id=artifact.artifact_id,
                type=artifact.type,  # type: ignore[arg-type]
                data=data,
                filename=artifact.filename,
                created_at=artifact.created_at,
            )
        )
    return result
