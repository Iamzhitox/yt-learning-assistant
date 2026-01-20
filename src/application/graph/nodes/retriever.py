from src.application.graph.state import State
from src.application.graph.helpers import (
    get_similarity_retriever,
    get_ensemble_retriever,
)
from src.domain.exceptions import RetrieverError


def init_retriever(state: State):
    vector_store = state.get("vector_store")
    llm = state.get("query_llm")
    playlist_id = state.get("playlist_id") or ""

    retriever = get_similarity_retriever(
        vector_store=vector_store, playlist_id=playlist_id
    )
    retriever = get_ensemble_retriever(
        llm=llm, vector_store=vector_store, retriever=retriever, playlist_id=playlist_id
    )

    return {"retriever": retriever}


def get_relevant_chunks(state: State):
    retriever = state.get("retriever")
    question = state.get("query", "")

    if not retriever:
        return {"retrieved_chunks": []}

    try:
        relevant_chunks = retriever.invoke(question)
    except Exception as e:
        raise RetrieverError(question, e) from e

    return {"retrieved_chunks": relevant_chunks}
