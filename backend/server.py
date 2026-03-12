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
MODEL_NAME   = os.getenv("MODEL_NAME", "llama2-uncensored:latest")
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
sd = sd.to(device)
if device == "cpu":
    sd.enable_attention_slicing()
sd.safety_checker = None
print("SD pipeline loaded.")

# ---------------- NEGATIVE PROMPT ----------------
NEGATIVE_PROMPT = (
    "phone, smartphone, holding phone, selfie stick, camera in hand, "
    "selfie, mirror selfie, hand holding phone, phone visible, "
    "professional photography, studio lighting, studio background, "
    "DSLR, Canon, Nikon, Sony, 85mm, 35mm lens, f/1.8, bokeh, "
    "professional photographer, fashion shoot, magazine cover, "
    "perfect lighting, dramatic lighting, rim light, "
    "8k, UHD, ultra high resolution, "
    "cropped, cut off, out of frame, partial body, headshot only, "
    "close-up only, portrait only, bust only, waist up only, "
    "deformed face, disfigured, bad face, ugly face, "
    "asymmetrical face, cross-eyed, extra eyes, lazy eye, "
    "poorly drawn face, mutated face, mutation, "
    "bad teeth, crooked teeth, bad eyes, bad lips, "
    "double face, cloned face, weird face, "
    "extra fingers, missing fingers, extra limbs, missing limbs, "
    "bad anatomy, bad proportions, deformed body, deformed legs, "
    "deformed feet, bad feet, missing feet, floating limbs, "
    "extra arms, extra hands, fused fingers, disconnected limbs, "
    "unnatural pose, stiff pose, "
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
def build_realistic_prompt(base: str, extra: str = "") -> str:
    """Pose and direction come from base/extra only — never hardcoded here."""
    suffix = (
        "full body shot, full length, head to toe, entire body visible, "
        "photo taken by friend, HD photograph, HD photo, "
        "natural light, realistic everyday background, "
        "photorealistic, hyperrealistic, RAW photo, "
        "detailed face, beautiful face, detailed eyes, realistic eyes, "
        "catchlight in eyes, natural skin texture, "
        "detailed hands, detailed feet, realistic clothing fabric, "
        "masterpiece, best quality, sharp focus"
    )
    parts = [p for p in [base, extra, suffix] if p]
    return ", ".join(parts)

# ---------------- STILL IMAGE ----------------
def _run_sd(prompt: str, steps: int = 35, seed: int = -1):
    generator = None
    if seed >= 0:
        generator = torch.Generator(device=device).manual_seed(seed)
    with torch.inference_mode():
        return sd(
            prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=7.0,
            clip_skip=2,
            width=512,
            height=768,
            generator=generator,
        ).images[0]

async def generate_image(prompt: str, steps: int = 35) -> str:
    loop = asyncio.get_running_loop()
    img  = await loop.run_in_executor(None, partial(_run_sd, prompt, steps))
    img  = img.resize((1080, 1620), resample=Image.LANCZOS)
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
    frames = []
    with torch.inference_mode():
        for seed in GIF_SEEDS:
            generator = torch.Generator(device=device).manual_seed(seed)
            img = sd(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=20,  # 20 steps × 4 frames ≈ same GPU work as 1 still image
                guidance_scale=7.0,
                clip_skip=2,
                width=512,
                height=512,              # square for GIF — fits 4 frames in same VRAM budget
                generator=generator,
            ).images[0]
            frames.append(img)

    # Build looping GIF: forward + reverse so it loops smoothly without a hard jump
    loop_frames = frames + frames[-2:0:-1]   # [0,1,2,3,2,1] — 6 frames, seamless loop

    filename = f"{uuid.uuid4()}.gif"
    out_path = os.path.join(GIF_FOLDER, filename)
    loop_frames[0].save(
        out_path,
        save_all=True,
        append_images=loop_frames[1:],
        duration=120,        # 120ms per frame = ~8fps
        loop=0,              # loop forever
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
                    "temperature":    0.7,
                    "num_predict":    60,
                    "num_ctx":        512,
                    "top_k":          20,
                    "top_p":          0.9,
                    "repeat_penalty": 1.1,
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
    allow_origins=["http://localhost:3000"],
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
            return {"reply": "Please create an avatar first! Use the settings panel.", "gif": None}
        try:
            prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {matched_motion}")
            rel_path = await generate_gif(prompt)
            return {"reply": "Here is an animated GIF of me! 🎬", "gif": f"{BASE_URL}/{rel_path}"}
        except Exception as e:
            print(f"[GIF error] {e}")
            return {"reply": "Sorry, GIF generation failed. Check server logs.", "gif": None}

    # Image keywords
    image_keywords = ["image", "picture", "photo", "pic", "selfie", "show me", "draw"]
    if any(kw in user_message.lower() for kw in image_keywords):
        if not avatar_prompt:
            return {"reply": "Please create an avatar first! Use the settings panel.", "image": None}
        prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {user_message}")
        rel_path = await generate_image(prompt)
        return {"reply": "Here is a picture of me ❤️", "image": f"{BASE_URL}/{rel_path}"}

    # Text chat
    chat_history.append(f"User: {user_message}")
    trim_history()

    sys_prompt = (
        f"You are a {personality} AI companion. "
        f"Appearance: {avatar_prompt}. Outfit: {outfit}.\n"
        f"Recent chat:\n{chr(10).join(chat_history[-4:])}\n"
        f"Reply warmly and in character. 1-2 sentences max."
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

    prompt   = build_realistic_prompt(
        avatar_prompt,
        f"wearing {outfit if outfit else 'casual clothes'}, plain white background"
    )
    rel_path = await generate_image(prompt)
    shutil.copy(os.path.join(ROOT, rel_path), os.path.join(MEDIA_FOLDER, "avatar.png"))
    return {"avatar": f"{BASE_URL}/media/avatar.png"}


@app.post("/changeoutfit")
async def change_outfit(data: OutfitRequest):
    global outfit
    outfit = data.outfit.strip()
    if not outfit:
        raise HTTPException(status_code=400, detail="Outfit cannot be empty.")

    prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, plain background")
    rel_path = await generate_image(prompt)
    return {"reply": f"Outfit changed to {outfit}! 👗", "image": f"{BASE_URL}/{rel_path}"}


@app.post("/setpersonality")
async def set_personality(data: PersonalityRequest):
    global personality
    personality = data.personality.strip()
    if not personality:
        raise HTTPException(status_code=400, detail="Personality cannot be empty.")
    return {"reply": f"Personality set to {personality}! ✨"}
