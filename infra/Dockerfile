# Containment prototype only: no agent or proxy is installed.
FROM ubuntu@sha256:186072bba1b2f436cbb91ef2567abca677337cfc786c86e107d25b7072feef0c
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates=20260816ubuntu0.24.04.2 curl=8.5.0-2ubuntu10.16 python3=3.12.3-0ubuntu2.1 && rm -rf /var/lib/apt/lists/*
USER 65534:65534
WORKDIR /workspace
CMD ["sleep", "infinity"]
