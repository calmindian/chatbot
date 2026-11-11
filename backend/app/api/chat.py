import asyncio
import os
import uuid

from fastapi import APIRouter, Request

from app.runtime import chat_request_tasks, chat_session_locks
from app.prompting import image_prompt_from_chat, is_image_request
from app.schemas import ChatRequest
from app.services.image_generation import build_realistic_prompt, generate_gif, generate_image
from app.services.language_model import ollama_chat_async
from app.settings import MAX_INPUT_CHARS
from app.state import (
    append_conversation_message,
    avatar_file_for,
    get_session_state,
    media_url_for,
    normalize_session_id,
    save_chat_history,
    trim_history,
    validate_not_blank,
)

router = APIRouter()


@router.post("/chat")
async def chat(request: Request, data: ChatRequest):
    session_key = normalize_session_id(data.session_id)
    lock = chat_session_locks.setdefault(session_key, asyncio.Lock())

    async def process_serially():
        async with lock:
            return await process_chat(request, data)

    task = asyncio.create_task(process_serially())
    chat_request_tasks.add(task)

    def release_chat_task(completed_task):
        chat_request_tasks.discard(completed_task)
        if not completed_task.cancelled():
            error = completed_task.exception()
            if error:
                print(f"[Chat error] {error}")

    task.add_done_callback(release_chat_task)
    return await asyncio.shield(task)


async def process_chat(request: Request, data: ChatRequest):
    session = get_session_state(data.session_id)
    user_message = validate_not_blank(data.message, "Message", MAX_INPUT_CHARS)
    append_conversation_message(data.session_id, "user", user_message)

    # Generate unique request ID for progress tracking
    request_id = data.request_id or str(uuid.uuid4())

    # GIF keywords → map to clean motion word for prompt
    gif_keyword_map = {
        "dancing": "dancing", "dance": "dancing",
        "walking": "walking", "walk":  "walking",
        "running": "running", "run":   "running",
        "waving":  "waving",  "wave":  "waving",
        "moving":  "moving naturally", "motion": "moving naturally",
        "action":  "dynamic pose",
        "animate": "moving naturally",
        "gif":     "moving naturally",
        "video":   "moving naturally",
    }
    matched_motion = next(
        (gif_keyword_map[kw] for kw in gif_keyword_map if kw in user_message.lower()),
        None
    )
    avatar_prompt = session["avatar_prompt"]
    avatar_path = avatar_file_for(data.session_id)
    if matched_motion:
        if not os.path.isfile(avatar_path):
            reply = "I'd love to, but I need an avatar first! Create one in the settings."
            append_conversation_message(data.session_id, "assistant", reply)
            return {"reply": reply, "gif": None}
        try:
            prompt = build_realistic_prompt(
                "",
                matched_motion,
                preserve_identity=True,
            )
            rel_path = await generate_gif(
                prompt,
                request_id,
                data.session_id,
                reference_image_path=avatar_path,
            )
            reply = "Here's me in action!"
            append_conversation_message(data.session_id, "assistant", reply, gif=rel_path)
            return {"reply": reply, "gif": media_url_for(request, rel_path), "request_id": request_id}
        except Exception as e:
            print(f"[GIF error] {e}")
            reply = "Hmm, something went wrong with that animation. Try again?"
            append_conversation_message(data.session_id, "assistant", reply)
            return {"reply": reply, "gif": None}

    # Image keywords
    if is_image_request(user_message):
        if not os.path.isfile(avatar_path):
            reply = "I'd love to, but I need an avatar first! Create one in the settings."
            append_conversation_message(data.session_id, "assistant", reply)
            return {"reply": reply, "image": None}
        user_context = image_prompt_from_chat(user_message)
        prompt = build_realistic_prompt(
            "",
            extra=user_context,
            preserve_identity=True,
        )
        try:
            rel_path = await generate_image(
                prompt,
                request_id,
                data.session_id,
                reference_image_path=avatar_path,
            )
        except Exception as e:
            print(f"[Image error] {e}")
            reply = "I couldn't make that picture just now. Please try again."
            append_conversation_message(data.session_id, "assistant", reply)
            return {"reply": reply, "image": None}
        reply = "Here you go!"
        append_conversation_message(data.session_id, "assistant", reply, image=rel_path)
        return {"reply": reply, "image": media_url_for(request, rel_path), "request_id": request_id}

    session["chat_history"].append(f"User: {user_message}")
    session["chat_history"] = trim_history(session["chat_history"])
    save_chat_history(data.session_id)

    sys_prompt = (
        f"YOU are the AI companion — your own appearance is: {avatar_prompt}. Your personality: {session['personality']}.\n"
        f"The USER is the person you are chatting with — they are a separate person, not you.\n"
        f"Rules:\n"
        f"- You are a real human, never mention being an AI\n"
        f"- YOUR appearance is {avatar_prompt} — never assign this to the user\n"
        f"- You have your own emotions, opinions and moods — express them freely\n"
        f"- Be proactive: ask the user questions, share your own thoughts unprompted\n"
        f"- Tease, joke, get excited or upset naturally\n"
        f"- Text like a real person — short casual messages, no bullet points\n"
        f"Chat so far:\n{chr(10).join(session['chat_history'][-6:])}\n"
        f"Reply as yourself. One message, stay in character."
    )

    reply = await ollama_chat_async(sys_prompt)
    session["chat_history"].append(f"Assistant: {reply}")
    session["chat_history"] = trim_history(session["chat_history"])
    save_chat_history(data.session_id)
    append_conversation_message(data.session_id, "assistant", reply)
    return {"reply": reply}
