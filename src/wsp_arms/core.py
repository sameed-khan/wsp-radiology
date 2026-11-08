"""Shared framework: paths, allocations, features, grouped CV, Youden threshold, run records."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_ROOT = '/home/skhanxx8/projects/wsp-radiology'
ENCODERS = ('skelex', 'medsiglip', 'dinov3')
KS = ('10', '20', '50', '100', '250', 'all')
RS = (1, 2, 3, 4, 5)
C_GRID = (0.01, 0.1, 1.0, 10.0)
N_TEST = 1593
RECORD_VERSION = 1


@dataclass(frozen=True)
class Paths:
    root: Path

    @classmethod
    def default(cls):
        return cls(Path(os.environ.get('WSP_ROOT', DEFAULT_ROOT)))

    @property
    def private(self):
        return self.root / 'data/locked/private'

    def allocation_dir(self, k, r):
        return self.private / 'allocations' / f'k{k}' / f'r{r}'

    def pool_features(self, enc):
        return self.root / 'features' / enc / 'pool'

    def test_features(self, enc):
        return self.private / 'features' / enc / 'test'

    def test_png_dir(self):
        return self.private / 'test-png'

    def run_dir(self, arm, enc, k, r):
        return self.private / 'runs/baselines' / arm / enc / f'k{k}' / f'r{r}'


# ---------------------------------------------------------------- io helpers
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(items):
    return hashlib.sha256('\n'.join(items).encode()).hexdigest()


def private_mkdir(path, stop):
    """mkdir -p with mode 0700 for every created level up to and including `stop`."""
    path = Path(path)
    todo = []
    cur = path
    while not cur.exists():
        todo.append(cur)
        cur = cur.parent
    for d in reversed(todo):
        d.mkdir(mode=0o700)
        os.chmod(d, 0o700)


def write_private_atomic(path, data, stop=None):
    path = Path(path)
    private_mkdir(path.parent, stop)
    raw = data if isinstance(data, bytes) else data.encode()
    tmp = path.with_name(path.name + f'.tmp{os.getpid()}')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def code_revision():
    here = Path(__file__).resolve().parent
    try:
        rev = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=here, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', str(here)], cwd=here, text=True, stderr=subprocess.DEVNULL).strip())
        return {'git_rev': rev, 'wsp_arms_dirty': dirty}
    except Exception:
        return {'git_rev': 'unknown', 'wsp_arms_dirty': None}


# ---------------------------------------------------------------- allocations
@dataclass
class Allocation:
    k: str
    r: int
    seed: int
    patient_ids: list
    images: list          # file names (sorted)
    patients: list        # patient id per image
    labels: np.ndarray    # int 0/1 per image
    sha256: str


def parse_k(k):
    k = str(k)
    if k == 'all':
        return 'all'
    if k == '0' or not k.isdigit():
        raise ValueError(f'invalid k: {k}')
    return k


def load_allocation(paths, k, r):
    k = parse_k(k)
    p = paths.allocation_dir(k, r) / 'allocation.json'
    d = json.loads(p.read_text())
    imgs = sorted(d['images'], key=lambda x: x['anonymous_filename'])
    return Allocation(
        k=k, r=int(r), seed=int(d['seed']), patient_ids=list(d['patient_ids']),
        images=[x['anonymous_filename'] for x in imgs], patients=[x['patient_id'] for x in imgs],
        labels=np.array([int(x['label']) for x in imgs], dtype=np.int64), sha256=sha256_file(p))


# ---------------------------------------------------------------- features
@dataclass
class Features:
    names: list
    X: np.ndarray
    index_sha256: str
    pooled_sha256: str

    def rows(self, names):
        pos = {n: i for i, n in enumerate(self.names)}
        return np.array([pos[n] for n in names], dtype=np.int64)


def load_features(directory, name='pooled'):
    directory = Path(directory)
    idx = directory / 'index.json'
    names = json.loads(idx.read_text())['filenames']
    X = np.load(directory / f'{name}.npy').astype(np.float32, copy=False)
    if len(names) != len(X):
        raise ValueError(f'{directory}: index/features length mismatch')
    return Features(names, X, sha256_file(idx), sha256_file(directory / f'{name}.npy'))


def load_test_features(paths, enc, name='pooled'):
    """Test features; checks the index equals the test-png *file listing* (names only, no manifest/labels)."""
    f = load_features(paths.test_features(enc), name)
    listing = sorted(p.name for p in paths.test_png_dir().glob('*.png'))
    if sorted(f.names) != listing or len(listing) != N_TEST:
        raise ValueError(f'test feature index does not match {N_TEST} test PNGs')
    return f


# ---------------------------------------------------------------- grouped CV
def make_folds(patients, labels, seed):
    """Patient-grouped folds -> list of arrays of held-out image indices.

    LOPO if <= 20 patients, else 5-fold; 5-fold assigns patients (shuffled by seed,
    stratified by patient label, round-robin) so every fold has similar class mix.
    """
    patients = np.asarray(patients)
    labels = np.asarray(labels)
    uniq = sorted(set(patients.tolist()))
    plabel = {p: int(labels[patients == p][0]) for p in uniq}
    if len(uniq) <= 20:
        groups = [[p] for p in uniq]
    else:
        rng = np.random.default_rng(seed % (2**32) + 12345)
        groups = [[] for _ in range(5)]
        j = 0
        for cls in (0, 1):
            ps = [p for p in uniq if plabel[p] == cls]
            ps = [ps[i] for i in rng.permutation(len(ps))]
            for p in ps:
                groups[j % 5].append(p)
                j += 1
    return [np.where(np.isin(patients, g))[0] for g in groups if g]


def auroc(y, p):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    if len(set(y.tolist())) < 2:
        return None
    return float(roc_auc_score(y, p))


def logloss(y, p):
    p = np.clip(np.asarray(p, dtype=np.float64), 1e-7, 1 - 1e-7)
    y = np.asarray(y)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def youden_threshold(y, p):
    """Threshold maximizing J=sens+spec-1 for rule `p >= t`; ties -> midpoint of the
    first maximal contiguous interval of equivalent thresholds. Returns (t, J).
    Requires both classes."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=np.float64)
    if y.min() == y.max():
        raise ValueError('youden needs both classes')
    s = np.unique(p)
    npos, nneg = int(y.sum()), int((1 - y).sum())
    # J for rule p >= s_i  (i = 0..n-1); rule "all negative" (t > s_max) has J = 0.
    ps = np.sort(p[y == 1]); ns = np.sort(p[y == 0])
    tpr = 1 - np.searchsorted(ps, s, side='left') / npos
    fpr = 1 - np.searchsorted(ns, s, side='left') / nneg
    J = tpr - fpr
    best = J.max()
    ok = np.isclose(J, best, rtol=0, atol=1e-12)
    first = int(np.argmax(ok))
    last = first
    while last + 1 < len(s) and ok[last + 1]:
        last += 1
    # thresholds t in (s[first-1], s[last]] give the optimal rule
    lo = s[first - 1] if first > 0 else s[first]
    hi = s[last]
    return float((lo + hi) / 2), float(best)


