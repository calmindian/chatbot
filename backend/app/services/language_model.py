"""Ollama chat completion client."""

import asyncio

import requests

from app.settings import MODEL_NAME, OLLAMA_URL

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


