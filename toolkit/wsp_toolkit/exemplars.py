"""Rank image or patch vectors and write labeled montages."""
import math
import torch
from PIL import Image, ImageDraw, ImageOps


def search(features, direction=None, *, sae=None, latent=None, k=10):
    """features: [images, dim] or [images, patches, dim]; return (score,image,patch)."""
    x = torch.as_tensor(features)
    if sae is not None:
        if latent is None:
            raise ValueError('latent required')
        with torch.no_grad():
            p = next(sae.parameters())
            x = x.to(p.device, p.dtype)
            flat = x.reshape(-1, x.shape[-1])
            scores = torch.cat([sae.encode(c)[:, latent] for c in flat.split(4096)]).reshape(x.shape[:-1]).cpu()
    else:
        scores = (x @ torch.as_tensor(direction, device=x.device, dtype=x.dtype)).cpu()
    if scores.ndim not in (1, 2) or k < 1:
        raise ValueError('expected image or patch scores and positive k')
    values, indices = torch.topk(scores.flatten(), min(k, scores.numel()))
    patches = scores.shape[1] if scores.ndim == 2 else 1
    return [(float(v), int(i) // patches, int(i) % patches if scores.ndim == 2 else None) for v, i in zip(values, indices)]


def montage(images, matches, path, *, columns=4, tile=160, grid=None):
    """grid=(rows, columns) crops patch-ranked exemplars to their source patch."""
    if columns < 1 or not matches:
        raise ValueError('nonempty matches and positive columns required')
    canvas = Image.new('RGB', (columns * tile, math.ceil(len(matches) / columns) * (tile + 20)), 'white')
    draw = ImageDraw.Draw(canvas)
    for n, (score, idx, patch) in enumerate(matches):
        image = images[idx]
        if patch is not None and grid is not None:
            rows, cols = grid
            if patch >= rows * cols:
                raise ValueError('patch outside grid')
            x, y = patch % cols, patch // cols
            image = image.crop((x * image.width // cols, y * image.height // rows, (x+1)*image.width//cols, (y+1)*image.height//rows))
        x, y = n % columns * tile, n // columns * (tile + 20)
        canvas.paste(ImageOps.fit(image.convert('RGB'), (tile, tile)), (x, y))
        draw.text((x, y + tile), f'{idx}:{patch} {score:.3g}', fill='black')
    canvas.save(path)
