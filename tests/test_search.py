"""Tests for STAC search functionality."""

import pytest


class TestSTACSearch:
    """Test STAC search functions."""

    def test_stac_search_worldcover(self, landcover_module, mock_requests, sample_stac_response):
        """Test WorldCover STAC search."""
        mock_requests.post = lambda url, json=None, timeout=None: type('MockResponse', (), {
            'json': lambda self: sample_stac_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()
        result = landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        assert "features" in result
        assert len(result["features"]) == 1

    def test_stac_search_bbox(self, landcover_module, mock_requests, sample_stac_response):
        """Test search with different bbox values."""
        captured_json = {}
        original_post = mock_requests.post

        def mock_post(url, json=None, timeout=None):
            captured_json.update(json or {})
            return type('MockResponse', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        assert captured_json.get("bbox") == [116.0, 39.0, 117.0, 40.0]

    def test_stac_search_year_2020(self, landcover_module, mock_requests, sample_stac_response):
        """Test search with year 2020."""
        captured_json = {}
        original_post = mock_requests.post

        def mock_post(url, json=None, timeout=None):
            captured_json.update(json or {})
            return type('MockResponse', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2020,
        )
        assert "2020-01-01" in captured_json.get("datetime", "")

    def test_stac_search_year_2021(self, landcover_module, mock_requests, sample_stac_response):
        """Test search with year 2021."""
        captured_json = {}
        original_post = mock_requests.post

        def mock_post(url, json=None, timeout=None):
            captured_json.update(json or {})
            return type('MockResponse', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        assert "2021-01-01" in captured_json.get("datetime", "")

    def test_stac_search_limit(self, landcover_module, mock_requests, sample_stac_response):
        """Test search with limit parameter."""
        captured_json = {}
        original_post = mock_requests.post

        def mock_post(url, json=None, timeout=None):
            captured_json.update(json or {})
            return type('MockResponse', (), {
                'json': lambda self: sample_stac_response,
                'status_code': 200,
                'raise_for_status': lambda self: None,
            })()

        mock_requests.post = mock_post
        landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
            limit=10,
        )
        assert captured_json.get("limit") == 10

    def test_stac_search_empty_response(self, landcover_module, mock_requests):
        """Test search with empty response."""
        empty_response = {
            "type": "FeatureCollection",
            "features": [],
            "context": {"returned": 0, "limit": 50, "matched": 0},
        }
        mock_requests.post = lambda url, json=None, timeout=None: type('MockResponse', (), {
            'json': lambda self: empty_response,
            'status_code': 200,
            'raise_for_status': lambda self: None,
        })()
        result = landcover_module.stac_search_worldcover(
            bbox=(116.0, 39.0, 117.0, 40.0),
            year=2021,
        )
        assert len(result["features"]) == 0


class TestSigning:
    """Test Planetary Computer signing."""

    def test_get_signed_href(self, landcover_module, monkeypatch, sample_worldcover_item):
        """Test getting signed href."""
        # Clear the SAS cache first
        landcover_module._SAS_CACHE.clear()

        class MockSession:
            def __init__(self):
                self.headers = {}
                self.trust_env = False

            def get(self, url, timeout=None, stream=False):
                return type('MockResponse', (), {
                    'json': lambda self: {"token": "test-token-123"},
                    'status_code': 200,
                    'text': '{"token": "test-token-123"}',
                    'raise_for_status': lambda self: None,
                })()

        import requests
        monkeypatch.setattr(requests, "Session", lambda: MockSession())

        href = landcover_module.get_signed_href(sample_worldcover_item, "map")
        assert href is not None
        assert "test-token-123" in href

    def test_get_signed_href_missing_asset(self, landcover_module, mock_requests, sample_worldcover_item):
        """Test getting signed href for missing asset."""
        href = landcover_module.get_signed_href(sample_worldcover_item, "nonexistent")
        assert href is None

    def test_get_signed_href_caching(self, landcover_module, monkeypatch, sample_worldcover_item):
        """Test that SAS token is cached."""
        call_count = 0

        class MockSession:
            def __init__(self):
                self.headers = {}
                self.trust_env = False

            def get(self, url, timeout=None, stream=False):
                nonlocal call_count
                call_count += 1
                return type('MockResponse', (), {
                    'json': lambda self: {"token": f"token-{call_count}"},
                    'status_code': 200,
                    'text': f'{{"token": "token-{call_count}"}}',
                    'raise_for_status': lambda self: None,
                })()

        import requests
        monkeypatch.setattr(requests, "Session", lambda: MockSession())

        # Clear cache
        landcover_module._SAS_CACHE.clear()

        # First call
        href1 = landcover_module.get_signed_href(sample_worldcover_item, "map")
        # Second call should use cache
        href2 = landcover_module.get_signed_href(sample_worldcover_item, "map")

        assert call_count == 1  # Only one API call due to caching
        assert href1 == href2


class TestDatasetMetadata:
    """Test dataset metadata functions."""

    def test_datasets_dict(self, landcover_module):
        """Test DATASETS dictionary."""
        assert "worldcover" in landcover_module.DATASETS
        assert "from-glc" in landcover_module.DATASETS
        assert "globeland30" in landcover_module.DATASETS

    def test_worldcover_dataset(self, landcover_module):
        """Test WorldCover dataset metadata."""
        wc = landcover_module.DATASETS["worldcover"]
        assert wc["name"] == "ESA WorldCover"
        assert wc["resolution"] == "10m"
        assert 2020 in wc["years"]
        assert 2021 in wc["years"]
        assert "map" in wc["assets"]

    def test_worldcover_classes(self, landcover_module):
        """Test WorldCover classification values."""
        assert landcover_module.WORLDCOVER_CLASSES[10] == "Tree cover"
        assert landcover_module.WORLDCOVER_CLASSES[50] == "Built-up"
        assert landcover_module.WORLDCOVER_CLASSES[80] == "Permanent water bodies"