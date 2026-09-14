# SamCore: imagen unica de despliegue (Space Docker de Hugging Face, GPU T4).
# Etapa 1: compila el frontend. Etapa 2: backend + motor + artefactos + pesos.

FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN corepack enable && corepack prepare pnpm@latest --activate && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SAMCORE_MOTOR=real \
    SAMCORE_PRECISION=fp32 \
    SAMCORE_HTTPS=1 \
    SAMCORE_BD=/data/samcore.db \
    SAMCORE_DATOS=/data/inspecciones \
    SAMCORE_PESOS=/app/backend/pesos \
    SAMCORE_FRONTEND=/app/frontend/dist \
    TORCH_HOME=/app/backend/pesos/torch

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 samcore

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.11.0 torchvision==0.26.0 \
    && pip install -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/artefactos ./artefactos
COPY backend/galeria ./galeria
COPY --from=frontend /src/dist /app/frontend/dist

# Pesos: SAM (verificado por SHA-256) y WideResNet-50 (cache de torchvision)
RUN python scripts/descargar_pesos.py /app/backend/pesos \
    && python -c "import torchvision; torchvision.models.wide_resnet50_2(weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)" \
    && mkdir -p /data && chown -R samcore:samcore /app /data

USER samcore
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
