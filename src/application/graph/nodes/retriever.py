from src.application.graph.state import State
from langchain_core.retrievers import BaseRetriever
from src.domain.exceptions import RetrieverError


def get_relevant_chunks_cls(retriever: BaseRetriever):
    def get_relevant_chunks(state: State):
        question = state.get("query", "")

        if not retriever:
            return {"retrieved_chunks": []}

        try:
            relevant_chunks = retriever.invoke(question)
        except Exception as e:
            raise RetrieverError(question, e) from e

        return {"retrieved_chunks": relevant_chunks}

    return get_relevant_chunks
