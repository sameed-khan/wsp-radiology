FROM mitmproxy/mitmproxy:11.0.2@sha256:92ab9e0626ec73a3abae9c460e5475323f414745d7d0001205c8fa0c77ad31a2
# Content inspection dependencies (pinned). Wheels for CPython 3.13 are available.
RUN pip install --no-cache-dir pillow==12.0.0 imagehash==4.3.2 numpy==2.2.6 scipy==1.16.3 PyWavelets==1.9.0 certifi==2025.10.5
COPY infra/proxy/wsp_policy.py infra/proxy/wsp_content.py infra/proxy/denylist.yaml /opt/wsp/
# Upstream trust: certifi by default; set WSP_UPSTREAM_CA=<mounted bundle> to trust a host/corporate store
# (needed on networks with a TLS-inspecting firewall). Never disable verification.
# Corpus is mounted read-only at /etc/wsp/hash-corpus.json; with no corpus all traffic is refused.
ENTRYPOINT ["mitmdump", "--set", "confdir=/var/lib/wsp-ca", "--set", "termlog_verbosity=error", "--set", "flow_detail=0", "--set", "rawtcp=false", "-s", "/opt/wsp/wsp_policy.py"]
