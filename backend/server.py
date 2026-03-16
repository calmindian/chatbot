import os
import uuid
import requests
import torch
import json
import asyncio
import shutil
import numpy as np
from PIL import Image
from functools import partial
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from diffusers import StableDiffusionPipeline, AutoencoderKL
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL     = os.getenv("BASE_URL",   "http://127.0.0.1:8000")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME   = os.getenv("MODEL_NAME", "dolphin-mistral:latest")
SD_PATH      = os.path.normpath(os.path.join(ROOT, os.getenv("SD_PATH",  "models/realistic")))
VAE_PATH     = os.path.normpath(os.path.join(ROOT, os.getenv("VAE_PATH", "models/vae")))
MEDIA_FOLDER = os.path.normpath(os.path.join(ROOT, "media"))
IMAGE_FOLDER = os.path.normpath(os.path.join(ROOT, "media", "images"))
GIF_FOLDER   = os.path.normpath(os.path.join(ROOT, "media", "gifs"))
MAX_HISTORY  = 20

os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(GIF_FOLDER,   exist_ok=True)

# ---------------- LOAD MODELS ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype  = torch.float16 if device == "cuda" else torch.float32
print(f"Device: {device.upper()}  |  dtype: {dtype}")

# ── VAE ───────────────────────────────────────────────────────
print("Loading VAE...")
vae_config = os.path.join(VAE_PATH, "config.json")
if not os.path.exists(vae_config):
    print(f"VAE not found — downloading stabilityai/sd-vae-ft-mse...")
    vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
    os.makedirs(VAE_PATH, exist_ok=True)
    vae.save_pretrained(VAE_PATH)
else:
    vae = AutoencoderKL.from_pretrained(VAE_PATH, torch_dtype=dtype)

# ── Stable Diffusion ──────────────────────────────────────────
# Single pipeline used for BOTH still images and GIFs.
# AnimateDiff was removed — on RTX 3050 (4 GB VRAM) it requires swapping
# 2 GB of weights CPU<->GPU which adds 20-30s overhead, making GIFs slower
# than plain SD. GIFs are now generated as 4 SD frames + PIL assembly.
print("Loading Stable Diffusion pipeline...")
sd = StableDiffusionPipeline.from_pretrained(SD_PATH, vae=vae, torch_dtype=dtype)
# Keep SD on CPU at startup — only move to GPU when generating images.
# This frees the full 4GB VRAM for Ollama during chat, making replies much faster.
sd = sd.to("cpu")
sd.enable_attention_slicing()
sd.safety_checker = None
sd_on_gpu = False
print("SD pipeline loaded on CPU (will move to GPU only for image generation).")

# ---------------- NEGATIVE PROMPT ----------------
NEGATIVE_PROMPT = (
    # phones / selfie artifacts
    "phone, smartphone, holding phone, selfie stick, camera in hand, "
    "selfie, mirror selfie, hand holding phone, phone visible, "
    # studio / professional look
    "professional photography, studio lighting, studio background, "
    "DSLR, Canon, Nikon, Sony, 85mm, 35mm lens, f/1.8, bokeh, "
    "perfect lighting, dramatic lighting, rim light, "
    "8k, UHD, ultra high resolution, "
    # crop / framing defects
    "cropped, cut off, out of frame, partial body, headshot only, "
    "close-up only, portrait only, bust only, waist up only, "
    # face defects
    "deformed face, disfigured, bad face, ugly face, "
    "asymmetrical face, cross-eyed, extra eyes, lazy eye, "
    "poorly drawn face, mutated face, mutation, "
    "bad teeth, crooked teeth, bad eyes, bad lips, "
    "double face, cloned face, weird face, "
    # body / anatomy defects
    "extra fingers, missing fingers, extra limbs, missing limbs, "
    "bad anatomy, bad proportions, deformed body, deformed legs, "
    "deformed feet, bad feet, missing feet, floating limbs, "
    "extra arms, extra hands, fused fingers, disconnected limbs, "
    "unnatural pose, stiff pose, "
    # quality
    "cartoon, anime, illustration, painting, drawing, sketch, "
    "blurry, out of focus, soft focus, low quality, low resolution, "
    "watermark, signature, text, logo, username, "
    "oversaturated, undersaturated, plastic skin, waxy skin, "
    "fake, 3d render, cgi, airbrushed, "
    "worst quality, normal quality, jpeg artifacts, noise, grain"
)

# ---------------- GLOBAL STATE ----------------
avatar_prompt: str = ""
chat_history:  list = []
personality:   str  = "friendly"
outfit:        str  = "casual"

# ---------------- PYDANTIC MODELS ----------------
class ChatRequest(BaseModel):
    message: str

class AvatarRequest(BaseModel):
    prompt: str

class OutfitRequest(BaseModel):
    outfit: str

class PersonalityRequest(BaseModel):
    personality: str

