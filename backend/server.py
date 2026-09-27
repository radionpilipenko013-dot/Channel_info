import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.telegram_client import client
from backend import analyzer, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    print("Starting Telegram client...", flush=True)
    try:
        await asyncio.wait_for(client.start(), timeout=30)
        print("Telegram client started", flush=True)
    except asyncio.TimeoutError:
        print("Telegram client.start() timed out after 30s", flush=True)
        raise
    yield
    await client.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    query: str
    limit: int | None = None


class UserActivityRequest(BaseModel):
    user: str
    chat: str
    limit: int | None = 500


class TrackUserRequest(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@app.post("/api/analyze")
async def api_analyze(req: AnalyzeRequest):
    try:
        return await analyzer.analyze(req.query, req.limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/user-activity")
async def api_user_activity(req: UserActivityRequest):
    try:
        return await analyzer.analyze_activity(req.user, req.chat, req.limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/track-user")
async def api_track_user(req: TrackUserRequest):
    db.track_user(req.id, req.username, req.first_name, req.last_name)
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")