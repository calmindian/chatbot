# chatbot-offline
Chatbot using Ollama, StableDiffusion, Python and ReactJS. Completely works offline after setting it up.

## Docker setup

Install Docker Engine and the Docker Compose plugin. For NVIDIA acceleration, install the NVIDIA driver and NVIDIA Container Toolkit. From the repository directory, run:

```bash
cp backend/.env.example backend/.env
# Change APP_PASSWORD to your preferred 4-digit PIN in backend/.env.
docker compose up -d --build
```

The app requires the shared 4-digit PIN at sign-in on each browser/device. Sessions use an HttpOnly cookie, and **Sign out** is in global settings. Keep `backend/.env` private; it is ignored by Git. The PIN is rate-limited, but has less security than a longer password, so use it only on a trusted home LAN. For HTTPS deployments, set `SESSION_COOKIE_SECURE=true`; do not expose the HTTP service to an untrusted network or the public internet.

On first startup, Compose downloads the `gurubot/girl` Ollama chat model and the Stable Diffusion/VAE models. This needs an internet connection and several gigabytes of free disk space; later runs reuse the downloaded models. Check startup progress with `docker compose logs -f model-init ollama-model-init backend`.

Older installs may still have the unused Moondream model in the persistent Ollama volume. It is no longer pulled or used; to free its disk space, remove it with `docker compose exec ollama ollama rm moondream:latest`.

Open `http://localhost:3000` on the Ubuntu machine. To use a phone or another device on the same Wi-Fi/LAN, find the Ubuntu host's current address with `hostname -I` and open `http://<host-ip>:3000` on that device. Allow inbound TCP port 3000 in the Ubuntu firewall if enabled. No IP address is stored in the source or Compose configuration: the frontend serves the site and proxies API/media requests on the same host and port.

## Code layout

- `ai-friend/src/components/` contains the main screen components and reusable icons; `services/` owns API and browser storage access; `styles/` and `utils/` contain shared presentation and chat helpers.
- `backend/server.py` assembles the FastAPI application and middleware. `backend/app/api/` groups system, chat, persona, and data routes; `backend/app/` also separates settings, request schemas, session persistence, and runtime coordination, while `backend/app/services/` contains image generation and language-model integrations.

The app has **Chats**, **Collection**, and **Settings** tabs. Create a chat with the floating **+** button. Open a chat's settings from its header to rename the chat, set its personality, and create or upload its avatar. Upload a JPEG, PNG, or WebP picture (up to 10 MB) to use directly. Request image changes naturally in chat, for example: “Change into a red gown and send me a picture.” The request text drives the outfit and scene; the saved avatar guides the person's face and body proportions, while pose, outfit, lighting, and background can vary. Generated images favor bright, natural light and use a vertical 3:4 frame without requiring a full-body view. The app does not run an image-captioning model. Add an optional avatar description to guide the companion's text conversations. The Collection tab shows generated images, GIFs, and avatars. Voice controls and **Delete all data** are in global settings.

Each browser/device keeps its own chat list; chats and their personas are saved on the backend and remain separate between devices. Create chats from the chat list, then open a chat's settings to configure its avatar and personality. Open tabs in the same browser sync while active and refresh when a suspended phone or browser becomes active again. A device may pause visible updates while its screen is off; it catches up when resumed.

**Delete all data** permanently removes every chat, persona setting, avatar, and generated image/GIF from the shared server, and clears the app's saved chat list and cache on connected devices (offline devices clear theirs when they reconnect). This affects other devices using the same server too. Downloaded AI model files are kept.

Stop the stack with `docker compose down`. Downloaded models remain in Docker volumes.
