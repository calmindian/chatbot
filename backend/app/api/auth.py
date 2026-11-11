"""Shared-password login and session management."""

import hmac
import time

from fastapi import APIRouter, HTTPException, Request

from app.schemas import PasswordLoginRequest
from app.settings import APP_PASSWORD

router = APIRouter(prefix="/auth")
LOGIN_WINDOW_SECONDS = 60
MAX_LOGIN_ATTEMPTS = 5
failed_logins: dict[str, tuple[int, float]] = {}


@router.get("/status")
async def auth_status(request: Request):
    return {"authenticated": request.session.get("authenticated") is True}


@router.post("/login")
async def login(request: Request, data: PasswordLoginRequest):
    client_ip = request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )
    now = time.monotonic()
    for ip, (_, started_at) in tuple(failed_logins.items()):
        if now - started_at >= LOGIN_WINDOW_SECONDS:
            del failed_logins[ip]
    attempts, window_start = failed_logins.get(client_ip, (0, now))
    if now - window_start >= LOGIN_WINDOW_SECONDS:
        attempts, window_start = 0, now
    if attempts >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in one minute.")

    if not hmac.compare_digest(data.password.encode("utf-8"), APP_PASSWORD.encode("utf-8")):
        if client_ip not in failed_logins and len(failed_logins) >= 1024:
            failed_logins.pop(next(iter(failed_logins)))
        failed_logins[client_ip] = (attempts + 1, window_start)
        raise HTTPException(status_code=401, detail="Incorrect password.")

    failed_logins.pop(client_ip, None)
    request.session["authenticated"] = True
    return {"authenticated": True}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}
