from fastapi import Request
from langchain_chroma import Chroma


def get_graph(request: Request):
    return request.app.state.graph


def get_vector_store(request: Request) -> Chroma:
    return request.app.state.vector_store


def get_checkpointer(request: Request):
    return request.app.state.checkpointer


def get_ingestion_lock(request: Request):
    return request.app.state.ingestion_lock


def get_ingestion_status(request: Request) -> dict:
    return request.app.state.ingestion_status
