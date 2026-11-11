import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from app import runtime
from app.api import auth, chat, data, personas, system
from app.settings import (
    APP_PASSWORD,
    APP_SESSION_SECRET,
    CORS_ORIGINS,
    DEFAULT_SESSION_ID,
    MEDIA_FOLDER,
    SESSION_COOKIE_SECURE,
)
from app.state import load_chat_history

if not APP_PASSWORD.isdigit() or len(APP_PASSWORD) != 4:
    raise RuntimeError("Set APP_PASSWORD to a four-digit PIN.")
if len(APP_SESSION_SECRET) < 32:
    raise RuntimeError("Set APP_SESSION_SECRET to a value at least 32 characters long.")

load_chat_history(DEFAULT_SESSION_ID)

app = FastAPI(title="AI Friend Backend")

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in {"/auth/status", "/auth/login"}:
            return await call_next(request)
        if request.session.get("authenticated") is True:
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})


app.add_middleware(AuthenticationMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SESSION_SECRET,
    session_cookie="ai_friend_session",
    same_site="strict",
    https_only=SESSION_COOKIE_SECURE,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|\[[0-9A-Fa-f:]+\])(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media") or request.url.path == "/conversation":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def coordinate_data_deletion(request: Request, call_next):
    if request.method != "POST" or request.url.path == "/delete-all-data":
        return await call_next(request)

    async with runtime.data_mutation_condition:
        await runtime.data_mutation_condition.wait_for(lambda: not runtime.deleting_all_data)
        runtime.active_mutation_requests += 1
    try:
        return await call_next(request)
    finally:
        async with runtime.data_mutation_condition:
            runtime.active_mutation_requests -= 1
            runtime.data_mutation_condition.notify_all()


app.mount("/media", StaticFiles(directory=MEDIA_FOLDER), name="media")
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(personas.router)
app.include_router(data.router)
