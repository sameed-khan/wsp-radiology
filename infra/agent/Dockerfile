FROM ubuntu@sha256:186072bba1b2f436cbb91ef2567abca677337cfc786c86e107d25b7072feef0c

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates=20260816ubuntu0.24.04.2 python3=3.12.3-0ubuntu2.1 \
    python3-pip=24.0+dfsg-1ubuntu1.3 tini=0.19.0-1 \
    git=1:2.43.0-1ubuntu7.4 curl=8.5.0-2ubuntu10.16 wget=1.21.4-1ubuntu4.5 \
    ripgrep=14.1.0-1 jq=1.7.1-3ubuntu0.24.04.2 unzip=6.0-28ubuntu4.1 \
    file=1:5.45-3build1 procps=2:4.0.4-4ubuntu3.3 \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu's system Python is externally managed; permit both this installation and
# agent-local pip --user installs, without making the root filesystem writable.
ENV PIP_BREAK_SYSTEM_PACKAGES=1 PYTHONUNBUFFERED=1 HOME=/workspace/home \
    PATH=/workspace/home/.local/bin:$PATH
RUN python3 -m pip install --no-cache-dir \
    torch==2.8.0 torchvision==0.23.0 transformers==4.57.3 peft==0.18.0 \
    timm==1.0.22 accelerate==1.12.0 safetensors==0.7.0 \
    scikit-learn==1.7.2 scipy==1.16.3 numpy==2.2.6 pandas==2.3.3 \
    pillow==12.0.0 imagehash==4.3.2 opencv-python-headless==4.12.0.88 \
    matplotlib==3.10.7 tqdm==4.67.1 pyarrow==22.0.0
WORKDIR /workspace
USER 1004:1004
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
