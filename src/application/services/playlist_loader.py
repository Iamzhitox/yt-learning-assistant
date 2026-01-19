import asyncio
import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.domain.models import YoutubePlaylist, YoutubeVideo
from src.domain.exceptions import (
    YouTubeAPIKeyError,
    PlaylistNotFoundError,
    VideoDetailsLoadError,
    VideoTranscriptError,
)
from src.infrastructure.adapters.loaders import (
    YoutubeLoaderWithProxy,
    TranscriptFormat,
)
from src.infrastructure.config import (
    GOOGLE_API_KEY,
    API_SERVICE_NAME,
    API_VERSION,
    LANG,
    PROXY_USER,
    PROXY_PASS,
)


class YouTubePlaylistLoader:
    yt_playlist_id: str
    yt_service = None
    yt_playlist: YoutubePlaylist

    def __init__(self, playlist_id: str):
        self.yt_playlist_id = playlist_id
        try:
            self.yt_service = build(
                API_SERVICE_NAME, API_VERSION, developerKey=GOOGLE_API_KEY
            )
        except Exception as e:
            raise YouTubeAPIKeyError(e) from e
        self.yt_playlist = YoutubePlaylist()

    def load_playlist_details(self):
        request = self.yt_service.playlists().list(
            part="snippet, contentDetails, contentDetails",
            id=self.yt_playlist_id,
        )

        try:
            response = request.execute()
            items = response.get("items", [])
            if not items:
                raise PlaylistNotFoundError(self.yt_playlist_id)
            playlist_data = items[0]
        except HttpError as e:
            raise PlaylistNotFoundError(self.yt_playlist_id) from e

        playlist_details = playlist_data.get("snippet", {})

        self.yt_playlist.author = playlist_details.get("channelTitle")
        self.yt_playlist.title = playlist_details.get("title")
        self.yt_playlist.description = playlist_details.get("description")
        self.yt_playlist.lang = playlist_details.get("defaultLanguage")
        self.yt_playlist.date = playlist_details.get("publishedAt")

        thumbnails = playlist_details.get("thumbnails", {})
        thumbnail = thumbnails.get("standard") or thumbnails.get("high") or thumbnails.get("default") or {}
        self.yt_playlist.thumbnail_url = thumbnail.get("url", "")

        content_details = playlist_data.get("contentDetails", {})
        self.yt_playlist.videos_qty = content_details.get("itemCount", 0)

        return self

    def load_video_details(self):
        request = self.yt_service.playlistItems().list(
            part="snippet, contentDetails",
            playlistId=self.yt_playlist_id,
            maxResults=20,
        )

        try:
            result = request.execute()
            items = result.get("items", [])

            if not items:
                return self

            video_ids = [item["contentDetails"]["videoId"] for item in items]
            videos_request = self.yt_service.videos().list(
                part="contentDetails,statistics", id=",".join(video_ids)
            )
            videos_response = videos_request.execute()

            videos_extra_data = {
                v["id"]: {
                    "duration": v["contentDetails"]["duration"],
                    "view_count": v["statistics"].get("viewCount"),
                    "like_count": v["statistics"].get("likeCount"),
                }
                for v in videos_response.get("items", [])
            }

            for video in items:
                video_details = video.get("contentDetails", {})
                video_snippet = video.get("snippet", {})

                video_id = video_details.get("videoId")
                video_position = video_snippet.get("position")
                video_title = video_snippet.get("title")
                video_description = video_snippet.get("description")

                thumbnails = video_snippet.get("thumbnails", {})
                thumbnail = thumbnails.get("standard") or thumbnails.get("high") or thumbnails.get("default") or {}
                video_thumbnail = thumbnail.get("url", "")

                extra = videos_extra_data.get(video_id, {})
                video_duration = self.duration_to_secs(extra.get("duration", ""))
                video_views = int(extra.get("view_count") or 0)
                video_likes = int(extra.get("like_count") or 0)

                self.yt_playlist.duration += video_duration
                self.yt_playlist.total_views += video_views

                yt_video = YoutubeVideo(
                    title=video_title,
                    video_id=video_id,
                    description=video_description,
                    thumbnail_url=video_thumbnail,
                    transcript=[],
                    position=video_position,
                    likes=video_likes,
                    views=video_views,
                    duration=video_duration,
                )

                self.yt_playlist.videos.append(yt_video)

        except HttpError as e:
            raise VideoDetailsLoadError(self.yt_playlist_id, e) from e

        return self

    @staticmethod
    def calculate_end_sec(start_sec: float) -> float:
        return start_sec + 29

    @staticmethod
    def duration_to_secs(duration: str) -> int:
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    async def load_transcript_videos(self, delay_seconds: int = 3):
        for idx, video in enumerate(self.yt_playlist.videos):
            try:
                yt_loader = YoutubeLoaderWithProxy(
                    video_id=video.video_id,
                    language=LANG,
                    chunk_size_seconds=30,
                    transcript_format=TranscriptFormat.CHUNKS,
                    webshare_username=PROXY_USER,
                    webshare_password=PROXY_PASS,
                )
                transcript_lines = yt_loader.load()
            except Exception as e:
                raise VideoTranscriptError(video.video_id, e) from e

            previous_chars_overlap = ""
            for transcript_line in transcript_lines:
                start_sec = transcript_line.metadata.get("start_seconds", 0)
                transcript_line.metadata.update(
                    {
                        "source_type": "video",
                        "video_id": video.video_id,
                        "video_title": video.title,
                        "video_position": video.position,
                        "playlist_id": self.yt_playlist_id,
                        "playlist_title": self.yt_playlist.title,
                        "end_seconds": self.calculate_end_sec(start_sec),
                    }
                )
                if previous_chars_overlap:
                    transcript_line.page_content = (
                        f"{previous_chars_overlap}"
                        f"{transcript_line.page_content}"
                    )
                previous_chars_overlap = transcript_line.page_content[-100:]

            video.transcript = list(transcript_lines)

            if idx < len(self.yt_playlist.videos) - 1:
                await asyncio.sleep(delay_seconds)

        return self

    def build(self):
        return self.yt_playlist
