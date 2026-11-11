"""Stable Diffusion initialization and image/GIF generation."""

import asyncio
import hashlib
import os
import threading
import uuid
from functools import partial

import torch
from diffusers import (
    AutoencoderKL,
    DPMSolverMultistepScheduler,
    StableDiffusionImg2ImgPipeline,
    StableDiffusionPipeline,
)
from PIL import Image, ImageOps

from app.settings import (
    GIF_FOLDER, GIF_HEIGHT, GIF_WIDTH, IMAGE_FOLDER, IMAGE_HEIGHT,
    IMAGE_WIDTH, ROOT, SD_PATH, VAE_PATH,
)
from app.state import normalize_session_id

LOW_VRAM = torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory < 6 * 1024**3
sd_generation_lock = threading.Lock()
gen_progress: dict[str, dict[str, int | str]] = {}
gen_progress_lock = threading.Lock()
MAX_PROGRESS_ENTRIES = 100


def set_generation_progress(request_id: str, progress: int, kind: str) -> None:
    with gen_progress_lock:
        if request_id not in gen_progress and len(gen_progress) >= MAX_PROGRESS_ENTRIES:
            gen_progress.pop(next(iter(gen_progress)))
        gen_progress[request_id] = {"progress": progress, "type": kind}


def get_generation_progress(request_id: str) -> dict[str, int | str] | None:
    with gen_progress_lock:
        progress = gen_progress.get(request_id)
        if progress and progress["progress"] >= 100:
            del gen_progress[request_id]
        return progress


def clear_generation_progress() -> None:
    with gen_progress_lock:
        gen_progress.clear()

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
# Realistic Vision ships a DEIS scheduler config, so force DPM++ 2M Karras explicitly.
sd.scheduler = DPMSolverMultistepScheduler.from_config(
    sd.scheduler.config,
    algorithm_type="dpmsolver++",
    solver_order=2,
    use_karras_sigmas=True,
)
sd.enable_attention_slicing()
sd.enable_vae_slicing()
if device == "cuda":
    if LOW_VRAM:
        print("[SD] Low-VRAM mode enabled for smaller portrait generation")
        sd.enable_model_cpu_offload()
    try:
        sd.enable_xformers_memory_efficient_attention()
        print("[SD] xFormers enabled for better quality")
    except Exception:
        print("[SD] xFormers not available, using standard attention")
sd.safety_checker = None
sd_img2img = StableDiffusionImg2ImgPipeline.from_pipe(sd)
print(f"SD pipeline loaded on {device.upper()} (optimized for anatomy/hand quality).")

# ---------------- NEGATIVE PROMPT ----------------
NEGATIVE_PROMPT = (
    "(watermark:1.5), text, logo, signature, cropped feet, out of frame, bad anatomy, "
    "extra limbs, extra fingers, cartoon, anime, blurry"
)
IDENTITY_NEGATIVE_PROMPT = (
    "face swap, different face, changed identity, distorted face, deformed face, malformed eyes"
)
REFERENCE_IMAGE_STRENGTH = 0.68

# ---------------- PROMPT BUILDER ----------------
def build_realistic_prompt(
    base: str,
    extra: str = "",
    background: str = "natural",
    preserve_identity: bool = False,
) -> str:
    """Build a photo-realistic, full-body prompt around the persona description."""
    framing = "full-body, head-to-toe, standing person, vertical photo, centered, distant"
    identity = (
        "same person as reference, preserve facial identity and natural facial proportions, "
        "symmetrical face, clearly defined eyes and mouth, same eyes, nose, lips, skin tone, "
        "hairstyle, body shape and proportions; "
        "change only the requested outfit, pose and background"
        if preserve_identity else ""
    )

    # Build context based on background type
    if background == "plain":
        context = "simple, plain white background, clean background"
    elif background == "avatar":
        context = "plain light grey background, soft natural window light"
    else:
        context = "in a natural everyday setting, natural environment"

    remaining_base = base
    remaining_extra = extra
    remaining_context = context
    quality = "photorealistic"
    parts = [framing, identity, remaining_base, remaining_extra, remaining_context, quality]
    parts = [part for part in parts if part]
    prompt = ", ".join(parts)
    while len(sd.tokenizer(prompt, truncation=False)["input_ids"]) > sd.tokenizer.model_max_length:
        if remaining_extra:
            remaining_extra = remaining_extra[:-8].rsplit(" ", 1)[0].strip()
        elif remaining_context:
            remaining_context = ""
        elif quality:
            quality = ""
        elif len(remaining_base) > 32:
            remaining_base = remaining_base[:-8].rsplit(" ", 1)[0].strip()
        else:
            break
        parts = [
            part for part in (
                framing,
                identity,
                remaining_base,
                remaining_extra,
                remaining_context,
                quality,
            ) if part
        ]
        prompt = ", ".join(parts)
    return prompt

