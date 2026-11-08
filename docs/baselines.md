# Phase 1 baselines: implementation and operations

This describes `wsp_arms` as implemented, not locked-test results. The binding
protocol is `docs/phase1-implementation-spec.md` §§5–6 and §10. Independent
code review was waived (ADR-003). No baseline code may read test labels or
compute test metrics; only the orchestrator runs locked scoring. See the lane
handoff for validation history and outstanding work.

## Inputs, outputs and shared rules

Run in the lane checkout with `uv`. Default data root is
`/home/skhanxx8/projects/wsp-radiology` (`WSP_ROOT` overrides it); models can
be selected with `WSP_MODELS=$ROOT/models`. The pool has 2,993 images and
private test has 1,593 images. Pooled features, allocations and test features
must already exist. Test filenames are checked against the private test PNG
listing, not a labeled manifest. Outputs are private under
`$ROOT/data/locked/private/runs/baselines/<arm>/<encoder>/k<k>/r<r>/`:
`predictions.csv` (`image,prob`) and `run.json` (written last as completion
marker; configuration, hashes, seeds, timing and threshold). Do not publish
private predictions, patient identifiers, labels or cache records. Record
and archive the non-reproducible D cache and required learned artifacts in
accordance with `docs/versioning-policy.md`.

Encoders: `skelex`, `medsiglip`, `dinov3`; budgets 10, 20, 50, 100, 250,
`all` (A/B/C/E), plus 0 for D/H; five resamples except D-ft r=1. A/C/E
are not applicable at k=0; B also is not applicable. Grouped CV is LOPO
at ≤20 patients, otherwise five-fold. Thresholds for A/C/D-head/E are
Youden on grouped out-of-fold predictions, midpoint for ties; B/D-ft/H use
fixed 0.5. Single-class target allocations use the constant image-level
training prior and threshold 0.5. k=0 uses no target tuning and threshold
0.5. Model selection and OOF metrics use only allocated target labels.

## Recipes and interpretation choices

* **A:** standardized pooled features, L2 logistic regression; grouped-CV
  log-loss selects C from 0.01, 0.1, 1, 10 (ties smaller). With fewer than
  two patients in either class C=1. Pooled features are final CLS for
  SKELEX/DINOv3 and MAP pool for MedSigLIP.
* **B-full/B-lora:** fresh linear head, AdamW weight decay 0.05, head LR
  1e-3, cosine schedule, 5% warmup, effective batch 16, bf16 and activation
  checkpointing, balanced cross entropy, final model, no early stopping.
  Full encoder LR 1e-5 with layer decay 0.75; LoRA rank 16, alpha 32,
  dropout 0.1, attention and MLP targets, LR 2e-4. Train for max(200,
  ceil(4 epochs in steps)), seed 1000*r+k. Augment with resized crop
  scale 0.7–1, ratio 0.8–1.25, horizontal flip, rotation ±10°, and
  brightness/contrast ±0.1. Default microbatch 2, MedSigLIP 1.
* **C:** start from A; five refits, weight 0.5 for hard pseudo-labels.
  Sticky selections add ceil(10% of the unlabeled pool) per tail per
  round subject to a total 50% cap, so later rounds can add none. Images
  of allocated patients are excluded from the unlabeled pool. OOF
  thresholds rerun the full procedure within each fold.
* **D:** Opus 5.5 reads each pool image once, zero-shot, using the fixed
  `config/arm-d-prompt.md`, low thinking and strict JSON p_monteggia 0–100;
  up to three attempts then failure/exclusion, cached privately. D-head uses
  A-style logistic regression on soft labels represented by weighted binary
  pairs; actual labels replace pseudo-labels at weight 5. The scaler fits
  unique images unweighted. Grouped CV excludes all held-out patient images
  from each fit; C=1 at k=0 or when fewer than two patients per class.
  D-ft uses B-lora on hard p≥50 labels with true labels substituted. Both
  require complete cache coverage; processed failures are excluded. The
  test-only `--allow-partial` uses separate output paths. A failed cached
  annotation is not automatically retried on restart; a torn final JSONL
  line requires repair. Earlier five validation entries lack verbatim response
  text, but retain parsed integer values.
* **E:** one SAE per encoder on pool patch tokens at 2/3 depth, dictionary
  8× hidden, top-k 32, Adam 1e-4 for 20,000 steps. Tokens are mean-centered
  and scaled by a global RMS; random token batch 2048, seed 7, normalized
  decoder columns, no auxiliary loss. Search stored CLS/patch means and
  SAE mean latents; use standardized difference-of-means direction, SAE
  top m=8/32/128, none or diagonal whitening. Diagonal means divide by
  pooled within-class variance + 0.1 on the standardized scale. Calibrate
  projected score with one-dimensional L2 logistic regression C=10. Select
  by grouped OOF AUROC, with deterministic simplicity tie-break. Search
  makes selected OOF AUROC optimistic; tiny allocations can be unstable.
