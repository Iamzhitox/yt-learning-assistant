"""Extended YouTube loader with Webshare proxy support."""

from typing import Any, Dict, List, Optional, Sequence, Union

from langchain_community.document_loaders.youtube import (
    YoutubeLoader,
    TranscriptFormat,
)
from langchain_core.documents import Document


class YoutubeLoaderWithProxy(YoutubeLoader):
    """
    Extended YouTube loader with Webshare proxy configuration support.

    This class extends the langchain YoutubeLoader to add Webshare proxy
    support for the youtube_transcript_api library, which helps bypass
    IP blocking.

    Example:
        loader = YoutubeLoaderWithProxy(
            video_id="dQw4w9WgXcQ",
            webshare_username="your-username",
            webshare_password="your-password",
            filter_ip_locations=["us", "de"]  # Optional
        )
        documents = loader.load()
    """

    def __init__(
        self,
        video_id: str,
        add_video_info: bool = False,
        language: Union[str, Sequence[str]] = "en",
        translation: Optional[str] = None,
        transcript_format: TranscriptFormat = TranscriptFormat.TEXT,
        continue_on_failure: bool = False,
        chunk_size_seconds: int = 120,
        webshare_username: Optional[str] = None,
        webshare_password: Optional[str] = None,
        filter_ip_locations: Optional[List[str]] = None,
    ):
        """
        Initialize with video ID and optional Webshare proxy config.

        Args:
            video_id: YouTube video ID
            add_video_info: Whether to add video metadata
            language: Language(s) for transcript
            translation: Language to translate to
            transcript_format: Format of the transcript output
            continue_on_failure: Whether to continue on errors
            chunk_size_seconds: Size of chunks in seconds
            webshare_username: Webshare proxy username (from dashboard)
            webshare_password: Webshare proxy password (from dashboard)
            filter_ip_locations: Optional list of country codes to
                filter IPs (e.g., ["us", "de"])
        """
        super().__init__(
            video_id=video_id,
            add_video_info=add_video_info,
            language=language,
            translation=translation,
            transcript_format=transcript_format,
            continue_on_failure=continue_on_failure,
            chunk_size_seconds=chunk_size_seconds,
        )
        self.webshare_username = webshare_username
        self.webshare_password = webshare_password
        self.filter_ip_locations = filter_ip_locations

    @classmethod
    def from_youtube_url(
        cls,
        youtube_url: str,
        webshare_username: Optional[str] = None,
        webshare_password: Optional[str] = None,
        filter_ip_locations: Optional[List[str]] = None,
        **kwargs: Any
    ) -> "YoutubeLoaderWithProxy":
        """
        Create loader from YouTube URL with optional Webshare proxy.

        Args:
            youtube_url: Full YouTube URL
            webshare_username: Webshare proxy username
            webshare_password: Webshare proxy password
            filter_ip_locations: Optional list of country codes to filter IPs
            **kwargs: Additional arguments passed to constructor

        Returns:
            YoutubeLoaderWithProxy instance
        """
        video_id = cls.extract_video_id(youtube_url)
        return cls(
            video_id,
            webshare_username=webshare_username,
            webshare_password=webshare_password,
            filter_ip_locations=filter_ip_locations,
            **kwargs
        )

    def load(self) -> List[Document]:
        """Load YouTube transcripts with Webshare proxy support."""
        try:
            from youtube_transcript_api import (
                FetchedTranscript,
                NoTranscriptFound,
                TranscriptsDisabled,
                YouTubeTranscriptApi,
            )
            from youtube_transcript_api.proxies import WebshareProxyConfig
        except ImportError:
            raise ImportError(
                'Could not import "youtube_transcript_api" Python package. '
                "Please install it with `pip install youtube-transcript-api`."
            )

        if self.add_video_info:
            video_info = self._get_video_info()
            self._metadata.update(video_info)

        try:
            # Create YouTubeTranscriptApi with Webshare proxy if provided
            if self.webshare_username and self.webshare_password:
                proxy_config = WebshareProxyConfig(
                    proxy_username=self.webshare_username,
                    proxy_password=self.webshare_password,
                    filter_ip_locations=self.filter_ip_locations,
                )
                ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
            else:
                ytt_api = YouTubeTranscriptApi()

            transcript_list = ytt_api.list(self.video_id)
        except TranscriptsDisabled:
            return []

        try:
            transcript = transcript_list.find_transcript(self.language)
        except NoTranscriptFound:
            transcript = transcript_list.find_transcript(["en"])

        if self.translation is not None:
            transcript = transcript.translate(self.translation)

        transcript_object = transcript.fetch()

        if isinstance(transcript_object, FetchedTranscript):
            transcript_pieces = [
                {
                    "text": snippet.text,
                    "start": snippet.start,
                    "duration": snippet.duration,
                }
                for snippet in transcript_object.snippets
            ]
        else:
            # type: ignore[no-redef]
            transcript_pieces: List[Dict[str, Any]] = transcript_object

        if self.transcript_format == TranscriptFormat.TEXT:
            transcript = " ".join(
                map(
                    lambda piece: piece["text"].strip(" "),
                    transcript_pieces,
                )
            )
            return [Document(page_content=transcript, metadata=self._metadata)]
        elif self.transcript_format == TranscriptFormat.LINES:
            return list(
                map(
                    lambda piece: Document(
                        page_content=piece["text"].strip(" "),
                        metadata=dict(
                            filter(
                                lambda item: item[0] != "text",
                                piece.items(),
                            )
                        ),
                    ),
                    transcript_pieces,
                )
            )
        elif self.transcript_format == TranscriptFormat.CHUNKS:
            return list(self._get_transcript_chunks(transcript_pieces))
        else:
            raise ValueError("Unknown transcript format.")
