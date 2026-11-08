"""WSP proxy policy addon (spec section 4, policy items 1-4). All decisions fail closed.

1. URL deny rules after normalization (also applied to redirect Locations).
2. Destination safety: resolve at connect time, refuse non-public destinations,
   pin the connection to the validated address, re-check redirect targets.
3. Content checks (infra/proxy/wsp_content.py) on every response body; basename
   check on request bodies; fail closed on any error or size over the limit.
4. Sanitized host-only JSONL log (no headers, cookies, query strings, bodies).

Additional fail-closed measures beyond the spec text: Range requests are
stripped and 206 responses blocked (otherwise a dataset could be fetched in
pieces that are individually unrecognizable); raw TCP, UDP and WebSocket
streams cannot be inspected and are killed.

TEST-ONLY: WSP_TEST_MODE=1 together with WSP_TEST_ALLOW_IPS=ip,ip exempts exact
IPs from the private-destination refusal so a local test server can be used.
Production configurations never set these; every log record carries
"test_mode": true while active.
"""
import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from mitmproxy import ctx, http
except ImportError:  # Host-side unit tests do not require mitmproxy.
    ctx = http = None

MFXR_REPO = "ninglitony/benchmark-for-mfxr"


def load_rules():
    # denylist.yaml is JSON (a YAML subset) so that no YAML parser is needed.
    return json.loads(Path(__file__).with_name("denylist.yaml").read_text())


# ------------------------------------------------------------------ URL rules
def normalized(value):
    # Several decoding passes catch nested escapes, bounded against abuse.
    for _ in range(8):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    value = value.lower().replace("\\", "/")
    value = re.sub(r"/(\./)+", "/", value)
    return re.sub(r"/+", "/", value)


def domain(host, suffix):
    return host == suffix or host.endswith("." + suffix)


def url_rule(url, rules):
    """Return the id of the deny rule matching `url`, or None (None != allowed)."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".").lower()
    except ValueError:
        return "invalid-url"
    if parts.scheme.lower() not in ("http", "https") or not host:
        return "invalid-url"
    full = normalized(url)
    path = normalized(parts.path + "?" + parts.query)
    if any(domain(host, entry) for entry in rules["relay_domains"]):
        return "hosted-relay"
    if any(domain(host, h) and any(path.startswith(p) for p in paths)
           for h, paths in rules["relay_paths"].items()):
        return "hosted-relay"
    if "10.6084/m9.figshare.30335941" in full:
        return "mfxr-doi"
    if (domain(host, "figshare.com") or "figshare-" in host or "figshare" in full) and (
        "30335941" in full or "66766667" in full
    ):
        return "mfxr-figshare"
    if MFXR_REPO in full:
        # Any host: direct, mirror, or a relay embedding the URL in its path.
        return "mfxr-repository"
    return None


# ----------------------------------------------------------- destination rule
_EXTRA_DENY = [ipaddress.ip_network(n) for n in (
    "100.64.0.0/10", "100.100.100.200/32", "169.254.0.0/16", "192.0.0.0/24", "198.18.0.0/15",
    "224.0.0.0/4", "240.0.0.0/4", "0.0.0.0/8", "fc00::/7", "fe80::/10", "ff00::/8",
    "fd00:ec2::254/128", "64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32", "::/128", "::1/128",
)]


def _test_allowed(ip):
    if os.environ.get("WSP_TEST_MODE") != "1":
        return False
    return str(ip) in {x.strip() for x in os.environ.get("WSP_TEST_ALLOW_IPS", "").split(",") if x.strip()}


def ip_refused(value):
    """True if the address is not an acceptable public destination."""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return True
    if _test_allowed(ip):
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    extra = [ipaddress.ip_network(n) for n in os.environ.get("WSP_EXTRA_DENY_CIDRS", "").split(",") if n.strip()]
    return (not ip.is_global or ip.is_multicast or ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_unspecified
            or any(ip in net for net in _EXTRA_DENY + extra if net.version == ip.version))


def resolve_blocking(host, port):
    """All addresses `host` resolves to (accepts any inet_aton literal form)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [i[4][0] for i in infos]


def destination_rule(host, port=443):
    """None if every resolved address is public, else a rule id."""
    try:
        addrs = resolve_blocking(host, port)
    except Exception:
        return "resolve-failed"
    if not addrs:
        return "resolve-failed"
    if any(ip_refused(a) for a in addrs):
        return "private-destination"
    return None


# --------------------------------------------------------------------- addon
def _now():
    return datetime.now(timezone.utc).isoformat()


