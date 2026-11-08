"""Reproducible PIL-based procedural interventions."""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageOps


def procedural(image, *, crop=None, contrast=1., gamma=1., flip=False, rotation=0., marker=None, noise=0., seed=0):
    image = image.convert('RGB')
    if crop is not None:
        image = image.crop(crop)
    image = ImageEnhance.Contrast(image).enhance(contrast)
    if gamma <= 0 or noise < 0:
        raise ValueError('gamma must be positive and noise nonnegative')
    image = image.point([round(255 * (i / 255) ** gamma) for i in range(256)] * 3)
    if flip:
        image = ImageOps.mirror(image)
    if rotation:
        image = image.rotate(rotation)
    if marker is not None:
        image = image.copy()
        ImageDraw.Draw(image).rectangle(marker, fill='white')
    if noise:
        arr = np.asarray(image, dtype=np.float32)
        arr += np.random.default_rng(seed).normal(0, noise, arr.shape)
        image = Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))
    return image


def occlude(image, box, fill=0):
    image = image.copy()
    ImageDraw.Draw(image).rectangle(box, fill=fill)
    return image


def probe(image, boxes, score, *, mode='occlusion'):
    """Score each crop or occlusion with caller-supplied image scoring function."""
    if mode not in ('crop', 'occlusion'):
        raise ValueError(mode)
    return [(box, score(image.crop(box) if mode == 'crop' else occlude(image, box))) for box in boxes]
