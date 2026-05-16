from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.lifespan import app_state, lifespan
from src.api.routers.chat import router as chat_router
from src.api.routers.files import router as files_router
from src.api.routers.history import router as history_router
from src.api.routers.playlists import router as playlists_router

app = FastAPI(title="YT Learning Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Chat-Id"],
)

app.include_router(playlists_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(files_router)


@app.on_event("startup")
async def _sync_app_state():
    # Mirror app_state dict into app.state for Depends(Request) access
    pass


@app.middleware("http")
async def _attach_state(request, call_next):
    for key, value in app_state.items():
        setattr(request.app.state, key, value)
    return await call_next(request)
