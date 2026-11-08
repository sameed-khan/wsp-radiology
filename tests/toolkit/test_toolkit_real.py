"""Real-encoder checks (need local model files; GPU for the heavier ones)."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'toolkit'))
from wsp_toolkit import encoders, load_encoder
from wsp_toolkit.features import extract, extract_paths, layer_module_name
from wsp_toolkit.training import Classifier, finetune_adapter, fit, predict
from wsp_ml import encoders as reference

MODELS = Path(os.environ.get('WSP_MODELS', '/home/skhanxx8/projects/wsp-radiology/models'))
pytestmark = pytest.mark.skipif(not (MODELS / 'skhoha/SKELEX').exists(), reason='model files unavailable')
cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA unavailable')


def images(tmp_path, n=3, size=(300, 260)):
    rng = np.random.default_rng(0)
    paths = []
    for i in range(n):
        p = tmp_path / f'{i}.png'
        Image.fromarray(rng.integers(0, 255, size, dtype=np.uint8)).save(p)
        paths.append(p)
    return paths


@cuda
@pytest.mark.parametrize('name', ['skelex', 'medsiglip', 'dinov3'])
def test_real_parity_with_wsp_ml_gpu(name, tmp_path, monkeypatch):
    monkeypatch.setenv('WSP_MODELS', str(MODELS))
    tk = load_encoder(name, 'cuda', torch.bfloat16)
    ref = reference.load_encoder(name, 'cuda', torch.bfloat16)
    paths = images(tmp_path, 2)
    x = torch.stack([tk.preprocess(Image.open(p)) for p in paths])
    assert torch.equal(x, torch.stack([ref.preprocess(Image.open(p)) for p in paths]))
    layers = [tk.num_layers // 3, tk.num_layers * 2 // 3, tk.num_layers]
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        a, b = tk.forward(x.cuda(), layers), ref.forward(x.cuda(), layers)
    assert torch.equal(a['pooled'], b['pooled'])
    for key in ('cls', 'patch_mean', 'patch_tokens'):
        assert a[key].keys() == b[key].keys() and all(torch.equal(a[key][i], b[key][i]) for i in a[key])
    n_patch = {'skelex': 196, 'dinov3': 196, 'medsiglip': 1024}[name]
    assert a['patch_tokens'][layers[0]].shape[1:] == (n_patch, tk.hidden_size)
    # hook at an arbitrary layer equals hidden state of that layer
    mod = layer_module_name(tk, layers[1])
    got = extract(tk, [x.cuda().to(torch.bfloat16)], modules=[mod], layers=[layers[1]], device='cuda')
    assert got[0]['hooks'][mod] is not None


def test_real_extract_paths_cpu_skelex(tmp_path, monkeypatch):
    monkeypatch.setenv('WSP_MODELS', str(MODELS))
    enc = load_encoder('skelex')
    paths = images(tmp_path, 3)
    r = extract_paths(enc, paths, layers=[8, 24], batch_size=2)
    assert r['pooled'].shape == (3, 1024) and r['cls'][8].shape == (3, 1024) and r['patch_mean'][24].shape == (3, 1024)
    r2 = extract_paths(enc, paths[:1], layers=[8], batch_size=1, patch_tokens=True)
    assert r2['patch_tokens'][8].shape == (1, 196, 1024)
    np.testing.assert_allclose(r2['cls'][8], r['cls'][8][:1], atol=1e-4)
    # deterministic, no token shuffling (mask_ratio 0)
    np.testing.assert_array_equal(r['pooled'], extract_paths(enc, paths, layers=[8, 24], batch_size=2)['pooled'])
    np.testing.assert_allclose(r['pooled'], extract_paths(enc, paths, layers=[8, 24], batch_size=3)['pooled'], atol=1e-4)


@cuda
@pytest.mark.parametrize('name,mode', [('skelex', 'lora'), ('skelex', 'full'), ('medsiglip', 'lora'), ('dinov3', 'lora')])
def test_real_finetune_with_provenance(name, mode, tmp_path, monkeypatch):
    monkeypatch.setenv('WSP_MODELS', str(MODELS))
    enc = load_encoder(name, 'cpu', torch.float32)
    finetune_adapter(enc, mode=mode, gradient_checkpointing=True)
    trainable = [n for n, p in enc.backbone.named_parameters() if p.requires_grad]
    assert trainable and (mode == 'full' or all('lora_' in n for n in trainable))
    model = Classifier(enc, torch.nn.Linear(enc.hidden_size, 2))
    paths = images(tmp_path, 4, (120, 100))
    x = torch.stack([enc.preprocess(Image.open(p)) for p in paths])
    y = torch.tensor([0, 1, 0, 1])
    torch.cuda.reset_peak_memory_stats()
    log = tmp_path / 'prov.jsonl'
    losses = fit(model, [(x[:2], y[:2]), (x[2:], y[2:])], steps=4, lr=1e-3, warmup=0.25, autocast=torch.bfloat16, device='cuda',
                 checkpoint_dir=tmp_path / 'ck', every=2, log_path=log, trainable_only=(mode == 'lora'))
    assert np.isfinite(losses).all()
    assert torch.cuda.max_memory_allocated() < 6 * 2**30
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(entries) == 2
    t = entries[1]['parents'][0]['tensors']
    changed = {k for k, v in t.items() if v['status'] == 'compared' and v['changed']}
    assert changed and (mode == 'full' or all('lora_' in k or k.startswith('head') for k in changed))
    assert predict(model, [x], device='cuda', autocast=torch.bfloat16).shape == (4, 2)
    del model, enc
    torch.cuda.empty_cache()
