import re
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import END
from langgraph.types import Command
from src.application.graph.state import State
from src.application.agents.supervisor import get_supervisor_llm, SUPERVISOR_ROUTING_PROMPT

DIRECT_RESPONSE_MARKER = "RESPOND:"
DELEGATE_ANALYST_MARKER = "ANALYST:"
DELEGATE_TEACHER_MARKER = "TEACHER:"

# finds the first marker anywhere in the LLM response, even if surrounded by extra text
_MARKER_RE = re.compile(
    r"(?:^|\n)\s*(ANALYST:|TEACHER:|RESPOND:)\s*(.*)",
    re.DOTALL,
)


def _parse_decision(text: str) -> tuple[str, str]:
    match = _MARKER_RE.search(text)
    if match:
        return match.group(1), match.group(2).strip()
    return DIRECT_RESPONSE_MARKER, text


def _build_manager_context(state: State) -> str:
    context = state.get("context", {})
    summary = context.get("summary") or "No previous history."
    last_messages = context.get("last_messages") or "No recent messages."

    metadata = state.get("playlist_metadata")
    if metadata:
        playlist_info = (
            f"Title: {metadata.get('title', 'N/A')}\n"
            f"Author: {metadata.get('author', 'N/A')}\n"
            f"Description: {metadata.get('description', 'N/A')}"
        )
    else:
        playlist_info = "Not available."

    agent_output = state.get("agent_output")
    agent_section = f"\n### Agent output\n{agent_output}" if agent_output else ""

    playlist_id = state.get("playlist_id", "")
    playlist_id_section = f"\n### Active playlist ID\n{playlist_id}" if playlist_id else ""

    return (
        f"### Previous history summary\n{summary}\n\n"
        f"### Latest messages\n{last_messages}\n\n"
        f"### Playlist metadata\n{playlist_info}"
        f"{playlist_id_section}"
        f"{agent_section}"
    )


def manager_node(state: State) -> Command:
    user_query = state.get("query", "")

    context_block = _build_manager_context(state)

    routing_messages = [
        SystemMessage(content=SUPERVISOR_ROUTING_PROMPT),
        HumanMessage(
            content=(
                f"## CONTEXT\n\n{context_block}\n\n"
                f"## USER MESSAGE\n\n{user_query}"
            )
        ),
    ]

    llm = get_supervisor_llm()
    response = llm.invoke(routing_messages)
    marker, content = _parse_decision(response.content.strip())

    if marker == DELEGATE_ANALYST_MARKER:
        return Command(
            goto="agent_analyst",
            update={
                "messages": [HumanMessage(content=content)],
                "agent_output": None,
            },
        )

    if marker == DELEGATE_TEACHER_MARKER:
        return Command(
            goto="agent_teacher",
            update={
                "messages": [HumanMessage(content=content)],
                "agent_output": None,
            },
        )

    return Command(
        goto=END,
        update={
            "messages": [AIMessage(content=content)],
            "agent_output": None,
        },
    )
