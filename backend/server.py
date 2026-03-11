import os
import uuid
import requests
import torch
import json
import asyncio
import shutil
import imageio
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
os.makedirs(GIF_FOLDER, exist_ok=True)

# ---------------- LOAD MODELS ----------------
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype  = torch.float16 if device == "cuda" else torch.float32
print(f"Device: {device.upper()}  |  dtype: {dtype}")

# Load VAE separately for sharper, more accurate faces
# (Realistic Vision noVAE edition requires an external VAE)
print("Loading VAE...")
vae_config = os.path.join(VAE_PATH, "config.json")
if not os.path.exists(vae_config):
    print(f"VAE not found at {VAE_PATH}")
    print("Downloading VAE (stabilityai/sd-vae-ft-mse)...")
    try:
        vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
        os.makedirs(VAE_PATH, exist_ok=True)
        vae.save_pretrained(VAE_PATH)
        print(f"VAE saved to {VAE_PATH}")
    except Exception as e:
        print(f"ERROR: Failed to load/download VAE: {e}")
        print("Make sure you have internet connection or run setup_offline.bat to pre-download models")
        raise
else:
    vae = AutoencoderKL.from_pretrained(VAE_PATH, torch_dtype=dtype)

print("Loading Realistic Vision pipeline...")
sd = StableDiffusionPipeline.from_pretrained(
    SD_PATH,
    vae=vae,
    torch_dtype=dtype,
)
sd = sd.to(device)
if device == "cpu":
    sd.enable_attention_slicing()   # saves RAM on CPU
sd.safety_checker = None
print("Models loaded.")

