FROM python:3.11-slim AS builder
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
EXPOSE 8501
USER myuser
CMD ["python", "-m", "streamlit", "run", "ui.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
