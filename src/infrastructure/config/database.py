from sqlmodel import create_engine, SQLModel
from .config import CHATS_DB_URL
from src.domain.models import Chat  # noqa: F401

engine = create_engine(CHATS_DB_URL, echo=True)
SQLModel.metadata.create_all(engine)
