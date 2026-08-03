import os

from app import credentials


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
