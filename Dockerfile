FROM python:3.11-slim

LABEL org.opencontainers.image.title="Lazarus Keeper Daemon"
LABEL org.opencontainers.image.description="Autonomous State-Warming Keeper Node for Stellar (Soroban)"
LABEL org.opencontainers.image.source="https://github.com/LazarusProtocol/keeper"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY keeper ./keeper

ENTRYPOINT ["python", "-m", "keeper.cli"]
CMD []

