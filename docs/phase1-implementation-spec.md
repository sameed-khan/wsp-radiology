# Phase 1 implementation specification (orchestrator-authored, 2026-11-08)

Status: binding engineering specification for the remaining Phase 1 work.
It operationalizes `plan.md`, ADR-001/ADR-002 (`docs/decisions.md`) and the
handoff. Where it narrows or deviates from `plan.md`, the deviation is listed
in section 10 and must be reported in the methods. Do not change recipes in
this file after any locked-test score has been computed; amend with a dated
note instead.

Roles: the **orchestrator** (the parent Pi session talking to the investigator)
builds/freezes the harness, launches and monitors F/G sessions, runs
baselines and evaluation, and audits. The **F/G agents** (Opus 5.5) do the
experimental work inside sandboxes. Implementation lanes are written by
GPT-6.1-Terra and independently reviewed by GPT-6.1-Sol.

Repository root on the host: `/home/skhanxx8/projects/wsp-radiology`
(below: `$ROOT`). Ignored large inputs live only in the main checkout
(`$ROOT/data`, `$ROOT/models`); worktrees must reference them by absolute path
and must never copy, move, or modify them.

## 1. Global rules (all lanes)

- Never print, copy, or mount credentials (`~/.pi/agent/auth.json`, HF token
  store, `.dvc/config.local`, rclone config). Never mount `$ROOT/data/locked`,
  the generation directory, `~/.pi`, or `/var/run/docker.sock` into agent
  containers. Never disable TLS verification. Use
  `REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` and
  `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` for host downloads.
- Do not restart Docker, change daemon config, host firewall/iptables,
  host networking, drivers, or reboot. Do not touch the existing `WinApps`
  and `dicom-twin-hapi-fhir` containers. Name every Docker resource with the
  prefix `wsp-` and clean up resources you create in tests.
- Never read locked test labels in code paths other than `wsp_eval` locked
  scoring. No component may compute test metrics before the orchestrator
  runs the scoring step.
- Python: host environment is `uv`-managed `.venv` (Python 3.14). Keep
  `uv.lock` consistent (`uv lock --check`). Existing 25 tests must still pass.
- Private outputs (labels, mappings, test images/features, predictions) go
  under `$ROOT/data/locked/private/` (mode 0700 dirs, 0600 files).

## 2. Data, patient map and sampler (lane L1)

- Positive class = MFXR `anomaly` (Monteggia fracture) = 1; `good` = 0.
- Materialize the investigator-approved reviewed map from the current
  generation's `prefix-map-proposal.json` and `inventory.json` (find via
  `readlink -f data/pool`): one row per prefix with
  `{source_prefix, patient_id, split, label, reviewed: true}` where
  `patient_id = "P" + source_prefix`. Write to
  `data/locked/private/patient-map-reviewed.json`; validate with the existing
  `validate_patient_map` (1,484 patients: 993 train, 491 test).
- Sampler: budgets k ∈ {10, 20, 50, 100, 250}; resamples r ∈ {1..5};
  `seed = int(sha256(f"wsp-phase1|mfxr|k={k}|r={r}").hexdigest()[:16], 16)`;
  draw k distinct train patients uniformly without replacement with
  `numpy.random.default_rng(seed).choice` over the sorted train patient IDs.
  `k = all` is all 993 train patients (one sample; resamples differ only in
  training seed). No stratification and no redraw if a sample is single-class
  (preregistered; single-class handling in section 5).
- Allocation file per (k, r): private JSON with seed, patient IDs and
  per-image `{anonymous_filename, patient_id, label}`; and an agent-facing
  `labels.csv` with columns `image,patient,label` where `patient` is a
  fresh opaque token (`sha256(seed|patient_id)[:12]`), never the source prefix.
- Test images: materialize the 1,593 official test images from the verified
  archive with the *identical* `load_image_bytes` → PNG normalization used
  for the pool, into `data/locked/private/test-png/` with random names, plus a
  private manifest `{file, patient_id, label, source_path, phash, sha256}`.
- Hash corpora for leakage controls (no labels):
  `data/locked/private/hash-corpus.json` with MFXR raw SHA-256 (all 4,586),
  normalized SHA-256, pHash for all images (tagged pool/test only), the
  archive SHA-256, and the set of original MFXR file basenames.

