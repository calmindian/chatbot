FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# PyTorch 2.4.1 + CUDA 12.1 (wheels bundle the CUDA libs; only the NVIDIA driver is needed on the host).
# --extra-index-url keeps PyPI available for normal dependencies.
# The cache mount means a retry won't re-download the ~1.5 GB of wheels.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    torch==2.4.1+cu121 \
    torchvision==0.19.1+cu121 \
    torchaudio==2.4.1+cu121 \
    --extra-index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
