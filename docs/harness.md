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

The simple backend and the networked `infra` backend have both been exercised
with real Haiku. Infra starts the L2 sandbox, watcher and GPU watchdog; helper
exits are logged and restarted by the supervisor.

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
cannot enforce the denylist; the secret scan is pattern-based; helper supervision is polling-based, and
watcher/watchdog outages between checks are possible.

## Orchestrator commands
(`wsp-harness [--root R] ...`; `--root` defaults to the repo.)
- `prepare-launch --k 10|50 --resample 1 [--image TAG] [--proxy-image TAG]` creates a fresh private `.runtime/run-inputs/` receipt and a separate labels-only directory in the main checkout. It prints both preview prompts and their unified diff, then a JSON checklist; exit 1 means at least one check failed. GPU free memory requires 22 GiB for two 11 GiB caps. Receipt includes image IDs and available repository digests, not a claim that mutable tags are pinned. The prompt preview uses a shared current timestamp; actual launch times and prompt hashes differ. Use the printed labels path for both arms, recheck its hash and all dynamic checks at launch. Readiness is not approval: orchestrator must verify red-team, prerequisite baselines, freeze/tag and investigator authorization. The receipt and labels contain private material; retain securely or delete when no longer needed.
- `launch --arm F|G --k K --labels DIR --pool DIR [--hours 24] [--backend simple|infra] [--test-model]`
  detaches the supervisor (setsid or `--daemonizer systemd`) and prints the run id.
  Infra backend also needs `--models-dir --external-dir --hash-corpus`; it defaults to `wsp-agent:phase1` and the sandbox defaults to `wsp-proxy:phase1`. `--image` overrides the agent image.
  Pass the resolved main-checkout pool, an agent-only labels directory, the
  main-checkout models and external directories, and the private hash corpus.
  State, proxy logs, CA keys and helper logs stay under the run's `state/`.
  `TASK.md`, `output/`, and (when available in the root or image) `TOOLKIT.md`
  are seeded in the workspace. The launch receipt records the selected image.
- `status [--run R]` — all runs, or one run's status.json plus supervisor liveness. The effective deadline, original deadline and total extension seconds are recorded in status.
- `extend --run R --seconds S --reason TEXT` — append a positive finite number of seconds to the host-owned extension ledger and log an infrastructure intervention. The supervisor picks it up on its next tick; `state/deadline.json` publishes the effective deadline atomically to subagents. An automatic rate-limit outage runs from the first classified failure to the next successful model progress; a fixed notice is sent after recovery. During an unresolved outage the supervisor and subagents wait for recovery rather than freezing at the unextended deadline. Stop remains available for operator action.
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
