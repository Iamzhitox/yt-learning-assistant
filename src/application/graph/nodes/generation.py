from src.application.graph.state import State
from src.application.graph.helpers import format_chunks_for_prompt
from src.domain.exceptions import LLMStreamError


def get_query(state: State):
    playlist = state.get("yt_playlist")
    playlist_title = playlist.title if playlist else ""

    msg = "Ready! Ask me a question about"
    human_question = input(f"{'='*40}\n\n{msg} \"{playlist_title}\":\n\n{'='*40}\n\n- ")

    return {"query": human_question}


def ask_answer_llm(state: State):
    relevant_lines = state.get("retrieved_chunks")
    chain_llm = state.get("llm_chain")
    playlist = state.get("yt_playlist")
    full_answer = ""

    print("\n\n\n", end="", flush=True)
    if relevant_lines:
        try:
            for chunk in chain_llm.stream(
                {
                    "question": state.get("query"),
                    "playlist_title": playlist.title if playlist else "",
                    "playlist_author": playlist.author if playlist else "",
                    "playlist_description": playlist.description if playlist else "",
                    "playlist_thumbnail_url": playlist.thumbnail_url if playlist else "",
                    "chunks_data": format_chunks_for_prompt(relevant_lines),
                }
            ):
                print(chunk.content, end="", flush=True)
                full_answer += chunk.content
            print()
        except Exception as e:
            raise LLMStreamError(e) from e

    return {"ai_answer": full_answer}
