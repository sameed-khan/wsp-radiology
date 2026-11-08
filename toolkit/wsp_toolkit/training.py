"""Linear-probe / LoRA / full fine-tune helpers with safetensors checkpointing and provenance."""
import math
from contextlib import nullcontext
from pathlib import Path

import torch
from torch import nn
from safetensors.torch import load_file, save_file

from .provenance import log_checkpoint

# peft regexes (full match on module path) for attention q,k,v,o and MLP linears, per encoder.
LORA_TARGETS = {
    'skelex': r'encoder\.layer\.\d+\.(attention\.attention\.(query|key|value)|attention\.output\.dense|intermediate\.dense|output\.dense)',
    'medsiglip': r'vision_model\.encoder\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|out_proj)|mlp\.(fc1|fc2))',
    'dinov3': r'layer\.\d+\.(attention\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(up_proj|down_proj))',
}


def save_checkpoint(model, path, *, operation='unknown', details=None, parents=(), log_path=None, trainable_only=False):
    """Save ``model.state_dict()`` as safetensors and log it. Refuses to overwrite a parent."""
    path = Path(path)
    if any(path.resolve() == Path(p).resolve() for p in parents):
        raise ValueError('checkpoint cannot overwrite a parent')
    path.parent.mkdir(parents=True, exist_ok=True)
    trainable = {n for n, p in model.named_parameters() if p.requires_grad}
    state = {k: v.detach().cpu().contiguous().clone() for k, v in model.state_dict().items() if not trainable_only or k in trainable}
    tmp = path.with_name(path.name + '.tmp')
    save_file(state, str(tmp))
    tmp.replace(path)
    return log_checkpoint(path, parents, operation, details or {}, log_path)


def load_checkpoint(model, path, strict=True):
    return model.load_state_dict(load_file(str(path), device='cpu'), strict=strict)


def linear_probe(dim, classes=2):
    return nn.Linear(dim, classes)


class Classifier(nn.Module):
    """Encoder adapter + head on the pooled feature. Build it *after* ``finetune_adapter``."""

    def __init__(self, adapter, head):
        super().__init__()
        self.adapter = adapter  # not a Module; keep backbone registered for state_dict/params
        self.backbone = adapter.backbone
        self.head = head

    def forward(self, x):
        return self.head(self.adapter.forward(x, layers=[])['pooled'])


def finetune_adapter(adapter, *, mode='full', target_modules=None, rank=16, alpha=32, dropout=0.1, gradient_checkpointing=False):
    """Prepare ``adapter.backbone`` for training. mode='full' unfreezes everything; mode='lora' wraps with peft
    (default targets: attention q,k,v,o + MLP for the three study encoders)."""
    backbone = adapter.backbone
    if mode == 'full':
        for p in backbone.parameters():
            p.requires_grad_(True)
    elif mode == 'lora':
        from peft import LoraConfig, get_peft_model
        target_modules = target_modules or LORA_TARGETS.get(adapter.name)
        if not target_modules:
            raise ValueError('supply target_modules')
        if gradient_checkpointing:
            backbone.enable_input_require_grads()
        adapter.backbone = get_peft_model(backbone, LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=dropout, target_modules=target_modules))
    else:
        raise ValueError(mode)
    if gradient_checkpointing:
        (adapter.backbone.gradient_checkpointing_enable if hasattr(adapter.backbone, 'gradient_checkpointing_enable') else adapter.backbone.base_model.gradient_checkpointing_enable)()
    adapter.backbone.train()
    return adapter


def _schedule(step, steps, warmup):
    w = max(1, int(round(steps * warmup)))
    if step < w:
        return (step + 1) / w
    return 0.5 * (1 + math.cos(math.pi * (step - w) / max(1, steps - w)))


def fit(model, batches, *, steps, lr=1e-3, weight_decay=0.0, warmup=0.0, param_groups=None, accumulate=1,
        class_weights=None, autocast=None, grad_clip=None, device='cpu', checkpoint_dir=None, every=100,
        log_path=None, forward=None, trainable_only=False):
    """Supervised fit on a re-iterable of (inputs, integer labels). Cosine schedule with linear warmup
    (fraction ``warmup``), optional gradient accumulation, class-weighted CE, ``autocast`` dtype (e.g.
    torch.bfloat16), periodic checkpoints logged to provenance. ``forward(model, x)`` overrides model(x).
    ``param_groups`` = [{'params': ..., 'lr': ...}] for per-group learning rates. Returns the loss list
    (one per optimizer step)."""
    model.to(device).train()
    groups = param_groups or [{'params': [p for p in model.parameters() if p.requires_grad]}]
    for g in groups:
        g.setdefault('lr', lr)
        g['base_lr'] = g['lr']
    opt = torch.optim.AdamW(groups, lr=lr, weight_decay=weight_decay)
    weight = None if class_weights is None else torch.as_tensor(class_weights, dtype=torch.float32, device=device)
    iterator = iter(batches)
    losses, parent = [], None

    def nxt():
        nonlocal iterator
        try:
            return next(iterator)
        except StopIteration:
            iterator = iter(batches)
            try:
                return next(iterator)
            except StopIteration as exc:
                raise ValueError('batches exhausted or empty; supply a re-iterable') from exc

    for step in range(steps):
        scale = _schedule(step, steps, warmup)
        for g in opt.param_groups:
            g['lr'] = g['base_lr'] * scale
        opt.zero_grad(set_to_none=True)
        total = 0.0
        for _ in range(accumulate):
            x, y = nxt()
            ctx = torch.autocast(torch.device(device).type, dtype=autocast) if autocast else nullcontext()
            with ctx:
                logits = forward(model, x.to(device)) if forward else model(x.to(device))
            loss = nn.functional.cross_entropy(logits.float(), y.to(device).long(), weight=weight, reduction='sum') / (len(y) * accumulate)
            loss.backward()
            total += float(loss.detach())
        if grad_clip:
            nn.utils.clip_grad_norm_([p for g in opt.param_groups for p in g['params']], grad_clip)
        opt.step()
        losses.append(total)
        n = step + 1
        if checkpoint_dir and (n % every == 0 or n == steps):
            path = Path(checkpoint_dir) / f'step-{n:06d}.safetensors'
            save_checkpoint(model, path, operation='gradient_training', details={'step': n, 'loss': total, 'lr': lr},
                            parents=[parent] if parent else [], log_path=log_path, trainable_only=trainable_only)
            parent = path
    return losses


@torch.no_grad()
def predict(model, batches, *, device='cpu', autocast=None, forward=None):
    """Softmax probabilities for an iterable of input batches (or (x, y) pairs)."""
    model.to(device).eval()
    out = []
    for b in batches:
        x = b[0] if isinstance(b, (tuple, list)) else b
        ctx = torch.autocast(torch.device(device).type, dtype=autocast) if autocast else nullcontext()
        with ctx:
            logits = forward(model, x.to(device)) if forward else model(x.to(device))
        out.append(logits.float().softmax(-1).cpu())
    return torch.cat(out)
