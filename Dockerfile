# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY scripts/download_model.sh /build/scripts/download_model.sh
RUN chmod +x /build/scripts/download_model.sh \
    && /build/scripts/download_model.sh /build/models

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -d /opt/app appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /build/models /opt/app/models
COPY model_manifest.yaml /opt/app/etc/default/model_manifest.yaml
COPY app /opt/app/app
COPY entrypoint.sh /opt/app/entrypoint.sh

RUN printf '#!/bin/bash\nexec /opt/venv/bin/python3 /opt/app/app/list_profiles.py "$@"\n' \
    > /usr/local/bin/list-profiles \
    && chmod +x /usr/local/bin/list-profiles /opt/app/entrypoint.sh

RUN chown -R appuser:appuser /opt/app
USER appuser

WORKDIR /opt/app
ENV MANIFEST_PATH=/opt/app/etc/default/model_manifest.yaml
ENV PROFILE=balanced

EXPOSE 8000

ENTRYPOINT ["/opt/app/entrypoint.sh"]