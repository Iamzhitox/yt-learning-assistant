import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from src.application.graph.helpers import playlist_exist
from src.application.graph.state import State
from src.application.graph.helpers import (
    init_vector_db,
    get_playlist_id,
    get_playlist_details,
    save_transcripts,
    get_callbacks,
)
from src.infrastructure.config import CHAT_STATE_DIR, DEFAULT_CHAT_ID
from src.application.services.memory_manager import MemoryManager
from src.application.graph.nodes.manager import manager_node
from src.application.graph.nodes.analyst import analyst_node
from src.application.graph.nodes.teacher import teacher_node
from src.application.services import YouTubePlaylistLoader

# region GRAPH


def create_compiled_graph(checkpointer: AsyncSqliteSaver):
    graph = StateGraph(State)

    graph.add_node("agent_manager", manager_node)
    graph.add_node("agent_analyst", analyst_node)
    graph.add_node("agent_teacher", teacher_node)

    graph.add_edge(START, "agent_manager")
    # all routing handled via Command(goto=...) inside each node

    compiled_graph = graph.compile(checkpointer=checkpointer)

    return compiled_graph


# region RUNNER


async def main():
    vector_store = init_vector_db()
    playlist_id = get_playlist_id()

    is_playlist_already_saved = playlist_exist(
        vector_store=vector_store, playlist_id=playlist_id
    )

    yt_service = YouTubePlaylistLoader(playlist_id=playlist_id)

    yt_playlist = await get_playlist_details(
        yt_service=yt_service,
        playlist_id=playlist_id,
        is_loaded=is_playlist_already_saved,
    )

    if not is_playlist_already_saved:
        save_transcripts(
            vector_store=vector_store, playlist=yt_playlist, playlist_id=playlist_id
        )

    async with AsyncSqliteSaver.from_conn_string(CHAT_STATE_DIR) as checkpointer:
        memory = MemoryManager(chat_id=DEFAULT_CHAT_ID, checkpointer=checkpointer)
        config: RunnableConfig = {
            "configurable": {"thread_id": memory.get_chat_id()},
            "callbacks": get_callbacks(),
        }

        compiled_graph = create_compiled_graph(checkpointer)

        playlist_title = yt_playlist.title
        print(
            f"\n{'='*50}\n\nStarted session about \"{playlist_title}\". Type 'exit' to quit.\n"
        )

        while True:
            user_input = input("- ").strip()
            if user_input.lower() == "exit":
                print("\nSession ended.\n")
                break
            if not user_input:
                continue

            context = await memory.get_context()

            state: State = {
                "context": context,
                "messages": [HumanMessage(content=user_input)],
                "query": user_input,
                "playlist_id": playlist_id,
                "playlist_metadata": {
                    "title": yt_playlist.title,
                    "author": yt_playlist.author,
                    "description": yt_playlist.description,
                },
            }

            result = await compiled_graph.ainvoke(state, config=config)
            await memory.update_chat()

            last_ai = next(
                (
                    m
                    for m in reversed(result.get("messages", []))
                    if isinstance(m, AIMessage)
                ),
                None,
            )
            if last_ai:
                print(f"\n{last_ai.content}\n")


if __name__ == "__main__":
    asyncio.run(main())
