"""Clustered evaluation of binary predictions."""
import numpy as np


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float('nan')
    ordered = np.sort(neg)
    return float(np.mean((np.searchsorted(ordered, pos, side='left') + np.searchsorted(ordered, pos, side='right')) / (2 * len(neg))))


def metrics(y, p, patient, threshold):
    y, p, patient = np.asarray(y), np.asarray(p), np.asarray(patient)
    unique = np.unique(patient)
    py, pp = [], []
    for ident in unique:
        mask = patient == ident
        py.append(int(np.max(y[mask])))
        pp.append(float(np.max(p[mask])))
    positive, negative = y == 1, y == 0
    bins = np.minimum((p * 15).astype(int), 14)
    ece = sum(np.sum(bins == b) / len(y) * abs(np.mean(p[bins == b]) - np.mean(y[bins == b])) for b in range(15) if np.any(bins == b))
    return {'auroc': auc(y, p), 'patient_auroc': auc(py, pp),
            'sensitivity': float(np.mean(p[positive] >= threshold)) if positive.any() else float('nan'),
            'specificity': float(np.mean(p[negative] < threshold)) if negative.any() else float('nan'),
            'brier': float(np.mean((p-y)**2)), 'ece': float(ece)}


def bootstrap(runs, iterations=2000, seed=0, other=None):
    """Runs are (labels, probabilities, patient IDs, threshold) on identical images."""
    y, _, patient, _ = runs[0][:4]
    patient = np.asarray(patient)
    patients = np.unique(patient)
    if not len(patients):
        raise ValueError('empty dataset')
    for run in runs + (other or []):
        if (not np.array_equal(run[0], y) or not np.array_equal(run[2], patient)
                or (len(run) > 4 and len(runs[0]) > 4 and not np.array_equal(run[4], runs[0][4]))
                or (len(run) > 4) != (len(runs[0]) > 4)):
            raise ValueError('runs must contain identical ordered images and labels')
    def calc(run, idx=None, ids=None):
        a, b, c, t = run[:4]
        if idx is None:
            return metrics(a, b, c, t)
        return metrics(np.asarray(a)[idx], np.asarray(b)[idx], ids, t)
    def point(rs):
        values = [calc(r) for r in rs]
        return {k: float(np.mean([v[k] for v in values])) for k in values[0]}
    result = point(runs)
    if other:
        baseline = point(other)
        result = {k: result[k] - baseline[k] for k in result}
    samples = {k: [] for k in result}
    rng = np.random.default_rng(seed)
    indices = [np.flatnonzero(patient == p) for p in patients]
    for _ in range(iterations):
        chosen = rng.integers(len(patients), size=len(patients))
        idx = np.concatenate([indices[i] for i in chosen])
        ids = np.repeat(np.arange(len(chosen)), [len(indices[i]) for i in chosen])
        val = calc(runs[rng.integers(len(runs))], idx, ids)
        if other:
            b = calc(other[rng.integers(len(other))], idx, ids)
            val = {k: val[k]-b[k] for k in val}
        for k, v in val.items():
            if np.isfinite(v): samples[k].append(v)
    return {k: {'estimate': v if np.isfinite(v) else None, 'ci': np.percentile(samples[k], [2.5, 97.5]).tolist() if samples[k] else None, 'valid_replicates': len(samples[k])} for k, v in result.items()}