# ---------------- NEGATIVE PROMPT ----------------
# Full-body focused — blocks cropped shots AND face/anatomy defects
NEGATIVE_PROMPT = (
    # block phones and selfie artifacts
    "phone, smartphone, holding phone, selfie stick, camera in hand, "
    "selfie, mirror selfie, hand holding phone, phone visible, "
    # block professional photography look
    "professional photography, studio lighting, studio background, "
    "DSLR, Canon, Nikon, Sony, 85mm, 35mm lens, f/1.8, bokeh, "
    "professional photographer, fashion shoot, magazine cover, "
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
    # body / anatomy
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

# ---------------- IMAGE HELPERS ----------------
def _run_sd(prompt: str, steps: int = 35):
    """
    Run SD synchronously in a thread executor.
    512x768 — taller than square so full body fits vertically.
    guidance_scale=7.0, clip_skip=2 for natural realistic look.
    """
    with torch.inference_mode():
        return sd(
            prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=7.0,
            clip_skip=2,
            width=600,
            height=800,   # portrait ratio — gives room for full body head to toe
        ).images[0]

async def generate_image(prompt: str, steps: int = 35) -> str:
    """Offload SD to a thread so FastAPI event loop stays free."""
    loop = asyncio.get_running_loop()
    img  = await loop.run_in_executor(None, partial(_run_sd, prompt, steps))
    path = os.path.join(IMAGE_FOLDER, f"{uuid.uuid4()}.png")
    img.save(path)
    rel  = os.path.relpath(path, ROOT).replace("\\", "/")
    return rel

def build_realistic_prompt(base: str, extra: str = "") -> str:
    """
    Full-body photorealistic prompt.
    Pose and direction come entirely from base/extra — never hardcoded here.
    Only framing (full body) and quality keywords are enforced globally.
    """
    suffix = (
        # framing — full body always, NO forced pose or direction
        "full body shot, full length, head to toe, entire body visible, "
        # photo feel
        "photo taken by friend, HD photograph, HD photo, "
        "natural light, realistic everyday background, "
        # realism
        "photorealistic, hyperrealistic, RAW photo, "
        # face quality
        "detailed face, beautiful face, detailed eyes, realistic eyes, "
        "catchlight in eyes, natural skin texture, "
        # body quality
        "detailed hands, detailed feet, realistic clothing fabric, "
        # quality
        "masterpiece, best quality, sharp focus"
    )
    parts = [p for p in [base, extra, suffix] if p]
    return ", ".join(parts)

async def generate_gif(prompt: str) -> str:
    """Generate smooth GIF with consistent scene and subtle motion variations."""
    loop = asyncio.get_running_loop()

    def _run_gif():
        """Generate GIF by adding small perturbations to a single base latent."""
        frames = []

        with torch.inference_mode():
            # Generate one base latent to keep scene consistent
            base_generator = torch.Generator(device=device).manual_seed(42)
            base_latent = torch.randn(
                (1, 4, 64, 64),  # SD latent shape
                generator=base_generator,
                device=device,
                dtype=dtype,
            )

            # Generate frames with tiny perturbations to the base latent
            # This keeps the scene, pose, and face consistent while adding subtle motion
            num_frames = 10
            perturbation_scale = 0.08  # Small noise = subtle variations only

            for frame_idx in range(num_frames):
                # Add very small Gaussian noise to base latent
                perturbation = torch.randn_like(base_latent) * perturbation_scale
                latent = base_latent + perturbation

                # Decode the perturbed latent into an image
                img = sd(
                    prompt=prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    num_inference_steps=25,
                    guidance_scale=7.0,
                    clip_skip=2,
                    width=512,
                    height=512,
                    latents=latent,
                ).images[0]

                frames.append(img)

        # Save as GIF
        filename = f"{uuid.uuid4()}.gif"
        out_path = os.path.join(GIF_FOLDER, filename)

        imageio.mimsave(out_path, frames, duration=0.15, loop=0)  # 6.7 fps

        return f"media/gifs/{filename}"

    rel_path = await loop.run_in_executor(None, _run_gif)
    return rel_path

# ---------------- OLLAMA ----------------
def _ollama_sync(prompt: str) -> str:
    """Synchronous Ollama call — always run via executor, never call directly in async code."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature":  0.7,
                    "num_predict":  150,   # was 80 — shorter = faster, still full sentences
                    "num_ctx":      512,  # context window — 512 is plenty for chat; default 4096 is slow
                    "top_k":        20,   # focus sampling — faster inference
                    "top_p":        0.9,
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
    """Run Ollama in a thread executor so FastAPI event loop is never blocked."""
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
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── No-cache middleware for media files ────────────────────
@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/media"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
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

    gif_keywords = ["gif", "animate", "dancing", "walking", "moving", "motion", "video", "action"]
    if any(kw in user_message.lower() for kw in gif_keywords):
        if not avatar_prompt:
            return {"reply": "Please create an avatar first! Use the settings panel.", "gif": None}
        try:
            prompt = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {user_message}")
            rel_path = await generate_gif(prompt)
            return {"reply": "Here is an animated GIF of me! 🎬", "gif": f"{BASE_URL}/{rel_path}"}
        except Exception as e:
            return {"reply": f"Sorry, GIF generation failed: {str(e)}", "gif": None}

    image_keywords = ["image", "picture", "photo", "pic", "selfie", "show me", "draw"]
    if any(kw in user_message.lower() for kw in image_keywords):
        if not avatar_prompt:
            return {"reply": "Please create an avatar first! Use the settings panel.", "image": None}
        prompt   = build_realistic_prompt(avatar_prompt, f"wearing {outfit}, {user_message}")
        rel_path = await generate_image(prompt)
        return {"reply": "Here is a picture of me ❤️", "image": f"{BASE_URL}/{rel_path}"}

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

    prompt   = build_realistic_prompt(
        avatar_prompt,
        f"wearing {outfit}, plain background"
    )
    rel_path = await generate_image(prompt)
    return {"reply": f"Outfit changed to {outfit}! 👗", "image": f"{BASE_URL}/{rel_path}"}


@app.post("/setpersonality")
async def set_personality(data: PersonalityRequest):
    global personality
    personality = data.personality.strip()
    if not personality:
        raise HTTPException(status_code=400, detail="Personality cannot be empty.")
    return {"reply": f"Personality set to {personality}! ✨"}