* **H:** reuse `features/external-manifests/`: GRAZ `fracture_visible`
  (6,777 negative / 13,550 positive), FracAtlas `fractured` (3,364 /
  719), MURA labeled train+valid studies (23,606 / 16,403; positive is
  abnormal, not necessarily fracture). Uniformly sample 40,000 images
  without replacement from the union, seed 7; inverse-frequency loss
  weights balance classes, rather than balanced sampling. One epoch of
  B-lora recipe retains the partial final batch. External image loading
  permits truncated JPEGs. Save private LoRA+head checkpoint; k=0 uses it
  directly, k>0 continues both adapter and transferred head with a new
  optimizer and the B-lora schedule. Smaller samples are validation only
  and use separate paths.

## Commands and scheduling

```sh
export ROOT=/home/skhanxx8/projects/wsp-radiology
export WSP_MODELS="$ROOT/models" OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
uv lock --check
uv run pytest -q
# CPU grids, at most 8 workers
uv run wsp-arms grid --arm A --jobs 8
uv run wsp-arms grid --arm C --jobs 8
uv run wsp-arms sae                         # GPU, once per encoder
uv run wsp-arms grid --arm E --jobs 8
uv run wsp-arms grid --arm B                # GPU, both variants
uv run wsp-arms pretrain-h --encoder skelex  # repeat medsiglip and dinov3
uv run wsp-arms grid --arm H                # after all full checkpoints
uv run wsp-arms grid --arm D-head --jobs 8  # after cache is complete
uv run wsp-arms grid --arm D-ft             # GPU, r=1
```

The D labeling job is orchestrator-owned and already running from a frozen
copy; do not launch another. For reference, `wsp-arms label-d` defaults to
six workers, three attempts and a private resumable JSONL cache at
`$ROOT/data/locked/private/arm-d/labels.jsonl`. Grids skip completed records;
use `--force` after changing a recipe, and beware that general completion
checks do not prove all input/code revisions match. D additionally checks
cache hash. GPU grids are sequential; interruption restarts an unfinished
training cell, not its optimizer state. `--steps`, reduced H `--sample-size`,
and `--allow-partial` are for validation only, not production estimates.
The protocol schedules GPU baselines after F/G sessions. Use host thread
limits appropriate to other workloads; do not exceed the shared GPU budget.

## Measured work and estimates

A/C/E full grids: 90 cells each; A wall 28 s, C 69 s, E about 17 s per
encoder (historical runs). Three E SAEs took 341/537/351 s and peak
2.24/6.26/3.51 GiB respectively (SKELEX/MedSigLIP/DINOv3); the MedSigLIP
measurement exceeded the later 6 GiB shared-test guidance, although below
its configured 8 GiB cap. SAE training restarts on interruption; token
memmap is temporary and SAE intermediate checkpoints are deleted.

B 50-step seconds/step, full/lora: SKELEX 0.468/0.730, MedSigLIP
1.937/2.402, DINOv3 0.604/0.879; measured peak GiB 5.15/1.36,
7.34/2.35, 5.14/1.35. Estimated full B grid 18.84 GPU-hours including
scaled inference/loading; approximate, not a completed grid. Timing schedule
was 50 steps, not full schedule; other workloads affect throughput. For H,
200-image SKELEX pretraining measured 14.56 images/s, extrapolated 0.76 h
for 40,000 images training only; rough MedSigLIP/DINOv3 estimates from B
are 1.67/0.61 h, not measured on external input. H continuation/grid,
D-ft grid and D-head grid have no measured total runtime. Avoid full-model
MedSigLIP GPU runs under a 6 GiB cap without reconfiguration/validation.

Completed validation: full A/C/E grids; one SKELEX B-lora k10 r1 run;
SKELEX H 200-image pretrain, k0 inference and k10 r1 continuation; five
real D labeling calls; synthetic D training tests. Full B/H/D grids were
not performed in these steps. No test labels or test metrics were used.

## Protocol deviations and limitations

C is self-training, not FixMatch. D is once-per-image zero-shot rather
than per-k few-shot, and D-ft only r1. B has two separately reported variants;
the protocol's AUROC target uses the larger B-full/B-lora mean at k=all
minus 0.02. A/B/C/E are inapplicable at k=0; D/H use fixed 0.5 there.
The GPU watchdog's equal 11 GiB F/G cap is not a hardware SM partition;
GPU baseline scheduling is separate. Other-fracture-control subgroup is
not estimable from available annotations. The required external-image/test
pHash overlap audit and sensitivity scoring are orchestrator work before
locked evaluation. Toolkit provenance is self-reported, not authoritative;
checkpoint helpers save model state, not optimizer resume state. SAE latent
semantics were not inspected. SKELEX derivative redistribution rights remain
unsettled. Independent review was waived; no clinical validation is implied.
