import os
import shutil
import uuid
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.schemas import AvatarRequest, PersonalityRequest
from app.services.image_generation import build_realistic_prompt, generate_image
from app.settings import (
    MAX_AVATAR_PIXELS,
    MAX_AVATAR_UPLOAD_BYTES,
    MAX_PERSONALITY_CHARS,
    MAX_PROMPT_CHARS,
    ROOT,
)
from app.state import (
    append_conversation_message,
    avatar_file_for,
    get_session_state,
    media_url_for,
    normalize_session_id,
    save_session_settings,
    validate_not_blank,
)

router = APIRouter()


@router.post("/setavatar")
async def set_avatar(request: Request, data: AvatarRequest):
    session = get_session_state(data.session_id)
    avatar_value = validate_not_blank(data.prompt, "Avatar prompt", MAX_PROMPT_CHARS)

    request_id = data.request_id or str(uuid.uuid4())
    prompt = build_realistic_prompt(
        avatar_value,
        background="avatar",
    )
    rel_path = await generate_image(prompt, request_id, data.session_id)
    generated_path = os.path.join(ROOT, rel_path)

    avatar_path = avatar_file_for(data.session_id)
    shutil.copy(generated_path, avatar_path)
    session["avatar_prompt"] = avatar_value
    save_session_settings(data.session_id)
    return {
        "avatar": media_url_for(request, f"media/avatars/{normalize_session_id(data.session_id)}.png"),
        "avatar_prompt": session["avatar_prompt"],
        "request_id": request_id,
    }


@router.post("/uploadavatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    avatar_prompt: str = Form(""),
):
    content = await file.read(MAX_AVATAR_UPLOAD_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Choose an image to upload.")
    if len(content) > MAX_AVATAR_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, or WebP image.")
            if image.width * image.height > MAX_AVATAR_PIXELS:
                raise HTTPException(status_code=400, detail="Image dimensions are too large.")
            image.verify()

        with Image.open(BytesIO(content)) as image:
            avatar = ImageOps.exif_transpose(image).convert("RGB")
            output = BytesIO()
            avatar.save(output, format="PNG", optimize=True)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid supported image.") from exc

    avatar_bytes = output.getvalue()

    session = get_session_state(session_id)
    session["avatar_prompt"] = (
        validate_not_blank(avatar_prompt, "Avatar prompt", MAX_PROMPT_CHARS)
        if avatar_prompt.strip()
        else ""
    )
    avatar_path = avatar_file_for(session_id)
    temporary_path = f"{avatar_path}.{uuid.uuid4()}.tmp"
    try:
        with open(temporary_path, "wb") as avatar_file:
            avatar_file.write(avatar_bytes)
        os.replace(temporary_path, avatar_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

    save_session_settings(session_id)
    return {
        "avatar": media_url_for(request, f"media/avatars/{normalize_session_id(session_id)}.png"),
        "avatar_prompt": session["avatar_prompt"],
    }


@router.post("/setpersonality")
async def set_personality(data: PersonalityRequest):
    session = get_session_state(data.session_id)
    personality_value = validate_not_blank(data.personality, "Personality", MAX_PERSONALITY_CHARS)
    session["personality"] = personality_value
    save_session_settings(data.session_id)
    reply = f"I'll be more {personality_value} from now on."
    append_conversation_message(data.session_id, "assistant", reply)
    return {"reply": reply}
