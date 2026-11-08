# Offline Docker containment prototype — NOT launch-ready

This is a CPU-only, **offline smoke-test fixture**, not an agent deployment.
It implements only a smaller containment slice of plan section 5.2. It has
no proxy, external route, agent, target hashes, data, credentials, or GPU.
Do not use it to run a pilot, red team, or agent. No red-team result is implied.
Docker is the user-authorized substitution for the plan's Podman. The Docker
socket remains on the host; anyone with access to that socket can escape the
container boundary, and Docker rootful remains part of the trusted host.

## What is tested

Run from the repository root on a Docker 29.3.1 host with Compose 5.1.1:

```sh
python3 infra/smoke.py > /tmp/wsp-sandbox-smoke.json
python3 -m json.tool /tmp/wsp-sandbox-smoke.json
```

The exit status and JSON `passed` flag represent all checks; build diagnostics
are included in the JSON. The script creates a random Compose project and a
fresh temporary workspace and removes its own container, network and image in
a `finally` block. If the process is killed or Docker becomes unavailable,
cleanup may fail; inspect and remove only resources bearing that printed
project name. It does not stop existing containers or alter host networking,
firewall or daemon settings. Docker image builds require package repository
access; no target data are retrieved. Existing build cache may remain.

The service has one Docker bridge network with both `internal: true` and
`com.docker.network.bridge.gateway_mode_ipv4: isolated`. The latter avoids
assigning a host-side bridge gateway, unlike merely assuming `internal`
is enough. The test verifies that Docker reports no container gateway, checks
Python TCP has no route to public, private and each discovered IPv4 host
address, direct UDP DNS has no route, hostname resolution fails, and direct
curl fails. DNS is configured as localhost rather than an external resolver;
this is an offline-only configuration, not a demonstrated DNS policy for an
online agent. Tests are point-in-time observations, not a proof against every
Docker/kernel configuration, every protocol or IPv6. No extra containers may
be attached to this network; doing so changes the threat model. Host, macvlan,
ipvlan, overlay, additional networks, published ports, and host namespace
sharing are unsupported. Revalidate after Docker, kernel, network, or image
changes. The script checks nonroot UID, capability drop, no-new-privileges,
read-only root, single workspace bind and writable workspace/tmp. It does not
validate other deployment configurations or make a hostile-container escape
claim. The writable workspace is disposable and mode 0777 solely for the test.

Observed run: Docker Engine 29.3.1, Compose 5.1.1, Python in image 3.12.3,
curl 8.5.0, ca-certificates 20260816ubuntu0.24.04.2; project
`wsp-sandbox-smoke-aaee80f22f81`, all 21 JSON checks true, including cleanup.
Base Ubuntu image is digest-pinned and the three directly installed package
versions are pinned; transitive apt dependencies and repositories are not
snapshot-pinned. Rebuilds may fail if versions disappear or may differ in
transitive dependencies. Host package trust must not be bypassed.

## Step 2 transport prototype — NOT launch-ready

`infra/proxy/Dockerfile` builds a digest-pinned mitmproxy image; its addon
only logs completed HTTP responses and **does not block any URL, destination,
content or upload**. Do not attach an untrusted agent. The logging skeleton
records host, path without query, URL hash, sizes, status and content hash;
paths can themselves contain secrets, and error/incomplete flows are not yet
recorded. Proxy diagnostic output may also contain sensitive information and
must remain host-only. Step 3 must implement and review the full policy and
fail-closed, complete logging before use.

Generate an installation CA on the trusted host with
`python -m infra.proxy.ca /private/new-ca-dir /public/new-ca-dir` (both paths
must not already exist). The private directory is 0700 and contains the proxy
CA private key; mount it **only** into the proxy at `/var/lib/wsp-ca`. Mount
only the public directory read-only into the client at `/opt/wsp-ca`; configure
`REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `PIP_CERT`,
`NODE_EXTRA_CA_CERTS`, and `GIT_SSL_CAINFO` to `/opt/wsp-ca/bundle.pem`.
Protect the private CA from all agents and rotate it if exposed. The bundle
combines the host's system CA bundle with this installation's public CA;
regenerate/update the bundle when system trust changes. Keep logs outside the
agent as well. The CA utility expects trusted parent directories and creates
fresh paths; a failed generation may leave partial directories to remove.

Build with `docker build -f infra/proxy/Dockerfile -t wsp-proxy:step2 .` and
run `uv run --extra test pytest -s -q tests/infra/test_proxy_step2_docker.py`
after building `wsp-agent-base:step1` using `infra/agent/Dockerfile`. The live
test uses an isolated internal network and an egress-attached proxy, verifies
CA-validated curl, requests and pip download, verifies curl rejects the
interception CA without the bundle, checks direct TCP port 443 to 1.1.1.1,
host IPv4 addresses and the conventional Docker gateway and direct UDP DNS to
8.8.8.8, and checks that query parameters do not appear in response logs. It
removes its disposable resources, including `wsp-egress` only if it created
it. Docker embedded DNS from the internal-only client did **not** resolve
`pypi.org` in the observed test; the proxy resolved it from the egress network.
This observation is host/configuration dependent and does not establish a
DNS security boundary. The TCP probes do not exhaust all host ports, addresses,
IPv6, or protocols. No private destination blocking is implemented yet.

## Mandatory blockers before any networked launch

* Design, implement, and independently review a separate TLS-intercepting
  proxy with its own generated CA, explicit proxy environment and CA trust;
  the current service cannot reach HTTPS at all. Verify allowed HTTPS and
  CONNECT-path blocking in executable tests, plus refusal of bypass traffic.
* Implement full-URL deny rules for Figshare article `30335941`, file
  `66766667`, and GitHub `ninglitony/Benchmark-for-MFXR`, including API,
  raw, codeload and download variants; block known hosted fetch relays and
  disable such agent tools. Address URL normalization, redirects, public
  hostnames resolving to private/local/IP destinations, and DNS rebinding at
  connection time. Resolve how agent DNS works without an exfiltration or
  bypass channel when a proxy is attached. Verify host isolation again in the
  resulting two-network topology. No claim of absolute protection from
  arbitrary Internet scraping is made.
* Implement host-only request logs that never expose query strings,
  authorization, cookies, or other secrets; use an appropriately sanitized
  path or digest. No logs are implemented here.
* Implement a hash-only corpus interface for SHA-256 and image pHash without
  exposing labels or source mapping; test synthetic images, ZIPs and bounded
  nested extraction. Explicitly fail closed or require an approved gate for
  oversized, encrypted, unsupported/unknown and opaque MIME content instead
  of silently skipping it. No content inspection exists here; the policy for
  unknown MIME and opaque content remains a launch decision.
* The plan's global image watcher is **UNIMPLEMENTED**: it would also flag
  legitimate pool crops and probes. An origin-aware watcher and the protocol
  for distinguishing permitted derivatives from external content require an
  explicit protocol choice and independent validation before launch.
* F/G weight provenance is undecided. Resolve and implement it, the real agent
  lifecycle, scoped mounts, GPU access, and all plan-required audits and
  red-team tests before a pilot. Never mount locked data, host credentials or
  the Docker socket in an agent. No actual MFXR content was fetched or tested
  in this smoke test.