def _block_response(rule):
    return http.Response.make(403, f"Blocked by sandbox policy ({rule}).\n".encode(),
                              {"content-type": "text/plain"})


class Policy:
    def __init__(self):
        self.rules = None
        self.corpus = None
        self.corpus_error = None
        self.limits = None
        self.names = {}  # pinned (ip, port) -> name the client asked for
        self.test_mode = os.environ.get("WSP_TEST_MODE") == "1"
        self.log_path = os.environ.get("WSP_PROXY_LOG", "/var/log/wsp/requests.jsonl")

    # -- setup
    def load(self, loader):
        import wsp_content as wc
        env = os.environ
        self.limits = wc.Limits(
            max_body=int(env.get("WSP_MAX_BODY", wc.Limits.max_body)),
            max_uncompressed=int(env.get("WSP_MAX_UNCOMPRESSED", wc.Limits.max_uncompressed)),
            max_member=int(env.get("WSP_MAX_MEMBER", wc.Limits.max_member)),
            max_carved=int(env.get("WSP_MAX_CARVED", wc.Limits.max_carved)))
        try:
            self.rules = load_rules()
        except Exception:
            self.rules = None
        try:
            self.corpus = wc.Corpus.load(env.get("WSP_HASH_CORPUS", "/etc/wsp/hash-corpus.json"))
        except Exception as e:  # never echo contents; type only
            self.corpus_error = type(e).__name__
        if ctx is not None:
            ctx.options.body_size_limit = str(self.limits.max_body)
            ctx.options.rawtcp = False
            if env.get("WSP_UPSTREAM_CA"):
                ctx.options.ssl_verify_upstream_trusted_ca = env["WSP_UPSTREAM_CA"]
        if self.test_mode:
            sys.stderr.write("WSP WARNING: TEST MODE ACTIVE; private-destination exemptions enabled\n")

    def ready(self):
        return self.rules is not None and self.corpus is not None

    def real_host(self, req, flow=None):
        name = self.names.get((req.host, req.port))
        if name is None and flow is not None:
            name = getattr(flow.server_conn, "sni", None)
        return name or req.host

    def candidate_urls(self, req):
        """URLs to match: the connection's real name, and the Host-header form."""
        host = self.real_host(req)
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        real = f"{req.scheme}://{host}:{req.port}{req.path}"
        return {real, req.pretty_url, req.url}

    # -- logging
    def log(self, flow, status, verdict, rule, body=b"", req_size=None, resp_size=None):
        req = flow.request
        try:
            url = req.pretty_url
            host, path = self.real_host(req, flow), urlsplit(url).path
        except Exception:
            url, host, path = "", None, ""
        rec = {
            "time": _now(), "run_id": os.environ.get("WSP_RUN_ID", "unknown"),
            "method": req.method, "scheme": req.scheme, "host": host, "path": path,
            "url_sha256": hashlib.sha256(url.encode()).hexdigest(), "status": status,
            "request_size": len(req.raw_content or b"") if req_size is None else req_size,
            "response_size": len(body) if resp_size is None else resp_size,
            "content_sha256": hashlib.sha256(body).hexdigest(),
            "verdict": verdict, "rule_id": rule,
        }
        self._write(rec)

    def _write(self, rec):
        if self.test_mode:
            rec["test_mode"] = True
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def log_conn(self, host, port, rule, verdict="blocked"):
        self._write({"time": _now(), "run_id": os.environ.get("WSP_RUN_ID", "unknown"),
                     "method": "CONNECT", "scheme": None, "host": host, "path": "",
                     "url_sha256": hashlib.sha256(f"{host}:{port}".encode()).hexdigest(),
                     "status": None, "request_size": 0, "response_size": 0,
                     "content_sha256": None, "verdict": verdict, "rule_id": rule})

    # -- hooks
    async def http_connect(self, flow):
        host, port = flow.request.host, flow.request.port
        rule = None
        if not self.ready():
            rule = "policy-unavailable"
        else:
            rule = await asyncio.to_thread(destination_rule, host, port)
        if rule:
            flow.metadata["wsp_rule"] = rule
            flow.response = _block_response(rule)

    async def server_connect(self, data):
        host, port = data.server.address
        try:
            addrs = await asyncio.to_thread(resolve_blocking, host, port)
        except Exception:
            addrs = []
        if not self.ready() or not addrs or any(ip_refused(a) for a in addrs):
            rule = "policy-unavailable" if not self.ready() else (
                "resolve-failed" if not addrs else "private-destination")
            self.log_conn(host, port, rule)
            data.server.error = "wsp-" + rule
            return
        # Pin to the validated address so a second (rebinding) DNS answer
        # cannot redirect the actual connection. SNI/verification host stay
        # the original name (data.server.sni was set before this hook).
        if data.server.sni is None and not _is_ip(host):
            data.server.sni = host
        if len(self.names) > 10000:
            self.names.clear()
        self.names[(addrs[0], port)] = host
        data.server.address = (addrs[0], port)

    async def request(self, flow):
        rule = None
        try:
            if not self.ready():
                rule = "policy-unavailable"
            else:
                for url in self.candidate_urls(flow.request):
                    rule = rule or url_rule(url, self.rules)
                if not rule:
                    # Clean 403 for plain-HTTP requests to private destinations
                    # (connect-time refusal would otherwise surface as a 502).
                    rule = await asyncio.to_thread(destination_rule, self.real_host(flow.request), flow.request.port)
                flow.request.headers.pop("range", None)       # see module docstring
                flow.request.headers.pop("if-range", None)
                body = flow.request.raw_content or b""
                if not rule and body:
                    import wsp_content as wc
                    rule = await asyncio.to_thread(wc.scan_upload, flow.request.content or b"", self.corpus, self.limits)
        except Exception:
            rule = "policy-error"
        if rule:
            flow.metadata["wsp_rule"] = rule
            flow.response = _block_response(rule)

    async def responseheaders(self, flow):
        if flow.metadata.get("wsp_rule"):
            return
        try:
            length = int(flow.response.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if self.limits and length > self.limits.max_body:
            flow.metadata["wsp_rule"] = "size-limit"
            flow.metadata["wsp_declared_size"] = length
            flow.response = _block_response("size-limit")

    async def response(self, flow):
        resp = flow.response
        original = resp.raw_content or b""
        status = resp.status_code
        rule = flow.metadata.get("wsp_rule")
        if not rule:
            try:
                rule = await asyncio.to_thread(self._check_response, flow)
            except Exception:
                rule = "policy-error"
            if rule:
                flow.response = _block_response(rule)
        self.log(flow, status, "blocked" if rule else "allowed", rule or "allowed", body=original,
                 resp_size=flow.metadata.get("wsp_declared_size"))

    def _check_response(self, flow):
        import wsp_content as wc
        resp = flow.response
        if not self.ready():
            return "policy-unavailable"
        if resp.status_code == 206:
            return "partial-content"
        loc = resp.headers.get("location")
        if loc and 300 <= resp.status_code < 400:
            target = urljoin(f"{flow.request.scheme}://{self.real_host(flow.request)}:{flow.request.port}{flow.request.path}", loc)
            rule = url_rule(target, self.rules)
            if rule:
                return "redirect-" + rule
            try:
                p = urlsplit(target)
                if p.hostname:
                    r = destination_rule(p.hostname, p.port or (443 if p.scheme == "https" else 80))
                    if r == "private-destination":
                        return "redirect-" + r
            except ValueError:
                return "redirect-invalid-url"
        raw = resp.raw_content or b""
        rule = wc.scan_body(raw, self.corpus, self.limits)
        if rule:
            return rule
        if resp.headers.get("content-encoding"):
            try:
                decoded = resp.get_content(strict=True)
            except Exception:
                return "decode-error"
            if decoded is not None and decoded != raw:
                return wc.scan_body(decoded, self.corpus, self.limits)
        return None

    def error(self, flow):
        err = flow.error.msg if flow.error else ""
        if "wsp-" in err:
            return  # already logged at connect time
        sys.stderr.write("WSP flow error class: %s\n" % err[:300].replace("\n", " "))
        rule = "size-limit" if "body" in err.lower() and "limit" in err.lower() else "flow-error"
        try:
            self.log(flow, None, "blocked", rule, body=b"")
        except Exception:
            pass

    # Raw TCP cannot be inspected. `rawtcp=false` (set in load() and the image
    # entrypoint) makes mitmproxy treat every tunnel as HTTP, so non-HTTP
    # streams fail to parse and are closed. As a second line of defense any
    # TCP message that still reaches this hook is emptied.
    def tcp_start(self, flow):
        a = flow.server_conn.address
        self.log_conn(a[0] if a else None, a[1] if a else None, "raw-tcp-blocked")

    def tcp_message(self, flow):
        flow.messages[-1].content = b""

    def udp_start(self, flow):
        flow.kill()
        self.log_conn(None, None, "udp-blocked")

    def websocket_start(self, flow):
        flow.kill()
        self.log_conn(flow.request.host, flow.request.port, "websocket-blocked")


def _is_ip(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


addons = [Policy()]
