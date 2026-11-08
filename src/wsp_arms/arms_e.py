"""Arm E: scripted interpretability-style classifier search (difference-of-means direction + 1-D calibration).

Candidate feature sets: raw CLS (where stored) and raw patch-mean at every stored layer, plus mean SAE latent
activations (SAE trained once per encoder at 2/3 depth; see sae_train.py). Classifier: difference-of-means
direction from the k labels on standardized features (SAE: top-m latents by |mean difference|, m in {8,32,128});
score = projection; 1-D logistic calibration on the k labels. Search over layer x feature set x m x whitening
{none, diagonal} by patient-grouped CV AUROC on the k labels; ties -> simplest.
"""
from __future__ import annotations

import json
import time

import numpy as np

from . import core
from .arms_ac import Constant, class_patient_counts, _record_base

M_GRID = (8, 32, 128)
WHITEN = ('none', 'diagonal')
DIAG_SHRINK = 0.1        # diagonal whitening divides by (within-class variance + 0.1) on the standardized scale
SD_FLOOR_REL = 1e-3      # std floor = 1e-3 * median positive std (SAE latents); constant columns -> std 1
CAL_C = 10.0             # 1-D calibration LR (L2, on z-scored score)
TIE_TOL = 1e-9


def stored_sets(paths, enc):
    """[(kind, layer)] of raw feature sets present for both pool and test dirs, ordered by depth."""
    out = []
    for kind in ('cls', 'patch_mean'):
        for f in sorted(paths.pool_features(enc).glob(f'{kind}-*.npy'), key=lambda p: int(p.stem.split('-')[1])):
            layer = int(f.stem.split('-')[1])
            if (paths.test_features(enc) / f.name).exists():
                out.append((kind, layer))
    if not out:
        raise FileNotFoundError('no stored layer features')
    return out


def config_key(cfg):
    """Simplicity order: raw < SAE; smaller m; no whitening < diagonal; CLS < patch-mean; deeper layer first."""
    kind, layer, m, wh = cfg
    return (kind == 'sae', m or 0, wh == 'diagonal', kind == 'patch_mean', -layer)


def all_configs(sets, sae_layer):
    cfgs = [(k, l, None, wh) for (k, l) in sets for wh in WHITEN]
    cfgs += [('sae', sae_layer, m, wh) for m in M_GRID for wh in WHITEN]
    return cfgs


class FeatureSet:
    def __init__(self, kind, layer, Xp, Xt):
        self.kind, self.layer, self.Xp, self.Xt = kind, layer, Xp, Xt


def _standardize_stats(X):
    mu = X.mean(0)
    sd = X.std(0)
    pos = sd[sd > 1e-8]
    floor = SD_FLOOR_REL * float(np.median(pos)) if len(pos) else 1.0
    sd = np.where(sd > 1e-8, np.maximum(sd, floor), 1.0)
    return mu, sd


def dom_direction(Xs, y, m, whiten):
    """Difference-of-means direction on standardized training features. Returns weight vector (zero outside top-m)."""
    d = Xs[y == 1].mean(0) - Xs[y == 0].mean(0)
    if whiten == 'diagonal':
        var = (((Xs[y == 1] - Xs[y == 1].mean(0)) ** 2).sum(0) + ((Xs[y == 0] - Xs[y == 0].mean(0)) ** 2).sum(0)) / max(len(y) - 2, 1)
        d = d / (var + DIAG_SHRINK)
    if m is not None and m < len(d):
        keep = np.argsort(-np.abs(Xs[y == 1].mean(0) - Xs[y == 0].mean(0)), kind='stable')[:m]
        w = np.zeros_like(d)
        w[keep] = d[keep]
        d = w
    return d


class Model:
    def __init__(self, mu, sd, w, cal_mu, cal_sd, lr):
        self.mu, self.sd, self.w, self.cal_mu, self.cal_sd, self.lr = mu, sd, w, cal_mu, cal_sd, lr

    def score(self, X):
        return ((X - self.mu) / self.sd) @ self.w

    def predict_proba(self, X):
        z = ((self.score(X) - self.cal_mu) / self.cal_sd).reshape(-1, 1)
        return self.lr.predict_proba(z)[:, 1]


def fit_model(X, y, m, whiten):
    from sklearn.linear_model import LogisticRegression
    y = np.asarray(y)
    if len(set(y.tolist())) < 2:
        return Constant(y.mean())
    mu, sd = _standardize_stats(X)
    Xs = (X - mu) / sd
    w = dom_direction(Xs, y, m, whiten)
    s = Xs @ w
    cal_mu, cal_sd = float(s.mean()), float(s.std()) or 1.0
    lr = LogisticRegression(C=CAL_C, max_iter=1000).fit(((s - cal_mu) / cal_sd).reshape(-1, 1), y)
    return Model(mu, sd, w, cal_mu, cal_sd, lr)


def cv_oof(X, y, folds, m, whiten):
    oof = np.full(len(y), np.nan)
    for held in folds:
        tr = np.setdiff1d(np.arange(len(y)), held)
        oof[held] = fit_model(X[tr], y[tr], m, whiten).predict_proba(X[held])
    return oof


def _load_sets(paths, enc, rows, sets):
    out = {}
    pdir, tdir = paths.pool_features(enc), paths.test_features(enc)
    for kind, layer in sets:
        Xp = np.load(pdir / f'{kind}-{layer}.npy').astype(np.float32, copy=False)[rows]
        Xt = np.load(tdir / f'{kind}-{layer}.npy').astype(np.float32, copy=False)
        out[(kind, layer)] = (Xp, Xt)
    return out


