import asyncio
import json
import uuid
from typing import AsyncIterator

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from sqlmodel import Session

from src.api.streaming.events import SSEEvent, format_sse
from src.domain.models import Artifact
from src.infrastructure.config import ENGINE, ENGINE_SESSION_KWARGS

class GraphExecutionError(Exception):
    """Wraps an exception raised inside the LangGraph task."""


_AGENT_NAMES = {"agent_manager", "agent_analyst", "agent_teacher"}
_ARTIFACT_TOOLS = {"create_quiz", "create_exam"}


def _persist_artifact(chat_db_id: int, type_: str, data: dict | list, filename: str | None = None) -> None:
    artifact = Artifact(
        artifact_id=str(uuid.uuid4()),
        chat_id=chat_db_id,
        type=type_,
        data=json.dumps(data, ensure_ascii=False),
        filename=filename,
    )
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        session.add(artifact)
        session.commit()


def _extract_citations(messages: list) -> list[dict]:
    seen: set[tuple] = set()
    citations: list[dict] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        raw = msg.content
        if not isinstance(raw, str):
            continue
        # ToolMessage content from chunks_from_query is a JSON list of Documents
        try:
            docs = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(docs, list):
            continue
        for doc in docs:
            meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            video_id = meta.get("video_id")
            start_seconds = meta.get("start_seconds")
            video_title = meta.get("video_title", "")
            if video_id is None or start_seconds is None:
                continue
            key = (video_id, int(start_seconds))
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "video_id": video_id,
                "start_seconds": int(start_seconds),
                "label": video_title,
            })
    return citations


class SSEAgentTracer(BaseCallbackHandler):
    def __init__(self, queue: asyncio.Queue, chat_db_id: int):
        super().__init__()
        self._queue = queue
        self._chat_db_id = chat_db_id
        self._current_tool: str | None = None

    def on_chain_start(self, serialized, inputs, **kwargs):
        if not serialized:
            return
        name = serialized.get("name", "")
        if name in _AGENT_NAMES:
            self._queue.put_nowait(SSEEvent("status_update", {"agent": name, "phase": "start"}))

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = serialized.get("name", "?") if serialized else "?"
        self._current_tool = name
        preview = str(input_str)[:100]
        self._queue.put_nowait(SSEEvent("status_update", {"tool": name, "phase": "start", "preview": preview}))

    def on_tool_end(self, output, **kwargs):
        name = self._current_tool or "?"
        output_str = str(output)

        if name == "create_quiz":
            try:
                quiz_data = json.loads(output_str)
                _persist_artifact(self._chat_db_id, "quiz", quiz_data)
                self._queue.put_nowait(SSEEvent("artifact_quiz", {"quiz": quiz_data}))
            except (json.JSONDecodeError, Exception):
                self._queue.put_nowait(SSEEvent("status_update", {"tool": name, "phase": "end", "preview": output_str[:300]}))

        elif name == "create_exam":
            # output is the file path: "output/exams/{filename}.pdf"
            filename = output_str.split("/")[-1] if "/" in output_str else output_str
            url = f"/files/exams/{filename}"
            artifact_data = {"filename": filename, "url": url}
            _persist_artifact(self._chat_db_id, "pdf", artifact_data, filename=filename)
            self._queue.put_nowait(SSEEvent("artifact_pdf", artifact_data))

        else:
            preview = output_str[:300]
            self._queue.put_nowait(SSEEvent("status_update", {"tool": name, "phase": "end", "preview": preview}))


async def run_graph_with_sse(
    graph,
    state: dict,
    config: dict,
    queue: asyncio.Queue,
    chat_db_id: int,
) -> AsyncIterator[str]:
    graph_task = asyncio.create_task(graph.ainvoke(state, config=config))

    while not graph_task.done():
        get_task = asyncio.create_task(queue.get())
        done, _ = await asyncio.wait(
            {graph_task, get_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if get_task in done:
            yield format_sse(get_task.result())
        else:
            get_task.cancel()

    # drain residual events
    while not queue.empty():
        yield format_sse(queue.get_nowait())

    if graph_task.exception():
        raise GraphExecutionError(str(graph_task.exception())) from graph_task.exception()

    result = graph_task.result()
    messages = result.get("messages", [])

    citations = _extract_citations(messages)
    if citations:
        _persist_artifact(chat_db_id, "citations", {"items": citations})
        yield format_sse(SSEEvent("citations", {"items": citations}))

    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last_ai:
        yield format_sse(SSEEvent("final_response", {"content": last_ai.content}))