# ---------------- PROMPT BUILDER ----------------
def build_realistic_prompt(base: str, extra: str = "", background: str = "natural") -> str:
    """Build a natural image prompt from base description and context."""
    # Use natural descriptors instead of technical photography terms
    suffix = (
        "natural pose, realistic lighting, high quality"
    )

    # Build context based on background type
    if background == "plain":
        context = "simple, plain white background"
    elif background == "avatar":
        context = "clean white background, professional look"
    else:
        context = "in a natural everyday setting"

    parts = [p for p in [base, extra, context, suffix] if p]
    return ", ".join(parts)

# ---------------- STILL IMAGE ----------------
def _run_sd(prompt: str, steps: int = 45, seed: int = -1):
    global sd_on_gpu
    # Move SD to GPU only while generating, then return it to CPU
    # so Ollama gets the full VRAM budget for chat responses
    if device == "cuda" and not sd_on_gpu:
        sd.to("cuda")
        sd_on_gpu = True
        print("[SD] Moved to GPU")
    generator = None
    if seed >= 0:
        generator = torch.Generator(device=device).manual_seed(seed)
    with torch.inference_mode():
        result = sd(
            prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=7.0,
            clip_skip=2,
            width=600,
            height=800,
            generator=generator,
        ).images[0]
    # Move back to CPU and free VRAM for Ollama
    if device == "cuda":
        sd.to("cpu")
        sd_on_gpu = False
        torch.cuda.empty_cache()
        print("[SD] Returned to CPU, VRAM freed")
    return result

async def generate_image(prompt: str, steps: int = 45) -> str:
    loop = asyncio.get_running_loop()
    img  = await loop.run_in_executor(None, partial(_run_sd, prompt, steps))
    path = os.path.join(IMAGE_FOLDER, f"{uuid.uuid4()}.png")
    img.save(path)
    return os.path.relpath(path, ROOT).replace("\\", "/")

# ---------------- GIF (SD multi-frame) ----------------
# Why not AnimateDiff: on RTX 3050 (4 GB VRAM) AnimateDiff cannot share VRAM
# with SD. Pipeline swapping moves ~2 GB of weights CPU<->GPU twice per GIF,
# adding 20-30s of overhead with no visible quality benefit at this resolution.
#
# This approach: generate 4 frames at 20 steps each using the SD pipeline that
# is already hot on GPU. Total ~20s. Frames use nearby seeds so they share the
# same general composition and feel like a smooth loop.
GIF_SEEDS = [42, 43, 44, 45]  # close seeds = similar composition per frame

def _run_gif(prompt: str) -> str:
    global sd_on_gpu
    if device == "cuda" and not sd_on_gpu:
        sd.to("cuda")
        sd_on_gpu = True
        print("[SD] Moved to GPU for GIF")
    frames = []
    with torch.inference_mode():
        for seed in GIF_SEEDS:
            generator = torch.Generator(device=device).manual_seed(seed)
            img = sd(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=45,
                guidance_scale=7.0,
                clip_skip=2,
                width=256,
                height=256,
                generator=generator,
            ).images[0]
            frames.append(img)

    # Move back to CPU and free VRAM
    if device == "cuda":
        sd.to("cpu")
        sd_on_gpu = False
        torch.cuda.empty_cache()
        print("[SD] Returned to CPU, VRAM freed")

    loop_frames = frames + frames[-2:0:-1]
    filename = f"{uuid.uuid4()}.gif"
    out_path = os.path.join(GIF_FOLDER, filename)
    loop_frames[0].save(
        out_path,
        save_all=True,
        append_images=loop_frames[1:],
        duration=120,
        loop=0,
        optimize=False,
    )
    return f"media/gifs/{filename}"

async def generate_gif(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_run_gif, prompt))

# ---------------- OLLAMA ----------------
def _ollama_sync(prompt: str) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature":    0.75,  # slightly higher = more natural varied replies
                    "num_predict":    300,   # chat replies rarely need more than 300 tokens
                    "num_ctx":        1024,  # 1024 = fastest chat on 4GB VRAM, still enough for context
                    "top_k":          40,    # higher = better word choices, more accurate
                    "top_p":          0.9,
                    "repeat_penalty": 1.15,  # slightly higher = less repetitive
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        print(f"[Ollama error] {e}")
        return "I'm having a little trouble thinking right now — try again in a moment! 💭"

async def ollama_chat_async(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ollama_sync, prompt)

# ---------------- CHAT HISTORY ----------------
def trim_history():
    global chat_history
    if len(chat_history) > MAX_HISTORY:
        chat_history = chat_history[-MAX_HISTORY:]

HISTORY_FILE = os.path.join(ROOT, "chat_history.json")

def save_chat_history():
    with open(HISTORY_FILE, "w") as f:
        json.dump(chat_history, f, indent=2)

def load_chat_history():
    global chat_history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            chat_history = json.load(f)

load_chat_history()

