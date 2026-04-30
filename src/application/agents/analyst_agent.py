from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from src.application.graph.helpers import gen_retriever, init_vector_db, scope_filter
from langchain_core.documents import Document
from langchain.chat_models import init_chat_model
from src.infrastructure.config import QUERY_MODEL, LLM_PROVIDER
from langchain_core.prompts import ChatPromptTemplate
from tavily import TavilyClient
from src.infrastructure.config import TAVILY_API_KEY
from src.domain.prompts.analyst_prompt_en import ANALYST_PROMPT_EN


@tool("chunks_from_query")
def retrieve_relevant_chunks(
    query: str,
    playlist_id: str,
    video_ids: list[str] = [],
) -> list[Document]:
    """
    Retrieves semantically relevant chunks from the vector database using a retriever.

    Use this tool when you need to find specific information within the content
    of a playlist or a subset of videos. The retriever performs a semantic search
    and returns only the most relevant chunks for the given query.

    Parameters:
        query (str): The search query used to find relevant chunks in the vector DB.
                     Should be as descriptive as possible to maximize result relevance.
                     Example: "what is a recursive function?"

        playlist_id (str): The YouTube playlist ID that scopes the search.
                           Required — the vector DB is fed from multiple playlists,
                           so this acts as the primary filter.
                           Example: "PLxyz123abc"

        video_ids (list[str]): Optional list of specific video IDs within the playlist
                               to further narrow the search. Assumed to belong to the
                               given playlist_id. If empty, the entire playlist is searched.
                               Example: ["abc001", "abc002"]

    Returns:
        list[Document]: A list of Document objects where each document contains:
            - page_content (str): The text content of the chunk.
            - metadata (dict): Includes fields like `video_id`, `start_seconds`,
                               video title, and playlist info.
    """
    vector_store = init_vector_db()
    retriever = gen_retriever(vector_store, playlist_id, video_ids)

    return retriever.invoke(query)


@tool("chunks_from_scope")
def get_chunks_from_scope(
    playlist_id: str, video_ids: list[str] = []
) -> list[Document]:
    """
    Retrieves all chunks within a given scope (playlist or specific videos) without
    semantic filtering. Returns raw chunks as-is from the vector store.

    Use this tool when you need the complete content of one or more videos,
    regardless of semantic relevance — for example, to reconstruct a full transcript
    or perform a broad analysis over all available content.

    Unlike `chunks_from_query`, this tool does not rank results by relevance.
    It fetches every chunk matching the scope filter.

    Parameters:
        playlist_id (str): The YouTube playlist ID used as the primary scope filter.
                           Example: "PLxyz123abc"

        video_ids (list[str]): Optional list of specific video IDs to include in the scope.
                               If empty, all chunks from the entire playlist are returned.
                               Example: ["vid001", "vid002", "vid003"]

    Returns:
        list[Document]: A list of all Document objects within the scope, where each contains:
            - page_content (str): The raw text of the chunk.
            - metadata (dict): Includes fields like `video_id`, `start_seconds`, title, etc.
    """
    vector_store = init_vector_db()
    chunk_filter = scope_filter(playlist_id, video_ids)

    result = vector_store._collection.get(where=chunk_filter)
    result_as_docs = [
        Document(page_content=chunk, metadata=metadata)
        for chunk, metadata in zip(result["documents"] or [], result["metadatas"] or [])
    ]

    return result_as_docs


@tool("chunks_to_transcript")
def create_transcript_from_chunks(chunks: list[Document]) -> str:
    """
    Reconstructs the full transcript of a single video by sorting its chunks
    chronologically by `start_seconds` and joining their text content.

    Use this tool in conjunction with `chunks_from_scope` to rebuild the complete,
    ordered transcript of a video as a single continuous string.

    IMPORTANT: All chunks passed to this tool must belong to the same video.
    Mixing chunks from different videos will produce an incorrect and incoherent
    transcript. If you need transcripts for multiple videos, call this tool
    separately for each video's chunks.

    Parameters:
        chunks (list[Document]): List of Document objects for a single video,
                                 typically obtained from `chunks_from_scope`.
                                 Each document must have `start_seconds` in its metadata
                                 for correct ordering.

    Returns:
        str: The complete transcript of the video as a single string,
             with chunks joined in chronological order.
    """
    sorted_chunks = sorted(chunks, key=lambda doc: doc.metadata.get("start_seconds", 0))
    return "".join([chunk.page_content for chunk in sorted_chunks])


@tool("search_on_web")
def search(query: str) -> str:
    """
    Performs a ranked web search via Tavily and returns the content of the top result.

    Use this tool when the information you need is not available in the vector database,
    or when you require external, up-to-date, or publicly sourced data to answer the
    supervisor's query.

    The search is limited to a single result (max_results=1), prioritizing quality
    over quantity.

    Parameters:
        query (str): The search query. The more specific and descriptive, the better
                     the result quality.
                     Example: "Python 3.13 new features release notes"

    Returns:
        str: A string containing the text content of the top-ranked search result.
    """
    search_client = TavilyClient(api_key=TAVILY_API_KEY)
    search_result = search_client.search(query, max_results=1)

    return search_result[0]["content"]


@tool("summarizer")
def summarizer(raw_content: str, summary_instructions: str = "") -> str:
    """
    Summarizes large text content via a dedicated LLM call outside the agent's context.

    Use this tool when the content is too long to process inline (e.g. full video
    transcripts from chunks_to_transcript). By offloading summarization here, the
    agent avoids filling its own context window with raw transcript data.

    Do NOT use this for short content — if it fits in your context, summarize it directly.

    Parameters:
        raw_content (str): The full text to summarize. Typically a full video transcript
                           or a long web search result.

        summary_instructions (str): Optional guidance for the summary: target length,
                                    thematic focus, output format, etc.
                                    Example: "Max 200 words, focus on technical concepts."

    Returns:
        str: The generated summary as a string.
    """
    llm = init_chat_model(model_provider=LLM_PROVIDER, model=QUERY_MODEL)
    prompt = ChatPromptTemplate.from_template(
        "Summarize the following content:\n\"{content}\"\n\nInstructions: {instructions}"
    )
    chain = prompt | llm
    result = chain.invoke({"content": raw_content, "instructions": summary_instructions})
    return result.content


def get_analyst_agent():
    llm = init_chat_model(model_provider=LLM_PROVIDER, model=QUERY_MODEL)
    analyst_agent = create_react_agent(
        model=llm,
        tools=[
            retrieve_relevant_chunks,
            get_chunks_from_scope,
            create_transcript_from_chunks,
            search,
            summarizer,
        ],
        prompt=ANALYST_PROMPT_EN,
    )
    return analyst_agent
