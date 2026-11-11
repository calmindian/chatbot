import asyncio
import os
import shutil
import uuid

from fastapi import APIRouter

from app import runtime, state
from app.schemas import ResetRequest
from app.services.image_generation import (
    clear_generation_progress,
    sd_generation_lock,
)
from app.settings import (
    AVATAR_FOLDER,
    GIF_FOLDER,
    HISTORY_DIR,
    IMAGE_FOLDER,
    MEDIA_FOLDER,
    ROOT,
)
from app.state import (
    avatar_file_for,
    conversation_file_for,
    get_session_state,
    history_file_for,
    save_server_data_version,
    session_settings_file_for,
)

router = APIRouter()


@router.post("/reset")
async def reset_all(data: ResetRequest | None = None):
    payload = data or ResetRequest()
    session = get_session_state(payload.session_id)

    previous_messages = list(session["messages"])
    session["avatar_prompt"] = ""
    session["chat_history"] = []
    session["messages"] = []
    session["personality"] = "friendly"

    for message in previous_messages:
        for key in ("image", "gif"):
            relative_path = message.get(key)
            if not relative_path:
                continue
            media_path = os.path.realpath(os.path.join(ROOT, relative_path))
            if os.path.commonpath([ROOT, media_path]) != ROOT:
                continue
            try:
                if os.path.isfile(media_path):
                    os.remove(media_path)
            except OSError as e:
                print(f"[reset] Could not delete {media_path}: {e}")

    avatar_path = avatar_file_for(payload.session_id)
    if os.path.exists(avatar_path):
        try:
            os.remove(avatar_path)
        except Exception as e:
            print(f"[reset] Could not delete avatar.png: {e}")

    history_path = history_file_for(payload.session_id)
    if os.path.exists(history_path):
        try:
            os.remove(history_path)
        except Exception as e:
            print(f"[reset] Could not delete chat history: {e}")

    conversation_path = conversation_file_for(payload.session_id)
    if os.path.exists(conversation_path):
        try:
            os.remove(conversation_path)
        except Exception as e:
            print(f"[reset] Could not delete conversation history: {e}")

    settings_path = session_settings_file_for(payload.session_id)
    if os.path.exists(settings_path):
        try:
            os.remove(settings_path)
        except Exception as e:
            print(f"[reset] Could not delete persona settings: {e}")

    return {"reply": "All data cleared — media, avatar and chat history deleted."}


def clear_directory_contents(directory: str):
    os.makedirs(directory, exist_ok=True)
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)


async def acquire_sd_generation_lock():
    acquire_task = asyncio.create_task(asyncio.to_thread(sd_generation_lock.acquire))
    try:
        await asyncio.shield(acquire_task)
    except asyncio.CancelledError:
        await acquire_task
        sd_generation_lock.release()
        raise


@router.post("/delete-all-data")
async def delete_all_server_data():
    async with runtime.delete_all_lock:
        try:
            async with runtime.data_mutation_condition:
                runtime.deleting_all_data = True
                await runtime.data_mutation_condition.wait_for(
                    lambda: runtime.active_mutation_requests == 0
                )
            if runtime.chat_request_tasks:
                await asyncio.gather(*tuple(runtime.chat_request_tasks), return_exceptions=True)
            await acquire_sd_generation_lock()
            try:
                with state.state_lock:
                    for directory in (HISTORY_DIR, IMAGE_FOLDER, GIF_FOLDER, AVATAR_FOLDER):
                        clear_directory_contents(directory)
                    legacy_avatar_path = os.path.join(MEDIA_FOLDER, "avatar.png")
                    if os.path.isfile(legacy_avatar_path):
                        os.remove(legacy_avatar_path)
                    state.session_state.clear()
                    clear_generation_progress()
                    state.server_data_version = uuid.uuid4().hex
                    save_server_data_version(state.server_data_version)
            finally:
                sd_generation_lock.release()
        finally:
            async with runtime.data_mutation_condition:
                runtime.deleting_all_data = False
                runtime.data_mutation_condition.notify_all()

    return {
        "reply": "All chats, persona settings, avatars, and generated media were deleted. Downloaded models were kept.",
        "server_data_version": state.server_data_version,
    }
