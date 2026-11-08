"""Step 2 logging only. NOT a policy or a safe production proxy."""
import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

from mitmproxy import http


def response(flow: http.HTTPFlow) -> None:
    request, response = flow.request, flow.response
    url = request.pretty_url
    parts = urlsplit(url)
    body = response.raw_content or b""
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "run_id": os.environ.get("WSP_RUN_ID", "unknown"),
        "method": request.method,
        "scheme": parts.scheme,
        "host": parts.hostname,
        "path": parts.path,
        "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
        "status": response.status_code,
        "request_size": len(request.raw_content or b""),
        "response_size": len(body),
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "verdict": "unfiltered",
        "rule_id": None,
    }
    with open(os.environ.get("WSP_PROXY_LOG", "/var/log/wsp/requests.jsonl"), "a", encoding="utf-8") as log:
        log.write(json.dumps(record, separators=(",", ":")) + "\n")
