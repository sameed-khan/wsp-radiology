"""Strict image-level labels for the three preregistered external datasets."""
import csv
import hashlib
from collections import Counter
from pathlib import Path

from PIL import Image, ImageFile

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp'}


def external_manifest(base, name):
    base = Path(base)
    root = base / name
    labels = {}

    def add(key, label):
        if key in labels:
            raise ValueError(f'duplicate label entry: {key}')
        if label not in ('0', '1'):
            raise ValueError(f'invalid binary label: {key}')
        labels[key] = int(label)

    if name in ('GRAZPEDWRI-DX', 'FracAtlas'):
        folder = root if name == 'GRAZPEDWRI-DX' else root / 'FracAtlas'
        with (folder / 'dataset.csv').open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                key = row['filestem'] if name == 'GRAZPEDWRI-DX' else row['image_id']
                label = row['fracture_visible'] if name == 'GRAZPEDWRI-DX' else row['fractured']
                add(key, label or '0' if name == 'GRAZPEDWRI-DX' else label)
        images = sorted(p for p in (folder / 'images').rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        if name == 'FracAtlas':
            unique = {}
            for image in images:
                if image.name in unique:
                    if hashlib.sha256(image.read_bytes()).digest() != hashlib.sha256(unique[image.name].read_bytes()).digest():
                        raise ValueError('conflicting duplicate image identifiers')
                    continue
                unique[image.name] = image
            images = list(unique.values())
        keys = [p.stem if name == 'GRAZPEDWRI-DX' else p.name for p in images]
    elif name == 'MURA':
        folder = root / 'MURA-v1.1'
        for split in ('train', 'valid'):
            with (folder / f'{split}_labeled_studies.csv').open(newline='') as f:
                for row in csv.reader(f):
                    if len(row) != 2:
                        raise ValueError('invalid MURA study row')
                    study = Path(row[0])
                    if study.is_absolute() or '..' in study.parts or study.parts[:2] != ('MURA-v1.1', split):
                        raise ValueError('invalid MURA study path')
                    add(study.as_posix(), row[1])
        images = sorted(p for split in ('train', 'valid') for p in (folder / split).rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        keys = [p.parent.relative_to(root).as_posix() for p in images]
    else:
        raise ValueError('invalid external dataset')
    # Match training's permissive JPEG decoding, but force full pixel decoding.
    # AppleDouble sidecars are never images even when named *.png.
    kept_images, kept_keys = [], []
    skipped_sidecar = skipped_undecodable = 0
    previous = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    try:
        for image, key in zip(images, keys):
            if image.name.startswith('._'):
                skipped_sidecar += 1
                continue
            try:
                with Image.open(image) as im:
                    im.load()
                    im.convert('RGB')
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                skipped_undecodable += 1
                continue
            kept_images.append(image)
            kept_keys.append(key)
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = previous
    images, keys = kept_images, kept_keys
    if not images or set(keys) != set(labels):
        raise ValueError('external images and label entries do not match')
    if name != 'MURA' and len(keys) != len(set(keys)):
        raise ValueError('duplicate image identifiers')
    entries = [{'file': str(p.relative_to(base)), 'label': labels[k]} for p, k in zip(images, keys)]
    counts = Counter(item['label'] for item in entries)
    return images, entries, {'images': len(entries), 'negative': counts[0], 'positive': counts[1], 'label_entries': len(labels),
                             'skipped_appledouble': skipped_sidecar, 'skipped_undecodable': skipped_undecodable}


def write_manifests(base=None, out=None):
    """Write public image/label manifests (file,label CSV + counts JSON) per external dataset."""
    import json
    from .data import ROOT
    base = Path(base) if base else ROOT / 'data/external/extracted'
    out = Path(out) if out else ROOT / 'features/external-manifests'
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in ('GRAZPEDWRI-DX', 'FracAtlas', 'MURA'):
        _, entries, counts = external_manifest(base, name)
        text = 'file,label\n' + ''.join(f"{e['file']},{e['label']}\n" for e in entries)
        (out / f'{name}.csv').write_text(text)
        (out / f'{name}.counts.json').write_text(json.dumps(counts, indent=2) + '\n')
        summary[name] = counts
    return summary
