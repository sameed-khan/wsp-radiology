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
No external labels are processed by this feature extractor. `--limit` is a
smoke-test option and overwrites the same feature output as a full run.

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