## 3. Encoders and features (lane L1)

Package `src/wsp_ml/`. Load only from local paths (`local_files_only=True`,
`HF_HUB_OFFLINE=1`), exact files in `models/`.

| Encoder id | Path | Input | Pooled feature |
|---|---|---|---|
| `skelex` | `models/skhoha/SKELEX` | 224, ImageNet mean/std, bicubic | CLS of final layernorm output |
| `medsiglip` | `models/google/medsiglip-448` | 448, mean/std 0.5, bicubic | vision tower `pooler_output` (MAP head) |
| `dinov3` | `models/facebook/dinov3-vitl16-pretrain-lvd1689m` | 224, ImageNet mean/std, bilinear | CLS token of final norm output |

- Preprocessing: grayscale radiograph PNG → RGB → resize the full image to
  the square input size (no crop; aspect ratio not preserved) → normalize.
  Implement it explicitly in one function per encoder and test it against
  the HF processor on a sample (allowing the documented no-crop choice).
- SKELEX is `ViTMAEForPreTraining`: load `ViTMAEModel` weights and **set
  `mask_ratio = 0.0`** and ensure no random shuffling (pass deterministic
  `noise` or verify the ViTMAE code path with mask_ratio 0 keeps token
  order); test that two forward passes are bit-identical in eval mode and
  that 196 patch tokens + CLS are returned.
- DINOv3 has 4 register tokens: the token layout is
  `[CLS, reg×4, patches]`; exclude registers from patch-token outputs.
- Each adapter exposes: `preprocess(PIL) -> tensor`, `forward(x,
  layers=[...]) -> {"pooled", "cls"[layer], "patch_mean"[layer],
  "patch_tokens"[layer] (optional)}`, `num_layers`, `hidden_size`,
  and a `trainable_module()` for fine-tuning with a fresh linear head.
- Feature extraction CLI `wsp-ml features --encoder E --set {pool,test,external}`:
  fp32 outputs saved as `.npy` + JSON index (filename order) with model file
  SHA-256, code revision, dtype/autocast settings. Store pooled features and,
  for layers at fractions {1/3, 1/2, 2/3, 5/6, 1} of depth, CLS and patch-mean
  features. Pool → `features/<enc>/pool/`; external →
  `features/<enc>/external/<dataset>/`; **test → `data/locked/private/features/<enc>/test/`**.
  Use bf16 autocast for speed, but record it; determinism check: rerun 8
  images and assert max abs diff < 1e-2.
- External labeled sets for arm H (binary "fracture/abnormal"):
  GRAZPEDWRI-DX (`dataset.csv`: `fracture_visible`), FracAtlas
  (`dataset.csv`: `fractured`), MURA (study label from `*_labeled_studies.csv`,
  all body parts, train+valid). Document exact column use and counts.
- CUDA smoke: tiny matmul on GPU vs CPU, and a single bf16 forward of each
  encoder. Record torch/CUDA/cuDNN versions.

## 4. Networked sandbox (lane L2)

Topology per session `<run>`:

- `wsp-int-<run>`: Docker bridge network, `internal: true` (and the
  `gateway_mode_ipv4: isolated` option already validated in `infra/`).
- `wsp-proxy-<run>`: mitmproxy (pinned image digest) attached to
  `wsp-int-<run>` and to an egress bridge `wsp-egress` (normal NAT bridge).
  Runs the addon `infra/proxy/wsp_policy.py`. No published host ports.
