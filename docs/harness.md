# Harness

## Search extension

`harness/pi-ext/web-search.ts` registers only `web_search`. The host-only
wrapper reads `exaApiKey` from `~/.pi/exa-search.json` and calls Exa search
for up to 10 titles, URLs, publication dates and short highlights. It does not
request full page text or expose a page-fetch tool. Never mount the credential
file into a container. Missing or invalid credentials yield a clear error;
provider errors are suppressed and the key is redacted from result fields.
Run `node --test tests/test_exa_search.mjs` for mocked tests. Search results
are untrusted third-party text. Exa generates highlights on its servers; this
search endpoint bypasses the sandbox proxy and snippet access does not enforce
the study denylist or replace network and content controls.

---

# Harness design (supersedes the status line above)

All of the following is implemented and was exercised with the `simple` backend
and real Haiku; the `infra` backend (L2 `infra.sandbox`, watcher, GPU watchdog)
is implemented against the documented API but **not exercised** because L2's
code was not in this worktree.

## Components and trust boundary
Trusted, host-only (never mounted into containers): `harness/pi-ext/*`
(container-tools, subagents, web-search + exa-search.mjs), `src/wsp_harness/*`
(supervisor, run, cli, evidence, config, sandbox_*), the run directory
`runs/<id>/{recorder,state,control,snapshots,launch.json,interventions.jsonl}`,
and `~/.pi` credentials. The agent container gets only `runs/<id>/workspace`
(rw, `/workspace`) and the pool/labels directories read-only
(`/inputs/pool`, `/inputs/labels`). Container: network none (simple backend),
cap-drop ALL, no-new-privileges, read-only rootfs, uid 1004, no docker.sock.
Pi itself runs on the host; its read/write/edit/bash tools are replaced by
`container-tools.ts`, which uses `docker exec` argv arrays with no host shell.
Subagents (`subagents.ts`) are fixed to `anthropic/claude-haiku-5-5`, have
container tools only (one level), at most 8 run concurrently, and are killed
at the deadline. API keys stay on the host.

## Run layout
`launch.json` (git revision, input/extension hashes, models, labels sha256,
start/deadline, rendered launch prompt + hash, image id);
`recorder/rpc-events.jsonl` (verbatim Pi stdout) + `rpc-receive-times.jsonl`;
`recorder/sessions/*.jsonl` (Pi session), `recorder/subagents/<uuid>.events.jsonl`
+ session files; `state/status.json`; `control/` (STOP_REQUEST.json, messages/);
`snapshots/` (hourly rsync link-dest + manifest, final snapshot);
`interventions.jsonl` (every auto/manual intervention).

## What is and is not guaranteed (ADR-001)
Guaranteed by construction/tests: complete tool-result record (`verify`
cross-checks the RPC log against parent and subagent session files), subagent
assistant messages all Haiku, frozen filesystem at the deadline
(abort, kill process group and run-tagged children, `docker pause`, final
snapshot, `docker rm -f`), host-clock deadline, logged interventions.
Not guaranteed: periodic snapshots are not atomic with a running agent; a
process that escapes the in-container process group is only stopped by
sandbox teardown; web_search goes through Exa outside the sandbox proxy and
cannot enforce the denylist; the secret scan is pattern-based; the `infra`
backend and L2 watcher/watchdog integration are untested here.

## Orchestrator commands
(`wsp-harness [--root R] ...`; `--root` defaults to the repo.)
- `launch --arm F|G --k K --labels DIR --pool DIR [--hours 24] [--backend simple|infra] [--test-model]`
  detaches the supervisor (setsid or `--daemonizer systemd`) and prints the run id.
  Infra backend also needs `--models-dir --external-dir --image --hash-corpus`.
- `status [--run R]` — all runs, or one run's status.json plus supervisor liveness.
- `intervene --run R --kind infra|message --note TEXT` — logged; `message` is
  delivered as a Pi steer (or prompt when idle).
- `stop --run R --reason TEXT` — writes control/STOP_REQUEST.json; supervisor freezes.
- `verify --run R` — JSON completeness report (exit 1 when incomplete).
- `account --run R [--no-prices]` — usage/cost by model, source, token type; retries; wall clock; GPU.
- `seal --run R [--artifacts DIR]` — receipt.json with sha256s, secret scan,
  copy to `artifacts/runs/<run>/` for `dvc add`. Never pushes.

## Tests
`uv run --extra test pytest -q` (offline). Paid/Docker: `WSP_LIVE=1 uv run --extra test pytest -q tests/test_harness_run.py tests/test_harness_supervisor.py tests/test_harness_cli.py tests/test_harness_e2e.py`;
other opt-in tests: `WSP_LIVE_CONTAINER_TEST`, `WSP_LIVE_SUBAGENT_TEST`, `WSP_LIVE_SNAPSHOT_TEST`.