# ---------------- STILL IMAGE ----------------
def identity_seed(session_id: str | None) -> int:
    digest = hashlib.sha256(normalize_session_id(session_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _run_sd(
    prompt: str,
    request_id: str,
    steps: int = 32,
    seed: int = 0,
    total_frames: int = 1,
    reference_image_path: str | None = None,
):
    with sd_generation_lock:
        return _run_sd_locked(prompt, request_id, steps, seed, total_frames, reference_image_path)


def _run_sd_locked(
    prompt: str,
    request_id: str,
    steps: int = 32,
    seed: int = 0,
    total_frames: int = 1,
    reference_image_path: str | None = None,
):
    # Progress callback for diffusers pipeline
    def callback_on_step_end(pipe, step_idx, timestep, callback_kwargs):
        base_progress = (step_idx + 1) / steps
        if total_frames > 1:
            frame_idx = (step_idx * total_frames) // steps
            adjusted_progress = frame_idx / total_frames + (base_progress / total_frames)
        else:
            adjusted_progress = base_progress
        set_generation_progress(
            request_id,
            min(99, int(adjusted_progress * 100)),
            "image" if total_frames == 1 else "gif",
        )
        return callback_kwargs

    generator = torch.Generator(device=device).manual_seed(seed)
    inference_args = {
        "prompt": prompt,
        "negative_prompt": f"{NEGATIVE_PROMPT}, {IDENTITY_NEGATIVE_PROMPT}",
        "num_inference_steps": steps,
        "guidance_scale": 7.0,
        "clip_skip": 1,
        "generator": generator,
        "callback_on_step_end": callback_on_step_end,
    }
    reference_image = None
    if reference_image_path:
        with Image.open(reference_image_path) as source:
            reference_image = ImageOps.fit(
                ImageOps.exif_transpose(source).convert("RGB"),
                (IMAGE_WIDTH, IMAGE_HEIGHT),
                method=Image.Resampling.LANCZOS,
            )

    def run_pipeline():
        with torch.inference_mode():
            if reference_image is not None:
                return sd_img2img(
                    image=reference_image,
                    strength=REFERENCE_IMAGE_STRENGTH,
                    **inference_args,
                ).images[0]
            return sd(
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                **inference_args,
            ).images[0]

    try:
        return run_pipeline()
    except RuntimeError as e:
        if device == "cuda" and "out of memory" in str(e).lower():
            print(f"[SD] CUDA OOM, retrying on CPU with reduced settings: {e}")
            sd.to("cpu")
            torch.cuda.empty_cache()
            inference_args["num_inference_steps"] = 16
            inference_args["guidance_scale"] = 5.5
            inference_args["generator"] = torch.Generator(device="cpu").manual_seed(seed)
            try:
                return run_pipeline()
            finally:
                sd.to(device)
        raise

async def generate_image(
    prompt: str,
    request_id: str,
    session_id: str | None = None,
    reference_image_path: str | None = None,
) -> str:
    loop = asyncio.get_running_loop()
    img = await loop.run_in_executor(
        None,
        partial(
            _run_sd,
            prompt,
            request_id,
            32,
            identity_seed(session_id),
            1,
            reference_image_path,
        ),
    )
    set_generation_progress(request_id, 100, "image")
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
GIF_SEED_OFFSETS = [0, 1, 2, 3]
GIF_STEPS = 24

def _run_gif(
    prompt: str,
    request_id: str,
    seed: int,
    reference_image_path: str | None = None,
) -> str:
    with sd_generation_lock:
        return _run_gif_locked(prompt, request_id, seed, reference_image_path)


def _run_gif_locked(
    prompt: str,
    request_id: str,
    seed: int,
    reference_image_path: str | None = None,
) -> str:
    # SD remains on GPU full-time for faster generation
    frames = []
    reference_image = None
    if reference_image_path:
        with Image.open(reference_image_path) as source:
            reference_image = ImageOps.fit(
                ImageOps.exif_transpose(source).convert("RGB"),
                (GIF_WIDTH, GIF_HEIGHT),
                method=Image.Resampling.LANCZOS,
            )
    with torch.inference_mode():
        for frame_idx, seed_offset in enumerate(GIF_SEED_OFFSETS):
            generator = torch.Generator(device=device).manual_seed((seed + seed_offset) % (2**32))

            # Progress callback
            def callback_on_step_end(pipe, step_idx, timestep, callback_kwargs):
                step_progress = (step_idx + 1) / GIF_STEPS
                frame_progress = (frame_idx + step_progress) / len(GIF_SEED_OFFSETS)
                set_generation_progress(request_id, min(99, int(frame_progress * 100)), "gif")
                return callback_kwargs

            inference_args = {
                "prompt": prompt,
                "negative_prompt": f"{NEGATIVE_PROMPT}, {IDENTITY_NEGATIVE_PROMPT}",
                "num_inference_steps": GIF_STEPS,
                "guidance_scale": 7.0,
                "clip_skip": 1,
                "generator": generator,
                "callback_on_step_end": callback_on_step_end,
            }
            if reference_image is not None:
                img = sd_img2img(
                    image=reference_image,
                    strength=REFERENCE_IMAGE_STRENGTH,
                    **inference_args,
                ).images[0]
            else:
                img = sd(width=GIF_WIDTH, height=GIF_HEIGHT, **inference_args).images[0]
            frames.append(img)

    set_generation_progress(request_id, 100, "gif")
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

async def generate_gif(
    prompt: str,
    request_id: str,
    session_id: str | None = None,
    reference_image_path: str | None = None,
) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(_run_gif, prompt, request_id, identity_seed(session_id), reference_image_path),
    )
