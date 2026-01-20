from src.application.graph.state import State
from src.application.graph.helpers import playlist_exist


def should_load_or_save(state: State) -> str:
    vector_store = state.get("vector_store")
    playlist_id = state.get("playlist_id") or ""

    if playlist_exist(vector_store=vector_store, playlist_id=playlist_id):
        return "load_existing"
    return "load_new"


def should_save_to_db(state: State) -> str:
    vector_store = state.get("vector_store")
    playlist_id = state.get("playlist_id") or ""

    if playlist_exist(vector_store=vector_store, playlist_id=playlist_id):
        return "skip_save"
    return "save_to_db"
