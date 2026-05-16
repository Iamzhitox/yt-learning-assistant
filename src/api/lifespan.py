import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.application.graph.builder import create_compiled_graph
from src.application.graph.helpers import init_vector_db
from src.infrastructure.config import CHAT_STATE_DIR

app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state["vector_store"] = init_vector_db()
    app_state["ingestion_status"] = {}
    app_state["ingestion_lock"] = asyncio.Lock()

    async with AsyncSqliteSaver.from_conn_string(CHAT_STATE_DIR) as checkpointer:
        app_state["checkpointer"] = checkpointer
        app_state["graph"] = create_compiled_graph(checkpointer)
        yield

    app_state.clear()
