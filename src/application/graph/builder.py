import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.runnables.config import RunnableConfig
from src.application.graph.helpers import playlist_exist
from src.application.graph.state import State
from src.application.graph.helpers import (
    init_vector_db,
    get_llm_chain,
    get_playlist_id,
    gen_retriever,
    get_playlist_details,
    save_transcripts,
)
from src.infrastructure.config import CHAT_STATE_DIR, DEFAULT_CHAT_ID
from src.application.services.memory_manager import MemoryManager
from src.application.graph.nodes import (
    get_relevant_chunks,
    get_query,
    ask_answer_llm,
)
from langchain_core.retrievers import BaseRetriever
from src.application.services import YouTubePlaylistLoader

# region GRAPH


def create_compiled_graph(checkpointer: AsyncSqliteSaver, retriever: BaseRetriever):
    llm_chain = get_llm_chain()
    graph = StateGraph(State)

    graph.add_node("get_human_question", get_query)
    graph.add_node("get_relevant_lines", get_relevant_chunks(retriever=retriever))
    graph.add_node("gen_ai_answer", ask_answer_llm(chain_llm=llm_chain))

    graph.add_edge(START, "get_human_question")
    graph.add_edge("get_human_question", "get_relevant_lines")
    graph.add_edge("get_relevant_lines", "gen_ai_answer")
    graph.add_edge("gen_ai_answer", END)

    compiled_graph = graph.compile(checkpointer=checkpointer)

    return compiled_graph


# region RUNNER


async def main():
    vector_store = init_vector_db()
    playlist_id = get_playlist_id()
    retriever = gen_retriever(vector_store=vector_store, playlist_id=playlist_id)

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
        context = await memory.get_context()
        config: RunnableConfig = {"configurable": {"thread_id": memory.get_chat_id()}}

        initial_state: State = {"context": context}
        compiled_graph = create_compiled_graph(checkpointer, retriever)

        await compiled_graph.ainvoke(initial_state, config=config)
        await memory.update_chat()


if __name__ == "__main__":
    asyncio.run(main())
