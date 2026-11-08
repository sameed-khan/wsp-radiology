# WSP toolkit (`wsp_toolkit`)

Installed in the agent image (`pip install ./toolkit` elsewhere). Standalone: no target data/labels, no dependency on other repo packages.
Encoders load offline from `/inputs/models` (override: `WSP_MODELS=...` or `load_encoder(..., model_root=...)`).
Encoders: `skelex`, `medsiglip`, `dinov3`. Layer numbers are **one-based transformer depths** (1..`enc.num_layers`).
`enc.forward(x, layers)` -> `{"pooled", "cls"{layer}, "patch_mean"{layer}, "patch_tokens"{layer}}` (DINOv3 registers excluded; MedSigLIP has no CLS: `cls` holds only the final pooled output). SKELEX runs with mask_ratio 0, no shuffling.
It is a convenience; you may write your own code.

## Features and hooks
```python
import torch; from PIL import Image
from wsp_toolkit import load_encoder
from wsp_toolkit.features import extract_paths, extract, layer_module_name
enc = load_encoder('skelex', device='cuda', dtype=torch.bfloat16)
f = extract_paths(enc, paths, layers=[8, 16, 24], batch_size=16, device='cuda', autocast=torch.bfloat16)   # numpy: f['pooled'], f['cls'][16], f['patch_mean'][16]
t = extract_paths(enc, paths[:32], layers=[16], device='cuda', kinds=(), patch_tokens=True)['patch_tokens'][16]  # [N, patches, D]; memory heavy: chunk
# forward hook on any module (names: enc.backbone.named_modules(); layer_module_name(enc, 16) gives block 16):
x = torch.stack([enc.preprocess(Image.open(p)) for p in paths[:4]]).cuda().bfloat16()
out = extract(enc, [x], modules=[layer_module_name(enc, 16)], layers=[16], device='cuda')[0]['hooks']
```
## Exemplars, probes
```python
from wsp_toolkit.exemplars import search, montage
m = search(t, direction=torch.randn(1024), k=12)            # [(score, image_idx, patch_idx)]; also search(t, sae=sae, latent=17)
montage([Image.open(p) for p in paths[:32]], m, 'montage.png', grid=(14, 14))   # patch matches are cropped to their patch (SKELEX/DINOv3 14x14; MedSigLIP 32x32)
from wsp_toolkit.probes import procedural, occlude, probe
img2 = procedural(img, crop=(0,0,200,200), contrast=1.3, gamma=0.8, flip=True, rotation=5, marker=(5,5,25,25), noise=3, seed=0)
probe(img, [(0,0,80,80), (80,0,160,80)], score_fn, mode='occlusion')   # or mode='crop'; score_fn(PIL)->float
```
## Top-k SAE
Precomputed pool-only SAEs and pool mean latents are available at `/workspace/provided/sae/`; see its README for loading and normalization.
```python
from wsp_toolkit.sae import TopKSAE, train_sae, inspect, mean_latents, load_sae
sae = TopKSAE(dim=1024, dictionary_size=8192, k=32)
train_sae(sae, re_iterable_of_[B,D]_batches, steps=20000, lr=1e-4, device='cuda', checkpoint='ck/sae', every=2000)  # stream batches; do not hold all tokens
stats = inspect(sae, tokens)          # frequency, mean, decoder_directions
sae = load_sae('ck/sae/step-020000.safetensors', 1024, 8192, 32)
```
## Linear probe, LoRA, full fine-tune
```python
from wsp_toolkit.training import linear_probe, fit, finetune_adapter, Classifier, predict, save_checkpoint, load_checkpoint
head = linear_probe(1024); fit(head, [(feats, labels)], steps=200, lr=1e-2, checkpoint_dir='ck/head')
finetune_adapter(enc, mode='lora', rank=16, alpha=32, dropout=0.1, gradient_checkpointing=True)  # or mode='full'; default LoRA targets = attention q,k,v,o + MLP
model = Classifier(enc, torch.nn.Linear(enc.hidden_size, 2))   # build AFTER finetune_adapter; pooled feature -> head
fit(model, loader, steps=500, lr=2e-4, weight_decay=0.05, warmup=0.05, accumulate=2, class_weights=[1, 3], autocast=torch.bfloat16,
    device='cuda', checkpoint_dir='ck/ft', every=100, trainable_only=True,
    param_groups=[{'params': head.parameters(), 'lr': 1e-3}, {'params': [p for p in enc.backbone.parameters() if p.requires_grad], 'lr': 2e-4}])
probs = predict(model, batches, device='cuda', autocast=torch.bfloat16)
```
`loader` must be re-iterable yielding `(x, int_labels)`. Build the encoder in fp32 for training (autocast does bf16). Checkpoints = safetensors model state (no optimizer state); `load_checkpoint(model, path)`. `trainable_only=True` saves only trainable tensors (LoRA + head): reload on top of a freshly built identical model with `strict=False`.
## Provenance (self-reported, supplementary)
`fit`/`train_sae`/`save_checkpoint` log automatically. For anything else:
```python
from wsp_toolkit.provenance import log_checkpoint
log_checkpoint('out.safetensors', parents=['a.safetensors', 'b.safetensors'], operation='composition', details={'alpha': 0.5})
```
`operation` is exactly one of `gradient_training`, `closed_form_fit`, `composition`, `direct_edit`, `mixed`, `unknown`. Appends to `/workspace/output/provenance.jsonl` (override `log_path=` / `WSP_PROVENANCE_LOG`) with the checkpoint SHA-256 and, per parent, its SHA-256 and a per-tensor change summary (added/removed/shape change, #changed, max/mean |delta|, relative change). Parents and checkpoints must be safetensors files; keep parents so the lineage chain is retained.
