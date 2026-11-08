import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'toolkit'))
from wsp_toolkit import encoders
from wsp_ml import encoders as reference
from wsp_toolkit.exemplars import search, montage
from wsp_toolkit.features import extract
from wsp_toolkit.probes import procedural, probe
from wsp_toolkit.sae import TopKSAE, train_sae, inspect
from wsp_toolkit.training import fit, linear_probe
from wsp_toolkit.provenance import log_checkpoint, sha256
from wsp_toolkit.training import save_checkpoint, load_checkpoint, Classifier, predict


class Backbone(torch.nn.Module):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.config = SimpleNamespace(num_hidden_layers=2, hidden_size=4, patch_size=2)
        self.layer = torch.nn.Identity()

    def forward(self, pixel_values, **kwargs):
        n = {'skelex': 5, 'dinov3': 9, 'medsiglip': 4}[self.name]
        tokens = self.layer(torch.arange(n*4, device=pixel_values.device).reshape(1,n,4).float().expand(pixel_values.shape[0],-1,-1))
        return SimpleNamespace(last_hidden_state=tokens, hidden_states=(tokens, tokens+1, tokens), pooler_output=tokens.mean(1))


@pytest.mark.parametrize('name', ['skelex', 'medsiglip', 'dinov3'])
def test_adapter_parity(name):
    image = Image.fromarray(np.arange(13*17, dtype=np.uint8).reshape(13,17))
    assert torch.equal(encoders.preprocess(image, name), reference.preprocess(image, name))
    a = encoders.Adapter(name, Backbone(name))
    b = reference.Adapter(name, Backbone(name))
    x = torch.zeros(2,3,4,4)
    for layer in [[], [1, 2], None]:
        left, right = a.forward(x, layer), b.forward(x, layer)
        assert torch.equal(left['pooled'], right['pooled'])
        for key in ('cls', 'patch_mean', 'patch_tokens'):
            assert left[key].keys() == right[key].keys()
            assert all(torch.equal(left[key][i], right[key][i]) for i in left[key])
    with pytest.raises(ValueError):
        a.forward(x, [3])
    result = extract(a, [x], modules=['layer'], layers=[1])
    assert result[0]['hooks']['layer'].shape[0] == 2
    assert not a.backbone.layer._forward_hooks


def test_interpret_and_train(tmp_path):
    image = Image.new('RGB', (16, 16), 'gray')
    assert procedural(image, noise=3, seed=2).tobytes() == procedural(image, noise=3, seed=2).tobytes()
    assert len(probe(image, [(0,0,4,4)], lambda im: im.size, mode='crop')) == 1
    matches = search(torch.randn(2, 4, 3), torch.ones(3), k=3)
    montage([image,image], matches, tmp_path/'montage.png', grid=(2,2))
    sae = TopKSAE(3, 12, 2)
    log = tmp_path/'sae.jsonl'
    train_sae(sae, [torch.randn(8,3)], steps=2, checkpoint=tmp_path/'sae', every=1, log_path=log)
    assert (sae.encode(torch.randn(8,3)) > 0).sum(-1).max() <= 2
    assert inspect(sae, torch.randn(8,3))['frequency'].shape == (12,)
    entries = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(entries) == 2 and entries[1]['parents'][0]['tensors']
    head = linear_probe(3)
    fit(head, [(torch.randn(8,3), torch.randint(0,2,(8,)))], steps=2, checkpoint_dir=tmp_path/'head', every=1, log_path=tmp_path/'head.jsonl')
    with pytest.raises(ValueError):
        log_checkpoint(tmp_path/'head/step-000001.safetensors', [], 'other', {}, tmp_path/'bad')


def test_source_parity_with_wsp_ml():
    import inspect
    assert inspect.getsource(encoders.preprocess) == inspect.getsource(reference.preprocess)
    assert inspect.getsource(encoders.Adapter) == inspect.getsource(reference.Adapter)
    assert encoders.MODELS == reference.MODELS


def test_standalone_imports():
    import subprocess
    code = "import sys; sys.path.insert(0, %r); import wsp_toolkit, wsp_toolkit.sae, wsp_toolkit.training, wsp_toolkit.features, wsp_toolkit.exemplars, wsp_toolkit.probes; bad=[m for m in sys.modules if m.split('.')[0] in ('wsp_ml','wsp_prep','wsp_arms','wsp_eval')]; assert not bad, bad" % str(Path(encoders.__file__).parents[1])
    subprocess.run([sys.executable, '-c', code], check=True)
    env = {k: v for k, v in os.environ.items() if k != 'WSP_MODELS'}
    out = subprocess.run([sys.executable, '-c', "import sys; sys.path.insert(0, %r); from wsp_toolkit import load_encoder\ntry: load_encoder('skelex')\nexcept Exception as e: print(e)" % str(Path(encoders.__file__).parents[1])], env=env, capture_output=True, text=True)
    assert '/inputs/models/skhoha/SKELEX' in out.stdout


