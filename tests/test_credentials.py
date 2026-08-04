import os

from app import credentials, state


def test_save_creates_file_and_parent_dir(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "credentials.env"
    monkeypatch.delenv("LIBRE_EMAIL", raising=False)
    monkeypatch.delenv("LIBRE_PASSWORD", raising=False)

    credentials.save("user@example.com", "hunter2", path=path)

    assert path.exists()


def test_save_then_load_round_trips_into_environ(tmp_path, monkeypatch):
    path = tmp_path / "credentials.env"
    monkeypatch.delenv("LIBRE_EMAIL", raising=False)
    monkeypatch.delenv("LIBRE_PASSWORD", raising=False)

    credentials.save("user@example.com", "hunter2", path=path)
    monkeypatch.delenv("LIBRE_EMAIL", raising=False)
    monkeypatch.delenv("LIBRE_PASSWORD", raising=False)
    credentials.load(path=path)

    assert os.environ["LIBRE_EMAIL"] == "user@example.com"
    assert os.environ["LIBRE_PASSWORD"] == "hunter2"


def test_blank_password_on_save_keeps_existing_password(tmp_path, monkeypatch):
    path = tmp_path / "credentials.env"
    monkeypatch.delenv("LIBRE_EMAIL", raising=False)
    monkeypatch.delenv("LIBRE_PASSWORD", raising=False)

    credentials.save("user@example.com", "hunter2", path=path)
    credentials.save("user@example.com", None, path=path)

    monkeypatch.delenv("LIBRE_EMAIL", raising=False)
    monkeypatch.delenv("LIBRE_PASSWORD", raising=False)
    credentials.load(path=path)

    assert os.environ["LIBRE_PASSWORD"] == "hunter2"


def test_save_advances_generation(tmp_path):
    path = tmp_path / "credentials.env"
    before = credentials.get_generation()

    credentials.save("user@example.com", "hunter2", path=path)

    assert credentials.get_generation() == before + 1


def test_load_is_a_noop_when_file_missing(tmp_path, monkeypatch):
    path = tmp_path / "does-not-exist.env"
    monkeypatch.delenv("LIBRE_EMAIL", raising=False)

    credentials.load(path=path)

    assert "LIBRE_EMAIL" not in os.environ


def test_mark_attempted_updates_attempted_generation():
    credentials.mark_attempted(5)

    assert credentials.get_attempted_generation() == 5


def test_connection_status_is_pending_before_fetch_loop_retries(monkeypatch):
    monkeypatch.setattr(credentials, "_generation", 2)
    monkeypatch.setattr(credentials, "_attempted_generation", 1)

    assert credentials.connection_status() == {"status": "pending"}


def test_connection_status_is_pending_even_if_error_is_a_stale_none(monkeypatch):
    # Regression test: a leftover `None` from the *previous* successful
    # connection must not be reported as success just because the current
    # generation hasn't actually been retried yet - this was the bug where
    # entering a wrong password still showed "Connected."
    monkeypatch.setattr(credentials, "_generation", 2)
    monkeypatch.setattr(credentials, "_attempted_generation", 1)
    monkeypatch.setattr(state, "_error", None)

    assert credentials.connection_status() == {"status": "pending"}


def test_connection_status_is_error_once_retried_and_failed(monkeypatch):
    monkeypatch.setattr(credentials, "_generation", 2)
    monkeypatch.setattr(credentials, "_attempted_generation", 2)
    monkeypatch.setattr(state, "_error", "401 Client Error: Unauthorized")

    assert credentials.connection_status() == {
        "status": "error",
        "error": "401 Client Error: Unauthorized",
    }


def test_connection_status_is_ok_once_retried_and_succeeded(monkeypatch):
    monkeypatch.setattr(credentials, "_generation", 2)
    monkeypatch.setattr(credentials, "_attempted_generation", 2)
    monkeypatch.setattr(state, "_error", None)

    assert credentials.connection_status() == {"status": "ok"}
