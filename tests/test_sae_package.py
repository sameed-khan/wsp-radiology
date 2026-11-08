import pytest

from wsp_arms.sae_package import copy_pool_artifact


def test_only_explicit_pool_safe_artifacts_cross_boundary(tmp_path):
    src = tmp_path / 'source'
    dst = tmp_path / 'destination'
    src.mkdir()
    dst.mkdir()
    (src / 'norm.json').write_text('{}')
    (src / 'test_mean_latents.npy').write_bytes(b'private')
    copy_pool_artifact(src, dst, 'norm.json')
    assert (dst / 'norm.json').read_text() == '{}'
    with pytest.raises(AssertionError):
        copy_pool_artifact(src, dst, 'test_mean_latents.npy')
    with pytest.raises(AssertionError):
        copy_pool_artifact(src, dst, 'sae.json')
    assert not (dst / 'test_mean_latents.npy').exists()
