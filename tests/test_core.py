import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from wsp_prep import core, cli


def test_metadata_stripped():
    buf = io.BytesIO()
    Image.new('RGB', (8, 8)).save(buf, 'JPEG', icc_profile=b'SECRET_SENTINEL')
    clean = core.load_image_bytes(buf.getvalue())
    out = io.BytesIO()
    clean.save(out, 'PNG')
    assert b'SECRET_SENTINEL' not in out.getvalue()
    assert not Image.open(io.BytesIO(out.getvalue())).info


def test_safe_zip_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('../../bad', 'x')
    with zipfile.ZipFile(buf) as z, pytest.raises(ValueError, match='unsafe'):
        list(core.safe_zip_members(z))


def test_generation_transaction_mapping_reuse(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'check_mfxr', lambda p: None)
    monkeypatch.setattr(core, 'EXPECTED_COUNTS', {'train/good': 1, 'test/good': 1})
    image = io.BytesIO()
    Image.new('RGB', (8, 8)).save(image, 'JPEG')
    archive = tmp_path / 'a.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('MFXR/train/good/a-1.jpg', image.getvalue())
        z.writestr('MFXR/test/good/b-1.jpg', image.getvalue())
    legacy = tmp_path / 'data/pool'
    legacy.mkdir(parents=True)
    (legacy / 'old').write_text('untrusted')
    with pytest.raises(ValueError, match='quarantine'):
        core.inventory_archive(archive, tmp_path)
    assert core.inventory_archive(archive, tmp_path, rebuild=True)['status'] == 'built'
    assert list((tmp_path / 'data/locked/quarantine').glob('*/old'))
    pool = tmp_path / 'data/pool'
    inventory = json.loads((pool.resolve().parent / 'locked/inventory.json').read_text())
    train = inventory['records'][0]
    assert core.digest(pool / train['anonymous_filename'], 'sha256') == train['normalized_sha256']
    assert core.inventory_archive(archive, tmp_path)['status'] == 'reused'
    previous = pool.resolve()
    monkeypatch.setattr(core, '_build_inventory', lambda *args: (_ for _ in ()).throw(ValueError('failure')))
    with pytest.raises(ValueError, match='failure'):
        core.inventory_archive(archive, tmp_path, rebuild=True)
    assert pool.resolve() == previous
    (pool / train['anonymous_filename']).write_bytes(b'bad')
    with pytest.raises(ValueError, match='hash'):
        core.inventory_archive(archive, tmp_path)


def test_patient_map_inventory_validation(tmp_path):
    inv = tmp_path / 'inv.json'
    inv.write_text(json.dumps({'records': [{'patient_prefix': 'a', 'split': 'train', 'label': 'good'}, {'patient_prefix': 'b', 'split': 'train', 'label': 'anomaly'}]}))
    path = tmp_path / 'map.json'
    rows = [{'source_prefix': p, 'patient_id': p, 'split': 'train', 'label': l, 'reviewed': True} for p, l in [('a','good'), ('b','anomaly')]]
    def check(value):
        path.write_text(json.dumps(value))
        return core.validate_patient_map(path, inv)
    assert check(rows)['valid']
    for bad in ([], rows[:1], [rows[0], {**rows[1], 'patient_id': 'a'}], [rows[0], {**rows[1], 'patient_id': ''}], [rows[0], {**rows[1], 'label': 'good'}], rows + [{**rows[0], 'source_prefix': 'extra'}]):
        with pytest.raises(ValueError):
            check(bad)


def test_fresh_mfxr_figshare_md5(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'figshare_file', lambda *a: {'computed_md5': core.MFXR_MD5, 'supplied_md5': core.MFXR_MD5, 'download_url': 'https://example.com/file'})
    called = []
    monkeypatch.setattr(core, 'atomic_download', lambda *a, **kw: called.append(kw))
    core.fetch_mfxr(tmp_path)
    assert called[0]['expected']['md5'] == core.MFXR_MD5


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a/b', '..'])
def test_external_manifest_path_rejected(tmp_path, name):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'datasets': [{'name': name, 'files': [{'name': 'a.zip'}]}]}))
    with pytest.raises(ValueError, match='unsafe'):
        core.download_external(manifest, tmp_path)


def test_external_symlink_rejected(tmp_path):
    (tmp_path / 'data').symlink_to(tmp_path, target_is_directory=True)
    manifest = tmp_path / 'm.json'
    manifest.write_text(json.dumps({'datasets': [{'name': 'ok', 'files': [{'name': 'a.zip'}]}]}))
    with pytest.raises(ValueError, match='symlink'):
        core.download_external(manifest, tmp_path)


def test_cli_url_redaction(tmp_path, monkeypatch, capsys):
    def fail(_):
        raise RuntimeError('failure https://example.com/file?token=secret')
    monkeypatch.setattr(cli, 'download_models', fail)
    assert cli.main(['--root', str(tmp_path), 'models']) == 1
    assert 'secret' not in capsys.readouterr().err


def test_patient_cross_split_and_unreviewed(tmp_path):
    inv = tmp_path / 'i.json'
    inv.write_text(json.dumps({'records': [{'patient_prefix': 'a', 'split': 'train', 'label': 'good'}, {'patient_prefix': 'b', 'split': 'test', 'label': 'good'}]}))
    rows = [{'source_prefix': p, 'patient_id': 'same', 'split': s, 'label': 'good', 'reviewed': True} for p, s in [('a', 'train'), ('b', 'test')]]
    path = tmp_path / 'map.json'
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='leaks'):
        core.validate_patient_map(path, inv)
    rows[0]['reviewed'] = False
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='reviewed'):
        core.validate_patient_map(path, inv)


def test_archive_member_size_cap():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('small', 'x')
    with zipfile.ZipFile(buf) as z:
        z.infolist()[0].file_size = 101 * 1024**2
        with pytest.raises(ValueError, match='resource limit'):
            list(core.safe_zip_members(z))
