# CLAID web application - container image for hosts that give the app a disk
# (Render, Railway, Fly.io, Google Cloud Run, a VPS, Docker locally).
#
#     docker build -f deploy/Dockerfile -t claid .
#     docker run -p 8000:8000 -v claid-data:/data claid      # http://127.0.0.1:8000
#
# It is deliberately in deploy/ rather than at the repository root: Vercel builds
# this project as a serverless Python function (app.py + requirements.txt), and a
# root Dockerfile would point that project at a different build path. Vercel works
# too - see "Deploying" in the README for what serverless storage means there.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CLAID_HOST=0.0.0.0 \
    CLAID_PORT=8000 \
    CLAID_STATE_DIR=/data

WORKDIR /app

# Dependencies first: they change far less often than the source tree.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt "gunicorn>=21"

COPY . .

# Runs and the extracted dataset live on the volume, never inside the image.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/about').read()"

# One worker, a few threads: the pipeline memoises the graph, the community
# comparison, the top-k baselines and the Isolation Forest fits per process, and
# the threads share that cache. A first run takes ~15-30 s, so the timeout is
# generous; the second one answers from the cache in about a second.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--timeout", "300", "app:app"]
