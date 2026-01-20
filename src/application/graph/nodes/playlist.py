from src.application.graph.state import State
from src.application.graph.helpers import get_playlist_id_from_url
from src.application.services import YouTubePlaylistLoader
from src.domain.exceptions import (
    PlaylistLoadError,
    TranscriptLoadError,
    VectorStoreWriteError,
)


def get_playlist_id(state: State):
    yt_playlist_url = input(
        f"{'='*50}\n\nChoose a playlist for the model to learn from:\n\n{'='*50}\n\n- "
    )
    yt_playlist_id = get_playlist_id_from_url(yt_playlist_url)
    print("\n\n")

    return {"playlist_id": yt_playlist_id}


def get_playlist_details(state: State):
    playlist_id = state.get("playlist_id") or ""

    try:
        yt_service = YouTubePlaylistLoader(playlist_id=playlist_id)
        yt_service.load_playlist_details()
        yt_service.load_video_details()
    except Exception as e:
        raise PlaylistLoadError(playlist_id, e) from e

    return {"yt_playlist_service": yt_service}


async def get_video_transcripts(state: State):
    yt_service = state.get("yt_playlist_service")
    playlist_id = state.get("playlist_id") or ""

    if yt_service:
        try:
            await yt_service.load_transcript_videos()
        except Exception as e:
            raise TranscriptLoadError(playlist_id, e) from e

    return {"yt_playlist_service": yt_service}


def build_playlist(state: State):
    yt_service = state.get("yt_playlist_service")
    if yt_service:
        yt_playlist = yt_service.build()
        return {"yt_playlist": yt_playlist}


def save_transcripts_in_vector_db(state: State):
    vector_store = state.get("vector_store")
    playlist = state.get("yt_playlist")
    playlist_id = state.get("playlist_id") or ""

    if playlist:
        try:
            for video in playlist.videos:
                vector_store.add_documents(video.transcript)
        except Exception as e:
            raise VectorStoreWriteError(playlist_id, e) from e
