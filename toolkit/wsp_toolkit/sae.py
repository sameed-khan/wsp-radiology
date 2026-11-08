"""Top-k sparse autoencoder over arbitrary leading token dimensions."""
import torch
from torch import nn


class TopKSAE(nn.Module):
    def __init__(self, dim, dictionary_size, k):
        super().__init__()
        if not 0 < k <= dictionary_size:
            raise ValueError('invalid k')
        self.encoder = nn.Linear(dim, dictionary_size)
        self.decoder = nn.Linear(dictionary_size, dim)
        self.k = k

    def encode(self, x):
        a = self.encoder(x).relu()
        values, indices = a.topk(self.k, dim=-1)
        return torch.zeros_like(a).scatter(-1, indices, values)

    def forward(self, x):
        return self.decoder(self.encode(x))


def train_sae(model, batches, *, steps, lr=1e-4, device='cpu', checkpoint=None, every=1000, log_path=None):
    from pathlib import Path
    from .training import save_checkpoint
    model.to(device).train()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    iterator = iter(batches)
    losses, parent = [], None
    for step in range(1, steps + 1):
        try:
            x = next(iterator)
        except StopIteration:
            iterator = iter(batches)
            try:
                x = next(iterator)
            except StopIteration as exc:
                raise ValueError('batches exhausted or empty; supply a re-iterable') from exc
        x = x.to(device)
        opt.zero_grad(set_to_none=True)
        loss = (model(x) - x).square().mean()
        loss.backward()
        opt.step()
        losses.append(float(loss.detach()))
        if checkpoint and (step % every == 0 or step == steps):
            path = Path(checkpoint) / f'step-{step:06d}.safetensors'
            save_checkpoint(model, path, operation='gradient_training', details={'step': step, 'loss': losses[-1]}, parents=[parent] if parent else [], log_path=log_path)
            parent = path
    return losses


def inspect(model, x):
    with torch.no_grad():
        a = model.encode(x)
        flat = a.reshape(-1, a.shape[-1])
        return {'frequency': (flat > 0).float().mean(0), 'mean': flat.mean(0), 'decoder_directions': model.decoder.weight.detach().T}


def load_sae(path, dim, dictionary_size, k):
    """Rebuild a TopKSAE from a safetensors checkpoint written by train_sae/save_checkpoint."""
    from .training import load_checkpoint
    model = TopKSAE(dim, dictionary_size, k)
    load_checkpoint(model, path)
    return model.eval()


def mean_latents(model, x, chunk=4096):
    """Mean SAE activation per latent over leading dims of x ([..., dim]) -> [dictionary]."""
    model.eval()
    with torch.no_grad():
        flat = x.reshape(-1, x.shape[-1]).to(next(model.parameters()).device)
        total = sum(model.encode(c).sum(0) for c in flat.split(chunk))
    return (total / flat.shape[0]).cpu()
