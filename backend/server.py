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
from diffusers import StableDiffusionPipeline, AutoencoderKL, DPMSolverMultistepScheduler
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# Progress tracking for image/GIF generation
gen_progress = {}  # {request_id: {"progress": 0-100, "type": "image|gif"}}
# ─────────────────────────────────────────────────────────────

# ---------------- LOAD ENV ----------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL     = os.getenv("BASE_URL",   "http://127.0.0.1:8000")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME   = os.getenv("MODEL_NAME", "mistral:latest")
SD_PATH      = os.path.normpath(os.path.join(ROOT, os.getenv("SD_PATH",  "models/dreamshaper")))
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
# Keep SD on GPU full-time for faster image/GIF generation.
# Chat (Ollama) will be slower due to shared VRAM, but image generation will be much faster.
sd = sd.to(device)
# Optimize for quality: use DPMSolver scheduler (better anatomy/details)
sd.scheduler = DPMSolverMultistepScheduler.from_config(sd.scheduler.config, use_karras_sigmas=True)
sd.enable_attention_slicing()
if device == "cuda":
    try:
        sd.enable_xformers_memory_efficient_attention()
        print("[SD] xFormers enabled for better quality")
    except Exception:
        print("[SD] xFormers not available, using standard attention")
sd.safety_checker = None
sd_on_gpu = True if device == "cuda" else False
print(f"SD pipeline loaded on {device.upper()} (optimized for anatomy/hand quality).")

# ---------------- NEGATIVE PROMPT ----------------
NEGATIVE_PROMPT = (
    # NOTE: photo words (DSLR, bokeh, studio lighting, 8k, 85mm, professional photography)
    # were removed from here -- putting them in the negative prompt pushes the model
    # AWAY from a photographic look.
    # look / style we do NOT want
    "cartoon, anime, illustration, painting, drawing, sketch, digital art, "
    "cgi, 3d render, semi-realistic, airbrushed, smooth skin, plastic skin, waxy skin, "
    "oversaturated, over-sharpened, "
    # eyes
    "bad eyes, empty eyes, dead eyes, deformed iris, deformed pupils, "
    "asymmetrical eyes, cross-eyed, lazy eye, uneven eyes, "
    # phones / selfie artifacts
    "phone, smartphone, holding phone, selfie stick, mirror selfie, "
    # framing defects
    "cropped, cut off, out of frame, partial body, "
    # face defects
    "deformed face, disfigured, ugly, poorly drawn face, mutated face, mutation, "
    "bad teeth, double face, cloned face, "
    # anatomy defects
    "extra fingers, missing fingers, extra limbs, missing limbs, "
    "bad anatomy, bad proportions, deformed body, deformed legs, "
    "extra arms, extra hands, fused fingers, too many fingers, long neck, "
    # quality
    "blurry, out of focus, low quality, low resolution, worst quality, "
    "jpeg artifacts, watermark, signature, text, logo, username"
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
    """Build a natural image prompt from base description and context, optimized for humans."""
    # Use quality descriptors that improve human generation
    suffix = (
        "RAW photo, candid photograph, natural light, "
        "detailed skin texture, visible pores, subtle skin imperfections, "
        "film grain, sharp focus, natural expression, 35mm photo"
    )

    # Build context based on background type
    if background == "plain":
        context = "simple, plain white background, clean background"
    elif background == "avatar":
        context = "plain light grey background, soft natural window light"
    else:
        context = "in a natural everyday setting, natural environment"

    parts = [p for p in [base, extra, context, suffix] if p]
    return ", ".join(parts)

# ---------------- STILL IMAGE ----------------
def _run_sd(prompt: str, request_id: str, steps: int = 30, seed: int = -1, total_frames: int = 1):
    # Progress callback for diffusers pipeline
    def callback_on_step_end(pipe, step_idx, timestep, callback_kwargs):
        # For images: step_idx goes 0 to steps-1
        # For GIFs: we'll scale appropriately
        base_progress = (step_idx + 1) / steps
        # Account for multiple frames in GIF (frames 0-3 will be 0%, then each frame adds ~25%)
        if total_frames > 1:
            frame_idx = (step_idx * total_frames) // steps
            adjusted_progress = frame_idx / total_frames + (base_progress / (steps * total_frames))
        else:
            adjusted_progress = base_progress
        gen_progress[request_id] = {
            "progress": min(99, int(adjusted_progress * 100)),  # cap at 99%, 100% will be set when done
            "type": "image" if total_frames == 1 else "gif"
        }
        return callback_kwargs

    # DreamShaper: optimized for photorealistic humans, good color & detail
    # 60 steps balances quality + speed
    generator = None
    if seed >= 0:
        generator = torch.Generator(device=device).manual_seed(seed)
    with torch.inference_mode():
        result = sd(
            prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=steps,
            guidance_scale=6.5,  # 5-7 looks photographic; 8+ gives a plastic/painted look
            clip_skip=1,  # full text encoder for anatomical accuracy
            width=512,
            height=768,  # increased for better full-body proportions
            generator=generator,
            callback_on_step_end=callback_on_step_end,
        ).images[0]
    return result

async def generate_image(prompt: str, request_id: str, steps: int = 30) -> str:
    loop = asyncio.get_running_loop()
    img  = await loop.run_in_executor(None, partial(_run_sd, prompt, request_id, steps, -1, 1))
    gen_progress[request_id] = {"progress": 100, "type": "image"}
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

def _run_gif(prompt: str, request_id: str) -> str:
    # SD remains on GPU full-time for faster generation
    frames = []
    with torch.inference_mode():
        for frame_idx, seed in enumerate(GIF_SEEDS):
            generator = torch.Generator(device=device).manual_seed(seed)

            # Progress callback
            def callback_on_step_end(pipe, step_idx, timestep, callback_kwargs):
                # Each frame is ~25%, scale by frame and step
                step_progress = (step_idx + 1) / 25  # GIF uses 25 steps
                frame_progress = (frame_idx + step_progress) / len(GIF_SEEDS)
                gen_progress[request_id] = {
                    "progress": min(99, int(frame_progress * 100)),
                    "type": "gif"
                }
                return callback_kwargs

            img = sd(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=25,  # lower for GIF speed
                guidance_scale=6.5,  # 5-7 looks photographic; 8+ gives a plastic/painted look
                clip_skip=1,  # full text encoder for anatomical accuracy
                width=256,
                height=320,  # increased for better proportions
                generator=generator,
                callback_on_step_end=callback_on_step_end,
            ).images[0]
            frames.append(img)

    gen_progress[request_id] = {"progress": 100, "type": "gif"}
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

async def generate_gif(prompt: str, request_id: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_run_gif, prompt, request_id))

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

