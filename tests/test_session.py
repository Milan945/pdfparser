import time
from pathlib import Path
import pytest
from api.session import store_session, get_session, delete_session, cleanup_old_sessions


@pytest.fixture
def tmp_pdf(tmp_path):
    f = tmp_path / "bill.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    return f


def test_store_and_retrieve(tmp_pdf):
    store_session("abc", tmp_pdf)
    assert get_session("abc") == tmp_pdf


def test_get_missing_returns_none():
    assert get_session("does-not-exist") is None


def test_delete_removes_entry_and_file(tmp_pdf):
    store_session("del1", tmp_pdf)
    delete_session("del1")
    assert get_session("del1") is None
    assert not tmp_pdf.exists()


def test_delete_missing_session_is_noop():
    delete_session("no-such-session")  # must not raise


def test_cleanup_old_sessions_removes_expired(tmp_path):
    old_file = tmp_path / "old.pdf"
    old_file.write_bytes(b"%PDF")
    store_session("old1", old_file)
    # Force the stored timestamp to be old
    from api import session as sess_module
    sess_module._sessions["old1"] = (old_file, time.time() - 7200)
    cleanup_old_sessions(max_age_seconds=3600)
    assert get_session("old1") is None
    assert not old_file.exists()


def test_cleanup_keeps_fresh_sessions(tmp_path):
    fresh_file = tmp_path / "fresh.pdf"
    fresh_file.write_bytes(b"%PDF")
    store_session("fresh1", fresh_file)
    cleanup_old_sessions(max_age_seconds=3600)
    assert get_session("fresh1") == fresh_file
