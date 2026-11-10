# chatbot-offline
Chatbot using Ollama, StableDiffusion, Python and ReactJS. Completely works offline after setting it up.

## Docker setup

Install Docker Engine and the Docker Compose plugin. For NVIDIA acceleration, install the NVIDIA driver and NVIDIA Container Toolkit. From the repository directory, run:

```bash
docker compose up -d --build
```

On first startup, Compose downloads the Ollama language model and Stable Diffusion/VAE models. This needs an internet connection and several gigabytes of free disk space; later runs reuse the downloaded models. Check startup progress with `docker compose logs -f model-init ollama-model-init backend`.

Open `http://localhost:3000` on the Ubuntu machine. To use a phone or another device on the same Wi-Fi/LAN, find the Ubuntu host's current address with `hostname -I` and open `http://<host-ip>:3000` on that device. Allow inbound TCP port 3000 in the Ubuntu firewall if enabled. No IP address is stored in the source or Compose configuration: the frontend serves the site and proxies API/media requests on the same host and port.

Set an avatar from the settings panel by describing one to generate it, or upload a JPEG, PNG, or WebP picture (up to 10 MB) to use directly.

Stop the stack with `docker compose down`. Downloaded models remain in Docker volumes.
