"""Local-only encoder adapters; layer numbers are one-based transformer depths."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .data import ROOT

MODELS = {'skelex': 'skhoha/SKELEX', 'medsiglip': 'google/medsiglip-448', 'dinov3': 'facebook/dinov3-vitl16-pretrain-lvd1689m'}


def preprocess(image, name):
    if name not in MODELS:
        raise ValueError(name)
    size = 448 if name == 'medsiglip' else 224
    method = Image.Resampling.BILINEAR if name == 'dinov3' else Image.Resampling.BICUBIC
    image = image.convert('RGB').resize((size, size), resample=method)
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    mean = np.array((0.5, 0.5, 0.5) if name == 'medsiglip' else (0.485, 0.456, 0.406), dtype=np.float32)
    std = np.array((0.5, 0.5, 0.5) if name == 'medsiglip' else (0.229, 0.224, 0.225), dtype=np.float32)
    return torch.from_numpy(((pixels - mean) / std).transpose(2, 0, 1).copy())


class Adapter:
    def __init__(self, name, backbone):
        self.name, self.backbone = name, backbone
        config = backbone.config
        self.num_layers = config.num_hidden_layers
        self.hidden_size = config.hidden_size
        self.layer_indices_default = sorted({round(self.num_layers * x / 6) for x in (2, 3, 4, 5, 6)})

    def preprocess(self, image):
        return preprocess(image, self.name)

    def trainable_module(self):
        return self.backbone

    def forward(self, x, layers=None):
        layers = self.layer_indices_default if layers is None else layers
        if any(i < 1 or i > self.num_layers for i in layers):
            raise ValueError('layer indices must be one-based transformer depths')
        kwargs = {'output_hidden_states': True, 'return_dict': True}
        if self.name == 'skelex':
            n = (x.shape[-1] // self.backbone.config.patch_size) ** 2
            kwargs['noise'] = torch.arange(n, device=x.device, dtype=torch.float32).expand(x.shape[0], -1)
        out = self.backbone(pixel_values=x, **kwargs)
        result = {'pooled': out.pooler_output if self.name == 'medsiglip' else out.last_hidden_state[:, 0], 'cls': {}, 'patch_mean': {}, 'patch_tokens': {}}
        for layer in layers:
            tokens = out.last_hidden_state if layer == self.num_layers else out.hidden_states[layer]
            start = 0 if self.name == 'medsiglip' else (5 if self.name == 'dinov3' else 1)
            patches = tokens[:, start:]
            result['patch_tokens'][layer] = patches
            result['patch_mean'][layer] = patches.mean(dim=1)
            if self.name != 'medsiglip':
                result['cls'][layer] = tokens[:, 0]
            elif layer == self.num_layers:
                result['cls'][layer] = out.pooler_output
        return result


def model_path(name):
    return Path(os.environ.get('WSP_MODELS', str(ROOT / 'models'))) / MODELS[name]


def load_encoder(name, device, dtype, *, path=None):
    if name not in MODELS:
        raise ValueError(name)
    os.environ['HF_HUB_OFFLINE'] = '1'
    from transformers import ViTMAEModel, SiglipVisionModel, DINOv3ViTModel, SiglipConfig
    cls = {'skelex': ViTMAEModel, 'medsiglip': SiglipVisionModel, 'dinov3': DINOv3ViTModel}[name]
    path = model_path(name) if path is None else Path(path)
    kwargs = {}
    if name == 'medsiglip':
        kwargs['config'] = SiglipConfig.from_pretrained(path, local_files_only=True).vision_config
    model = cls.from_pretrained(path, local_files_only=True, dtype=dtype, **kwargs)
    if name == 'skelex':
        model.config.mask_ratio = 0.0
        model.embeddings.config.mask_ratio = 0.0
    model.to(device).eval()
    return Adapter(name, model)
