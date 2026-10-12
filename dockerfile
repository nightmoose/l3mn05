# Dockerfile - L3MN05 v0.7.2 (modular agents + integrations)

FROM python:3.12-slim

# System deps + permanent git identity (baked into image) — YOUR ORIGINAL

RUN apt-get update && apt-get install -y git gh curl && rm -rf /var/lib/apt/lists/* \
    && git config --global user.email "horace@l3mn05.local" \
    && git config --global user.name "Horace L3MN05"

RUN pip install --no-cache-dir setuptools==75.2.0

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY skills/ skills/
COPY tools/ tools/
COPY utils/ utils/
COPY . /app

COPY worker_scaffold.py .
COPY worker_improve.py .
COPY worker_review.py .