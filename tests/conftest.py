"""Pytest configuration for landcover-download tests."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest


def load_landcover_module():
    """Load landcover-download.py as a module."""
    module_name = "landcover_download"
    # Get the directory containing this conftest.py
    tests_dir = Path(__file__).parent
    project_dir = tests_dir.parent
    module_path = project_dir / "landcover-download.py"

    if not module_path.exists():
        raise FileNotFoundError(f"Module file not found: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def landcover_module():
    """Load and return the landcover_download module."""
    return load_landcover_module()


@pytest.fixture
def sample_worldcover_item():
    """Sample STAC item for ESA WorldCover."""
    return {
        "id": "ESA_WorldCover_10m_2021_v200_N39E116",
        "type": "Feature",
        "collection": "esa-worldcover",
        "bbox": [116.0, 39.0, 117.0, 40.0],
        "properties": {
            "datetime": "2021-01-01T00:00:00Z",
        },
        "assets": {
            "map": {
                "href": "https://example.com/worldcover/map.tif",
                "type": "image/tiff",
                "title": "Land Cover Map",
            },
            "input_data": {
                "href": "https://example.com/worldcover/input.tif",
                "type": "image/tiff",
                "title": "Input Data",
            },
        },
    }


@pytest.fixture
def sample_stac_response(sample_worldcover_item):
    """Sample STAC search response."""
    return {
        "type": "FeatureCollection",
        "features": [sample_worldcover_item],
        "links": [],
        "context": {
            "returned": 1,
            "limit": 50,
            "matched": 1,
        },
    }


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests module for testing."""
    class MockResponse:
        def __init__(self, json_data, status_code=200, headers=None):
            self.json_data = json_data
            self.status_code = status_code
            self.headers = headers or {}
            self.text = str(json_data)

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

        def iter_content(self, chunk_size=1):
            yield b"test data chunk"

    class MockSession:
        def __init__(self):
            self.headers = {}
            self.trust_env = False

        def post(self, url, json=None, timeout=None):
            return MockResponse({
                "type": "FeatureCollection",
                "features": [],
                "context": {"returned": 0, "limit": 50, "matched": 0},
            })

        def get(self, url, timeout=None, stream=False):
            if "token" in url:
                return MockResponse({"token": "test-token-123"})
            return MockResponse(b"", headers={"Content-Length": "1024"})

    import requests
    mock_session = MockSession()
    monkeypatch.setattr(requests, "Session", lambda: mock_session)
    return mock_session