def run(arm, enc, k, r, paths=None, force=False):
    assert arm == 'E'
    from . import sae_train
    paths = paths or core.Paths.default()
    k = core.parse_k(k)
    run_dir = paths.run_dir('E', enc, k, r)
    if not force and core.is_complete(run_dir):
        return json.loads((run_dir / 'run.json').read_text())
    t0 = time.monotonic()
    alloc = core.load_allocation(paths, k, r)
    pool = core.load_features(paths.pool_features(enc))
    test = core.load_test_features(paths, enc)
    rows = pool.rows(alloc.images)
    y, patients = alloc.labels, np.array(alloc.patients)
    sdir = sae_train.sae_dir(paths, enc)
    sae_meta = json.loads((sdir / 'sae.json').read_text())
    sae_layer = sae_meta['layer']
    # SAE latents must be aligned to the same file order as the feature indices
    if sae_meta['pool_names_sha256'] != core.sha256_text(pool.names) or sae_meta['test_names_sha256'] != core.sha256_text(test.names):
        raise ValueError('SAE latent file order does not match feature indices')
    sets = stored_sets(paths, enc)
    data = _load_sets(paths, enc, rows, sets)
    sae_p = np.load(sdir / 'pool_mean_latents.npy')[rows]
    sae_t = np.load(sdir / 'test_mean_latents.npy')
    data[('sae', sae_layer)] = (sae_p, sae_t)
    t_load = time.monotonic() - t0

    rec = _record_base('E', enc, alloc, paths, pool, test, run_dir)
    rec['features'] = {'sets': [f'{a}-{b}' for a, b in sets] + [f'sae-{sae_layer}'], 'sae_sha256': sae_meta['sae_sha256'],
                       'pool_index_sha256': pool.index_sha256, 'test_index_sha256': test.index_sha256}
    n0, n1 = class_patient_counts(patients, y)
    rec['n_train_patients_by_class'] = {'0': n0, '1': n1}
    folds = core.make_folds(patients, y, alloc.seed)
    rec['cv'] = {'scheme': 'LOPO' if len(set(patients.tolist())) <= 20 else '5-fold', 'n_folds': len(folds), 'grouping': 'patient'}
    rec['config'] = {'m_grid': list(M_GRID), 'whitening': list(WHITEN), 'diag_shrink': DIAG_SHRINK, 'sd_floor_rel': SD_FLOOR_REL,
                     'calibration': f'1-D L2 logistic regression C={CAL_C} on z-scored score',
                     'selection': 'patient-grouped CV AUROC (pooled OOF calibrated probs); ties (1e-9) -> simplest: raw<SAE, smaller m, no whitening<diagonal, CLS<patch-mean, deeper layer'}
    if min(n0, n1) == 0:
        prior = float(y.mean())
        rec.update(single_class=True, constant_prior=prior, selected=None, threshold=0.5, threshold_method='fixed_0.5_single_class',
                   oof_metrics=None, note='single-class allocation: constant training class prior')
        probs = np.full(len(test.names), prior)
        rec['timings_sec'] = {'load': t_load, 'cv': 0.0, 'fit': 0.0, 'total': time.monotonic() - t0}
        return core.write_run(paths, run_dir, rec, test.names, probs)

    t1 = time.monotonic()
    cfgs = all_configs(sets, sae_layer)
    oofs, aucs = {}, {}
    for cfg in cfgs:
        kind, layer, m, wh = cfg
        X = data[(kind, layer)][0]
        oofs[cfg] = cv_oof(X, y, folds, m, wh)
        a = core.auroc(y, oofs[cfg])
        aucs[cfg] = -1.0 if a is None else a
    best = max(aucs.values())
    cands = [c for c in cfgs if aucs[c] >= best - TIE_TOL]
    sel = min(cands, key=config_key)
    t2 = time.monotonic()
    thr, method, J = core.threshold_from_oof(y, oofs[sel])
    kind, layer, m, wh = sel
    model = fit_model(data[(kind, layer)][0], y, m, wh)
    probs = model.predict_proba(data[(kind, layer)][1])
    sel_d = {'feature_set': kind, 'layer': layer, 'm': m, 'whitening': wh}
    rec.update(single_class=False, selected=sel_d, n_tied_candidates=len(cands), threshold=thr, threshold_method=method,
               cv_auroc_by_config={f'{c[0]}-{c[1]}|m={c[2]}|{c[3]}': round(aucs[c], 6) for c in cfgs},
               oof_metrics={'auroc': core.auroc(y, oofs[sel]), 'logloss': core.logloss(y, oofs[sel]), 'youden_J': J, 'n': int(len(y)),
                            'note': 'out-of-fold on the k labeled patients only; selected-config OOF is optimistically biased by the search'})
    if isinstance(model, Model) and kind == 'sae':
        nz = np.flatnonzero(model.w)
        rec['selected_latents'] = [int(i) for i in nz[np.argsort(-np.abs(model.w[nz]))][:128]]
    rec['timings_sec'] = {'load': t_load, 'cv': t2 - t1, 'fit': time.monotonic() - t2, 'total': time.monotonic() - t0}
    return core.write_run(paths, run_dir, rec, test.names, probs)
