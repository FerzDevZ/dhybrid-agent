# Dhybrid Agent — image produksi
# Multi-stage: build hanya untuk mengemas; runtime minimal (tidak bawa toolchain build).
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# copy package + install (deps diambil dari pyproject — core saja)
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Workspace agent (direktori kerja) & jalur config/audit/checkpoint
ENV DHYBRID_WORKSPACE=/workspace \
    DHYBRID_AUDIT_DIR=/data/audit \
    DHYBRID_CHECKPOINT_DIR=/data/checkpoints
RUN mkdir -p /workspace /data/audit /data/checkpoints

# Egress policy default aman: kosong = izinkan semua; set via env saat deploy.
# Bisnis eksekusi terminal tidak tersedia di image ini (sandbox); overridable per deploy.

WORKDIR /workspace
ENTRYPOINT ["dhybrid"]
CMD ["run-from-env"]