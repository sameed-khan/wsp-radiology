"""Arm D training from the preregistered pseudo-label cache; never reads test labels."""
from __future__ import annotations

import json
import time
import numpy as np
from . import arm_b, arm_d_labels, arms_ac, core


def load_cache(paths, allow_partial=False):
    pool = {p.name: p for p in (paths.root / 'data/pool').glob('*.png')}
    if not pool:
        raise ValueError('pool contains no PNG images')
    cache = paths.private / 'arm-d/labels.jsonl'
    raw = cache.read_bytes() if cache.exists() else b''
    import hashlib
    prompt = hashlib.sha256((paths.root / 'config/arm-d-prompt.md').read_bytes()).hexdigest()
    rows = {}
    for line in raw.splitlines():
        row = json.loads(line)
        name = row['image']
        if name not in pool or name in rows:
            raise ValueError('cache contains unknown or duplicate image')
        if row['model'] != arm_d_labels.MODEL or row['prompt_sha256'] != prompt:
            raise ValueError('cache prompt/model mismatch')
        if row['image_sha256'] != core.sha256_file(pool[name]):
            raise ValueError('cached image content changed')
        p = row['p_monteggia']
        if p is not None and (isinstance(p, bool) or not isinstance(p, (int, float)) or not np.isfinite(p) or not 0 <= p <= 100 or p != int(p)):
            raise ValueError('invalid cached probability')
        rows[name] = None if p is None else p / 100
    missing = len(pool) - len(rows)
    coverage = {'pool': len(pool), 'processed': len(rows), 'successful': sum(v is not None for v in rows.values()),
                'failed_excluded': sum(v is None for v in rows.values()), 'missing': missing,
                'cache_sha256': hashlib.sha256(raw).hexdigest()}
    if missing and not allow_partial:
        raise ValueError(f'incomplete D cache: processed {len(rows)}/{len(pool)}, missing {missing}, failed/excluded {coverage["failed_excluded"]}')
    if not coverage['successful']:
        raise ValueError('D cache has no successful pseudo-labels')
    return {n: p for n, p in rows.items() if p is not None}, coverage


