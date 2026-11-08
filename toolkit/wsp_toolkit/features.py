"""Batched activation capture from explicitly named modules."""
import torch


def extract(adapter, batches, modules=None, layers=None, device='cpu'):
    """Return CPU batches of adapter outputs and optional named-module activations.

    Module names are backbone.named_modules() paths; hooks are removed even on error.
    Hooks retain the complete raw output, including CLS/patch tokens when present.
    """
    modules = modules or []
    named = dict(adapter.backbone.named_modules())
    missing = set(modules) - named.keys()
    if missing:
        raise ValueError(f'unknown modules: {sorted(missing)}')
    captured = {}
    def cpu(value):
        if torch.is_tensor(value):
            return value.detach().cpu()
        if isinstance(value, (tuple, list)):
            return [cpu(v) for v in value]
        if isinstance(value, dict):
            return {k: cpu(v) for k, v in value.items()}
        return value
    handles = [named[name].register_forward_hook(lambda m, i, o, name=name: captured.__setitem__(name, cpu(o))) for name in modules]
    try:
        result = []
        with torch.no_grad():
            for batch in batches:
                captured.clear()
                output = cpu(adapter.forward(batch.to(device), layers=layers))
                result.append({'features': output, 'hooks': dict(captured)})
        return result
    finally:
        for handle in handles:
            handle.remove()


def layer_module_name(adapter, layer):
    """Module path of the one-based transformer block ``layer`` (usable as ``modules=[...]``)."""
    if not 1 <= layer <= adapter.num_layers:
        raise ValueError('layer must be one-based depth')
    names = dict(adapter.backbone.named_modules())
    for pattern in ('encoder.layer.{}', 'vision_model.encoder.layers.{}', 'layer.{}', 'encoder.layers.{}'):
        for prefix in ('', 'base_model.model.'):
            name = prefix + pattern.format(layer - 1)
            if name in names:
                return name
    raise ValueError('cannot locate transformer blocks; inspect adapter.backbone.named_modules()')


def extract_paths(adapter, paths, *, layers=None, batch_size=16, device='cpu', autocast=None, kinds=('pooled', 'cls', 'patch_mean'), patch_tokens=False):
    """Extract features for image files. Returns {'pooled': [N,D], 'cls': {layer: [N,D]}, 'patch_mean': {...}}
    as float32 numpy (plus 'patch_tokens': {layer: [N,P,D]} if requested; memory heavy -- use small chunks)."""
    import numpy as np
    from PIL import Image
    paths = list(paths)
    out = {}
    adapter.backbone.eval()
    for i in range(0, len(paths), batch_size):
        x = torch.stack([adapter.preprocess(Image.open(p)) for p in paths[i:i + batch_size]]).to(device)
        with torch.no_grad(), (torch.autocast(torch.device(device).type, dtype=autocast) if autocast else torch.autocast('cpu', enabled=False)):
            r = adapter.forward(x, layers=layers)
        for key in kinds + (('patch_tokens',) if patch_tokens else ()):
            v = r[key]
            if isinstance(v, dict):
                slot = out.setdefault(key, {})
                for layer, t in v.items():
                    slot.setdefault(layer, []).append(t.float().cpu().numpy())
            else:
                out.setdefault(key, []).append(v.float().cpu().numpy())
    for key, v in out.items():
        out[key] = {l: np.concatenate(a) for l, a in v.items()} if isinstance(v, dict) else np.concatenate(v)
    return out
