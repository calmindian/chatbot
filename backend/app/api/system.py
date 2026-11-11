import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app import state
from app.services.image_generation import device, get_generation_progress
from app.settings import AVATAR_FOLDER, DEFAULT_SESSION_ID, GIF_FOLDER, IMAGE_FOLDER, MODEL_NAME, ROOT
from app.state import avatar_file_for, get_session_state, media_url_for, normalize_session_id, state_lock

router = APIRouter()


@router.get("/health")
async def health():
    session = get_session_state(DEFAULT_SESSION_ID)
    return {
        "status":      "ok",
        "llm_model":   MODEL_NAME,
        "sd_device":   device,
        "personality": session["personality"],
        "server_data_version": state.server_data_version,
    }


@router.get("/conversation")
async def get_conversation(request: Request, session_id: str = DEFAULT_SESSION_ID):
    session = get_session_state(session_id)
    messages = []
    with state_lock:
        for message in session["messages"]:
            item = message.copy()
            for key in ("image", "gif"):
                if item.get(key):
                    item[key] = media_url_for(request, item[key])
            messages.append(item)
        avatar_path = avatar_file_for(session_id)
        avatar_url = None
        if os.path.isfile(avatar_path):
            avatar_version = os.stat(avatar_path).st_mtime_ns
            avatar_url = f"{media_url_for(request, f'media/avatars/{normalize_session_id(session_id)}.png')}?t={avatar_version}"
        return {
            "messages": messages,
            "avatar_prompt": session["avatar_prompt"],
            "personality": session["personality"],
            "avatar_url": avatar_url,
        }


@router.get("/collection")
async def get_media_collection(request: Request):
    items = []
    for folder, kind in (
        (IMAGE_FOLDER, "image"),
        (GIF_FOLDER, "gif"),
        (AVATAR_FOLDER, "avatar"),
    ):
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                modified = entry.stat(follow_symlinks=False).st_mtime
                relative_path = os.path.relpath(entry.path, ROOT).replace("\\", "/")
                items.append({
                    "url": f"{media_url_for(request, relative_path)}?t={int(modified * 1000)}",
                    "kind": kind,
                    "created_at": datetime.fromtimestamp(modified, timezone.utc).isoformat(),
                })
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items}


@router.get("/progress/{request_id}")
async def get_progress(request_id: str):
    """Get generation progress for image/GIF."""
    progress = get_generation_progress(request_id)
    if progress:
        return progress
    return {"progress": 0, "type": "unknown"}
