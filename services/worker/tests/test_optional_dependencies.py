import tomllib
from pathlib import Path


def test_scrapling_runtime_extra_installs_supported_fetchers() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    dependencies = project["project"]["optional-dependencies"]["scrapling"]
    assert any(item.startswith("scrapling[fetchers]") for item in dependencies)


def test_installed_scrapling_extra_can_load_all_supported_fetchers() -> None:
    import importlib.util

    import pytest

    if importlib.util.find_spec("scrapling") is None:
        pytest.skip("optional Scrapling runtime is not installed")
    from scrapling.fetchers import AsyncFetcher, DynamicFetcher, Fetcher

    assert Fetcher is not None
    assert AsyncFetcher is not None
    assert DynamicFetcher is not None
