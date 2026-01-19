class InvalidPlaylistUrlError(ValueError):
    """Could not extract playlist ID from the URL."""

    def __init__(self, url: str):
        super().__init__(f"Could not extract playlist ID from URL: {url}")
        self.url = url


class PlaylistNotFoundError(ValueError):
    """The playlist does not exist or is not accessible."""

    def __init__(self, playlist_id: str):
        super().__init__(f"Playlist not found or not accessible: {playlist_id}")
        self.playlist_id = playlist_id


class PlaylistLoadError(RuntimeError):
    """Failed to load playlist data from YouTube."""

    def __init__(self, playlist_id: str, original_error: Exception):
        super().__init__(
            f"Failed to load playlist '{playlist_id}': {original_error}"
        )
        self.playlist_id = playlist_id
        self.original_error = original_error


class PlaylistDocumentsNotFoundError(ValueError):
    """No documents found for the given playlist ID."""

    def __init__(self, playlist_id: str):
        super().__init__(f"No documents found for playlist_id: {playlist_id}")
        self.playlist_id = playlist_id


class EmptyPlaylistDocumentsError(ValueError):
    """All documents are empty for the given playlist ID."""

    def __init__(self, playlist_id: str):
        super().__init__(
            f"All documents are empty for playlist_id: {playlist_id}"
        )
        self.playlist_id = playlist_id


class TranscriptLoadError(RuntimeError):
    """Failed to load video transcripts."""

    def __init__(self, playlist_id: str, original_error: Exception):
        super().__init__(
            f"Failed to load transcripts for playlist '{playlist_id}': {original_error}"
        )
        self.playlist_id = playlist_id
        self.original_error = original_error


class YouTubeAPIError(RuntimeError):
    """General error from YouTube API."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class YouTubeAPIKeyError(YouTubeAPIError):
    """YouTube API key is invalid or missing."""

    def __init__(self, original_error: Exception | None = None):
        super().__init__(
            "YouTube API key is invalid or missing. Check GOOGLE_YT_API_KEY configuration.",
            original_error,
        )


class VideoDetailsLoadError(RuntimeError):
    """Failed to load video details from YouTube."""

    def __init__(self, playlist_id: str, original_error: Exception):
        super().__init__(
            f"Failed to load video details for playlist '{playlist_id}': {original_error}"
        )
        self.playlist_id = playlist_id
        self.original_error = original_error


class VideoTranscriptError(RuntimeError):
    """Failed to load transcript for a specific video."""

    def __init__(self, video_id: str, original_error: Exception):
        super().__init__(
            f"Failed to load transcript for video '{video_id}': {original_error}"
        )
        self.video_id = video_id
        self.original_error = original_error
