FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# requirements.txt may be UTF-16 LE on Windows; convert to UTF-8 for pip
RUN python3 -c "data=open('requirements.txt','rb').read(); open('requirements.txt','w',encoding='utf-8').write(data.decode('utf-16')) if data[:2] in (b'\xff\xfe',b'\xfe\xff') else None"

# torch CPU-only packages live on the PyTorch index
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .
