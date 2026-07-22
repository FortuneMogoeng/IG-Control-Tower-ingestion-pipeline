"""
Pytest configuration for the IG Control Tower ingestion smoke suite.

Integration tests (marked `integration`) need a live Azure connection and are
skipped unless `--run-integration` is passed AND
AZURE_STORAGE_CONNECTION_STRING is set. Everything else runs offline.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Make the pipeline modules importable without installing the repo as a package.
for p in (
    ROOT / "scripts",
    ROOT / "scripts" / "parsers",
    ROOT / "azure" / "document-parser-fn",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that require a live Azure connection",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: needs live Azure (--run-integration + "
        "AZURE_STORAGE_CONNECTION_STRING)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="needs --run-integration + Azure connection")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return ROOT / "tests" / "fixtures"
