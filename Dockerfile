FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Só as dependências da API. O worker roda no GitHub Actions e instala
# requirements-worker.txt lá.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/

ENV PYTHONPATH=/app/core
ENV PORT=8000

# Default: API read-only. O worker e o publisher sobrescrevem este comando.
CMD ["sh", "-c", "uvicorn core.step5_api:app --host 0.0.0.0 --port ${PORT}"]