# ---------------- FASTAPI ----------------
app = FastAPI(title="AI Friend Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://192.168.10.113:3000"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"]        = "no-cache"
        response.headers["Expires"]       = "0"
    return response

app.mount("/media", StaticFiles(directory=MEDIA_FOLDER), name="media")

# ---------------- ROUTES ----------------

@app.get("/health")
async def health():
    return {
        "status":      "ok",
        "llm_model":   MODEL_NAME,
        "sd_device":   device,
        "personality": personality,
    }


@app.post("/chat")
async def chat(data: ChatRequest):
    global chat_history, avatar_prompt, personality, outfit

    user_message = data.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

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
    if matched_motion:
        if not avatar_prompt:
            return {"reply": "I'd love to, but I need an avatar first! Create one in the settings.", "gif": None}
        try:
            prompt   = build_realistic_prompt(avatar_prompt, f"{matched_motion} in {outfit.lower()}")
            rel_path = await generate_gif(prompt)
            return {"reply": "Here's me in action!", "gif": f"{BASE_URL}/{rel_path}"}
        except Exception as e:
            print(f"[GIF error] {e}")
            return {"reply": "Hmm, something went wrong with that animation. Try again?", "gif": None}

    # Image keywords
    image_keywords = ["image", "picture", "photo", "pic", "selfie", "show me", "draw"]
    if any(kw in user_message.lower() for kw in image_keywords):
        if not avatar_prompt:
            return {"reply": "I'd love to, but I need an avatar first! Create one in the settings.", "image": None}
        # Clean up user prompt for more natural results
        user_context = user_message.lower()
        for kw in image_keywords:
            user_context = user_context.replace(kw, "").strip()
        extra = f"in {outfit.lower()}, {user_context}" if user_context else f"in {outfit.lower()}"
        prompt   = build_realistic_prompt(avatar_prompt, extra)
        rel_path = await generate_image(prompt)
        return {"reply": "Here you go!", "image": f"{BASE_URL}/{rel_path}"}

    # Text chat
    chat_history.append(f"User: {user_message}")
    trim_history()

    sys_prompt = (
        f"YOU are the AI companion — your own appearance is: {avatar_prompt}. Your outfit: {outfit}. Your personality: {personality}.\n"
        f"The USER is the person you are chatting with — they are a separate person, not you.\n"
        f"Rules:\n"
        f"- You are a real human, never mention being an AI\n"
        f"- YOUR appearance is {avatar_prompt} — never assign this to the user\n"
        f"- You have your own emotions, opinions and moods — express them freely\n"
        f"- Be proactive: ask the user questions, share your own thoughts unprompted\n"
        f"- Tease, joke, get excited or upset naturally\n"
        f"- Text like a real person — short casual messages, no bullet points\n"
        f"Chat so far:\n{chr(10).join(chat_history[-6:])}\n"
        f"Reply as yourself. One message, stay in character."
    )

    reply = await ollama_chat_async(sys_prompt)
    chat_history.append(f"Assistant: {reply}")
    trim_history()
    save_chat_history()

    return {"reply": reply}


@app.post("/setavatar")
async def set_avatar(data: AvatarRequest):
    global avatar_prompt
    avatar_prompt = data.prompt.strip()
    if not avatar_prompt:
        raise HTTPException(status_code=400, detail="Avatar prompt cannot be empty.")

    outfit_text = outfit.lower() if outfit else "casual clothes"
    prompt   = build_realistic_prompt(
        avatar_prompt,
        f"in {outfit_text}",
        background="avatar"
    )
    rel_path = await generate_image(prompt, steps=45)
    shutil.copy(os.path.join(ROOT, rel_path), os.path.join(MEDIA_FOLDER, "avatar.png"))
    return {"avatar": f"{BASE_URL}/media/avatar.png"}


@app.post("/changeoutfit")
async def change_outfit(data: OutfitRequest):
    global outfit
    outfit = data.outfit.strip()
    if not outfit:
        raise HTTPException(status_code=400, detail="Outfit cannot be empty.")

    prompt   = build_realistic_prompt(avatar_prompt, f"in {outfit.lower()}", background="plain")
    rel_path = await generate_image(prompt)
    return {"reply": f"All dressed up in {outfit}!", "image": f"{BASE_URL}/{rel_path}"}


@app.post("/setpersonality")
async def set_personality(data: PersonalityRequest):
    global personality
    personality = data.personality.strip()
    if not personality:
        raise HTTPException(status_code=400, detail="Personality cannot be empty.")
    return {"reply": f"I'll be more {personality} from now on."}


@app.post("/reset")
async def reset_all():
    global avatar_prompt, chat_history, personality, outfit

    # Clear in-memory state
    avatar_prompt = ""
    chat_history  = []
    personality   = "friendly"
    outfit        = "casual"

    # Delete all generated images and GIFs
    for folder in [IMAGE_FOLDER, GIF_FOLDER]:
        for f in os.listdir(folder):
            fpath = os.path.join(folder, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except Exception as e:
                print(f"[reset] Could not delete {fpath}: {e}")

    # Delete avatar.png
    avatar_path = os.path.join(MEDIA_FOLDER, "avatar.png")
    if os.path.exists(avatar_path):
        try:
            os.remove(avatar_path)
        except Exception as e:
            print(f"[reset] Could not delete avatar.png: {e}")

    # Delete chat history file
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except Exception as e:
            print(f"[reset] Could not delete chat_history.json: {e}")

    return {"reply": "All data cleared — media, avatar and chat history deleted."}
