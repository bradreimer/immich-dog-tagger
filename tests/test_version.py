import re
from importlib.metadata import PackageNotFoundError

from immich_dog_tagger import version as version_module
from immich_dog_tagger.version import get_version


def test_get_version_returns_installed_package_version():
    assert re.match(r"^\d+\.\d+\.\d+", get_version())


def test_get_version_falls_back_when_package_metadata_missing(monkeypatch):
    def raise_not_found(_name):
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "_installed_version", raise_not_found)

    assert get_version() == version_module._FALLBACK_VERSION
