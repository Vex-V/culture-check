# Culture Check: one CPU container. Whisper runs on CTranslate2 (no torch).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml LICENSE README.md ./
COPY vidra ./vidra
COPY culturecheck ./culturecheck
RUN pip install --no-cache-dir .

# Whisper's weights in the image, so the first upload does not wait for them.
ENV HF_HOME=/opt/hf
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
ENV HF_HUB_OFFLINE=1

# deploy/seed is not in the repo: scripts/bundle.py writes it before a deploy.
COPY deploy /opt/deploy

ENV CC_DATA=/tmp/data CC_SEED_DIR=/opt/deploy/seed HOST=0.0.0.0 PORT=80 PYTHONUNBUFFERED=1
EXPOSE 80
CMD ["culturecheck"]
