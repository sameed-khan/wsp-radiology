# Docker sandbox — not yet launch-ready

The networked implementation and its end-to-end tests are described in Steps 4–6
below. Launch remains blocked by the outstanding calibration, integration and
red-team work described there. Independent code review was waived.

## Phase 1 image build (2026-11-08)

Built from committed tree `36bec83` with `git archive HEAD` piped to each
Docker build (no ignored data or host credentials in the context):

```sh
git archive HEAD | docker build -f infra/agent/Dockerfile -t wsp-agent-base:phase1 -
git archive HEAD | docker build -f infra/agent/Dockerfile.toolkit --build-arg BASE_IMAGE=wsp-agent-base:phase1 -t wsp-agent:phase1 -
git archive HEAD | docker build -f infra/proxy/Dockerfile -t wsp-proxy:phase1 -
```

Local image IDs / repository digests as reported by `docker image inspect`:

| Tag | ID / local repository digest (sha256) |
|---|---|
| `wsp-agent-base:phase1` | `ecc0d6ffc4f1fbf6c13a8e0a8df7b280291a9cb271a0b0b0b1b91a7fb158afe8` |
| `wsp-agent:phase1` | `b53856a9bba52e3f7b40c336760089587c5b1ae33675aa5846320ac021c7631b` |
| `wsp-proxy:phase1` | `0ba5936a53048910ab675d51d0201dee214455858137316120d9027fef9bf25d` |

Tags are mutable; verify IDs against launch receipts before use. These are local
build digests, not published registry attestations. BuildKit reused cached base
and proxy layers; apt and transitive pip inputs are not fully snapshot-pinned.
The toolkit layer was built from the committed tree. The phase1 agent and proxy
passed the real-topology Haiku harness test and the Docker-marked suite; the
historical step2 transport test still uses its step2/step1 images. These tests
are not a red-team approval or a launch authorization.

## Historical offline containment fixture

The following CPU-only offline smoke-test fixture is separate from the networked
sandbox. It has no proxy, external route, agent, target hashes, data, credentials,
or GPU. No red-team result is implied.
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

## Historical Step 2 transport prototype

Step 2 originally provided transport and logging only; Step 3 subsequently
added policy and content scanning. Proxy logs include paths without query
strings, and paths can themselves contain secrets. Proxy diagnostic output
may also contain sensitive information; keep all logs host-only.

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

## Historical blockers list (written at step 2; steps 3-6 implement the items below, see the Step 6 section for status)

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

## Step 4 sandbox lifecycle API (`infra/sandbox.py`)

`create(SandboxSpec)` builds, per run id (`[a-z0-9][a-z0-9_.-]{0,39}`): internal+isolated network `wsp-int-<run>`,
proxy `wsp-proxy-<run>` (internal + `wsp-egress`, runs as the host user with cap-drop ALL, read-only rootfs, mounts the
0700 private CA dir, host-only log dir and corpus read-only), and agent `wsp-agent-<run>` (internal network only,
user 1004:1004, cap-drop ALL, no-new-privileges, read-only rootfs, tmpfs /tmp 16g, shm 16g, pids 4096, memory/swap
cap, cpus, `--gpus device=0`, tini + `sleep infinity`; mounts only /workspace rw, /inputs/{pool,labels,models,external}
ro, /opt/wsp-ca ro; proxy and CA env vars). All resources carry label `wsp.run=<run>`; `destroy()` is idempotent and only
removes labelled resources. CA is generated per installation in `state_dir/ca` (or `ca_dir`). `labels_dir` must contain
only `labels.csv`. `pause` freezes the agent only (proxy keeps running). Run the CLI with `python -m infra.sandbox`.
Tests: `uv run --extra test pytest -q tests/infra/test_sandbox_step4_docker.py` (needs images `wsp-agent-base:step1`,
`wsp-proxy:step3`). Limits: GPU watchdog/watcher are not launched by `create` (step 5; `state_dir/sandbox.json` holds the
`container:cap` argument); the proxy image tag default is now `wsp-proxy:phase1`.

## Step 5: workspace watcher and GPU watchdog (host processes)

Both run on the trusted host, never inside the sandbox; their state/control dirs must not be mounted into agents.

- `python -m infra.watcher --workspace W --corpus C --state-dir S --control-dir D [--interval 120] [--run-id R] [--once]`
  scans new/changed regular files (symlinks never followed; mtime/size/inode cache; SIGUSR1 = scan now).
  It reuses the proxy's scanner (`wsp_content`: sha256, normalized-pixel sha, pHash, JPEG/PNG carving,
  base64, bounded recursive archives, basenames). **stop** (writes `D/STOP_REQUEST.json`
  `{reason,file,rule,time}`): exact raw or normalized SHA-256 of any MFXR image (including pool images), archive SHA-256,
  or >= 3 distinct MFXR basenames. **alert**: pHash 0..6 to a test image; unscannable/oversize (> 2 GiB) content.
  **info `pool-derivative`**: non-exact image matches only pool images (pHash <= 6 to pool, > 6 from test). A file near both a
  pool and a test image is judged by the test image. Exact matches always take precedence. `--phash-stop-distance N`
  explicitly opts into stopping for test pHash distance <= N (0..6); by default no test pHash alone stops a run.
  Logs (`S/watcher.jsonl`) hold only relative path, rule, size - never hashes, basenames or content.

