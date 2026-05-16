from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select

from src.api.dependencies import get_ingestion_lock, get_vector_store
from src.api.schemas import IngestPlaylistRequest, PlaylistResponse, VideoSummary
from src.application.graph.helpers import get_playlist_id_from_url, playlist_exist
from src.application.services import YouTubePlaylistLoader
from src.domain.exceptions import InvalidPlaylistUrlError, PlaylistNotFoundError
from src.domain.models import Playlist, Video
from src.infrastructure.config import ENGINE, ENGINE_SESSION_KWARGS

router = APIRouter(prefix="/playlists", tags=["playlists"])


def _playlist_to_response(playlist: Playlist, videos: list[Video]) -> PlaylistResponse:
    return PlaylistResponse(
        playlist_id=playlist.playlist_id,
        title=playlist.title,
        author=playlist.author,
        description=playlist.description,
        thumbnail_url=playlist.thumbnail_url,
        videos_qty=playlist.videos_qty,
        videos=[
            VideoSummary(
                video_id=v.video_id,
                title=v.title,
                thumbnail_url=v.thumbnail_url,
                duration_seconds=v.duration_seconds,
            )
            for v in sorted(videos, key=lambda v: v.position)
        ],
        status=playlist.status,  # type: ignore[arg-type]
    )


def _get_playlist_with_videos(playlist_id: str) -> tuple[Playlist, list[Video]] | None:
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        playlist = session.exec(
            select(Playlist).where(Playlist.playlist_id == playlist_id)
        ).first()
        if not playlist:
            return None
        videos = list(session.exec(select(Video).where(Video.playlist_id == playlist_id)).all())
    return playlist, videos


async def _index_transcripts(
    playlist_id: str,
    yt_service: YouTubePlaylistLoader,
    vector_store,
    lock,
    ingestion_status: dict,
) -> None:
    try:
        await yt_service.load_transcript_videos()
        playlist = yt_service.build()

        async with lock:
            for video in playlist.videos:
                vector_store.add_documents(video.transcript)

        with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
            db_playlist = session.exec(
                select(Playlist).where(Playlist.playlist_id == playlist_id)
            ).first()
            if db_playlist:
                db_playlist.status = "ready"
                session.add(db_playlist)
                session.commit()

        ingestion_status[playlist_id] = "ready"
    except Exception:
        ingestion_status[playlist_id] = "error"
        with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
            db_playlist = session.exec(
                select(Playlist).where(Playlist.playlist_id == playlist_id)
            ).first()
            if db_playlist:
                db_playlist.status = "error"
                session.add(db_playlist)
                session.commit()


@router.get(
    "",
    response_model=list[PlaylistResponse],
    summary="List indexed playlists",
    description=(
        "Returns all playlists that have been fully indexed (status `ready`). "
        "Playlists still being processed (`indexing`) or that failed (`error`) are excluded. "
        "Each entry includes the ordered list of videos with their metadata."
    ),
)
def list_playlists():
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        playlists = list(session.exec(select(Playlist).where(Playlist.status == "ready")).all())
        result = []
        for p in playlists:
            videos = list(session.exec(select(Video).where(Video.playlist_id == p.playlist_id)).all())
            result.append(_playlist_to_response(p, videos))
    return result


@router.post(
    "",
    response_model=PlaylistResponse,
    status_code=202,
    summary="Ingest a YouTube playlist",
    description=(
        "Starts the ingestion pipeline for a YouTube playlist URL. "
        "Playlist and video metadata are fetched synchronously from the YouTube API and saved immediately. "
        "Transcript loading and vector indexing run in the background — the response is returned with `status: indexing` "
        "before that process completes. Poll `GET /playlists/{playlist_id}` to check when `status` becomes `ready`. "
        "If the playlist was already indexed, returns the existing record immediately with `status: ready` (idempotent)."
    ),
    responses={
        202: {"description": "Playlist accepted — metadata returned, transcripts indexing in background."},
        422: {"description": "The URL is not a valid YouTube playlist URL."},
        404: {"description": "Playlist not found on YouTube."},
        502: {"description": "YouTube API returned an unexpected error."},
    },
)
async def ingest_playlist(
    body: IngestPlaylistRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    vector_store=Depends(get_vector_store),
    lock=Depends(get_ingestion_lock),
):
    try:
        playlist_id = get_playlist_id_from_url(body.url)
    except InvalidPlaylistUrlError:
        raise HTTPException(status_code=422, detail="Invalid YouTube playlist URL")

    existing = _get_playlist_with_videos(playlist_id)
    if existing:
        playlist, videos = existing
        return _playlist_to_response(playlist, videos)

    try:
        yt_service = YouTubePlaylistLoader(playlist_id=playlist_id)
        yt_service.load_playlist_details()
        yt_service.load_video_details()
    except PlaylistNotFoundError:
        raise HTTPException(status_code=404, detail="Playlist not found on YouTube")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"YouTube API error: {e}")

    yt_playlist = yt_service.build()

    db_videos: list[Video] = []
    with Session(ENGINE, **ENGINE_SESSION_KWARGS) as session:
        db_playlist = Playlist(
            playlist_id=playlist_id,
            title=yt_playlist.title or "",
            author=yt_playlist.author or "",
            description=yt_playlist.description or "",
            thumbnail_url=yt_playlist.thumbnail_url or "",
            videos_qty=yt_playlist.videos_qty or 0,
            status="indexing",
        )
        session.add(db_playlist)
        session.flush()

        for video in yt_playlist.videos:
            db_video = Video(
                video_id=video.video_id,
                playlist_id=playlist_id,
                title=video.title or "",
                thumbnail_url=video.thumbnail_url or "",
                duration_seconds=video.duration or 0,
                position=video.position or 0,
            )
            session.add(db_video)
            db_videos.append(db_video)

        session.commit()

    ingestion_status: dict = request.app.state.ingestion_status
    ingestion_status[playlist_id] = "indexing"

    background_tasks.add_task(
        _index_transcripts,
        playlist_id,
        yt_service,
        vector_store,
        lock,
        ingestion_status,
    )

    return _playlist_to_response(db_playlist, db_videos)


@router.get(
    "/{playlist_id}",
    response_model=PlaylistResponse,
    summary="Get playlist details",
    description=(
        "Returns full metadata and video list for a single playlist. "
        "Also returns playlists with `status: indexing` or `status: error`, "
        "so the frontend can poll this endpoint while ingestion is in progress."
    ),
    responses={
        404: {"description": "No playlist with this ID exists in the database."},
    },
)
def get_playlist(playlist_id: str):
    result = _get_playlist_with_videos(playlist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist, videos = result
    return _playlist_to_response(playlist, videos)
