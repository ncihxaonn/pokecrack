FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN groupadd --system pokecrack && useradd --system --gid pokecrack --home /app pokecrack

COPY pyproject.toml ./
COPY pokecrack_worker ./pokecrack_worker
RUN python -m pip install --upgrade pip && python -m pip install .

USER pokecrack
# HEALTHCHECK command: pokecrack-worker health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["pokecrack-worker", "health"]
ENTRYPOINT ["pokecrack-worker"]
CMD ["worker", "--once"]
