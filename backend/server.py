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
from diffusers import (
    StableDiffusionPipeline,
    AutoencoderKL,
    AnimateDiffPipeline,
    MotionAdapter,
    EulerDiscreteScheduler,
)
from diffusers.utils import export_to_gif
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL      = os.getenv("BASE_URL",    "http://127.0.0.1:8000")
OLLAMA_URL    = os.getenv("OLLAMA_URL",  "http://localhost:11434/api/generate")
MODEL_NAME    = os.getenv("MODEL_NAME",  "llama2-uncensored:latest")
SD_PATH       = os.path.normpath(os.path.join(ROOT, os.getenv("SD_PATH",     "models/realistic")))
VAE_PATH      = os.path.normpath(os.path.join(ROOT, os.getenv("VAE_PATH",    "models/vae")))
MOTION_PATH   = os.path.normpath(os.path.join(ROOT, os.getenv("MOTION_PATH", "models/motion")))
MEDIA_FOLDER  = os.path.normpath(os.path.join(ROOT, "media"))
IMAGE_FOLDER  = os.path.normpath(os.path.join(ROOT, "media", "images"))
GIF_FOLDER    = os.path.normpath(os.path.join(ROOT, "media", "gifs"))
MAX_HISTORY   = 20

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
    print(f"VAE not found at {VAE_PATH} — downloading stabilityai/sd-vae-ft-mse...")
    try:
        vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
        os.makedirs(VAE_PATH, exist_ok=True)
        vae.save_pretrained(VAE_PATH)
        print(f"VAE saved to {VAE_PATH}")
    except Exception as e:
        print(f"ERROR: VAE download failed: {e}")
        raise
else:
    vae = AutoencoderKL.from_pretrained(VAE_PATH, torch_dtype=dtype)

# ── Stable Diffusion (still images) ──────────────────────────
print("Loading Stable Diffusion pipeline (images)...")
sd = StableDiffusionPipeline.from_pretrained(SD_PATH, vae=vae, torch_dtype=dtype)
sd = sd.to(device)
if device == "cpu":
    sd.enable_attention_slicing()
sd.safety_checker = None
print("SD pipeline loaded.")

# ── AnimateDiff (GIFs) ────────────────────────────────────────
# Uses the same SD checkpoint + VAE, adds a lightweight motion adapter (~200 MB).
# The motion adapter teaches SD how to generate temporally consistent frames.
print("Loading AnimateDiff motion adapter...")
motion_config = os.path.join(MOTION_PATH, "config.json")
if not os.path.exists(motion_config):
    print(f"Motion adapter not found at {MOTION_PATH} — downloading guoyww/animatediff-motion-adapter-v1-5-2...")
    try:
        adapter = MotionAdapter.from_pretrained(
            "guoyww/animatediff-motion-adapter-v1-5-2", torch_dtype=dtype
        )
        os.makedirs(MOTION_PATH, exist_ok=True)
        adapter.save_pretrained(MOTION_PATH)
        print(f"Motion adapter saved to {MOTION_PATH}")
    except Exception as e:
        print(f"ERROR: Motion adapter download failed: {e}")
        raise
else:
    adapter = MotionAdapter.from_pretrained(MOTION_PATH, torch_dtype=dtype)

print("Building AnimateDiff pipeline...")
ad = AnimateDiffPipeline.from_pretrained(
    SD_PATH,
    motion_adapter=adapter,
    vae=vae,
    torch_dtype=dtype,
)
# EulerDiscreteScheduler with linear beta is the recommended scheduler for AnimateDiff
ad.scheduler = EulerDiscreteScheduler.from_config(
    ad.scheduler.config, beta_schedule="linear"
)
ad = ad.to(device)
ad.safety_checker = None

# RTX 3050 has 4 GB VRAM — these two flags are essential to avoid OOM on 16-frame GIFs
ad.enable_vae_slicing()        # decode frames one at a time instead of all at once
ad.enable_attention_slicing()  # chunk attention computation to save VRAM

print("AnimateDiff pipeline loaded.")

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

# ---------------- IMAGE HELPERS ----------------
def _run_sd(prompt: str, steps: int = 35):
    with torch.inference_mode():
        return sd(
            prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=7.0,
            clip_skip=2,
            width=512,
            height=768,
        ).images[0]

async def generate_image(prompt: str, steps: int = 35) -> str:
    loop = asyncio.get_running_loop()
    img  = await loop.run_in_executor(None, partial(_run_sd, prompt, steps))
    img  = img.resize((1080, 1620), resample=Image.LANCZOS)
    path = os.path.join(IMAGE_FOLDER, f"{uuid.uuid4()}.png")
    img.save(path)
    return os.path.relpath(path, ROOT).replace("\\", "/")

def build_realistic_prompt(base: str, extra: str = "") -> str:
    """
    Pose and direction come from base/extra only — never hardcoded here.
    """
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

# ---------------- ANIMATEDIFF GIF ----------------
def _run_animatediff(prompt: str) -> str:
    """
    Generate animated GIF using AnimateDiff.
    - 16 frames in ONE pipeline pass (not 16 separate calls)
    - 512x512 square (AnimateDiff v1.5 is trained at square resolution)
    - 20 steps balances quality vs speed on RTX 3050 (~45-60s total)
    - Output: all 16 frames as a looping GIF at 8fps = 2s loop
    """
    with torch.inference_mode():
        output = ad(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_frames=16,           # 16 frames = smooth 2s loop at 8fps
            num_inference_steps=20,  # 20 steps — good quality, ~45-60s on RTX 3050
            guidance_scale=7.5,
            clip_skip=2,
            width=512,
            height=512,              # AnimateDiff v1.5 is trained at 512x512
            generator=torch.Generator(device=device).manual_seed(42),
        )

    frames   = output.frames[0]  # list of 16 PIL Images
    filename = f"{uuid.uuid4()}.gif"
    out_path = os.path.join(GIF_FOLDER, filename)
    export_to_gif(frames, out_path, fps=8)
    return f"media/gifs/{filename}"

async def generate_gif(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_run_animatediff, prompt))

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

    # GIF request — AnimateDiff
    gif_keywords = ["gif", "animate", "dancing", "walking", "moving", "motion", "video", "action"]
    if any(kw in user_message.lower() for kw in gif_keywords):
        if not avatar_prompt:
            return {"reply": "Please create an avatar first! Use the settings panel.", "gif": None}
        try:
            prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {user_message}")
            rel_path = await generate_gif(prompt)
            return {"reply": "Here is an animated GIF of me! 🎬", "gif": f"{BASE_URL}/{rel_path}"}
        except Exception as e:
            print(f"[AnimateDiff error] {e}")
            return {"reply": "Sorry, GIF generation failed. Check server logs.", "gif": None}

    # Image request — Stable Diffusion
    image_keywords = ["image", "picture", "photo", "pic", "selfie", "show me", "draw"]
    if any(kw in user_message.lower() for kw in image_keywords):
        if not avatar_prompt:
            return {"reply": "Please create an avatar first! Use the settings panel.", "image": None}
        prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {user_message}")
        rel_path = await generate_image(prompt)
        return {"reply": "Here is a picture of me ❤️", "image": f"{BASE_URL}/{rel_path}"}

    # Text chat — Ollama
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
