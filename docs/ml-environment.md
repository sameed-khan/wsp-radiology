# Phase 1 ML environment

Install with `uv sync --frozen --extra test --extra models --extra ml`.
Pinned direct ML dependencies: torch 2.10.0+cu128, torchvision 0.25.0+cu128,
transformers 5.2.0, peft 0.18.1, safetensors 0.7.0, numpy 2.4.2,
scipy 1.17.0, scikit-learn 1.8.0, pandas 3.0.0. Torch wheels are
from the explicit PyTorch CUDA 12.8 index; the full lock is in `uv.lock`.
All model loading is offline from the local model directory.

Run `wsp-ml patient-map`, `wsp-ml sample`, `wsp-ml test-images`,
`wsp-ml hash-corpus`, and `wsp-ml cuda-smoke` in order. Then run
`wsp-ml features --encoder skelex --set pool`, substituting medsiglip or
dinov3 and pool or test. External image extraction uses
`--set external:FracAtlas`, `external:GRAZPEDWRI-DX`, or `external:MURA`.
External labels and inclusion rules are described below. `--limit` writes
a separate smoke-test destination.

The input is RGB-converted, resized to a square without crop, and normalized.
SKELEX uses 224 bicubic and ImageNet normalization; MedSigLIP 448 bicubic
and mean/std 0.5; DINOv3 224 bilinear and ImageNet normalization. Comparing
three pool images to the supplied HF processors, max absolute differences
were SKELEX 0.3152/0.4552/0.2276 (HF defaults to bilinear, spec requires
bicubic), MedSigLIP <= 1.2e-7, DINOv3 0.0174/0.0139/0.0140 (HF's fast
tensor resize differs numerically from PIL bilinear). HF processors also
resize to the full square in these supplied configurations.

Feature files are `pooled.npy`, `cls-<depth>.npy`, and
`patch_mean-<depth>.npy`, in `features/<encoder>/pool/`,
`features/<encoder>/external/<name>/`, or private
`data/locked/private/features/<encoder>/test/`. Arrays are fp32, extracted
under bf16 autocast; `index.json` defines row order, model hashes, revision,
layers, available CLS representations and determinism check. Depths are
one-based. DINOv3 excludes four register tokens from patch means. SKELEX
uses zero masking with deterministic ordered noise. MedSigLIP has no CLS:
intermediate CLS is absent and final CLS is its MAP pooled feature, labeled
`map_pool` in the index. No target test labels are accessed by encoders.

External feature indices contain `labels` entries `{file,label}` in exactly
`filenames` order, image-level `label_counts`, and `source_label_counts`.
GRAZPEDWRI-DX matches `filestem` to PNG and maps `fracture_visible` 1 to 1,
blank to 0: 20,327 images (13,550 positive; 6,777 negative). FracAtlas
matches `image_id` to image and uses binary `fractured`: 4,083 images (719
positive; 3,364 negative). Two FracAtlas image IDs occur in both class
folders; byte-identical copies are deduplicated in lexical path order, and
CSV labels, not folder names, determine the target. Conflicting bytes fail.
MURA propagates train and valid `*_labeled_studies.csv` binary labels to all
images in each study across all body parts: 14,656 studies, 40,009 images
(16,403 positive; 23,606 negative). Missing, extra, duplicate or invalid
label entries fail rather than silently dropping images. Counts measured on
local extracted datasets; these external sets are not target labels.

Limited feature runs write under the full destination's `limit-N/` child,
not over complete arrays. Publication of full runs is still not atomic;
rerun interrupted extractions and check the index before consumption.
Nonuniform synthetic preprocessing regression comparisons allow max absolute
differences 0.7 (SKELEX, bicubic vs HF bilinear), 0.009 (MedSigLIP), and
0.08 (DINOv3); the fast HF resize can differ by a pixel rounding step even
where pool-image comparisons above happened to agree more closely.

`wsp-ml external-manifests` writes public `file,label` CSVs and `*.counts.json`
to `$ROOT/features/external-manifests/`. `wsp-ml audit-features` writes the
sanitized audit of the six real feature sets (no filenames/labels) to
`.runtime/l1-audit-features.json`.
