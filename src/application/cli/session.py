from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from sqlmodel import Session, select
from src.domain.models import Chat, Playlist
from src.domain.models.youtube import YoutubePlaylist
from src.application.services.memory_manager import MemoryManager
from src.domain.exceptions import InvalidPlaylistUrlError
from src.infrastructure.config import ENGINE, ENGINE_SESSION_KWARGS


def _parse_playlist_id(url: str) -> str:
    query_params = parse_qs(urlparse(url).query)
    if "list" in query_params:
        return query_params["list"][0]
    raise InvalidPlaylistUrlError(url)

_SEP = "=" * 50


def list_indexed_playlists() -> list[Playlist]:
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        query = (
            select(Playlist)
            .where(Playlist.status == "ready")
            .order_by(Playlist.indexed_at.desc())
        )
        return list(session.exec(query).all())


def prompt_playlist_selection(playlists: list[Playlist]) -> Playlist | None:
    print(f"\n{_SEP}\n")
    for i, pl in enumerate(playlists, 1):
        print(f"  [{i}] {pl.title}")
    print(f"  [{len(playlists) + 1}] + Enter a new playlist URL")
    print(f"\n{_SEP}\n")

    while True:
        raw = input("Select an option: ").strip()
        if not raw.isdigit():
            print("Please enter a valid number.")
            continue
        choice = int(raw)
        if 1 <= choice <= len(playlists):
            return playlists[choice - 1]
        if choice == len(playlists) + 1:
            return None
        print(f"Please enter a number between 1 and {len(playlists) + 1}.")


def prompt_new_playlist_url() -> str:
    url = input(f"\n{_SEP}\n\nEnter the YouTube playlist URL:\n\n{_SEP}\n\n- ").strip()
    print("\n")
    return _parse_playlist_id(url)


def save_new_playlist(playlist_id: str, yt_playlist: YoutubePlaylist) -> Playlist:
    playlist = Playlist(
        playlist_id=playlist_id,
        title=yt_playlist.title,
        author=yt_playlist.author,
        description=yt_playlist.description,
        thumbnail_url=yt_playlist.thumbnail_url,
        videos_qty=yt_playlist.videos_qty,
        status="ready",
        indexed_at=datetime.now(timezone.utc),
    )
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        session.add(playlist)
        session.commit()
        session.refresh(playlist)
    return playlist


def get_or_create_chat(playlist_id: str, checkpointer) -> MemoryManager:
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        chat = session.exec(
            select(Chat).where(Chat.playlist_id == playlist_id)
        ).first()

    if chat:
        return MemoryManager(
            chat_id=str(chat.chat_id),
            checkpointer=checkpointer,
            playlist_id=playlist_id,
        )
    return MemoryManager(
        chat_id=None,
        checkpointer=checkpointer,
        playlist_id=playlist_id,
    )


async def print_resume_context(memory: MemoryManager) -> None:
    if memory.is_new_chat():
        return

    context = await memory.get_context()
    summary = context.get("summary") or ""
    last_messages = context.get("last_messages") or ""

    if not summary and not last_messages:
        return

    print(f"\n{_SEP}")
    print("Resuming previous conversation")
    print(_SEP)

    if summary:
        print(f"\n[Summary]\n{summary}")

    if last_messages:
        print(f"\n[Recent messages]\n{last_messages}")

    print(_SEP + "\n")
