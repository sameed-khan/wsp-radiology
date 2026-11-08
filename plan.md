# Plan: weight-space programming for label-efficient radiology models

Status: approved design for the Phase 1 pilot, 2026-11-08.
Background notes are in `research/datasets.md`
and `research/mech-interp-toolbox.md`.

## 1. Question

Does a reasoning optimizer that may edit network weights directly
reach a given performance with fewer expert labels on a new dataset
than the same optimizer without that permission,
and fewer than standard label-efficient methods?

The reasoning optimizer is Claude Opus 5.5.
It is not restricted in tools:
it may use any interpretability method, train models, read images,
and use any public data, model, or label on the internet,
except sources that contain labels for the target dataset (section 5).
The only manipulated variable is the number of expert labels
on the target dataset (the label budget, k).

## 2. Outcome levels

The study maps results to five levels, fixed before any run.
Arms are defined in section 6.
"Non-inferior" uses a margin of 0.02 AUROC.

1. **Level 1:** arm G at k ≤ 10 is better than arm B with all labels.
2. **Level 2:** arm G at k ≤ 10 is non-inferior to arm B with all labels.
3. **Level 3:** arm G reaches the AUROC target (section 8)
   at no more than half the k required by the best of arms A–F and H.
4. **Level 4:** arm G is better than the best of arms A–F and H
   at the same k for at least one k,
   and the gain is not explained by threshold or calibration changes.
5. **Level 5:** no gain over arm F or arm E.
   Repairs or audit findings are reported descriptively.

The primary contrast is G versus F.
It isolates the effect of permission to write weights directly,
because both arms have the same model, tools, data, and time.

## 3. Phases

1. **Phase 1 (pilot):** MFXR, binary classification, frozen-encoder start.
   Purpose: test the harness, the toolkit, and the size of any G–F effect.
2. **Phase 2:** RSNA Knee Abnormality Detection,
   12-label classification, hidden test set scored by Kaggle.
   Run only if Phase 1 passes the gate in section 10.
3. **Phase 3:** detection or segmentation.
   Candidates are LIDC-annot-NLST501 and a chest CT task for Pillar-0.
   Chosen after Phase 2.

The rest of this document specifies Phase 1 in detail.

## 4. Phase 1 data: MFXR

- **Source:** Monteggia fracture X-ray dataset ([paper][mfxr-paper],
  [data][mfxr-data]), CC BY 4.0, public since 2026-07-18.
  This is after the Opus 5.5 training cutoff (June 2026).