def test_model_root_configurable(tmp_path, monkeypatch):
    monkeypatch.delenv('WSP_MODELS', raising=False)
    with pytest.raises(Exception) as err:
        encoders.load_encoder('skelex', model_root=tmp_path)
    assert str(tmp_path) in str(err.value)
    with pytest.raises(ValueError):
        encoders.load_encoder('nope')


def test_provenance_changes_and_robustness(tmp_path):
    from safetensors.torch import save_file
    log = tmp_path / 'p.jsonl'
    a, b = tmp_path / 'a.safetensors', tmp_path / 'b.safetensors'
    save_file({'w': torch.zeros(4, 4), 'i': torch.arange(3), 'gone': torch.ones(2), 'h': torch.zeros(2, dtype=torch.bfloat16)}, str(a))
    save_file({'w': torch.eye(4), 'i': torch.arange(3), 'new': torch.ones(1), 'h': torch.ones(2, dtype=torch.bfloat16)}, str(b))
    e = log_checkpoint(b, [a], 'direct_edit', {'loss': float('nan'), 'x': torch.tensor(1.5)}, log)
    t = e['parents'][0]['tensors']
    assert e['sha256'] == sha256(b) and e['parents'][0]['sha256'] == sha256(a)
    assert t['w']['changed'] == 4 and t['w']['max_abs_delta'] == 1.0 and t['i']['changed'] == 0
    assert t['gone']['status'] == 'removed' and t['new']['status'] == 'added' and t['h']['changed'] == 2
    assert e['details'] == {'loss': 'nan', 'x': 1.5}
    assert json.loads(log.read_text().splitlines()[0])['operation'] == 'direct_edit'
    for op in ('gradient_training', 'closed_form_fit', 'composition', 'direct_edit', 'mixed', 'unknown'):
        log_checkpoint(b, [], op, {}, log)
    with pytest.raises(FileNotFoundError):
        log_checkpoint(b, [tmp_path / 'missing'], 'mixed', {}, log)
    with pytest.raises(ValueError):
        save_checkpoint(torch.nn.Linear(1, 1), b, parents=[b], log_path=log)


def test_fit_options_and_resume(tmp_path):
    torch.manual_seed(0)
    x = torch.randn(64, 5); y = (x[:, 0] > 0).long()
    head = linear_probe(5)
    batches = [(x[i:i+16], y[i:i+16]) for i in range(0, 64, 16)]
    losses = fit(head, batches, steps=60, lr=0.1, warmup=0.05, accumulate=2, class_weights=[1., 2.], grad_clip=1.0,
                 checkpoint_dir=tmp_path, every=30, log_path=tmp_path/'l.jsonl')
    assert len(losses) == 60 and losses[-1] < losses[0]
    ck = sorted(tmp_path.glob('*.safetensors'))
    assert [c.name for c in ck] == ['step-000030.safetensors', 'step-000060.safetensors']
    other = linear_probe(5); load_checkpoint(other, ck[-1])
    assert torch.equal(other.weight, head.weight)
    assert (predict(other, [x]).argmax(1) == y).float().mean() > 0.8
    entries = [json.loads(l) for l in (tmp_path/'l.jsonl').read_text().splitlines()]
    assert entries[1]['parents'][0]['sha256'] == entries[0]['sha256']
    assert entries[1]['operation'] == 'gradient_training'


def test_sae_search(tmp_path):
    sae = TopKSAE(3, 12, 2)
    patches = torch.randn(4, 6, 3)
    m = search(patches, sae=sae, latent=5, k=3)
    scores = sae.encode(patches)[..., 5]
    assert [round(s, 5) for s, _, _ in m] == [round(float(v), 5) for v in scores.flatten().topk(3).values]
    from wsp_toolkit.sae import load_sae, mean_latents
    train_sae(sae, [torch.randn(8, 3)], steps=1, checkpoint=tmp_path, every=1, log_path=tmp_path/'l.jsonl')
    again = load_sae(tmp_path/'step-000001.safetensors', 3, 12, 2)
    z = torch.randn(5, 3)
    assert torch.equal(again(z), sae(z.double().float()).detach()) or torch.allclose(again(z), sae(z), atol=1e-6)
    assert mean_latents(again, torch.randn(2, 5, 3)).shape == (12,)


def test_gpu_smoke():
    if not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    model = TopKSAE(16, 64, 4)
    losses = train_sae(model, [torch.randn(16,16, device='cuda')], steps=2, device='cuda')
    assert len(losses) == 2 and np.isfinite(losses).all()