def fit_soft(X, p, C, weights):
    """A's scaler and LR, with soft probabilities represented by weighted binary pairs."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    p, weights = np.asarray(p), np.asarray(weights)
    sc = StandardScaler().fit(X)
    Z = sc.transform(X)
    y = np.tile([0, 1], len(p))
    w = np.column_stack((weights * (1-p), weights * p)).ravel()
    if not np.any(w[y == 0]) or not np.any(w[y == 1]):
        return arms_ac.Constant(np.average(p, weights=weights))
    clf = LogisticRegression(C=C, max_iter=2000)
    clf.fit(np.repeat(Z, 2, axis=0), y, sample_weight=w)
    return arms_ac.LR(sc, clf)


def run(arm, enc, k, r, paths=None, force=False, allow_partial=False, steps=None, micro_batch=None):
    paths = paths or core.Paths.default()
    k = str(k)
    if k != '0':
        k = core.parse_k(k)
    if arm not in ('D-head', 'D-ft') or (arm == 'D-ft' and int(r) != 1):
        raise ValueError('D-ft is restricted to r=1')
    pseudo, coverage = load_cache(paths, allow_partial)
    output_arm = arm + '-partial' if allow_partial else arm
    out = paths.run_dir(output_arm, enc, k, r)
    if not force and core.is_complete(out):
        old = json.loads((out / 'run.json').read_text())
        if old.get('cache_coverage', {}).get('cache_sha256') == coverage['cache_sha256']:
            return old
    (out / 'run.json').unlink(missing_ok=True)
    t0 = time.monotonic()
    alloc = core.load_allocation(paths, k, r) if k != '0' else None
    names = sorted(set(pseudo) | (set(alloc.images) if alloc else set()))
    true = dict(zip(alloc.images, alloc.labels.tolist())) if alloc else {}
    p = np.array([true[n] if n in true else pseudo[n] for n in names], dtype=float)
    weights = np.array([5.0 if n in true else 1.0 for n in names])
    rec = {'arm': arm, 'encoder': enc, 'k': k, 'r': int(r), 'cache_coverage': coverage,
           'allocation_sha256': alloc.sha256 if alloc else None, 'allocation_seed': alloc.seed if alloc else None,
           'training_seed': arm_b.train_seed(k, r), 'train_image_list_sha256': core.sha256_text(names),
           'n_train_images': len(names), 'n_true_images': len(true), 'oof_metrics': None,
           'threshold': 0.5, 'threshold_method': 'fixed_0.5_zero_shot' if not alloc else 'fixed_0.5_class_balanced_finetuned'}
    test_names = sorted(q.name for q in paths.test_png_dir().glob('*.png'))
    if len(test_names) != core.N_TEST:
        raise ValueError('unexpected number of test PNGs')
    single = alloc is not None and len(set(alloc.labels.tolist())) < 2
    if single:
        prior = float(alloc.labels.mean())
        probs = np.full(len(test_names), prior)
        rec.update(single_class=True, constant_prior=prior, threshold_method='fixed_0.5_single_class')
    elif arm == 'D-ft':
        import torch
        labels = (p >= .5).astype(int)
        arm_b.cap_vram()
        model, groups, adapter = arm_b.build_model(enc, 'lora', seed=rec['training_seed'])
        info = arm_b.train_model(model, groups, enc, arm_b.pool_files(paths, names), labels, rec['training_seed'], steps=steps, micro_batch=micro_batch)
        probs = arm_b.predict_files(model, enc, [paths.test_png_dir() / n for n in test_names])
        rec.update(single_class=False, recipe=arm_b.RECIPE, steps=info['steps'], class_weights=arm_b.class_weights(labels),
                   peak_vram_gb=torch.cuda.max_memory_allocated()/2**30,
                   train_loss_all_finite=bool(np.all(np.isfinite(info['losses']))))
        del model, adapter
        torch.cuda.empty_cache()
    else:
        pool = core.load_features(paths.pool_features(enc))
        test = core.load_test_features(paths, enc)
        X = pool.X[pool.rows(names)]
        C, losses = 1.0, {}
        if alloc:
            ix = np.array([names.index(n) for n in alloc.images])
            folds = core.make_folds(alloc.patients, alloc.labels, alloc.seed)
            n0, n1 = arms_ac.class_patient_counts(alloc.patients, alloc.labels)
            def oof(c):
                result = np.empty(len(ix))
                for held in folds:
                    # Held-out patients are excluded entirely, including their pseudo-labels.
                    mask = np.ones(len(names), dtype=bool)
                    mask[ix[held]] = False
                    result[held] = fit_soft(X[mask], p[mask], c, weights[mask]).predict_proba(X[ix[held]])
                return result
            if min(n0, n1) >= 2:
                predictions = {c: oof(c) for c in core.C_GRID}
                losses = {c: core.logloss(alloc.labels, v) for c, v in predictions.items()}
                C = min(core.C_GRID, key=lambda c: (losses[c], c))
                pred = predictions[C]
            else:
                pred = oof(C)
            threshold, method, J = core.threshold_from_oof(alloc.labels, pred)
            rec.update(threshold=threshold, threshold_method=method,
                       oof_metrics={'auroc': core.auroc(alloc.labels, pred), 'logloss': core.logloss(alloc.labels, pred), 'youden_J': J, 'n': len(ix)})
        probs = fit_soft(X, p, C, weights).predict_proba(test.X)
        test_names = test.names
        rec.update(single_class=False, C=C, cv_logloss_by_C={str(c): v for c, v in losses.items()},
                   C_selection='grouped_cv_logloss' if losses else 'default_C=1',
                   sample_weights={'pseudo': 1, 'true': 5}, features={'pool_index_sha256': pool.index_sha256, 'pool_pooled_sha256': pool.pooled_sha256, 'test_index_sha256': test.index_sha256, 'test_pooled_sha256': test.pooled_sha256})
    rec['timings_sec'] = {'total': time.monotonic() - t0}
    return core.write_run(paths, out, rec, test_names, probs)
