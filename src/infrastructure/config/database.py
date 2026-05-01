from sqlmodel import create_engine, SQLModel
from .config import CHATS_DB_URL
from src.domain.models import Chat  # noqa: F401

engine = create_engine(CHATS_DB_URL, echo=True, connect_args={"check_same_thread": False})
ENGINE_SESSION_KWARGS = {"expire_on_commit": False}
SQLModel.metadata.create_all(engine)
