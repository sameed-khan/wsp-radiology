"""Arm A (L2 logistic regression on frozen pooled features) and arm C (self-training on top of A)."""
from __future__ import annotations

import time

import numpy as np

from . import core

SELF_TRAIN = dict(rounds=5, frac_per_side=0.10, cap=0.50, pseudo_weight=0.5)


class Constant:
    """Single-class training set: constant prior."""
    def __init__(self, prior):
        self.prior = float(prior)

    def predict_proba(self, X):
        return np.full(len(X), self.prior)


class LR:
    def __init__(self, scaler, clf):
        self.scaler, self.clf = scaler, clf

    def predict_proba(self, X):
        return self.clf.predict_proba(self.scaler.transform(X))[:, 1]


def fit_lr(X, y, C, w=None):
    """Standardize + L2 LR. If training labels are single-class, return the class prior."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    y = np.asarray(y)
    if len(set(y.tolist())) < 2:
        return Constant(np.average(y, weights=w))
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(C=C, max_iter=2000)
    clf.fit(sc.transform(X), y, sample_weight=w)
    return LR(sc, clf)


def class_patient_counts(patients, y):
    pl = {}
    for p, l in zip(patients, y):
        pl[p] = int(l)
    n1 = sum(pl.values())
    return len(pl) - n1, n1


def oof_predict(X, y, folds, fit_predict):
    oof = np.full(len(y), np.nan)
    for held in folds:
        train = np.setdiff1d(np.arange(len(y)), held)
        oof[held] = fit_predict(train, held)
    return oof


def choose_C(X, y, patients, folds):
    """Patient-grouped CV log-loss over C_GRID. Returns (C, {C: logloss}, {C: oof})."""
    n0, n1 = class_patient_counts(patients, y)
    if min(n0, n1) < 2:
        return 1.0, {}, {}
    losses, oofs = {}, {}
    for C in core.C_GRID:
        oof = oof_predict(X, y, folds, lambda tr, te: fit_lr(X[tr], y[tr], C).predict_proba(X[te]))
        losses[C], oofs[C] = core.logloss(y, oof), oof
    best = min(core.C_GRID, key=lambda c: (losses[c], c))
    return best, losses, oofs


def self_train(Xl, yl, Xu, C, cfg=SELF_TRAIN, Xeval=None):
    """Self-training (arm C). Pseudo-labels are sticky and cumulative: each round adds the
    top `frac_per_side` and bottom `frac_per_side` (of the unlabeled pool size) of the
    still-unlabeled images by current predicted probability, until pseudo-labels reach `cap` of the pool.
    Returns (model, info)."""
    model = fit_lr(Xl, yl, C)
    info = {'rounds': []}
    n_u = len(Xu)
    if n_u == 0 or isinstance(model, Constant):
        return model, dict(info, skipped='no unlabeled pool' if n_u == 0 else 'single-class labels')
    per_side = int(np.ceil(cfg['frac_per_side'] * n_u))
    cap = int(np.floor(cfg['cap'] * n_u))
    remaining = np.arange(n_u)
    pidx, plab = np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    for rd in range(cfg['rounds']):
        room = cap - len(pidx)
        if room <= 0 or len(remaining) < 2:
            info['rounds'].append({'round': rd + 1, 'added_pos': 0, 'added_neg': 0, 'total': int(len(pidx))})
            continue
        n_side = min(per_side, room // 2, len(remaining) // 2)
        if n_side == 0:
            info['rounds'].append({'round': rd + 1, 'added_pos': 0, 'added_neg': 0, 'total': int(len(pidx))})
            continue
        p = model.predict_proba(Xu[remaining])
        order = np.argsort(p, kind='stable')
        neg, pos = remaining[order[:n_side]], remaining[order[-n_side:]]
        pidx = np.concatenate([pidx, neg, pos])
        plab = np.concatenate([plab, np.zeros(n_side, dtype=np.int64), np.ones(n_side, dtype=np.int64)])
        remaining = np.setdiff1d(remaining, np.concatenate([neg, pos]))
        X = np.concatenate([Xl, Xu[pidx]])
        y = np.concatenate([yl, plab])
        w = np.concatenate([np.ones(len(yl)), np.full(len(pidx), cfg['pseudo_weight'])])
        model = fit_lr(X, y, C, w)
        info['rounds'].append({'round': rd + 1, 'added_pos': int(n_side), 'added_neg': int(n_side), 'total': int(len(pidx))})
    info['n_pseudo'] = int(len(pidx))
    info['n_unlabeled'] = int(n_u)
    return model, info


def _record_base(arm, enc, alloc, paths, pool, test, run_dir):
    return {
        'arm': arm, 'encoder': enc, 'k': alloc.k, 'r': alloc.r,
        'allocation_seed': alloc.seed, 'allocation_sha256': alloc.sha256,
        'n_train_patients': len(alloc.patient_ids), 'n_train_images': len(alloc.images),
        'n_train_pos_images': int(alloc.labels.sum()),
        'train_image_list_sha256': core.sha256_text(alloc.images),
        'features': {'name': 'pooled', 'pool_index_sha256': pool.index_sha256, 'pool_pooled_sha256': pool.pooled_sha256,
                     'test_index_sha256': test.index_sha256, 'test_pooled_sha256': test.pooled_sha256},
    }


def run(arm, enc, k, r, paths=None, force=False):
    """Run arm 'A' or 'C' for one (enc, k, r); writes predictions.csv + run.json. Returns record."""
    paths = paths or core.Paths.default()
    k = core.parse_k(k)
    run_dir = paths.run_dir(arm, enc, k, r)
    if not force and core.is_complete(run_dir):
        import json
        return json.loads((run_dir / 'run.json').read_text())
    t0 = time.monotonic()
    alloc = core.load_allocation(paths, k, r)
    pool = core.load_features(paths.pool_features(enc))
    test = core.load_test_features(paths, enc)
    rows = pool.rows(alloc.images)
    Xl, y, patients = pool.X[rows], alloc.labels, np.array(alloc.patients)
    seed = alloc.seed
    t_load = time.monotonic() - t0

    rec = _record_base(arm, enc, alloc, paths, pool, test, run_dir)
    n0, n1 = class_patient_counts(patients, y)
    rec['n_train_patients_by_class'] = {'0': n0, '1': n1}
    single = min(n0, n1) == 0
    folds = core.make_folds(patients, y, seed)
    rec['cv'] = {'scheme': 'LOPO' if len(set(patients.tolist())) <= 20 else '5-fold', 'n_folds': len(folds), 'grouping': 'patient'}
    t1 = time.monotonic()
    if single:
        prior = float(y.mean())
        probs = np.full(len(test.names), prior)
        rec.update(single_class=True, constant_prior=prior, C=None, threshold=0.5, threshold_method='fixed_0.5_single_class',
                   oof_metrics=None, note='single-class allocation: constant training class prior (AUROC 0.5 by construction)')
        timings = {'cv': 0.0, 'fit': 0.0}
    else:
        C, losses, oofs = choose_C(Xl, y, patients, folds)
        rec.update(single_class=False, C=C, C_selection='grouped_cv_logloss' if losses else 'default_C=1 (<2 patients in a class)',
                   cv_logloss_by_C={str(c): v for c, v in losses.items()})
        if arm == 'A':
            if losses:
                oof = oofs[C]
            else:
                oof = oof_predict(Xl, y, folds, lambda tr, te: fit_lr(Xl[tr], y[tr], C).predict_proba(Xl[te]))
            Xu = None
        elif arm == 'C':
            unl_mask = np.ones(len(pool.names), dtype=bool)
            unl_mask[rows] = False
            Xu = pool.X[unl_mask]
            rec['self_training'] = dict(SELF_TRAIN, n_unlabeled_pool=int(len(Xu)),
                                        note='pseudo-labels sticky/cumulative; per-side count = ceil(0.1*pool) per round, total capped at 50% of pool; scaler refit each round')
            oof = oof_predict(Xl, y, folds, lambda tr, te: self_train(Xl[tr], y[tr], Xu, C)[0].predict_proba(Xl[te]))
        else:
            raise ValueError(arm)
        thr, method, J = core.threshold_from_oof(y, oof)
        t2 = time.monotonic()
        rec.update(threshold=thr, threshold_method=method,
                   oof_metrics={'auroc': core.auroc(y, oof), 'logloss': core.logloss(y, oof), 'youden_J': J, 'n': int(len(y)),
                                'note': 'out-of-fold on the k labeled patients only'})
        if arm == 'A':
            model = fit_lr(Xl, y, C)
        else:
            model, info = self_train(Xl, y, Xu, C)
            rec['self_training']['final'] = info
        probs = model.predict_proba(test.X)
        timings = {'cv': t2 - t1, 'fit': time.monotonic() - t2}
    rec['timings_sec'] = dict(timings, load=t_load, total=time.monotonic() - t0)
    rec['sample_weights'] = {'labeled': 1.0, 'pseudo': SELF_TRAIN['pseudo_weight']} if arm == 'C' else None
    rec['config'] = {'C_grid': list(core.C_GRID), 'standardize': True, 'penalty': 'l2', 'solver': 'lbfgs', 'max_iter': 2000}
    return core.write_run(paths, run_dir, rec, test.names, probs)