Calibration: `.runtime/overlap-calibration.json` recorded 64,358 external images hashed, 63 failures,
7 test images with external matches <= 4, including one <= 2; inspection identified radiograph pHash false positives.
The calibrated decision is alert-only with orchestrator visual review at hourly checks. This supersedes the original
spec's <= 2 stop rule. The proxy retains pHash <= 4 blocking; sensitivity re-scoring excludes the 7 affected test images.
Exact pool image copies also stop under the calibration's exact-hash rule, despite pool access being permitted; avoid copying
those bytes into the workspace or handle the resulting stop as an infrastructure/protocol issue.
- `python -m infra.gpu_watchdog --state-dir S (--container NAME:CAP_GIB | --sandbox-json S/sandbox.json)`.
  Kills the largest GPU process of a container that exceeds its cap, as that process's own UID:
  the sandbox drops all capabilities, so `docker exec -u 0 ... kill` fails with EPERM against UID 1004 processes
  (observed live). Namespace PID 1 (tini) cannot be signalled from inside; the invariant is that agent work is only
  ever started with `docker exec` (never PID 1), and a PID-1 over-cap is logged as `kill-failed`.

Limitations: the watcher is periodic (120 s) so a file created and deleted between scans is missed; the pHash
calibration has observed false positives and 63 external hash failures; archive/size limits make some content only
alert-level; the watchdog polls every 5 s (transient overage possible) and PID reuse between check and kill is
narrowed (identity re-check) but not eliminated. Neither process is started by `sandbox.create`.

## Step 6: end-to-end suite and residual risks

`uv run --extra test pytest -q -m docker` runs all live Docker tests. The focused
`uv run --extra test pytest -q -m docker tests/infra/test_e2e_sandbox_docker.py` (35 tests; needs Docker, the GPU,
images `wsp-agent:phase1` and `wsp-proxy:phase1`; creates `wsp-egress` if absent and removes only what it created).
One module-scoped sandbox is created through `infra.sandbox.create()` (hardened GPU agent, internal network, policy
proxy on `wsp-egress`); a synthetic test server on `wsp-egress` is exempted from private-destination refusal only by the
TEST-ONLY `test_allow_ips` flag. Every request is issued from inside the agent as uid 1004. Covered (spec section 4 Tests):

- allowed HTTPS to pypi.org, huggingface.co, github.com (curl, requests, `git ls-remote`);
- 11 denied MFXR URL forms (GitHub/API/raw/codeload, Figshare article/API/ndownloader, DOI, case/percent/slash variants,
  jina relay) -> 403, and denied redirect chains;
- bypass fails: direct TCP, UDP DNS to 8.8.8.8, no DNS resolution (`gethostbyname` fails), host IPs on ports 22/80/2375,
  docker gateway, egress-bridge neighbours, no gateway on the internal network;
- proxy refuses private destinations (RFC1918, link-local/metadata, CGNAT, ULA, docker bridge) and after redirects;
- synthetic hash corpus: raw bytes, re-encoded/resized (pHash), inside a zip, carved from a parquet-like blob, basename
  text list are blocked with nothing but the 403 text saved; clean image/text allowed; proxy logs hold no basenames/canary;
- `nvidia-smi` and a CUDA torch matmul in the agent;
- watcher: non-exact pool derivatives only `info`, test pHash 0-6 -> alert (no stop), exact image copy -> STOP_REQUEST.json,
  basenames text -> stop-level finding; watcher log has no hashes/basenames; control/state dirs invisible in the agent;
- no docker.sock, canary "locked"/credential files, private CA key, host state dirs or secret-looking env in the agent;
  labels dir holds only labels.csv; the Step 4 topology tests check the exact six bind mounts;
- GPU watchdog kills an over-cap CUDA process in the live sandbox (sandbox survives); finally no labelled leftovers.

DNS: Docker's embedded DNS on the internal network does not resolve external names (tested at step 2 and in step 6);
agents depend on the proxy resolving names. Residual risks: see the Limitations lists above (loopback inside the
agent is NO_PROXY so agent-local services are reachable by design; calibrated pHash alerts require human review; watcher periodic; watchdog polling/PID-reuse; IPv6/non-443 ports not exhaustive; the proxy and agent
images use mutable tags and are not digest-pinned in the API; unhashed pip pins; no independent review was performed;
red-team of tool-level exfiltration channels (e.g. DNS tunnelling via the proxy's allowed domains, slow-drip uploads to
allowed hosts) is not done).
