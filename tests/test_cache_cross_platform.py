"""Regression: LF/CRLF file endings must not invalidate a valid ensemble."""
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from api import _cache_is_current


def test_raw_windows_ensemble_hash_is_accepted(tmp_path):
    content = b"foo: 1\r\nbar: 2\r\n"
    (tmp_path / "soil.yaml").write_bytes(content)
    meta = {"hash_file_parametri": {"soil.yaml": hashlib.sha256(content).hexdigest()}}
    with patch("api.config.PARAMS_DIR", tmp_path):
        assert _cache_is_current(meta)


def test_pilot_unix_hash_is_accepted_with_windows_files(tmp_path):
    (tmp_path / "soil.yaml").write_bytes(b"foo: 1\r\nbar: 2\r\n")
    meta = {"hash_file_parametri": {"soil.yaml": hashlib.sha256(b"foo: 1\nbar: 2\n").hexdigest()}}
    with patch("api.config.PARAMS_DIR", tmp_path):
        assert _cache_is_current(meta)


def test_changed_scientific_parameter_is_rejected(tmp_path):
    (tmp_path / "soil.yaml").write_bytes(b"foo: 999\r\nbar: 2\r\n")
    meta = {"hash_file_parametri": {"soil.yaml": hashlib.sha256(b"foo: 1\nbar: 2\n").hexdigest()}}
    with patch("api.config.PARAMS_DIR", tmp_path):
        assert not _cache_is_current(meta)
