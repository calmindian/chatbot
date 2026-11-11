"""Session state and JSON-backed persistence."""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.settings import (
    AVATAR_FOLDER, BASE_URL, DEFAULT_SESSION_ID, HISTORY_DIR, MAX_HISTORY,
    SERVER_DATA_VERSION_FILE,
)

state_lock = threading.RLock()
session_state = {}


def save_server_data_version(version: str) -> None:
    temporary_path = f"{SERVER_DATA_VERSION_FILE}.{uuid.uuid4()}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            file.write(version)
        os.replace(temporary_path, SERVER_DATA_VERSION_FILE)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def load_server_data_version() -> str:
    if os.path.isfile(SERVER_DATA_VERSION_FILE):
        with open(SERVER_DATA_VERSION_FILE, "r", encoding="utf-8") as file:
            version = file.read().strip()
        if version:
            return version
    version = uuid.uuid4().hex
    save_server_data_version(version)
    return version


server_data_version = load_server_data_version()


def normalize_session_id(session_id: str | None) -> str:
    raw = (session_id or DEFAULT_SESSION_ID).strip()
    raw = raw or DEFAULT_SESSION_ID
    if len(raw) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        raise HTTPException(status_code=400, detail="Invalid conversation ID.")
    return raw


def session_settings_file_for(session_id: str | None = None) -> str:
    return os.path.join(HISTORY_DIR, f"{normalize_session_id(session_id)}_settings.json")


def avatar_file_for(session_id: str | None = None) -> str:
    return os.path.join(AVATAR_FOLDER, f"{normalize_session_id(session_id)}.png")


def save_session_settings(session_id: str | None = None):
    session_key = normalize_session_id(session_id)
    state = get_session_state(session_key)
    path = session_settings_file_for(session_key)
    temporary_path = f"{path}.{uuid.uuid4()}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump({
                "avatar_prompt": state["avatar_prompt"],
                "personality": state["personality"],
            }, file, indent=2)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def get_session_state(session_id: str | None = None):
    session_key = normalize_session_id(session_id)
    with state_lock:
        if session_key not in session_state:
            state = {
                "avatar_prompt": "",
                "chat_history": [],
                "messages": [],
                "personality": "friendly",
            }
            history_path = os.path.join(HISTORY_DIR, f"{session_key}.json")
            conversation_path = os.path.join(HISTORY_DIR, f"{session_key}_messages.json")
            settings_path = os.path.join(HISTORY_DIR, f"{session_key}_settings.json")
            if os.path.isfile(history_path):
                with open(history_path, "r", encoding="utf-8") as file:
                    state["chat_history"] = json.load(file)
            if os.path.isfile(conversation_path):
                with open(conversation_path, "r", encoding="utf-8") as file:
                    state["messages"] = json.load(file)
            elif state["chat_history"]:
                for item in state["chat_history"]:
                    role, separator, text = item.partition(": ")
                    if separator and role in {"User", "Assistant"}:
                        state["messages"].append({
                            "id": str(uuid.uuid4()),
                            "role": "user" if role == "User" else "assistant",
                            "text": text,
                            "image": None,
                            "gif": None,
                            "time": datetime.now(timezone.utc).isoformat(),
                        })
            if os.path.isfile(settings_path):
                with open(settings_path, "r", encoding="utf-8") as file:
                    settings = json.load(file)
                state.update({
                    key: settings[key]
                    for key in ("avatar_prompt", "personality")
                    if key in settings
                })
            session_state[session_key] = state
        return session_state[session_key]


def validate_not_blank(value: str, field_name: str, max_len: int):
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty.")
    if len(cleaned) > max_len:
        raise HTTPException(status_code=400, detail=f"{field_name} must be {max_len} characters or fewer.")
    return cleaned


# ---------------- CHAT HISTORY ----------------
def trim_history(history):
    if len(history) > MAX_HISTORY:
        return history[-MAX_HISTORY:]
    return history


def build_public_base_url(request=None) -> str:
    if request is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
        return f"{forwarded_proto}://{forwarded_host}"
    return BASE_URL


def media_url_for(request, relative_path: str) -> str:
    return f"{build_public_base_url(request)}/{relative_path.lstrip('/')}"


def history_file_for(session_id: str | None = None) -> str:
    normalized = normalize_session_id(session_id)
    return os.path.join(HISTORY_DIR, f"{normalized}.json")


def save_chat_history(session_id: str | None = None):
    state = get_session_state(session_id)
    path = history_file_for(session_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state["chat_history"], f, indent=2)


def load_chat_history(session_id: str | None = None):
    state = get_session_state(session_id)
    path = history_file_for(session_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            state["chat_history"] = json.load(f)
    return state


def conversation_file_for(session_id: str | None = None) -> str:
    normalized = normalize_session_id(session_id)
    return os.path.join(HISTORY_DIR, f"{normalized}_messages.json")


def save_conversation(session_id: str | None = None):
    state = get_session_state(session_id)
    path = conversation_file_for(session_id)
    temporary_path = f"{path}.{uuid.uuid4()}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(state["messages"], file, indent=2)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def append_conversation_message(
    session_id: str | None,
    role: str,
    text: str,
    image: str | None = None,
    gif: str | None = None,
):
    state = get_session_state(session_id)
    message = {
        "id": str(uuid.uuid4()),
        "role": role,
        "text": text,
        "image": image,
        "gif": gif,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    with state_lock:
        state["messages"].append(message)
        save_conversation(session_id)
    return message
