# KnowledgeVault backend image (KV-35).
#
# Build and run it together with Postgres from the repo root:
#     docker compose up --build
#
# The embedding model is downloaded while the image is built, so a container
# starts without needing to reach the internet. Settings come from environment
# variables (see settings.py); DATABASE_URL has no default and must be passed in.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# The CPU-only build of PyTorch is far smaller than the default (CUDA) one.
# Installed first so the next step sees it as already satisfied.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model (about 90 MB) into the image. Keep this name in
# step with MODEL_NAME in embeddings.py.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Do not run as root inside the container.
RUN useradd --create-home --shell /usr/sbin/nologin app
USER app

EXPOSE 8000

# init_db.py runs the database migrations (enables pgvector, creates or upgrades
# the tables; safe to re-run), then the API starts.
CMD ["sh", "-c", "python init_db.py && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
