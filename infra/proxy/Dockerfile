FROM mitmproxy/mitmproxy:11.0.2@sha256:92ab9e0626ec73a3abae9c460e5475323f414745d7d0001205c8fa0c77ad31a2
COPY infra/proxy/wsp_policy.py /opt/wsp/wsp_policy.py
ENTRYPOINT ["mitmdump", "--set", "confdir=/var/lib/wsp-ca", "--set", "termlog_verbosity=error", "--set", "flow_detail=0", "-s", "/opt/wsp/wsp_policy.py"]
