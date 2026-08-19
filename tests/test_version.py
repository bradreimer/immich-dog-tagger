import re
from importlib.metadata import PackageNotFoundError

from immich_dog_tagger import version as version_module
from immich_dog_tagger.version import get_version


def test_get_version_returns_installed_package_version(monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert re.match(r"^\d+\.\d+\.\d+$", get_version())


def test_get_version_falls_back_when_package_metadata_missing(monkeypatch):
    def raise_not_found(_name):
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "_installed_version", raise_not_found)
    monkeypatch.delenv("GIT_COMMIT", raising=False)

    assert get_version() == version_module._FALLBACK_VERSION


def test_get_version_appends_short_commit_sha_when_present(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "a1b2c3d4e5f6")

    version = get_version()

    assert version.endswith("+a1b2c3d")
    assert re.match(r"^\d+\.\d+\.\d+\+[0-9a-f]{7}$", version)


def test_get_version_truncates_commit_sha_to_seven_characters(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "1234567890abcdef")

    assert get_version().split("+", 1)[1] == "1234567"


def test_get_version_ignores_blank_commit_sha(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "   ")

    assert "+" not in get_version()
