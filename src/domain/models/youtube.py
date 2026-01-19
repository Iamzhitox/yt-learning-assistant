from pydantic import BaseModel, Field
from langchain_core.documents import Document


class YoutubeVideo(BaseModel):
    title: str = Field(default="")
    video_id: str = Field(default="")
    description: str = Field(default="")
    transcript: list[Document] = Field(default=[])
    thumbnail_url: str = Field(default="")
    position: int = Field(default=-1)
    duration: int = Field(default=0)
    views: int = Field(default=0)
    likes: int = Field(default=0)


class YoutubePlaylist(BaseModel):
    author: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    videos: list[YoutubeVideo] = Field(default=[])
    videos_qty: int = Field(default=0)
    thumbnail_url: str = Field(default="")
    lang: str = Field(default="")
    date: str = Field(default="")
    duration: int = Field(default=0)
    total_views: int = Field(default=0)