- **Content:** 4,586 pediatric forearm radiographs at one hospital
  (Shenzhen Children's Hospital). The paper reports 1,482 patients;
  the release has 1,484 patient identifiers (993 train, 491 test).
  Use the release identifiers, as approved by the investigator,
  and report this discrepancy.
  The label is Monteggia fracture versus control;
  controls include normal forearms and other fractures.
  Labels were assigned by a pediatric orthopedist from the image
  and clinical record and verified by a second surgeon.
- **Splits:** the official patient-level split.
  The training split (2,993 images) is the pool.
  The test split (1,593 images, about 63% positive) is locked.
- **Preparation before any run:**
  1. Download the data once, on the orchestrator account.
  2. Record the SHA-256 of the archive and of every image.
  3. Copy pool images to the agent workspace with random file names.
     Strip folder structure, file names, and metadata,
     because the original layout may encode the class.
  4. Keep the test split and all pool labels
     in `data/locked/`, readable only by the orchestrator account.

## 5. Label accounting and leakage control

### 5.1 What counts as a label

- A label is an expert label on a target-dataset patient.
- Each run receives exactly k labeled patients, sampled at random
  by patient from the pool with a recorded seed.
  All images of a sampled patient carry the patient's label.
- The labeled file is the only source of target labels.
  No arm may query the locked labels.
  Any validation set must come from the k labeled patients.
- External public data, labels, and models are allowed for all arms.
  They are logged, not counted.
- Images read by Opus (for pseudo-labels or inspection) are logged
  as LLM-derived labels, not counted as expert labels.

### 5.2 Denylist

These sources contain target labels or models trained on them.
Using any of them invalidates a run.

- MFXR on Figshare and any mirror.
- The MFXR benchmark code repository ([mfxr-code]) and any
  predictions or weights trained on MFXR.
- For Phase 2: the competition data outside the provided copy,
  the published LLM labels of the 1st- and 7th-place teams,
  the NTejas report labels, and the released 3rd- and 6th-place weights.

Enforcement is technical, not only instructed.
A denylist inside the web-search tool alone is not enough,
because the agents have a shell and can reach the network
with curl, Python, git, or the Hugging Face and Kaggle clients.
Some hosted fetch providers also retrieve pages on their own servers,
where a local proxy sees only the provider's API call.
Enforcement therefore has four layers:

1. **Container with a single exit.**
   Each session runs in a hardened, nonroot Docker container with GPU
   access. Docker replaces Podman by investigator approval; the existing
   rootful Docker daemon is part of the trusted host, not rootless isolation.
   The container sits on an internal network
   whose only route out is a mitmproxy container.
   Connections that bypass the proxy fail.
   The container mounts only the agent workspace,
   so `data/locked/` does not exist inside it.
2. **Full-URL denylist at the proxy.**
   The proxy decrypts HTTPS with its own certificate authority,
   which is trusted inside the container,
   so it can match full paths rather than domains.
   This allows Figshare, Zenodo, GitHub, Hugging Face, and Kaggle
   while blocking the specific MFXR records and repositories.
   Blocked requests return HTTP 403, and every request is logged.
3. **Content blocking.**
   A URL denylist misses unknown mirrors.
   The SHA-256 and perceptual hash of every MFXR image are known,
   so blocking also uses content:
   - The proxy hashes downloaded files, and the files inside archives
     below a size limit, and blocks any match to MFXR.
   - A watcher outside the container scans new image files
     in the agent workspace with perceptual hashes,
     which survive resizing and re-encoding.
     A match stops the session and marks the run invalid.
4. **Tool configuration.**
   The F and G agent definitions disable fetch providers
   that retrieve pages on third-party servers,
   so all fetches pass through the proxy.
   Web search stays enabled; search results return snippets,
   not label files.

The anonymized pool file names (section 4) add a further check.
A public label file is keyed by original MFXR file names,
so it cannot be joined to pool images
without downloading the original images,
which layer 3 detects.
Text about MFXR, such as the paper and its baseline AUCs, is allowed.
It describes the task but contains no labels.

Before the real runs, a red-team agent in the same container
is instructed to obtain MFXR images or labels by any means.
Every attempt must be blocked or detected,
and the result is reported in the methods.
After each real run, the orchestrator audits the proxy log
and the agent transcript.
Agents are told the denylist and the reason for it at launch.

### 5.3 Overlap with external data

Other public pediatric musculoskeletal datasets may contain
the same images as the MFXR test split.
Before results are scored,
compare perceptual hashes of all test images
with every external dataset that any arm downloaded.
Report near-duplicates and re-score without the affected test images.

## 6. Arms

All arms start from the same encoders and the same pool images.
Arms F and G may replace or combine encoders; every change is logged.

| Arm | Method | LLM |
|---|---|---|
| A | Logistic regression on frozen features | No |
| B | Fine-tuning (full and LoRA) on k labels | No |
| C | Semi-supervised: self-training or FixMatch | No |
| D | Opus pseudo-labels the pool; a model trains on them | Labels |
| E | Scripted interpretability pipeline | No |
| F | Opus agent, all tools, no direct weight writes | Agent |
| G | Opus agent, all tools, direct weight writes (WSP) | Agent |
| H | Transfer from public labeled data, then k labels | No |

Arm notes:

- **D:** Opus 5.5 reads every pool image once per k.
  Its prompt may include the k labeled images as examples.
  A head and a fine-tuned model are trained on the pseudo-labels
  plus the k labels; the better one on the k labels is reported.
- **E:** SAE on pool features, difference-of-means directions
  from the k labels, and an automated search over layer, feature set,
  and scale.
  This is the non-LLM version of the methods arm G is expected to use.
- **H:** the source datasets are fixed in advance:
  GRAZPEDWRI-DX, FracAtlas, and MURA.
  Pretrain on them, then fine-tune on the k labels.
- **F and G** are described in section 7.
- **Weight provenance:** F and G retain unrestricted experimentation
  within the study rules; a restricted fitting/editing service is not used.
  F is prohibited from direct weight writes; G is permitted them.
  The trusted harness records tool/session history and checkpoint lineage
  outside agent write access. Audit attributes changes to direct
  LLM-prescribed edits, closed-form fitting or gradient training,
  retaining mixed ancestry and explicitly marking unknown attribution.
  This is audited provenance, not a technical proof of each weight's origin.
  The investigator-approved evidence boundary is specified in
  [ADR-001](docs/decisions.md#adr-001-unrestricted-fg-experimentation-with-protected-audit-records).

### 6.1 Encoders

| Encoder | Role | License |
|---|---|---|
| SKELEX (ViT-L MAE, MSK radiographs) | Primary | CC BY-NC-ND 4.0 |
| MedSigLIP-448 (image and text towers) | Comparator | HAI-DEF terms |
| DINOv3-L (natural images) | Comparator | Open |

- Arms A–E and H run on all three encoders.
- Arms F and G start from SKELEX and may use the others.
- SKELEX is no-derivatives: publish head edits or weight differences,
  not a modified SKELEX checkpoint.

## 7. Agent arms (F and G)

### 7.1 Setup

- Each agent is a dedicated pi agent defined in the project-local
  `.pi/` folder: Claude Opus 5.5 at medium effort.
- The two definitions differ only in the weight-write permission
  and the sentence that describes it.
- Each session runs in its own container (section 5.2)
  with its own workspace, no access to `data/locked/`,
  and network access only through the proxy.
- Agents and their subagents cannot write, delete, replace or disable
  authoritative Pi histories, audit records, or trusted harness code and
  configuration. A trusted supervisor/recorder outside their writable
  execution sandbox retains full history and artifact hashes; experimental
  scripts and workspace snapshots supplement the tool-call record.
  Log-integrity and event-completeness checks are launch prerequisites.
- Each session gets a fixed GPU share.
  F and G at the same k run at the same time with the same share
  (for example, 12 GB VRAM each).

### 7.2 Launch instructions

The launch prompt states:

- the task, the target finding, and the clinical context;
- the k labeled patients and the unlabeled pool;
- the starting encoder and the required output interface;
- the denylist and the reason for it;
- the permission to write weights directly (G only)
  or the prohibition (F only);
- the deadline: "You have 24 hours from now",
  with the absolute timestamp.

### 7.3 Toolkit

Both arms have the same tools.
The toolkit review (`research/mech-interp-toolbox.md`) lists the methods.
At a minimum:

- activation hooks, exemplar search, and crop probes;
- SAE training and feature inspection;
- procedural probe images (crops, contrast, flips, pasted markers);
- public unlabeled and labeled images, such as MURA, FracAtlas,
  and GRAZPEDWRI-DX;
- Opus image reading;
- GPU training with checkpoints, so features can be watched as they form;
- internet access through the proxy.

No open generative model exists for musculoskeletal radiographs,
so probe images are procedural edits and real images from other datasets.

### 7.4 Output

Each session must produce, before the deadline:

- a model directory with weights and an inference script
  that maps an image to a fracture probability;
- a decision threshold chosen using only the k labels;
- a written report of what was done and why;
- the weight-provenance log.

If no output exists at the deadline,
the last saved model is used and the run is marked incomplete.

### 7.5 Orchestrator duties

The orchestrator is the agent that the investigator talks to.

- Launch sessions and record start times.
- Check each session about every hour.
  Resolve infrastructure blockers (crashed jobs, disk, proxy errors)
  without giving task advice.
  Log every intervention.
- Stop each session at 24 hours and freeze its workspace.
- Run the locked test evaluation for all arms.
- Audit proxy logs and transcripts (section 5.2).

## 8. Budgets, endpoints, and analysis

### 8.1 Phase 1 budgets

- **Arms A–E and H:** k ∈ {0, 10, 20, 50, 100, 250, all},
  5 resamples each, on all three encoders.
  Arm B is not run at k = 0.
- **Arms F and G:** k ∈ {10, 50}, 1 resample, on SKELEX.
  That is 4 sessions of 24 hours.
  Run F and G for one k in parallel, then the other k:
  about 2 days in total.
- At k = 0, methods requiring target labels are not applicable.
  Applicable zero-shot methods use no target-label tuning or model selection
  and a preregistered fixed decision threshold.
- The F and G resamples use the same labeled patients
  as resample 1 of the other arms.

### 8.2 Endpoints

- **Primary:** test AUROC at each k.
- **AUROC target:** arm B with all labels minus 0.02.
  The label requirement of an arm is the smallest k that reaches it.
- **Secondary:** sensitivity and specificity at the threshold fixed
  from the k labels; Brier score and expected calibration error;
  AUROC on the subgroup of control images that contain other fractures.
- **Resources:** tokens, cost, wall-clock time, GPU hours,
  external data used, and orchestrator interventions.

### 8.3 Analysis

- Confidence intervals by bootstrap over test patients;
  for arms with resamples, nested within resamples.
- With one F and G resample per k,
  Phase 1 reports effect sizes with intervals that cover
  only test-patient variation.
  It does not support claims about label-sampling variation.
- Report any gain in AUROC separately from gains in threshold choice
  and calibration.

## 9. Compute and cost

- **GPU:** one 24 GB card is enough for Phases 1 and 2.
  ViT-L fine-tuning at 224 px fits with bf16 and gradient checkpointing.
  MedSigLIP at 448 px needs LoRA or gradient checkpointing.
  The knee pipeline (2.5D ConvNeXt-T) fits.
- **Disk:** at least 1 TB free; the knee data are about 570 GB.
- **RAM:** 64 GB recommended.
- **API:** no spending cap.
  Expected Phase 1 cost is about $1,000–2,000 for agent sessions
  and under $50 for arm D.

## 10. Gate from Phase 1 to Phase 2

Proceed to Phase 2 if both hold:

- arm G is better than arm F at one or more k,
  with the gain present in AUROC and not only in threshold or calibration;
- the audit finds no use of denylisted sources in arm G.

If the gate fails, expand Phase 1 to more resamples and budgets
before deciding, because one resample per k has high variance.

## 11. Phase 2 outline: RSNA knee

- **Data:** 58 expert-labeled studies, 4,349 studies with reports only,
  and a hidden test set of about 1,322 studies scored by Kaggle
  late submission.
  RSNA has approved sending the data to third-party APIs.
- **Budgets:** k ∈ {0, 10, 20, 40, 58} gold studies.
  Reports are a label channel; arms that use them record that use.
- **Evaluation:** one preregistered late submission per arm and k.
  The 0.960 private leaderboard score is reported as context only.
- **Comparators:** arms D and F, and the top-team recipes
  rebuilt at 58 gold studies.
- **Encoders:** MRI-CORE (Apache 2.0) or OrthoFoundation
  (verify weight release and license), and ImageNet ConvNeXt-T.

## 12. Work before the first run

1. Move the repository to the GPU machine.
2. Download MFXR, record hashes, and build `data/locked/`
   and the anonymized pool.
3. Download SKELEX, MedSigLIP, and DINOv3-L; extract frozen features.
4. Build the agent container, the proxy, the denylist,
   and the content watcher; run the red-team test.
5. Write the F and G agent definitions in `.pi/`
   and the launch prompt template.
6. Implement arms A–E and H and run them at all budgets.
7. Freeze this plan and the launch prompts, then launch F and G.

## References

[mfxr-paper]: https://www.nature.com/articles/s41597-026-07547-y
[mfxr-data]: https://doi.org/10.6084/m9.figshare.30335941
[mfxr-code]: https://github.com/ninglitony/Benchmark-for-MFXR
