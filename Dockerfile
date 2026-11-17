# Single-container image for a free Hugging Face Docker Space.
# Runs Ollama, the FastAPI backend and the built React UI in one container
# on port 7860. Nothing runs on the developer's laptop.

# ---- Build the React frontend ------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Runtime ------------------------------------------------------------
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates zstd sleuthkit \
    && rm -rf /var/lib/apt/lists/*

# Ollama (CPU). The install script skips systemd setup inside Docker.
RUN curl -fsSL https://ollama.com/install.sh | sh

# Hugging Face Spaces run the container as uid 1000.
RUN useradd -m -u 1000 user
USER user
RUN mkdir -p /home/user/.ollama/models

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONWARNINGS=ignore \
    PORT=7860 \
    SERVE_FRONTEND=1 \
    CYBERGUARD_A2A_URL=http://127.0.0.1:7860/ \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_MODEL=qwen2.5:3b \
    CYBERGUARD_CREW_AGENTS=1

WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user backend ./backend
COPY --chown=user data/samples ./data/samples
COPY --chown=user --from=frontend /build/dist ./frontend/dist
COPY --chown=user hf/start.sh ./start.sh
RUN mkdir -p data/uploads

EXPOSE 7860
CMD ["bash", "start.sh"]
