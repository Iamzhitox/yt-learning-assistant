import asyncio

from langgraph.graph import StateGraph, START, END

from src.application.graph.state import State
from src.application.graph.helpers import (
    init_vector_db,
    get_query_model,
    get_llm_chain,
)
from src.application.graph.nodes import (
    get_playlist_id,
    get_playlist_details,
    get_video_transcripts,
    build_playlist,
    save_transcripts_in_vector_db,
    init_retriever,
    get_relevant_chunks,
    get_query,
    ask_answer_llm,
)
from src.application.graph.edges import should_load_or_save, should_save_to_db


def build_graph(graph: StateGraph) -> StateGraph:
    graph.add_node("ask_playlist_id", get_playlist_id)
    graph.add_node("set_retriever", init_retriever)
    graph.add_node("load_playlist_details", get_playlist_details)
    graph.add_node("save_transcripts", get_video_transcripts)
    graph.add_node("build_playlist", build_playlist)
    graph.add_node("save_transcripts_in_vector_db", save_transcripts_in_vector_db)
    graph.add_node("get_human_question", get_query)
    graph.add_node("get_relevant_lines", get_relevant_chunks)
    graph.add_node("gen_ai_answer", ask_answer_llm)

    graph.add_edge(START, "ask_playlist_id")
    graph.add_edge("ask_playlist_id", "load_playlist_details")

    graph.add_conditional_edges(
        "load_playlist_details",
        should_load_or_save,
        {
            "load_existing": "build_playlist",
            "load_new": "save_transcripts",
        },
    )

    graph.add_edge("save_transcripts", "build_playlist")

    graph.add_conditional_edges(
        "build_playlist",
        should_save_to_db,
        {
            "skip_save": "set_retriever",
            "save_to_db": "save_transcripts_in_vector_db",
        },
    )

    graph.add_edge("save_transcripts_in_vector_db", "set_retriever")

    graph.add_edge("set_retriever", "get_human_question")
    graph.add_edge("get_human_question", "get_relevant_lines")
    graph.add_edge("get_relevant_lines", "gen_ai_answer")
    graph.add_edge("gen_ai_answer", END)

    return graph


def create_compiled_graph():
    vector_store = init_vector_db()
    query_llm = get_query_model()
    llm_chain = get_llm_chain()

    initial_state: State = {
        "query_llm": query_llm,
        "vector_store": vector_store,
        "llm_chain": llm_chain,
    }

    graph = StateGraph(State)
    graph = build_graph(graph)
    compiled_graph = graph.compile()

    return compiled_graph, initial_state


async def main():
    compiled_graph, initial_state = create_compiled_graph()
    await compiled_graph.ainvoke(initial_state)


if __name__ == "__main__":
    asyncio.run(main())