- `wsp-agent-<run>`: agent image, attached **only** to `wsp-int-<run>`;
  `HTTP(S)_PROXY`/`http(s)_proxy`/`ALL_PROXY` = `http://wsp-proxy-<run>:8080`,
  `NO_PROXY=localhost,127.0.0.1`. The mitmproxy CA certificate is trusted
  system-wide in the image at runtime (mounted public cert +
  `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `PIP_CERT`,
  `NODE_EXTRA_CA_CERTS`, `GIT_SSL_CAINFO` pointing to a combined bundle).
  The CA private key exists only in the host-only proxy confdir.
- Agent container hardening: `--user 1004:1004`, `--cap-drop ALL`,
  `--security-opt no-new-privileges`, read-only root fs, tmpfs `/tmp` (16g),
  `--shm-size 16g`, `--pids-limit 4096`, `--memory 28g`, `--cpus 10`,
  `--gpus device=0`, `HOME=/workspace/home`, no Docker socket, no host
  namespaces, no published ports. Mounts only:
  `/workspace` (rw, run workspace), `/inputs/pool` (ro, resolved pool dir),
  `/inputs/labels` (ro, directory containing only `labels.csv`),
  `/inputs/models` (ro, `$ROOT/models`), `/inputs/external` (ro,
  `$ROOT/data/external/extracted`), `/opt/wsp-ca` (ro, public CA cert).
- Agent image `infra/agent/Dockerfile` (`wsp-agent:<tag>`): CUDA-enabled
  PyTorch matching host driver (CUDA ≤ 13.0), Python 3.12, pinned
  versions: torch, torchvision, transformers (DINOv3 support), peft, timm,
  accelerate, safetensors, scikit-learn, scipy, numpy, pandas, pillow,
  imagehash, opencv-python-headless, matplotlib, tqdm, pyarrow; plus
  `git`, `curl`, `wget`, `ripgrep`, `jq`, `unzip`, `file`, `procps`; plus the
  toolkit package (`toolkit/`, lane L4) installed into the image. Agents may
  `pip install --user` additional packages through the proxy.
- Proxy policy (`wsp_policy.py`), all decisions fail closed:
  1. Deny (HTTP 403 with a plain explanation) full-URL rules, matched after
     normalization (lowercase host, percent-decoding, collapsing slashes):
     Figshare article `30335941` and file `66766667` in any figshare.com /
     api.figshare.com / ndownloader.figshare.com / figshare-* CDN form,
     DOI `10.6084/m9.figshare.30335941`, GitHub `ninglitony/Benchmark-for-MFXR`
     on github.com, api.github.com, raw.githubusercontent.com,
     codeload.github.com, objects.githubusercontent.com redirects (deny via
     redirect-chain inspection), gist/jsdelivr/statically/githack mirrors of
     that repo; known hosted fetch/relay services (r.jina.ai, jina.ai reader,
     archive.org/web snapshots of the denied URLs, `webcache`, translate
     proxies, 12ft, `*.firecrawl.dev`, `api.tavily.com/extract`, etc. —
     keep a reviewed list in `infra/proxy/denylist.yaml`).
  2. Destination safety: resolve at connect time inside the proxy and refuse
     loopback, RFC1918, link-local, CGNAT, multicast, ULA/IPv6 local,
     metadata IPs, and the Docker bridge subnets; refuse raw-IP hosts in
     private ranges; re-check after redirects.
  3. Content: buffer bodies up to 4 GiB (larger → block, fail closed, logged,
     orchestrator may allowlist explicit URLs). For every response body:
     SHA-256 vs MFXR raw/normalized/archive hashes; if image (magic bytes) →
     decode with pixel limit → pHash vs all MFXR pHashes (Hamming ≤ 4 →
     block); carve embedded JPEG/PNG streams from any body (parquet, arrow,
     tar, pdf, etc., bounded to 20,000 carved images) and apply the same
     checks; recursively open zip/tar/gz/bz2/xz/zstd containers to depth 3
     and ≤ 20 GiB uncompressed (encrypted or over-limit → block); text bodies
     → block if ≥ 3 distinct original MFXR basenames (e.g. `248388-1.jpg`)
     appear. Uploads (request bodies) are scanned with the same rules for
     the basenames check only.
  4. Logging (host-only JSONL, never mounted into agents): time, run id,
     method, scheme, host, path without query, SHA-256 of the full URL,
     status, request/response sizes, content SHA-256, verdict, rule id. Never
     log headers, cookies, query strings, or bodies.
- Workspace watcher (host process, per run): scans the workspace every 120 s
  (and on demand) for new/changed files. Images → SHA-256 and pHash.
  **Stop & invalidate** (via harness callback) if: SHA-256 equals any MFXR
  raw/archive hash; pHash Hamming ≤ 2 to any **test-split** image; a text
  file contains ≥ 3 original MFXR basenames. **Alert only** (logged for
  orchestrator review) for pHash 3–6 to test images. Matches to pool
  images are permitted (the pool is mounted on purpose) and are recorded
  as `pool-derivative` only. Archives in the workspace are scanned like the
  proxy does (bounded). Thresholds are calibrated against the section 8.3
  overlap audit before launch; record the calibration.
- GPU watchdog (host process): every 5 s read
  `nvidia-smi --query-compute-apps=pid,used_memory`, map host PIDs to
  containers via `/proc/<pid>/cgroup`; per-session cap **11 GiB** total; on
  violation SIGKILL the largest offending process in that container
  (`docker exec -u 0 <ctr> kill -9 <nspid>` or `docker kill`-free
  equivalent) and log it. Also log per-container GPU memory and utilization
  samples every 30 s for accounting (SM time is shared, not partitioned).
- Tests (`tests/infra/`, run against real Docker, GPU-enabled topology):
  allowed HTTPS to pypi.org/huggingface.co/github.com through the proxy;
  denied MFXR URLs return 403; direct egress bypassing the proxy fails
  (TCP, UDP DNS to 8.8.8.8, host IPs, docker gateway); proxy refuses private
  destinations; synthetic hash corpus test (a generated image registered in a
  test corpus is blocked as raw bytes, re-encoded/resized (pHash), inside a
  zip, carved from a parquet-like blob; basename text list blocked);
  `nvidia-smi` and a CUDA torch op inside the agent container; watcher
  detections and pool-derivative non-detection; GPU watchdog kills an
  over-cap process; no credentials/docker socket/locked paths visible inside.

## 5. Arms A–E, H and locked evaluation (lane L4)

Package `src/wsp_arms/` and `src/wsp_eval/`. Encoders × k × resamples as in
`plan.md` 8.1. Every run writes a private record (config, seeds, code
revision, train image list hash, predictions on pool-irrelevant test set,
threshold) under `data/locked/private/runs/baselines/<arm>/<enc>/k<k>/r<r>/`.

Shared rules:
- Training data = only the (k, r) allocation (+ pool images unlabeled where
  the arm allows + external public data for H). Validation/model selection
  only from the k labeled patients by patient-grouped CV.
- Threshold from k labels: out-of-fold (patient-grouped, LOPO if k ≤ 20,
  else 5-fold) predictions, threshold maximizing Youden's J; ties → midpoint
  of the optimal interval. k=0 and single-class samples → fixed threshold 0.5
  on predicted probability. Fine-tuned arms (B, D-ft, H) do not refit OOF
  (too costly); they use the fixed threshold 0.5 on their class-balanced
  output (preregistered; threshold is a secondary endpoint only).
- Single-class (k, r) sample: supervised arms output the constant training
  class prior (AUROC 0.5 by construction); report it.
- Not applicable at k=0: A, B, C, E. Applicable at k=0: D (pseudo-labels
  only), H (transfer model as is). Zero-shot runs: threshold 0.5, no target
  tuning.

Recipes (fixed; no tuning against test):
- **A** L2 logistic regression on standardized pooled features; C chosen
  from {0.01, 0.1, 1, 10} by patient-grouped CV log-loss (LOPO if k ≤ 20,
  else 5-fold); k with < 2 patients per class → C = 1.
- **B** fine-tuning, two variants reported separately, both on all three
  encoders: `B-full` (all encoder parameters, lr 1e-5, layer-wise decay
  0.75) and `B-lora` (LoRA r=16, α=32, dropout 0.1 on attention q,k,v,o and
  MLP; lr 2e-4). Fresh linear head lr 1e-3. AdamW wd 0.05, cosine schedule
  with 5% warmup, batch 16 (grad accumulation allowed), bf16 autocast,
  gradient checkpointing. Steps = max(200, ceil(4 epochs)). Augmentation:
  RandomResizedCrop(scale 0.7–1.0, ratio 0.8–1.25), horizontal flip,
  rotation ±10°, brightness/contrast ±0.1. Class-balanced loss weights.
  No early stopping (final step model). Training seed = 1000·r + k.
- **C** self-training on frozen pooled features: start from A; 5 rounds; each
  round pseudo-label unlabeled pool images whose predicted probability is in
  the top 10% (positive) or bottom 10% (negative) per round cumulatively
  (cap 50% of pool), sample weight 0.5, refit with A's chosen C.
- **D** Opus 5.5 zero-shot pseudo-labels, once for every pool image
  (preregistered prompt in `config/arm-d-prompt.md`, no example images,
  thinking low, output JSON `{"p_monteggia": 0–100}`; parse failures retried
  ×3 then excluded). Variants: `D-head` = A recipe on pool soft labels
  (p/100, as weighted binary pairs) plus the k true labels (weight 5,
  replacing pseudo-labels for those images), all (k, r, enc); `D-ft` = B-lora
  recipe on hard pseudo-labels (p ≥ 50) + k labels, **r = 1 only**, all k and
  encoders. k=0 uses pseudo-labels only.
- **E** scripted interpretability: per encoder, train one top-k SAE
  (dictionary 8× hidden, k=32, 20k steps, Adam 1e-4) on pool patch tokens
  of the 2/3-depth layer (all pool images, no labels; done once). Candidate
  feature sets: raw CLS/patch-mean at each stored layer and SAE mean
  latent activations. Classifier: difference-of-means direction from the k
  labels (on standardized features; SAE: top-m latents by |mean
  difference|, m ∈ {8, 32, 128}), score = projection; logistic calibration
  of the scalar score (1-D LR) on the k labels. Search over layer × feature
  set × m × whitening {none, diagonal} by patient-grouped CV AUROC on the k
  labels; ties → simplest. All automated.
- **H** transfer: per encoder, B-lora recipe trained on the union of
  GRAZPEDWRI-DX, FracAtlas and MURA binary labels (class-balanced, 1 epoch
  over a seeded 40,000-image sample, seed 7), then (k > 0) continue with the
  B-lora recipe on the k labels with a fresh head initialized from the
  transfer head. k=0: transfer model directly, threshold 0.5.

Locked evaluation (`wsp_eval`):
- Input: per-test-image probability CSV for all 1,593 private test files.
  Missing/NaN predictions are an evaluation failure (scored as 0.5 and
  flagged).
- Metrics: image-level AUROC (primary), sensitivity/specificity at the
  run's fixed threshold, Brier, ECE (15 equal-width bins), and
  patient-level AUROC (max over patient images) as a secondary.
- CI: 2,000 bootstrap replicates resampling test patients (cluster
  bootstrap); for arms with resamples, nested: resample r uniformly within
  each replicate. Paired G−F differences with the same patient replicates.
- The "other-fracture controls" subgroup cannot be identified: MFXR does not
  provide subgroup annotations. Report as not estimable; do not infer.
- Overlap audit: before scoring, compute pHash Hamming distances between all
  test images and every image in GRAZPEDWRI-DX, FracAtlas, MURA and any
  external image recorded by the F/G proxies; report pairs ≤ 6; re-score
  excluding test images with a match ≤ 4 as a sensitivity analysis.
- Scoring is executed only by the orchestrator via
  `wsp-eval score --run ...`; it writes private outputs and a disclosure-safe
  aggregate summary.

F/G evaluation: the frozen final workspace snapshot is mounted read-only at
`/workspace` in a fresh `wsp-agent` container with `--network none`, test
PNGs mounted read-only at `/eval/images`, output dir at `/eval/out`; run
`python /workspace/output/model/predict.py --images /eval/images --out
/eval/out/preds.csv` with a 3-hour timeout and the 11 GiB GPU cap. The
threshold is read from `/workspace/output/model/threshold.json`.

## 6. Agent toolkit (lane L4)

**Amendment 2026-11-08 (ADR-004):** F and G receive identical precomputed label-free pool-patch SAEs (SKELEX layers 8/12/16/20 and MedSigLIP/DINOv3 at two-thirds depth), pool mean latents and quality statistics in `/workspace/provided/sae/`. R receives the package if present. No test data are included. Agents may ignore these or train their own. The launch receipt records the package manifest hash; readiness checks validate the package. File permissions are read-only, not a security boundary against the workspace owner.

`toolkit/wsp_toolkit/` (pip-installable, used by arm E on the host and in
the agent image). Documented in `toolkit/TOOLKIT.md` (copied to each
workspace). Contents: encoder loaders (same adapters as `wsp_ml`, path
`/inputs/models`), batched feature extraction with forward hooks at any
layer (CLS/patch tokens), exemplar search (top-activating images/patches for a
direction or SAE latent, montage writer), crop/occlusion probes, procedural
probe generators (crop, contrast, gamma, flips, rotation, pasted markers,
noise), top-k SAE training/inspection, linear-probe and LoRA/full fine-tune
helpers with periodic checkpointing (safetensors) and a provenance logger
(`wsp_toolkit.provenance.log_checkpoint(path, parents, operation, details)`
appending to `/workspace/output/provenance.jsonl` with SHA-256 and
per-tensor change summaries). The toolkit must not contain any MFXR data or
labels. The toolkit is a convenience; agents may write their own code.

## 7. Pi harness and recorder (lane L3)

Trusted code in `harness/` (host only, never mounted into containers).

- **Container tool extension** `harness/pi-ext/container-tools.ts`: overrides
  `read`, `write`, `edit`, `bash` (and `grep`/`find`/`ls` if enabled) so all
  operations execute in `wsp-agent-<run>` via
  `docker exec -i -u 1004:1004 -w <cwd> <ctr> ...` using argument arrays
  (no host shell interpolation). Paths are container paths; the agent's cwd
  is `/workspace`. Image reads return image attachments (Opus/Haiku image
  reading). Rewrites the system-prompt cwd line. Container name comes from
  an env var set by the supervisor, not from the agent.
- **Haiku subagent tool** (ADR-002) in the same or a sibling extension:
  `subagent` with params `{task: string, wait?: boolean}`; spawns a host
  `pi` child with **hard-coded** `--model anthropic/claude-haiku-5-5`,
  `--thinking medium`, the same container-tools extension and container,
  `--no-extensions -e <container-tools>` (no subagent tool for children:
  one level only), `--no-skills --no-context-files --no-prompt-templates`,
  `--session-dir <run recorder>/subagents/`, mode json, prompt = task.
  Returns the child's final text (truncated with full output saved in the
  recorder) and the child id; async mode returns id immediately and a
  companion `subagent_result {id}` tool polls/waits. No limit on total
  children; at most 8 concurrent per session (queue beyond). Children obey
  the session deadline (killed at deadline). Child stdout events are also
  logged by the supervisor.
- **Supervisor** `harness/supervisor.py` (`wsp-harness launch|status|intervene|stop|seal`):
  creates the run directory `runs/<run>/` (gitignored, 0700) with
  `recorder/` (Pi session dir, raw RPC event log, subagent sessions,
  supervisor log), `workspace/` (mounted rw into the container),
  `snapshots/`, `proxy/`, `watcher/`, `gpu/`, `interventions.jsonl`,
  `launch.json` (Git revision, prompt/config/extension/image hashes, model
  IDs, sample manifest hash, deadlines). Starts sandbox (lane L2 API),
  watcher, GPU watchdog. Starts `pi --mode rpc` on the host with
  `--model anthropic/claude-opus-5-5 --thinking medium --session-dir
  runs/<run>/recorder/sessions --no-extensions -e container-tools.ts
  -e <web-search-ext> --no-skills --no-context-files --no-prompt-templates
  --no-themes --tools <allowlist>` and the arm definition from
  `.pi/agents/wsp-arm-{f,g}.md` (frontmatter = model/thinking/tools; body =
  appended system prompt). Sends the launch prompt from
  `.pi/prompts/wsp-launch.md` (rendered with k, timestamps; rendered text
  and hash recorded). Logs every RPC event verbatim to
  `recorder/rpc-events.jsonl`.
- Continuation: when the agent becomes idle before the deadline and
  `/workspace/output/FINAL` does not exist, wait 5 minutes (from the idle
  moment) then send the fixed message from `.pi/prompts/wsp-continue.md`
  (current time, deadline, time remaining). This is a preregistered
  harness message, identical for F and G, logged as
  `auto-continuation` (not an intervention). If FINAL exists, the session
  ends early and is frozen. API errors: exponential backoff retry
  (1, 2, 4 … ≤ 15 min) logged as `auto-retry`.
- Deadline: at T+24h send RPC abort, terminate pi and children, `docker
  pause` the agent container, take the final snapshot, then stop and remove
  containers/networks. Hourly snapshots: `rsync -a --link-dest` of the
  workspace into `snapshots/<UTC time>/` plus a SHA-256 manifest of all files
  and an index of checkpoint-like files (`*.pt, *.pth, *.safetensors, *.bin,
  *.ckpt, *.npz, *.npy` > 1 MiB) with hashes, so checkpoint lineage over time
  is reconstructable.
- Interventions: `wsp-harness intervene --run R --kind {infra,message}
  --note ...` appends to `interventions.jsonl`; `message` additionally sends
  an RPC steer message (only for infrastructure notices; never task advice).
- Accounting: `wsp-harness account --run R` sums usage/cost from all session
  files (parent and subagents) by model and token type, API-equivalent
  `cost.total` (note `totalFromProvider` false), counts retries/errors,
  GPU-hours/peak memory from watchdog samples, wall clock, proxy bytes,
  and snapshots the pi model price table used.
- Integrity tests: from inside the agent container (via the tools and
  directly) attempt to locate/alter recorder files, the harness, `~/.pi`,
  the Docker socket, and locked data — all absent; verify
  every `tool_execution_end` in `rpc-events.jsonl` has a matching tool
  result entry in the session file and vice versa (event completeness),
  including subagents; verify the agent cannot choose a non-Haiku model
  for subagents; verify the deadline kill and freeze on a short test run
  (2-minute deadline, Haiku as the parent model for the test only).
- Seal: `wsp-harness seal --run R` writes `receipt.json` (SHA-256 of every
  evidence file), then packages evidence into DVC-tracked directories under
  `artifacts/runs/<run>/` (`dvc add` of a directory; no 128 MiB limit) with
  a secret-pattern scan report; push only after orchestrator review.

## 8. Order of operations (orchestrator)

1. L1 → merge. L2, L3 in parallel with L1; L4 after L1 merges.
2. Sol review of each lane; fix; merge; full test suite.
3. Bucket privacy check; DVC-archive preparation mappings/receipts.
4. Extract features; overlap audit; calibrate watcher thresholds.
5. Integration: short Haiku dry-run session in the real topology;
   red-team session (Opus 5.5, 60 min, same container/proxy, instructed to
   obtain MFXR images or labels by any means); fix and repeat until all
   attempts are blocked or detected.
6. Arm D pseudo-labeling (before F/G to avoid API contention).
7. Freeze: commit, tag `phase1-launch-freeze`, record hashes.
8. Launch F/G k=10 in parallel (24 h); then k=50 (24 h). CPU arms (A, C,
   D-head, E) run on the host meanwhile with `taskset`/`nice` limits
   (≤ 4 cores) and no GPU use.
9. GPU arms (B, D-ft, H) after F/G sessions end.
10. Audits (proxy, transcripts, provenance, F-prohibition, watcher,
    resources), overlap re-scoring, then locked scoring of all arms,
    gate evaluation, report.

## 9. F/G specifics

- k = 10 and k = 50 use the resample-1 allocation (same as baselines).
- Workspace layout at launch: `/workspace/TASK.md` (launch prompt copy),
  `/workspace/TOOLKIT.md`, `/workspace/output/` (empty), `/inputs/...`.
- Required outputs (plan 7.4) in `/workspace/output/`: `model/predict.py`
  (+ any files it needs anywhere under `/workspace`), `model/threshold.json`,
  `REPORT.md`, `provenance.jsonl`, and the `FINAL` marker when done.
- If no output at deadline: the last saved model referenced in
  `output/model/` is used; if none, the run is incomplete and scored as
  missing (AUROC not reported; counted as failure).

## 10. Deviations from plan.md (to report)

- C uses self-training on frozen features (plan permits self-training or
  FixMatch); no FixMatch.
- D labels each pool image once (zero-shot, no examples) rather than once
  per k with k-shot examples; `D-ft` only for resample 1.
- B is reported as two variants; the AUROC target is the larger of the
  B-full / B-lora mean AUROC at k = all, minus 0.02 (conservative).
- E and A at k=0 not applicable; H and D are the k=0 zero-shot arms.
- GPU share: equal 11 GiB VRAM caps enforced by a kill-on-violation host
  watchdog; SM time is not partitioned (non-MIG A5000). Not a hardware
  partition.
- Baseline GPU arms run after the F/G sessions (scheduling only; recipes
  are frozen before launch).
- Other-fracture-control subgroup not estimable (no annotations).
- F/G may spawn Haiku 5.5 subagents (ADR-002).