HISTORY_FILE = os.path.join(os.getenv("DATA_DIR", ROOT), "chat_history.json")

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
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
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


@app.get("/progress/{request_id}")
async def get_progress(request_id: str):
    """Get generation progress for image/GIF."""
    if request_id in gen_progress:
        return gen_progress[request_id]
    return {"progress": 0, "type": "unknown"}

@app.post("/chat")
async def chat(data: ChatRequest):
    global chat_history, avatar_prompt, personality, outfit

    user_message = data.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Generate unique request ID for progress tracking
    request_id = str(uuid.uuid4())

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
            rel_path = await generate_gif(prompt, request_id)
            return {"reply": "Here's me in action!", "gif": f"{BASE_URL}/{rel_path}", "request_id": request_id}
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
        rel_path = await generate_image(prompt, request_id)
        return {"reply": "Here you go!", "image": f"{BASE_URL}/{rel_path}", "request_id": request_id}

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

    request_id = str(uuid.uuid4())
    outfit_text = outfit.lower() if outfit else "casual clothes"
    prompt   = build_realistic_prompt(
        avatar_prompt,
        f"in {outfit_text}",
        background="avatar"
    )
    rel_path = await generate_image(prompt, request_id, steps=30)
    shutil.copy(os.path.join(ROOT, rel_path), os.path.join(MEDIA_FOLDER, "avatar.png"))
    return {"avatar": f"{BASE_URL}/media/avatar.png", "request_id": request_id}


@app.post("/changeoutfit")
async def change_outfit(data: OutfitRequest):
    global outfit
    outfit = data.outfit.strip()
    if not outfit:
        raise HTTPException(status_code=400, detail="Outfit cannot be empty.")

    request_id = str(uuid.uuid4())
    prompt   = build_realistic_prompt(avatar_prompt, f"in {outfit.lower()}", background="plain")
    rel_path = await generate_image(prompt, request_id)
    return {"reply": f"All dressed up in {outfit}!", "image": f"{BASE_URL}/{rel_path}", "request_id": request_id}


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