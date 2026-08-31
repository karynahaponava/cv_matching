FROM python:3.11-slim AS builder
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
RUN groupadd -g 1000 myuser && \
    useradd -u 1000 -g myuser -m -s /bin/bash myuser
WORKDIR /app
COPY --from=builder --chown=myuser:myuser /root/.local /home/myuser/.local
COPY --chown=myuser:myuser . .
ENV PATH="/home/myuser/.local/bin:${PATH}"
EXPOSE 8000
USER myuser
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]