def threshold_from_oof(y, p):
    """(threshold, method, oof_youden_J). Falls back to 0.5 when OOF lacks both classes."""
    y = np.asarray(y)
    if len(set(y.tolist())) < 2 or not np.all(np.isfinite(p)):
        return 0.5, 'fixed_0.5_single_class', None
    t, j = youden_threshold(y, p)
    return t, 'youden_oof_grouped', j


# ---------------------------------------------------------------- run records
def write_predictions(path, names, probs, stop=None):
    probs = np.asarray(probs, dtype=np.float64)
    if len(names) != N_TEST or probs.shape != (N_TEST,) or not np.all(np.isfinite(probs)):
        raise ValueError('predictions must be finite and cover all 1,593 test files')
    lines = ['image,prob'] + [f'{n},{p:.10g}' for n, p in zip(names, probs)]
    write_private_atomic(path, '\n'.join(lines) + '\n', stop)


def is_complete(run_dir):
    rec = Path(run_dir) / 'run.json'
    if not rec.exists() or not (Path(run_dir) / 'predictions.csv').exists():
        return False
    try:
        return json.loads(rec.read_text()).get('status') == 'complete'
    except Exception:
        return False


def write_run(paths, run_dir, record, names, probs):
    """predictions first, run.json last (run.json marks completion)."""
    write_predictions(Path(run_dir) / 'predictions.csv', names, probs)
    record = dict(record, status='complete', record_version=RECORD_VERSION,
                  predictions_sha256=sha256_file(Path(run_dir) / 'predictions.csv'),
                  n_predictions=len(names), finished_unix=time.time(), **{'code': code_revision()})
    write_private_atomic(Path(run_dir) / 'run.json', json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record
