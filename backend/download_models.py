"""One-time model download. Run with:
    docker compose run --rm backend python download_models.py
Saves into /app/models (the `models` volume)."""
import os
from diffusers import StableDiffusionPipeline, AutoencoderKL

SD_MODEL_ID = "SG161222/Realistic_Vision_V5.1_noVAE"   # photorealistic SD1.5 (DreamShaper looks painterly)
SD_PATH = "/app/models/realistic"
VAE_MODEL_ID = "stabilityai/sd-vae-ft-mse"
VAE_PATH = "/app/models/vae"

if not os.path.exists(os.path.join(SD_PATH, "model_index.json")):
    print(f"Downloading {SD_MODEL_ID} (~2-4 GB)...")
    StableDiffusionPipeline.from_pretrained(SD_MODEL_ID, safety_checker=None).save_pretrained(SD_PATH)
    print("SD model saved.")
else:
    print("Realistic Vision already present -- skipping.")

if not os.path.exists(os.path.join(VAE_PATH, "config.json")):
    print(f"Downloading {VAE_MODEL_ID} (~335 MB)...")
    AutoencoderKL.from_pretrained(VAE_MODEL_ID).save_pretrained(VAE_PATH)
    print("VAE saved.")
else:
    print("VAE already present -- skipping.")
