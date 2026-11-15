"""Tests for the no-terminal Windows launcher without opening a browser or server."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parent.parent / "Launch Explorer.pyw"
    loader = SourceFileLoader("explorer_launcher", str(path))
    module = module_from_spec(spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


def local_data(root):
    directory = root / "data" / "derived"
    directory.mkdir(parents=True)
    for name in ("events.json", "analysis.json"):
        (directory / name).write_text("{}", encoding="utf-8")


def test_missing_data_explains_how_to_recover(launcher, monkeypatch):
    errors = []
    monkeypatch.setattr(launcher, "fail", errors.append)
    launcher.main()
    assert "analysis files are missing" in errors[0]


def test_existing_viewer_opens_without_starting_another(launcher, monkeypatch):
    local_data(launcher.ROOT)
    opened = []
    monkeypatch.setattr(launcher, "viewer_ready", lambda: True)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("started another server"))
    launcher.main()
    assert opened == ["http://127.0.0.1:5174/?data=local"]


def test_unrelated_server_is_not_reused(launcher, monkeypatch):
    local_data(launcher.ROOT)
    errors = []
    monkeypatch.setattr(launcher, "viewer_ready", lambda: False)
    monkeypatch.setattr(launcher, "port_free", lambda: False)
    monkeypatch.setattr(launcher, "fail", errors.append)
    launcher.main()
    assert "already in use" in errors[0]
